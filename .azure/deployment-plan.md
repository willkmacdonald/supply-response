# Supply Response Personal-Tenant Deployment Plan

## Hide completed case launcher — 2026-09-14

Scope: once an analysis is loaded, remove the **Saved demos** launcher and its
saved-results recovery note from the active workspace. Keep both available
before analysis so a presenter can reopen a saved case or retry an unfinished
case. This extends the completed email-step cleanup; the analysis, source links,
planning routes and five stage tabs remain unchanged. Same approved Azure
target; no data, identity, role, schema, configuration or infrastructure changes.

### All validation checks pass — completed case launcher

- [x] 1. AZD Installation: 1.30.0
- [x] 2. Schema Validation: unchanged validated azure.yaml
- [x] 3. Environment Setup: existing guarded profile
- [x] 4. Authentication Check: existing authenticated environment
- [x] 5. Subscription/Location Check: Azure Dev / East US 2, unchanged
- [x] 6. Aspire Pre-Provisioning Checks: not applicable
- [x] 7. Provision Preview: passed; no resources created or deleted
- [x] 8. Build Verification: 364 web tests and production build passed
- [x] 9. Docker Build Context Validation: unchanged
- [x] 10. Package Validation: guarded azd package passed
- [x] 11. Azure Policy Validation: seven existing assignments; preview passed
- [x] 12. Aspire Post-Provisioning Checks: not applicable

### Validation Proof — completed case launcher

The regression test first failed because the analyzed page still contained the
**Saved demos** heading. It passed after launcher visibility was bound to the
absence of an analysis. The full web suite (364 tests), TypeScript/Vite build,
and local browser checks at 1440px and 390px passed. Both browser views continue
directly from the header to planning routes and the analysis tabs with no email
panel, saved-demo launcher, recovery note, overflow or page error. Fresh guarded
preflight, AZD authentication, package validation, policy listing, no-create/
no-delete provision preview, Docker context review and static role review passed.
Deployment proof is recorded below when completed.

## Hide completed email-discovery step — 2026-09-14

Scope: after a reviewed supplier email successfully opens its completed
analysis, remove the entire email-discovery panel from the current page. Keep
the panel visible during processing and after any failure so the presenter can
retry. Same approved Azure target; no data, identity, role, schema, or
infrastructure changes.

### All validation checks pass — completed email step

- [x] 1. AZD Installation: 1.30.0
- [x] 2. Schema Validation: unchanged validated azure.yaml
- [x] 3. Environment Setup: existing guarded profile
- [x] 4. Authentication Check: existing authenticated environment
- [x] 5. Subscription/Location Check: Azure Dev / East US 2, unchanged
- [x] 6. Aspire Pre-Provisioning Checks: not applicable
- [x] 7. Provision Preview: passed; no resources created or deleted
- [x] 8. Build Verification: 363 web tests and production build passed
- [x] 9. Docker Build Context Validation: unchanged
- [x] 10. Package Validation: passed through guarded ACR path
- [x] 11. Azure Policy Validation: seven existing assignments; preview passed
- [x] 12. Aspire Post-Provisioning Checks: not applicable

### Validation Proof — completed email step

The regression test first failed because the completed email panel remained in
the document, then passed after the success-only dismissal was added. The full
web suite (363 tests), TypeScript/Vite production build, and browser checks at
1440px and 390px passed. The browser proof confirms the panel disappears after
successful analysis without overflow or page errors; failure-path tests retain
the email review for retry.
Guarded preflight, official schema validation, AZD authentication, Azure policy
listing, provision preview, packaging, and live role verification all passed.

### Deployment proof — completed email step

Source `9ecb912`; ACR run `ch1s` succeeded. Revision
`ca-sr-demo--0000035` is latest-ready with 100% traffic on immutable image
`sha256:9ce005afcbb4a242dcb33fb1bf1ad8b0b0e74d9eb099ff33ca7ae802339e139f`.
Guarded Fabric/Foundry readiness and application smoke checks passed. The
post-release role query confirmed the existing AcrPull, Key Vault Secrets User,
and Foundry User assignments. In the live Alex browser, Work IQ found the real
0914-A supplier email, **Analyze this disruption** completed on the same saved
case and analysis, and the entire **Supplier email** region disappeared. The
analyzed case remained visible; no duplicate case, outbound email, or approval
was created.

## Email entry visibility correction — 2026-09-14

Scope: keep inbox discovery available with an open case; show found email text
before analysis; explicitly analyze a newly created email case or reopen its
existing analysis. Remove the three prominent analysis-context lines and retain
timestamps in collapsed source details. Same approved target, no schema, roles,
configuration, recipient, or infrastructure changes.

### All validation checks pass — email entry correction

- [x] 1. AZD Installation: 1.30.0
- [x] 2. Schema Validation: official azure.yaml schema passed
- [x] 3. Environment Setup: existing guarded profile preflight passed
- [x] 4. Authentication Check: Will authenticated
- [x] 5. Subscription/Location Check: Azure Dev / East US 2, unchanged
- [x] 6. Aspire Pre-Provisioning Checks: not applicable
- [x] 7. Provision Preview: passed, no resources created/deleted
- [x] 8. Build Verification: 363 web tests and TypeScript/Vite build passed
- [x] 9. Docker Build Context Validation: lockfile and four Entra arguments intact
- [x] 10. Package Validation: guarded ACR path, azd package passed
- [x] 11. Azure Policy Validation: seven existing assignments; preview passed
- [x] 12. Aspire Post-Provisioning Checks: not applicable

### Validation Proof — email entry correction

Fresh 2026-09-14 checks: guarded preflight, preview, package; official schema;
AZD version/auth; policy list; 363 web tests and production build. Regression
tests first failed on the hidden inbox action, hidden email excerpt, prominent
metadata, and missing analyze action, then passed with the correction. Static
resource roles unchanged: AcrPull on shared ACR, Secrets User on vault, Foundry
User on project; live assignments independently confirmed. No database changes.
Actual App browser checks at 1440px and 390px, using explicitly simulated
responses, passed: loaded-case email check, immediate message text, existing
analysis reuse, collapsed metadata, no overflow or page errors.

### Deployment proof — email entry correction

Source `61b8fa5`, ACR run `ch1r` succeeded; revision `ca-sr-demo--0000034` is
latest-ready with 100% traffic. Immutable image:
`sha256:c7f34a20704951ab06cf231315bc5b306672a8693b7173f8ef8c33f74960cd83`.
Guarded Fabric/Foundry smoke and HTTP health passed; `azd show` confirmed the
existing environment. Post-release role query confirmed the same three scoped
assignments. Live Alex browser showed the email check with the existing case
open, no three-line metadata block, and Work IQ found the real 0914-A email with
its actual text and Outlook link. No email sent or approval submitted.
The live Analyze this disruption action then completed and reopened identical
case `RL-INBOUND-48f48fb45f22d0f5a0c30e4c301aaf887daae09dacfad264b7e4322f75b3105c`
and analysis `RL-ANALYSIS-b50702a5-5e6c-4655-963b-86c89ce8d993`.
The mailbox result remained visible and its check button remained enabled.

## Reviewed inbound email to case release — 2026-09-14 UTC

Scope: explicit reviewed Will-to-Alex email creates an email-bound case and
analysis. Existing approved Azure target, identities, roles, schema and older
cases are unchanged. No outgoing email or approval is performed. User explicitly
authorized body/link retrieval, saving this email into its case and analysis.

### Validation checklist — email to case

- [x] 1. AZD Installation: 1.30.0
- [x] 2. Schema Validation: official Azure/azure-dev v1.0 schema passed
- [x] 3. Environment Setup: existing approved profile guarded preflight passed
- [x] 4. Authentication Check: interactive Will authenticated
- [x] 5. Subscription/Location Check: exact Azure Dev / East US 2 verified
- [x] 6. Aspire Pre-Provisioning Checks: not applicable
- [x] 7. Provision Preview: passed; no resources created or deleted
- [x] 8. Build Verification: 360 web tests and production build passed
- [x] 9. Docker Build Context Validation: lockfile and four Entra args retained
- [x] 10. Package Validation: passed; supported guarded ACR image path retained
- [x] 11. Azure Policy Validation: seven assignments, same target preview passed
- [x] 12. Aspire Post-Provisioning Checks: not applicable

### Validation Proof — email to case

Fresh September 14: guarded .tmp/approval_release.py preflight/preview/package
passed. Official azure.yaml schema validated; azd authentication/version verified.
Full web suite 360 passed; focused20 and build also passed after readable blocker
copy correction. Backend integration/domain/API/persistence: 661 passed,18 skipped
(live settings absent), one preexisting deprecation warning. Existing migration
logging-order pollution documented in backend report; integration-before-persistence
run passed. Runtime lint/type checks and diff whitespace checks passed.
Static and live role checks match unchanged app AcrPull on ACR, Secrets User on
vault and Foundry User (53ca6127 role ID, formerly Azure AI User) on project.
No SQL schema/grants change. Independent review of f4b1de8..b6b4764 found no
Critical or Important findings; parent independently reran all39 new backend tests.
Local presenter interaction verified
at 1440px and 390px with explicit simulated fixtures, no overflow or page errors.
Work IQ metadata-only checks proved the same Internet Message-ID resolves after
Inbox to Archive and back, while the ordinary Outlook locator changed. The
message was restored to Inbox. Revision33/source974d4a1 deployed successfully,
ACR run ch1q, image sha256:42524abd04a483b33ded515418929d48b49ab13ef97423dd50e403a9a67ce3a2.
Latest-ready,100% traffic, unchanged scale0–2 and resource-scoped roles. Guarded
Fabric/Foundry smoke and azd show passed. Real Alex browser created from Will's
0914-A email, analyzed that bound message, opened its exact Outlook citation,
and repeated creation returned the identical case/analysis without a new one.
Full evidence: docs/reviews/2026-09-14-email-to-case-release.md.

## Read-only inbox check release — 2026-09-14 UTC

Scope: presenter-controlled Work IQ discovery and validated email review from
Will to Alex; no case creation, send, schema, role or infrastructure changes.
Existing approved Azure Dev / East US 2 / rg-supply-response-demo / ca-sr-demo.
The live launcher starts with Check email for disruptions. Saved work is secondary.

### All validation checks pass — inbox check

- [x] 1. AZD Installation: installed 1.30.0.
- [x] 2. Schema Validation: official Microsoft azure.yaml schema passed.
- [x] 3. Environment Setup: existing profile checked by guarded preflight.
- [x] 4. Authentication Check: interactive Will authenticated.
- [x] 5. Subscription/Location Check: existing exact target verified.
- [x] 6. Aspire Pre-Provisioning Checks: not applicable.
- [x] 7. Provision Preview: passed; existing resources only, no creates/deletes.
- [x] 8. Build Verification: 355 web tests and TypeScript/Vite build pass.
- [x] 9. Docker Build Context Validation: four Entra args and lockfile intact.
- [x] 10. Package Validation: passed; supported image path remains guarded ACR.
- [x] 11. Azure Policy Validation: seven existing assignments, no scope changes.
- [x] 12. Aspire Post-Provisioning Checks: not applicable.

### Section 7: Validation Proof — inbox check

Fresh 2026-09-14 checks: guarded preflight, preview and package passed against
the unchanged approved target. Official azure.yaml schema validation passed.
355 web tests and production build passed; 108 API/Work IQ tests passed.
Ruff and diff whitespace checks passed. Desktop (1440px) and phone (390px)
browser proof: actual component with explicitly simulated responses, preview
and Outlook link visible, prior cases collapsed/recoverable, no overflow/errors.
Review fixes simplify the search to subject:RL-001 with strict local markers
and limit the sanitized preview to 4,000 characters plus ellipsis.
Static roles: unchanged app AcrPull on ACR, Secrets User on vault, Azure AI User
on Foundry project. No new permission or SQL migration is needed. Actual live
retrieval was verified after deployment: real Alex browser found Will's
`Demo run 0914-A`, received 2026-09-14 05:10:43 UTC, on a check started at
05:24:34 UTC. Expanded preview matches the revised FYI body and exact quantities
and per-unit price. No seeded-message substitution, case creation, approval or
mail send occurred. Live screenshot and accessibility trace captured in task.

Release source `736c339`, ACR run `ch1p`, revision `ca-sr-demo--0000032`,
latest-ready with 100% traffic, unchanged scale 0–2. Immutable image digest:
`sha256:0bb30064c74fbed94da3f9472769913900fa6172556276dc74e31c9553b8ac38`.
Guarded live Fabric/Foundry readiness and `azd show` passed.
The returned citation opened the exact new message in Alex's Outlook account,
with matching sender, subject and body. Runtime roles remain unchanged.

## Simplified demo launcher release — 2026-09-14 UTC

Scope: user-approved featured resume for the verified analyzed disruption,
collapsed older cases, and separate honest new-demo copy. No records deleted;
no API, schema, identity, approval, mail, or infrastructure design changes.
Same approved Azure Dev / East US 2 / rg-supply-response-demo / ca-sr-demo target.

### All validation checks pass — launcher

- [x] 1. AZD Installation: 1.30.0.
- [x] 2. Schema Validation: official Microsoft azure.yaml JSON schema passed.
- [x] 3. Environment Setup: existing supply-response-personal profile verified.
- [x] 4. Authentication Check: interactive Will account authenticated.
- [x] 5. Subscription/Location Check: guarded exact-target preflight passed.
- [x] 6. Aspire Pre-Provisioning Checks: not applicable.
- [x] 7. Provision Preview: passed, existing resources only; no creates/deletes.
- [x] 8. Build Verification: TypeScript/Vite passed; 351 web tests passed.
- [x] 9. Docker Build Context Validation: unchanged Dockerfile/four Entra args,
  package-lock present; supported guarded ACR build path unchanged.
- [x] 10. Package Validation: azd package passed (no declared services).
- [x] 11. Azure Policy Validation: existing seven assignments, preview passed.
- [x] 12. Aspire Post-Provisioning Checks: not applicable.

### Section 7: Validation Proof — launcher

Fresh checks above executed 2026-09-14 UTC with `.tmp/approval_release.py`
preflight/preview/package. Static review confirms exact resource-scoped app
AcrPull, Key Vault Secrets User and Foundry project User roles unchanged;
live assignments also verified. No SQL migration/grant required.
New tests failed before implementation; 351 web tests and production build pass.
1440px/390px local browser checks pass: collapsed list, exact featured case
navigation, twelve other fixture cases retained, no overflow or page errors.
Screenshots in `.tmp/launcher-proof/` inspected; fixture explicitly simulated.
Independent read-only review found no actionable issues.

Release source `d14b2d5`, ACR run `ch1n`, revision `ca-sr-demo--0000031`:
latest-ready, Healthy/Running, 100% traffic, unchanged scale 0–2. Immutable image
`sha256:b58cca6e109e52b93181d3585bf2ace79d294bea0cbb53220274e174a5b5cadb`.
Guarded live Fabric/Foundry readiness passed; `azd show` confirmed the existing
environment. All three runtime resource-scoped roles remain unchanged.
Live Alex browser verified the new launcher, collapsed older cases, all twelve
other records retained, and Resume navigating to case
`RL-CASE-bcbb8740-c770-42fd-aa67-981d08b66383` with saved analysis
`RL-ANALYSIS-aa9e5be1-6d28-491e-a179-0eb4752bf00c`. The existing supplier email
and analysis display correctly. No case, analysis, approval or email was created
or deleted. Returned browser to the launcher for the presenter.

## Response selection feedback release — 2026-09-14 UTC

Scope: approved visible selected-card feedback and navigation to approval only.
Existing Azure Dev / East US 2 / rg-supply-response-demo / ca-sr-demo target is
unchanged. No backend, schema, RBAC, identity, mail, or execution changes.

### Section 7: Validation Proof — selection feedback

- `npm test`: 348 passed across 24 files; regression tests failed on the missing
  selected state before implementation and now pass.
- `npm run build`: TypeScript and Vite production build passed.
- Browser checks at 1440px and 390px: selected outline/text, continuation to tab4,
  focus, retained selection, no overflow, no page errors, no mutation requests.
  Screenshots inspected in `.tmp/selection-proof/` (simulated local data).
- Independent read-only review: no actionable findings.
- Existing-target guarded preflight passed. AZD 1.30.0 installed, existing named
  environment verified, authenticated interactive Will identity confirmed.
- Official Microsoft azure.yaml JSON schema validation passed.
- Guarded `azd provision --preview --no-prompt` passed; same existing resource
  group, app, insights and vault; no creates/deletes. Existing metadata/secret
  reference reconciliation only, no intended infrastructure changes.
