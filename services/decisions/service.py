from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from data.domain.analysis import AnalysisResponseOptionMaterial, AnalysisVersion
from data.domain.cases import CaseInstance
from data.domain.decisions import (
    ApprovalSatisfaction,
    ApprovalTarget,
    AuthorizationConditions,
    Decision,
    DecisionKind,
    IdentitySnapshot,
    RecordDecisionCommand,
    StandingAuthorization,
)
from data.domain.evidence import IdentitySource
from data.domain.execution import ActionPlanningRequested
from services.persistence.ports import UnitOfWork
from services.persistence.store import ImmutableRecordConflict


class DecisionError(RuntimeError):
    """Base error for immutable Decision recording."""


class DecisionPolicyViolation(DecisionError):
    """Raised when current state does not authorize a Decision."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "DECISION_POLICY_VIOLATION",
        role: str | None = None,
        blocking_codes: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.role = role
        self.blocking_codes = blocking_codes


class IdempotencyKeyConflict(DecisionError):
    """Raised when an idempotency key is reused for another request."""


UnitOfWorkFactory = Callable[[], UnitOfWork]


def _request_fingerprint(
    command: RecordDecisionCommand,
    actor: IdentitySnapshot,
) -> str:
    payload = {
        "actor": json.loads(actor.model_dump_json(exclude_none=False, by_alias=True)),
        "command": json.loads(
            command.model_dump_json(exclude_none=False, by_alias=True)
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DecisionPolicy:
    _ROLE_PERSONAS = {
        "finance_approver": "RL-PERSONA-TAYLOR",
        "quality_approver": "RL-PERSONA-JORDAN",
    }

    @staticmethod
    def _authorize_actor(
        command: RecordDecisionCommand,
        actor: IdentitySnapshot,
    ) -> None:
        if (
            actor.persona_id != "RL-PERSONA-ALEX"
            or actor.identity_source is not IdentitySource.ENTRA
            or actor.source_id != "RL-ENTRA-ALEX"
        ):
            raise DecisionPolicyViolation(
                "Decision requires the server-owned Alex identity",
                code="ROLE_REQUIRED",
                role="response_approver",
            )
        if "response_approver" not in actor.effective_roles:
            raise DecisionPolicyViolation(
                "Decision requires the response_approver role",
                code="ROLE_REQUIRED",
                role="response_approver",
            )
        if (
            command.kind is DecisionKind.APPROVED
            and "material_planner" not in actor.effective_roles
        ):
            raise DecisionPolicyViolation(
                "Approval requires the material_planner role",
                code="ROLE_REQUIRED",
                role="material_planner",
            )

    @staticmethod
    def _require_current_analysis(
        command: RecordDecisionCommand,
        case: CaseInstance,
        projection,
        analysis: AnalysisVersion,
    ) -> None:
        if analysis.analysis_id != command.analysis_id:
            raise DecisionPolicyViolation(
                "Decision analysis_id is inconsistent",
                code="STALE_ANALYSIS",
            )
        if analysis.case_id != command.case_id or case.case_id != command.case_id:
            raise DecisionPolicyViolation(
                "Decision case and analysis are inconsistent",
                code="STALE_ANALYSIS",
            )
        if (
            projection.current_analysis_id != analysis.analysis_id
            or projection.current_analysis_hash != analysis.material_hash
        ):
            raise DecisionPolicyViolation(
                "Decision must use the current analysis and material hash",
                code="STALE_ANALYSIS",
            )
        if (
            analysis.material.case_id != case.case_id
            or analysis.material.template_id != case.template_id
            or analysis.material.case_purpose is not case.purpose
            or analysis.material.runtime_mode is not case.runtime_mode
            or analysis.material.scenario_effective_time != case.scenario_effective_time
        ):
            raise DecisionPolicyViolation(
                "Current analysis provenance does not match the Case Instance",
                code="STALE_ANALYSIS",
            )

    @staticmethod
    def _selected_option(
        command: RecordDecisionCommand,
        analysis: AnalysisVersion,
    ):
        option = next(
            (
                item
                for item in analysis.response_options
                if item.option_id == command.selected_option_id
            ),
            None,
        )
        if option is None:
            raise DecisionPolicyViolation(
                "Selected option is not part of the current analysis",
                code="OPTION_NOT_IN_ANALYSIS",
            )
        material_option = next(
            (
                item
                for item in analysis.material.response_options
                if item.option_id == option.option_id
            ),
            None,
        )
        if (
            material_option is None
            or material_option != AnalysisResponseOptionMaterial.from_option(option)
        ):
            raise DecisionPolicyViolation(
                "Selected option snapshot conflicts with immutable analysis material"
            )
        if not option.executable or option.predicted is None or option.blocking_codes:
            raise DecisionPolicyViolation(
                "Selected option is not executable",
                code="OPTION_NOT_EXECUTABLE",
                blocking_codes=option.blocking_codes,
            )
        if option.option_id not in analysis.ranking.eligible_option_ids:
            raise DecisionPolicyViolation(
                "Selected option is absent from the ranking eligibility trace"
            )
        evidence_ids = {item.evidence_id for item in analysis.evidence_items}
        material_evidence_ids = {
            item.evidence_id for item in analysis.material.evidence
        }
        if not set(option.evidence_ids).issubset(
            evidence_ids.intersection(material_evidence_ids)
        ):
            raise DecisionPolicyViolation(
                "Selected option evidence lineage is incomplete"
            )
        return option

    @staticmethod
    def _target_matches_current_state(
        satisfaction: ApprovalSatisfaction,
        *,
        case: CaseInstance,
        analysis: AnalysisVersion,
        option,
    ) -> bool:
        target = satisfaction.target
        target_case = target.case
        predicted = option.predicted
        return bool(
            predicted is not None
            and target_case.case_id == case.case_id
            and target_case.template_id == case.template_id
            and target_case.purpose is case.purpose
            and target_case.runtime_mode is case.runtime_mode
            and target_case.scenario_effective_time == case.scenario_effective_time
            and target.corpus is analysis.material.corpus
            and target.scenario_effective_time == case.scenario_effective_time
            and target.total_response_cost == predicted.response_cost
            and target.requested_side_effects == option.requested_side_effects
        )

    def _revalidate_existing_satisfactions(
        self,
        *,
        case: CaseInstance,
        analysis: AnalysisVersion,
        option,
    ) -> tuple[ApprovalSatisfaction, ...]:
        option_satisfactions = tuple(
            item
            for item in analysis.approval_satisfactions
            if item.option_id == option.option_id
        )
        if any(not item.satisfied for item in option_satisfactions):
            raise DecisionPolicyViolation(
                "Selected option contains an unsatisfied approval prerequisite"
            )

        required_roles = set(option.prerequisite_roles) - {
            "material_planner",
            "response_approver",
        }
        accepted: list[ApprovalSatisfaction] = []
        for role in sorted(required_roles):
            expected_persona = self._ROLE_PERSONAS.get(role)
            candidates = tuple(
                item
                for item in option_satisfactions
                if item.role == role
                and item.satisfied
                and (expected_persona is None or item.persona_id == expected_persona)
            )
            valid = tuple(
                item
                for item in candidates
                if self._target_matches_current_state(
                    item,
                    case=case,
                    analysis=analysis,
                    option=option,
                )
                and StandingAuthorization(
                    authorization_id=item.authorization_id,
                    persona_id=item.persona_id,
                    role=item.role,
                    conditions=item.authorization_conditions,
                ).permits(option, item.target)
            )
            if len(valid) != 1:
                raise DecisionPolicyViolation(
                    f"Selected option requires a current {role} satisfaction"
                )
            accepted.append(valid[0])
        return tuple(accepted)

    @staticmethod
    def _alex_material_planner_satisfaction(
        *,
        actor: IdentitySnapshot,
        case: CaseInstance,
        analysis: AnalysisVersion,
        option,
    ) -> ApprovalSatisfaction:
        assert option.predicted is not None
        scenario_time = case.scenario_effective_time
        authorization = StandingAuthorization(
            authorization_id="RL-AUTH-ALEX-MATERIAL-DECISION",
            persona_id=actor.persona_id,
            role="material_planner",
            conditions=AuthorizationConditions(
                allowed_option_kinds=(option.option_kind,),
                maximum_response_cost=option.predicted.response_cost,
                allowed_corpora=(analysis.material.corpus,),
                allowed_template_ids=(case.template_id,),
                allowed_case_purposes=(case.purpose,),
                valid_from=scenario_time,
                valid_through=scenario_time,
                forbidden_external_side_effects=(),
            ),
        )
        target = ApprovalTarget(
            case=case,
            corpus=analysis.material.corpus,
            scenario_effective_time=scenario_time,
            total_response_cost=option.predicted.response_cost,
            requested_side_effects=option.requested_side_effects,
        )
        return ApprovalSatisfaction.from_authorization(
            analysis.analysis_id,
            option,
            authorization,
            target,
        )

    def authorize_and_materialize(
        self,
        command: RecordDecisionCommand,
        actor: IdentitySnapshot,
        case: CaseInstance,
        projection,
        analysis: AnalysisVersion,
    ) -> tuple[ApprovalSatisfaction, ...]:
        self._authorize_actor(command, actor)
        self._require_current_analysis(command, case, projection, analysis)
        if command.kind is DecisionKind.REJECTED:
            return ()

        option = self._selected_option(command, analysis)
        existing = self._revalidate_existing_satisfactions(
            case=case,
            analysis=analysis,
            option=option,
        )
        material = self._alex_material_planner_satisfaction(
            actor=actor,
            case=case,
            analysis=analysis,
            option=option,
        )
        return tuple(sorted((*existing, material), key=lambda item: item.role))


class DecisionService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        *,
        policy: DecisionPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._policy = policy or DecisionPolicy()
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _return_existing(
        existing: Decision,
        request_fingerprint: str,
    ) -> Decision:
        if existing.request_fingerprint != request_fingerprint:
            raise IdempotencyKeyConflict(
                "idempotency key was already used for a different request"
            )
        return existing

    def _load_idempotent_result(
        self,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> Decision | None:
        with self._uow_factory() as uow:
            existing = uow.decisions.get_by_idempotency_key(idempotency_key)
            if existing is None:
                return None
            return self._return_existing(existing, request_fingerprint)

    def record(
        self,
        command: RecordDecisionCommand,
        actor: IdentitySnapshot,
    ) -> Decision:
        request_fingerprint = _request_fingerprint(command, actor)
        try:
            with self._uow_factory() as uow:
                existing = uow.decisions.get_by_idempotency_key(command.idempotency_key)
                if existing is not None:
                    return self._return_existing(existing, request_fingerprint)

                projection = uow.cases.get_projection(command.case_id)
                case = projection.case
                analysis = uow.cases.get_analysis(command.analysis_id)
                satisfactions = self._policy.authorize_and_materialize(
                    command,
                    actor,
                    case,
                    projection,
                    analysis,
                )
                decision = Decision.from_command(
                    command,
                    actor,
                    analysis,
                    satisfactions,
                    request_fingerprint=request_fingerprint,
                    decided_at=self._clock(),
                )
                uow.decisions.insert(decision)
                uow.decisions.insert_satisfactions(
                    decision.decision_id,
                    satisfactions,
                )
                if decision.kind is DecisionKind.APPROVED:
                    uow.execution.insert_outbox(
                        ActionPlanningRequested.for_decision(decision)
                    )
                    uow.cases.set_current_decision(
                        decision.case_id,
                        decision.decision_id,
                    )
                else:
                    uow.cases.mark_rejected(
                        decision.case_id,
                        decision.decision_id,
                    )
                uow.commit()
                return decision
        except IntegrityError as error:
            existing = self._load_idempotent_result(
                command.idempotency_key,
                request_fingerprint,
            )
            if existing is not None:
                return existing
            raise ImmutableRecordConflict(
                "Decision transaction violated immutable persistence constraints"
            ) from error
