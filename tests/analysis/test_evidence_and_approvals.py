from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from data.domain.analysis import (
    AnalysisMaterial,
    PredictedOutcome,
    ResponseOption,
    ResponseOptionKind,
)
from data.domain.cases import CaseInstance
from data.domain.common import CasePurpose, RuntimeMode
from data.domain.decisions import (
    ApprovalSatisfaction,
    ApprovalTarget,
    CorpusScope,
    ExternalSideEffect,
    StandingAuthorization,
)
from data.domain.evidence import (
    ActorProvenance,
    AuthorityScope,
    BusinessValidityState,
    ConflictResolution,
    EvidenceConflict,
    EvidenceItem,
    EvidenceKind,
    EvidenceRequirement,
    EvidenceSourceSystem,
    FreshnessState,
    IdentitySource,
    RetrievalHealth,
    UncertaintyState,
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
    evidence_id: str = "RL-E-1",
    kind: EvidenceKind | str = EvidenceKind.SOURCE_STATEMENT,
    authority_scope: tuple[AuthorityScope | str, ...] = (
        AuthorityScope.SUPPLIER_STATEMENT,
    ),
    source_system: EvidenceSourceSystem | str = EvidenceSourceSystem.WORK_IQ,
    citation_url: str | None = "https://rl.example/evidence/RL-E-1",
    requirement: EvidenceRequirement = EvidenceRequirement.REQUIRED_AUTHORITATIVE,
    runtime_mode: RuntimeMode = RuntimeMode.LIVE,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        case_id="RL-CASE-1",
        kind=kind,
        authority_scope=authority_scope,
        source_system=source_system,
        source_id="RL-SOURCE-1",
        source_timestamp=SCENARIO_EFFECTIVE_TIME - timedelta(hours=1),
        retrieved_at=SCENARIO_EFFECTIVE_TIME,
        retrieved_for_analysis_id="RL-ANALYSIS-1",
        retrieval_health=RetrievalHealth.HEALTHY,
        effective_at=SCENARIO_EFFECTIVE_TIME,
        expires_at=SCENARIO_EFFECTIVE_TIME + timedelta(days=1),
        claim="RL supplier commitment exists.",
        excerpt="RL supplier committed a partial receipt.",
        citation_url=citation_url,
        runtime_mode=runtime_mode,
        synthetic=False,
        requirement=requirement,
        uncertainty_state=UncertaintyState.CERTAIN,
    )


def evidence_conflict(*, feasibility_relevant: bool) -> EvidenceConflict:
    return EvidenceConflict(
        conflict_id="RL-CONFLICT-1",
        case_id="RL-CASE-1",
        evidence_ids=("RL-E-1", "RL-E-2"),
        authority_scope=(AuthorityScope.SUPPLIER_STATEMENT,),
        description="RL sources disagree on the supplier commitment.",
        feasibility_relevant=feasibility_relevant,
    )


def alex_actor(*, roles: tuple[str, ...] = ("material_planner",)) -> ActorProvenance:
    return ActorProvenance(
        persona_id="RL-PERSONA-ALEX",
        roles=roles,
        identity_source=IdentitySource.ENTRA,
        source_id="RL-ENTRA-ALEX",
    )


def current_evidence_validation(
    evidence_items: tuple[EvidenceItem, ...] | None = None,
):
    return validate_required_evidence(
        evidence_items
        or (
            evidence_item(evidence_id="RL-E-1"),
            evidence_item(evidence_id="RL-E-2"),
        ),
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
    )


def combined_option(
    *,
    option_kind: ResponseOptionKind = ResponseOptionKind.COMBINED,
    response_cost: Decimal = Decimal("24750"),
    requested_side_effects: tuple[ExternalSideEffect, ...] = (),
) -> ResponseOption:
    return ResponseOption(
        option_id="RL-OPTION-COMBINED",
        option_kind=option_kind,
        name="RL combined response",
        executable=True,
        active_mitigation=True,
        predicted=PredictedOutcome(
            uncovered_part_demand=2300,
            otif_loss_percentage=50,
            revenue_at_risk=Decimal("375000"),
            margin_at_risk=Decimal("125000"),
            response_cost=response_cost,
        ),
        prerequisite_roles=("material_planner", "finance_approver"),
        requested_side_effects=requested_side_effects,
    )


def taylor_authorization() -> StandingAuthorization:
    return StandingAuthorization.taylor_rl001()


def case_instance(
    *,
    case_id: str = "RL-CASE-1",
    runtime_mode: RuntimeMode = RuntimeMode.LIVE,
) -> CaseInstance:
    return CaseInstance(
        case_id=case_id,
        template_id="RL-001",
        purpose=CasePurpose.SHOWCASE,
        runtime_mode=runtime_mode,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
    )