- `azd package --no-prompt` passed (no declared services); supported image path
  remains guarded ACR build with four exact Entra arguments, not AZD packaging.
  Dockerfile and lockfile verified; no build-context dependency changes.
- Azure Policy assignment inventory unchanged; exact preview passed.
- Static role review: app identity retains exact ACR Pull, vault Secrets User,
  Foundry project Azure AI User scopes. No privilege changes.
- Aspire pre/post checks and EF migrations: not applicable; no SQL changes.

Release verified: ACR run ch1m succeeded; revision30 is latest-ready with 100%
traffic and unchanged scale0–2. Image digest:
`sha256:e269e7160d40b916b0761a715424b8f6cc6a80f5446bd7649bf46d7f6ddf96b1`.
Guarded live Fabric/Foundry readiness passed. `azd show` confirmed the existing
environment; exact three resource-scoped runtime roles remain unchanged.
Live Alex browser: selected Expedite, visibly verified outline and ✓ Selected,
continued to tab4 with focus and separate Submit for Finance review control.
Restored Combined and verified its original waiting-for-Taylor review remained.
No submission, approval, mail, execution, new case, or new analysis was performed.
Prior revision29 approval acceptance below is historical.

> **Status:** Validated — completed-case-launcher correction passed fresh validation; revision35 remains live pending this release.

## Independent approval browser release — 2026-09-13

User approved connecting and deploying Alex → Taylor → Alex, with real separate
identity browser verification. Preserve the existing Azure Dev subscription,
East US 2, resource group rg-supply-response-demo and Container App ca-sr-demo.
No new resources, app roles, identities, consent, mail, report publication, scale
changes or destructive data operations. Recipe remains AZD via the existing
guarded deployment script; use this worktree's committed image and infrastructure.

- [x] Connect exact existing Taylor identity and default-off independent workflow
  setting through the supported Bicep/parameter/script path.
- [x] Review API and browser integration and verify local journey, not just units.
- [x] Check approval schema with read-only queries; review any required additive
  migration and native acceptance before activation. Additive migration applied.
- [x] Resolve automatic action-planning compatibility for independent decisions;
  label operational execution and outgoing email as not delivered in this milestone.
- [x] Complete azure-validate with fresh proof, guarded existing-target preview,
  build/package and role checks. Previous release proof below is historical only.
- [ ] Deploy the reviewed exact image, verify health and real Alex/Taylor sessions.

Deployment and health passed; the combined checkbox remains open for Taylor's
real session. ACR run ch1k succeeded; image digest
sha256:cc7716326e2758eaca834b531b81a679108ea4d4ad384580ff371af031b5661d.
Revision29 is latest-ready, Healthy/Running/Provisioned with 100% traffic and
unchanged scale 0–2. Guarded smoke passed live Fabric/Foundry readiness. `azd show`
confirmed the existing named environment (no separately declared services).
Taylor object binding and independent flag were read back from the deployed app.

The reviewed operational migration retained schema version12 and identical
payload hashes/counts for all 12 old cases, 8 analyses and 1 decision. Both Finance
tables and projection columns exist with trusted constraints; no grants added.
Subsequent browser acceptance deliberately created one fresh case, analyzed it
through live services and submitted its $24,750 combined response as real Alex.
The app displays Waiting for Taylor with an exact review link. Taylor's existing
account reached the Microsoft password screen; no Taylor action or Alex final
approval has been performed. Full evidence:
docs/reviews/2026-09-13-approval-browser-release.md.

Fresh read-only checks September 13: Azure Dev tenant and existing app target
resolved; latest ready revision remains 0000028. Taylor Brooks (Finance) is
already assigned the API's finance_approver app role. The running app has no
Taylor object-ID or independent-Finance environment setting. The existing app's
read-only database check confirmed version 12 but missing Finance tables and
proposal columns. Its identity has no CREATE TABLE/ALTER permission; no privilege
changes are needed or planned. Direct administrator connectivity was then verified
outside the restricted local network sandbox.

### All validation checks pass

- [x] 1. AZD Installation
- [x] 2. Schema Validation
- [x] 3. Environment Setup
- [x] 4. Authentication Check
- [x] 5. Subscription/Location Check
- [x] 6. Aspire Pre-Provisioning Checks (not applicable)
- [x] 7. Provision Preview
- [x] 8. Build Verification
- [x] 9. Docker Build Context Validation
- [x] 10. Package Validation
- [x] 11. Azure Policy Validation
- [x] 12. Aspire Post-Provisioning Checks (not applicable)
- [x] Static and pre-deployment live role verification

### Validation proof — approval milestone

September 13, approximately 22:00–22:15 America/Chicago: AZD 1.30.0,
`azd auth login --check-status` (Will), named environment and exact existing
subscription/location passed. Official Azure/azure-dev JSON schema validated
azure.yaml. `.tmp/approval_release.py preflight`, `preview`, and `package`
passed. Preview reconciles existing Container App/Application Insights provider
properties; no resource creation/deletion, role expansion or scale change.
Seven existing policy assignments were inspected; preview had no policy denial.
Dockerfile, lockfiles and four required frontend build arguments were reviewed.
This project's azure.yaml intentionally has no services: azd package is a no-op;
the guarded release builds the real image with ACR and all required arguments.

Parent backend/API/auth/Finance/execution/persistence/deployment regression:
561 passed, 11 skipped, one inherited warning; all fabric_live tests excluded.
Fresh `npm test -- --run`: 346 passed across 24 files. `npm run build` passed.
Local two-page browser proof covers rejection/resubmission/approval/finalization,
desktop and phone layouts, using explicitly labeled simulated API responses.
This is not real Microsoft-session proof. Final approval wording regression was
observed failing then passing. Static Bicep and live role listing agree on only
resource-scoped AcrPull, Key Vault Secrets User and Foundry User for the existing
app principal; no grants were added.

Native SQL Server 2022 upgrade test passed on the
existing private supply-response-test VM: 1 passed in 0.91 seconds. The guarded
runner created and removed only its fresh disposable database. It proved legacy
payload/version preservation, additive column defaults, repeat application,
trusted foreign keys and filtered uniqueness. Operational SQL SHA-256:
38b1656ad9acf79f5d69ebebc34e5be1ab09440cc354fd7f02e760f8da3f3b66.
Independent schema review approved the bounded upgrade before live application.
SSH host trust was restored by matching the public key fingerprint to
https://exe.dev/docs/faq/host-key; verification was never disabled.

## Traditional operational reporting release — 2026-09-12

User approved the traditional reporting correction and implementation. Same
existing Azure Dev subscription, East US 2, supply-response-personal environment,
ca-sr-demo, Fabric SQL database, report and semantic model. No new resources,
permissions, licensing, scale changes, saved-case mutations or operational actions.
The additive isolated reporting dataset and reviewed semantic model have their
own verification record. Website changes only correct traditional navigation and
scope language; reporting activation remains separately gated on native proof.

Recipe: AZD, existing guarded deployment script. No infrastructure redesign.

- [x] All validation checks pass, including final reporting artifact review and native acceptance.
  - [x] 1. AZD Installation.
  - [x] 2. Schema Validation.
  - [x] 3. Environment Setup.
  - [x] 4. Authentication Check.
  - [x] 5. Subscription/Location Check.
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview.
  - [x] 8. Build Verification.
  - [x] 9. Docker Build Context Validation.
  - [x] 10. Package Validation.
  - [x] 11. Azure Policy Validation.
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static and live role verification.

### Validation Proof — current reporting release

Fresh September 12 checks around 21:01 America/Chicago: AZD1.30.0, login as Will,
named environment, official Azure/azure-dev azure.yaml JSON schema validation,
guarded existing-target preflight, named provision preview, 326 frontend tests,
production build, uv build, named azd package, and 98 infrastructure/activation
tests passed. One inherited Starlette deprecation warning remains. The first
preflight attempt omitted the local environment selector and stopped before
mutation; rerunning with the verified operator and selected environment passed.

Preview has no resource creation/deletion or permission expansion. It reconciles
the existing Container App and Application Insights provider properties. Seven
existing policy assignments were read; preview returned no denial. Dockerfile
and exclusions are unchanged, npm lock exists, no new application permission is
needed. Static Bicep and live assignments confirm the same resource-scoped
AcrPull, Key Vault Secrets User and Foundry User for principal
a95ffce4-570b-4931-bfd4-4894e7281890. Final reporting artifact review/native
acceptance still precedes receipt activation. Evidence is recorded in
docs/reviews/2026-09-12-traditional-reporting-verification.md.

Final artifact fd53e99 was published at 21:40 America/Chicago. Independent remote
definition review matched all 180 committed report parts and the existing model
binding. Native Alex-session acceptance confirmed the corrected stock table,
shipment snapshot/row/chart and whole-dollar response-options table. Artifact
digest: 198ea01a8fc25a999355b730c92e843f6dc565e645c8ef571e6ab403b9b177c0.
Final regression evidence: 187 Fabric tests passed (one optional live test skipped),
326 web tests passed, production build passed, 98 deployment/activation tests
passed, and guarded read-only existing-target preflight passed. Persisted native
query results include unavailable output for mismatched identities. The
azure-validate workflow completed ResolveErrors before this status was set.
Receipt activation is accepted for September 12 traditional/exact-source reporting,
not for populated execution outcomes or a separate finance-person login workflow.

### Reporting release deployment proof

Guarded deployment of 78a6bf5 completed September 12 around 21:55 America/Chicago.
ACR run ch1j succeeded; image digest
sha256:dd20b4659bb37a6154d7137829c845de3748d503e29bbb4ee4add679ba842c08.
Revision ca-sr-demo--0000028 is Healthy/Running, Provisioned/Succeeded, latest-ready,
with 100% traffic and unchanged scale 0–2. Two initial existing-health timeouts
were retried by the guard; live health passed before deployment continued.
Post-deployment --smoke passed Fabric/Foundry readiness without delegated retrieval.
Runtime reports saved-analysis-v1 activation. Three exact existing roles remain
AcrPull, Key Vault Secrets User and Foundry User; no role or SQL grant was added.

azd show completed; this project intentionally has no separately declared services,
so its output gives the resource-group link rather than an endpoint. The actual
Container App read confirmed:
https://ca-sr-demo.orangehill-337f5d48.eastus2.azurecontainerapps.io/.
Actual browser acceptance as Alex used the existing September 9 case/analysis.
Live DOM links and native Power BI destinations reconciled inventory, orders and
shipment; broad navigation contains only the explicit fictional dataset filter.
Header/tabs, USD totals and unit prices, source icons and explanation dialog passed.
No cases, analyses, decisions, approvals or execution records were written.

## Presenter experience release — 2026-09-12

User approved deployment of the reviewed local experience to the existing demo.
Same Azure Dev subscription, East US 2, supply-response-personal environment and
ca-sr-demo application. Changes since be45c4d are frontend and documentation only:
presenter header, three stage tabs, source icons, USD formatting and recommendation
explanation sheet. No source/SQL/schema/report publication, permission, scale,
case/analysis/decision/execution writes, Git push or merge are part of this release.
The preview fixture is not the production entry point.

- [x] All validation checks pass.
  - [x] 1. AZD Installation (1.30.0).
  - [x] 2. Schema Validation (official Azure/azure-dev schema).
  - [x] 3. Environment Setup (existing named environment).
  - [x] 4. Authentication Check (Will, interactive User).
  - [x] 5. Subscription/Location Check (Azure Dev / East US 2).
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview (success, no resource creation/deletion).
  - [x] 8. Build Verification (325 tests, TypeScript/Vite, uv build).
  - [x] 9. Docker Build Context Validation (unchanged Dockerfile, exclusions, locks).
  - [x] 10. Package Validation (named azd package passed).
  - [x] 11. Azure Policy Validation (same seven assignments; no preview denial).
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static and pre-deployment live role verification.

### Validation Proof

Fresh checks September 12, approximately 18:54–18:57 America/Chicago:
`azd version`, `azd env list`, `azd auth login --check-status`, exact guarded
preflight, official-schema jsonschema validation, named `azd provision --preview
--no-prompt`, `npm test` (325/325), `npm run build`, `uv build`, named `azd package`,
policy/role/resource queries, and `git diff --check` passed. Initial sandboxed CLI,
package and cache operations were denied; scoped escalated reruns succeeded.
The resource tag query initially used incompatible CLI flags; the supported query
returned exactly one target, ca-sr-demo. No configuration changed to resolve these.

Preview reconciles only the existing app and Application Insights; no new/deleted
resources or permission changes. Backend, infrastructure, deployment scripts,
Docker inputs and migrations are identical to deployed be45c4d. Static definitions
and live assignments confirm resource-scoped AcrPull, Key Vault Secrets User and
Foundry User for unchanged principal a95ffce4-570b-4931-bfd4-4894e7281890.
Existing schema access is preserved; no SQL grants/migrations are required.

Rollback checkpoint: ca-sr-demo--0000026, image digest
sha256:51d21a6e997e198867af0c8c8e0cef19bb4940cf4390d0f59a81f742507e5af2.
Scale is 0–2 and latest revision has 100% traffic.
Desktop/mobile sheet and currency acceptance is documented in
docs/reviews/2026-09-12-recommendation-explanation-sheet-verification.md.


### Deployment and live acceptance

Guarded deployment of c8a7c38 completed September 12, approximately 19:03
America/Chicago. ACR run ch1h succeeded. Image digest:
sha256:5cef6c684159811db263fa7943fda1b3f9f0250c19f258fe6c328cb325409cc4.
Revision ca-sr-demo--0000027 is Healthy/Running with 100% traffic. Existing health
initially timed out twice, then passed before the image build; no bypass was used.
Post-deployment `azd show`, active revision query, public health/runtime reads,
asset checks and unchanged three-role assignment verification passed. Health is
live/Fabric SQL/schema12; all four capability readiness checks report ready.
Served assets: index-D9jRDwmc.js, application-IVdiKzW2.js,
application-BVnbdk36.css. New labels, sheet styling and source SVG assets verified.

Browser acceptance used the actual deployed application and Alex's existing
Microsoft session, not the preview fixture. Reopened existing case
RL-CASE-213c13ef-828c-4b6d-b56c-5f8332c406d1 and its September 9 analysis.
Verified updated header, all three stage tabs, $955,000/$328,000/$0 baseline,
$7.50/$1.50 unit prices, recommendation explanation trigger and modal, predicted
comparison values and recorded ranking reason. Visually inspected the live sheet.
Escape dismissed it and returned focus to its trigger; reopening worked.
No case creation, analysis, source retrieval, decision approval or execution ran.
This particular saved analysis reports Power BI comparison unavailable; readiness
is not proof of report availability for an individual historical analysis.
The live sheet was left open for the presenter. Fresh retrieval and actual
approval/execution remain untested in this release acceptance.

## Session recovery release — 2026-09-12 (validation proof)

Scope: the approved expired-session correction only; same Azure Dev subscription
`24ee21b9-2893-4e4d-bd85-5d3be76470cd`, East US 2, environment
`supply-response-personal`, existing `ca-sr-demo` in `rg-supply-response-demo`.
No reporting publication/activation, source changes, schema migrations, permissions,
new resources, case/analysis/decision/action writes, Git push, or merge.
Prior Validated status records prior releases, not completion of this release.

- [x] All validation checks pass.
  - [x] 1. AZD Installation (1.30.0).
  - [x] 2. Schema Validation (official Azure/azure-dev schema).
  - [x] 3. Environment Setup (existing named environment).
  - [x] 4. Authentication Check (Will, interactive User).
  - [x] 5. Subscription/Location Check (same confirmed Azure Dev / East US 2).
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview (success; no resource creation/deletion).
  - [x] 8. Build Verification (305 frontend tests, production build, uv build).
  - [x] 9. Docker Build Context Validation (unchanged locked inputs/exclusions).
  - [x] 10. Package Validation (azd package and uv build passed).
  - [x] 11. Azure Policy Validation (same seven assignments; preview no denial).
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static and live role verification (same principal, three exact-resource roles).

Fresh validation commands completed September 12: `azd version`, `azd auth
login --check-status`, named environment lookup, guarded same-tenant preflight,
official-schema jsonschema check, `azd provision --preview --no-prompt`,
`azd package --no-prompt`, `uv build`, policy/role reads, `npm test`,
`npm run build`, and `git diff --check`. The first preflight invocation omitted
the local environment selector and failed before cloud mutations; setting the
already-selected name in the process environment resolved it. No remote setting
was changed. Initial public curl reads timed out; subsequent IPv4 and normal
reads returned 200 live/Fabric SQL/schema12. Callback GET200 has no COOP header.

