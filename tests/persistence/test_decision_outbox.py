from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from services.decisions.service import (
    DecisionPolicyViolation,
    DecisionService,
    IdempotencyKeyConflict,
)
from data.domain import (
    CasePurpose,
    CaseStatus,
    QualificationStatus,
    RuntimeMode,
)
from data.domain.common import ResponseOptionKind
from data.domain.decisions import (
    AuthorizationConditions,
    CorpusScope,
    DecisionKind,
    ExternalSideEffect,
    IdentitySnapshot,
    RecordDecisionCommand,
    StandingAuthorization,
)
from data.domain.evidence import IdentitySource
from data.synthetic.rl001 import build_rl001_evidence, instantiate_rl001
from services.analysis.service import (
    AnalyzeCaseCommand,
    analysis_material_hash,
    analyze_case,
)
from services.persistence.sqlite import sqlite_store
from services.persistence.store import PersistenceIntegrityError, serialize_model
from data.domain.execution import ActionPlanningRequested
from services.persistence.tables import (
    approval_satisfactions,
    decisions,
    outbox_events,
)


@dataclass(frozen=True)
class DecisionContext:
    store: object
    case: object
    snapshot: object
    analysis: object

    @property
    def uow_factory(self):
        return self.store.uow_factory


def build_analysis(
    case,
    snapshot,
    *,
    analysis_id: str,
    calculation_version: str = "rl001-options-v1",
):
    started_at = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
    return analyze_case(
        AnalyzeCaseCommand(
            analysis_id=analysis_id,
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=snapshot,
            evidence_items=build_rl001_evidence(
                snapshot,
                analysis_id=analysis_id,
                retrieved_at=started_at,
            ),
            standing_authorizations=(StandingAuthorization.taylor_rl001(),),
            analysis_started_at=started_at,
            created_at=started_at,
            calculation_version=calculation_version,
        )
    )


def beta_without_jordan_analysis(case, snapshot, *, analysis_id: str):
    qualification = snapshot.beta_qualification.model_copy(
        update={
            "status": QualificationStatus.APPROVED,
            "effective_date": date(2026, 9, 1),
            "audit_complete": True,
            "first_article_complete": True,
        }
    )
    approved_snapshot = snapshot.model_copy(
        update={"beta_qualification": qualification}
    )
    scenario_time = case.scenario_effective_time
    jordan = StandingAuthorization(
        authorization_id="RL-AUTH-JORDAN-QUALITY-1",
        persona_id="RL-PERSONA-JORDAN",
        role="quality_approver",
        conditions=AuthorizationConditions(
            allowed_option_kinds=(ResponseOptionKind.ALTERNATE_SOURCE,),
            maximum_response_cost=Decimal("0"),
            allowed_corpora=(CorpusScope.DEMO_CORPUS,),
            allowed_template_ids=(case.template_id,),
            allowed_case_purposes=(case.purpose,),
            valid_from=scenario_time,
            valid_through=scenario_time + timedelta(days=14),
            forbidden_external_side_effects=tuple(ExternalSideEffect),
        ),
    )
    started_at = datetime.fromisoformat("2026-09-01T09:01:00-05:00")
    complete = analyze_case(
        AnalyzeCaseCommand(
            analysis_id=analysis_id,
            case=case,
            corpus=CorpusScope.DEMO_CORPUS,
            operational_snapshot=approved_snapshot,
            evidence_items=build_rl001_evidence(
                approved_snapshot,
                analysis_id=analysis_id,
                retrieved_at=started_at,
            ),
            standing_authorizations=(StandingAuthorization.taylor_rl001(), jordan),
            analysis_started_at=started_at,
            created_at=started_at,
            calculation_version="rl001-options-v1",
        )
    )
    beta = next(
        item for item in complete.response_options if item.option_id == "RL-OPTION-BETA"
    )
    assert beta.executable
    missing_quality = tuple(
        item
        for item in complete.approval_satisfactions
        if item.role != "quality_approver"
    )
    material = complete.material.model_copy(
        update={
            "approval_satisfactions": tuple(
                item
                for item in complete.material.approval_satisfactions
                if item.role != "quality_approver"
            )
        }
    )
    return (
        complete.model_copy(
            update={
                "approval_satisfactions": missing_quality,
                "material": material,
                "material_hash": analysis_material_hash(material),
            }
        ),
        approved_snapshot,
    )


