# Alex → Taylor → Alex browser milestone

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan with controller review.

**Goal:** Deliver the authenticated submission, independent Finance decision, and final Alex decision in the deployed application, with browser evidence.

**Architecture:** Connect the accepted FinanceService and FinanceDecisionService to explicit authenticated HTTP operations. Route verified sessions to either the existing planner workspace or a Finance inbox/detail screen. New independent cases are server-selected behind a default-off deployment setting; old cases retain their original workflow.

**Tech Stack:** Existing FastAPI/Pydantic, SQLAlchemy, React/TypeScript, MSAL, Vitest and pytest.

## Global constraints

- Reuse Taylor's existing Finance Approver identity and Alex's existing planner / response-approver identity.
- Server-side tenant/object/role binding determines authority; a query parameter, display name or local persona selector does not.
- Costs strictly greater than $20,000 require an explicit Taylor review.
- Alex's final approval remains a separate action after all prerequisites are satisfied.
- Existing historical Decisions and standing-authorization evidence remain readable and immutable under their original workflow version.
- No real mail, new consent, replacement identity, schema deletion, or Power BI changes in this milestone.
- USD whole-dollar totals; preserve source icons, bottom provenance, and five-tab planner layout.
- Local signed-token tests are not proof of actual Microsoft sign-in. Real browser/session checks and release validation remain required.
- All pytest runs exclude `fabric_live` unless the controller explicitly authorizes a separate native database verification against a resolved safe target.

## Task 1: Authenticated approval HTTP journey

**Files:** `apps/api/app/auth.py`, `settings.py`, `dependencies.py`, `contracts.py`, `main.py`, `routes/cases.py`, `routes/decisions.py`, `routes/execution.py`; create `routes/finance.py`, `finance_contracts.py`, `routes/session.py` and focused `tests/api/test_finance_journey.py`, `tests/auth/test_planner_route_boundary.py`. Existing auth/API tests may be amended only to supply the newly required real authenticated binding.

**Consumes:** Existing `FinanceService.status/submit/list_pending/detail/resolve`, `FinanceDecisionService.finalize`, `BoundFinanceActors`, `ProposalState`, `SubmissionResult`, `ResolutionResult`, `FinanceReviewDetail`; their accepted domain validation, currentness and immutable replay contracts remain unchanged.

**Produces:**

```text
GET /api/me -> {mode: "entra"|"fallback", persona_id: string|null,
  display_name: string|null, independent_finance_enabled: boolean}
GET /api/cases/{case_id}/proposal -> ProposalState (Alex)
POST /api/cases/{case_id}/proposals -> SubmissionResult (Alex)
  body {option_id, expected}; Idempotency-Key header
GET /api/finance/reviews -> FinanceReviewDetail[] (Taylor)
GET /api/finance/reviews/{review_id} -> FinanceReviewDetail (Taylor)
POST /api/finance/reviews/{review_id}/resolutions -> ResolutionResult (Taylor)
  body {expected, expected_review_revision, approved, reason?}; Idempotency-Key
POST /api/cases/{case_id}/proposal-decisions -> DecisionResponse (Alex)
  body {expected, kind, rejection_reason?}; Idempotency-Key
```