Implementation `5bbb75b` independently approved by session_recovery_review with
no findings. Parent verified real installed MSAL bridge in Chromium against both
Vite development and a production build with synthetic credentials: silent
broadcast without dashboard/API startup, exact case/analysis return navigation,
and safe malformed-callback failure. Full App recovery at 1280px and 390px
preserves the URL, makes no API requests, hides generic workspace errors, and
displays an actionable sign-in notice. Screenshots inspected in
`.artifacts/session-recovery/recovery-1280.png` and `recovery-390.png`.
These are synthetic local-browser checks, not live Microsoft sign-in acceptance.

Release completed September 12 using the existing guarded deployment. ACR run
`ch1g` succeeded; revision `ca-sr-demo--0000026` is Ready/Running with 100% traffic.
Immutable image digest: `sha256:51d21a6e997e198867af0c8c8e0cef19bb4940cf4390d0f59a81f742507e5af2`.
Post-release `azd show`, health/runtime reads, and existing three-role verification
passed. Scale remains 0–2 and the managed identity is unchanged. Health reports
live/Fabric SQL/schema12; runtime reports all four capabilities ready (not an
end-to-end source retrieval test).

The same isolated Chromium callback tests also passed against the deployed URL:
silent broadcast without App/API startup, exact original case/analysis URL return,
and safe malformed-callback guidance. Public bundle inspection confirmed
`index-DUUx6KrO.js` and `application-DhINkC1k.js` contain the correction. These
synthetic checks created no cases and exchanged no Microsoft tokens. A genuine
expired Microsoft session has not yet been observed completing recovery.

## Validation Proof — native readability and reopening correction, 2026-09-11

User requested continuing until the live experience looks right, with proof.
Scope: wrapped Power BI business text, one heading per card, taller overview
rows, and GET-only reopening of an existing case. Reuse the same confirmed Azure
Dev / East US 2 / supply-response-personal resources and exact report/model IDs.
No schema, source data, role, licensing, decision, execution, push, or merge changes.
The reporting activation receipt remains absent. Plan:
`docs/superpowers/plans/2026-09-11-native-readability-and-reopen.md`.

- [x] All validation checks pass.
  - [x] 1. AZD Installation (1.30.0).
  - [x] 2. Schema Validation (official Azure/azure-dev JSON schema).
  - [x] 3. Environment Setup (same existing named environment).
  - [x] 4. Authentication Check (Will interactive User).
  - [x] 5. Subscription/Location Check (same confirmed Azure Dev / East US 2).
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview (AZD and detailed ARM what-if succeeded).
  - [x] 8. Build Verification (292 frontend tests, production build, uv build).
  - [x] 9. Docker Build Context Validation (unchanged locked inputs/exclusions).
  - [x] 10. Package Validation (azd package and uv build passed).
  - [x] 11. Azure Policy Validation (seven assignments; no preview denial).
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static role verification (same principal and three exact-resource roles).

Read-only exact-resource preflight passed. Initial invocation lacked the local
operator selector; resolved by checking the signed-in Will account and passing
its identity in memory. No identity/configuration change was made. The initial
parser run lacked access to its public package cache; reruns use the existing
locked Microsoft parser dependencies. Local failures are not hidden as passes.
Native acceptance will be recorded separately from deployment/schema success.

Detailed preview succeeded. The local summary initially encountered a null delta;
reading the saved result with null handling passed. No resources are created or
deleted. The same image, resources, probes, scale 0–2 and runtime settings are
preserved; origin/Insights expressions and provider metadata are the only app
differences. Three reference-based role expressions are unsupported by what-if;
static templates and actual assignments separately confirm the existing roles.
Private app/role/preview baseline:
`/var/folders/zf/rcq9c9jx42l97zd9fgs115400000gn/T/readability-release-baseline-6apuvtv0`.

Report formatting commit `6304b8f` independently passed spec/code review with no
findings. Its 148 generator/project tests (including Microsoft TOM), fresh 62
generator tests, artifact checks and Fabric publication dry run passed. The
report/model definitions, association and datasource metadata are backed up at
`/var/folders/zf/rcq9c9jx42l97zd9fgs115400000gn/T/readability-report-baseline-d9nyl81a`.
This reviewed report-only publication proceeds independently of the app release;
it does not provision Azure infrastructure or activate a reporting receipt.
The app build/review gate remains pending while reopening is corrected.

App reopening corrections through `ecbdf0f` now independently pass spec/quality
review. Fresh frontend suite:292passed; production build passed with the existing
513.84kB chunk advisory. Local isolated desktop/mobile presentation tests:2passed;
source footers remain below all card contents. These use local synthetic fixtures
and are not live-user proof. Frontend native acceptance follows deployment.

The first report formatting publication failed actual native acceptance: titles
were no longer duplicated, but the card runtime still rendered single-line
ellipses. Correction `7b6e20e` replaces all 46 string callouts with native bound
paragraph textboxes, retaining every measure, position, title and filter.
Independent final spec/code review passed with no findings; all 153 report tests,
locked Microsoft TOM, schema/author checks and a fresh publication dry run passed.
Direct Measure evaluation and visual fit still require the actual service check.
Native rendering of the 46 paragraph textboxes passed across the eight pages.
The case picker cleanup `f5191ad` passed independent review and was deployed as
revision24; exact-case reopening, unchanged refresh and invalid-bookmark recovery
were verified. Native Actions/outcomes found a chart axis identity collision.
Reviewed `4748a91` replaces only that chart with a single-axis table; all 154 report
tests, offline author/schema checks and fresh publication dry run passed. No DAX,
SQL, model identity, data or permission changes are needed. The same report/model
were published and their binding/SQL datasource reverified. A matching existing
app release is verified ready as `ca-sr-demo--0000025`, image
`sha256:dfd3e0f566ec0d929a0cc5fbe77a8a92697850f7a91fd91df24c6f4d6b29b4dc`,
with 100% traffic, live health, schema 12, unchanged identity/scale, and the reporting
receipt still empty. Exact original-case refresh remained unchanged after this
final release. Detailed native acceptance and remaining coverage gaps are recorded in
`docs/reviews/2026-09-11-native-planner-acceptance.md`.

Azure validation workflow completed its error-resolution step after all listed
checks passed. This Validated status permits the bounded existing-app deployment,
not report activation or a claim that the rendered experience has passed.

## Validation Proof — planner conformance correction release

User approved releasing reviewed corrections through `80410e4`, then checking the
deployed cards and Power BI pages. Reuse the confirmed Azure Dev subscription,
East US 2, `supply-response-personal`, existing app and existing report/model IDs.
No schema/data migration is needed: database scripts, infrastructure and deployment
scripts are unchanged from `ae17131`. Publish the corrected existing report/model
and app; keep the new reporting receipt empty until native acceptance succeeds.
No new resources, grants, source edits, case creation, analysis, Decision approval,
action execution, simulation, Git push or merge is included.

- [x] All validation checks pass.
  - [x] 1. AZD Installation (1.30.0).
  - [x] 2. Schema Validation (official Azure/azure-dev JSON schema).
  - [x] 3. Environment Setup (existing named environment selected).
  - [x] 4. Authentication Check (Will interactive User).
  - [x] 5. Subscription/Location Check (same Azure Dev / East US 2).
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview (AZD preview and detailed ARM what-if succeeded).
  - [x] 8. Build Verification (246 frontend tests, production web build, uv build).
  - [x] 9. Docker Build Context Validation (unchanged locked inputs/exclusions).
  - [x] 10. Package Validation (azd package --no-prompt passed).
  - [x] 11. Azure Policy Validation (seven assignments reviewed; no preview denial).
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static role verification (unchanged exact-resource registry/vault/project roles).

Fresh read-only named-environment preflight passed. Confirmed bootstrap false and
new reporting receipt empty. The reviewed SQL correction passed 139 tests on the
dedicated synthetic SQL engine; reporting regression passed 186 tests. These are
not substitutes for native Power BI DAX, visual/access/navigation acceptance.
Fresh validation completed 2026-09-10 03:27 UTC. Commands included the named
environment preflight, official `azure.yaml` JSON Schema validation,
`npm test -- --run`, production frontend build, `uv build`, `azd package
--no-prompt`, `fabric/deploy.py --dry-run`, `azd provision --preview --no-prompt`
and a detailed `az deployment sub what-if`. All passed. Fabric dry run included
the pinned TOM parser and exact generated artifacts. The 505.86 kB frontend
bundle warning is non-blocking.

The detailed preview changes existing app and Insights metadata only: no resource
creation or deletion. Image, CPU/memory and probes (compared by type) match the
baseline; scale remains 0–2. Secret name/system identity are unchanged. Origin,
vault URI and Insights connection expressions reference the same verified
resources; other differences are provider defaults/read-only fields. Three
reference-based role entries cannot be expanded by what-if; static definitions
and live assignments confirm the same exact-resource registry, vault and Foundry
roles. Live baseline is revision `ca-sr-demo--0000021`, latest traffic 100%, image
digest `b5b6c974ac775e6465b890e56306adf9f35da5d69cfeda1f35c089609a2b26df`.
Existing report/model IDs and their association match the prior release.
Fresh report/model definitions, report association and datasource metadata were
exported to owner-only rollback files at
`/var/folders/zf/rcq9c9jx42l97zd9fgs115400000gn/T/conformance-release-baseline-k8go4hn4`.
No cloud mutation in this release yet. Native browser inspection is currently
blocked by the locked Mac; it remains an activation gate, not a publication gate.
Prior release evidence follows as history.

### Publication and live verification — 2026-09-10

Published the existing `SupplyResponse` semantic model and report successfully
using `fabric/deploy.py`, then deployed source checkpoint `d6961ab` using the
validated guarded `scripts/deploy_personal_tenant.sh --apply` workflow. Registry
build `ch1c` succeeded. No SQL migration, permission change, case/analysis creation,
action execution, simulation, Git push or merge was performed.

The report remains `e7611c8c-c887-443f-858a-13b1044bb4b9` and its model remains
`2100a769-d718-47b7-9715-7f4e804f1c8a`, in the same approved workspace. The model
association and datasource metadata match the pre-release backup. All eight
native report pages are present with planner-facing names.

Live Azure verification passed:

- Ready revision `ca-sr-demo--0000022`, latest traffic 100%.
- Immutable image digest
  `f69648ad7d50418319b160ba16f93f1656a450754cbf4c1fe8ff241e71a9e3d4`.
- Same system identity and three exact-resource AcrPull, Key Vault Secrets User
  and Foundry User roles; min/max replicas remain 0–2.
- `/health`: status ok, live mode, Fabric SQL, schema version 12.
- `/api/runtime`: operational store, Work IQ, agent runtime and Power BI ready.
  This is readiness evidence, not a new end-to-end analysis run.
- New reporting receipt remains empty and reporting activation contract absent.
- Live bundle `/assets/index-BeBzPXHl.js` contains the corrected original-delivery
  wording, expandable partial-quantity fields and evidence footer. The obsolete
  `Saved disruption:` and `Recorded partial supply:` strings are absent. Bundle
  inspection is not a visual check of pill placement.

Read-only Power BI DAX returned 12 existing cases, seven analyses, 70 saved
records and 42 response options. All seven case/analysis scope checks passed,
including corrected original-delivery versus proposed-shipment narratives.
Unselected scope asks for a case rather than showing unrelated data. These
checks do not create or refresh business analyses.
Exact shipment, transfer and qualification measures returned the requested
record identity and matching quantity. A mismatched case/analysis returned no
selected analysis or disruption narrative. All bounded checks completed with
exit code zero. There are no existing cases with multiple analyses, so this run
cannot prove historical-analysis persistence; no historical fixture was created.

Owner-only live verification evidence is stored in
`/var/folders/zf/rcq9c9jx42l97zd9fgs115400000gn/T/conformance-live-checks-uw5yb3py`.
`azd show` was run; this guarded project deliberately has no AZD service entry,
so the verified endpoint was read directly from the Container App:
https://ca-sr-demo.orangehill-337f5d48.eastus2.azurecontainerapps.io/.

The Mac remains locked. Native visual fit, Alex access, card-to-record navigation
and the full artifact-bound acceptance matrix remain unverified. New links stay
inactive; no release attestation has been issued.

## Validation Proof — coordinated planner reporting release (2026-09-09)

User approved publication of the reviewed planner application and its matching
Fabric SQL/report/model, followed by native data/access/navigation acceptance.
Use the existing Azure Dev / East US 2 / supply-response-personal targets.
Preserve report/model IDs, stored payloads, identities, permissions and scaling.
No Decision approval, playback, source-message edits, new cloud resources or
Git push is included. On resumption, the user explicitly approved deploying now
with the new reporting links disabled, before native browser acceptance.
No historical acceptance fixture is authorized. Native visual/access/history
checks remain activation gates, not blockers to this bounded publication.

- [x] All validation checks pass.
  - [x] 1. AZD Installation (1.30.0).
  - [x] 2. Schema Validation (official Azure/azure-dev JSON schema).
  - [x] 3. Environment Setup (isolated checkout; verified existing bindings).
  - [x] 4. Authentication Check (existing Will interactive account).
  - [x] 5. Subscription/Location Check (same confirmed Azure Dev / East US 2).
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview (detailed ARM what-if and resolved configuration).
  - [x] 8. Build Verification (`uv build` passed).
  - [x] 9. Docker Build Context Validation (Dockerfile, ignore rules, lockfiles).
  - [x] 10. Package Validation (`azd package --no-prompt` passed).
  - [x] 11. Azure Policy Validation (seven assignments reviewed; no preview denial).
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static role verification (same app principal; resource-scoped registry,
    vault secret-read and Foundry User assignments, no role changes).

Initial read-only inventory confirms revision20 and its immutable image, same
system identity and scale 0–2. Fabric contains the same report/model and schema12.
Nine cases contain four analyses across four cases, with no within-case history.
Existing report/model definitions, association, data-source metadata and workspace
access were exported to owner-only local rollback files. No cloud mutation yet.
The missing optional reporting-receipt deployment path was repaired in
`5ac9ebf` and independently reviewed: spec compliant, quality approved, no
Critical/Important findings. The focused deployment/activation suite reported
98 passing tests and the inherited Starlette deprecation warning. Reporting
artifact digest remains unchanged; no receipt was issued or installed.

Fresh read-only release preflight and `fabric/deploy.py --dry-run` passed. The
report/model association matches the expected existing IDs; the saved SQL
binding matches the runtime target (database-name capitalization differs).
Twenty-four corresponding runtime settings match exactly. Alex is not a direct
workspace member; report-specific access still requires native verification.
The current app remains revision20, latest traffic100%, scale0–2.

The first AZD preview used the default bootstrap parameter and was **not
applied**. Local AZD configuration now explicitly sets bootstrap false and the
existing immutable image. The corrected preview passed without new resources,
preserved targetPort8000 and proposed existing app/Insights reconciliation only.
Fresh completion at 2026-09-09 21:45 UTC: official JSON Schema validation passed;
read-only resource/auth/binding preflight passed; frontend TypeScript/Vite build
passed. The detailed ARM what-if succeeded. Image/resources and probes (by type)
match the prior app. Secret identity/name are unchanged; differences for the
secret URI, frontend origin and Insights connection are unresolved expressions
over the same verified resources. The only new environment setting is the blank
reporting receipt. Other deltas are provider-returned defaults/read-only fields
and existing Insights metadata reconciliation. Three reference-based role entries
cannot be expanded by what-if; static definitions and live exact-resource role
IDs independently match (AcrPull, Key Vault Secrets User, Foundry User). The role
display name is now Foundry User; its unchanged role UUID is authoritative.
The single API-tagged target was verified by filtering the supported resource
list response. Seven existing security/Defender policy assignments reviewed;
preview shows no policy denial or new/deleted resources. Prior same-source Python
build, package, 98 deployment/activation tests and Fabric/TOM dry run remain valid.

Publish SQL reporting views, existing model/report, then app with an empty
reporting receipt. Do not issue/activate a receipt based on publication success.
No test cases, approvals, action execution or source-message edits are included.
Existing saved records have not been changed. Owner-only rollback
snapshot: `/private/tmp/planner-release-baseline-p_55r30z` (report/model definitions,
association, datasource and access metadata). Retain it until acceptance closes.