@pytest.fixture
def decision_context(tmp_path) -> DecisionContext:
    store = sqlite_store(f"sqlite:///{tmp_path / 'decisions.db'}")
    case, snapshot = instantiate_rl001(
        case_id="RL-CASE-DECISION-1",
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
    )
    analysis = build_analysis(
        case,
        snapshot,
        analysis_id="RL-ANALYSIS-DECISION-1",
    )
    store.create_case(case, snapshot)
    store.save_analysis(analysis)
    store.save_case_projection(
        case.model_copy(update={"status": CaseStatus.AWAITING_DECISION})
    )
    return DecisionContext(store=store, case=case, snapshot=snapshot, analysis=analysis)


@pytest.fixture
def sqlite_uow(decision_context):
    return decision_context.uow_factory


def alex_identity(
    *,
    effective_roles: tuple[str, ...] = (
        "material_planner",
        "response_approver",
    ),
    persona_id: str = "RL-PERSONA-ALEX",
) -> IdentitySnapshot:
    return IdentitySnapshot(
        persona_id=persona_id,
        effective_roles=effective_roles,
        identity_source=IdentitySource.ENTRA,
        source_id="RL-ENTRA-ALEX",
        display_name="Alex Morgan",
        user_principal_name="alex@example.invalid",
    )


def approved_combined_command(
    idempotency_key: str,
    *,
    analysis_id: str = "RL-ANALYSIS-DECISION-1",
) -> RecordDecisionCommand:
    return RecordDecisionCommand(
        case_id="RL-CASE-DECISION-1",
        analysis_id=analysis_id,
        selected_option_id="RL-OPTION-COMBINED",
        kind=DecisionKind.APPROVED,
        idempotency_key=idempotency_key,
    )


def rejection_command(
    idempotency_key: str = "RL-IDEMPOTENCY-REJECT",
    *,
    reason: str = "Supplier recovery evidence must be refreshed.",
) -> RecordDecisionCommand:
    return RecordDecisionCommand(
        case_id="RL-CASE-DECISION-1",
        analysis_id="RL-ANALYSIS-DECISION-1",
        selected_option_id=None,
        kind=DecisionKind.REJECTED,
        idempotency_key=idempotency_key,
        rejection_reason=reason,
    )


def test_approval_atomically_writes_decision_outbox_and_projection(sqlite_uow):
    command = approved_combined_command("RL-IDEMPOTENCY-1")

    decision = DecisionService(sqlite_uow).record(command, alex_identity())

    with sqlite_uow() as uow:
        assert uow.decisions.get(decision.decision_id) == decision
        events = uow.execution.list_outbox(decision_id=decision.decision_id)
        assert [(event.event_type, event.decision_id) for event in events] == [
            ("ActionPlanningRequested", decision.decision_id)
        ]
        projection = uow.cases.get_projection(decision.case_id)
        assert projection.current_decision_id == decision.decision_id
        assert projection.case.status is CaseStatus.ACTION_PLANNING


def test_same_idempotency_key_returns_same_decision_and_one_event(sqlite_uow):
    service = DecisionService(sqlite_uow)

    first = service.record(
        approved_combined_command("RL-IDEMPOTENCY-2"), alex_identity()
    )
    second = service.record(
        approved_combined_command("RL-IDEMPOTENCY-2"), alex_identity()
    )

    assert second == first
    with sqlite_uow() as uow:
        assert len(uow.decisions.list_for_case(first.case_id)) == 1
        assert len(uow.execution.list_outbox(decision_id=first.decision_id)) == 1


def test_same_idempotency_key_rejects_payload_or_actor_mismatch(sqlite_uow):
    service = DecisionService(sqlite_uow)
    first = service.record(
        approved_combined_command("RL-IDEMPOTENCY-MISMATCH"), alex_identity()
    )

    with pytest.raises(IdempotencyKeyConflict, match="different request"):
        service.record(
            rejection_command("RL-IDEMPOTENCY-MISMATCH"),
            alex_identity(),
        )
    with pytest.raises(IdempotencyKeyConflict, match="different request"):
        service.record(
            approved_combined_command("RL-IDEMPOTENCY-MISMATCH"),
            alex_identity(effective_roles=("response_approver",)),
        )

    with sqlite_uow() as uow:
        assert uow.decisions.list_for_case(first.case_id) == (first,)
        assert len(uow.execution.list_outbox(decision_id=first.decision_id)) == 1


