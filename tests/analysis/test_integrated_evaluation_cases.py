from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

import pytest

from data.domain import CasePurpose, QualificationStatus, RuntimeMode
from data.domain.common import ResponseOptionKind
from data.domain.decisions import (
    AuthorizationConditions,
    CorpusScope,
    ExternalSideEffect,
    StandingAuthorization,
)
from data.domain.evidence import (
    ActorProvenance,
    AuthorityScope,
    ConflictResolution,
    EvidenceConflict,
    EvidenceItem,
    EvidenceKind,
    EvidenceRequirement,
    EvidenceSourceSystem,
    IdentitySource,
    RetrievalHealth,
    UncertaintyState,
)
from data.synthetic.rl001 import OperationalSnapshot, instantiate_rl001
from services.analysis.service import AnalyzeCaseCommand, analyze_case


Expected = dict[str, object]
CaseBuilder = Callable[[], tuple[AnalyzeCaseCommand, Expected]]


def _evidence(
    command: AnalyzeCaseCommand,
    *,
    evidence_id: str,
    claim: str,
    source_timestamp_present: bool = True,
    authority_scope: tuple[AuthorityScope, ...] = (AuthorityScope.OPERATIONAL_DATE,),
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        case_id=command.case.case_id,
        kind=EvidenceKind.OPERATIONAL_FACT,
        authority_scope=authority_scope,
        source_system=EvidenceSourceSystem.SYNTHETIC_FIXTURE,
        source_id=f"RL-SOURCE-{evidence_id}",
        source_timestamp=(
            command.analysis_started_at - timedelta(minutes=1)
            if source_timestamp_present
            else None
        ),
        retrieved_at=command.analysis_started_at,
        retrieved_for_analysis_id=command.analysis_id,
        retrieval_health=RetrievalHealth.HEALTHY,
        effective_at=command.case.scenario_effective_time,
        expires_at=command.case.scenario_effective_time + timedelta(days=1),
        claim=claim,
        excerpt=claim,
        citation_url=f"https://rl.example/evidence/{evidence_id}",
        runtime_mode=command.case.runtime_mode,
        synthetic=True,
        requirement=EvidenceRequirement.REQUIRED_AUTHORITATIVE,
        uncertainty_state=UncertaintyState.CERTAIN,
    )


def _command(case_id: str) -> AnalyzeCaseCommand:
    case, snapshot = instantiate_rl001(
        case_id=case_id,
        purpose=CasePurpose.AUTOMATED_TEST,
        runtime_mode=RuntimeMode.FALLBACK,
    )
    command = AnalyzeCaseCommand(
        analysis_id=f"RL-ANALYSIS-{case_id}",
        case=case,
        corpus=CorpusScope.DEMO_CORPUS,
        operational_snapshot=snapshot,
        standing_authorizations=(StandingAuthorization.taylor_rl001(),),
        analysis_started_at=case.scenario_effective_time,
        created_at=case.scenario_effective_time + timedelta(minutes=2),
        calculation_version="rl001-options-v1",
    )
    snapshot = command.operational_snapshot
    evidence_items = (
        _evidence(
            command,
            evidence_id=snapshot.alpha_expedite.receipt_id,
            claim="Alpha partial shipment quantity and date are confirmed.",
            authority_scope=(
                AuthorityScope.OPERATIONAL_QUANTITY,
                AuthorityScope.OPERATIONAL_DATE,
            ),
        ),
        _evidence(
            command,
            evidence_id=snapshot.transfer.transfer_id,
            claim="Dallas transfer quantity and date are confirmed.",
            authority_scope=(
                AuthorityScope.OPERATIONAL_QUANTITY,
                AuthorityScope.OPERATIONAL_DATE,
            ),
        ),
        _evidence(
            command,
            evidence_id=snapshot.beta_qualification.evidence_ref,
            claim="Beta qualification state is pending.",
            authority_scope=(AuthorityScope.QUALIFICATION_STATE,),
        ),
    )
    return command.model_copy(update={"evidence_items": evidence_items})


