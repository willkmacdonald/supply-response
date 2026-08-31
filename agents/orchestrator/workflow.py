from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Never
from urllib.parse import unquote

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler
from pydantic import ValidationError

from data.domain.analysis import AnalysisVersion
from data.domain.evidence import AuthorityScope, EvidenceItem
from services.analysis.service import AnalyzeCaseCommand

from .contracts import (
    AgentExplanationUnavailable,
    AnalyzeCommand,
    BoundedEvidence,
    ContextMessage,
    DecisionExplanation,
    DecisionSelection,
    DeterministicMessage,
    ExtractedFacts,
    OrchestrationResult,
    PartialDeterministicResult,
    SignalMessage,
)
from .local import LocalAgentSet

_MAX_PROMPT_CHARS = 16_000
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MODEL_POLICY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_MODEL_COMPARATOR = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MODEL_NUMBER = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(
        r"(?i)\b(?:client[_ -]?secret|obo(?:[_ -]?assertion)?|assertion)\s*[:=]\s*[^\s&,;]+"
    ),
    re.compile(
        r"(?i)\b(?:tenant[_ -]?id|object[_ -]?id|upn|tid|oid)"
        r"\s*(?::|=|\bis\b)\s*[^\s&,;]+"
    ),
    re.compile(r"(?i)https://[^\s/@:]+:[^\s/@]+@[^\s/]+"),
    re.compile(
        r"(?i)[?&](?:access_token|client_secret|assertion|sig|token|code)=[^&#\s]+"
    ),
    re.compile(
        r"(?i)(?<![A-Za-z0-9])(?:x[\s_-]*api[\s_-]*key|api[\s_-]*key|"
        r"password|passwd|pwd|client[\s_-]*secret|secret|token|account[\s_-]*key|"
        r"shared[\s_-]*access[\s_-]*(?:key|signature)|secret[\s_-]*access[\s_-]*key)"
        r"\s*[:=]\s*(?:\"[^\"\r\n]+\"|'[^'\r\n]+'|[^\s,;]+)"
    ),
    re.compile(r"(?i)\bauthorization\s*:\s*(?:basic|bearer)\s+[^\s,;]+"),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@[^\s/]+"),
    re.compile(
        r"(?is)-----BEGIN\s+(?:(?:RSA|EC|DSA|OPENSSH|ENCRYPTED)\s+)?"
        r"PRIVATE\s+KEY-----.*?-----END\s+(?:(?:RSA|EC|DSA|OPENSSH|ENCRYPTED)\s+)?"
        r"PRIVATE\s+KEY-----"
    ),
)
_REDACTED = "[REDACTED]"


def _normalized_sensitive_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\\r\\n", "\n").replace("\\n", "\n")
    for _ in range(2):
        decoded = unquote(normalized)
        if decoded == normalized:
            break
        normalized = decoded
    return normalized


def _contains_sensitive(value: str) -> bool:
    normalized = _normalized_sensitive_text(value)
    return any(pattern.search(normalized) for pattern in _SENSITIVE_PATTERNS)


def _redact_text(value: str) -> str:
    # Redact the complete containing field so encoded or delimiter-adjacent material
    # cannot survive while a matched fragment is replaced.
    return _REDACTED if _contains_sensitive(value) else value


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {_scrub(key): _scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub(item) for item in value)
    if isinstance(value, set):
        return {_scrub(item) for item in value}
    if isinstance(value, frozenset):
        return frozenset(_scrub(item) for item in value)
    return value


def _safe_partial(analysis: AnalysisVersion) -> PartialDeterministicResult:
    safe = AnalysisVersion.model_validate(_scrub(analysis.model_dump()))
    return PartialDeterministicResult(
        analysis_version=safe,
        evidence_items=safe.evidence_items,
    )


def _require_model_value(value: str, pattern: re.Pattern[str], *, field: str) -> None:
    if not pattern.fullmatch(value) or _contains_sensitive(value):
        raise ValueError(f"{field} violates the model data boundary")


def _validate_evidence_payload(payload: dict[str, Any]) -> None:
    for item in payload["evidence"]:
        _require_model_value(
            item["evidence_id"], _MODEL_ID, field="evidence identifier"
        )
        for scope in item["authority_scope"]:
            _require_model_value(scope, _MODEL_COMPARATOR, field="authority scope")
        for field in ("claim", "excerpt"):
            if _contains_sensitive(item[field]):
                raise ValueError(f"evidence {field} violates the model data boundary")