def test_concurrent_same_idempotency_key_creates_one_decision_and_event(
    decision_context,
):
    barrier = Barrier(2)
    command = approved_combined_command("RL-IDEMPOTENCY-CONCURRENT")

    def record() -> str:
        barrier.wait()
        return (
            DecisionService(decision_context.uow_factory)
            .record(
                command,
                alex_identity(),
            )
            .decision_id
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        decision_ids = tuple(executor.map(lambda _: record(), range(2)))

    assert len(set(decision_ids)) == 1
    with decision_context.uow_factory() as uow:
        decision = uow.decisions.get(decision_ids[0])
        assert uow.decisions.list_for_case(decision.case_id) == (decision,)
        assert len(uow.execution.list_outbox(decision_id=decision.decision_id)) == 1


def test_rejection_is_immutable_and_creates_no_outbox(sqlite_uow):
    decision = DecisionService(sqlite_uow).record(
        rejection_command(), alex_identity(effective_roles=("response_approver",))
    )

    with sqlite_uow() as uow:
        assert decision.kind is DecisionKind.REJECTED
        assert decision.selected_option is None
        assert decision.rejection_reason == (
            "Supplier recovery evidence must be refreshed."
        )
        assert uow.decisions.get(decision.decision_id) == decision
        assert uow.execution.list_outbox(decision_id=decision.decision_id) == ()
        projection = uow.cases.get_projection(decision.case_id)
        assert projection.current_decision_id == decision.decision_id
        assert projection.case.status is CaseStatus.DECISION_REJECTED


def test_alex_approval_atomically_records_material_planner_satisfaction(sqlite_uow):
    decision = DecisionService(sqlite_uow).record(
        approved_combined_command("RL-IDEMPOTENCY-3"), alex_identity()
    )

    with sqlite_uow() as uow:
        satisfactions = uow.decisions.list_approval_satisfactions(decision.decision_id)
        assert [
            (item.role, item.persona_id, item.satisfied) for item in satisfactions
        ] == [
            ("finance_approver", "RL-PERSONA-TAYLOR", True),
            ("material_planner", "RL-PERSONA-ALEX", True),
        ]
        assert decision.approval_satisfactions == satisfactions


def test_decision_contains_complete_option_identity_and_analysis_lineage(sqlite_uow):
    decision = DecisionService(sqlite_uow).record(
        approved_combined_command("RL-IDEMPOTENCY-LINEAGE"), alex_identity()
    )

    assert decision.selected_option == next(
        option
        for option in decision_context_analysis(sqlite_uow).response_options
        if option.option_id == "RL-OPTION-COMBINED"
    )
    analysis = decision_context_analysis(sqlite_uow)
    assert decision.analysis_material_hash == analysis.material_hash
    assert decision.evidence_ids == decision.selected_option.evidence_ids
    assert decision.assumptions == decision.selected_option.assumptions
    assert decision.constraints == decision.selected_option.blocking_codes
    assert decision.comparator_trace == analysis.ranking
    assert decision.calculation_version == analysis.material.calculation_version
    assert decision.evidence_policy_version == analysis.material.evidence_policy_version
    assert decision.approval_policy_version == analysis.material.approval_policy_version
    assert decision.ranking_policy_version == analysis.ranking.policy_version
    assert decision.runtime_mode is RuntimeMode.FALLBACK
    assert decision.scenario_effective_time == analysis.material.scenario_effective_time
    assert decision.actor == alex_identity()


def decision_context_analysis(sqlite_uow):
    with sqlite_uow() as uow:
        return uow.cases.get_analysis("RL-ANALYSIS-DECISION-1")


def test_failure_before_outbox_rolls_back_every_approval_write(decision_context):
    def fail_before_outbox():
        raise RuntimeError("injected outbox failure")

    faulting_factory = partial(
        decision_context.store.uow_factory,
        before_outbox_insert=fail_before_outbox,
    )

    with pytest.raises(RuntimeError, match="injected outbox failure"):
        DecisionService(faulting_factory).record(
            approved_combined_command("RL-IDEMPOTENCY-ROLLBACK"),
            alex_identity(),
        )

    with decision_context.store.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(decisions)) == 0
        assert (
            connection.scalar(
                select(func.count())
                .select_from(approval_satisfactions)
                .where(approval_satisfactions.c.decision_id.is_not(None))
            )
            == 0
        )
        assert connection.scalar(select(func.count()).select_from(outbox_events)) == 0
    with decision_context.uow_factory() as uow:
        projection = uow.cases.get_projection(decision_context.case.case_id)
        assert projection.current_decision_id is None
        assert projection.case.status is CaseStatus.AWAITING_DECISION