def _jordan_quality_authorization() -> StandingAuthorization:
    start = OperationalSnapshot.rl001().scenario_effective_time
    return StandingAuthorization(
        authorization_id="RL-AUTH-JORDAN-QUALITY-1",
        persona_id="RL-PERSONA-JORDAN",
        role="quality_approver",
        conditions=AuthorizationConditions(
            allowed_option_kinds=(ResponseOptionKind.ALTERNATE_SOURCE,),
            maximum_response_cost=Decimal("0"),
            allowed_corpora=(CorpusScope.DEMO_CORPUS,),
            allowed_template_ids=("RL-001",),
            allowed_case_purposes=tuple(CasePurpose),
            valid_from=start,
            valid_through=start + timedelta(days=14),
            forbidden_external_side_effects=tuple(ExternalSideEffect),
        ),
    )


def _with_snapshot(
    command: AnalyzeCaseCommand, snapshot: OperationalSnapshot
) -> AnalyzeCaseCommand:
    return command.model_copy(update={"operational_snapshot": snapshot})


def _expected(**values: object) -> Expected:
    return values


def confirmed_recovery_case() -> tuple[AnalyzeCaseCommand, Expected]:
    command = _command("RL-EVAL-001")
    disruption = command.operational_snapshot.disruption.model_copy(
        update={"recovery_date": date(2026, 9, 12)}
    )
    command = _with_snapshot(
        command,
        command.operational_snapshot.model_copy(update={"disruption": disruption}),
    )
    return command, _expected(expedite_uncertainties=(), expedite_execution_risk=0)


def unconfirmed_recovery_case() -> tuple[AnalyzeCaseCommand, Expected]:
    return _command("RL-EVAL-002"), _expected(
        expedite_uncertainties=("Remaining supplier recovery date is unconfirmed.",),
        expedite_execution_risk=2,
    )


def partial_shipment_case() -> tuple[AnalyzeCaseCommand, Expected]:
    command = _command("RL-EVAL-003")
    snapshot = command.operational_snapshot
    inventory = tuple(
        position.model_copy(
            update={"on_hand": 0, "quality_hold": 0, "protected_allocation": 0}
        )
        if position.plant_id == snapshot.transfer.source_plant_id
        else position
        for position in snapshot.inventory_positions
    )
    orders = tuple(
        order.model_copy(update={"customer_priority": index})
        for index, order in enumerate(snapshot.production_orders, start=1)
    )
    command = _with_snapshot(
        command,
        snapshot.model_copy(
            update={"inventory_positions": inventory, "production_orders": orders}
        ),
    )
    return command, _expected(
        expedite_executable=True,
        expedite_quantity=command.operational_snapshot.alpha_expedite.quantity,
    )


def conflicting_dates_case() -> tuple[AnalyzeCaseCommand, Expected]:
    command = _command("RL-EVAL-004")
    operational = _evidence(
        command,
        evidence_id="RL-EVIDENCE-OPERATIONAL-DATE",
        claim="Operational due date is 2026-09-08.",
    )
    communicated = _evidence(
        command,
        evidence_id="RL-EVIDENCE-COMMUNICATED-DATE",
        claim="Communicated due date is 2026-09-06.",
    )
    conflict = EvidenceConflict(
        conflict_id="RL-CONFLICT-DATES",
        case_id=command.case.case_id,
        evidence_ids=(operational.evidence_id, communicated.evidence_id),
        authority_scope=(AuthorityScope.OPERATIONAL_DATE,),
        description="Communicated and operational dates disagree.",
        feasibility_relevant=True,
    )
    command = command.model_copy(
        update={"evidence_items": (operational, communicated), "conflicts": (conflict,)}
    )
    return command, _expected(
        conflict_ids=("RL-CONFLICT-DATES",),
        evidence_blocking_codes=("EVIDENCE_CONFLICT_UNRESOLVED",),
        evidence_uncertainty=("conflicted", "conflicted"),
    )


def beta_approved_case() -> tuple[AnalyzeCaseCommand, Expected]:
    command = _command("RL-EVAL-005")
    qualification = command.operational_snapshot.beta_qualification.model_copy(
        update={
            "status": QualificationStatus.APPROVED,
            "effective_date": date(2026, 9, 1),
            "audit_complete": True,
            "first_article_complete": True,
        }
    )
    command = _with_snapshot(
        command,
        command.operational_snapshot.model_copy(
            update={"beta_qualification": qualification}
        ),
    ).model_copy(
        update={
            "standing_authorizations": (
                *command.standing_authorizations,
                _jordan_quality_authorization(),
            )
        }
    )
    return command, _expected(
        beta_executable=True,
        beta_blocking_codes=(),
        beta_has_predicted_outcome=True,
        beta_ranking_eligible=True,
        quality_approval_satisfied=True,
    )