### Publication result — 2026-09-09 21:53 UTC

- Source release `ae17131`; registry build `ch1b` succeeded. Immutable image digest
  `b5b6c974ac775e6465b890e56306adf9f35da5d69cfeda1f35c089609a2b26df`.
- Applied reviewed `002_analytics_views.sql` batches in one transaction. Before
  and after hashes of saved case, analysis and decision payloads match exactly:
  ten cases, five analyses, zero decisions. No fixture or business operation was
  created. Prior SQL definitions/fingerprints retained in owner-only
  `planner-sql-rollback-fbbob76c` under the task's temporary directory.
- Published the existing SemanticModel and Report with `fabric/deploy.py`.
  Read-back retains the same report/model association and SQL datasource. Pages
  API returns all eight expected pages. Read-only DAX returns five saved analyses,
  fifty supporting records and thirty options, matching SQL counts. This is a
  publication/data-connectivity check, not complete DAX/native acceptance.
- Guarded app deployment completed. Existing-health requests initially timed out
  twice, then passed without bypass. Revision `ca-sr-demo--0000021` is latest-ready,
  provisioning Succeeded and receives100% latest-revision traffic. System identity,
  scale0–2 and exact-resource AcrPull/vault secret-read/Foundry User roles remain
  unchanged. No placeholder revision was deployed.
- `/health` HTTP200 confirms live Fabric SQL/schema12. `/api/runtime` HTTP200
  reports all existing capabilities ready. The new reporting receipt is explicitly
  empty and `power_bi_reporting_contract` is absent, so new report links remain
  inactive. No acceptance receipt was issued.
- Public HTML and `/assets/index-BRNVKedn.js` return HTTP200. Deployed bundle
  contains all three investigation-row labels and bottom-of-card evidence status.
  `azd show` confirms the selected environment; service URLs are absent because
  this project intentionally builds via its guarded script. Container App ingress
  independently confirms the existing HTTPS demo endpoint.

Remaining: native report layout/text fit, Alex access, historical filter
persistence and every card-to-exact-record journey, then receipt activation.
The Mac lock and unapproved historical fixture do not invalidate publication;
they remain acceptance constraints. No merge, Git push, source-message edits,
case creation, analysis invocation, decision approval or action execution occurred.

## Validation Proof — descriptive citation labels (2026-09-08)

User approved deploying the two clearer link labels to the existing demo.
Scope: UI wording and regression coverage only; URLs, trust policy, evidence,
approvals, identity, roles, scaling and infrastructure are unchanged. No new
Case, Analyze, Decision, execution, source edits or Git push are authorized here.
The user's Outlook and Teams screenshots independently confirm both original
source links open the intended demo messages.

- [x] All validation checks pass.
  - [x] 1. AZD Installation.
  - [x] 2. Schema Validation.
  - [x] 3. Environment Setup.
  - [x] 4. Authentication Check.
  - [x] 5. Subscription/Location Check.
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview.
  - [x] 8. Build Verification.
  - [x] 9. Docker Build Context Validation.
  - [x] 10. Package Validation.
  - [x] 11. Azure Policy Validation.
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static role verification.

At 14:51 UTC, fresh 58 frontend tests and production TypeScript/Vite build passed.
`uv build` passed after permitting access to the existing local cache;
`git diff --check` passed. AZD 1.30.0 authenticated as Will, default named
environment `supply-response-personal`, confirmed Azure Dev tenant/subscription
and East US 2. Exact read-only preflight passed. Named `azd provision --preview
--no-prompt` accepted azure.yaml/Bicep with no new resources, only existing app
and Insights reconciliation; named `azd package` passed. Dockerfile/ignore rules
and both lockfiles verified. No Aspire, schema migration or grant applies.
Policy assignment inventory reviewed; no preview denial. Static roles and live
pre-deploy assignments match exact-resource AcrPull, Key Vault Secrets User and
Foundry User. One API-tagged app; existing shared environment Succeeded.

Release `51d6147`, ACR build `ch1a` (Succeeded at 14:55:24 UTC), activated
`ca-sr-demo--0000020` with immutable digest
`a08730d8a23fa2d9349e65423d7153679cfbf1098cfc0fd12f71843ec25ca0c4`.
The first apply stopped before mutation because sandbox permissions prevented
the required local commit; after an approved local commit, the guarded retry
completed. Existing-health checks retried transient timeouts without bypass.
Revision20 is sole active/latest-ready Healthy/Running, provisioning Succeeded,
100% traffic, unchanged identity and scale 0–2; the exact three scoped roles
remain unchanged. `azd show` confirms the same named environment; ingress confirms
the existing demo URL. Public HTML and `/assets/index-D0eOUMQz.js` returned HTTP
200; both new labels were found in the published bundle. No browser refresh or
case mutation was needed. The broader post-deploy `--smoke` request was rejected
by automatic approval review as beyond the established label-only scope and was
not retried; verification used permitted deployment metadata and public static
assets instead. No new delegated analysis or source-service acceptance is claimed.

## Validation Proof — Teams citation preservation (2026-09-08)

User explicitly approved deployment to the existing demo and one fresh Alex
analysis to verify both source citations. No Decision approval/execution, source
edits, identity/role/billing changes, new resources, or Git push. Preserve the
existing Azure Dev / East US2 named environment and immutable saved analyses.
The reviewed patch only preserves GUID-valued Teams tenant routing parameters
in server-classified citation fields on optional-explanation failure.

- [x] All validation checks pass.
  - [x] 1. AZD Installation.
  - [x] 2. Schema Validation.
  - [x] 3. Environment Setup.
  - [x] 4. Authentication Check.
  - [x] 5. Subscription/Location Check.
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview.
  - [x] 8. Build Verification.
  - [x] 9. Docker Build Context Validation.
  - [x] 10. Package Validation.
  - [x] 11. Azure Policy Validation.
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static role verification.

Previous-turn regression reproduced literal `[REDACTED]` in both citation fields.
Review approved the correction; fresh release checks and live verification follow.

At13:17 UTC, fresh full `.venv/bin/pytest -q -ra` passed with14 expected live
skips and the existing Starlette/httpx warning. `npm test -- --run` passed52 tests;
`npm run build`, `uv build`, scoped Ruff and Pyright passed. AZD1.30.0 authentication
is Will; default named environment, Azure Dev tenant/subscription and East US2
match. `scripts/preflight_personal_tenant.sh` passed read-only exact bindings.
`azd provision --environment supply-response-personal --preview --no-prompt`
accepted azure.yaml/Bicep and proposed no new resources; existing Container App
and Insights metadata reconciliation only. Named `azd package` passed.
Dockerfile, ignore rules and both locked dependency inputs checked. No Aspire,
schema migration or grant change applies. Policy inventory reviewed with no
preview denial. Static role definitions match the exact three scoped live roles
(ACR pull, vault secrets read, Foundry User); identity/scale0–2 unchanged.
Tag lookup corrected to a supported resource-group query and confirmed one API
target. Shared environment Succeeded. Revision18 digest retained above as rollback.

Release commit c010d5d, ACR build ch19 Succeeded, immutable digest
29a68454fc082c7299da977d5007b5a2b7972f048c1e337cd6b3439c0b47ede5
activated revision19. Existing-health gate passed after two transient timeouts,
without bypass or placeholder replacement.

Post-deploy `--smoke` passed live Fabric/Foundry readiness. `azd show` confirms
the named environment; ingress confirms the same HTTPS demo. Revision19 is sole
active/latest-ready Healthy/Running with100% traffic, unchanged identity, exact
three scoped roles and scale0–2. One new showcase Case was created through the
normal signed-in browser and one Analyze clicked. At approximately 13:25 UTC,
Case `RL-CASE-be7746d5-42eb-4930-b8cc-501328853318` completed analysis with five
Open citation links (three Power BI, one Teams, one Outlook). Both Microsoft 365
link targets match the expected source URLs. The missing-citation warning is gone
and Approve combined response is enabled; $24,750 and 2,300 uncovered units are
displayed. No source links were opened, Decision approved, or actions executed.
The verified Case remains open in the browser. No second Analyze or Git push.


## Validation Proof — structured discovery (2026-09-08)

User approved the documented bounded Work IQ entity-query approach and supplier
binding reconciliation. No new resources, roles, billing, source edits, direct
Graph client or Git push. Preserve existing Alex OBO, source validators and
timeouts. Exact scope: docs/superpowers/specs/2026-09-08-workiq-structured-discovery-design.md.

- [x] All validation checks pass.
  - [x] 1. AZD Installation.
  - [x] 2. Schema Validation.
  - [x] 3. Environment Setup.
  - [x] 4. Authentication Check.
  - [x] 5. Subscription/Location Check.
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview.
  - [x] 8. Build Verification.
  - [x] 9. Docker Build Context Validation.
  - [x] 10. Package Validation.
  - [x] 11. Azure Policy Validation.
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static role verification.

Baseline: existing 84 discovery/evidence tests passed before implementation.
Before 05:59 UTC, fresh AZD1.30.0, Will authentication, default named environment,
Azure Dev tenant/subscription/East US2 checks passed. Read-only preflight (including
reconciled binding receipt), named provision preview and azd package passed.
Preview accepted azure.yaml and has no new resources: existing Container App
and Insights metadata reconciliation only. Dockerfile/ignore and locked inputs
checked; no Aspire or schema/grant change applies. Policy inventory has no new
denials. Static roles match the exact three existing scoped live roles for the
unchanged identity. Revision17 remains Healthy/Running, same scale0–2/traffic.
Frontend51 tests and production build passed; Python package passed. Full Python
regression passed after allowing the existing validator's public NuGet restore
(first restricted run failed only four dependency-download cases). Expected14
live skips and existing Starlette/httpx warning remain. Independent review of
d581d43 identified duplicate/nonmatching malformed collection rejection gaps;
test-first correction and full scoped typing verification are in progress.
Correction0466aac rejects every malformed/duplicate ID before filtering; restored
actor, sanitizer and individual-fetch deadline tests. Independent re-review
approved with no findings (35 tests independently run), including the final
test-only Team/channel duplicate cases. At approximately06:05 UTC, final full
`.venv/bin/pytest -q -ra` exited0 with14 expected live skips and the existing
warning. `uv build` passed; scoped Pyright including all changed tests returned
0 errors. Controller49 focused tests and final22 structured tests passed; commit
hooks ran Ruff clean. No runtime changes since0466aac. Existing revision17 digest
and old supplier binding/receipt are retained as rollback inputs in ignored notes.
Normal application MCP/OBO acceptance remains a post-deployment gate.

Post-deploy result: release5fea43f, ACRch18, immutable digest
f05099e8170e50bca8e1774c45be91b58752ea8d0bac9605a1f82c33ac1ad760,
revision18 sole active/latest-ready Healthy/Running. Identity/exact three scoped
roles/scale0–2 unchanged. Smoke/readiness and supplier binding/receipt match pass.
`azd show` and ingress confirm the existing environment/HTTPS URL. One normal
Alex Analyze at approximately06:11 UTC displayed both Work IQ source bodies as
healthy, three Fabric evidence items and calculated options. Teams Open citation
link is absent; frontend citation gate disables approval/rejection. Source
discovery/read/validation is now verified in-app, but citation navigation and the
full Decision/execution journey are not. No second Analyze or Git push.

Generated: 2026-08-31; validation evidence updated 2026-09-07 UTC

## Validation Proof — confirmed answer-field correction

Scope: normalize the observed `answer` and documented `response` aliases at the
MCP boundary, preserving metadata and requiring bounded nonempty strings and a
valid conversation ID. If both aliases occur they must match exactly; invalid
explicit values cannot fall back. Discovery, fetch, identity/source validation,
prompts, requests and fixed-state diagnostics are unchanged. No new resources,
permissions, billing, source edits, automatic retry or Git push.

- [x] All validation checks pass.
  - [x] 1. AZD Installation.
  - [x] 2. Schema Validation.
  - [x] 3. Environment Setup.
  - [x] 4. Authentication Check.
  - [x] 5. Subscription/Location Check.
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview.
  - [x] 8. Build Verification.
  - [x] 9. Docker Build Context Validation.
  - [x] 10. Package Validation.
  - [x] 11. Azure Policy Validation.
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static role verification.

RED reproduced22 failures with the observed answer-field fixtures, including
the authenticated normal Analyze and both source paths. GREEN:112 focused
transport/shape/evidence/live-wiring tests pass; scoped Ruff/Pyright pass.
Full `uv run pytest -q` and `uv build` passed, with expected live skips and the
existing Starlette/httpx warning. Initial sandbox cache access was denied before
execution; approved cache access allowed the complete run. All51 web tests and
179-module build passed. Independent review found no actionable issues and
independently passed112 focused tests. At02:47 UTC on September8, fresh AZD1.30.0,
Will authentication, default named environment and Azure Dev tenant/subscription
checks passed. Read-only preflight, named provision preview (20seconds, no new
resources) and azd package passed; current azure.yaml accepted. Policy inventory
unchanged with no preview denial. Dockerfile/ignore and locked inputs checked;
static registry/vault/Foundry assignments match exact live three-role inventory.
Baseline revision16, sole API target, existing shared environment/East US2,
identity and scale0–2 verified. Retain revision16 digest for rollback. No Aspire,
new schema or grant applies. Normal live acceptance remains unverified.

Deployment commit `5566822`, successful ACR build `ch17`, immutable digest
`f9bb03126cb284537dee9353b0c9d699938df0315d57572df8869d8ffe2d0d0a`
activated `ca-sr-demo--0000017`. Existing-health gate passed after transient
timeouts without bypass. Post-deploy smoke, exact three-role/identity/scale checks,
sole active/latest-ready Healthy/Running revision and100% traffic passed.
`azd show` confirms the named environment; ingress confirms the same HTTPS URL.
At approximately02:54 UTC on September8, one normal Alex Analyze on the existing
Case returned supplier/discovery503. Both safe source records are
step=parse_locations, reason=no_locations, parsed=0, scoped=-1, matched=-1,
http_status=0. Thus ask field validation now passes, but no supported location is
extracted. No fetch or accepted evidence occurred. Missing links versus unsupported
link format remains unresolved. No body capture, second attempt or Git push.

## Validation Proof — ask answer-field diagnostics

- [x] All validation checks pass.
  - [x] 1. AZD Installation.
  - [x] 2. Schema Validation.
  - [x] 3. Environment Setup.
  - [x] 4. Authentication Check.
  - [x] 5. Subscription/Location Check.
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview.
  - [x] 8. Build Verification.
  - [x] 9. Docker Build Context Validation.
  - [x] 10. Package Validation.
  - [x] 11. Azure Policy Validation.
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static role verification.

User approved checking which answer field differs without message-body capture.
Success: fixed status labels for literal response/conversationId/answer/error
fields, then one normal existing-Case Alex Analyze and a supported conclusion.
No raw values, unknown keys, lengths, credentials, permission changes, Graph,
new resources, automatic analysis retry, Git push or speculative parser fix.

Offline RED:16 real MCP-wrapper cases failed because statuses were absent.
GREEN:95 focused transport/evidence/live-wiring/shape tests pass; scoped Ruff and
Pyright pass. Full `uv run pytest -q` and `uv build` passed; expected live skips
and existing Starlette/httpx warning only. All51 frontend tests and179-module
build passed. Independent review found no actionable issues and independently
passed50 shape/transport tests. At approximately02:23 UTC on September8,
AZD1.30.0/auth/default-environment and Azure account checks confirmed the existing
Will User, Azure Dev subscription/tenant and named environment. Read-only preflight,
named provision preview and package passed. Preview has no new resources, only
existing Container App and Insights metadata reconciliation. Policy inventory is
unchanged. Dockerfile/ignore/locked inputs and static role modules were checked.
Live baseline revision15, identity, scale0–2 and exact three scoped roles match.
The current Microsoft Learn reference documents response/conversationId, whereas
the Microsoft iq-series lab describes answer/conversationId in structured content.
These are hypotheses, not proof of the actual live fields. This diagnostic keeps
the rejection contract unchanged and records field states only on that rejection.

Deployment `664b67f`, ACR build `ch16`, immutable digest
`042a556dcf974e5fb8d045709d068ea92556c4c8263b0eba7fd03069652aa2a9`
is sole active/latest-ready revision `ca-sr-demo--0000016`, Healthy/Running with
100% traffic. Post-deploy smoke, environment/endpoint checks and exact three-role
verification passed; identity and scale0–2 are unchanged. At approximately02:33
UTC on September8, the result of the one normal existing-Case Alex Analyze was
confirmed: supplier/discovery503. Both source results have response=missing,
conversation_id=valid, answer=valid, error=missing. The adapter requires response
and rejects the result before locator parsing. No source body was captured or
evidence accepted. No retry, parser fix or Git push. See the deployment result.

