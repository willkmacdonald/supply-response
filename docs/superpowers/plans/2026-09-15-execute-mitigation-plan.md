# Execute Mitigation Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete tab 5 so Alex can see and simulate the approved option's exact mitigation actions, review an editable supplier email, explicitly send it to Will, and see truthful send status.

**Architecture:** Extend the existing Decision → outbox → execution-action → playback path instead of adding another workflow. Independent-finance Decisions will use an option-aware planner and dynamic simulated outcomes; a small outbound-mail aggregate will version the web-reviewed draft and track Microsoft Graph submission/reconciliation separately from simulation. The browser continues to call only FastAPI, and the API sends through Microsoft Graph with Alex's existing delegated identity.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy/Alembic, MSAL, httpx, React/TypeScript, Vitest, pytest, Microsoft Graph delegated mail APIs.

## Global Constraints

- The approved specifications are `docs/superpowers/specs/2026-09-12-email-to-mitigation-workflow-design.md` and `docs/superpowers/specs/2026-09-12-option-execution-and-reviewed-email-design.md`.
- Reuse the existing independent Taylor review and Alex final Decision. Only the current unchanged approved proposal may execute or send.
- Expedite, transfer, resequence, and combined responses produce only their applicable actions, using the approved snapshot quantities, dates, and costs. Baseline and blocked alternate-supplier options remain non-executable.
- Operational actions are visibly simulated. Simulation never calls Microsoft Graph and never marks email sent.
- The only real email path is Alex (`agent@willmacdonald.com`) to Supplier Alpha (demo)—Will (`will@willmacdonald.com`), configured at deployment; no CC, BCC, attachments, arbitrary recipient, purchase-order change, or financial commitment.
- Saving/editing, reviewing, and sending are separate actions. Editing after review invalidates that review. Sending requires the current Alex identity and a current approved Decision.
- `202 Accepted` means accepted by Microsoft Graph, not delivered. Show `Sent` only after exact-message reconciliation; Will opening the received email is the live acceptance check.
- A timeout after submission becomes `Send status uncertain`; checking status never automatically resends.
- Preserve all legacy action, draft, playback, and observation records without rewriting their JSON.
- Do not deploy, change tenant permissions, send email, or delete live data without separate approval for that exact live action.

---

### Task 1: Option-aware action planning for the independent workflow

**Files:**
- Modify: `data/domain/execution.py`
- Modify: `services/execution/planner.py`
- Modify: `services/execution/worker.py`
- Modify: `apps/api/app/dependencies.py`
- Modify: `apps/api/app/test_support.py`
- Modify: `apps/api/app/routes/cases.py`
- Modify: `apps/api/app/routes/execution.py`
- Test: `tests/execution/test_action_planning.py`
- Test: `tests/finance/test_planning_worker_currentness.py`
- Test: `tests/api/test_finance_journey.py`

**Interfaces:**
- Consumes: `Decision.selected_option`, `CaseStore.get_analysis(analysis_id)`, and `AnalysisVersion.material.operational_snapshot_json`.
- Produces: `plan_actions(decision: Decision, analysis: AnalysisVersion) -> tuple[ExecutionAction, ...]` and independent-finance Decisions whose `action_planning_status` can reach `complete`. Playback remains disabled for the independent workflow until Task 2 makes it option-aware.
- Extends `ExecutionAction` with backward-compatible display fields: `purpose: str | None = None`, `expected_result: str | None = None`, and `execution_mode: Literal["simulation", "communication_preparation"] | None = None`.

- [ ] **Step 1: Write failing planner tests for all supported options**

  Add parameterized tests that assert these exact action-kind sequences:

  ```python
  EXPECTED = {
      "RL-OPTION-EXPEDITE": (
          "prepare_alpha_recovery_draft",
          "coordinate_alpha_expedited_partial",
          "update_disruption_status",
      ),
      "RL-OPTION-TRANSFER": (
          "prepare_alpha_recovery_draft",
          "transfer_dallas_to_chicago",
          "update_disruption_status",
      ),
      "RL-OPTION-RESEQUENCE": (
          "prepare_alpha_recovery_draft",
          "resequence_priority_production",
          "update_disruption_status",
      ),
      "RL-OPTION-COMBINED": tuple(kind.value for kind in ExecutionActionKind),
  }
  ```

  Assert the expedite text includes `3,000`, `September 6, 2026`, and `$7.50 per unit`; transfer includes `1,500`, `Dallas`, `Chicago`, and `September 5, 2026`; resequence names the protected customer order(s); every plan has supplier communication and disruption-status actions. Assert baseline, alternate supplier, a rejected Decision, an absent option, and a Decision/Analysis mismatch raise `ValueError` without inserting actions.

