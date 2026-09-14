# Authenticated approval HTTP journey — Task 1 report

## Implemented

- Added exact Taylor Entra binding, optional Taylor setting, default-off independent Finance setting validation, exact Alex planner guard, Taylor Finance guard, and safe `/api/me` projection.
- Protected all planner routers (cases, legacy decisions, execution, dashboard, and enabled test support) before handler work; retained fallback preview and bootstrap routes.
- Composed the accepted `FinanceService` and `FinanceDecisionService` with the existing UoW, clock, and `BoundFinanceActors`.
- Added strict proposal, Finance review/detail/resolution, and final proposal-decision HTTP contracts with bounded named error mappings.
- Added effective saved `workflow_version` to case responses and immutable `proposal_approval_evidence` to decision responses.
- Server-selects the independent workflow only for newly retrieved live cases while enabled; saved cases are not migrated.
- Explicit action-planning retry now rejects a false/no-work worker result; execution proposal staleness has its dedicated bounded conflict.

## TDD evidence

- RED: `.venv/bin/python -m pytest tests/api/test_finance_journey.py tests/auth/test_planner_route_boundary.py -m 'not fabric_live' -o addopts='' -q` — 2 failed because `PersonaBinding.taylor` did not exist, the expected preproduction contract gap.
- GREEN: same focused command — 2 passed. The signed-token live-mode SQLite journey covers exact `/api/me`, the full planner route denial matrix, Alex denial from Finance, Taylor rejection, Alex resubmission, Taylor approval, and separate Alex final approval.

## Verification

- `.venv/bin/python -m pytest tests/api tests/auth tests/finance -m 'not fabric_live' -o addopts='' -q` — 353 passed, 11 skipped; one existing Starlette/httpx deprecation warning.
- `.venv/bin/python -m pytest tests/api/test_finance_journey.py tests/auth/test_planner_route_boundary.py tests/execution tests/finance -m 'not fabric_live' -o addopts='' -q` — 274 passed, 11 skipped.
- Ruff on all changed backend/test files — clean.
- `uv run pyright` scoped to changed backend files — 0 errors, 0 warnings. Repository-wide Pyright still has 65 unrelated baseline errors.

## Files changed

`apps/api/app/auth.py`, `settings.py`, `dependencies.py`, `contracts.py`, `main.py`, `finance_contracts.py`, `routes/cases.py`, `routes/decisions.py`, `routes/execution.py`, `routes/finance.py`, `routes/session.py`, `tests/api/test_finance_journey.py`, and `tests/auth/test_planner_route_boundary.py`.

## Self-review / concerns

- Request construction catches validation errors only around command construction; service execution catches only named domain errors, so persistence/infrastructure corruption remains an unbounded server failure.
- No tenant, consent, schema, mail, deployment, frontend, or worker-runtime changes were made. The controller separately identified that the current live schema lacks Finance tables; activation must remain off until that additive prerequisite is resolved.