def beta_pending_case() -> tuple[AnalyzeCaseCommand, Expected]:
    return _command("RL-EVAL-006"), _expected(
        beta_executable=False,
        beta_blocking_codes=("QUALITY_QUALIFICATION_PENDING",),
    )


def transfer_available_case() -> tuple[AnalyzeCaseCommand, Expected]:
    command = _command("RL-EVAL-007")
    return command, _expected(
        transfer_executable=True,
        transfer_available_units=command.operational_snapshot.usable_inventory(
            command.operational_snapshot.transfer.part_id,
            command.operational_snapshot.transfer.source_plant_id,
        ),
    )


def no_feasible_mitigation_case() -> tuple[AnalyzeCaseCommand, Expected]:
    command = _command("RL-EVAL-008")
    snapshot = command.operational_snapshot
    alpha_evidence = _evidence(
        command,
        evidence_id=snapshot.alpha_expedite.receipt_id,
        claim="Alpha partial shipment timestamp is unavailable.",
        source_timestamp_present=False,
        authority_scope=(
            AuthorityScope.OPERATIONAL_QUANTITY,
            AuthorityScope.OPERATIONAL_DATE,
        ),
    )
    inventory = tuple(
        position.model_copy(
            update={"on_hand": 0, "quality_hold": 0, "protected_allocation": 0}
        )
        if position.plant_id == snapshot.transfer.source_plant_id
        else position
        for position in snapshot.inventory_positions
    )
    orders = tuple(
        order.model_copy(update={"customer_priority": index})
        for index, order in enumerate(snapshot.production_orders, start=1)
    )
    command = _with_snapshot(
        command,
        snapshot.model_copy(
            update={"inventory_positions": inventory, "production_orders": orders}
        ),
    ).model_copy(
        update={
            "evidence_items": (
                alpha_evidence,
                *(
                    item
                    for item in command.evidence_items
                    if item.evidence_id != alpha_evidence.evidence_id
                ),
            )
        }
    )
    return command, _expected(
        no_feasible_mitigation=True,
        recommended_option_id=None,
        infeasible_option_ids=(
            "RL-OPTION-BETA",
            "RL-OPTION-COMBINED",
            "RL-OPTION-EXPEDITE",
            "RL-OPTION-RESEQUENCE",
            "RL-OPTION-TRANSFER",
        ),
        combined_blocking_codes=(
            "TRANSFER_INVENTORY_UNAVAILABLE",
            "RESEQUENCE_NOT_APPLICABLE",
            "EVIDENCE_TIMESTAMP_STALE",
        ),
    )


def finance_threshold_case() -> tuple[AnalyzeCaseCommand, Expected]:
    return _command("RL-EVAL-009"), _expected(
        expedite_response_cost=Decimal("22500"),
        expedite_prerequisite_roles=("material_planner", "finance_approver"),
        finance_approval_satisfied=True,
    )


def stale_evidence_case() -> tuple[AnalyzeCaseCommand, Expected]:
    command = _command("RL-EVAL-010")
    evidence = _evidence(
        command,
        evidence_id=command.operational_snapshot.beta_qualification.evidence_ref,
        claim="Beta qualification evidence has no trustworthy source timestamp.",
        source_timestamp_present=False,
        authority_scope=(AuthorityScope.QUALIFICATION_STATE,),
    )
    transfer_id = command.operational_snapshot.transfer.transfer_id
    command = command.model_copy(
        update={
            "evidence_items": (
                evidence,
                *(
                    item
                    for item in command.evidence_items
                    if item.evidence_id == transfer_id
                ),
            )
        }
    )
    return command, _expected(
        evidence_freshness=("stale", "current"),
        evidence_blocking_codes=("EVIDENCE_TIMESTAMP_STALE",),
        beta_executable=False,
        beta_blocking_codes=(
            "QUALITY_QUALIFICATION_PENDING",
            "EVIDENCE_TIMESTAMP_STALE",
        ),
        beta_ranking_eligible=False,
        expedite_executable=False,
        expedite_blocking_codes=(
            "EVIDENCE_TIMESTAMP_STALE",
            "REQUIRED_EVIDENCE_MISSING",
        ),
    )