## Validation Proof — discovery-substep diagnostics

User approved failure-only safe substep statuses and one further normal Alex
Analyze. Implementation `0d5cb0a`: no endpoint, prompt, retry, validation, public
error or permissions change. Only fixed reason names, substeps, bounded numeric
HTTP status and locator counts are logged. No source text, IDs or credentials.

- [x] All validation checks pass.
  - [x] 1. AZD Installation.
  - [x] 2. Schema Validation.
  - [x] 3. Environment Setup.
  - [x] 4. Authentication Check.
  - [x] 5. Subscription/Location Check.
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview.
  - [x] 8. Build Verification.
  - [x] 9. Docker Build Context Validation.
  - [x] 10. Package Validation.
  - [x] 11. Azure Policy Validation.
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static least-privilege role verification.

RED: seven simulated upstream failures produced no diagnostic records. GREEN:
52 focused evidence/live-wiring/diagnostic tests passed, including sanitization,
success, both sources and cancellation/timeout behavior. Scoped Ruff/Pyright and
uv package build passed. Independent review found no findings. Web regression
passed all 51 tests; the production build passed (179 modules).
The full Python run caught ten diagnostic capture failures: importing fabric-cicd
sets the root logger to ERROR. A test-only warning-capture fixture now isolates
these assertions, matching the other diagnostic tests. Fabric compatibility plus
all 29 evidence tests pass together; Ruff/Pyright pass. The fixture was separately
reviewed with no findings. Full `uv run pytest -q` rerun exited 0, with expected
live-test skips and the existing Starlette/httpx warning only; no production
behavior was changed to address test isolation.

2026-09-08 02:04 UTC: current Azure account is the approved Will User in Azure
Dev and the recorded tenant. AZD 1.30.0/auth/default environment checks passed.
Policy inventory remains the existing security benchmark/Defender assignments.
Named-environment preflight, `azd provision --preview --no-prompt --environment
supply-response-personal` and `azd package --no-prompt --environment
supply-response-personal` passed: no new resources; existing Container App and
Application Insights metadata reconciliation only. Existing Dockerfile/ignore,
locked inputs and registry/vault/Foundry role modules are unchanged. Live baseline
is revision14, same identity and exactly the existing three scoped roles.
Deployment `e145843` completed as ACR build `ch15`, immutable digest
`d9341d15de084ff516d7d125218bf821965cd3e095adb519a98e760eac921c9a`.
Revision15 is sole active/latest-ready, Healthy/Running, 100% traffic. Identity,
exact three scoped roles and scale0–2 remain unchanged. Post-deploy `--smoke`
passed live Fabric/Foundry readiness. `azd show` confirms the existing environment;
this infrastructure-only project has no AZD service entries, so the endpoint
was independently verified from the Container App's ingress configuration.

One normal Alex Analyze on the existing Case at approximately02:14 UTC returned
the same public supplier/discovery503. Both safe records show `step=ask`,
`reason=discovery_shape`, status0 and parsed/scoped/matched counts-1. OBO and
initialization completed; the decoded ask result failed expected response and/or
conversationId string constraints before locator parsing. Which field/type/bound
failed is not established. No message fetch or accepted evidence is claimed.
No retry or Git push. See the updated deployment result for the precise next gate.

## Validation Proof — production Work IQ discovery/evidence integration

Deployment result: `aa67991` built as ACR `ch14`, immutable image digest
`5603a03bd1def6b52f692c252cf3344c63036cf8cc69b4cd222df59bfed4894d`.
Revision `ca-sr-demo--0000014` is sole active/latest-ready, Healthy/Running with
100% traffic. Exact identity/three roles and scale0–2 are unchanged. Live smoke
and health/schema12 passed. One Alex Analyze around23:40Z failed with supplier
`discovery`; both source paths logged only sanitized failures. No successful
analysis/citation/Foundry outcome is claimed. No retry or Git push. See
`docs/deployment/workiq-discovery-integration-result.md` for the precise boundary.

The user approved the written discovery/evidence spec and implementation plan,
including deployment to the existing app and one normal Alex live analysis.
No new resources, roles, permissions, billing or source edits; no Git push.
All three implementation tasks are independently reviewed. Final whole-change
review of 91c1681..1f6afc3 approved deployment with no Critical/Important findings.

- [x] All validation checks pass for the current integration.
  - [x] 1. AZD Installation.
  - [x] 2. Schema Validation.
  - [x] 3. Environment Setup.
  - [x] 4. Authentication Check.
  - [x] 5. Subscription/Location Check.
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview.
  - [x] 8. Build Verification.
  - [x] 9. Docker Build Context Validation.
  - [x] 10. Package Validation.
  - [x] 11. Azure Policy Validation.
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).
  - [x] Static least-privilege role-assignment verification.

At 22:51 UTC on 2026-09-07, `azd version` confirmed 1.30.0, `azd auth login
--check-status` confirmed Will, and `azd env list --output json` confirmed the
existing default `supply-response-personal` environment. `az account show`
matched the approved Azure Dev subscription/tenant and interactive User identity.
The CLI advertises an available update; no toolchain change is needed or applied.
Read-only policy inventory still contains the recorded Microsoft security
benchmark/Defender assignments; final current-template preview remains pending.
Baseline Azure inspection confirms revision `ca-sr-demo--0000013` remains the
only active/latest-ready revision, Healthy (currently scaled to zero), 100%
traffic; scale remains 0–2 and the exact managed identity is unchanged. Retained
rollback image digest: `109d0f6c58eaeb0e537bd3432b8900fc75164203e09b9ab120c81edf87afc7e4`.
Read-only app role inventory confirms exactly three existing assignments:
`AcrPull` at the shared registry, `Key Vault Secrets User` at the project vault,
and `Foundry User` at the existing project. No broader runtime role is present.
Docker context inspection confirms locked Node/Python inputs, nonroot runtime,
required public Entra build arguments and exclusion of local environment,
scratch, test, credential and browser-state files. No Dockerfile change.
Controller release verification at e773dac: full `uv run pytest -q` exited 0,
with expected live-test skips and the existing Starlette/httpx warning; `uv build`
passed. `npm --prefix apps/web test` passed all 51 tests in five files and
`npm --prefix apps/web run build` passed the 179-module production build.
The four nonsecret bindings were verified against the existing corpus/directory
metadata; the ignored environment now has the exact v2 receipt from the reviewed
shared recipe. `bash scripts/preflight_personal_tenant.sh` passed. Named-environment
`azd provision --preview --no-prompt --environment supply-response-personal`
passed in 20 seconds: no new resources, only existing Container App settings/image
and Application Insights metadata reconciliation. `azd package --no-prompt
--environment supply-response-personal` passed; azure.yaml was accepted. No
policy blocked preview. Static registry/vault/Foundry modules were re-read and
match the three exact live role assignments. No Aspire services apply.
Final receipt enforcement fix `1f6afc3` rejects invalid receipts before any live
resource construction. Its independent re-review passed; the controller reran
83 covering wiring/live/deployment tests and `uv build`, both passed. Task-scoped
Ruff/Pyright and offline Bicep/shell checks passed. Whole-change review then
approved deployment without additional findings. The pre-existing Starlette
warning is unchanged; no claim of globally clean unrelated static debt is made.
Current validation completed on 2026-09-07 at approximately 23:35 UTC. Normal
Alex Analyze and its live discovery/evidence/citation outcome remain unverified.
Prior deployment evidence below is historical, not a substitute for this gate.

## Validation Proof — MCP probe cleanup, 2026-09-07 UTC

The single deployed Alex-authenticated Work IQ MCP fetch succeeded with HTTP 200
and every safe validation flag true. Same single replica and zero restarts before
and after; no retry, Graph call, permissions or billing change. See
`docs/deployment/workiq-mcp-probe-result.md` for the sanitized outcome.

- [x] All validation checks pass for cleanup.
  - [x] 1. AZD Installation.
  - [x] 2. Schema Validation.
  - [x] 3. Environment Setup.
  - [x] 4. Authentication Check.
  - [x] 5. Subscription/Location Check.
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable).
  - [x] 7. Provision Preview.
  - [x] 8. Build Verification.
  - [x] 9. Docker Build Context Validation.
  - [x] 10. Package Validation.
  - [x] 11. Azure Policy Validation.
  - [x] 12. Aspire Post-Provisioning Checks (not applicable).

Nine temporary files removed; four runtime files restored exactly to c88bf2f.
Retirement regression failed before removal and passes afterward. Full Python
suite and uv build passed; 51 frontend tests and build passed. Scoped Ruff/Pyright
and diff check passed. Named-environment preflight, 20-second provision preview
and azd package passed; no new resources. Azure CLI/azd operator, subscription,
tenant and region unchanged. Azure policy inventory read; no blocking policy.
Static Bicep and live exact registry/vault/Foundry roles agree. Docker inputs and
sensitive-file exclusions unchanged; no Aspire services. Independent cleanup
review found the baseline SPA returns POST 405 for removed routes. The retirement
test now covers static assets, verifies GET 404 / POST 405 and absent OpenAPI;
all three focused tests pass. Independent re-review approved with no remaining
findings and confirmed all four runtime files exactly match c88bf2f.
Cleanup bc3f11a deployed via approved apply/smoke; ACR ch13 succeeded, revision13
sole active/latest/ready, Healthy/Running at 100% traffic. Probe revision12 is
inactive, Stopped and at zero traffic. Live retired-route GET404/POST405 and
OpenAPI absence verified. Health live Fabric SQL/schema12 and Fabric/Foundry
smoke passed; no delegated operation. Managed identity/exact roles unchanged;
azd show verified named environment. No normal analysis change or Git push.

## Validation Proof — temporary app-authenticated MCP probe, 2026-09-07 UTC

The approved scope is one Alex-only, fixed-source MCP fetch with the existing
application OBO credentials, followed by mandatory removal and cleanup deployment.
No Graph fallback, permissions, billing, schema, or ordinary analysis changes.
The UTC window remains disabled until implementation review and browser readiness.

- [x] All validation checks pass for the temporary probe.
  - [x] 1. AZD Installation: version 1.30.0.
  - [x] 2. Schema Validation: existing azure.yaml accepted by preview/package.
  - [x] 3. Environment Setup: existing supply-response-personal selected.
  - [x] 4. Authentication Check: Will verified in Azure CLI and azd.
  - [x] 5. Subscription/Location Check: Azure Dev, existing approved tenant/RG, East US 2.
  - [x] 6. Aspire Pre-Provisioning Checks: not an Aspire application.
  - [x] 7. Provision Preview: succeeded; no new resources, expected existing app metadata/image reconciliation.
  - [x] 8. Build Verification: full Python suite and uv build passed at 5fe3591; 53 frontend tests/build passed.
  - [x] 9. Docker Build Context Validation: locked Node/Python inputs, sensitive local files excluded, one Uvicorn worker.
  - [x] 10. Package Validation: azd package succeeded; ACR build remains deployment-time packaging.
  - [x] 11. Azure Policy Validation: assignments read; no policy blocked provisioning preview.
  - [x] 12. Aspire Post-Provisioning Checks: not applicable.

Read-only preflight passed; exact existing managed-identity registry/vault/Foundry
roles agree with static Bicep. No roles added. Current revision 11 retained.
Browser sign-in selected Alex's saved account and returned to the app without a
Case creation or retrieval. Baseline Python suite had four network-restricted
NuGet failures; all four passed when rerun with network access. Probe tests and
final build/review evidence will be recorded before changing status to Validated.

Final evidence: independent review approved 5fe3591 after correcting cancellation
cleanup, bounded/redacted OBO responses, exact Teams links and MCP/SSE validation.
43 focused tests passed; scoped Ruff/Pyright clean; full final Python suite and
uv build passed, with expected live-test skips and existing Starlette warning.
The optional diagnostic HTTP seam does not change normal OBO defaults and will
be reverted during cleanup. No source content was retrieved during validation.
Controller fixed activation at 2026-09-07 21:30:00Z through 22:00:00Z (30 minutes),
with one explicit Alex browser POST after revision/replica verification.

## Validation Proof — capture retirement, 2026-09-07 UTC

- The approved single response pair was inspected; destructive read returned
  `spent`. Both tasks reported source lookup unavailable for the exact opaque
  identifiers and supplied no usable facts/citations. No answer bodies were
  saved to files. A subsequent independent state check was console-rate-limited;
  no retry was made during its ten-minute backoff window.
- Removal is part of the original explicit approval. Scope is the temporary
  module, startup hook, client wrapper, capture-only tests and retired runbook.
  Existing evidence checks, structural diagnostics, infrastructure, identities,
  source bindings, billing and database schema are unchanged.
- The capture-absence regression failed before removal for the expected module
  presence assertion and passed afterward. Full `uv run pytest -q` and `uv build`
  passed, with expected skips and the existing Starlette/httpx warning. Scoped
  Ruff/Pyright passed; all 51 web tests and the 179-module web build passed.
- Independent read-only review found no issues and verified both runtime files
  match the pre-capture revision exactly. Capture-only files are deleted and the
  operator runbook is retired; only paraphrased findings remain.
- Fresh Will authentication, named-environment preflight, 20-second provision
  preview and azd package passed. No new resources; same approved subscription,
  tenant and East US 2. Azure policy inventory read; no policy blocked preview.
  Static Bicep role review and live exact registry/vault/Foundry role reads agree.
  Docker inputs remain locked, ignored local data excluded, no Aspire services.
- Unique API deployment target and revision 10/latest/ready identity confirmed.
  Initial resource-tag CLI query used an unsupported flag combination; corrected
  read-only query confirmed exactly one target. No setting change was needed.
- Cleanup commit `19cb18a` deployed through the approved apply/smoke workflow.
  Existing-health gate passed after two timeouts without bypass. Immutable ACR
  build succeeded; revision 11 is latest/ready, Healthy/Running, sole active
  revision with 100% traffic. Revision 10 is retired. Live Fabric/Foundry smoke
  and direct health passed (live Fabric SQL, schema 12); exact roles unchanged.
- Post-deployment console verification returned `No module named
  integrations.workiq.memory_capture`, confirming the module is absent from the
  running image. An initial quoted Python check hit console argument splitting;
  the simple module check provided the actual proof. No new retrieval occurred.
  Named environment verified with azd show. No Git push. Source lookup and
  evidence mapping remain unresolved; this deployment only retires diagnostics.

## Validation Proof — memory-only inspection, 2026-09-07 UTC

- User explicitly approved a temporary diagnostic deployment to inspect one
  supplier/Quality final-answer and citation pair in memory, excluding headers,
  tokens and saved response bodies. Removal after inspection is also approved.
  Existing tenant/subscription/East US 2 resources and main branch are retained.
- Default-disabled Linux abstract Unix socket, same-UID kernel peer check, one
  operator arm per process, one case/analysis pair after validated-Alex OBO,
  strict projection bounds, destructive read, automatic expiry and no public
  endpoint/log/file output. See `docs/deployment/workiq-memory-capture.md`.
- Twelve new tests pass, including the real HTTP/OBO-to-normalizer seam retaining
  the existing malformed-facts failure. Initial feature assertions failed before
  implementation. Full Python regression and package build passed; 51 web tests
  and the 179-module web build passed. Targeted 101-test Work IQ set and scoped
  Ruff/Pyright checks passed.
- Independent review identified a serialized-output retention bug. The Linux
  socket probe reproduced it before correction and passed afterward as UID 10001
  with a read-only filesystem and no network. Reviewer re-review approved.
- Fresh azd authentication confirms Will as operator. Named-environment preflight
  passed with current operator ID, approved tenant/subscription, East US 2,
  existing shared resources, exact Entra registrations, Fabric and Foundry.
  Two initial local invocations lacked required preflight environment selectors;
  those checks stopped before cloud mutation and passed with explicit selectors.
- `azd provision --preview --no-prompt --environment supply-response-personal`
  passed in 20 seconds; no new resources. `azd package` passed. Policy inventory
  was read; no policy blocked preview. No Aspire services. Docker inputs remain
  locked and infrastructure-only azure.yaml is unchanged.
- Static role review: unchanged exact registry AcrPull, vault Secrets User and
  project Azure AI User assignments. No new data-plane operation or role needed.
  Live revision 9 remains provisioned with the same managed identity.
