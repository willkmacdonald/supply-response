from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from data.domain.common import ResponseOptionKind
from data.domain.decisions import Decision, DecisionKind, IdentitySnapshot
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
from services.execution.currentness import guard_execution_current
from services.execution.planner import action_kinds_for
from services.execution.worker import ExecutionService
from services.persistence.ports import UnitOfWork

UnitOfWorkFactory = Callable[[], UnitOfWork]


_DRAFT_SUBJECT = "RL-001 supplier communication draft"


def playback_steps(
    actions: tuple[ExecutionAction, ...],
) -> tuple[PlaybackStep, ...]:
    return tuple(
        PlaybackStep(offset_seconds=index * 2, action_kind=action.kind.value)
        for index, action in enumerate(actions)
    )


def predicted_observations(
    decision: Decision,
) -> tuple[tuple[str, str, str], ...]:
    assert decision.selected_option is not None
    predicted = decision.selected_option.predicted
    assert predicted is not None
    return (
        ("uncovered_part_demand", str(predicted.uncovered_part_demand), "units"),
        ("response_cost", str(predicted.response_cost), "USD"),
        ("revenue_at_risk", str(predicted.revenue_at_risk), "USD"),
        ("margin_at_risk", str(predicted.margin_at_risk), "USD"),
        ("otif_loss_percentage", str(predicted.otif_loss_percentage), "percent"),
    )


def _draft_body(decision: Decision) -> str:
    option = decision.selected_option
    assert option is not None
    response = (
        "The approved Dallas transfer response uses internal coordination. "
        "No supplier order was placed."
        if option.option_kind is ResponseOptionKind.TRANSFER
        else (
            f"The approved response is: {option.name}. This simulation did not order "
            "or send a supplier shipment."
        )
    )
    return (
        "FICTIONAL DEMO — supplier communication draft for Alex's review.\n"
        f"Case reference: {decision.case_id}\n"
        f"Selected response: {option.name}\n\n"
        f"{response}\n"
        "Please confirm the remaining recovery timing for disruption RL-001.\n\n"
        "Not sent.\n"
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
            if decision.selected_option is None:
                raise PlaybackStateError("Playback requires a selected Decision option")
            expected_kinds = action_kinds_for(decision.selected_option.option_kind)
            if tuple(action.kind for action in actions) != expected_kinds:
                raise PlaybackStateError(
                    "Playback requires the exact planned Decision actions"
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
            inserted = uow.execution.insert_playback_if_absent(playback)
            if inserted:
                guard_execution_current(uow, decision.decision_id)
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

        for step in playback_steps(actions):
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
            decision = uow.decisions.get(shell.decision_id)
            filled = shell.model_copy(
                update={"subject": _DRAFT_SUBJECT, "body": _draft_body(decision)}
            )
            if shell.subject is not None:
                uow.execution.fill_draft_artifact(filled)
                return
            guard_execution_current(uow, shell.decision_id)
            uow.execution.fill_draft_artifact(filled)
            uow.commit()

    def _record_completion(
        self,
        playback: Playback,
        actions: tuple[ExecutionAction, ...],
        clock: PlaybackClock,
    ) -> Playback:
        with self._uow_factory() as uow:
            current = uow.execution.get_playback(playback.playback_id)
            normalized = playback.model_copy(
                update={
                    "status": current.status,
                    "completed_at": current.completed_at,
                    "failed_at": current.failed_at,
                    "error_code": current.error_code,
                }
            )
            if normalized != current:
                raise PlaybackStateError(
                    "Playback identity differs from canonical record"
                )
            if current.status is not PlaybackStatus.IN_PROGRESS:
                return current
            canonical_actions = uow.execution.list_actions(
                decision_id=current.decision_id
            )
            decision = uow.decisions.get(current.decision_id)
            if decision.selected_option is None:
                raise PlaybackStateError("Playback requires a selected Decision option")
            expected_kinds = action_kinds_for(decision.selected_option.option_kind)
            if (
                tuple(action.kind for action in canonical_actions) != expected_kinds
                or len({action.action_id for action in canonical_actions})
                != len(expected_kinds)
                or any(
                    action.status is not ExecutionStatus.COMPLETED
                    for action in canonical_actions
                )
                or tuple(
                    action.model_copy(update={"status": ExecutionStatus.PLANNED})
                    for action in actions
                )
                != tuple(
                    action.model_copy(update={"status": ExecutionStatus.PLANNED})
                    for action in canonical_actions
                )
            ):
                raise PlaybackStateError(
                    "Playback requires the exact completed Decision action set"
                )
            decision = guard_execution_current(uow, current.decision_id)
            case = uow.cases.get_case(current.case_id)
            recorded_at = clock.now()
            action_ids = {action.kind: action.action_id for action in canonical_actions}
            for metric, predicted, unit in predicted_observations(decision):
                observation = OutcomeObservation(
                    observation_id=_deterministic_id(
                        "RL-OBSERVATION", decision.decision_id, metric
                    ),
                    case_id=decision.case_id,
                    decision_id=decision.decision_id,
                    playback_id=current.playback_id,
                    action_id=action_ids[ExecutionActionKind.UPDATE_DISRUPTION_STATUS],
                    metric=metric,
                    observed_value=predicted,
                    unit=unit,
                    predicted_value=predicted,
                    scenario_effective_time=decision.scenario_effective_time,
                    scenario_timezone=case.scenario_timezone,
                    recorded_at=recorded_at,
                    source_reference=f"Simulated: RL-001:{metric}",
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
