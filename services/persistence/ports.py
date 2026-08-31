from types import TracebackType
from typing import Protocol, runtime_checkable

from data.domain import CaseInstance, CasePurpose
from data.domain.analysis import AnalysisVersion
from data.domain.decisions import ApprovalSatisfaction, CaseProjection, Decision
from data.domain.execution import ActionPlanningRequested
from data.synthetic.rl001 import OperationalSnapshot


@runtime_checkable
class CaseStore(Protocol):
    def create_case(
        self,
        case: CaseInstance,
        snapshot: OperationalSnapshot,
    ) -> None: ...

    def get_case(self, case_id: str) -> CaseInstance: ...

    def save_analysis(self, analysis: AnalysisVersion) -> None: ...

    def get_analysis(self, analysis_id: str) -> AnalysisVersion: ...

    def get_projection(self, case_id: str) -> CaseProjection: ...

    def set_current_decision(self, case_id: str, decision_id: str) -> None: ...

    def mark_rejected(self, case_id: str, decision_id: str) -> None: ...

    def save_case_projection(self, case: CaseInstance) -> None: ...

    def list_cases(
        self,
        *,
        purpose: CasePurpose | None = None,
    ) -> tuple[CaseInstance, ...]: ...


class DecisionStore(Protocol):
    def get(self, decision_id: str) -> Decision: ...

    def get_by_idempotency_key(self, idempotency_key: str) -> Decision | None: ...

    def list_for_case(self, case_id: str) -> tuple[Decision, ...]: ...

    def insert(self, decision: Decision) -> None: ...

    def insert_satisfactions(
        self,
        decision_id: str,
        satisfactions: tuple[ApprovalSatisfaction, ...],
    ) -> None: ...

    def list_approval_satisfactions(
        self,
        decision_id: str,
    ) -> tuple[ApprovalSatisfaction, ...]: ...


class ExecutionStore(Protocol):
    def insert_outbox(self, event: ActionPlanningRequested) -> None: ...

    def list_outbox(
        self,
        *,
        decision_id: str,
    ) -> tuple[ActionPlanningRequested, ...]: ...


class UnitOfWork(Protocol):
    cases: CaseStore
    decisions: DecisionStore
    execution: ExecutionStore

    def __enter__(self) -> "UnitOfWork": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
