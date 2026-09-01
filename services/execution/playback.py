from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from data.domain.decisions import DecisionKind, IdentitySnapshot
from data.domain.evidence import IdentitySource
from data.domain.execution import (
    DraftArtifact,
    ExecutionAction,
    ExecutionActionKind,
    ExecutionStatus,
    ObservationKind,
    OutcomeObservation,
    Playback,
    PlaybackStatus,
    PlaybackStep,
)
from services.execution.worker import ExecutionService
from services.persistence.ports import UnitOfWork

UnitOfWorkFactory = Callable[[], UnitOfWork]


PRODUCTION_STEPS = (
    PlaybackStep(offset_seconds=0, action_kind="prepare_alpha_recovery_draft"),
    PlaybackStep(
        offset_seconds=10,
        action_kind="coordinate_alpha_expedited_partial",
    ),
    PlaybackStep(offset_seconds=20, action_kind="transfer_dallas_to_chicago"),
    PlaybackStep(offset_seconds=35, action_kind="resequence_priority_production"),
    PlaybackStep(offset_seconds=50, action_kind="update_disruption_status"),
)


_OUTCOMES = (
    ("alpha_expedited_quantity", "3000", "2800", "units"),
    ("dallas_transfer_quantity", "1500", "1500", "units"),
    ("total_response_arranged_supply", "4500", "4300", "units"),
    ("uncovered_part_demand", "2300", "2500", "units"),
    ("response_cost", "24750", "25000", "USD"),
    ("protected_customer_orders", "1", "1", "orders"),
    ("revenue_protected", "580000", "580000", "USD"),
    ("margin_protected", "203000", "203000", "USD"),
    ("otif_loss_percentage", "50", "50", "percent"),
    ("remaining_alpha_recovery_date", "unknown", "2026-09-12", "date"),
)


_DRAFT_SUBJECT = "RL-001 recovery-date confirmation request"
_DRAFT_BODY = (
    "To RL-Supplier Alpha,\n\n"
    "Please confirm the remaining recovery date for disruption RL-001. "
    "This simulated draft has not been sent.\n"
)


class PlaybackAuthorizationError(RuntimeError):
    """Raised when playback is not explicitly started by authorized Alex."""


class PlaybackStateError(RuntimeError):
    """Raised when playback cannot safely advance its bounded actions."""


class PlaybackInterrupted(RuntimeError):
    """Raised when application shutdown interrupts runtime playback."""


class PlaybackClock(Protocol):
    def now(self) -> datetime: ...

    def wait_until(self, target: datetime) -> None: ...


class RealClock:
    def __init__(self) -> None:
        self._stopped = Event()

    def now(self) -> datetime:
        return datetime.now(UTC)

    def wait_until(self, target: datetime) -> None:
        delay = (target - self.now()).total_seconds()
        if delay > 0 and self._stopped.wait(delay):
            raise PlaybackInterrupted("playback interrupted by application shutdown")

    def reset(self) -> None:
        self._stopped.clear()

    def stop(self) -> None:
        self._stopped.set()


class ImmediateClock:
    def __init__(self, current: datetime | None = None) -> None:
        self._current = current or datetime.now(UTC)

    def now(self) -> datetime:
        return self._current

    def wait_until(self, target: datetime) -> None:
        self._current = max(self._current, target)


def _deterministic_id(prefix: str, decision_id: str, material: str) -> str:
    value = uuid5(NAMESPACE_URL, f"{decision_id}:{material}")
    return f"{prefix}-{value}"


