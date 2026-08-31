from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from typing import Any, Never

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
)
_REDACTED = "[REDACTED]"


def _contains_sensitive(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SENSITIVE_PATTERNS)


def _redact_text(value: str) -> str:
    for pattern in _SENSITIVE_PATTERNS:
        value = pattern.sub(_REDACTED, value)
    return value


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub(item) for item in value)
    return value


def _safe_partial(analysis: AnalysisVersion) -> PartialDeterministicResult:
    safe = AnalysisVersion.model_validate(_scrub(analysis.model_dump()))
    return PartialDeterministicResult(
        analysis_version=safe,
        evidence_items=safe.evidence_items,
    )


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
    return {
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
        deterministic: AnalysisVersion | None = None

        def analyze_once(value: AnalyzeCaseCommand) -> AnalysisVersion:
            nonlocal deterministic
            if deterministic is None:
                deterministic = self._analyze(value)
            return deterministic

        try:
            workflow = build_framework_workflow(self._agent_factory(), analyze_once)
            if self._topology_observer is not None:
                self._topology_observer(
                    ("signal", "context", "deterministic_analysis", "decision")
                )
            run = await workflow.run(command)
            outputs = run.get_outputs()
            if len(outputs) != 1 or not isinstance(outputs[0], OrchestrationResult):
                raise RuntimeError("workflow returned an invalid output contract")
            result = outputs[0]
        except Exception as exc:
            if isinstance(exc, AgentExplanationUnavailable):
                raise
            deterministic = analyze_once(command.deterministic)
            raise AgentExplanationUnavailable(_safe_partial(deterministic)) from None
        if result.explanation_status == "rejected":
            # A disagreement is safely downgraded without weakening the analysis.
            return result
        if result.explanation_status != "available":
            raise AgentExplanationUnavailable(_safe_partial(result.analysis_version))
        return result