def approval_target(
    option: ResponseOption,
    *,
    corpus: CorpusScope = CorpusScope.DEMO_CORPUS,
    scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
    total_response_cost: Decimal | None = None,
    requested_side_effects: tuple[ExternalSideEffect, ...] | None = None,
) -> ApprovalTarget:
    assert option.predicted is not None
    target_case = case_instance().model_copy(
        update={"scenario_effective_time": scenario_effective_time}
    )
    return ApprovalTarget(
        case=target_case,
        corpus=corpus,
        scenario_effective_time=scenario_effective_time,
        total_response_cost=(
            option.predicted.response_cost
            if total_response_cost is None
            else total_response_cost
        ),
        requested_side_effects=(
            option.requested_side_effects
            if requested_side_effects is None
            else requested_side_effects
        ),
    )


def test_uncited_required_workiq_evidence_blocks_authoritative_analysis():
    evidence = evidence_item(
        kind="source_statement", source_system="work_iq", citation_url=None
    )
    result = validate_required_evidence(
        (evidence,),
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
    )
    assert result.blocking_codes == ("REQUIRED_CITATION_MISSING",)


def test_agent_cannot_resolve_a_feasibility_relevant_conflict():
    conflict = evidence_conflict(feasibility_relevant=True)
    with pytest.raises(PolicyViolation, match="authorized human"):
        resolve_conflict(
            conflict,
            evidence_validation=current_evidence_validation(),
            actor=alex_actor(roles=("agent",)),
            governing_evidence_id="RL-E-2",
            why="RL agent attempted to choose a source.",
        )


def test_taylor_standing_authorization_satisfies_combined_finance_prerequisite():
    option = combined_option()
    result = evaluate_approval_satisfaction(
        option=option,
        analysis_id="RL-ANALYSIS-1",
        standing_authorizations=(taylor_authorization(),),
        target=approval_target(option),
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
        (stale_and_expired, evidence_item(evidence_id="RL-E-2")),
        runtime_mode=RuntimeMode.LIVE,
        analysis_id="RL-ANALYSIS-1",
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
        required_authority_scope=(AuthorityScope.QUALIFICATION_STATE,),
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
        evidence_validation=current_evidence_validation(),
        actor=alex_actor(),
        governing_evidence_id="RL-E-2",
        why="RL supplier citation is the current governing statement.",
    )
    assert resolution == ConflictResolution(
        conflict_id="RL-CONFLICT-1",
        governing_evidence_id="RL-E-2",
        actor=alex_actor(),
        why="RL supplier citation is the current governing statement.",
    )

    result = validate_required_evidence(
        (
            evidence_item(evidence_id="RL-E-1"),
            evidence_item(evidence_id="RL-E-2"),
        ),
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
        conflicts=(conflict,),
        conflict_resolutions=(resolution,),
    )
    assert "EVIDENCE_CONFLICT_UNRESOLVED" not in result.blocking_codes


def test_forged_resolution_with_nonmember_evidence_does_not_clear_conflict():
    conflict = evidence_conflict(feasibility_relevant=True)
    forged = ConflictResolution(
        conflict_id="RL-CONFLICT-1",
        governing_evidence_id="RL-E-999",
        actor=alex_actor(),
        why="RL attempted to select an unrelated source.",
    )
    with pytest.raises(PolicyViolation, match="governing evidence"):
        validate_required_evidence(
            (
                evidence_item(evidence_id="RL-E-1"),
                evidence_item(evidence_id="RL-E-2"),
            ),
            analysis_id="RL-ANALYSIS-1",
            runtime_mode=RuntimeMode.LIVE,
            scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
            analysis_started_at=SCENARIO_EFFECTIVE_TIME,
            analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
            conflicts=(conflict,),
            conflict_resolutions=(forged,),
        )


def test_agent_cannot_resolve_even_a_context_only_conflict():
    with pytest.raises(PolicyViolation, match="authorized human"):
        resolve_conflict(
            evidence_conflict(feasibility_relevant=False),
            evidence_validation=current_evidence_validation(),
            actor=alex_actor(roles=("agent",)),
            governing_evidence_id="RL-E-1",
            why="RL agent attempted to choose a source.",
        )


@pytest.mark.parametrize(
    "actor",
    (
        ActorProvenance(
            persona_id="RL-PERSONA-ALEX",
            roles=(),
            identity_source=IdentitySource.ENTRA,
            source_id="RL-ENTRA-ALEX",
        ),
        ActorProvenance(
            persona_id="RL-PERSONA-UNKNOWN",
            roles=("material_planner",),
            identity_source=IdentitySource.ENTRA,
            source_id="RL-ENTRA-UNKNOWN",
        ),
        ActorProvenance(
            persona_id="RL-PERSONA-TAYLOR",
            roles=("material_planner",),
            identity_source=IdentitySource.ENTRA,
            source_id="RL-ENTRA-TAYLOR",
        ),
        ActorProvenance(
            persona_id="RL-PERSONA-ALEX",
            roles=("material_planner",),
            identity_source=IdentitySource.ENTRA,
            source_id="",
        ),
    ),
)
def test_forged_actor_provenance_cannot_resolve_conflict(actor):
    with pytest.raises(PolicyViolation, match="authorized human"):
        resolve_conflict(
            evidence_conflict(feasibility_relevant=True),
            evidence_validation=current_evidence_validation(),
            actor=actor,
            governing_evidence_id="RL-E-1",
            why="RL actor attempted to choose a source.",
        )