@pytest.mark.parametrize(
    ("identity", "message"),
    [
        (
            alex_identity(persona_id="RL-PERSONA-IMPOSTOR"),
            "Alex",
        ),
        (
            alex_identity(effective_roles=("material_planner",)),
            "response_approver",
        ),
        (
            alex_identity(effective_roles=("response_approver",)),
            "material_planner",
        ),
    ],
)
def test_approval_revalidates_alex_persona_and_roles(sqlite_uow, identity, message):
    with pytest.raises(DecisionPolicyViolation, match=message):
        DecisionService(sqlite_uow).record(
            approved_combined_command(f"RL-IDEMPOTENCY-ACTOR-{message}"),
            identity,
        )


def test_approval_revalidates_taylor_finance_satisfaction(decision_context):
    analysis = decision_context.analysis.model_copy(
        update={"approval_satisfactions": ()}
    )
    changed_material = analysis.material.model_copy(
        update={"approval_satisfactions": ()}
    )
    from services.analysis.service import analysis_material_hash

    analysis = analysis.model_copy(
        update={
            "material": changed_material,
            "material_hash": analysis_material_hash(changed_material),
        }
    )
    replacement_store = sqlite_store(
        f"sqlite:///{decision_context.store.engine.url.database}-missing-finance"
    )
    replacement_store.create_case(decision_context.case, decision_context.snapshot)
    replacement_store.save_analysis(analysis)

    with pytest.raises(DecisionPolicyViolation, match="finance_approver"):
        DecisionService(replacement_store.uow_factory).record(
            approved_combined_command("RL-IDEMPOTENCY-NO-FINANCE"),
            alex_identity(),
        )


def test_old_analysis_is_rejected_after_material_reanalysis(decision_context):
    changed = build_analysis(
        decision_context.case,
        decision_context.snapshot,
        analysis_id="RL-ANALYSIS-DECISION-2",
        calculation_version="rl001-options-v2",
    )
    decision_context.store.save_case_projection(
        decision_context.case.model_copy(
            update={"status": CaseStatus.REANALYSIS_REQUIRED}
        )
    )
    decision_context.store.save_analysis(changed)

    with pytest.raises(DecisionPolicyViolation, match="current analysis"):
        DecisionService(decision_context.uow_factory).record(
            approved_combined_command("RL-IDEMPOTENCY-STALE"),
            alex_identity(),
        )


def test_material_change_marks_case_for_reanalysis_without_rewriting_decision(
    decision_context,
):
    first = DecisionService(decision_context.uow_factory).record(
        approved_combined_command("RL-IDEMPOTENCY-MATERIAL-CHANGE"),
        alex_identity(),
    )
    changed = build_analysis(
        decision_context.case,
        decision_context.snapshot,
        analysis_id="RL-ANALYSIS-DECISION-MATERIAL-CHANGE",
        calculation_version="rl001-options-v2",
    )

    decision_context.store.save_analysis(changed)

    with decision_context.uow_factory() as uow:
        projection = uow.cases.get_projection(first.case_id)
        assert projection.case.status is CaseStatus.REANALYSIS_REQUIRED
        assert projection.current_decision_id == first.decision_id
        assert uow.decisions.get(first.decision_id) == first


def test_later_approval_becomes_current_without_rewriting_history(decision_context):
    service = DecisionService(decision_context.uow_factory)
    first = service.record(
        approved_combined_command("RL-IDEMPOTENCY-4"), alex_identity()
    )
    with decision_context.store.engine.connect() as connection:
        original_payload = connection.scalar(
            select(decisions.c.payload_json).where(
                decisions.c.decision_id == first.decision_id
            )
        )

    changed = build_analysis(
        decision_context.case,
        decision_context.snapshot,
        analysis_id="RL-ANALYSIS-DECISION-2",
        calculation_version="rl001-options-v2",
    )
    decision_context.store.save_analysis(changed)
    second = service.record(
        approved_combined_command(
            "RL-IDEMPOTENCY-5",
            analysis_id=changed.analysis_id,
        ),
        alex_identity(),
    )

    with decision_context.uow_factory() as uow:
        assert uow.decisions.get(first.decision_id) == first
        assert uow.decisions.get(second.decision_id) == second
        assert (
            uow.cases.get_projection(first.case_id).current_decision_id
            == second.decision_id
        )
    with decision_context.store.engine.connect() as connection:
        assert (
            connection.scalar(
                select(decisions.c.payload_json).where(
                    decisions.c.decision_id == first.decision_id
                )
            )
            == original_payload
            == serialize_model(first)
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"selected_option_id": None},
        {"selected_option": None},
        {"rejection_reason": "not a rejection"},
    ],
)
def test_decision_model_rejects_incoherent_approval_shape(sqlite_uow, changes):
    decision = DecisionService(sqlite_uow).record(
        approved_combined_command("RL-IDEMPOTENCY-MODEL-APPROVED"),
        alex_identity(),
    )

    with pytest.raises(ValidationError):
        decision.__class__.model_validate({**decision.model_dump(), **changes})


