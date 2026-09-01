# Supply Response Personal-Tenant Deployment Plan

> **Status:** Ready for Validation

Generated: 2026-08-31

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
| Fabric SQL | Existing Fabric SQL Database in the confirmed tenant | Managed-identity database principal/grants performed by an explicit approval-gated command; not created by Bicep |
| Work IQ | Existing tenant capability | Confidential API client secret stored in Key Vault; OBO only after an authenticated Alex request |
| Entra web/API apps | Existing or separately provisioned tenant registrations | IDs are environment-specific configuration; client secret resides only in Key Vault |
| Power BI | Existing/published Fabric-backed report | Canonical report URL and receipt are deployment configuration, not provisioned here |

### Runtime behavior

- A Node build stage builds `apps/web/dist`.
- A Python 3.12 runtime stage installs ODBC Driver 18 and locked Python dependencies, copies the SPA into `apps/api/static`, and runs as a nonroot user.
- FastAPI registers `/api` and `/health` routes before static SPA handling. A focused application change and tests will prove API routes are never shadowed and SPA navigation resolves correctly.
- The Uvicorn command is `uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000 --proxy-headers`.
- Normal cost-control parameters use `minReplicas=0`; the rehearsal/showcase parameter file uses `minReplicas=1` for a bounded demo window.
- Live mode remains fail-closed. It never substitutes SQLite, synthetic evidence, or local agents after a live dependency failure.

### Security and identity

- The deployment checks the active Azure tenant, subscription, Foundry resource, Fabric workspace/database, and token `tid` before mutation.
- Scripts compare full immutable IDs but print only redacted IDs.
- The Container App uses a system-assigned managed identity for ACR pull, Key Vault secret retrieval, Foundry access, and Fabric SQL authentication.
- Confidential settings are Key Vault references. Client secrets, bearer tokens, Fabric connection strings, and browser storage state are never Bicep parameters, outputs, image layers, logs, or ordinary environment-variable values.
- Actual UPNs and Entra object IDs remain deployment-specific; domain history uses stable fictional persona IDs.
- Key Vault uses RBAC authorization, soft delete, and purge protection. This deployment never uses ACR admin access.
- The existing shared registry currently has its admin account enabled for other workloads. This deployment does not change that shared setting, does not read its admin credentials, and authenticates exclusively through managed identity. Disabling the shared admin account is a separate hardening decision because it could affect existing applications.
- Public Container App ingress is HTTPS-only. The POC does not add a VNet/private endpoints; that is a documented nonproduction tradeoff.
- The deploy script is fail-closed and requires an explicit apply flag plus exact subscription, tenant, region, and resource-group confirmation. Its default mode is validation/dry-run.
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
| `Dockerfile`, `.dockerignore` | Reproducible nonroot production image | Complete; locally built and smoke-tested |
| `azure.yaml` | azd project/service definition | Complete |
| `infra/main.bicep`, `infra/main.parameters.json` | Subscription target and azd-compatible environment parameters | Complete; compiles locally |
| `infra/modules/registry.bicep` | Reference the existing ACR and grant managed-identity `AcrPull` without admin credentials | Complete |
| `infra/modules/container-apps.bicep` | Reference the existing environment; create the HTTPS app, identity, scaling, and bootstrap configuration | Complete |
| `infra/modules/key-vault.bicep` | RBAC-enabled protected vault | Complete |
| `infra/modules/monitoring.bicep` | Reference existing Log Analytics and create workspace-based Application Insights | Complete |
| `infra/modules/foundry-access.bicep` | Approval-gated least-privilege Foundry role assignment | Complete; not applied |
| `scripts/preflight_personal_tenant.sh` | Read-only same-tenant and prerequisite checks | Complete; syntax-only validation performed |
| `scripts/deploy_personal_tenant.sh` | Explicit, restart-safe approval-gated deployment orchestration | Complete; syntax-only validation performed, never applied |
| `apps/api/app/main.py` and focused tests | Serve the built SPA without shadowing API/health routes | Complete |
| `tests/deployment/test_infrastructure.py` | Static and compiled-template security/architecture contract | Complete; 6 tests pass |
| `docs/deployment/personal-tenant.md` | Exact preparation, approval, deployment, rollback, and cost steps | Complete |

## 8. Research summary