- Final post-review full Python regression and package build passed. The
  azure-validate workflow reached UpdateStatus after all checks and proof.
  One API tag target and a healthy existing shared environment were confirmed.
- Commit `0ee6fae` deployed through the approved apply/smoke workflow. The
  existing-health gate passed after two timeouts; no bypass was used. ACR build
  succeeded and the new revision is Healthy/Running, latest/ready, at 100% traffic.
  Live Fabric/Foundry smoke and direct health passed (live Fabric SQL, schema 12).
  Exact registry/vault/Foundry roles and managed identity are unchanged.
- `azd show` verified the named environment; direct app reads verified the
  endpoint and immutable image (this project intentionally has no azd services).
  A state-only console check against the sole new replica returned `disabled`
  with a successful cluster status. No answer has been captured or inspected.
  Capture is deliberately unarmed until Alex is ready, to avoid losing the
  one-shot window to scale-to-zero or expiry. No Git push.

## Validation Proof — Work IQ response-shape diagnostic, 2026-09-07 UTC

- User approved a temporary, failure-only structural diagnostic after the live
  normalizer rejected completed Work IQ tasks. No response contents were captured.
- Commit `9680fb3` adds allowlisted keys, fixed JSON types, container counts and
  truncation only. Scalar values and unknown keys never enter the diagnostic.
  Limits: 128 shared nodes, 12 levels, two examples, 8,192 serialized characters,
  and one record per source kind per process. Parser and evidence rules unchanged.
- Targeted verification: 123 Work IQ tests passed; scoped Ruff and Pyright passed.
  Tests were observed failing before implementation and before the evidence-path
  priority correction. Task review requested exact safety-boundary regressions;
  four focused tests now pin the depth, shared nodes, examples and output fallback
  without changing production code. Task re-review and whole-change review
  approved with no remaining findings.
- By 16:28Z, full `uv run pytest -q` passed with expected skips and the existing
  Starlette/httpx deprecation warning; `uv build` produced both distributions.
  All 51 web tests and the 179-module production build passed.
- Fresh `azd auth login --check-status` and named-environment preflight passed.
  `azd provision --preview --no-prompt --environment supply-response-personal`
  passed in 20 seconds with no new resources; `azd package` passed. Azure policy
  assignments were read and no policy blocked preview. No Aspire services.
- Static review confirmed unchanged exact registry, vault and Foundry roles,
  locked Docker inputs and infrastructure-only azd configuration. Existing
  revision 8 remains Healthy at 100% traffic with the same managed identity.
- Reviewed commit `b1a62a0` deployed through the approved apply/smoke workflow.
  The existing revision passed its health gate after two startup timeouts; the
  workflow did not bypass the gate. At 16:40:04Z, the new revision was latest/ready,
  Healthy/Running with 100% traffic; the preceding revision had zero traffic.
  Fabric/Foundry readiness and direct `/health` passed (live Fabric SQL, schema 12).
  `azd show` and direct app reads confirmed the existing environment and endpoint.
  Identity and the exact registry/vault/Foundry role scopes are unchanged.
  Exact revision/image identifiers are in the ignored local environment record.
- One authenticated Alex observation remains pending: computer use reports the
  Mac is locked. No delegated operation was attempted. This is diagnostic
  visibility, not a mapping correction or proof of analysis success. No Git push.

## Validation Proof — Work IQ A2A task-envelope correction, 2026-09-07 UTC

- Following user activation of Work IQ usage billing, the 15:16:29Z Alex retry
  passed the HTTP/JSON-RPC checks but failed local task-status validation for
  both sources. The live response body was not captured or logged.
- Microsoft's A2A 1.0 quickstart puts the completed task at `result.task`, with
  its identifier at `task.id`. The client and normalizer incorrectly read a
  flattened result and `taskId`. The user approved correction and deployment.
- The exact-request regression and both fixture normalization/HTTP-to-evidence
  regressions failed before the production fix. All 71 targeted tests passed
  afterward, covering malformed/legacy tasks, limits and trust boundaries.
  Requests, OBO, public errors, authority rules and contextual text are unchanged.
- Independent read-only review found no actionable issues. Scoped Pyright passed.
  The commit hook required clearing pre-existing lint in touched files: native
  Python 3.12 ISO parsing replaces redundant Z substitution, and two auth tests
  now assert authentication/authorization exceptions instead of any exception.
  All 71 targeted tests, scoped Ruff (no exclusions) and Pyright then passed.
  Full regression/package rerun and cleanup re-review also passed.
- All 51 web tests and the 179-module production build passed. Full
  `uv run pytest -q` passed with expected skips and the existing Starlette/httpx
  warning; `uv build` produced both distributions.
- Fresh operator authentication and named-environment preflight matched the
  existing approved tenant/subscription/East US 2 and shared resources. Provision
  preview passed in 20 seconds with no new resources; azd package passed.
  Policy inventory was read and no policy blocked the preview. No Aspire services.
- Static RBAC review confirmed exact registry AcrPull, vault Secrets User and
  Foundry project access for the same app identity. Infrastructure, locked Docker
  inputs, secrets, roles, databases, source data and scaling are unchanged.
- Reviewed commit `848e686` deployed successfully. At 15:32:42Z the new immutable
  revision was latest/ready, Healthy/Running and serving 100% of traffic; the
  preceding revision had zero traffic. Live Fabric/Foundry readiness passed.
  `azd show` and direct app reads verified the existing environment and endpoint.
  The app identity and exact registry/vault/Foundry role scopes are unchanged.
  Exact revision and image identifiers are in the ignored local environment file.
- Alex's delegated analysis retry remains pending. A completed task must still
  satisfy the existing authoritative-evidence checks. No Git push was requested.

## Validation Proof — Work IQ HTTP-status diagnostic, 2026-09-07 UTC

- Alex's retry at 05:23:59Z passed OBO validation and reached the Work IQ HTTP
  response check. Both source calls failed with `WorkIQProtocolError`; the
  existing diagnostic did not retain the unsuccessful HTTP status. The user
  approved recording only that numeric status and deploying the diagnostic.
- `workiq_http_failed status=<integer>` is emitted before the existing exception.
  No authentication, request, response-validation, evidence, or public-error
  behavior changes. No headers, prompts, tokens, bodies or traces are logged.
- Eight diagnostic assertions failed before implementation. All 91 targeted
  tests passed afterward, including nine new HTTP tests. Scoped Ruff/Pyright
  passed; independent read-only review found no actionable issues.
- At approximately 05:32Z, full `uv run pytest -q` and `uv build` passed with
  expected skips and the existing Starlette/httpx warning. All 51 web tests and
  the 179-module production build passed. Locked Docker inputs are unchanged.
- Fresh azd authentication and named-environment preflight matched the approved
  tenant, subscription, East US 2 and existing shared resources. Provision
  preview passed in 19 seconds with no new resources; azd package passed.
  Policy inventory was read and no policy blocked the preview. No Aspire services.
- Static RBAC review confirmed the same app identity receives exact registry
  AcrPull, vault Secrets User and project Foundry access. No infrastructure,
  role, credential, database, source-data or scaling changes are in this patch.
- Commit `5ba33d9` deployed successfully; verified at 05:37:22Z. The new immutable
  revision is latest/ready, Healthy/Running and serves 100% of traffic. Live
  Fabric/Foundry readiness passed; identity and exact Azure roles are unchanged.
  `azd show` confirmed the existing environment; direct app reads verified the
  endpoint and image. Exact identifiers are retained in the ignored local record.
- The next delegated Alex retry is pending. This diagnostic is not a claim that
  live Work IQ retrieval or full analysis is fixed. No Git push was requested.

## Validation Proof — exact Work IQ scope fix, 2026-09-07 UTC

- Live response diagnostics showed a nonempty Bearer token with the exact
  resource-qualified scope requested by the app, but no unqualified scope.
  The app's short-name-only check rejected that response. User approved the
  narrow fix and redeployment; no tenant or credential changes are required.
- The validator now recognizes either complete, case-sensitive token:
  `WorkIQAgent.Ask` or `api://workiq.svc.cloud.microsoft/WorkIQAgent.Ask`.
  Actor provenance, requested scope, token presence and Bearer checks are
  unchanged. Lookalike scopes and other resource names remain rejected.
- Two regression tests reproduced the observed failure before the fix. All 82
  targeted tests then passed, including exact-scope, malformed-scope and invalid
  token cases. Scoped Ruff/Pyright are clean; independent review found no issues.
- Python package build, 51 web tests and the 179-module web build passed.
  Fresh preflight matched the approved environment and operator. Provision
  preview passed in 19 seconds without new resources; azd package passed.
  Policy inventory, static exact-resource roles, infrastructure and locked
  Docker context are unchanged. This is not an Aspire project.
- Full `uv run pytest -q` passed with expected skips and the existing
  Starlette/httpx warning. Reviewed commit `cbf34ba` deployed successfully; the
  new revision is latest/ready, Healthy/Running and serves 100% of traffic.
  Live readiness passed, and exact runtime roles and identity are unchanged.
  `azd show` and direct Container App reads verified the environment, endpoint,
  revision and immutable image. Exact identifiers are in the ignored local
  record. No live analysis success is claimed before Alex's next retry.

## Validation Proof — Work IQ response diagnostics, 2026-09-07 UTC

- The deployed diagnostics isolated both source retrieval failures to
  `WorkIQAuthenticationError` in OBO response validation. Alex's authenticated
  request reached analysis. Read-only checks found the API and Work IQ service
  principals enabled, exact tenant-wide `WorkIQAgent.Ask` consent present, and
  API credential metadata unexpired. These checks do not identify the rejected
  token-response detail or prove the deployed secret's validity.
- User approved a narrowly scoped follow-up diagnostic and redeployment. The
  token acceptance rule remains unchanged; logs contain only fixed outcomes,
  allowlisted OAuth/AAD codes and booleans. Unknown error values are no longer
  echoed in exception text. No permissions, secrets or source data are changed.
- Six diagnostic assertions failed before implementation. All 64 targeted tests
  then passed; scoped Ruff/Pyright are clean. Full `uv run pytest -q` passed with
  existing skips and the Starlette/httpx warning. Independent read-only review
  found no actionable issues.
- `uv build`, 51 web tests and web production build passed. Infrastructure,
  Docker context and locked dependencies are unchanged from the reviewed prior
  deployment. Exact-resource static RBAC remains unchanged; no Aspire services.
- Fresh named-environment preflight and operator authentication passed against
  the same approved tenant/subscription/East US 2 bindings. Provision preview
  passed in 19 seconds with no new resources, followed by successful azd package.
  Policy assignments remain unchanged and no policy blocked the preview.
- Reviewed commit `8bdada8` deployed successfully. The new revision is latest,
  ready, Healthy and Running with 100% traffic; the prior revision has zero
  traffic. Live Fabric/Foundry readiness passed. The app's system identity and
  exact registry/vault/Foundry role scopes remain unchanged.
- `azd show` verified the named environment and resource group; direct Container
  App reads verified the endpoint/revision and immutable image. Exact identifiers
  are in the ignored environment record. Alex's next analysis retry is pending;
  no successful Work IQ exchange or live Analysis is claimed.

## Validation Proof — safe analysis diagnostics, 2026-09-07 UTC

- User approved diagnostic logging and redeployment after the Alex browser
  request reached analysis and returned `LIVE_SOURCE_UNAVAILABLE` (503).
- Scope: stage and exception code metadata only; no payloads, credentials,
  exception messages or raw tracebacks. Public errors and live-mode behavior
  remain unchanged. No infrastructure, identity, source data or role changes.
- TDD: six missing-diagnostic assertions failed before implementation; all seven
  diagnostic tests and the 37-test live integration set then passed. Independent
  read-only code review found no actionable issues.
- Fresh full `uv run pytest -q` passed with expected skips and the existing
  Starlette/httpx warning. Scoped Ruff and Pyright passed with zero findings.
  `uv build`, 51 web tests and the 179-module web production build passed.
- The existing named azd environment and interactive operator passed preflight
  after supplying the script's required environment/operator bindings. Exact
  subscription, tenant, East US 2 and shared-service bindings remain unchanged.
- `azd provision --preview --no-prompt --environment supply-response-personal`
  passed in 20 seconds: no new resources, existing app/Insights updates only.
  `azd package` passed. Docker context retains locked dependencies and excludes
  private environment records. This is not an Aspire project.
- Current policy inventory and successful preview show no blocking denial.
  Static roles remain exact registry AcrPull, vault Secrets User, and project
  Foundry User assignments for the same Container App system identity.
- Deployment of reviewed commit `cac6f3a` completed. The new immutable revision
  is latest and ready; provision state is Succeeded. Live readiness and direct
  `/health` passed with Fabric SQL/schema 12. Existing app identity and exact
  AcrPull, vault Secrets User and Foundry User scopes remain unchanged.
- `azd show` confirmed the existing environment/resource group (the project
  intentionally has no azd services); direct Container App inspection verified
  its endpoint. Exact revision/image identifiers are in the ignored local record.
- Alex's same-Case retry is pending. Deployment success does not establish the
  underlying source failure's cause or a successful live analysis.

## Validation Proof — RL-001 loader update, 2026-09-06

This section supersedes older setup/pending-state notes below, which retain the
historical provisioning record.

- Final review fixed pyodbc timezone loss with an explicitly typed bind. A
  read-only live probe proved the original offset and instant are preserved.
  Final 24 loader tests and scoped checks passed; full regression passed after the
  production fix, and package rebuild passed.
- Approved loader runs returned `planned`, `inserted`, then `unchanged`. Both
  applies passed full stored-data and production-adapter readback.
- Approved deployment activated a ready immutable revision; live Fabric/Foundry
  smoke and exact runtime role verification passed. Identifiers are recorded in
  the ignored environment record.
- Browser Case creation succeeded. Analysis returned 401 `INVALID_ACCESS_TOKEN`;
  the application's Entra sign-in record identifies the administrator, not Alex.
  Public signing-key validation passed in the container. A fresh Alex session,
  delegated invocation, Decision/execution/outcomes, and report parity remain.

- Existing environment and interactive Azure authentication verified with
  `azd version`, `azd auth login --check-status`, and
  `scripts/preflight_personal_tenant.sh`. Exact tenant/subscription/region,
  shared resource, Foundry and Fabric bindings passed.
- `azd provision --preview --no-prompt --environment supply-response-personal`
  passed (20 seconds); no new resources, existing app and Insights updates only.
  `azd package --no-prompt --environment supply-response-personal` passed.
- Current policy-assignment inventory and successful preview showed no denial of
  the intended update. No Aspire application is present.
- `uv build` produced the source distribution and wheel; web tests (51) and Vite
  production build passed. Locked npm and Python inputs remain in Docker context;
  private environment files are excluded.
- Each loader task's full `uv run pytest -q` passed. Scoped Ruff/Pyright passed.
  Existing broad lint/type debt (82 Ruff findings and 47 Pyright errors in
  untouched files) and one third-party Starlette warning remain, and are not
  represented as clean global static checks.
- Static resource-specific managed-identity roles remain exact ACR Pull,
  vault Secrets User and Foundry Azure AI User; no role/schema changes are part
  of the loader update.
- Local read-only Fabric SQL access passed and confirmed zero source rows before
  the loader. `/health` returned live/Fabric SQL/schema version 12.

## 1. Project overview

**Goal:** Prepare the approved Supply Response demonstration for an Azure Developer CLI deployment into the personal `willmacdonald.com` tenant. The deployed workload is one HTTPS Azure Container App that serves both the FastAPI API and the built React application.

**Path:** Modernize an existing local application by adding Azure hosting artifacts. This is not a new application or an `azd init -t` template operation.

**Approved sources:**

- `docs/superpowers/plans/2026-08-30-supply-response-demo-implementation.md`, Task 18
- `docs/superpowers/specs/2026-08-30-supply-response-demo-contract-design.md`
- `CONTEXT.md`
- `docs/adr/`

**Authorization boundary:** This plan authorizes local preparation and read-only validation only. It does not authorize Azure resource creation, role assignment, Key Vault writes, image pushes, Entra changes, Fabric changes, Foundry publication, Power BI publication, Work IQ calls, Demo Corpus creation, or live browser execution. The first cloud mutation requires a separate explicit approval.

## 2. Confirmed requirements and Azure context

