# Approval-only execution deferral report

## Implemented

- Added optional workflow eligibility to existing outbox claim operations and `ActionPlanningWorker`; its default remains unrestricted for accepted domain/service callers.
- Application composition now processes only legacy workflow outboxes. Independent Finance outboxes remain durable, pending, unclaimed, unattempted and error-free across ticks and restart.
- Eligibility selection scans the existing ordered SQL join to Case payloads, decodes the canonical `CaseInstance`, and uses its effective workflow version; legacy payloads without an explicit version remain eligible. No schema or persistence abstraction was added.
- Mixed queues skip deferred independent work and continue processing eligible legacy work.
- Independent action retry and playback commands return bounded conflicts, while Case controls suppress retry/playback affordances. Read-only historical execution routes remain readable.
- Normalized configured tenant/Alex UUIDs in the exact planner guard, preserving exact persona/source/role checks and allowing valid uppercase configured UUID text.
- Updated the approval browser milestone plan with the explicit approval-only boundary.

## TDD evidence

- RED: `.venv/bin/python -m pytest tests/finance/test_planning_worker_currentness.py -k legacy_only_worker -o addopts='' -q` — 3 failed because `ActionPlanningWorker` lacked `processable_workflow_versions`.
- GREEN: the same focused family plus the signed HTTP journey — 5 passed, including restart, mixed-queue, explicit retry, controls, playback conflict and uppercase UUID configuration.

## Verification

- `.venv/bin/python -m pytest tests/api tests/auth tests/execution tests/finance tests/persistence -m 'not fabric_live' -o addopts='' -q` — 496 passed, 11 skipped; one existing Starlette/httpx deprecation warning.
- Ruff on all changed implementation/test files — clean.
- Changed-file Pyright — 0 errors, 0 warnings.

## Files changed

`services/execution/worker.py`, `services/persistence/ports.py`, `services/persistence/store.py`, `apps/api/app/dependencies.py`, `apps/api/app/routes/cases.py`, `apps/api/app/routes/execution.py`, `tests/finance/test_planning_worker_currentness.py`, `tests/api/test_finance_journey.py`, and the approval browser milestone plan.

## Concerns

None within this bounded prerequisite. Independent execution remains deliberately unavailable until option-aware planning/playback is separately accepted.