- **Container Apps:** Reuse the existing public Consumption workload-profile environment. Use one system-assigned identity, HTTPS-only ingress, explicit startup/liveness/readiness probes, 0.5 vCPU/1 GiB, HTTP scaling, and `minReplicas=0` except during a bounded demo window.
- **Two-phase identity binding:** A system-assigned identity does not exist until the Container App is created. Initial Bicep therefore uses a public Microsoft placeholder on its native port 80 with no custom probes and without Key Vault or private-registry configuration. After exact-scope RBAC propagation, the approval-gated workflow builds the private image and runs Bicep again with final mode: managed-identity ACR and Key Vault bindings, target port 8000, and all three `/health` probes are established together. This avoids circular dependencies and never uses registry admin credentials.
- **Key Vault:** Create a dedicated Standard RBAC vault with soft delete and purge protection. Secret values are never IaC parameters or outputs.
- **Monitoring:** Reuse `shared-services-logs`, create a workspace-based Application Insights component, and initialize Python Azure Monitor OpenTelemetry only when its connection string is present. Tests and fallback mode emit no cloud telemetry.
- **azd:** Use `infra/main.parameters.json`; azd's ARM JSON parameter format is required for environment substitution. A `.bicepparam` file is intentionally not used.
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
- [x] Run Python, web, infrastructure, shell, Docker, and Bicep local verification.
- [x] Mark this plan `Ready for Validation` only when preparation tests pass.

### Phase 3 — validation

- [ ] Invoke `azure-validate`; do not deploy directly.
- [ ] Compile Bicep and validate parameter contracts.
- [ ] Run a read-only what-if/policy check only after separate approval if it contacts Azure.
- [ ] Verify the container starts locally, `/health` works, SPA navigation works, and `/api` remains reachable.
- [ ] Record validation proof and mark the plan `Validated` only when all required checks pass.

### Phase 4 — deployment, separately authorized

- [ ] Obtain explicit approval immediately before the first cloud mutation.
- [ ] Invoke `azure-deploy`; do not call `azd up` or `azd deploy` outside that workflow.
- [ ] Provision infrastructure, push the image, populate Key Vault, apply narrowly scoped identity access, and bind external prerequisites.
- [ ] Smoke-test the deployed `/health` endpoint without invoking Work IQ as an unauthenticated user.
- [ ] Perform separately approved Entra, Fabric, Work IQ, Foundry, Power BI, and live-browser gates in their documented order.
- [ ] Record endpoint, immutable resource IDs, receipts, and verification evidence without secrets.

## 10. Local preparation proof

This evidence is local and offline except for downloading public container build
dependencies. It is not `azure-validate` proof and does not authorize deployment.

| Check | Command | Result | Timestamp |
|---|---|---|---|
| TDD red phase | `.venv/bin/pytest tests/deployment/test_infrastructure.py tests/api/test_static_hosting.py -q` | Initial 8 expected failures plus 9 review-contract failures before their fixes | 2026-08-31 |
| Focused infrastructure/API | `.venv/bin/pytest tests/deployment/test_infrastructure.py tests/api/test_static_hosting.py tests/api/test_telemetry.py -q` | 20 passed, including an actual exact-Entra Vite production bundle | 2026-08-31 |
| Relevant API/integration | `.venv/bin/pytest tests/api tests/test_api.py tests/integration/test_live_case_contract.py tests/integrations/test_fabric_health.py tests/deployment/test_infrastructure.py -q` | 65 passed | 2026-08-31 |
| Full Python regression | `.venv/bin/pytest -q` with public NuGet access for the existing locked TMDL validator | Passed; expected live-only skips, no failures | 2026-08-31 |
| Web unit suite | `npm test -- --run` | 5 files, 49 tests passed | 2026-08-31 |
| Web production build | `npm run build` | Passed; Vite built 179 modules | 2026-08-31 |
| Python lint/type | `.venv/bin/ruff check ...`; `.venv/bin/pyright --pythonpath .venv/bin/python ...` | Passed; 0 type errors | 2026-08-31 |
| Shell syntax | `bash -n scripts/preflight_personal_tenant.sh scripts/deploy_personal_tenant.sh` | Passed | 2026-08-31 |
| Bicep compilation | `bicep build infra/main.bicep` with temporary extraction directory | Passed without warnings | 2026-08-31 |
| Production image | Initial Task 18 image built and ran; review-fix rebuild used `--network=none` with exact Entra args | Initial image passed; offline rebuild stopped at uncached Debian/ODBC packages, so the final image must be rebuilt when approved public package access is available | 2026-08-31 |
| Local container | Initial Task 18 image plus `curl /health`, `/`, `/api/runtime` | Initial health, SPA, and API responses verified; exact-Entra final image smoke remains paired with the approved rebuild | 2026-08-31 |

## 11. Next step

Perform independent implementation review, then invoke `azure-validate` only as a
separate controller step. Stop again before any read-only cloud what-if and before
the first cloud mutation.