- [ ] **Step 2: Verify the focused tests fail**

  Run: `.venv/bin/python -m pytest tests/execution/test_action_planning.py tests/finance/test_planning_worker_currentness.py -q -o addopts=''`

  Expected: FAIL because `plan_actions` accepts only a Decision and rejects every option except combined.

- [ ] **Step 3: Add option-specific action metadata and planning**

  Parse the immutable snapshot from the approved Analysis and build only the applicable kinds. Keep deterministic action/draft IDs unchanged:

  ```python
  def plan_actions(
      decision: Decision,
      analysis: AnalysisVersion,
  ) -> tuple[ExecutionAction, ...]:
      if decision.kind is not DecisionKind.APPROVED:
          raise ValueError("actions require an approved Decision")
      if (
          decision.analysis_id != analysis.analysis_id
          or decision.analysis_material_hash != analysis.material_hash
          or decision.selected_option is None
          or decision.selected_option_id != decision.selected_option.option_id
          or not decision.selected_option.executable
      ):
          raise ValueError("Decision does not identify a current executable option")
      snapshot = OperationalSnapshot.model_validate_json(
          analysis.material.operational_snapshot_json
      )
      kinds = action_kinds_for(decision.selected_option.option_kind)
      return tuple(
          build_action(decision, snapshot, kind)
          for kind in kinds
      )
  ```

  `action_kinds_for` must map exactly to `EXPECTED` above. `build_action` supplies human-readable purpose/result from the snapshot, assigns Alex to coordinated/preparation actions and the system to status update, and labels coordination as `simulation` while the draft action is `communication_preparation`.

- [ ] **Step 4: Let the worker plan independent Decisions and expose the existing controls**

  Change the worker `Planner` signature to accept `(Decision, AnalysisVersion)`, load `uow.cases.get_analysis(decision.analysis_id)` inside the claimed transaction, and call the new planner. Configure `ActionPlanningWorker` for both `WorkflowVersion.LEGACY` and `WorkflowVersion.INDEPENDENT_FINANCE`. Enable only action-planning status and retry for independent Decisions in this task; keep action retry and playback behind `INDEPENDENT_EXECUTION_DEFERRED` until Task 2 replaces their combined-only assumptions.

  Update the existing automated-test planner wrapper and `after_plan` seam to pass the same Decision/Analysis pair without changing fault behavior.

- [ ] **Step 5: Run focused backend tests**

  Run: `.venv/bin/python -m pytest tests/execution/test_action_planning.py tests/finance/test_planning_worker_currentness.py tests/api/test_finance_journey.py -q -o addopts=''`

  Expected: PASS, including a fresh independent case that reaches a complete, option-specific action list only after Alex's final approval.

- [ ] **Step 6: Commit the bounded planning increment**

  ```bash
  git add data/domain/execution.py services/execution/planner.py services/execution/worker.py apps/api/app/dependencies.py apps/api/app/test_support.py apps/api/app/routes/cases.py apps/api/app/routes/execution.py tests/execution/test_action_planning.py tests/finance/test_planning_worker_currentness.py tests/api/test_finance_journey.py
  git commit -m "feat: plan approved mitigation actions by option"
  ```

---

### Task 2: Dynamic simulation and a draft ready for Alex's review

**Files:**
- Modify: `services/execution/playback.py`
- Modify: `apps/api/app/routes/execution.py`
- Modify: `apps/web/src/components/InvestigationFlow.tsx`
- Modify: `apps/web/src/components/ExecutionPanel.tsx`
- Modify: `apps/web/src/components/OutcomePanel.tsx`
- Modify: `apps/web/src/hooks/useCaseWorkspace.ts`
- Modify: `apps/web/src/types.ts`
- Test: `tests/execution/test_playback.py`
- Test: `tests/finance/test_playback_currentness.py`
- Test: `apps/web/src/components/ExecutionPanel.test.tsx`
- Test: `apps/web/src/components/InvestigationFlow.test.tsx`

