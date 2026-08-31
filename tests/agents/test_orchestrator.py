from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from agents.orchestrator.contracts import (
    AgentExplanationUnavailable,
    AnalyzeCommand,
)
from agents.orchestrator.local import LocalAgentSet
from agents.orchestrator.workflow import Orchestrator
from data.domain import CasePurpose, RuntimeMode
from data.domain.decisions import CorpusScope, StandingAuthorization
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case

NOW = datetime(2026, 8, 30, 15, tzinfo=UTC)


def command() -> AnalyzeCommand:
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-AGENT-001",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
    )
    deterministic = AnalyzeCaseCommand(
        analysis_id="RL-ANALYSIS-AGENT-001",
        case=case,
        corpus=CorpusScope.DEMO_CORPUS,
        operational_snapshot=snapshot,
        evidence_items=build_rl001_evidence(
            snapshot,
            analysis_id="RL-ANALYSIS-AGENT-001",
            retrieved_at=NOW,
        ),
        standing_authorizations=(StandingAuthorization.taylor_rl001(),),
        analysis_started_at=NOW,
        created_at=NOW,
        calculation_version="rl001-options-v1",
    )
    return AnalyzeCommand(deterministic=deterministic)


class FakeAgent:
    def __init__(self, response: dict[str, Any] | BaseException) -> None:
        self.response = response
        self.payloads: list[dict[str, Any]] = []

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payloads.append(payload)
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


def agents(
    *,
    signal: dict[str, Any] | BaseException | None = None,
    context: dict[str, Any] | BaseException | None = None,
    decision: dict[str, Any] | BaseException | None = None,
) -> tuple[Callable[[], LocalAgentSet], list[LocalAgentSet]]:
    made: list[LocalAgentSet] = []

    def factory() -> LocalAgentSet:
        result = LocalAgentSet(
            signal=FakeAgent(
                signal
                or {
                    "facts": ["Alpha confirmed an explicit partial-shipment fact."],
                    "uncertainties": [],
                }
            ),
            context=FakeAgent(
                context
                or {
                    "facts": ["Beta qualification is explicitly pending."],
                    "uncertainties": [],
                }
            ),
            decision=FakeAgent(
                decision
                or {
                    "recommended_option_id": "RL-OPTION-COMBINED",
                    "explanation": "The deterministic result recommends the combined response.",
                }
            ),
        )
        made.append(result)
        return result

    return factory, made


@pytest.mark.anyio
async def test_agent_disagreement_cannot_change_authoritative_analysis() -> None:
    factory, made = agents(
        decision={
            "recommended_option_id": "RL-OPTION-BETA",
            "explanation": "Choose Beta because it sounds fast and costs 1 invented dollar.",
        }
    )
    result = await Orchestrator(factory, analyze_case).analyze(command())

    assert result.analysis_version.ranking.recommended_option_id == "RL-OPTION-COMBINED"
    assert result.decision_explanation is None
    assert result.explanation_status == "rejected"
    decision_payload = cast(FakeAgent, made[0].decision).payloads[0]
    assert decision_payload["recommended_option_id"] == "RL-OPTION-COMBINED"
    assert "operational_snapshot_json" not in decision_payload


@pytest.mark.anyio
async def test_agent_failure_preserves_token_free_deterministic_result() -> None:
    factory, _ = agents(context=TimeoutError("Bearer RL-TEST-SECRET"))

    with pytest.raises(AgentExplanationUnavailable) as caught:
        await Orchestrator(factory, analyze_case).analyze(command())

    partial = caught.value.partial_result
    assert (
        partial.analysis_version.ranking.recommended_option_id == "RL-OPTION-COMBINED"
    )
    assert partial.evidence_items
    assert "RL-TEST-SECRET" not in str(caught.value)
    assert "RL-TEST-SECRET" not in partial.model_dump_json()


@pytest.mark.anyio
async def test_model_payloads_are_minimized_bounded_and_identity_free() -> None:
    factory, made = agents()
    await Orchestrator(factory, analyze_case).analyze(command())

    signal_payload = cast(FakeAgent, made[0].signal).payloads[0]
    assert set(signal_payload) == {"evidence"}
    serialized = str(signal_payload)
    assert "bearer" not in serialized.lower()
    assert "upn" not in serialized.lower()
    assert "tenant" not in serialized.lower()
    assert "operational_snapshot" not in serialized
    assert len(serialized) < 16_000


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        {"facts": ["ok"], "uncertainties": [], "tool_calls": ["danger"]},
        {"facts": ["x" * 5000], "uncertainties": []},
        {"facts": ["invented price: $123"], "uncertainties": []},
    ],
)
async def test_untrusted_signal_output_is_rejected(response: dict[str, Any]) -> None:
    factory, _ = agents(signal=response)
    with pytest.raises(AgentExplanationUnavailable):
        await Orchestrator(factory, analyze_case).analyze(command())


@pytest.mark.anyio
async def test_fresh_workflow_and_executors_are_built_for_every_run() -> None:
    factory, made = agents()
    orchestrator = Orchestrator(factory, analyze_case)

    await orchestrator.analyze(command())
    await orchestrator.analyze(command())

    assert len(made) == 2
    assert made[0] is not made[1]
    assert made[0].signal is not made[1].signal
    assert (
        orchestrator.framework_workflows[0] is not orchestrator.framework_workflows[1]
    )
    assert orchestrator.topologies == [
        ("signal", "context", "deterministic_analysis", "decision"),
        ("signal", "context", "deterministic_analysis", "decision"),
    ]


@pytest.mark.anyio
async def test_local_fallback_has_same_contract_and_no_network_agent() -> None:
    result = await Orchestrator(LocalAgentSet.deterministic, analyze_case).analyze(
        command()
    )

    assert result.analysis_version.ranking.recommended_option_id == "RL-OPTION-COMBINED"
    assert result.explanation_status == "available"
    assert result.decision_explanation is not None
    assert result.decision_explanation.recommended_option_id == "RL-OPTION-COMBINED"