- [ ] Write failing signed-token tests for Alex submit → Taylor reject → Alex resubmit → Taylor approve → Alex final approval, using local live-mode SQLite and stubbed providers/JWKS only. Include low-cost no-Finance, stale token, replay of original receipt, exact identities, and no mutation on GET.
- [ ] Write the full existing planner-route denial matrix from `.superpowers/sdd/finance-auth-api-next-task-map.md` (including dashboard and enabled test-support), with tripwire data/provider methods. Run RED before production changes.
- [ ] Implement Taylor factory and optional `taylor_object_id` setting using `SUPPLY_RESPONSE_TAYLOR_OBJECT_ID`. Add shared exact-Alex authorization before every existing planner route. Preserve Alex-only legacy composition and fallback preview; `/health`, `/api/runtime`, static assets and verified `/api/me` are deliberate bootstrap exceptions.
- [ ] Add `independent_finance_enabled: bool = False`. Enabling requires LIVE mode, valid distinct tenant/Alex/Taylor IDs and matching authenticated composition. Valid configured historical Finance queries remain available if later disabled; independent commands fail `409 FINANCE_WORKFLOW_DISABLED`. Never fall back to standing authorization.
- [ ] Compose accepted Finance services with the existing UoW/clock/identity configuration; no new persistence wrapper. Strict body wrappers forbid extra fields and construct the accepted command from path/header/body once. Domain command validation errors become bounded 422 only during construction, not via a broad catch around service execution.
- [ ] Implement exact routes above. Use response models for the accepted safe domain results. Add `workflow_version` to CaseResponse (effective saved version, never current flag), `proposal_approval_evidence` to DecisionResponse. Preserve old persisted JSON.
- [ ] Map named permission errors to 403, missing records to 404, currentness/revision/command conflicts to 409 with bounded codes (`STALE_PROPOSAL`, `FINANCE_COMMAND_CONFLICT`, `FINANCE_FINALIZATION_CONFLICT`, `EXECUTION_PROPOSAL_STALE`); invalid policy to 409 `FINANCE_REQUEST_INVALID`. Do not expose arbitrary exception text or disguise corruption/infrastructure failures. Explicit worker retry False returns 409 `ACTION_PLANNING_RETRY_NOT_AVAILABLE`.
- [ ] For new cases only, reconstruct the just-retrieved, not-yet-persisted Case using `CaseInstance.model_validate({...case.model_dump(), "workflow_version": WorkflowVersion.INDEPENDENT_FINANCE})` when enabled. Do not use model_copy to migrate saved cases; existing identifiers/policy remain unchanged. Keep Case creation server-controlled, not client-selectable.
- [ ] Run focused tests while iterating, then one scoped auth/API/Finance regression excluding live tests, Ruff/Pyright and commit only Task 1 files. Report exact RED/GREEN and remaining concerns to `.superpowers/sdd/approval-http-task-report.md`.

## Task 2: Visible browser journey

**Files:** `apps/web/src/App.tsx`, `api.ts`, `types.ts`, `auth/AuthProvider.tsx`, `components/InvestigationFlow.tsx`, new `finance/` components/hooks/tests, minimal `styles.css` additions; existing auth/App tests.

**Consumes:** Task 1 exact HTTP contracts. Interface names are fixed above; Python domain files supply nested field types.

- [ ] Add typed HTTP methods and signed-session lookup. Before mounting any planner data hook in Entra mode, obtain `/api/me`; Taylor mounts only Finance inbox/detail, Alex mounts planner. Account changes remount scoped state; late results cannot populate the next identity's screen. Sign-in uses real MSAL account selection and preserves the exact review deep link.
- [ ] Finance screen lists pending requests and a `?financeReviewId=` exact detail. Show selected response, USD cost, impacts, evidence, submission/review times and review status. Reject requires reason. Resolved/superseded historical requests remain readable and not actionable. Bounded refreshing shows cross-session updates; error is not an empty inbox.
- [ ] For saved independent cases, replace the legacy DecisionPanel with an independent approval panel. Show selected response and cost, submit/replace/resubmit, waiting state, exact Taylor link, rejection reason, approval outcome, then distinct final Alex approval. Low-cost text is “Finance review not required—within the spending threshold”. Do not treat old standing Finance satisfaction as approval.
- [ ] Command timeout retries retain exact body/token/key. A changed intent gets a new key. After command receipt, separately fetch current state; do not render an old replay receipt as current. Clear actionability on errors/stale data and explain refresh/reselect steps. Disable double clicks immediately.
- [ ] Verify role isolation, rejection/resubmission/approval, threshold status, stale/disabled/errors, keyboard navigation and original-key retries with component/API tests. Build and inspect wide/narrow layouts. No fake persona picker or browser fixture presented as live proof.

## Task 3: Integrated release and two-session proof

- [ ] Review Tasks 1–2 as one business journey, run integrated tests once, inspect the actual browser app.
- [ ] Resolve deployment prerequisites: existing Taylor setting/role assignment read-only, Finance schema availability, new-case policy, and automatic action-planning compatibility. Do not activate an option whose final approval would misrepresent execution. Execution/email remain a separately labelled later milestone; do not claim they are delivered.
- [ ] Use azure-validate then azure-deploy for the existing prepared app. Preserve previous deployable revision and exact bindings. Record the tested/deployed source revision and fresh health checks.
- [ ] Sign in separately as Alex and Taylor; show rejection with reason, resubmission, approval, Alex result and separate final decision. If an interactive sign-in is required from Will, report the exact single step rather than claiming completion.
- [ ] Update README.md, docs/ROADMAP.md and milestone evidence with actual local/deployed status and browser proof. CONTEXT.md changes only if domain meaning changed.

## Delivery acceptance

This plan is complete only when the deployed Alex/Taylor approval journey has been observed, or a concrete external blocker is reported. Backend test totals and a static preview are supporting evidence, not the deliverable.
