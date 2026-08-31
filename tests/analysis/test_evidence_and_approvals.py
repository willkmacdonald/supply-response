from datetime import timedelta
from decimal import Decimal

import pytest

from data.domain.analysis import AnalysisMaterial, PredictedOutcome, ResponseOption
from data.domain.common import RuntimeMode
from data.domain.decisions import ApprovalSatisfaction, StandingAuthorization
from data.domain.evidence import (
    ConflictResolution,
    EvidenceConflict,
    EvidenceItem,
    EvidenceKind,
)
from data.synthetic.rl001 import OperationalSnapshot, SCENARIO_EFFECTIVE_TIME
from services.analysis.service import analysis_material_hash, create_analysis_version
from services.policy.approvals import evaluate_approval_satisfaction
from services.policy.evidence import (
    PolicyViolation,
    resolve_conflict,
    validate_required_evidence,
)


def evidence_item(
    *,
    kind: EvidenceKind | str = EvidenceKind.OPERATIONAL_FACT,
    source_system: str = "RL-FABRIC",
    citation_url: str | None = "https://rl.example/evidence/RL-E-1",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id="RL-E-1",
        case_id="RL-CASE-1",
        kind=kind,
        authority_scope=("RL-FIELD-SUPPLIER-COMMITMENT",),
        source_system=source_system,
        source_id="RL-SOURCE-1",
        source_timestamp=SCENARIO_EFFECTIVE_TIME - timedelta(hours=1),
        retrieved_at=SCENARIO_EFFECTIVE_TIME,
        effective_at=SCENARIO_EFFECTIVE_TIME,
        expires_at=SCENARIO_EFFECTIVE_TIME + timedelta(days=1),
        claim="RL supplier commitment exists.",
        excerpt="RL supplier committed a partial receipt.",
        citation_url=citation_url,
        runtime_mode=RuntimeMode.LIVE,
        synthetic=False,
    )


def evidence_conflict(*, feasibility_relevant: bool) -> EvidenceConflict:
    return EvidenceConflict(
        conflict_id="RL-CONFLICT-1",
        case_id="RL-CASE-1",
        evidence_ids=("RL-E-1", "RL-E-2"),
        authority_scope=("RL-FIELD-SUPPLIER-COMMITMENT",),
        description="RL sources disagree on the supplier commitment.",
        feasibility_relevant=feasibility_relevant,
    )


def combined_option() -> ResponseOption:
    return ResponseOption(
        option_id="RL-OPTION-COMBINED",
        name="RL combined response",
        executable=True,
        active_mitigation=True,
        predicted=PredictedOutcome(
            uncovered_part_demand=2300,
            otif_loss_percentage=50,
            revenue_at_risk=Decimal("375000"),
            margin_at_risk=Decimal("125000"),
            response_cost=Decimal("24750"),
        ),
        prerequisite_roles=("material_planner", "finance_approver"),
    )


def taylor_authorization() -> StandingAuthorization:
    return StandingAuthorization.taylor_rl001()


def test_uncited_required_workiq_evidence_blocks_authoritative_analysis():
    evidence = evidence_item(
        kind="source_statement", source_system="work_iq", citation_url=None
    )
    result = validate_required_evidence((evidence,), runtime_mode=RuntimeMode.LIVE)
    assert result.blocking_codes == ("REQUIRED_CITATION_MISSING",)


def test_agent_cannot_resolve_a_feasibility_relevant_conflict():
    conflict = evidence_conflict(feasibility_relevant=True)
    with pytest.raises(PolicyViolation, match="authorized human"):
        resolve_conflict(
            conflict,
            actor_roles=("agent",),
            governing_evidence_id="RL-E-2",
        )


def test_taylor_standing_authorization_satisfies_combined_finance_prerequisite():
    result = evaluate_approval_satisfaction(
        option=combined_option(),
        analysis_id="RL-ANALYSIS-1",
        standing_authorizations=(taylor_authorization(),),
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
    )
    assert [(item.role, item.satisfied) for item in result] == [
        ("finance_approver", True)
    ]
    assert result[0].persona_id == "RL-PERSONA-TAYLOR"


def test_evidence_validation_reports_each_field_scoped_blocking_code():
    stale_and_expired = evidence_item().model_copy(
        update={
            "source_timestamp": None,
            "expires_at": SCENARIO_EFFECTIVE_TIME - timedelta(seconds=1),
        }
    )
    conflict = evidence_conflict(feasibility_relevant=True)

    result = validate_required_evidence(
        (stale_and_expired,),
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        required_authority_scope=("RL-FIELD-QUALIFICATION",),
        conflicts=(conflict,),
    )

    assert result.blocking_codes == (
        "EVIDENCE_TIMESTAMP_STALE",
        "EVIDENCE_EXPIRED",
        "EVIDENCE_CONFLICT_UNRESOLVED",
        "AUTHORITY_SCOPE_MISMATCH",
    )


def test_typed_human_resolution_clears_only_the_matching_conflict():
    conflict = evidence_conflict(feasibility_relevant=True)
    resolution = resolve_conflict(
        conflict,
        actor_roles=("material_planner",),
        governing_evidence_id="RL-E-2",
    )
    assert resolution == ConflictResolution(
        conflict_id="RL-CONFLICT-1",
        governing_evidence_id="RL-E-2",
        actor_roles=("material_planner",),
    )

    result = validate_required_evidence(
        (evidence_item(),),
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        conflicts=(conflict,),
        conflict_resolutions=(resolution,),
    )
    assert "EVIDENCE_CONFLICT_UNRESOLVED" not in result.blocking_codes