| Attribute | Value |
|---|---|
| Classification | Proof of concept / personal-tenant demonstration |
| Scale | Small; one operator-facing demo workload, `maxReplicas=2` |
| Budget | Cost-optimized |
| Subscription | Azure Dev (immutable ID confirmed separately; deployment-local only) — confirmed 2026-08-31 |
| Location | East US 2 (`eastus2`) — confirmed 2026-08-31 |
| Tenant | `willmacdonald.com` (immutable ID confirmed separately; deployment-local only) — confirmed 2026-08-31 |
| Data | Fictional Demo Corpus only; no customer, production, or real-person content |
| Availability | Demo availability, not a production SLA |
| Compliance | Same-tenant fail-closed preflight; immutable provenance; no external operational actions |

East US 2 supports the selected generally available services. Fabric, Power BI, Work IQ, Entra, and the existing Foundry project are external prerequisites and are not provisioned by this Bicep deployment.

### Policy constraints

The subscription currently has Microsoft cloud security benchmark and Defender auto-provisioning policy initiatives assigned. No discovered assignment specifies an allowed-region, required-tag, resource-type, or SKU denial. Validation must still compile the final template and use an Azure what-if/read-only policy evaluation before deployment because initiative effects can change.

## 3. Components detected

| Component | Type | Technology | Path |
|---|---|---|---|
| Supply Response API | API and runtime progression worker | Python 3.12, FastAPI, Uvicorn, SQLAlchemy/pyodbc | `apps/api`, `services`, `integrations`, `agents`, `data` |
| Supply Response Web | SPA | React, TypeScript, Vite, MSAL | `apps/web` |
| Fabric integration | External operational/analytics data adapter | Fabric SQL, pyodbc, SQL scripts, Power BI project | `integrations/fabric`, `fabric` |
| Work IQ integration | External delegated evidence adapter | Microsoft 365 Work IQ A2A, OBO | `integrations/workiq` |
| Foundry agents | External pinned agent runtime | Microsoft Agent Framework / Foundry | `agents`, `scripts/publish_foundry_agents.py` |
| Persistence | Portable store | Fabric SQL in live mode; SQLite only in fallback mode | `services/persistence`, `migrations` |

### Existing deployment state

| Item | State before Task 18 |
|---|---|
| `azure.yaml` | Absent |
| Application Bicep | Absent; only Entra manifests/scripts exist under `infra/entra` |
| Production Dockerfile | Absent |
| API static hosting | Absent; required for the approved single-container architecture |
| Azure Developer CLI defaults | Subscription and location already match the confirmed target; no azd project/environment exists |

## 4. Recipe selection

**Selected:** Azure Developer CLI with Bicep (`azd` + Bicep).

**Rationale:** The approved implementation plan already calls for `azure.yaml`, modular Bicep, one production container image, and a Container Apps deployment. The recipe provides repeatable environment values and validation while keeping infrastructure declarative. No template initialization will be run in this non-empty repository.

## 5. Architecture

**Stack:** Containers on Azure Container Apps.

| Component | Azure service / dependency | Configuration |
|---|---|---|
| React + FastAPI workload | Existing `shared-services-env` Consumption environment | One external HTTPS app; insecure HTTP disabled; target port 8000; system-assigned identity; `maxReplicas=2` |
| Container image | Existing `wkmsharedservicesacr` Standard registry | Managed-identity pull through `AcrPull`; never use or expose the registry's existing admin credentials; one multi-stage production image |
| Runtime secrets | New project-specific Azure Key Vault Standard | RBAC authorization; Container App Key Vault references; no confidential Bicep outputs or plain environment-variable values |
| Logs and traces | Existing `shared-services-logs` plus a new workspace-based Application Insights component | Application-level sampling and bounded verbosity; connection string provided as nonsecret runtime configuration |
| Foundry | Existing project in the confirmed tenant | Existing resource ID parameter; least-privilege runtime role assignment only after approval |
| Fabric SQL | Existing `SupplyResponseDemo` SQL Database in the dedicated `Supply Response Demo` workspace | Exact workspace/database bindings are verified; schema version 12, SQL authentication, idempotent double-application, and health are live-validated; the future Container App managed-identity database grant remains an explicit approval-gated deployment step and is not created by Bicep |
| Work IQ | Existing tenant capability | Confidential API client secret stored in Key Vault; OBO only after an authenticated Alex request |
| Entra web/API apps | Existing or separately provisioned tenant registrations | IDs are environment-specific configuration; client secret resides only in Key Vault |
| Power BI | Published source-controlled Fabric-backed report | Canonical report URL and receipt are stored only in the ignored deployment environment; populated Decision-ID parity remains a post-deployment gate |

### Runtime behavior

- A Node build stage builds `apps/web/dist`.
- The Container App name is an explicit 2–32-character deployment binding with no consecutive hyphens, independent of the azd environment name; this keeps resource naming valid and the redirect stable.
- A Python 3.12 runtime stage installs ODBC Driver 18 and locked Python dependencies, copies the SPA into `apps/api/static`, and runs as a nonroot user.
- FastAPI registers `/api` and `/health` routes before static SPA handling. A focused application change and tests will prove API routes are never shadowed and SPA navigation resolves correctly.
- The Uvicorn command is `uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000 --proxy-headers`.
- Normal cost-control parameters use `minReplicas=0`; the rehearsal/showcase parameter file uses `minReplicas=1` for a bounded demo window.
- Live mode remains fail-closed. It never substitutes SQLite, synthetic evidence, or local agents after a live dependency failure.

### Security and identity

- The personal-tenant workflow requires an interactive Azure CLI User login and rejects service-principal operators. It checks the active tenant, subscription, ARM-token operator `oid`/`tid`, Graph-backed exact Entra application reads, Foundry resource, and Fabric workspace/database before mutation.
- Scripts compare full immutable IDs but print only redacted IDs.
- The Container App uses a system-assigned managed identity for ACR pull, Key Vault secret retrieval, Foundry access, and Fabric SQL authentication.
- Confidential settings are Key Vault references. Client secrets, bearer tokens, Fabric connection strings, and browser storage state are never Bicep parameters, outputs, image layers, logs, or ordinary environment-variable values. Successful bearer-token stdout is deleted immediately after in-memory parsing. After Bicep completes a true bootstrap, the script creates one deterministic exact-scope operator Secrets Officer assignment, waits for data-plane access, seeds only when no version exists, and removes the assignment before continuing. Bicep and placeholder restores cannot recreate it. Rotation is a separate dry-run-by-default, approval-gated procedure. Before secret access it binds the confirmed canonical Container App ID, system identity, exact Key Vault secret reference, derived ingress origin, and sole active latest-ready revision; the deployed live Playwright gate then verifies Work IQ/OBO.
- Actual UPNs and Entra object IDs remain deployment-specific; domain history uses stable fictional persona IDs.
- Key Vault uses RBAC authorization, soft delete, and purge protection. This deployment never uses ACR admin access.
- The existing shared registry currently has its admin account enabled for other workloads. This deployment does not change that shared setting, does not read its admin credentials, and authenticates exclusively through managed identity. Disabling the shared admin account is a separate hardening decision because it could affect existing applications.
- Public Container App ingress is HTTPS-only. The POC does not add a VNet/private endpoints; that is a documented nonproduction tradeoff.
- The deploy script is fail-closed and requires an explicit apply flag plus exact subscription, tenant, region, and resource-group confirmation. Its default mode is validation/dry-run.
- Rotation bindings and deployment health contracts use explicit Python condition checks with `SystemExit(1)`; they do not use optimization-removable runtime assertions. Regression tests execute the wrong-binding and unhealthy-runtime paths with `PYTHONOPTIMIZE=1`.
- Deployment image lookup tags use the Git revision plus a digest of the four public Entra bundle values, so a configuration change cannot silently reuse the prior tag; Bicep receives the resolved immutable ACR manifest digest. Raw identifier-bearing command diagnostics stay in owner-only temporary storage and only categorical, fail-closed summaries reach the console.
- No script automates tenant consent or sends messages, modifies orders, creates commitments, or performs other external business actions.

### Cost controls

- Reuse the existing Consumption environment, Standard ACR, and Log Analytics workspace; Task 18 adds no new fixed-price registry or environment.
- Container Apps scales to zero outside rehearsal/showcase windows.
- A project-specific Key Vault Standard has no base monthly charge and incurs only low-volume operation charges.
- Application Insights uses sampling and bounded log verbosity against the existing pay-as-you-go workspace.
- A maximum of two Container App replicas.
- The deployment documentation includes an explicit command to restore `minReplicas=0` after a demo; it does not delete resources automatically.
- Expected incremental Task 18 baseline is approximately $0–$3/month at demo volume, excluding Fabric, Power BI, Foundry model, and Work IQ charges. Leaving one 0.5-vCPU/1-GiB replica continuously active could instead add roughly $39/month before shared free grants.

## 6. Provisioning-limit checklist

Read-only checks were performed on 2026-08-31 for the confirmed subscription and East US 2. The quota extension version was `1.0.0`.

| Resource type / limit | Add | Current | Total after deployment | Limit / capacity | Source and result |
|---|---:|---:|---:|---:|---|
| `Microsoft.Resources/resourceGroups` | 1 | 10 | 11 | 980/subscription | Azure CLI count + Microsoft ARM limits; healthy |
| `Microsoft.App/managedEnvironments` | 0 | 5 | 5 | 50/region | Reuse `shared-services-env`; `az quota` `ManagedEnvironmentCount`; healthy |
| `Microsoft.App/containerApps` in `shared-services-env` | 1 | 4 | 5 | 500/environment | Azure Resource Graph count + Azure Container Apps documented resource limit; healthy |
| `Microsoft.ContainerRegistry/registries` | 0 | 3 | 3 | Existing Standard registry includes 100 GiB | Reuse `wkmsharedservicesacr`; no additional registry unit; demo image is expected to remain within included storage |
| `Microsoft.KeyVault/vaults` Standard | 1 | 2 | 3 | No vault-count restriction; 4,000 other transactions/10 seconds per vault | Azure CLI count + Microsoft Key Vault limits; demo usage is negligible |
| `Microsoft.OperationalInsights/workspaces` pay-as-you-go | 0 | 5 | 5 | No workspace-count limit for nonlegacy tiers | Reuse `shared-services-logs`; healthy |
| `Microsoft.Insights/components` workspace-based | 1 | 0 | 1 | No project-specific ingestion cap is configured | Azure CLI count + Microsoft Azure Monitor limits; application sampling and bounded verbosity control demo telemetry without claiming a workspace cap |

**Capacity status:** All planned resources are within applicable quotas and documented service limits. No quota increase is required.

## 7. Files and scope

| File | Purpose | Status |
|---|---|---|
| `.azure/deployment-plan.md` | Deployment source of truth | Ready for validation |
| `Dockerfile`, `.dockerignore` | Reproducible nonroot production image | Contract-tested; tenant-exact public-dependency rebuild and local fallback smoke test passed |
| `azure.yaml` | Infrastructure-only azd project definition; image build stays in the approved argument-aware script | Complete |
| `infra/main.bicep`, `infra/main.parameters.json` | Subscription target and azd-compatible environment parameters | Complete; compiles locally |
| `infra/modules/registry.bicep` | Reference the existing ACR and grant managed-identity `AcrPull` without admin credentials | Complete |
| `infra/modules/container-apps.bicep` | Reference the existing environment; create the HTTPS app, identity, scaling, and bootstrap configuration | Complete |
| `infra/modules/key-vault.bicep` | RBAC-enabled protected vault | Complete |
| `infra/modules/monitoring.bicep` | Reference existing Log Analytics and create workspace-based Application Insights | Complete |
| `infra/modules/foundry-access.bicep` | Approval-gated least-privilege Foundry role assignment | Complete; not applied |
| `scripts/preflight_personal_tenant.sh` | Read-only same-tenant and prerequisite checks | Complete; syntax-only validation performed |
| `scripts/deploy_personal_tenant.sh` | Explicit, restart-safe approval-gated deployment orchestration | Complete; syntax-only validation performed, never applied |
| `apps/api/app/main.py` and focused tests | Serve the built SPA without shadowing API/health routes | Complete |
| `tests/deployment/test_infrastructure.py` | Static, production-bundle, runbook, and compiled-template security/architecture contract | Complete; current count recorded in local proof |
| `docs/deployment/personal-tenant.md` | Exact preparation, approval, deployment, rollback, and cost steps | Complete |

## 8. Research summary

- **Container Apps:** Reuse the existing public Consumption workload-profile environment. Use one system-assigned identity, HTTPS-only ingress, explicit startup/liveness/readiness probes, 0.5 vCPU/1 GiB, HTTP scaling, and `minReplicas=0` except during a bounded demo window.
- **Two-phase identity binding:** A system-assigned identity does not exist until the Container App is created. A first deployment therefore uses a public Microsoft placeholder on its native port 80 with no custom probes and without Key Vault or private-registry configuration. An upgrade first proves the existing non-placeholder revision is healthy and never switches it back to bootstrap. After exact-scope RBAC propagation, the approval-gated workflow builds the private image and runs Bicep in final mode: managed-identity ACR and Key Vault bindings, target port 8000, and all three `/health` probes are established together. This avoids circular dependencies and never uses registry admin credentials.
- **Key Vault:** Create a dedicated Standard RBAC vault with soft delete and purge protection. The Container App receives only Secrets User. After a successful bootstrap, the script creates one locally deterministic exact operator Secrets Officer assignment, removes it immediately after the metadata-read/optional-seed window, and verifies/removes that same ID on interruption or partial create. Secret values are never IaC parameters or outputs.
- **Monitoring:** Reuse `shared-services-logs`, create a workspace-based Application Insights component, and initialize Python Azure Monitor OpenTelemetry only when its connection string is present. Tests and fallback mode emit no cloud telemetry.
- **azd:** Use `infra/main.parameters.json`; azd's ARM JSON parameter format is required for environment substitution. `azure.yaml` is deliberately infrastructure-only so `azd package`/`azd deploy` cannot silently omit required Vite build arguments. The approval-gated script owns the one argument-aware ACR build path. A `.bicepparam` file is intentionally not used.
- **Shared-resource safety:** Existing shared resource configuration and SKUs are not modified. The approved deployment does add an exact-scope `AcrPull` role assignment and writes the project image into the shared ACR's `supply-response` repository. The current ACR admin-account setting remains a separately managed residual risk; this deployment authenticates only by managed identity.
- **Verification:** Compile Bicep locally, validate shell scripts without applying, build/run the container when local tooling permits, and verify `/health`, `/api`, and SPA routing before handing off to `azure-validate`.

## 9. Execution checklist

### Phase 1 — planning

- [x] Analyze and scan the workspace.
- [x] Confirm the subscription, region, and tenant.
- [x] Record classification, scale, budget, and safety constraints.
- [x] Check subscription policy assignments.
- [x] Select azd + Bicep and Container Apps.
- [x] Validate East US 2 capacity and service limits.
- [x] Document architecture, security, cost, and scope.
- [x] User approved the shared-infrastructure cost revision on 2026-08-31.

### Phase 2 — local preparation after approval

- [x] Load the Azure Container Apps, ACR, Key Vault, monitoring, OpenTelemetry, and azd service references.
- [x] Write failing infrastructure and static-hosting tests first; eight expected failures recorded before implementation.
- [x] Generate and harden the production Docker image definition.
- [x] Implement and test FastAPI static hosting after API/health routes.
- [x] Generate modular Bicep and `azure.yaml`.
- [x] Generate fail-closed preflight and deployment scripts.
- [x] Update personal-tenant deployment documentation.
- [x] Run Python, web, infrastructure, shell, and Bicep local verification.
- [x] Rebuild and smoke-test the production image with nonsecret fixture Entra build values after public package/network approval.
- [x] Rebuild and smoke-test the final tenant-exact image after the Entra registrations exist.
- [x] Mark this plan `Ready for Validation` only when preparation tests pass.

### Phase 3 — validation

- [x] Invoke `azure-validate`; do not deploy directly.
- [x] All validation checks pass.
  - [x] 1. AZD Installation.
  - [x] 2. Schema Validation.
  - [x] 3. Environment Setup.
  - [x] 4. Authentication Check.
  - [x] 5. Subscription/Location Check.
  - [x] 6. Aspire Pre-Provisioning Checks (not applicable; this is not a .NET Aspire project).
  - [x] 7. Provision Preview.
  - [x] 8. Build Verification.
  - [x] 9. Docker Build Context Validation.
  - [x] 10. Package Validation.
  - [x] 11. Azure Policy Validation.
  - [x] 12. Aspire Post-Provisioning Checks (not applicable; this is not a .NET Aspire project).
  - [x] Static least-privilege role-assignment verification.