@pytest.mark.parametrize(
    "changes",
    [
        {"selected_option_id": "RL-OPTION-COMBINED"},
        {"selected_option": {"option_id": "RL-OPTION-COMBINED"}},
        {"approval_satisfactions": (object(),)},
        {"rejection_reason": None},
    ],
)
def test_decision_model_rejects_incoherent_rejection_shape(sqlite_uow, changes):
    decision = DecisionService(sqlite_uow).record(
        rejection_command("RL-IDEMPOTENCY-MODEL-REJECT"),
        alex_identity(effective_roles=("response_approver",)),
    )

    with pytest.raises(ValidationError):
        decision.__class__.model_validate({**decision.model_dump(), **changes})


def test_decision_read_rejects_valid_json_with_forged_analysis_lineage(
    decision_context,
):
    decision = DecisionService(decision_context.uow_factory).record(
        approved_combined_command("RL-IDEMPOTENCY-FORGED-LINEAGE"),
        alex_identity(),
    )
    forged = decision.model_copy(update={"calculation_version": "forged-v999"})

    with decision_context.store.engine.begin() as connection:
        connection.execute(
            update(decisions)
            .where(decisions.c.decision_id == decision.decision_id)
            .values(payload_json=serialize_model(forged))
        )

    with decision_context.uow_factory() as uow:
        with pytest.raises(PersistenceIntegrityError, match="Analysis Version"):
            uow.decisions.get(decision.decision_id)


def test_decision_read_rejects_missing_bound_satisfaction(decision_context):
    decision = DecisionService(decision_context.uow_factory).record(
        approved_combined_command("RL-IDEMPOTENCY-SATISFACTION-READ"),
        alex_identity(),
    )
    with decision_context.store.engine.begin() as connection:
        connection.execute(
            delete(approval_satisfactions).where(
                approval_satisfactions.c.decision_id == decision.decision_id,
                approval_satisfactions.c.role == "finance_approver",
            )
        )

    with decision_context.uow_factory() as uow:
        with pytest.raises(PersistenceIntegrityError, match="Satisfaction"):
            uow.decisions.get(decision.decision_id)


def test_decision_read_rejects_reassigned_bound_satisfaction(decision_context):
    service = DecisionService(decision_context.uow_factory)
    first = service.record(
        approved_combined_command("RL-IDEMPOTENCY-SATISFACTION-FIRST"),
        alex_identity(),
    )
    changed = build_analysis(
        decision_context.case,
        decision_context.snapshot,
        analysis_id="RL-ANALYSIS-SATISFACTION-REASSIGNED",
        calculation_version="rl001-options-v2",
    )
    decision_context.store.save_analysis(changed)
    second = service.record(
        approved_combined_command(
            "RL-IDEMPOTENCY-SATISFACTION-SECOND",
            analysis_id=changed.analysis_id,
        ),
        alex_identity(),
    )
    with decision_context.store.engine.begin() as connection:
        connection.execute(
            update(approval_satisfactions)
            .where(
                approval_satisfactions.c.decision_id == first.decision_id,
                approval_satisfactions.c.role == "finance_approver",
            )
            .values(decision_id=second.decision_id)
        )

    with decision_context.uow_factory() as uow:
        with pytest.raises(PersistenceIntegrityError, match="Satisfaction"):
            uow.decisions.get(first.decision_id)
        with pytest.raises(PersistenceIntegrityError, match="Satisfaction"):
            uow.decisions.get(second.decision_id)