def test_directly_constructed_forged_resolution_is_revalidated_at_consumption():
    forged = ConflictResolution(
        conflict_id="RL-CONFLICT-1",
        governing_evidence_id="RL-E-1",
        actor=ActorProvenance(
            persona_id="RL-PERSONA-TAYLOR",
            roles=("material_planner",),
            identity_source=IdentitySource.ENTRA,
            source_id="RL-ENTRA-TAYLOR",
        ),
        why="RL forged actor attempted to choose a source.",
    )
    with pytest.raises(PolicyViolation, match="authorized human"):
        validate_required_evidence(
            (
                evidence_item(evidence_id="RL-E-1"),
                evidence_item(evidence_id="RL-E-2"),
            ),
            analysis_id="RL-ANALYSIS-1",
            runtime_mode=RuntimeMode.LIVE,
            scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
            analysis_started_at=SCENARIO_EFFECTIVE_TIME,
            analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
            conflicts=(evidence_conflict(feasibility_relevant=True),),
            conflict_resolutions=(forged,),
        )


def test_mismatched_nonblank_identity_source_cannot_resolve_conflict():
    actor = alex_actor().model_copy(update={"source_id": "RL-ENTRA-SOMEONE-ELSE"})
    with pytest.raises(PolicyViolation, match="authorized human"):
        resolve_conflict(
            evidence_conflict(feasibility_relevant=True),
            evidence_validation=current_evidence_validation(),
            actor=actor,
            governing_evidence_id="RL-E-1",
            why="RL mismatched identity attempted to choose a source.",
        )


@pytest.mark.parametrize(
    ("source_system", "kind", "authority_scope"),
    (
        (
            EvidenceSourceSystem.WORK_IQ,
            EvidenceKind.SOURCE_STATEMENT,
            (AuthorityScope.OPERATIONAL_QUANTITY,),
        ),
        (
            EvidenceSourceSystem.WORK_IQ,
            EvidenceKind.CONTEXTUAL_EVIDENCE,
            (AuthorityScope.QUALIFICATION_STATE,),
        ),
        (
            EvidenceSourceSystem.FABRIC,
            EvidenceKind.OPERATIONAL_FACT,
            (AuthorityScope.PREREQUISITE_APPROVAL,),
        ),
    ),
)
def test_source_system_cannot_self_assert_an_unauthorized_scope(
    source_system, kind, authority_scope
):
    item = evidence_item(
        source_system=source_system,
        kind=kind,
        authority_scope=authority_scope,
    )
    result = validate_required_evidence(
        (item,),
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
        required_authority_scope=authority_scope,
    )
    assert "AUTHORITY_SCOPE_MISMATCH" in result.blocking_codes
    assert result.item_results[0].authoritative is False


def test_contextual_evidence_is_visible_but_cannot_satisfy_a_gate():
    item = evidence_item(
        kind=EvidenceKind.CONTEXTUAL_EVIDENCE,
        authority_scope=(AuthorityScope.COLLABORATION_STATEMENT,),
        requirement=EvidenceRequirement.CONTEXTUAL,
        citation_url=None,
    )
    result = validate_required_evidence(
        (item,),
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
        required_authority_scope=(AuthorityScope.COLLABORATION_STATEMENT,),
    )
    assert result.item_results[0].authoritative is False
    assert result.item_results[0].requirement == EvidenceRequirement.CONTEXTUAL
    assert result.blocking_codes == ("AUTHORITY_SCOPE_MISMATCH",)


def test_contextual_kind_cannot_self_promote_by_claiming_required_status():
    item = evidence_item(
        kind=EvidenceKind.CONTEXTUAL_EVIDENCE,
        authority_scope=(AuthorityScope.COLLABORATION_STATEMENT,),
        requirement=EvidenceRequirement.REQUIRED_AUTHORITATIVE,
    )
    result = validate_required_evidence(
        (item,),
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
        required_authority_scope=(AuthorityScope.COLLABORATION_STATEMENT,),
    )
    assert result.item_results[0].authoritative is False
    assert result.blocking_codes == ("AUTHORITY_SCOPE_MISMATCH",)


@pytest.mark.parametrize(
    ("source_system", "runtime_mode"),
    (
        (EvidenceSourceSystem.FABRIC, RuntimeMode.FALLBACK),
        (EvidenceSourceSystem.SQLITE, RuntimeMode.LIVE),
        (EvidenceSourceSystem.SYNTHETIC_FIXTURE, RuntimeMode.LIVE),
        (EvidenceSourceSystem.WORK_IQ, RuntimeMode.FALLBACK),
    ),
)
def test_source_authority_is_bound_to_its_runtime_mode(source_system, runtime_mode):
    operational = source_system != EvidenceSourceSystem.WORK_IQ
    item = evidence_item(
        kind=(
            EvidenceKind.OPERATIONAL_FACT
            if operational
            else EvidenceKind.SOURCE_STATEMENT
        ),
        authority_scope=(
            (AuthorityScope.OPERATIONAL_QUANTITY,)
            if operational
            else (AuthorityScope.SUPPLIER_STATEMENT,)
        ),
        source_system=source_system,
        runtime_mode=runtime_mode,
    )
    result = validate_required_evidence(
        (item,),
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=runtime_mode,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
        required_authority_scope=item.authority_scope,
    )
    assert result.item_results[0].authoritative is False
    assert "AUTHORITY_SCOPE_MISMATCH" in result.blocking_codes