class PlaybackService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        *,
        clock: PlaybackClock | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock or RealClock()

    @staticmethod
    def _authorize(actor: IdentitySnapshot) -> None:
        if (
            actor.persona_id != "RL-PERSONA-ALEX"
            or actor.identity_source is not IdentitySource.ENTRA
            or actor.source_id != "RL-ENTRA-ALEX"
            or not {"material_planner", "response_approver"}.issubset(
                actor.effective_roles
            )
        ):
            raise PlaybackAuthorizationError(
                "Playback requires the server-owned authorized Alex identity"
            )

    def start(self, decision_id: str, actor: IdentitySnapshot) -> Playback:
        self._authorize(actor)
        with self._uow_factory() as uow:
            decision = uow.decisions.get(decision_id)
            if decision.kind is not DecisionKind.APPROVED:
                raise PlaybackStateError("Playback requires an approved Decision")
            if decision.actor != actor:
                raise PlaybackAuthorizationError(
                    "Playback actor must match the approved Decision actor"
                )
            existing = uow.execution.get_playback_for_decision(decision_id)
            if existing is not None:
                return existing
            actions = uow.execution.list_actions(decision_id=decision_id)
            if tuple(action.kind.value for action in actions) != tuple(
                step.action_kind for step in PRODUCTION_STEPS
            ):
                raise PlaybackStateError(
                    "Playback requires the five planned Decision actions"
                )
            playback = Playback(
                playback_id=_deterministic_id(
                    "RL-PLAYBACK", decision_id, "simulated-playback"
                ),
                case_id=decision.case_id,
                decision_id=decision.decision_id,
                actor=actor,
                started_at=self._clock.now(),
            )
            uow.execution.insert_playback_if_absent(playback)
            uow.commit()
        with self._uow_factory() as uow:
            canonical = uow.execution.get_playback_for_decision(decision_id)
            if canonical is None or canonical.playback_id != playback.playback_id:
                raise PlaybackStateError(
                    "Playback insert did not retain its canonical Decision linkage"
                )
            return canonical

    def run_to_completion(
        self,
        playback_id: str,
        *,
        clock: PlaybackClock | None = None,
    ) -> Playback:
        active_clock = clock or self._clock
        with self._uow_factory() as uow:
            playback = uow.execution.get_playback(playback_id)
            if playback.status is PlaybackStatus.COMPLETED:
                return playback
            if playback.status is PlaybackStatus.FAILED:
                return playback
            actions = uow.execution.list_actions(decision_id=playback.decision_id)
        by_kind = {action.kind: action for action in actions}

        for step in PRODUCTION_STEPS:
            active_clock.wait_until(
                playback.started_at + timedelta(seconds=step.offset_seconds)
            )
            self._complete_action(
                by_kind[ExecutionActionKind(step.action_kind)],
                active_clock,
            )

        return self._record_completion(playback, actions, active_clock)

    def record_failure(self, playback_id: str) -> Playback:
        """Durably end a playback after its bounded runtime retries are exhausted."""
        with self._uow_factory() as uow:
            current = uow.execution.get_playback(playback_id)
            if current.status is not PlaybackStatus.IN_PROGRESS:
                return current
            failed = current.model_copy(
                update={
                    "status": PlaybackStatus.FAILED,
                    "failed_at": self._clock.now(),
                    "error_code": "PLAYBACK_EXECUTION_FAILED",
                }
            )
            uow.execution.update_playback(failed)
            uow.commit()
            return failed

    def _complete_action(
        self,
        expected: ExecutionAction,
        clock: PlaybackClock,
    ) -> None:
        execution = ExecutionService(self._uow_factory, clock=clock.now)
        with self._uow_factory() as uow:
            action = uow.execution.get_action(expected.action_id)
            attempts = uow.execution.list_attempts(action.action_id)
        if action.status is ExecutionStatus.COMPLETED:
            return
        if action.status is ExecutionStatus.PLANNED:
            attempt = execution.start(action.action_id)
        elif action.status is ExecutionStatus.IN_PROGRESS and attempts:
            attempt = attempts[-1]
        else:
            raise PlaybackStateError(
                f"Playback action cannot advance from {action.status.value}"
            )

        if action.kind is ExecutionActionKind.PREPARE_ALPHA_RECOVERY_DRAFT:
            self._fill_draft(action)
        execution.complete(action.action_id, attempt.attempt_id)

    def _fill_draft(self, action: ExecutionAction) -> None:
        with self._uow_factory() as uow:
            shell = uow.execution.get_draft_artifact(action.action_id)
            filled = shell.model_copy(
                update={"subject": _DRAFT_SUBJECT, "body": _DRAFT_BODY}
            )
            uow.execution.fill_draft_artifact(filled)
            uow.commit()

    def _record_completion(
        self,
        playback: Playback,
        actions: tuple[ExecutionAction, ...],
        clock: PlaybackClock,
    ) -> Playback:
        recorded_at = clock.now()
        action_ids = {action.kind: action.action_id for action in actions}
        alpha_metrics = {
            "alpha_expedited_quantity",
            "remaining_alpha_recovery_date",
        }
        with self._uow_factory() as uow:
            current = uow.execution.get_playback(playback.playback_id)
            if current.status is PlaybackStatus.COMPLETED:
                return current
            decision = uow.decisions.get(playback.decision_id)
            case = uow.cases.get_case(playback.case_id)
            for metric, predicted, observed, unit in _OUTCOMES:
                if metric in alpha_metrics:
                    action_kind = ExecutionActionKind.COORDINATE_ALPHA_EXPEDITED_PARTIAL
                elif metric == "dallas_transfer_quantity":
                    action_kind = ExecutionActionKind.TRANSFER_DALLAS_TO_CHICAGO
                else:
                    action_kind = ExecutionActionKind.UPDATE_DISRUPTION_STATUS
                observation = OutcomeObservation(
                    observation_id=_deterministic_id(
                        "RL-OBSERVATION", decision.decision_id, metric
                    ),
                    case_id=decision.case_id,
                    decision_id=decision.decision_id,
                    playback_id=current.playback_id,
                    action_id=action_ids[action_kind],
                    metric=metric,
                    observed_value=observed,
                    unit=unit,
                    predicted_value=predicted,
                    scenario_effective_time=decision.scenario_effective_time,
                    scenario_timezone=case.scenario_timezone,
                    recorded_at=recorded_at,
                    source_reference=f"RL-001 simulated playback:{metric}",
                    kind=ObservationKind.SIMULATED,
                    synthetic=True,
                )
                uow.execution.insert_observation(observation)
            completed = current.model_copy(
                update={
                    "status": PlaybackStatus.COMPLETED,
                    "completed_at": recorded_at,
                }
            )
            uow.execution.update_playback(completed)
            uow.commit()
            return completed

    def observations(self, decision_id: str) -> tuple[OutcomeObservation, ...]:
        with self._uow_factory() as uow:
            return uow.execution.list_observations(decision_id)

    def draft(self, decision_id: str, artifact_kind: str) -> DraftArtifact:
        with self._uow_factory() as uow:
            actions = uow.execution.list_actions(decision_id=decision_id)
            for action in actions:
                if action.draft_artifact_id is None:
                    continue
                artifact = uow.execution.get_draft_artifact(action.action_id)
                if artifact.artifact_kind == artifact_kind:
                    return artifact
        raise PlaybackStateError(
            f"Draft Artifact does not exist for Decision: {decision_id}"
        )