def test_decision_read_rejects_extra_duplicate_or_altered_satisfaction(
    decision_context,
):
    decision = DecisionService(decision_context.uow_factory).record(
        approved_combined_command("RL-IDEMPOTENCY-SATISFACTION-ALTERED"),
        alex_identity(),
    )
    taylor = next(
        item
        for item in decision.approval_satisfactions
        if item.role == "finance_approver"
    )
    altered_target = taylor.target.model_copy(
        update={"total_response_cost": Decimal("0")}
    )
    altered = taylor.model_copy(update={"target": altered_target})
    duplicate = taylor.model_copy(
        update={"authorization_id": "RL-AUTH-TAYLOR-DUPLICATE"}
    )
    with decision_context.store.engine.begin() as connection:
        connection.execute(
            update(approval_satisfactions)
            .where(
                approval_satisfactions.c.decision_id == decision.decision_id,
                approval_satisfactions.c.role == "finance_approver",
            )
            .values(payload_json=serialize_model(altered))
        )
        connection.execute(
            approval_satisfactions.insert().values(
                analysis_id=duplicate.analysis_id,
                decision_id=decision.decision_id,
                option_id=duplicate.option_id,
                authorization_id=duplicate.authorization_id,
                persona_id=duplicate.persona_id,
                role=duplicate.role,
                satisfied=duplicate.satisfied,
                payload_json=serialize_model(duplicate),
            )
        )

    with decision_context.uow_factory() as uow:
        with pytest.raises(PersistenceIntegrityError, match="Satisfaction"):
            uow.decisions.list_for_case(decision.case_id)


def test_decision_model_rejects_duplicate_approval_roles(sqlite_uow):
    decision = DecisionService(sqlite_uow).record(
        approved_combined_command("RL-IDEMPOTENCY-MODEL-DUPLICATE"),
        alex_identity(),
    )

    with pytest.raises(ValidationError, match="Satisfaction"):
        decision.__class__.model_validate(
            {
                **decision.model_dump(),
                "approval_satisfactions": (
                    *decision.approval_satisfactions,
                    decision.approval_satisfactions[0],
                ),
            }
        )


def test_outbox_read_rejects_event_for_rejected_decision(decision_context):
    service = DecisionService(decision_context.uow_factory)
    approved = service.record(
        approved_combined_command("RL-IDEMPOTENCY-OUTBOX-APPROVED"),
        alex_identity(),
    )
    rejected = service.record(
        rejection_command("RL-IDEMPOTENCY-OUTBOX-REJECTED"),
        alex_identity(effective_roles=("response_approver",)),
    )
    with decision_context.uow_factory() as uow:
        event = uow.execution.list_outbox(decision_id=approved.decision_id)[0]
    forged = event.model_copy(
        update={
            "decision_id": rejected.decision_id,
            "case_id": rejected.case_id,
            "analysis_id": rejected.analysis_id,
        }
    )
    with decision_context.store.engine.begin() as connection:
        connection.execute(
            update(outbox_events)
            .where(outbox_events.c.event_id == event.event_id)
            .values(
                decision_id=rejected.decision_id, payload_json=serialize_model(forged)
            )
        )

    with decision_context.uow_factory() as uow:
        with pytest.raises(PersistenceIntegrityError, match="rejected Decision"):
            uow.execution.list_outbox(decision_id=rejected.decision_id)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_id", "RL-CASE-FORGED"),
        ("analysis_id", "RL-ANALYSIS-FORGED"),
        ("event_type", "ForgedEvent"),
    ],
)
def test_outbox_read_rejects_forged_case_analysis_or_type(
    decision_context,
    field,
    value,
):
    decision = DecisionService(decision_context.uow_factory).record(
        approved_combined_command("RL-IDEMPOTENCY-OUTBOX-FORGED"),
        alex_identity(),
    )
    with decision_context.uow_factory() as uow:
        event = uow.execution.list_outbox(decision_id=decision.decision_id)[0]
    payload = json.loads(serialize_model(event))
    payload[field] = value
    with decision_context.store.engine.begin() as connection:
        connection.execute(
            update(outbox_events)
            .where(outbox_events.c.event_id == event.event_id)
            .values(payload_json=json.dumps(payload))
        )

    with decision_context.uow_factory() as uow:
        with pytest.raises(PersistenceIntegrityError):
            uow.execution.list_outbox(decision_id=decision.decision_id)


def test_beta_approval_fails_without_current_jordan_quality_satisfaction(
    sqlite_uow,
):
    command = RecordDecisionCommand(
        case_id="RL-CASE-DECISION-1",
        analysis_id="RL-ANALYSIS-DECISION-1",
        selected_option_id="RL-OPTION-BETA",
        kind=DecisionKind.APPROVED,
        idempotency_key="RL-IDEMPOTENCY-BETA-NO-JORDAN",
    )

    with pytest.raises(DecisionPolicyViolation, match="executable"):
        DecisionService(sqlite_uow).record(command, alex_identity())


