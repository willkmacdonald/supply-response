from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

import pytest

from data.domain import CasePurpose, CaseStatus, RuntimeMode
from data.domain.decisions import (
    CorpusScope,
    DecisionKind,
    IdentitySnapshot,
    RecordDecisionCommand,
    StandingAuthorization,
    Decision,
)
from data.domain.evidence import IdentitySource
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case
from services.decisions.service import DecisionService
from services.execution.planner import plan_actions
from services.execution.worker import ExecutionService
from services.execution.worker import UnitOfWorkFactory
from services.persistence.sqlite import sqlite_store
from services.persistence.store import SqlAlchemyStore


APPROVED_DECISION_ID = "RL-DECISION-00000000-0000-0000-0000-000000000008"


def alex_identity(
    *,
    persona_id: str = "RL-PERSONA-ALEX",
    effective_roles: tuple[str, ...] = (
        "material_planner",
        "response_approver",
    ),
) -> IdentitySnapshot:
    return IdentitySnapshot(
        persona_id=persona_id,
        effective_roles=effective_roles,
        identity_source=IdentitySource.ENTRA,
        source_id="RL-ENTRA-ALEX",
        display_name="Alex Morgan",
        user_principal_name="alex@example.invalid",
    )


@dataclass(frozen=True)
class PlanningContext:
    store: SqlAlchemyStore
    decision: Decision

    @property
    def uow_factory(self) -> UnitOfWorkFactory:
        return cast(UnitOfWorkFactory, self.store.uow_factory)


@pytest.fixture
def planning_context(tmp_path, monkeypatch) -> PlanningContext:
    store = sqlite_store(f"sqlite:///{tmp_path / 'execution.db'}")
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-EXECUTION-1",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
    )
    started_at = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
    analysis = analyze_case(
        AnalyzeCaseCommand(
            analysis_id="RL-ANALYSIS-EXECUTION-1",
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=snapshot,
            evidence_items=build_rl001_evidence(
                snapshot,
                analysis_id="RL-ANALYSIS-EXECUTION-1",
                retrieved_at=started_at,
            ),
            standing_authorizations=(StandingAuthorization.taylor_rl001(),),
            analysis_started_at=started_at,
            created_at=started_at,
            calculation_version="rl001-options-v1",
        )
    )
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    store.save_case_projection(
        case.model_copy(update={"status": CaseStatus.AWAITING_DECISION})
    )
    monkeypatch.setattr("data.domain.decisions.uuid4", lambda: UUID(int=8))
    decision = DecisionService(cast(UnitOfWorkFactory, store.uow_factory)).record(
        RecordDecisionCommand(
            case_id=case.case_id,
            analysis_id=analysis.analysis_id,
            selected_option_id="RL-OPTION-COMBINED",
            kind=DecisionKind.APPROVED,
            idempotency_key="RL-IDEMPOTENCY-EXECUTION-1",
        ),
        alex_identity(),
    )
    assert decision.decision_id == APPROVED_DECISION_ID
    return PlanningContext(store=store, decision=decision)


@pytest.fixture
def approved_combined_decision(planning_context):
    return planning_context.decision


@pytest.fixture
def planned_action(approved_combined_decision):
    return plan_actions(approved_combined_decision)[0]


@pytest.fixture
def execution_service(planning_context):
    return ExecutionService(planning_context.uow_factory)
