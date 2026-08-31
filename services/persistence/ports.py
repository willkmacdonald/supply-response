from types import TracebackType
from typing import Protocol, runtime_checkable

from data.domain import CaseInstance, CasePurpose
from data.domain.analysis import AnalysisVersion
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

    def save_case_projection(self, case: CaseInstance) -> None: ...

    def list_cases(
        self,
        *,
        purpose: CasePurpose | None = None,
    ) -> tuple[CaseInstance, ...]: ...


class DecisionStore(Protocol):
    """Focused Decision operations are introduced with Task 6."""


class ExecutionStore(Protocol):
    """Focused execution operations are introduced after Task 6."""


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