def test_rejection_reanalysis_keeps_history_and_allows_later_approval(
    decision_context,
):
    service = DecisionService(decision_context.uow_factory)
    rejected = service.record(
        rejection_command("RL-IDEMPOTENCY-REJECT-REANALYSIS"),
        alex_identity(effective_roles=("response_approver",)),
    )
    changed = build_analysis(
        decision_context.case,
        decision_context.snapshot,
        analysis_id="RL-ANALYSIS-REJECT-REANALYSIS",
        calculation_version="rl001-options-v2",
    )
    decision_context.store.save_analysis(changed)

    approved = service.record(
        approved_combined_command(
            "RL-IDEMPOTENCY-REJECT-REANALYSIS-APPROVED",
            analysis_id=changed.analysis_id,
        ),
        alex_identity(),
    )

    with decision_context.uow_factory() as uow:
        assert uow.decisions.get(rejected.decision_id) == rejected
        assert uow.cases.get_projection(rejected.case_id).current_decision_id == (
            approved.decision_id
        )


def test_idempotency_race_after_both_requests_observe_no_existing_row(
    decision_context,
):
    before_insert = Barrier(2)
    factory = partial(
        decision_context.store.uow_factory,
        before_decision_insert=before_insert.wait,
    )
    command = approved_combined_command("RL-IDEMPOTENCY-PREINSERT-RACE")

    with ThreadPoolExecutor(max_workers=2) as executor:
        returned = tuple(
            executor.map(
                lambda _: DecisionService(factory).record(command, alex_identity()),
                range(2),
            )
        )

    assert returned[0] == returned[1]
    with decision_context.uow_factory() as uow:
        stored = uow.decisions.list_for_case(command.case_id)
        assert stored == (returned[0],)
        assert len(uow.execution.list_outbox(decision_id=stored[0].decision_id)) == 1


def test_decision_read_derives_required_finance_satisfaction_from_analysis(
    decision_context,
):
    decision = DecisionService(decision_context.uow_factory).record(
        approved_combined_command("RL-IDEMPOTENCY-DERIVED-FINANCE"),
        alex_identity(),
    )
    finance = next(
        item
        for item in decision.approval_satisfactions
        if item.role == "finance_approver"
    )
    forged_finance = finance.model_copy(
        update={
            "persona_id": "RL-PERSONA-EVE",
            "authorization_conditions": finance.authorization_conditions.model_copy(
                update={"maximum_response_cost": Decimal("0")}
            ),
        }
    )
    forged = decision.model_copy(
        update={
            "approval_satisfactions": tuple(
                forged_finance if item.role == "finance_approver" else item
                for item in decision.approval_satisfactions
            )
        }
    )
    with decision_context.store.engine.begin() as connection:
        connection.execute(
            update(decisions)
            .where(decisions.c.decision_id == decision.decision_id)
            .values(payload_json=serialize_model(forged))
        )
        connection.execute(
            update(approval_satisfactions)
            .where(
                approval_satisfactions.c.decision_id == decision.decision_id,
                approval_satisfactions.c.role == "finance_approver",
            )
            .values(
                persona_id=forged_finance.persona_id,
                payload_json=serialize_model(forged_finance),
            )
        )

    with decision_context.uow_factory() as uow:
        with pytest.raises(PersistenceIntegrityError, match="required satisfaction"):
            uow.decisions.get(decision.decision_id)


def test_decision_read_rejects_finance_removed_from_both_representations(
    decision_context,
):
    decision = DecisionService(decision_context.uow_factory).record(
        approved_combined_command("RL-IDEMPOTENCY-DERIVED-FINANCE-MISSING"),
        alex_identity(),
    )
    without_finance = decision.model_copy(
        update={
            "approval_satisfactions": tuple(
                item
                for item in decision.approval_satisfactions
                if item.role != "finance_approver"
            )
        }
    )
    with decision_context.store.engine.begin() as connection:
        connection.execute(
            update(decisions)
            .where(decisions.c.decision_id == decision.decision_id)
            .values(payload_json=serialize_model(without_finance))
        )
        connection.execute(
            delete(approval_satisfactions).where(
                approval_satisfactions.c.decision_id == decision.decision_id,
                approval_satisfactions.c.role == "finance_approver",
            )
        )

    with decision_context.uow_factory() as uow:
        with pytest.raises(PersistenceIntegrityError, match="required satisfaction"):
            uow.decisions.get(decision.decision_id)


def test_rejected_decision_rejects_option_projection_material(sqlite_uow):
    rejected = DecisionService(sqlite_uow).record(
        rejection_command("RL-IDEMPOTENCY-REJECTED-PROJECTION"),
        alex_identity(effective_roles=("response_approver",)),
    )

    with pytest.raises(ValidationError, match="rejection Decision"):
        rejected.__class__.model_validate(
            {
                **rejected.model_dump(),
                "evidence_ids": ("RL-EVIDENCE-1",),
            }
        )