def test_future_effective_and_exact_expiry_are_typed_business_invalidity():
    future = evidence_item(evidence_id="RL-E-FUTURE").model_copy(
        update={"effective_at": SCENARIO_EFFECTIVE_TIME + timedelta(seconds=1)}
    )
    expired = evidence_item(evidence_id="RL-E-EXPIRED").model_copy(
        update={"expires_at": SCENARIO_EFFECTIVE_TIME}
    )
    result = validate_required_evidence(
        (future, expired),
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
    )
    states = {item.evidence_id: item.business_validity for item in result.item_results}
    assert states == {
        "RL-E-EXPIRED": BusinessValidityState.EXPIRED,
        "RL-E-FUTURE": BusinessValidityState.NOT_YET_EFFECTIVE,
    }
    assert "EVIDENCE_NOT_YET_EFFECTIVE" in result.blocking_codes
    assert "EVIDENCE_EXPIRED" in result.blocking_codes


def test_scenario_clock_is_required_and_never_inferred_from_retrieval_time():
    with pytest.raises(TypeError, match="scenario_effective_time"):
        validate_required_evidence(
            (evidence_item(),),
            analysis_id="RL-ANALYSIS-1",
            runtime_mode=RuntimeMode.LIVE,
        )


def test_source_retrieval_order_and_current_analysis_health_are_visible():
    item = evidence_item().model_copy(
        update={
            "source_timestamp": SCENARIO_EFFECTIVE_TIME + timedelta(seconds=1),
            "retrieved_for_analysis_id": "RL-ANALYSIS-OLD",
            "retrieval_health": RetrievalHealth.UNHEALTHY,
        }
    )
    result = validate_required_evidence(
        (item,),
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
    )
    assert result.item_results[0].freshness == FreshnessState.STALE
    assert "EVIDENCE_TIMESTAMP_STALE" in result.blocking_codes
    assert "RETRIEVAL_HEALTH_UNACCEPTABLE" in result.blocking_codes
    assert result.policy_version == "evidence-policy-v3"


@pytest.mark.parametrize(
    "update",
    (
        {"source_id": ""},
        {"excerpt": "  "},
        {"citation_url": "RL-NOT-A-URL"},
        {"source_timestamp": None},
        {"retrieved_at": None},
    ),
)
def test_required_live_workiq_evidence_requires_complete_navigable_metadata(update):
    item = evidence_item().model_copy(update=update)
    result = validate_required_evidence(
        (item,),
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
    )
    assert result.blocking_codes
    assert result.item_results[0].authoritative is False


def test_taylor_authorization_has_exact_scope_and_inclusive_scenario_window():
    authorization = taylor_authorization()
    conditions = authorization.conditions
    assert conditions.allowed_option_kinds == (
        ResponseOptionKind.EXPEDITE,
        ResponseOptionKind.COMBINED,
    )
    assert conditions.allowed_corpora == (CorpusScope.DEMO_CORPUS,)
    assert str(conditions.maximum_response_cost) == "25000"
    assert {item.value for item in conditions.forbidden_external_side_effects} == {
        "external_sending",
        "purchase_order_change",
        "financial_commitment",
    }
    option = combined_option()
    assert authorization.permits(
        option,
        approval_target(option, scenario_effective_time=conditions.valid_from),
    )
    assert authorization.permits(
        option,
        approval_target(option, scenario_effective_time=conditions.valid_through),
    )
    assert not authorization.permits(
        option,
        approval_target(
            option,
            scenario_effective_time=conditions.valid_through
            + timedelta(microseconds=1),
        ),
    )


def test_material_planner_remains_a_prerequisite_without_invented_satisfaction():
    option = combined_option()
    result = evaluate_approval_satisfaction(
        option=option,
        analysis_id="RL-ANALYSIS-2",
        standing_authorizations=(taylor_authorization(),),
        target=approval_target(option),
    )
    assert [item.role for item in result] == ["finance_approver"]
    assert "material_planner" in combined_option().prerequisite_roles


@pytest.mark.parametrize(
    "corpus",
    (CorpusScope.REAL_BUSINESS, CorpusScope.UNSPECIFIED),
)
def test_taylor_rejects_non_demo_corpus_targets(corpus):
    option = combined_option()
    assert not taylor_authorization().permits(
        option, approval_target(option, corpus=corpus)
    )


@pytest.mark.parametrize("side_effect", tuple(ExternalSideEffect))
def test_taylor_rejects_every_forbidden_external_side_effect(side_effect):
    option = combined_option(requested_side_effects=(side_effect,))
    assert not taylor_authorization().permits(option, approval_target(option))


def test_taylor_cost_cap_is_inclusive_and_excess_is_rejected():
    at_cap = combined_option(response_cost=Decimal("25000"))
    above_cap = combined_option(response_cost=Decimal("25000.01"))
    authorization = taylor_authorization()
    assert authorization.permits(at_cap, approval_target(at_cap))
    assert not authorization.permits(above_cap, approval_target(above_cap))


