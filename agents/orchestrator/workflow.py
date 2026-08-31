from __future__ import annotations

import re
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
    DeterministicMessage,
    ExtractedFacts,
    OrchestrationResult,
    PartialDeterministicResult,
    SignalMessage,
)
from .local import LocalAgentSet

_MAX_PROMPT_CHARS = 16_000
_OPTION_ID = re.compile(r"RL-OPTION-[A-Z0-9-]+")
_NUMBER = re.compile(r"(?<![A-Za-z])\$?\d+(?:[,.]\d+)*(?:%|\b)")


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
    if len(str(payload)) > _MAX_PROMPT_CHARS:
        raise ValueError("bounded evidence prompt exceeds the configured limit")
    return payload


def _parse_extraction(value: dict[str, Any], payload: dict[str, Any]) -> ExtractedFacts:
    result = ExtractedFacts.model_validate(value)
    allowed_text = " ".join(
        f"{item['claim']} {item['excerpt']}" for item in payload["evidence"]
    )
    for text in (*result.facts, *result.uncertainties):
        if len(text) > 2_000:
            raise ValueError("agent output exceeds the configured limit")
        for number in _NUMBER.findall(text):
            if number not in allowed_text:
                raise ValueError(
                    "agent output introduced a number absent from evidence"
                )
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
                "comparator": stage.comparator,
                "threshold": str(stage.threshold),
                "values": [
                    {"option_id": value.option_id, "value": str(value.value)}
                    for value in stage.values
                ],
                "retained_option_ids": list(stage.retained_option_ids),
            }
            for stage in ranking.stages
        ],
    }


def _parse_decision(
    value: dict[str, Any], payload: dict[str, Any]
) -> DecisionExplanation:
    result = DecisionExplanation.model_validate(value)
    if result.recommended_option_id != payload["recommended_option_id"]:
        raise ValueError("agent disagreed with deterministic recommendation")
    allowed = str(payload)
    mentioned_options = set(_OPTION_ID.findall(result.explanation))
    if mentioned_options - {result.recommended_option_id}:
        raise ValueError("agent explanation introduced a different option")
    for number in _NUMBER.findall(result.explanation):
        if number not in allowed:
            raise ValueError(
                "agent explanation introduced a number absent from analysis"
            )
    return result


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
        try:
            result = _parse_extraction(await self._agent.invoke(payload), payload)
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
        try:
            result = _parse_extraction(await self._agent.invoke(payload), payload)
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
        except ValidationError:
            status = "unavailable"
        except ValueError:
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
    ) -> None:
        self._agent_factory = agent_factory
        self._analyze = analyze
        self.framework_workflows: list[Any] = []
        self.topologies: list[tuple[str, ...]] = []

    async def analyze(self, command: AnalyzeCommand) -> OrchestrationResult:
        workflow = build_framework_workflow(self._agent_factory(), self._analyze)
        self.framework_workflows.append(workflow)
        self.topologies.append(
            ("signal", "context", "deterministic_analysis", "decision")
        )
        run = await workflow.run(command)
        outputs = run.get_outputs()
        if len(outputs) != 1 or not isinstance(outputs[0], OrchestrationResult):
            # This cannot safely expose an SDK exception or event payload.
            deterministic = self._analyze(command.deterministic)
            raise AgentExplanationUnavailable(
                PartialDeterministicResult(
                    analysis_version=deterministic,
                    evidence_items=deterministic.evidence_items,
                )
            )
        result = outputs[0]
        if result.explanation_status == "rejected":
            # A disagreement is safely downgraded without weakening the analysis.
            return result
        if result.explanation_status != "available":
            raise AgentExplanationUnavailable(
                PartialDeterministicResult(
                    analysis_version=result.analysis_version,
                    evidence_items=result.analysis_version.evidence_items,
                )
            )
        return result