def test_rejected_decision_retains_immutable_analysis_comparator_trace(sqlite_uow):
    rejected = DecisionService(sqlite_uow).record(
        rejection_command("RL-IDEMPOTENCY-REJECTED-TRACE-SHAPE"),
        alex_identity(effective_roles=("response_approver",)),
    )

    with sqlite_uow() as uow:
        analysis = uow.cases.get_analysis(rejected.analysis_id)

    assert rejected.comparator_trace == analysis.ranking
    with pytest.raises(ValidationError, match="rejection Decision"):
        rejected.__class__.model_validate(
            {**rejected.model_dump(), "comparator_trace": None}
        )


def test_rejected_decision_read_rejects_forged_comparator_trace(decision_context):
    rejected = DecisionService(decision_context.uow_factory).record(
        rejection_command("RL-IDEMPOTENCY-REJECTED-TRACE"),
        alex_identity(effective_roles=("response_approver",)),
    )
    with decision_context.uow_factory() as uow:
        ranking = uow.cases.get_analysis(rejected.analysis_id).ranking
    forged = rejected.model_copy(
        update={
            "comparator_trace": ranking.model_copy(
                update={"policy_version": "RL-RANKING-FORGED"}
            )
        }
    )
    with decision_context.store.engine.begin() as connection:
        connection.execute(
            update(decisions)
            .where(decisions.c.decision_id == rejected.decision_id)
            .values(payload_json=serialize_model(forged))
        )

    with decision_context.uow_factory() as uow:
        with pytest.raises(PersistenceIntegrityError, match="Analysis Version"):
            uow.decisions.get(rejected.decision_id)


def test_approved_decision_allows_exactly_one_planning_event(sqlite_uow):
    decision = DecisionService(sqlite_uow).record(
        approved_combined_command("RL-IDEMPOTENCY-ONE-OUTBOX"),
        alex_identity(),
    )

    with sqlite_uow() as uow:
        with pytest.raises(IntegrityError):
            uow.execution.insert_outbox(ActionPlanningRequested.for_decision(decision))


def test_insert_outbox_rejects_rejected_decision_before_writing(sqlite_uow):
    rejected = DecisionService(sqlite_uow).record(
        rejection_command("RL-IDEMPOTENCY-REJECTED-DIRECT-OUTBOX"),
        alex_identity(effective_roles=("response_approver",)),
    )

    with sqlite_uow() as uow:
        with pytest.raises(PersistenceIntegrityError, match="approved Decision"):
            uow.execution.insert_outbox(ActionPlanningRequested.for_decision(rejected))
        assert uow.execution.list_outbox(decision_id=rejected.decision_id) == ()


def test_outbox_read_rejects_missing_planning_event(decision_context):
    decision = DecisionService(decision_context.uow_factory).record(
        approved_combined_command("RL-IDEMPOTENCY-MISSING-OUTBOX"),
        alex_identity(),
    )
    with decision_context.store.engine.begin() as connection:
        connection.execute(
            delete(outbox_events).where(
                outbox_events.c.decision_id == decision.decision_id
            )
        )

    with decision_context.uow_factory() as uow:
        with pytest.raises(PersistenceIntegrityError, match="exactly one"):
            uow.decisions.get(decision.decision_id)


def test_executable_beta_requires_current_jordan_quality_satisfaction(
    decision_context,
):
    analysis, approved_snapshot = beta_without_jordan_analysis(
        decision_context.case,
        decision_context.snapshot,
        analysis_id="RL-ANALYSIS-BETA-WITHOUT-JORDAN",
    )
    replacement_store = sqlite_store(
        f"sqlite:///{decision_context.store.engine.url.database}-beta-without-jordan"
    )
    replacement_store.create_case(decision_context.case, approved_snapshot)
    replacement_store.save_analysis(analysis)
    command = RecordDecisionCommand(
        case_id=analysis.case_id,
        analysis_id=analysis.analysis_id,
        selected_option_id="RL-OPTION-BETA",
        kind=DecisionKind.APPROVED,
        idempotency_key="RL-IDEMPOTENCY-BETA-WITHOUT-JORDAN",
    )

    with pytest.raises(DecisionPolicyViolation, match="quality_approver"):
        DecisionService(replacement_store.uow_factory).record(command, alex_identity())