def test_taylor_rejects_pre_window_and_disallowed_typed_option_kind():
    combined = combined_option()
    disguised_transfer = combined_option(option_kind=ResponseOptionKind.TRANSFER)
    authorization = taylor_authorization()
    assert not authorization.permits(
        combined,
        approval_target(
            combined,
            scenario_effective_time=authorization.conditions.valid_from
            - timedelta(microseconds=1),
        ),
    )
    assert not authorization.permits(
        disguised_transfer,
        approval_target(disguised_transfer),
    )


def test_taylor_rejects_a_target_cost_that_differs_from_the_option():
    option = combined_option()
    assert not taylor_authorization().permits(
        option,
        approval_target(option, total_response_cost=Decimal("1")),
    )


def test_approval_satisfaction_snapshots_target_and_all_authorization_conditions():
    option = combined_option()
    target = approval_target(option)
    result = evaluate_approval_satisfaction(
        option=option,
        analysis_id="RL-ANALYSIS-1",
        standing_authorizations=(taylor_authorization(),),
        target=target,
    )
    assert result[0].target == target
    assert result[0].authorization_conditions == taylor_authorization().conditions


def test_direct_approval_satisfaction_cannot_bypass_target_policy():
    option = combined_option()
    with pytest.raises(ValueError, match="does not permit"):
        ApprovalSatisfaction.from_authorization(
            "RL-ANALYSIS-1",
            option,
            taylor_authorization(),
            approval_target(option, corpus=CorpusScope.REAL_BUSINESS),
        )


def analysis_material(item: EvidenceItem, **analysis_overrides) -> AnalysisMaterial:
    return create_analysis(evidence_items=(item,), **analysis_overrides).material


def material_with_satisfaction(analysis_id: str) -> AnalysisMaterial:
    item = evidence_item().model_copy(update={"retrieved_for_analysis_id": analysis_id})
    return create_analysis(
        analysis_id=analysis_id,
        evidence_items=(item,),
    ).material