- [x] Record validation proof and mark the plan `Validated` only when every required check passes.

### Phase 4 — deployment, separately authorized

- [x] Obtain explicit approval immediately before the first cloud mutation.
- [x] Invoke `azure-deploy`; do not call `azd up` or `azd deploy` outside that workflow.
- [x] Provision the Azure infrastructure, push the immutable image, populate Key Vault, and apply narrowly scoped Azure identity access.
- [ ] Grant the deployed Container App identity exact Fabric SQL access and complete the remaining external post-provision bindings.
- [ ] Smoke-test the deployed `/health` endpoint without invoking Work IQ as an unauthenticated user.
- [ ] Perform separately approved Entra, Fabric, Work IQ, Foundry, Power BI, and live-browser gates in their documented order.
- [x] Record endpoint, immutable resource IDs, receipts, and verification evidence without secrets.

## Role Assignment Verification

- Status: Verified in live Azure state.
- Identity checked: the Supply Response Container App system-assigned managed identity.
- Roles confirmed: `AcrPull` scoped to the exact shared registry, `Key Vault Secrets User` scoped to the project vault, and `Azure AI User` scoped to the exact Foundry project.
- External data access: Fabric SQL remains an explicit post-provision contained-user grant; Work IQ uses Alex's delegated OBO flow and does not use ARM RBAC.
- Issues: None. No subscription- or resource-group-wide runtime role assignment is present.

### Live role verification — 2026-09-05 UTC

- The Container App system identity has one `AcrPull` assignment at the exact shared registry scope.
- The identity has one `Key Vault Secrets User` assignment at the exact project vault scope.
- The identity has role-definition `53ca6127-db72-4b80-b1b0-d745d6d5456d` at the exact Foundry project scope; the CLI did not resolve its display name, so the immutable role-definition ID was used.
- The temporary operator `Key Vault Secrets Officer` assignment count is zero after bootstrap cleanup.
- Fabric SQL remains a separate contained-database-user grant and is not represented by Azure RBAC.

## 10. Local preparation proof

This evidence is local and offline except for downloading public container build
dependencies. It is not `azure-validate` proof and does not authorize deployment.

| Check | Command | Result | Timestamp |
|---|---|---|---|
| TDD red phase | `.venv/bin/pytest tests/deployment/test_infrastructure.py tests/api/test_static_hosting.py -q` | Initial 8 expected failures, 9 first-review failures, 9 second-review failures, 8 final-hardening expected failures, 6 definitive-pass expected failures, 4 lifecycle-pass expected failures, 3 final-acceptance expected failures, and 3 optimized-runtime expected failures before their fixes | 2026-08-31 |
| Focused infrastructure/API | `.venv/bin/pytest tests/deployment/test_infrastructure.py tests/api/test_static_hosting.py tests/api/test_telemetry.py -q` | 39 passed (35 deployment contracts plus static-hosting/telemetry), including executable fake-command rotation failure/signal and `PYTHONOPTIMIZE=1` fail-closed coverage plus an actual exact-Entra Vite production bundle | 2026-08-31 |
| Relevant API/integration | `.venv/bin/pytest tests/api tests/test_api.py tests/integration/test_live_case_contract.py tests/integrations/test_fabric_health.py tests/deployment/test_infrastructure.py -q` | 84 passed | 2026-08-31 |
| Full Python regression | Earlier Task 18 baseline with public NuGet access | Passed before review fixes; current review scope is covered by the focused and relevant suites above, while a new locked NuGet restore was not authorized | 2026-08-31 |
| Web unit suite | `npm test -- --run` | 5 files, 49 tests passed | 2026-08-31 |
| Web production build | `npm run build` | Passed; Vite built 179 modules | 2026-08-31 |
| Python lint/type | `.venv/bin/ruff check tests/deployment/test_infrastructure.py`; `.venv/bin/pyright --pythonpath .venv/bin/python tests/deployment/test_infrastructure.py` | Passed; 0 type errors in the final-hardening Python scope. A broad whole-repository Ruff run still reports 151 pre-existing findings outside this focused patch. | 2026-08-31 |
| Shell syntax | `/bin/bash -n scripts/lib/safe_command.sh scripts/lib/key_vault_operator_access.sh scripts/lib/deployment_health.sh scripts/preflight_personal_tenant.sh scripts/deploy_personal_tenant.sh scripts/rotate_entra_client_secret.sh` | Passed on Bash 3.2 | 2026-08-31 |
| Bicep compilation | `bicep build infra/main.bicep` with temporary extraction directory | Passed without warnings | 2026-08-31 |
| Production image | Initial Task 18 image built and ran; review-fix rebuild used `--network=none` with exact Entra args | Initial image passed; offline rebuild stopped at uncached Debian/ODBC packages; superseded by the approved 2026-09-01 public-dependency rebuild below | 2026-08-31 |
| Local container | Initial Task 18 image plus `curl /health`, `/`, `/api/runtime` | Initial health, SPA, and API responses verified; superseded by the rebuilt-image smoke below | 2026-08-31 |
| AZD environment | `azd env new supply-response-personal` plus local environment-value inspection | Environment created with the confirmed immutable subscription and tenant IDs, `eastus2`, target/shared resource names, `minReplicas=0`, and bootstrap mode; no cloud resources changed | 2026-09-01 |
| Azure identity | `azd auth login --check-status`; `az account show` | Passed for the interactive User account in the confirmed Azure Dev subscription and tenant | 2026-09-01 |
| Shared resources | Read-only Container Apps environment, ACR, and Log Analytics inspection | `shared-services-env` is an external East US 2 Consumption environment; `wkmsharedservicesacr` is Standard; `shared-services-logs` is East US 2 PerGB2018; no settings changed | 2026-09-01 |
| Subscription policy | Read-only policy-assignment inspection | Microsoft cloud security benchmark and Defender initiatives found; no explicit allowed-region, required-tag, resource-type, or SKU denial found; final template evaluation remains pending | 2026-09-01 |
| Production image rebuild | `docker build` with locked dependencies and nonsecret fixture Entra build values | Passed; ODBC Driver 18 installed and image runs as nonroot (`supply-response:validation-e57ba7a`) | 2026-09-01 |
| Rebuilt-image smoke | Local container on `127.0.0.1:18080`; `GET /health`, `/api/runtime`, `/`, and exact `/api` | Health returned `runtime_mode=fallback`; runtime contract and SPA passed; exact `/api` correctly returned 404; container stopped cleanly | 2026-09-01 |
| Entra discovery | Read-only exact display-name queries for `Supply Response API` and `Supply Response Web` | Neither registration exists; tenant-exact Vite bundle and client-secret binding cannot yet be produced | 2026-09-01 |
| Work IQ tenant enablement | `az ad sp create --id fdcc1f02-fc51-4226-8753-f668596af7f7` followed by an exact read-only service-principal query | Explicitly authorized Microsoft first-party principal created and enabled; identifier URI is `api://workiq.svc.cloud.microsoft` and the one enabled `WorkIQAgent.Ask` delegated scope has Microsoft-published ID `0b1715fd-f4bf-4c63-b16d-5be31f9847c2`; no consent granted | 2026-09-01 |
| Supply Response Entra registrations | `infra/entra/configure.sh --apply` followed by `--check` | Explicitly authorized API and SPA registrations plus service principals created in the confirmed tenant; exact manifest, `access_as_user`, `WorkIQAgent.Ask`, and canonical callback contracts passed; ignored tenant state is owner-only mode `0600`; no consent or persona role assignment performed | 2026-09-01 |
| Entra administrator consent | `az ad app permission admin-consent` for the verified API and Web client IDs followed by exact OAuth grant queries | Explicitly authorized tenant-wide delegated grants verified: API to Work IQ has only `WorkIQAgent.Ask`; Web to API has only `access_as_user`; both target the expected service principal and neither has a user-specific principal | 2026-09-01 |
| Entra persona assignments | `infra/entra/assign-personas.sh --apply` followed by `--check` | Explicitly authorized fixed mapping created and exactly verified: Alex has Material Planner and Response Approver, Jordan has Quality Approver, and Taylor has Finance Approver; no missing or excess Supply Response roles | 2026-09-01 |
| AZD Entra bindings | `azd env set` plus value-by-value equality checks in `supply-response-personal` | Verified API/Web client IDs, three persona object IDs, Work IQ resource app ID, and canonical redirect promoted into the ignored local azd environment without printing values | 2026-09-01 |
| Tenant-exact image | `docker build` with the verified four-value public Entra bundle | Passed with locked dependencies and production Vite bundle; local tag `supply-response:validation-entra-e57ba7a` | 2026-09-01 |
| Tenant-exact image smoke | Local container on `127.0.0.1:18081`; health, runtime, SPA, exact `/api`, and image-user checks | Fallback health/runtime contract passed; SPA title served; exact `/api` returned 404; image user is `appuser`; container stopped automatically | 2026-09-01 |
| Foundry discovery | Read-only project-resource inventory | Six projects found across East US and East US 2; user selected existing `m365-resource/m365` in East US 2 | 2026-09-01 |
| Foundry local tooling | Foundry skill dependency check plus explicitly authorized extension compatibility update | `azure.ai.agents` upgraded from beta.2 to beta.7 and `microsoft.foundry` beta.2 installed with its declared local dependencies; no cloud resource changed | 2026-09-01 |
| Foundry project binding | Read-only ARM/account inspection followed by local azd equality checks | Existing project `m365-resource/m365` in `DefaultResourceGroup-NCUS` is provisioned, East US 2, and public-network enabled; immutable resource ID and canonical project endpoint promoted into `supply-response-personal`; no agent published or role assigned | 2026-09-01 |
| Foundry Luna publication preflight | Fresh exact account/project reads, data-plane SDK inspection, per-agent version reads, and immediate ARM deployment read | Active tenant/subscription and retained project bindings matched; `m365-resource/m365` is provisioned in East US 2; data plane returned deployment/model `gpt-5.6-luna`; immediate ARM read returned `Succeeded`; current identity read deployments and agent versions | 2026-09-02 |
| Foundry prompt-agent publication | `AZURE_DEV_USER_AGENT=microsoft_foundry_skill uv run python scripts/publish_foundry_agents.py --publish` | Created three previously absent matching contracts: `supply-response-signal=1`, `supply-response-context=1`, and `supply-response-decision=1`; reused none | 2026-09-02 |
| Foundry live verification and promotion | Canonical `_AGENT_` name/version variables plus `scripts/verify_foundry_agents.py --live`, seven exact `azd env set` operations, read-back comparison, and ignored operator receipt | All three immutable remote contracts matched their manifests; receipt fingerprint `8fb99387be06…9adad68c271c`; seven bindings read back exactly; ignored receipt is mode `0600`. No agent invocation or evaluation was performed | 2026-09-02 |
| Fabric discovery and binding | Read-only Fabric workspace and item API requests using the Fabric resource audience | Verified the dedicated `Supply Response Demo` workspace and exact `SupplyResponseDemo` SQL Database item binding; workspace/database IDs match the ignored azd environment; no identifiers are printed here | 2026-09-04 |
| Fabric SQL authentication | Approval-gated live SQL connection using Entra authentication | Successful SQL authentication against the exact Fabric server/database binding; no connection values or tokens were recorded | 2026-09-04 |
| Fabric schema application | Approval-gated live schema deployment | Operational and analytics scripts applied twice; both runs were idempotent, with schema version 12 and the required analytics views present | 2026-09-04 |
| Fabric live integration and health | Approval-gated live integration test and health check | Passed against the live Fabric SQL store; schema version 12, `operational_store=fabric_sql`, and Fabric health/provenance checks matched the contract | 2026-09-04 |
| Power BI publication and empty-state render | Approval-gated semantic-model/report deployment, DAX smoke query, and browser inspection | Published both items, bound Fabric SQL with OAuth2, executed DAX successfully, and rendered both required pages without visual errors; populated parity remains pending | 2026-09-04 |
| Provision preview | `azd provision --preview --no-prompt` | No changes attempted. The approval-gated preview remains pending after the verified Fabric setup; remaining inputs cover the Container App managed-identity grant, Work IQ/SharePoint, and Power BI | 2026-09-04 |
| Post-publication provision preview | `AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --preview --no-prompt --environment supply-response-personal` | No changes attempted. Verified Foundry and Fabric bindings are recorded; preview remains pending for Work IQ/SharePoint and Power BI inputs and the later Container App identity grant | 2026-09-04 |
| Work IQ corpus binding | Exact Outlook/Teams artifact verification, Alex visibility checks, source-ID promotion, and SHA-256 receipt verification | Supplier and Jordan Quality artifacts are bound as `rl-001-v1`; exact tenant SharePoint host recorded; erroneous Will-authored Teams duplicate soft-deleted while Jordan's source remained intact | 2026-09-04 |
| Azure recipe prerequisites | `azd version`; `azd auth login --check-status`; exact azd/Azure account comparison; Aspire detection; `az bicep build` | Passed with azd 1.30.0, authenticated Will identity, confirmed subscription/tenant/`eastus2`, no Aspire project, and warning-free Bicep compilation | 2026-09-04 |
| Final provision preview | `azd provision --preview --no-prompt --environment supply-response-personal` | Passed in 20 seconds; preview only, with four creates (resource group, Container App, Application Insights, and Key Vault) and no Azure changes applied | 2026-09-04 |
| Current build and package verification | `uv run pytest -q`; `npm test -- --run`; `npm run build`; Docker context inspection; `azd package --no-prompt --environment supply-response-personal` | Passed: Python exit 0 with expected skips and one third-party deprecation warning; 49 web tests; 179-module production bundle; locked npm context; azd package success | 2026-09-04 |
| Azure Policy validation | Read-only assignment inventory plus successful final what-if | Existing benchmark and Defender assignments remain; no location, resource-type, SKU, or tag policy blocked the exact four-resource preview | 2026-09-04 |
| Static RBAC review | Exact principal/role/scope review across `infra/main.bicep` and RBAC modules | Passed: exact-resource `AcrPull`, `Key Vault Secrets User`, and project-scoped `Azure AI User`; Fabric SQL post-provision grant and delegated Work IQ boundary remain explicit | 2026-09-04 |
| Azure deployment | `scripts/deploy_personal_tenant.sh --apply` through `azure-deploy` | Passed: preflight matched the confirmed environment; the resource group, Container App, Application Insights, and Key Vault were provisioned; the protected secret was seeded; the immutable ACR digest was activated as the first ready/running revision; the temporary local secret file and operator vault role were removed | 2026-09-05 |
| Live Azure RBAC | Exact-scope role-assignment reads for the deployed Container App principal | Passed: one ACR Pull, one Key Vault Secrets User, and the expected immutable Foundry role-definition assignment; no temporary operator Secrets Officer assignment remains | 2026-09-05 |

### Outstanding post-deployment acceptance prerequisites

The real azd environment intentionally contains no synthetic substitute for a live
tenant binding. Azure provisioning is complete; the following post-deployment
acceptance groups remain:

- Entra: the API/Web registrations, client IDs, delegated administrator consent,
  all three persona bindings, exact app-role assignments, selected-azd-environment
  promotion, and tenant-exact image are verified.
- Fabric: complete for workspace/database discovery, SQL authentication, schema
  version 12, idempotent double-application, live integration, and health. The
  future Container App managed-identity database grant remains.
- Foundry: complete. The existing East US 2 project is bound; exact immutable
  signal/context/decision version `1` contracts and their verified publication
  receipt are promoted in the ignored azd environment.
- Work IQ: the first-party resource service principal is enabled and the API has
  tenant-wide consent for its exact delegated scope. The `rl-001-v1` corpus,
  supplier/quality source IDs, exact SharePoint host, and deployment receipt are
  bound; live retrieval and citation navigation remain final acceptance checks.
- Power BI: populated showcase-case consistency and Decision-ID parity after application deployment.

These are outputs of external setup and acceptance tasks, not values Task 18 should
invent. The deployment does not count as a complete live Case journey until the
Fabric identity grant and all approval-gated invocation, parity, and browser checks
pass.

## 11. Next step

Apply the deployed Container App managed-identity Fabric SQL grant through its
separate approval gate, verify the pinned Foundry agents, and run the user-context-
free live smoke check. Then run the approval-gated Work IQ, authenticated browser,
and populated Power BI parity checks in their documented order. The complete live
Case journey remains pending, and each additional cloud mutation or delegated live
invocation still requires the applicable explicit approval.
