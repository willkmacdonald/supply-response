from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import Literal

from data.domain.analysis import AnalysisVersion
from data.domain.decisions import Decision
from data.domain.execution import ExecutionAction
from services.execution.worker import ExecutionService

AutomatedFault = Literal["planning_failure", "first_action_failure"]
Planner = Callable[[Decision, AnalysisVersion], tuple[ExecutionAction, ...]]


class AutomatedTestFaults:
    """One-shot, case-scoped faults available only in automated-test composition."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self._armed: dict[str, AutomatedFault] = {}
        self._lock = Lock()

    def arm(self, case_id: str, fault: AutomatedFault) -> None:
        with self._lock:
            self._armed[case_id] = fault

    def wrap(self, planner: Planner) -> Planner:
        def fault_aware_planner(
            decision: Decision,
            analysis: AnalysisVersion,
        ) -> tuple[ExecutionAction, ...]:
            with self._lock:
                fault = self._armed.get(decision.case_id)
                if fault == "planning_failure":
                    self._armed.pop(decision.case_id)
            if fault == "planning_failure":
                raise RuntimeError("automated test planning failure")
            return planner(decision, analysis)

        return fault_aware_planner

    def after_plan(
        self,
        decision: Decision,
        analysis: AnalysisVersion,
        actions: tuple[ExecutionAction, ...],
        execution: ExecutionService,
    ) -> None:
        del analysis
        with self._lock:
            fault = self._armed.get(decision.case_id)
            if fault == "first_action_failure":
                self._armed.pop(decision.case_id)
        if fault != "first_action_failure":
            return
        attempt = execution.start(actions[0].action_id)
        execution.fail(
            actions[0].action_id,
            attempt.attempt_id,
            "AUTOMATED_TEST_ACTION_FAILURE",
        )