CASE_BUILDERS: dict[str, CaseBuilder] = {
    "RL-EVAL-001": confirmed_recovery_case,
    "RL-EVAL-002": unconfirmed_recovery_case,
    "RL-EVAL-003": partial_shipment_case,
    "RL-EVAL-004": conflicting_dates_case,
    "RL-EVAL-005": beta_approved_case,
    "RL-EVAL-006": beta_pending_case,
    "RL-EVAL-007": transfer_available_case,
    "RL-EVAL-008": no_feasible_mitigation_case,
    "RL-EVAL-009": finance_threshold_case,
    "RL-EVAL-010": stale_evidence_case,
}


def summarize(analysis, *, keys: set[str]) -> Expected:
    options = {option.option_id: option for option in analysis.response_options}
    expedite = options["RL-OPTION-EXPEDITE"]
    beta = options["RL-OPTION-BETA"]
    transfer = options["RL-OPTION-TRANSFER"]
    combined = options["RL-OPTION-COMBINED"]
    snapshot = OperationalSnapshot.model_validate_json(
        analysis.material.operational_snapshot_json
    )
    summary: Expected = {
        "expedite_uncertainties": tuple(
            assumption
            for assumption in expedite.assumptions
            if "unconfirmed" in assumption
        ),
        "expedite_execution_risk": expedite.execution_risk,
        "expedite_executable": expedite.executable,
        "expedite_blocking_codes": expedite.blocking_codes,
        "expedite_quantity": snapshot.alpha_expedite.quantity,
        "conflict_ids": tuple(
            conflict.conflict_id for conflict in analysis.material.conflicts
        ),
        "evidence_blocking_codes": tuple(
            code.value for code in analysis.evidence_validation.blocking_codes
        ),
        "evidence_uncertainty": tuple(
            result.uncertainty_state.value
            for result in analysis.evidence_validation.item_results
        ),
        "beta_executable": beta.executable,
        "beta_blocking_codes": beta.blocking_codes,
        "beta_has_predicted_outcome": beta.predicted is not None,
        "beta_ranking_eligible": beta.option_id in analysis.ranking.eligible_option_ids,
        "transfer_executable": transfer.executable,
        "transfer_available_units": snapshot.usable_inventory(
            snapshot.transfer.part_id, snapshot.transfer.source_plant_id
        ),
        "no_feasible_mitigation": analysis.ranking.no_feasible_mitigation,
        "recommended_option_id": analysis.ranking.recommended_option_id,
        "infeasible_option_ids": analysis.ranking.infeasible_option_ids,
        "combined_blocking_codes": combined.blocking_codes,
        "expedite_response_cost": expedite.predicted.response_cost,
        "expedite_prerequisite_roles": expedite.prerequisite_roles,
        "finance_approval_satisfied": any(
            approval.option_id == expedite.option_id
            and approval.role == "finance_approver"
            and approval.satisfied
            for approval in analysis.approval_satisfactions
        ),
        "quality_approval_satisfied": any(
            approval.option_id == beta.option_id
            and approval.role == "quality_approver"
            and approval.satisfied
            for approval in analysis.approval_satisfactions
        ),
        "evidence_freshness": tuple(
            result.freshness.value
            for result in analysis.evidence_validation.item_results
        ),
    }
    return {key: summary[key] for key in summary if key in keys}


@pytest.mark.parametrize("case_id", sorted(CASE_BUILDERS))
def test_integrated_evaluation_case(case_id):
    command, expected = CASE_BUILDERS[case_id]()
    assert summarize(analyze_case(command), keys=set(expected)) == expected