def _normalize_span(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _evidence_payload(
    items: tuple[EvidenceItem, ...], *, scopes: set[AuthorityScope]
) -> dict[str, Any]:
    bounded = tuple(
        BoundedEvidence(
            evidence_id=item.evidence_id,
            authority_scope=tuple(scope.value for scope in item.authority_scope),
            claim=item.claim,
            excerpt=item.excerpt or item.claim,
        )
        for item in items
        if set(item.authority_scope) & scopes
    )[:10]
    payload = {"evidence": [item.model_dump(mode="json") for item in bounded]}
    _validate_evidence_payload(payload)
    serialized = str(payload)
    if _contains_sensitive(serialized):
        raise ValueError("evidence payload violates the model data boundary")
    if len(serialized) > _MAX_PROMPT_CHARS:
        raise ValueError("bounded evidence prompt exceeds the configured limit")
    return payload


def _parse_extraction(
    value: dict[str, Any],
    payload: dict[str, Any],
    *,
    scopes: set[AuthorityScope],
) -> ExtractedFacts:
    result = ExtractedFacts.model_validate(value)
    evidence = {item["evidence_id"]: item for item in payload["evidence"]}
    if not evidence and (result.facts or result.uncertainties):
        raise ValueError("an extraction requires supplied relevant evidence")
    for reference in (*result.facts, *result.uncertainties):
        source = evidence.get(reference.evidence_id)
        if source is None:
            raise ValueError("agent cited evidence outside the supplied payload")
        scope = reference.authority_scope
        if scope not in scopes or scope.value not in source["authority_scope"]:
            raise ValueError("agent cited an authority scope outside its purpose")
        span = _normalize_span(reference.source_span)
        allowed = (
            _normalize_span(source["claim"]),
            _normalize_span(source["excerpt"]),
        )
        if not span or not any(span in candidate for candidate in allowed):
            raise ValueError("agent source span is not grounded in cited evidence")
    return result


def _decision_payload(analysis: AnalysisVersion) -> dict[str, Any]:
    ranking = analysis.ranking
    recommended = ranking.recommended_option_id
    if recommended is None:
        recommended = "NO-FEASIBLE-MITIGATION"
    payload = {
        "analysis_id": analysis.analysis_id,
        "recommended_option_id": recommended,
        "policy_version": ranking.policy_version,
        "stages": [
            {
                "stage_reference": f"ranking-stage-{index}",
                "comparator": stage.comparator,
                "threshold": str(stage.threshold),
                "values": [
                    {"option_id": value.option_id, "value": str(value.value)}
                    for value in stage.values
                ],
                "retained_option_ids": list(stage.retained_option_ids),
            }
            for index, stage in enumerate(ranking.stages, start=1)
        ],
    }
    _require_model_value(payload["analysis_id"], _MODEL_ID, field="analysis identifier")
    _require_model_value(
        payload["recommended_option_id"],
        _MODEL_ID,
        field="recommended option identifier",
    )
    _require_model_value(
        payload["policy_version"], _MODEL_POLICY, field="ranking policy"
    )
    for stage in payload["stages"]:
        _require_model_value(
            stage["stage_reference"], _MODEL_ID, field="stage reference"
        )
        _require_model_value(
            stage["comparator"], _MODEL_COMPARATOR, field="ranking comparator"
        )
        _require_model_value(
            stage["threshold"], _MODEL_NUMBER, field="ranking threshold"
        )
        for item in stage["values"]:
            _require_model_value(
                item["option_id"], _MODEL_ID, field="ranked option identifier"
            )
            value_pattern = (
                _MODEL_ID if stage["comparator"] == "option_id" else _MODEL_NUMBER
            )
            _require_model_value(item["value"], value_pattern, field="ranking value")
        for option_id in stage["retained_option_ids"]:
            _require_model_value(
                option_id, _MODEL_ID, field="retained option identifier"
            )
    serialized = str(payload)
    if _contains_sensitive(serialized):
        raise ValueError("decision payload violates the model data boundary")
    if len(serialized) > _MAX_PROMPT_CHARS:
        raise ValueError("bounded decision prompt exceeds the configured limit")
    return payload


def _parse_decision(
    value: dict[str, Any], payload: dict[str, Any]
) -> DecisionExplanation:
    result = DecisionSelection.model_validate(value)
    if result.recommended_option_id != payload["recommended_option_id"]:
        raise ValueError("agent disagreed with deterministic recommendation")
    stage_by_reference = {item["stage_reference"]: item for item in payload["stages"]}
    if len(set(result.stage_references)) != len(result.stage_references):
        raise ValueError("agent repeated a deterministic stage reference")
    if any(
        reference not in stage_by_reference for reference in result.stage_references
    ):
        raise ValueError("agent cited a stage outside the deterministic payload")
    if stage_by_reference and not result.stage_references:
        raise ValueError("agent omitted deterministic stage support")
    clauses = [
        f"The deterministic Analysis Version recommends {result.recommended_option_id}."
    ]
    for reference in result.stage_references:
        stage = stage_by_reference[reference]
        retained = ", ".join(stage["retained_option_ids"]) or "no options"
        clauses.append(
            f"{reference} applied {stage['comparator']} at threshold "
            f"{stage['threshold']} and retained {retained}."
        )
    return DecisionExplanation(
        recommended_option_id=result.recommended_option_id,
        stage_references=result.stage_references,
        explanation=" ".join(clauses),
    )


class SignalExecutor(Executor):
    def __init__(self, agent: Any) -> None:
        super().__init__("signal")
        self._agent = agent

    @handler
    async def extract(
        self, message: AnalyzeCommand, ctx: WorkflowContext[SignalMessage]
    ) -> None:
        payload = _evidence_payload(
            message.deterministic.evidence_items,
            scopes={AuthorityScope.SUPPLIER_STATEMENT},
        )
        if not payload["evidence"]:
            await ctx.send_message(SignalMessage(command=message))
            return
        try:
            result = _parse_extraction(
                await self._agent.invoke(payload),
                payload,
                scopes={AuthorityScope.SUPPLIER_STATEMENT},
            )
            await ctx.send_message(SignalMessage(command=message, extraction=result))
        except Exception:  # noqa: BLE001 - the SDK trust boundary fails closed
            await ctx.send_message(SignalMessage(command=message, failed=True))


class ContextExecutor(Executor):
    def __init__(self, agent: Any) -> None:
        super().__init__("context")
        self._agent = agent

    @handler
    async def extract(
        self, message: SignalMessage, ctx: WorkflowContext[ContextMessage]
    ) -> None:
        payload = _evidence_payload(
            message.command.deterministic.evidence_items,
            scopes={
                AuthorityScope.COLLABORATION_STATEMENT,
                AuthorityScope.QUALIFICATION_STATE,
            },
        )
        if not payload["evidence"]:
            await ctx.send_message(
                ContextMessage(
                    command=message.command,
                    signal=message.extraction,
                    failed=message.failed,
                )
            )
            return
        try:
            result = _parse_extraction(
                await self._agent.invoke(payload),
                payload,
                scopes={
                    AuthorityScope.COLLABORATION_STATEMENT,
                    AuthorityScope.QUALIFICATION_STATE,
                },
            )
            await ctx.send_message(
                ContextMessage(
                    command=message.command,
                    signal=message.extraction,
                    context=result,
                    failed=message.failed,
                )
            )
        except Exception:  # noqa: BLE001 - the SDK trust boundary fails closed
            await ctx.send_message(
                ContextMessage(
                    command=message.command,
                    signal=message.extraction,
                    failed=True,
                )
            )


class DeterministicAnalysisExecutor(Executor):
    def __init__(
        self, analyze: Callable[[AnalyzeCaseCommand], AnalysisVersion]
    ) -> None:
        super().__init__("deterministic_analysis")
        self._analyze = analyze

    @handler
    async def analyze(
        self, message: ContextMessage, ctx: WorkflowContext[DeterministicMessage]
    ) -> None:
        result = self._analyze(message.command.deterministic)
        await ctx.send_message(
            DeterministicMessage(
                analysis_version=result,
                signal=message.signal,
                context=message.context,
                failed=message.failed,
            )
        )


class DecisionExplanationExecutor(Executor):
    def __init__(self, agent: Any) -> None:
        super().__init__("decision")
        self._agent = agent

    @handler
    async def explain(
        self,
        message: DeterministicMessage,
        ctx: WorkflowContext[Never, OrchestrationResult],
    ) -> None:
        payload = _decision_payload(message.analysis_version)
        explanation: DecisionExplanation | None = None
        status = "unavailable" if message.failed else "available"
        try:
            explanation = _parse_decision(await self._agent.invoke(payload), payload)
        except (ValidationError, ValueError):
            status = "rejected"
        except Exception:  # noqa: BLE001 - SDK details must not cross this boundary
            status = "unavailable"
        if message.failed:
            explanation = None
            status = "unavailable"
        await ctx.yield_output(
            OrchestrationResult(
                analysis_version=message.analysis_version,
                signal_extraction=message.signal,
                context_extraction=message.context,
                decision_explanation=explanation,
                explanation_status=status,
            )
        )


def build_framework_workflow(
    agent_set: LocalAgentSet,
    analyze: Callable[[AnalyzeCaseCommand], AnalysisVersion],
):
    signal = SignalExecutor(agent_set.signal)
    context = ContextExecutor(agent_set.context)
    deterministic = DeterministicAnalysisExecutor(analyze)
    decision = DecisionExplanationExecutor(agent_set.decision)
    workflow = (
        WorkflowBuilder(start_executor=signal)
        .add_edge(signal, context)
        .add_edge(context, deterministic)
        .add_edge(deterministic, decision)
        .build()
    )
    return workflow


@dataclass(frozen=True, slots=True)
class _ExecutionOutcome:
    result: OrchestrationResult | None = None
    failed_partial: PartialDeterministicResult | None = None


async def _execute_workflow(
    *,
    agent_factory: Callable[[], LocalAgentSet],
    analyze: Callable[[AnalyzeCaseCommand], AnalysisVersion],
    topology_observer: Callable[[tuple[str, ...]], None] | None,
    command: AnalyzeCommand,
) -> _ExecutionOutcome:
    """Contain raw workflow state and return only a sanitized public outcome."""
    deterministic: AnalysisVersion | None = None

    def analyze_once(value: AnalyzeCaseCommand) -> AnalysisVersion:
        nonlocal deterministic
        if deterministic is None:
            deterministic = analyze(value)
        return deterministic

    try:
        workflow = build_framework_workflow(agent_factory(), analyze_once)
        if topology_observer is not None:
            topology_observer(
                ("signal", "context", "deterministic_analysis", "decision")
            )
        run = await workflow.run(command)
        outputs = run.get_outputs()
        if len(outputs) != 1 or not isinstance(outputs[0], OrchestrationResult):
            raise RuntimeError("workflow returned an invalid output contract")
        return _ExecutionOutcome(result=outputs[0])
    except Exception:  # noqa: BLE001 - discard every untrusted SDK object here
        deterministic = analyze_once(command.deterministic)
        return _ExecutionOutcome(failed_partial=_safe_partial(deterministic))


def _raise_unavailable(partial: PartialDeterministicResult) -> Never:
    """Raise from a frame containing only the already-scrubbed public result."""
    public = AgentExplanationUnavailable(partial)
    public.__cause__ = None
    public.__context__ = None
    public.__traceback__ = None
    raise public from None


class Orchestrator:
    """Runs a fresh fixed Agent Framework graph for every analysis."""

    def __init__(
        self,
        agent_factory: Callable[[], LocalAgentSet],
        analyze: Callable[[AnalyzeCaseCommand], AnalysisVersion],
        *,
        topology_observer: Callable[[tuple[str, ...]], None] | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._analyze = analyze
        self._topology_observer = topology_observer

    async def analyze(self, command: AnalyzeCommand) -> OrchestrationResult:
        outcome = await _execute_workflow(
            agent_factory=self._agent_factory,
            analyze=self._analyze,
            topology_observer=self._topology_observer,
            command=command,
        )
        # Neither the raw command nor the internal outcome may remain reachable
        # from a public exception traceback frame.
        del command
        failed_partial = outcome.failed_partial
        result = outcome.result
        outcome = None
        if failed_partial is not None:
            _raise_unavailable(failed_partial)
        if result is None:  # pragma: no cover - guarded by the workflow contract
            raise RuntimeError("workflow did not produce a result")
        if result.explanation_status == "rejected":
            # A disagreement is safely downgraded without weakening the analysis.
            return result
        if result.explanation_status != "available":
            failed_partial = _safe_partial(result.analysis_version)
            result = None
            _raise_unavailable(failed_partial)
        return result