**Interfaces:**
- Consumes: Task 1's option-specific `ExecutionAction` list and the immutable approved `Decision.selected_option.predicted` values.
- Produces: dynamic `PlaybackService.run_to_completion(playback_id)` and a tab-5 presentation that separates simulated coordination from the unsent supplier communication.

- [ ] **Step 1: Write failing dynamic-playback tests**

  For each supported option, assert playback accepts exactly its planned action kinds, completes those actions, and records observations derived from the selected option's predicted outcome. Assert transfer playback never records an Alpha expedited quantity; expedite playback never records a Dallas transfer; resequence playback records neither. Assert `source_reference` and UI say `Simulated`, and the draft remains unsent.

- [ ] **Step 2: Verify the focused tests fail**

  Run: `.venv/bin/python -m pytest tests/execution/test_playback.py tests/finance/test_playback_currentness.py -q -o addopts=''`

  Expected: FAIL because playback requires the fixed five-action combined sequence and fixed combined observations.

- [ ] **Step 3: Replace fixed playback assumptions with the Decision's plan**

  Replace `PRODUCTION_STEPS` and `_OUTCOMES` as global combined-only truth with helpers:

  ```python
  def playback_steps(actions: tuple[ExecutionAction, ...]) -> tuple[PlaybackStep, ...]:
      return tuple(
          PlaybackStep(offset_seconds=index * 2, action_kind=action.kind.value)
          for index, action in enumerate(actions)
      )

  def predicted_observations(decision: Decision) -> tuple[tuple[str, str, str], ...]:
      predicted = decision.selected_option.predicted
      assert predicted is not None
      return (
          ("uncovered_part_demand", str(predicted.uncovered_part_demand), "units"),
          ("response_cost", str(predicted.response_cost), "USD"),
          ("revenue_at_risk", str(predicted.revenue_at_risk), "USD"),
          ("margin_at_risk", str(predicted.margin_at_risk), "USD"),
          ("otif_loss_percentage", str(predicted.otif_loss_percentage), "percent"),
      )
  ```

  Keep the legacy combined workflow's stored history readable. Create the supplier draft from the selected response with a visible fictional-demo statement and the case reference. A transfer-only email must describe the approved transfer/resequencing result without implying that a supplier shipment was ordered.

- [ ] **Step 4: Replace the independent-workflow placeholder on tab 5**

  Remove `INDEPENDENT_EXECUTION_DEFERRED` now that playback and action retry are option-aware. Render the existing `ExecutionPanel` for both workflow versions after final approval. Show, for each action: purpose, `Owner: Alex` or `Owner: System`, expected result, status, and `What happens here: Simulated coordination` or `Draft prepared for Alex to review`. Change the playback control to `Run simulated coordination` and keep the email card visibly `Not sent` after simulation.

- [ ] **Step 5: Add frontend tests for visible feedback and truthful status**

  Assert a user entering tab 5 after final approval sees the correct actions immediately, a visible progress state after clicking simulation, option-specific completed states afterward, and a separate email card that still says `Not sent`. Assert the old `Execution is not available` text is absent.

- [ ] **Step 6: Run focused frontend and backend tests**

  Run: `.venv/bin/python -m pytest tests/execution/test_playback.py tests/finance/test_playback_currentness.py -q -o addopts=''`

  Run: `npm --prefix apps/web test -- --run src/components/ExecutionPanel.test.tsx src/components/InvestigationFlow.test.tsx`

  Expected: PASS.

- [ ] **Step 7: Commit the visible simulation increment**

  ```bash
  git add services/execution/playback.py apps/api/app/routes/execution.py apps/web/src/components/InvestigationFlow.tsx apps/web/src/components/ExecutionPanel.tsx apps/web/src/components/OutcomePanel.tsx apps/web/src/hooks/useCaseWorkspace.ts apps/web/src/types.ts tests/execution/test_playback.py tests/finance/test_playback_currentness.py apps/web/src/components/ExecutionPanel.test.tsx apps/web/src/components/InvestigationFlow.test.tsx
  git commit -m "feat: show and simulate the approved mitigation plan"
  ```

---

### Task 3: Versioned reviewed supplier email