def test_material_hash_ignores_retrieval_retries_and_display_only_metadata():
    original = evidence_item()
    retried = original.model_copy(
        update={
            "retrieved_at": original.retrieved_at + timedelta(minutes=5),
            "excerpt": "RL display excerpt with the same normalized claim.",
            "citation_url": "https://rl.example/evidence/RL-E-1?display=compact",
        }
    )
    recording_time = SCENARIO_EFFECTIVE_TIME + timedelta(minutes=5)

    assert analysis_material_hash(
        analysis_material(original, created_at=recording_time)
    ) == analysis_material_hash(analysis_material(retried, created_at=recording_time))


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
    case = case_instance()
    analysis = create_analysis_version(
        analysis_id="RL-ANALYSIS-3",
        case=case,
        corpus=CorpusScope.DEMO_CORPUS,
        operational_snapshot=OperationalSnapshot.rl001(
            case_id=case.case_id, runtime_mode=case.runtime_mode
        ),
        evidence_items=(
            evidence_item().model_copy(
                update={"retrieved_for_analysis_id": "RL-ANALYSIS-3"}
            ),
        ),
        response_options=(combined_option(),),
        standing_authorizations=(taylor_authorization(),),
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
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


def create_analysis(**overrides):  # allowed
    analysis_id = overrides.pop("analysis_id", "RL-ANALYSIS-1")
    case = overrides.pop("case", case_instance())
    defaults = {
        "analysis_id": analysis_id,
        "case": case,
        "corpus": CorpusScope.DEMO_CORPUS,
        "operational_snapshot": OperationalSnapshot.rl001(
            case_id=case.case_id,
            runtime_mode=case.runtime_mode,
        ),
        "evidence_items": (evidence_item(),),
        "response_options": (combined_option(),),
        "standing_authorizations": (taylor_authorization(),),
        "analysis_started_at": SCENARIO_EFFECTIVE_TIME,
        "created_at": SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
        "calculation_version": "RL-CALC-V1",
    }
    defaults.update(overrides)
    return create_analysis_version(**defaults)


@pytest.mark.parametrize(
    "overrides",
    (
        {
            "evidence_items": (
                evidence_item().model_copy(update={"case_id": "RL-CASE-2"}),
            )
        },
        {
            "evidence_items": (
                evidence_item().model_copy(
                    update={"runtime_mode": RuntimeMode.FALLBACK}
                ),
            )
        },
        {
            "conflicts": (
                evidence_conflict(feasibility_relevant=True).model_copy(
                    update={"case_id": "RL-CASE-2"}
                ),
            )
        },
    ),
)
def test_analysis_rejects_mixed_evidence_or_conflict_provenance(overrides):
    with pytest.raises(PolicyViolation, match="provenance"):
        create_analysis(**overrides)


def test_analysis_rejects_mixed_snapshot_case_and_mode_provenance():
    case = case_instance()
    wrong_case = OperationalSnapshot.rl001(
        case_id="RL-CASE-2", runtime_mode=RuntimeMode.LIVE
    )
    wrong_mode = OperationalSnapshot.rl001(
        case_id=case.case_id, runtime_mode=RuntimeMode.FALLBACK
    )
    with pytest.raises(PolicyViolation, match="provenance"):
        create_analysis(operational_snapshot=wrong_case)
    with pytest.raises(PolicyViolation, match="provenance"):
        create_analysis(operational_snapshot=wrong_mode)


def conflict_evidence_bundle():
    first = evidence_item(evidence_id="RL-E-1")
    second = evidence_item(evidence_id="RL-E-2")
    conflict = evidence_conflict(feasibility_relevant=True)
    resolution = resolve_conflict(
        conflict,
        evidence_validation=current_evidence_validation((first, second)),
        actor=alex_actor(),
        governing_evidence_id="RL-E-2",
        why="RL supplier citation is the current governing statement.",
    )
    return (first, second), conflict, resolution


def test_material_hash_changes_with_conflict_resolution_and_validation_state():
    evidence, conflict, resolution = conflict_evidence_bundle()
    unresolved = create_analysis(
        evidence_items=evidence,
        conflicts=(conflict,),
    )
    resolved = create_analysis(
        evidence_items=evidence,
        conflicts=(conflict,),
        conflict_resolutions=(resolution,),
    )
    expired = create_analysis(
        evidence_items=(
            evidence_item().model_copy(update={"expires_at": SCENARIO_EFFECTIVE_TIME}),
        ),
    )
    current = create_analysis()
    assert unresolved.material_hash != resolved.material_hash
    assert expired.material_hash != current.material_hash
    assert unresolved.material.evidence_validation.blocking_codes == (
        "EVIDENCE_CONFLICT_UNRESOLVED",
    )
    assert unresolved.material.conflicts[0].conflict_id == "RL-CONFLICT-1"


def test_required_authority_scope_is_material_even_when_satisfied():
    without_requirement = create_analysis(required_authority_scope=())
    with_requirement = create_analysis(
        required_authority_scope=(AuthorityScope.SUPPLIER_STATEMENT,)
    )
    assert without_requirement.material_hash != with_requirement.material_hash
    assert with_requirement.material.required_authority_scope == (
        AuthorityScope.SUPPLIER_STATEMENT,
    )


def test_full_authorization_conditions_are_material_under_a_reused_id():
    original = taylor_authorization()
    changed = original.model_copy(
        update={
            "conditions": original.conditions.model_copy(
                update={"maximum_response_cost": Decimal("24999")}
            )
        }
    )
    first = create_analysis(standing_authorizations=(original,))
    second = create_analysis(standing_authorizations=(changed,))
    assert first.material_hash != second.material_hash
    assert first.material.standing_authorizations[
        0
    ].conditions.maximum_response_cost == Decimal("25000")


def test_unordered_inputs_produce_the_same_material_hash():
    evidence, first_conflict, first_resolution = conflict_evidence_bundle()
    second_conflict = first_conflict.model_copy(update={"conflict_id": "RL-CONFLICT-2"})
    second_resolution = first_resolution.model_copy(
        update={"conflict_id": "RL-CONFLICT-2"}
    )
    expedite = combined_option(
        option_kind=ResponseOptionKind.EXPEDITE,
        response_cost=Decimal("22500"),
    ).model_copy(update={"option_id": "RL-OPTION-EXPEDITE"})
    other_authorization = taylor_authorization().model_copy(
        update={
            "authorization_id": "RL-AUTH-JORDAN-QUALITY-1",
            "persona_id": "RL-PERSONA-JORDAN",
            "role": "quality_approver",
        }
    )
    forwards = create_analysis(
        evidence_items=evidence,
        response_options=(combined_option(), expedite),
        conflicts=(first_conflict, second_conflict),
        conflict_resolutions=(first_resolution, second_resolution),
        standing_authorizations=(taylor_authorization(), other_authorization),
    )
    backwards = create_analysis(
        evidence_items=tuple(reversed(evidence)),
        response_options=(expedite, combined_option()),
        conflicts=(second_conflict, first_conflict),
        conflict_resolutions=(second_resolution, first_resolution),
        standing_authorizations=(other_authorization, taylor_authorization()),
    )
    assert forwards.material_hash == backwards.material_hash


def test_nested_operational_collections_are_canonicalized_by_stable_id():
    snapshot = OperationalSnapshot.rl001(
        case_id="RL-CASE-1", runtime_mode=RuntimeMode.LIVE
    )
    reversed_snapshot = snapshot.model_copy(
        update={
            "inventory_positions": tuple(reversed(snapshot.inventory_positions)),
            "production_orders": tuple(reversed(snapshot.production_orders)),
            "customer_orders": tuple(reversed(snapshot.customer_orders)),
        }
    )
    assert (
        create_analysis(operational_snapshot=snapshot).material_hash
        == create_analysis(operational_snapshot=reversed_snapshot).material_hash
    )


@pytest.mark.parametrize(
    ("field_name", "id_field"),
    (
        ("inventory_positions", "inventory_id"),
        ("production_orders", "production_order_id"),
        ("customer_orders", "customer_order_line_id"),
    ),
)
def test_duplicate_nested_operational_stable_ids_are_rejected(field_name, id_field):
    snapshot = OperationalSnapshot.rl001(
        case_id="RL-CASE-1", runtime_mode=RuntimeMode.LIVE
    )
    values = getattr(snapshot, field_name)
    duplicate = values[1].model_copy(update={id_field: getattr(values[0], id_field)})
    invalid = snapshot.model_copy(update={field_name: (values[0], duplicate)})
    with pytest.raises(ValueError, match=f"duplicate operational {field_name}"):
        create_analysis(operational_snapshot=invalid)


@pytest.mark.parametrize(
    "duplicate_field",
    (
        "evidence_items",
        "response_options",
        "conflicts",
        "conflict_resolutions",
        "standing_authorizations",
    ),
)
def test_duplicate_stable_ids_are_rejected(duplicate_field):
    evidence, conflict, resolution = conflict_evidence_bundle()
    duplicate_values = {
        "evidence_items": (evidence[0], evidence[0]),
        "response_options": (combined_option(), combined_option()),
        "conflicts": (conflict, conflict),
        "conflict_resolutions": (resolution, resolution),
        "standing_authorizations": (taylor_authorization(), taylor_authorization()),
    }
    overrides = {duplicate_field: duplicate_values[duplicate_field]}
    if duplicate_field == "conflict_resolutions":
        overrides.update(evidence_items=evidence, conflicts=(conflict,))
    with pytest.raises(ValueError, match="duplicate"):
        create_analysis(**overrides)


def assert_deeply_immutable(value):
    assert not isinstance(value, (dict, list, set))
    if isinstance(value, BaseModel):
        for field_name in type(value).model_fields:
            assert_deeply_immutable(getattr(value, field_name))
    elif isinstance(value, tuple):
        for item in value:
            assert_deeply_immutable(item)


def test_analysis_material_is_deeply_immutable_and_hash_remains_consistent():
    analysis = create_analysis(
        required_authority_scope=(AuthorityScope.SUPPLIER_STATEMENT,)
    )
    original_hash = analysis.material_hash
    assert_deeply_immutable(analysis.material)
    assert isinstance(analysis.material.operational_snapshot_json, str)
    with pytest.raises(ValidationError, match="frozen"):
        analysis.material.required_authority_scope = ()
    with pytest.raises(ValidationError, match="frozen"):
        analysis.material.response_options[0].blocking_codes = ("RL-MUTATED",)
    assert analysis_material_hash(analysis.material) == original_hash


def test_final_review_declared_conflict_scope_cannot_relabel_validated_scope():
    quality_items = tuple(
        evidence_item(
            evidence_id=evidence_id,
            kind=EvidenceKind.OPERATIONAL_FACT,
            authority_scope=(AuthorityScope.QUALIFICATION_STATE,),
            source_system=EvidenceSourceSystem.FABRIC,
        )
        for evidence_id in ("RL-E-QUALITY-1", "RL-E-QUALITY-2")
    )
    validation = validate_required_evidence(
        quality_items,
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
    )
    forged_scope = EvidenceConflict(
        conflict_id="RL-CONFLICT-QUALITY-1",
        case_id="RL-CASE-1",
        evidence_ids=("RL-E-QUALITY-1", "RL-E-QUALITY-2"),
        authority_scope=(AuthorityScope.SUPPLIER_STATEMENT,),
        description="RL qualification records disagree.",
        feasibility_relevant=True,
    )

    with pytest.raises(PolicyViolation, match="validated evidence scope"):
        resolve_conflict(
            forged_scope,
            evidence_validation=validation,
            actor=alex_actor(),
            governing_evidence_id="RL-E-QUALITY-1",
            why="RL planner selected the newer qualification record.",
        )
    with pytest.raises(PolicyViolation, match="validated evidence scope"):
        create_analysis(
            evidence_items=quality_items,
            conflicts=(forged_scope,),
        )


def test_final_review_unresolved_conflict_makes_each_item_nonauthoritative():
    evidence = (
        evidence_item(evidence_id="RL-E-1"),
        evidence_item(evidence_id="RL-E-2"),
    )
    validation = validate_required_evidence(
        evidence,
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
        conflicts=(evidence_conflict(feasibility_relevant=True),),
    )

    assert all(
        item.uncertainty_state == UncertaintyState.CONFLICTED
        and item.authoritative is False
        for item in validation.item_results
    )


def test_final_review_old_retrieval_relabelled_current_is_still_stale():
    analysis_started_at = SCENARIO_EFFECTIVE_TIME + timedelta(hours=2)
    relabelled = evidence_item().model_copy(
        update={"retrieved_for_analysis_id": "RL-ANALYSIS-1"}
    )

    validation = validate_required_evidence(
        (relabelled,),
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=analysis_started_at,
        analysis_recorded_at=analysis_started_at + timedelta(minutes=2),
    )

    assert validation.item_results[0].freshness == FreshnessState.STALE
    assert validation.item_results[0].business_validity == BusinessValidityState.VALID
    assert "EVIDENCE_RETRIEVAL_OUTSIDE_WINDOW" in validation.blocking_codes


@pytest.mark.parametrize(
    ("field_name", "claimed_version"),
    (
        ("evidence_policy_version", "RL-FORGED-EVIDENCE-POLICY"),
        ("approval_policy_version", "RL-FORGED-APPROVAL-POLICY"),
    ),
)
def test_final_review_analysis_rejects_unexecuted_policy_lineage(
    field_name, claimed_version
):
    with pytest.raises(PolicyViolation, match="policy version"):
        create_analysis(**{field_name: claimed_version})


def test_final_review_conflict_resolution_requires_nonblank_rationale():
    with pytest.raises(ValidationError, match="why"):
        ConflictResolution(
            conflict_id="RL-CONFLICT-1",
            governing_evidence_id="RL-E-1",
            actor=alex_actor(),
            why="   ",
        )


def test_final_review_conflict_rationale_is_material_and_changes_hash():
    evidence = (
        evidence_item(evidence_id="RL-E-1"),
        evidence_item(evidence_id="RL-E-2"),
    )
    validation = validate_required_evidence(
        evidence,
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
    )
    conflict = evidence_conflict(feasibility_relevant=True)
    first = resolve_conflict(
        conflict,
        evidence_validation=validation,
        actor=alex_actor(),
        governing_evidence_id="RL-E-2",
        why="RL supplier timestamp is newer.",
    )
    second = first.model_copy(
        update={"why": "RL supplier timestamp and citation are more reliable."}
    )

    first_analysis = create_analysis(
        evidence_items=evidence,
        conflicts=(conflict,),
        conflict_resolutions=(first,),
    )
    second_analysis = create_analysis(
        evidence_items=evidence,
        conflicts=(conflict,),
        conflict_resolutions=(second,),
    )

    assert first_analysis.material.conflict_resolutions[0].why == first.why
    assert first_analysis.material_hash != second_analysis.material_hash


def test_final_correction_fresh_wall_clock_windows_do_not_change_material_hash():
    first = create_analysis()
    later_start = SCENARIO_EFFECTIVE_TIME + timedelta(hours=1)
    later_retrieval = evidence_item().model_copy(
        update={
            "retrieved_at": later_start,
            "retrieved_for_analysis_id": "RL-ANALYSIS-2",
        }
    )
    second = create_analysis(
        analysis_id="RL-ANALYSIS-2",
        evidence_items=(later_retrieval,),
        analysis_started_at=later_start,
        created_at=later_start + timedelta(minutes=2),
    )

    assert first.evidence_validation == second.evidence_validation
    assert first.analysis_started_at != second.analysis_started_at
    assert first.retrieval_window_ends_at != second.retrieval_window_ends_at
    assert first.material_hash == second.material_hash
    assert "analysis_started_at" not in type(first.material).model_fields
    assert "retrieval_window_ends_at" not in type(first.material).model_fields


def test_final_correction_retrieval_after_analysis_recording_is_rejected():
    with pytest.raises(PolicyViolation, match="recording time"):
        create_analysis(
            evidence_items=(
                evidence_item().model_copy(
                    update={
                        "retrieved_at": SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2)
                    }
                ),
            ),
            created_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=1),
        )