def test_resolved_feasibility_conflict_does_not_block_referenced_option():
    command = _command("RL-EVAL-RESOLVED")
    alpha_id = command.operational_snapshot.alpha_expedite.receipt_id
    alpha = _evidence(
        command,
        evidence_id=alpha_id,
        claim="Alpha receipt date is 2026-09-06.",
        authority_scope=(
            AuthorityScope.OPERATIONAL_QUANTITY,
            AuthorityScope.OPERATIONAL_DATE,
        ),
    )
    corroborating = _evidence(
        command,
        evidence_id="RL-EVIDENCE-ALPHA-CORROBORATING",
        claim="Alpha receipt date is 2026-09-07.",
        authority_scope=(
            AuthorityScope.OPERATIONAL_QUANTITY,
            AuthorityScope.OPERATIONAL_DATE,
        ),
    )
    conflict = EvidenceConflict(
        conflict_id="RL-CONFLICT-ALPHA-RESOLVED",
        case_id=command.case.case_id,
        evidence_ids=(alpha.evidence_id, corroborating.evidence_id),
        authority_scope=(AuthorityScope.OPERATIONAL_DATE,),
        description="Alpha receipt dates initially disagreed.",
        feasibility_relevant=True,
    )
    resolution = ConflictResolution(
        conflict_id=conflict.conflict_id,
        governing_evidence_id=alpha.evidence_id,
        actor=ActorProvenance(
            persona_id="RL-PERSONA-ALEX",
            roles=("material_planner",),
            identity_source=IdentitySource.ENTRA,
            source_id="RL-ENTRA-ALEX",
        ),
        why="The current operational receipt record governs.",
    )
    command = command.model_copy(
        update={
            "evidence_items": (
                alpha,
                corroborating,
                *(
                    item
                    for item in command.evidence_items
                    if item.evidence_id != alpha.evidence_id
                ),
            ),
            "conflicts": (conflict,),
            "conflict_resolutions": (resolution,),
        }
    )

    analysis = analyze_case(command)
    expedite = next(
        option
        for option in analysis.response_options
        if option.option_id == "RL-OPTION-EXPEDITE"
    )

    assert expedite.executable is True
    assert "EVIDENCE_CONFLICT_UNRESOLVED" not in expedite.blocking_codes


def test_absent_partial_shipment_blocks_expedite_and_combined_options():
    command = _command("RL-EVAL-NO-PARTIAL-SHIPMENT")
    command = _with_snapshot(
        command,
        command.operational_snapshot.model_copy(update={"alpha_expedite": None}),
    )

    analysis = analyze_case(command)
    options = {option.option_id: option for option in analysis.response_options}

    assert options["RL-OPTION-EXPEDITE"].executable is False
    assert options["RL-OPTION-EXPEDITE"].blocking_codes == (
        "ALPHA_PARTIAL_SHIPMENT_UNAVAILABLE",
    )
    assert options["RL-OPTION-COMBINED"].executable is False
    assert (
        "ALPHA_PARTIAL_SHIPMENT_UNAVAILABLE"
        in options["RL-OPTION-COMBINED"].blocking_codes
    )


def test_missing_required_option_evidence_blocks_before_ranking():
    command = _command("RL-EVAL-MISSING-OPTION-EVIDENCE")
    alpha_id = command.operational_snapshot.alpha_expedite.receipt_id
    command = command.model_copy(
        update={
            "evidence_items": tuple(
                item for item in command.evidence_items if item.evidence_id != alpha_id
            )
        }
    )

    analysis = analyze_case(command)
    options = {option.option_id: option for option in analysis.response_options}

    assert options["RL-OPTION-EXPEDITE"].executable is False
    assert options["RL-OPTION-EXPEDITE"].blocking_codes == (
        "REQUIRED_EVIDENCE_MISSING",
    )
    assert options["RL-OPTION-COMBINED"].executable is False
    assert "RL-OPTION-COMBINED" in analysis.ranking.infeasible_option_ids


def test_global_authority_scope_failure_prevents_combined_recommendation():
    command = _command("RL-EVAL-GLOBAL-AUTHORITY-MISMATCH").model_copy(
        update={"required_authority_scope": (AuthorityScope.SUPPLIER_STATEMENT,)}
    )

    analysis = analyze_case(command)

    assert analysis.evidence_validation.blocking_codes == ("AUTHORITY_SCOPE_MISMATCH",)
    assert analysis.ranking.recommended_option_id is None
    assert analysis.ranking.no_feasible_mitigation is True
    assert all(
        "AUTHORITY_SCOPE_MISMATCH" in option.blocking_codes
        for option in analysis.response_options
        if option.active_mitigation
    )


def test_approved_beta_without_quality_satisfaction_is_not_feasible():
    command, _ = beta_approved_case()
    command = command.model_copy(
        update={
            "standing_authorizations": tuple(
                authorization
                for authorization in command.standing_authorizations
                if authorization.role != "quality_approver"
            )
        }
    )

    analysis = analyze_case(command)
    beta = next(
        option
        for option in analysis.response_options
        if option.option_id == "RL-OPTION-BETA"
    )

    assert beta.executable is False
    assert "QUALITY_APPROVAL_UNSATISFIED" in beta.blocking_codes
    assert beta.option_id not in analysis.ranking.eligible_option_ids