**Files:**
- Create: `data/domain/outbound_mail.py`
- Create: `services/execution/mail_service.py`
- Create: `migrations/versions/0009_outbound_supplier_email.py`
- Modify: `services/persistence/tables.py`
- Modify: `services/persistence/ports.py`
- Modify: `services/persistence/store.py`
- Modify: `services/persistence/presenter_runs.py`
- Modify: `apps/api/app/contracts.py`
- Modify: `apps/api/app/routes/execution.py`
- Modify: `apps/api/app/dependencies.py`
- Test: `tests/execution/test_reviewed_email.py`
- Test: `tests/persistence/test_sqlite_store.py`
- Test: `tests/api/test_reviewed_email.py`

**Interfaces:**
- Consumes: the current approved Decision, its draft-owning `ExecutionAction`, and the current authenticated Alex actor.
- Produces: `ReviewedEmailService.get(decision_id)`, `.save(decision_id, subject, body, actor)`, and `.review(decision_id, revision, actor)` plus GET/PUT/POST review endpoints under `/api/decisions/{decision_id}/supplier-email`.
- Produces API state with `revision`, `subject`, `body`, fixed `from_address`, fixed `to_address`, `reviewed_revision`, `reviewed_at`, `reviewed_by`, and `send_status`.

- [ ] **Step 1: Write failing domain, persistence, and API tests**

  Assert initial draft revision 1 is generated from the approved option; editing inserts revision 2 and clears effective review; review records Alex and exact revision; editing to revision 3 disables send until revision 3 is reviewed. Assert Taylor, a different recipient, CC/BCC/attachments, blank/oversized subject/body, stale Decision, and mismatched action are rejected. Assert an upgrade from migration `0008_case_proposal_selection` preserves existing rows and adds the new tables.

- [ ] **Step 2: Verify the tests fail**

  Run: `.venv/bin/python -m pytest tests/execution/test_reviewed_email.py tests/api/test_reviewed_email.py tests/persistence/test_sqlite_store.py -q -o addopts=''`

  Expected: FAIL because reviewed outbound email records and routes do not exist.

- [ ] **Step 3: Add the smallest durable mail aggregate**

  Add one immutable revision table and one current delivery table:

  ```python
  class SupplierEmailRevision(FrozenModel):
      email_id: str
      decision_id: str
      action_id: str
      revision: int
      subject: str
      body: str
      from_address: str
      to_address: str
      edited_by: IdentitySnapshot
      edited_at: datetime
      reviewed_by: IdentitySnapshot | None = None
      reviewed_at: datetime | None = None

  class SupplierEmailDelivery(FrozenModel):
      email_id: str
      decision_id: str
      reviewed_revision: int | None = None
      send_status: Literal["draft", "submitting", "accepted", "sent-confirmed", "failed", "uncertain"] = "draft"
      provider_message_id: str | None = None
      internet_message_id: str | None = None
      correlation_id: str | None = None
      status_updated_at: datetime
      failure_code: str | None = None
  ```

  The Alembic migration creates `supplier_email_revisions` with unique `(email_id, revision)` and `supplier_email_deliveries` with one row per `email_id`. Add both to presenter-run pruning so deleting an old presenter run cannot leave orphaned mail state.

- [ ] **Step 4: Implement save/review services and routes**

  Use `guard_execution_current` before every write, require the configured Alex identity, derive sender/recipient only from settings, and return safe plain-language 409/422 responses. Endpoints:

  ```text
  GET  /api/decisions/{decision_id}/supplier-email
  PUT  /api/decisions/{decision_id}/supplier-email
       {"revision": 1, "subject": "...", "body": "..."}
  POST /api/decisions/{decision_id}/supplier-email/review
       {"revision": 2}
  ```

  Saving requires the caller's expected current revision, creates the next revision, and never accepts sender/recipient fields from the request. Reviewing requires the current revision and leaves `send_status="draft"`.

- [ ] **Step 5: Run focused tests**

  Run: `.venv/bin/python -m pytest tests/execution/test_reviewed_email.py tests/api/test_reviewed_email.py tests/persistence/test_sqlite_store.py -q -o addopts=''`

  Expected: PASS, including reload/restart persistence and presenter-run pruning.