def test_final_correction_conflict_scope_may_be_valid_evidence_scope_subset():
    evidence = tuple(
        evidence_item(
            evidence_id=evidence_id,
            authority_scope=(
                AuthorityScope.OPERATIONAL_QUANTITY,
                AuthorityScope.QUALIFICATION_STATE,
            ),
            kind=EvidenceKind.OPERATIONAL_FACT,
            source_system=EvidenceSourceSystem.FABRIC,
        )
        for evidence_id in ("RL-E-MULTISCOPE-1", "RL-E-MULTISCOPE-2")
    )
    validation = validate_required_evidence(
        evidence,
        analysis_id="RL-ANALYSIS-1",
        runtime_mode=RuntimeMode.LIVE,
        scenario_effective_time=SCENARIO_EFFECTIVE_TIME,
        analysis_started_at=SCENARIO_EFFECTIVE_TIME,
        analysis_recorded_at=SCENARIO_EFFECTIVE_TIME + timedelta(minutes=2),
    )
    conflict = EvidenceConflict(
        conflict_id="RL-CONFLICT-OPERATIONAL-SUBSET-1",
        case_id="RL-CASE-1",
        evidence_ids=("RL-E-MULTISCOPE-1", "RL-E-MULTISCOPE-2"),
        authority_scope=(AuthorityScope.OPERATIONAL_QUANTITY,),
        description="RL multiscope records disagree on operational quantity.",
        feasibility_relevant=True,
    )
    resolution = resolve_conflict(
        conflict,
        evidence_validation=validation,
        actor=alex_actor(),
        governing_evidence_id="RL-E-MULTISCOPE-2",
        why="RL supplier citation is newer.",
    )

    analysis = create_analysis(
        evidence_items=evidence,
        conflicts=(conflict,),
        conflict_resolutions=(resolution,),
    )

    assert (
        "EVIDENCE_CONFLICT_UNRESOLVED"
        not in analysis.evidence_validation.blocking_codes
    )
    assert analysis.material.conflicts[0].authority_scope == (
        AuthorityScope.OPERATIONAL_QUANTITY,
    )