def test_forged_resolution_with_nonmember_evidence_does_not_clear_conflict():
    conflict = evidence_conflict(feasibility_relevant=True)
    forged = ConflictResolution(
        conflict_id="RL-CONFLICT-1",
        governing_evidence_id="RL-E-999",
        actor_roles=("material_planner",),
    )
    result = validate_required_evidence(
        (evidence_item(),),
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        conflicts=(conflict,),
        conflict_resolutions=(forged,),
    )
    assert "EVIDENCE_CONFLICT_UNRESOLVED" in result.blocking_codes


def test_agent_cannot_resolve_even_a_context_only_conflict():
    with pytest.raises(PolicyViolation, match="authorized human"):
        resolve_conflict(
            evidence_conflict(feasibility_relevant=False),
            actor_roles=("agent",),
            governing_evidence_id="RL-E-1",
        )


def test_taylor_authorization_has_exact_scope_and_inclusive_scenario_window():
    authorization = taylor_authorization()
    assert authorization.allowed_option_kinds == ("expedite", "combined")
    assert authorization.corpus_scope == "demo_corpus"
    assert str(authorization.maximum_response_cost) == "25000"
    assert {item.value for item in authorization.forbidden_external_side_effects} == {
        "external_sending",
        "purchase_order_change",
        "financial_commitment",
    }
    assert authorization.permits(combined_option(), authorization.valid_from)
    assert authorization.permits(combined_option(), authorization.valid_through)
    assert not authorization.permits(
        combined_option(), authorization.valid_through + timedelta(microseconds=1)
    )


def test_material_planner_remains_a_prerequisite_without_invented_satisfaction():
    result = evaluate_approval_satisfaction(
        option=combined_option(),
        analysis_id="RL-ANALYSIS-2",
        standing_authorizations=(taylor_authorization(),),
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
    )
    assert [item.role for item in result] == ["finance_approver"]
    assert "material_planner" in combined_option().prerequisite_roles


def analysis_material(item: EvidenceItem) -> AnalysisMaterial:
    return AnalysisMaterial.from_inputs(
        case_id="RL-CASE-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        operational_snapshot=OperationalSnapshot.rl001(),
        evidence_items=(item,),
        response_options=(combined_option(),),
        approval_satisfactions=(),
        conflict_resolutions=(),
        calculation_version="RL-CALC-V1",
        evidence_policy_version="RL-EVIDENCE-POLICY-V1",
        approval_policy_version="RL-APPROVAL-POLICY-V1",
    )


def material_with_satisfaction(analysis_id: str) -> AnalysisMaterial:
    satisfaction = ApprovalSatisfaction.from_authorization(
        analysis_id,
        combined_option(),
        taylor_authorization(),
    )
    return AnalysisMaterial.from_inputs(
        case_id="RL-CASE-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        operational_snapshot=OperationalSnapshot.rl001(),
        evidence_items=(evidence_item(),),
        response_options=(combined_option(),),
        approval_satisfactions=(satisfaction,),
        conflict_resolutions=(),
        calculation_version="RL-CALC-V1",
        evidence_policy_version="RL-EVIDENCE-POLICY-V1",
        approval_policy_version="RL-APPROVAL-POLICY-V1",
    )


def test_material_hash_ignores_retrieval_retries_and_display_only_metadata():
    original = evidence_item()
    retried = original.model_copy(
        update={
            "retrieved_at": original.retrieved_at + timedelta(minutes=5),
            "excerpt": "RL display excerpt with the same normalized claim.",
            "citation_url": "https://rl.example/evidence/RL-E-1?display=compact",
        }
    )

    assert analysis_material_hash(
        analysis_material(original)
    ) == analysis_material_hash(analysis_material(retried))


def test_material_hash_changes_when_normalized_evidence_content_changes():
    original = evidence_item()
    changed = original.model_copy(update={"claim": "RL supplier commitment changed."})
    assert analysis_material_hash(
        analysis_material(original)
    ) != analysis_material_hash(analysis_material(changed))


def test_material_hash_excludes_analysis_instance_identity():
    assert analysis_material_hash(
        material_with_satisfaction("RL-ANALYSIS-10")
    ) == analysis_material_hash(material_with_satisfaction("RL-ANALYSIS-11"))


def test_create_analysis_version_uses_injected_clock_and_material_hash():
    created_at = SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2)
    analysis = create_analysis_version(
        analysis_id="RL-ANALYSIS-3",
        case_id="RL-CASE-1",
        operational_snapshot=OperationalSnapshot.rl001(),
        evidence_items=(evidence_item(),),
        response_options=(combined_option(),),
        standing_authorizations=(taylor_authorization(),),
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        created_at=created_at,
        calculation_version="RL-CALC-V1",
    )
    assert analysis.created_at == created_at
    assert analysis.material_hash == analysis_material_hash(analysis.material)
    assert [
        (item.role, item.option_id) for item in analysis.approval_satisfactions
    ] == [("finance_approver", "RL-OPTION-COMBINED")]
    with pytest.raises(Exception, match="frozen"):
        analysis.material_hash = "RL-MUTATED"