- [ ] **Step 6: Commit the reviewed-draft increment**

  ```bash
  git add data/domain/outbound_mail.py services/execution/mail_service.py migrations/versions/0009_outbound_supplier_email.py services/persistence/tables.py services/persistence/ports.py services/persistence/store.py services/persistence/presenter_runs.py apps/api/app/contracts.py apps/api/app/routes/execution.py apps/api/app/dependencies.py tests/execution/test_reviewed_email.py tests/persistence/test_sqlite_store.py tests/api/test_reviewed_email.py
  git commit -m "feat: version and review supplier email drafts"
  ```

---

### Task 4: Microsoft Graph submission and reconciliation

**Files:**
- Create: `integrations/graph_mail/__init__.py`
- Create: `integrations/graph_mail/client.py`
- Create: `integrations/graph_mail/obo.py`
- Modify: `services/execution/mail_service.py`
- Modify: `apps/api/app/settings.py`
- Modify: `apps/api/app/dependencies.py`
- Modify: `apps/api/app/contracts.py`
- Modify: `apps/api/app/routes/execution.py`
- Modify: `infra/entra/api-app.json`
- Modify: `infra/entra/configure.sh`
- Modify: `scripts/preflight_personal_tenant.sh`
- Modify: `infra/modules/container-apps.bicep`
- Modify: `infra/main.parameters.json`
- Test: `tests/integration/test_graph_mail.py`
- Test: `tests/api/test_reviewed_email.py`
- Test: `tests/deployment/test_infrastructure.py`

**Interfaces:**
- Consumes: Task 3's exact reviewed `SupplierEmailRevision`, `SupplierEmailDelivery`, and the validated opaque bearer assertion retained by `AuthService`.
- Produces: `GraphMailPort.capability(actor) -> GraphMailCapability`, `.create_draft(revision, actor) -> ProviderDraft`, `.send_draft(provider_message_id, actor) -> None`, `.get_message(provider_message_id, actor) -> ProviderMessage`; `ReviewedEmailService.send(...)`; and `ReviewedEmailService.check_send_status(...)`.

- [ ] **Step 1: Write failing adapter and send-state tests with mocked HTTP**

  Assert the adapter obtains a delegated Graph token for `https://graph.microsoft.com/.default`, uses `POST /v1.0/me/messages`, verifies the returned immutable message with `GET /v1.0/me/messages/{id}`, then uses `POST /v1.0/me/messages/{id}/send`. Every message request includes `Prefer: IdType="ImmutableId"`. Assert the verified sender, sole recipient, subject, and text body exactly match the reviewed revision before send.

  Cover: create failure → `failed`; mismatch before submit → `failed` with no send; 202 → `accepted`; exact immutable message later showing a sent time → `sent-confirmed`; timeout/connection loss after send begins → `uncertain`; check-status on uncertain never creates or sends another message; repeated/concurrent Send returns the same canonical state and causes at most one provider submission.

- [ ] **Step 2: Verify focused tests fail**

  Run: `.venv/bin/python -m pytest tests/integration/test_graph_mail.py tests/api/test_reviewed_email.py -q -o addopts=''`

  Expected: FAIL because the Graph adapter and send routes do not exist.

- [ ] **Step 3: Implement a bounded delegated Graph adapter**

  Reuse the existing `AuthService._validated_user_assertion(actor)` capability pattern. Exchange on behalf of Alex for the API application's consented Graph permissions, keep tokens opaque/non-serializable, use a bounded `httpx.AsyncClient`, reject redirects and oversized/non-JSON responses, and expose only allowlisted safe failure codes. Do not route sending through Work IQ.

  `capability` performs only read operations: verify `/me` is Alex's configured mailbox, read one Sent Items message with immutable IDs, and retrieve that exact ID again. It never creates, changes, deletes, or sends a message.

- [ ] **Step 4: Implement send claim and exact-message reconciliation**

  `POST /api/decisions/{decision_id}/supplier-email/send` accepts only `{"revision": N}`. In one transaction, verify current Decision/current revision/review and change `draft|failed` to `submitting` with a correlation ID. Persist the provider immutable ID before calling send. Treat HTTP 202 as `accepted`; only reconciliation can change it to `sent-confirmed`. A timeout or indeterminate response changes it to `uncertain`, and `POST .../check-send-status` performs GET-only reconciliation.

