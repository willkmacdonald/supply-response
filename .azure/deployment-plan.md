# Supply Response Personal-Tenant Deployment Plan

> **Status:** Validated — safe analysis diagnostics update, 2026-09-07 UTC. Existing deployment is healthy; diagnostic deployment and Alex's same-Case retry remain pending.

Generated: 2026-08-31; validation evidence updated 2026-09-07 UTC

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
- Validation complete; diagnostic deployment and same-Case retry pending.

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