- [ ] **Step 5: Add settings and deployment configuration without applying it**

  Add required live settings for the fixed sender/recipient and a default-off `mail_send_enabled`. Add Microsoft Graph delegated `Mail.ReadWrite` and `Mail.Send` to `infra/entra/api-app.json` and make `configure.sh` resolve their published scope IDs by exact value. Update preflight to require the exact configured permissions only when mail sending is enabled. Do not run `configure.sh --apply`, grant consent, deploy, or send during this task.

- [ ] **Step 6: Run focused integration and infrastructure tests**

  Run: `.venv/bin/python -m pytest tests/integration/test_graph_mail.py tests/api/test_reviewed_email.py tests/deployment/test_infrastructure.py -q -o addopts=''`

  Expected: PASS with zero real network calls and zero real sends.

- [ ] **Step 7: Commit the Graph adapter increment**

  ```bash
  git add integrations/graph_mail data/domain/outbound_mail.py services/execution/mail_service.py apps/api/app/settings.py apps/api/app/dependencies.py apps/api/app/contracts.py apps/api/app/routes/execution.py infra/entra/api-app.json infra/entra/configure.sh scripts/preflight_personal_tenant.sh infra/modules/container-apps.bicep infra/main.parameters.json tests/integration/test_graph_mail.py tests/api/test_reviewed_email.py tests/deployment/test_infrastructure.py
  git commit -m "feat: send reviewed supplier email through Graph"
  ```

---

### Task 5: Finish the tab-5 presenter experience and local acceptance

**Files:**
- Create: `apps/web/src/components/SupplierEmailPanel.tsx`
- Create: `apps/web/src/components/SupplierEmailPanel.test.tsx`
- Modify: `apps/web/src/components/ExecutionPanel.tsx`
- Modify: `apps/web/src/hooks/useCaseWorkspace.ts`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/styles.css`
- Modify: `apps/web/e2e/app.spec.ts`
- Modify: `README.md`
- Modify: `docs/ROADMAP.md`

**Interfaces:**
- Consumes: Tasks 3–4 supplier-email GET/save/review/send/check-status endpoints.
- Produces: an editable, reload-safe supplier-email panel and a complete mocked/local walkthrough from final approval through simulated actions and reviewed send state.

- [ ] **Step 1: Write failing frontend interaction tests**

  Assert the panel shows `From: Alex — agent@willmacdonald.com`, `To: Supplier Alpha (demo) — will@willmacdonald.com`, editable subject/body, and `Not sent`. Editing shows `Save changes`; saved content shows `Review this email`; reviewed content enables `Send email`. Editing again disables Send and requires review again. Clicking Send immediately shows `Sending…`, prevents a second click, and maps server states to `Accepted by Microsoft 365`, `Sent`, `Send failed`, or `Send status uncertain` with `Check send status` only for uncertain. Never show `Delivered`.

- [ ] **Step 2: Verify the frontend tests fail**

  Run: `npm --prefix apps/web test -- --run src/components/SupplierEmailPanel.test.tsx src/components/ExecutionPanel.test.tsx`

  Expected: FAIL because the email panel and API methods do not exist.

- [ ] **Step 3: Implement the panel and workspace actions**

  Add typed API methods:

  ```typescript
  supplierEmail: (decisionId: string): Promise<SupplierEmailState>
  saveSupplierEmail: (decisionId: string, input: {revision: number; subject: string; body: string}): Promise<SupplierEmailState>
  reviewSupplierEmail: (decisionId: string, revision: number): Promise<SupplierEmailState>
  sendSupplierEmail: (decisionId: string, revision: number): Promise<SupplierEmailState>
  checkSupplierEmail: (decisionId: string): Promise<SupplierEmailState>
  ```

  Load the mail state whenever execution is loaded, preserve edits while moving among tabs, and show one plain-language status banner after every click. Keep simulation controls and actual mail status visually separate.

- [ ] **Step 4: Add the end-to-end local presenter test**

  Using mocked authenticated API responses, cover: fresh inbound case → analysis → response selection → Taylor approval → Alex final approval → option-specific tab 5 → run simulation → edit/save/review email → Send accepted → status check Sent. Repeat with a new presenter run and assert no approval, actions, playback, or mail state leaks from the first run.

- [ ] **Step 5: Update user-facing documentation to the implemented boundary**

  Update `README.md` and `docs/ROADMAP.md` with what is locally complete, what remains simulated, and the exact remaining live gates. Do not claim consent, deployment, provider acceptance, sent confirmation, or receipt until separately observed.

- [ ] **Step 6: Run proportional full verification**

  Run: `.venv/bin/python -m pytest -q -m 'not fabric_live and not power_bi_live and not workiq_live and not foundry_live' -o addopts=''`

  Run: `.venv/bin/python -m ruff check apps services data integrations tests migrations`

  Run: `npm --prefix apps/web test`

  Run: `npm --prefix apps/web run build`

  Expected: all commands PASS; Graph test doubles record no more than one send; no live Microsoft call occurs.

- [ ] **Step 7: Commit the completed local feature**

  ```bash
  git add apps/web/src/components/SupplierEmailPanel.tsx apps/web/src/components/SupplierEmailPanel.test.tsx apps/web/src/components/ExecutionPanel.tsx apps/web/src/hooks/useCaseWorkspace.ts apps/web/src/api.ts apps/web/src/types.ts apps/web/src/styles.css apps/web/e2e/app.spec.ts README.md docs/ROADMAP.md
  git commit -m "feat: complete execute mitigation plan experience"
  ```

---

### Task 6: Separately approved live gates

**Files:**
- Modify only after observed acceptance: `docs/deployment/personal-tenant.md`
- Modify only after observed acceptance: `.azure/deployment-plan.md`
- Modify only after observed acceptance: `docs/ROADMAP.md`

**Interfaces:**
- Consumes: the locally verified feature from Tasks 1–5.
- Produces: tenant permission proof, deployed browser proof, and one user-authorized real supplier email acceptance record.

- [ ] **Step 1: Stop and request exact approval for the tenant permission change**

  Explain that the supported approach is delegated Microsoft Graph `Mail.ReadWrite` + `Mail.Send` on the existing API app, limited in code to Alex → Will. State that consent changes the tenant and is not covered by implementation approval. Also request approval to run the read-only mailbox identity/reconciliation capability check after consent.

- [ ] **Step 2: If approved, apply and verify permissions without sending**

  Run the repository's existing Entra configuration workflow, have the user grant the displayed delegated consent, then run the configuration preflight and the approved read-only mailbox capability check. Expected: exact Graph delegated permissions present, `/me` is the configured Alex mailbox, and one existing immutable Sent Items ID can be re-read exactly; no application permission, mailbox write, or email send occurs.

- [ ] **Step 3: Stop and request exact deployment approval**

  State the commit/revision to deploy and that mail sending will remain disabled until browser verification is ready.

- [ ] **Step 4: If approved, deploy and verify the five-stage browser flow without sending**

  Use a fresh presenter run. Expected: tab 5 shows the chosen option's action list, simulated coordination works, the draft is editable/reviewable, reload preserves state, and a second run begins cleanly.

- [ ] **Step 5: Stop and request exact approval for one real email send**

  Show the exact From, To, subject, and full body to the user before asking. Approval authorizes one click for that reviewed revision only.

- [ ] **Step 6: If approved, send once and verify honestly**

  Expected sequence: `Sending…` → `Accepted by Microsoft 365` → `Sent` after exact-message reconciliation. Final acceptance requires Will to open the received message. If status is uncertain, use only `Check send status`; do not resend without a new exact approval.

- [ ] **Step 7: Record only observed results**

  Update deployment/roadmap documentation with the exact revision, tenant permission result, browser run, provider status, and Will's receipt confirmation. Record failures or uncertainty as such.

## Self-review

- Spec coverage: Tasks 1–2 cover option-specific actions and simulation; Tasks 3–5 cover editable reviewed email, revision invalidation, fixed identities, explicit send, durable status, concurrency/reload, truthful copy, and repeatable runs; Task 6 preserves the separately approved tenant/deploy/send gates and live receipt acceptance.
- Scope: no real ERP write, purchase-order change, supplier commitment, arbitrary recipient, unattended monitoring, direct Graph discovery, new identity, or new service is included.
- Backward compatibility: new optional action fields preserve old JSON; legacy playback/history remain readable; outbound-mail storage is additive; retention includes new rows.
- Type consistency: the same `SupplierEmailRevision`, `SupplierEmailDelivery`, `SupplierEmailState`, and route names are used from persistence through API and browser.
- Placeholder scan: no deferred implementation markers or unspecified error-handling steps remain.
