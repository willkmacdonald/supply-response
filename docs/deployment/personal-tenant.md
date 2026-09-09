# Personal-tenant Entra setup

This repository defines, but does not currently deploy, two single-tenant Microsoft Entra registrations:

- **Supply Response API** — a web API that exposes `access_as_user`, defines four user app roles, and requests delegated `WorkIQAgent.Ask`.
- **Supply Response Web** — a public SPA that requests only `api://<API_CLIENT_ID>/access_as_user`. MSAL supplies the protocol scopes needed for sign-in.

Both manifests use `AzureADMyOrg`. Tenant registration, consent, and role assignment are external mutations and require explicit approval. The checked-in files contain no tenant ID, client ID, object ID, UPN, bearer token, or credential.

## Local validation (safe now)

The dry-run paths consume deterministic fixtures and do not invoke Azure CLI or Microsoft Graph:

```bash
export SUPPLY_RESPONSE_CONFIRM_TENANT=willmacdonald.com
export SUPPLY_RESPONSE_EXPECTED_TENANT_ID=<fixture-tenant-id>
export SUPPLY_RESPONSE_WORKIQ_RESOURCE_APP_ID=<fixture-workiq-app-id>
export SUPPLY_RESPONSE_API_CLIENT_ID=<fixture-api-client-id>
export SUPPLY_RESPONSE_WEB_CLIENT_ID=<fixture-web-client-id>
export SUPPLY_RESPONSE_REDIRECT_URI=http://localhost:5173/auth/callback
export SUPPLY_RESPONSE_ALEX_OBJECT_ID=<fixture-alex-object-id>
export SUPPLY_RESPONSE_JORDAN_OBJECT_ID=<fixture-jordan-object-id>
export SUPPLY_RESPONSE_TAYLOR_OBJECT_ID=<fixture-taylor-object-id>

./infra/entra/configure.sh --dry-run --fixture tests/auth/fixtures/configure.json
./infra/entra/assign-personas.sh --dry-run --fixture tests/auth/fixtures/assignments.json
```

These are synthetic fixture UUIDs, not deployment values.

## Approval-gated tenant work

Do not perform these steps without explicit approval for the target directory:

1. Confirm the active Azure CLI directory is the verified `willmacdonald.com` directory. Record its immutable tenant UUID in `SUPPLY_RESPONSE_EXPECTED_TENANT_ID`, the Work IQ resource application UUID in `SUPPLY_RESPONSE_WORKIQ_RESOURCE_APP_ID`, and the exact registered SPA redirect URI in `SUPPLY_RESPONSE_REDIRECT_URI`. The redirect authority must already be canonical (lowercase host, no default `:443`/`:80` port); one trailing slash is removed consistently by provisioning and the SPA.
2. Set `SUPPLY_RESPONSE_CONFIRM_TENANT=willmacdonald.com`, then run `./infra/entra/configure.sh --apply`. It creates or patches the two applications and service principals, resolves the single enabled `WorkIQAgent.Ask` scope by exact value, and writes deployment IDs to ignored `infra/entra/.env.tenant` with mode `0600`. Newly created client IDs are persisted immediately with `SUPPLY_RESPONSE_ENTRA_STATE=INCOMPLETE`; a retry reuses those IDs and changes the state to `COMPLETE` only after exact validation succeeds.
3. Review and grant tenant consent for the API's delegated `WorkIQAgent.Ask` permission and the Web application's delegated `access_as_user` permission. Consent is deliberately not automated by `configure.sh`.
4. Resolve Alex, Jordan, and Taylor to immutable Entra **object IDs** through an approved administrative process. Never configure persona authorization by UPN or display name. Export the three `SUPPLY_RESPONSE_*_OBJECT_ID` values and run `./infra/entra/assign-personas.sh --apply`.
5. After propagation, separately approve the read-only live validations `./infra/entra/configure.sh --check` and `./infra/entra/assign-personas.sh --check`.

The assignment is exact and fixed:

| Stable persona | Deployment binding | API app roles |
|---|---|---|
| `RL-PERSONA-ALEX` | `SUPPLY_RESPONSE_ALEX_OBJECT_ID` | `material_planner`, `response_approver` |
| `RL-PERSONA-JORDAN` | `SUPPLY_RESPONSE_JORDAN_OBJECT_ID` | `quality_approver` |
| `RL-PERSONA-TAYLOR` | `SUPPLY_RESPONSE_TAYLOR_OBJECT_ID` | `finance_approver` |

The scripts reject missing, malformed, duplicate, disabled, excess, or ambiguous tenants, scopes, roles, IDs, and assignments. Checks compare canonical complete app-role, delegated-permission, API-scope, redirect, and persona-assignment structures rather than merely checking that required entries are present. Re-running apply is restart-safe: registrations are updated by the persisted client IDs and existing exact role assignments are left in place.

## Runtime configuration

The SPA's four settings are all-or-nothing:

```text
VITE_ENTRA_TENANT_ID=<tenant UUID>
VITE_ENTRA_WEB_CLIENT_ID=<Web application client UUID>
VITE_ENTRA_API_SCOPE=api://<API application client UUID>/access_as_user
VITE_ENTRA_REDIRECT_URI=<exact registered redirect URI>
```

MSAL uses the tenant-specific authority, redirect flow, silent acquisition, and `sessionStorage`; it never uses `localStorage`. The API client asks MSAL for a token for each request and attaches it only in the `Authorization: Bearer` header. Fallback mode remains usable when all four variables are absent.

The backend `AuthService` accepts only RS256 access tokens from the exact tenant issuer and a scalar API audience. It validates signature, expiry, not-before time, `tid`, `oid`, the exact `access_as_user` delegated scope, exact app-role sets for the bound persona, and bounded Entra metadata/JWKS. The validated inbound token is the only value preserved inside a redacted, non-serializable user assertion for a later Work IQ on-behalf-of exchange. Decision identity snapshots retain tenant ID, object ID, stable persona ID, UPN/display name, and effective roles—but never the bearer token.

The Task 17 FastAPI graph is now composed once per application instance. Fallback uses SQLite, synthetic evidence, and local deterministic explainers. Live uses only Fabric SQL, the exact `AuthService` instance for delegated Work IQ OBO, pinned Foundry agents, and the validated Power BI report URL; it never substitutes fallback data after a live-source failure. Startup and `/health` construct/report readiness only and do not invoke Work IQ, Foundry, OBO, or any user-context operation. Shutdown closes the Work IQ HTTP client and database engine.

The live backend additionally requires these deployment settings, all supplied outside source control:

```text
SUPPLY_RESPONSE_API_CLIENT_ID
SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET
SUPPLY_RESPONSE_ALEX_OBJECT_ID
SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SOURCE_ID
SUPPLY_RESPONSE_WORKIQ_QUALITY_SOURCE_ID
SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SENDER
SUPPLY_RESPONSE_WORKIQ_QUALITY_AUTHOR_OBJECT_ID
SUPPLY_RESPONSE_WORKIQ_TEAM_ID
SUPPLY_RESPONSE_WORKIQ_CHANNEL_ID
SUPPLY_RESPONSE_WORKIQ_CORPUS_VERSION
SUPPLY_RESPONSE_WORKIQ_DEPLOYMENT_RECEIPT
SUPPLY_RESPONSE_TENANT_SHAREPOINT_HOST
SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT
SUPPLY_RESPONSE_FOUNDRY_SIGNAL_AGENT_NAME
SUPPLY_RESPONSE_FOUNDRY_SIGNAL_AGENT_VERSION
SUPPLY_RESPONSE_FOUNDRY_CONTEXT_AGENT_NAME
SUPPLY_RESPONSE_FOUNDRY_CONTEXT_AGENT_VERSION
SUPPLY_RESPONSE_FOUNDRY_DECISION_AGENT_NAME
SUPPLY_RESPONSE_FOUNDRY_DECISION_AGENT_VERSION
SUPPLY_RESPONSE_FOUNDRY_DEPLOYMENT_RECEIPT
SUPPLY_RESPONSE_POWER_BI_REPORT_URL
SUPPLY_RESPONSE_POWER_BI_DEPLOYMENT_RECEIPT
SUPPLY_RESPONSE_FABRIC_CITATION_BASE_URL
```

Fabric must contain a verified, current `app.live_operational_sources` row for
`RL-001`. Its snapshot and evidence JSON are the source record: live Case creation
and every analysis re-read that row and preserve its original Fabric source IDs,
timestamps, citations, and `LIVE` provenance. Synthetic RL-001 builders are never
called by the live graph. `app.analysis_claims` provides the database-authoritative,
leased material claim used by multiple API workers; analysis plus projection are
committed in one transaction and a losing worker returns the canonical winner.

The three deployment receipts are SHA-256 bindings, not secrets. Power BI binds
the exact canonical report URL. Work IQ receipt version 2 hashes these exact UTF-8
values joined by one newline, with no trailing newline: `workiq-binding-v2`, corpus
version, supplier source ID, Quality source ID, supplier sender, Quality author
object ID, Team ID, and channel ID. Foundry binds endpoint followed by each
signal/context/decision agent name and pinned version. `/api/runtime` reports a
capability `ready` only when the corresponding binding is exact; configuration
alone remains `unverified`. Fabric readiness still requires the bounded Task 12
connectivity and schema-version check.

`SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT` is an optional, separate acceptance
setting. Supply it only after artifact-bound SQL, model, DAX, native-browser, and
access acceptance is complete. Omitting it or explicitly setting it to an empty
value disables saved-analysis links on the next declarative deployment, including
clearing a value previously saved by AZD. This deployment task neither issues nor
installs an acceptance receipt.

Recompute the nonsecret Work IQ receipt after any one of those bindings changes:

```bash
python3 -c 'import hashlib,sys; print(hashlib.sha256("\n".join(sys.argv[1:]).encode("utf-8")).hexdigest())' \
  workiq-binding-v2 \
  "$SUPPLY_RESPONSE_WORKIQ_CORPUS_VERSION" \
  "$SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SOURCE_ID" \
  "$SUPPLY_RESPONSE_WORKIQ_QUALITY_SOURCE_ID" \
  "$SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SENDER" \
  "$SUPPLY_RESPONSE_WORKIQ_QUALITY_AUTHOR_OBJECT_ID" \
  "$SUPPLY_RESPONSE_WORKIQ_TEAM_ID" \
  "$SUPPLY_RESPONSE_WORKIQ_CHANNEL_ID"
```

Set the resulting digest as `SUPPLY_RESPONSE_WORKIQ_DEPLOYMENT_RECEIPT`. The
deployment script independently recomputes the same digest and stops before
provisioning if it differs.

`SUPPLY_RESPONSE_POWER_BI_REPORT_URL` and the Fabric citation base must be canonical `https://app.powerbi.com` URLs without credentials, explicit ports, query strings, or fragments. Work IQ citations are accepted only through the Task 15 Microsoft 365 tenant/host policy. Missing or untrusted required live citations remain visible as `Required live citation missing` and disable approval.

## Approval-gated live browser gate

The normal fallback Playwright project remains local and does not require MSAL. The separate `live` project skips before browser/network activity unless every explicit prerequisite exists:

```text
SUPPLY_RESPONSE_LIVE_E2E=1
SUPPLY_RESPONSE_LIVE_BASE_URL=<exact deployed HTTPS URL>
SUPPLY_RESPONSE_EXPECTED_DEPLOYMENT_ORIGIN=<same exact HTTPS origin>
SUPPLY_RESPONSE_ALEX_STORAGE_STATE=<owner-only 0600 Playwright state>
SUPPLY_RESPONSE_EXPECTED_SCENARIO_EFFECTIVE_TIME=2026-09-01T09:00:00-05:00
SUPPLY_RESPONSE_EXPECTED_CORPUS_VERSION=<pinned corpus version>
SUPPLY_RESPONSE_EXPECTED_SUPPLIER_SOURCE_ID=<exact supplier artifact source ID>
SUPPLY_RESPONSE_EXPECTED_QUALITY_SOURCE_ID=<exact Quality artifact source ID>
SUPPLY_RESPONSE_EXPECTED_SIGNAL_AGENT_VERSION=<pinned numeric version>
SUPPLY_RESPONSE_EXPECTED_CONTEXT_AGENT_VERSION=<pinned numeric version>
SUPPLY_RESPONSE_EXPECTED_DECISION_AGENT_VERSION=<pinned numeric version>
SUPPLY_RESPONSE_TENANT_SHAREPOINT_HOST=<exact tenant SharePoint host>
```

The gate is resolved while Playwright configuration loads, before local servers or a
browser can start. A live selection never starts fallback servers. The live project
disables trace, screenshots, and video so bearer-bearing headers cannot enter browser
artifacts. Run it only after Task 18 approval, tenant provisioning, exact
Foundry/corpus verification, successful read-only Work IQ citation verification as
Alex, and confirmation that `/api/runtime` reports all four capabilities ready. The
gate creates a fresh `showcase` Case, verifies the two required Work IQ artifacts
through the Task 15 authenticated rendered-artifact verifier, requires analysis
within 90 seconds, five actions within 15 seconds, simulated observations within 65
seconds, and the same immutable Decision ID in analysis lineage, actions,
observations, and Power BI within 60 seconds.

No secret or certificate is generated by the repository or stored in source control.

## Azure Container Apps runtime (Task 18)

> **STOP — separate approval required.** The commands in this section create or
> update Azure resources, role assignments, a registry image, and a Key Vault
> secret. Local preparation does not authorize running `--apply`, `azd provision`,
> a what-if, an image push, or any live prerequisite check.

The personal-tenant runtime reuses `shared-services-env`,
`wkmsharedservicesacr`, and `shared-services-logs` in `shared-services-rg` without
changing their configuration or SKU. It does create one narrowly scoped
`AcrPull` assignment on the shared registry and writes the project image to the
`supply-response` repository in that registry. It creates a separate Supply
Response resource group containing one Container App, one project Key Vault, and
one workspace-based Application Insights resource. Normal scaling is 0–2 replicas
at 0.5 vCPU/1 GiB. Set `SUPPLY_RESPONSE_MIN_REPLICAS=1` only for a bounded
rehearsal or showcase.

The incremental baseline is expected to be approximately $0–$3/month at demo
volume, excluding Fabric, Power BI, Foundry model, and Work IQ usage. The shared
registry already has its admin account enabled for other workloads. This project
does not read or use those credentials; it pulls exclusively with its Container
App system identity. Disabling the shared setting requires a separate impact
review.

### Local-only validation

These commands do not contact or mutate Azure:

```bash
.venv/bin/pytest tests/deployment/test_infrastructure.py tests/api/test_static_hosting.py tests/api/test_telemetry.py -q
bash -n scripts/preflight_personal_tenant.sh scripts/deploy_personal_tenant.sh
DOTNET_BUNDLE_EXTRACT_BASE_DIR=/tmp/supply-response-bicep ~/.azure/bin/bicep build infra/main.bicep --outfile /tmp/supply-response-main.json
```

The production image is a two-stage Node/Python 3.12 build with ODBC Driver 18,
locked Python dependencies, built React assets, a nonroot runtime user, and one
Uvicorn process on port 8000. FastAPI registers health and API routes before the
SPA fallback; unknown `/api` paths remain 404s.

`azure.yaml` is intentionally infrastructure-only. Do not use `azd package`,
`azd deploy`, or `azd up`: those paths do not carry the four required public Vite
build arguments. The only approved deployment image build is the argument-aware
`az acr build` call inside `deploy_personal_tenant.sh --apply`. A checked local
equivalent is:

```bash
docker build --pull=false --tag supply-response:entra-contract-check \
  --build-arg 'VITE_ENTRA_TENANT_ID=<fixture-tenant-id>' \
  --build-arg 'VITE_ENTRA_WEB_CLIENT_ID=<fixture-web-client-id>' \
  --build-arg 'VITE_ENTRA_API_SCOPE=api://<fixture-api-client-id>/access_as_user' \
  --build-arg 'VITE_ENTRA_REDIRECT_URI=https://demo.example.test/auth/callback' .
```

The values above are fixtures. A full image build may download public base images
and packages and therefore requires network approval; the Vite production-bundle
contract test runs locally without embedding tenant values in source.

### Approval-gated preparation

The deployment principal needs these exact permissions before `--apply`:

- At **subscription scope**, `Microsoft.Resources/subscriptions/resourceGroups/write`
  plus deployment write/read permissions for the new resource group (normally
  Contributor at subscription scope because the group does not exist yet).
- At the **shared ACR resource scope**, read plus
  `Microsoft.ContainerRegistry/registries/scheduleRun/action` for the remote build,
  repository push, and `Microsoft.Authorization/roleAssignments/write` for the
  Container App's `AcrPull` assignment.
- At the **project resource-group scope**, create/update rights for Container Apps,
  Application Insights, and Key Vault, plus
  `Microsoft.Authorization/roleAssignments/write` for the Key Vault assignment.
  Initial secret population additionally requires the data-plane action
  `Microsoft.KeyVault/vaults/secrets/readMetadata/action` and
  `Microsoft.KeyVault/vaults/secrets/setSecret/action`. The Key Vault Secrets
  Officer role supplies both at the exact new-vault scope. A management-plane
  secret write permission is not a substitute. After Bicep successfully creates
  the bootstrap vault, the apply script creates one deterministic exact-scope
  assignment for the separately confirmed current principal, then removes it
  immediately after inspection and optional seed. Bicep and placeholder restores
  never create operator elevation. This requires
  `Microsoft.Authorization/roleAssignments/delete` at the new-vault scope as well
  as write.
- At the **Foundry project scope**,
  `Microsoft.Authorization/roleAssignments/write` for the exact `Azure AI User`
  assignment. Reader access is also required on the existing Container Apps
  environment, shared Log Analytics workspace, shared ACR, and Foundry project.

Owner, Role Based Access Control Administrator, or User Access Administrator may
supply `roleAssignments/write` only at the scopes where assigned; Contributor
alone cannot. Fabric SQL administration, tenant consent, persona assignment,
Foundry publication, Power BI publication, and Demo Corpus work remain separate
procedures and are never automated here.

This personal-tenant workflow intentionally supports only an interactive Entra
**User** operator. Before preflight, run `az login --tenant <confirmed-tenant-id>`
and select the confirmed subscription; service-principal login is rejected by
preflight, deployment, and rotation. The signed-in user must also be able to read
the two application registrations through Microsoft Graph. Preflight exercises
that existing delegated app-read path with exact `az ad app show --id` checks for
the Web and API registrations; it does not perform a Graph lookup for the
operator object ID because that ID comes from the ephemeral ARM token's `oid`.

Configure azd values without putting secrets in its environment:

```bash
azd env new supply-response-personal
azd env select supply-response-personal
export SUPPLY_RESPONSE_AZD_ENVIRONMENT=supply-response-personal
export AZURE_SUBSCRIPTION_ID=<confirmed-subscription-id>
export AZURE_TENANT_ID=<confirmed-tenant-id>
export AZURE_LOCATION=eastus2
export SUPPLY_RESPONSE_RESOURCE_GROUP=rg-supply-response-demo
export SUPPLY_RESPONSE_CONTAINER_APP_NAME=ca-sr-demo
export SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_ID=<confirmed-current-object-id>
export SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_TYPE=User
azd env set AZURE_SUBSCRIPTION_ID <confirmed-subscription-id>
azd env set AZURE_TENANT_ID <confirmed-tenant-id>
azd env set AZURE_LOCATION eastus2
azd env set SUPPLY_RESPONSE_RESOURCE_GROUP rg-supply-response-demo
azd env set SUPPLY_RESPONSE_CONTAINER_APP_NAME ca-sr-demo
azd env set SUPPLY_RESPONSE_SHARED_RESOURCE_GROUP shared-services-rg
azd env set SUPPLY_RESPONSE_SHARED_CONTAINER_APPS_ENVIRONMENT shared-services-env
azd env set SUPPLY_RESPONSE_SHARED_REGISTRY wkmsharedservicesacr
azd env set SUPPLY_RESPONSE_SHARED_LOG_ANALYTICS_WORKSPACE shared-services-logs
```

For an existing checkout, run `azd env list`, then explicitly run
`azd env select supply-response-personal`; do not rely on whichever environment
was last active. Preflight compares the selected `AZURE_ENV_NAME` to
`SUPPLY_RESPONSE_AZD_ENVIRONMENT` and stops on drift.

Export the nonsecret live settings listed above and the exact Foundry project
resource ID plus Fabric workspace and SQL item IDs for preflight. On a true
bootstrap with no existing `entra-client-secret`, also supply a nonsymlink regular
file containing the Entra confidential-client secret. The file must be
owned by the current UID, have no group/world permission bits (mode `0600` or
stricter), and contain no newline. Never pass the secret as a command argument or
store it in azd. The deployment script writes it with `--file` and suppresses
command output. Also export the Web application client ID
and the exact registered callback. For this single-container deployment the
callback must be `https://<exact-container-app-fqdn>/auth/callback`; the script
derives that value from the exact bounded app and refuses any mismatch. The
four validated public Entra values are then embedded into the production Vite
bundle as ACR build arguments. Before mutation, preflight also reads both Entra
registrations and requires the exact Web redirect plus one enabled
`access_as_user` API scope. Choose and freeze an explicit Container App name of
2–32 lowercase letters, numbers, or hyphens (letter first, alphanumeric last,
with no consecutive hyphens).
It is deliberately independent of the arbitrary-length azd environment name.
The hostname combines that bounded name with the existing Container Apps
environment's `properties.defaultDomain`. Update the Web registration under the
separate Entra approval and run `infra/entra/configure.sh --check` before starting
this deployment.

The default script mode performs only read-only preflight and prints the planned
sequence:

```bash
./scripts/deploy_personal_tenant.sh
```

After a new explicit cloud-mutation approval, set all four exact confirmations
and run apply:

```bash
export CONFIRM_SUBSCRIPTION_ID=<confirmed-subscription-id>
export CONFIRM_TENANT_ID=<confirmed-tenant-id>
export CONFIRM_LOCATION=eastus2
export CONFIRM_RESOURCE_GROUP=rg-supply-response-demo
export SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE=/owner-only/path/entra-client-secret
./scripts/deploy_personal_tenant.sh --apply
```

The restart-safe sequence is: same-tenant preflight; reject tracked or untracked
changes under the committed image build context; inspect the exact app; create
the viable Microsoft placeholder only when the app/identity is absent; verify an
existing non-placeholder revision is healthy before an upgrade; check exact
managed-identity role records; create and verify the exact deterministic
temporary Key Vault Secrets Officer assignment for the confirmed current
operator; wait until a real Key Vault metadata read succeeds; seed the secret
only when a bootstrap has no existing version; remove the exact temporary
operator assignment immediately; build an image tagged
with both the Git revision and a SHA-256 digest of the tenant, Web client, API
scope, and exact redirect; resolve its ACR manifest digest; and deploy only the
immutable `registry/supply-response@sha256:...` reference. A role
record is not treated as proof of data-plane propagation. Recognized ACR pull or
Key Vault identity failures trigger bounded retries. The placeholder is restored
only for a first deployment that started from it; an upgrade preserves the prior
healthy final revision. Raw stdout and stderr from identifier-bearing Azure,
azd, Fabric, Foundry, ACR, Key Vault, and role commands are written only to
mode-`0600`
files inside a mode-`0700` temporary directory, and the console receives a
redacted categorized summary. Successful runs remove the directory; failed runs
retain it and print its path so the owner can troubleshoot and then delete it.
Other failures stop immediately.

If an interrupted bootstrap leaves the temporary role behind, do not continue to
the final deployment. Under a separate exact-target removal approval, first
verify the selected azd environment plus active subscription and tenant. Resolve
the exact vault ID, recompute the deterministic assignment ID, fetch it at that
vault scope, and require its principal ID/type, scope, and role definition to
match before deleting:

```bash
set -euo pipefail
source scripts/lib/safe_command.sh
safe_init_diagnostics
source scripts/lib/key_vault_operator_access.sh
safe_capture selected_env recovery-env azd env get-value AZURE_ENV_NAME
safe_capture active_subscription recovery-subscription az account show --query id --output tsv
safe_capture active_tenant recovery-tenant az account show --query tenantId --output tsv
[[ "$selected_env" == "$SUPPLY_RESPONSE_AZD_ENVIRONMENT" ]]
[[ "$active_subscription" == "$AZURE_SUBSCRIPTION_ID" ]]
[[ "$active_tenant" == "$AZURE_TENANT_ID" ]]
safe_capture vault_name recovery-vault-name azd env get-value SUPPLY_RESPONSE_KEY_VAULT_NAME
safe_capture vault_id recovery-vault-id az keyvault show --name "$vault_name" --query id --output tsv
configure_temporary_kv_operator_access "$vault_id" \
  "$SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_ID" \
  "$SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_TYPE"
KV_OPERATOR_CLEANUP_ACTIVE=true
verify_temporary_kv_operator_access
cleanup_temporary_kv_operator_access
```

The verifier fetches only the locally derived exact assignment ID and refuses
deletion unless it matches the confirmed principal, exact vault scope, and role
definition `b86a8fe4-44ce-4948-aee5-eccb2c155cd7`. It never trusts an azd output
or deletes by role name alone. The Container App retains only Key Vault Secrets
User; it is never granted Secrets Officer.

### Separate Entra client-secret rotation

Normal apply does not rotate this credential. Rotation uses the dedicated script,
which is dry-run by default:

```bash
./scripts/rotate_entra_client_secret.sh
```

The mutation path requires exact subscription, tenant, vault ID and URI,
Container App ID and name, current interactive User principal, both deployed
origin variables, and replacement-file settings plus matching
`CONFIRM_SUBSCRIPTION_ID`, `CONFIRM_TENANT_ID`, `CONFIRM_VAULT_ID`, and
`CONFIRM_CONTAINER_APP_ID` and `CONFIRM_CONTAINER_APP_NAME` values. In
particular, set `SUPPLY_RESPONSE_KEY_VAULT_URI`,
`SUPPLY_RESPONSE_CONTAINER_APP_ID`, `SUPPLY_RESPONSE_LIVE_BASE_URL`, and
`SUPPLY_RESPONSE_EXPECTED_DEPLOYMENT_ORIGIN` to their separately confirmed exact
values. Set every remaining live Playwright gate variable listed earlier, then
obtain separate approvals for temporary role creation, secret read/set, revision
restart, the live-demo business actions, and possible rollback before running:

```bash
./scripts/rotate_entra_client_secret.sh --apply
```

Before creating that assignment or reading a secret, the script fetches the exact
Container App by its canonical ARM ID and requires the returned ID, resource
group/name, and system-assigned identity to match. Its sole
`entra-client-secret` reference must equal the confirmed vault URI plus
`secrets/entra-client-secret`. The returned ingress FQDN derives the HTTPS origin;
both live origin variables must equal it, and exactly one active latest-ready
revision must belong to that app. Any mismatch stops before secret mutation.

The script then creates one deterministic Key Vault Secrets Officer assignment at
the exact vault scope. At that scope, the role supplies the required rotation actions:
`Microsoft.KeyVault/vaults/secrets/readMetadata/action`,
`Microsoft.KeyVault/vaults/secrets/getSecret/action`, and
`Microsoft.KeyVault/vaults/secrets/setSecret/action`. It waits for real
data-plane access, downloads the old value into an owner-only rollback file,
sets the validated replacement, restarts the exact active revision, and runs
`npm --prefix apps/web run test:e2e -- --project=live`. That deployed gate performs
authenticated Alex Work IQ/OBO; the local Python integration test is not used.

Restart or live-gate failure restores the prior value, restarts, and reruns the
same deployed gate. Success, failure, interruption, and handled signals all run
the cleanup hook: it removes the rollback file before diagnostics can be retained
and verifies/removes only the deterministic exact role assignment. If cleanup or
rollback is interrupted, use the verified recovery procedure above for the role;
the previous Key Vault version remains available for a newly approved recovery.
Record only redacted version suffixes, UTC time, revision, gate result, rollback
result, and exact-role cleanup result—never a secret value or bearer token.

### Separate Fabric SQL access procedure

> **Separate approval required.** The following commands change the Fabric SQL
> Database. Run them as a confirmed Fabric SQL administrator only after reviewing
> the exact server, database, Container App principal ID, and generated SQL.

Apply the committed idempotent schema first, then create a contained user for the
Container App identity and grant only DML over the application schema:

```bash
export SUPPLY_RESPONSE_CONTAINER_APP_PRINCIPAL_ID="$(az containerapp identity show \
  --resource-group "$SUPPLY_RESPONSE_RESOURCE_GROUP" \
  --name "$(azd env get-value SERVICE_API_NAME)" --query principalId -o tsv)"

sqlcmd -S "$SUPPLY_RESPONSE_FABRIC_SQL_SERVER" -d "$SUPPLY_RESPONSE_FABRIC_SQL_DATABASE" -G \
  -b -i fabric/sql/001_operational_schema.sql
sqlcmd -S "$SUPPLY_RESPONSE_FABRIC_SQL_SERVER" -d "$SUPPLY_RESPONSE_FABRIC_SQL_DATABASE" -G \
  -b -i fabric/sql/002_analytics_views.sql

sqlcmd -S "$SUPPLY_RESPONSE_FABRIC_SQL_SERVER" -d "$SUPPLY_RESPONSE_FABRIC_SQL_DATABASE" -G -b -Q \
  "IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'ca-supply-response') CREATE USER [ca-supply-response] FROM EXTERNAL PROVIDER WITH OBJECT_ID='$SUPPLY_RESPONSE_CONTAINER_APP_PRINCIPAL_ID'; GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::app TO [ca-supply-response];"
```

Verify the exact committed schema version (`12`) and the four schema permissions:

```bash
sqlcmd -S "$SUPPLY_RESPONSE_FABRIC_SQL_SERVER" -d "$SUPPLY_RESPONSE_FABRIC_SQL_DATABASE" -G -b -Q \
  "SET NOCOUNT ON; SELECT schema_version FROM app.schema_version WHERE component=N'operational'; SELECT permission_name, state_desc FROM sys.database_permissions WHERE grantee_principal_id=USER_ID(N'ca-supply-response') AND class_desc=N'SCHEMA' AND major_id=SCHEMA_ID(N'app') ORDER BY permission_name;"
```

The first result must be `12`; the second must contain exactly `DELETE`,
`INSERT`, `SELECT`, and `UPDATE`, all in `GRANT` state. Save the redacted workspace
ID, SQL item ID, principal ID, schema version, timestamp, and command exit status
in ignored `.artifacts/deployment/fabric-sql-receipt.txt`; never save an access
token.

### Load the canonical RL-001 operational source

The live application fails closed until Fabric contains the verified fictional
RL-001 source bundle. Load it only after schema version 12 and the contained-user
permissions have been verified. The command defaults to a read-only plan and
uses the selected Azure CLI tenant; it never prints credentials or payload JSON.

```bash
set -a
source .azure/supply-response-personal/.env
set +a
export SUPPLY_RESPONSE_RUNTIME_MODE=live
export SUPPLY_RESPONSE_CREDENTIAL_MODE=azure_cli
export SUPPLY_RESPONSE_ALLOWED_TENANT_ID="$AZURE_TENANT_ID"
uv run python scripts/load_fabric_rl001.py
```

After separate approval to insert the verified fictional bundle:

```bash
uv run python scripts/load_fabric_rl001.py --apply
```

The first apply reports `inserted`; an exact repeat reports `unchanged`. A
different payload under `RL-001-OPERATIONAL-V1` fails without updating or
deleting the existing authoritative row.

Recovery is a separate approved SQL change:

```sql
REVOKE SELECT, INSERT, UPDATE, DELETE ON SCHEMA::app FROM [ca-supply-response];
DROP USER [ca-supply-response];
```

### Separate pre-deployment Foundry verification and receipt

> **Separate live-read approval required.** Bicep grants the Container App only
> `Azure AI User` at the exact Foundry project scope. Agent publication remains a
> different mutation and is never performed by this deployment script.

Complete this procedure before `--apply`, because the exact receipt is required
as declarative final-revision configuration. After the three versions have
already been separately published and pinned, run:

```bash
export SUPPLY_RESPONSE_ENTRA_TENANT_ID="$AZURE_TENANT_ID"
.venv/bin/python scripts/verify_foundry_agents.py --live
```

The verifier prints the three checked immutable versions first and, only after
all exact remote checks succeed, ends with an assignment in this form:

```text
SUPPLY_RESPONSE_FOUNDRY_DEPLOYMENT_RECEIPT=<64-lowercase-hexadecimal-characters>
```

Copy that exact emitted assignment into the selected ignored azd environment
(`.azure/<environment-name>/.env`) and export the same exact value in the shell
used for deployment. Do not calculate or edit the receipt manually, and do not
put an actual receipt in this runbook.

Record the verified names, immutable versions, project resource ID, timestamp,
and receipt in ignored `.artifacts/deployment/foundry-receipt.txt`. If verification
detects drift, do not change the pinned version in place: publish a new version
under separate approval, verify it, recompute the receipt, and redeploy. To revoke
runtime access, remove the Container App's `Azure AI User` assignment at the exact
project scope under its own approval.

After both procedures, obtain approval for the user-context-free live endpoint
check and run:

```bash
./scripts/deploy_personal_tenant.sh --smoke
```

The bounded gate parses `/health` and `/api/runtime`, requires live Fabric schema
readiness and the exact pinned Foundry receipt, and does not invoke Work IQ, OBO,
or any external business action.

### Recovery and post-demo cost control

For an analysis response of `LIVE_SOURCE_UNAVAILABLE`, first inspect its optional
fixed `source_kind` (`supplier` or `quality`) and `stage` (`authentication`,
`discovery`, `fetch`, `validation`, or `timeout`) fields. Then inspect the Container App
console logs for `live_analysis_failed`. The `stage` distinguishes Fabric,
supplier and Quality retrieval, evidence validation, orchestration, and
persistence. `error_type`, `origin` (function and line), and immediate cause
metadata locate the failing code without recording exception messages, source
content, tokens, SQL values, or actor details. Concurrent retrieval failures may
produce both a source-specific event and an aggregate `retrieve_sources` event.
The public response remains bounded, and a live Case never silently falls back.
Use the request time and active revision to match diagnostics to a retry; do not
enable payload logging or copy access tokens to investigate.

If the failing step is Work IQ token exchange, `workiq_obo_failed` distinguishes
`remote_error` (an error field returned by the identity client) from
`response_rejected` (local response validation). It records only allowlisted
OAuth/AAD codes and booleans for token presence, Bearer type, and the two exact
expected scope forms. `unknown` means the code was absent or not allowlisted;
it is not evidence of a particular identity failure. The response validator
accepts complete scope tokens matching either `WorkIQAgent.Ask` or
`api://workiq.svc.cloud.microsoft/WorkIQAgent.Ask`; other resources, suffixes,
`.default`, and malformed scopes do not satisfy this check. Nonempty Bearer
tokens and the validated delegated Alex actor are still required. Never log the
raw token response.

The production path opens an isolated Work IQ MCP session for each source. `ask`
receives only the fictional topic and human-readable location; configured IDs,
known URLs, expected quantities/dates, and copied source text are not discovery
inputs. `fetch` is called only with a complete supported individual-message path
returned by discovery. A successful answer or HTTP response is not evidence:
the fetched entity must match the configured source, sender/author and
mailbox/Team/channel binding before its inert normalized body becomes a source
statement. Do not enable raw response, prompt, token, or message-body logging.

If the final revision is unhealthy, leave the previous healthy revision available,
inspect redacted Container Apps/Application Insights diagnostics, correct the
configuration, and rerun. Do not expose a secret while troubleshooting. If RBAC
has not propagated, wait and rerun; do not fall back to ACR admin credentials or
a plain environment secret.

Immediately after each rehearsal/showcase, restore scale-to-zero:

```bash
azd env set SUPPLY_RESPONSE_MIN_REPLICAS 0
az containerapp update --resource-group "$SUPPLY_RESPONSE_RESOURCE_GROUP" \
  --name "$SUPPLY_RESPONSE_CONTAINER_APP_NAME" --min-replicas 0 --output none
```

This is a cloud mutation and requires its own exact-target approval. Using the
same persisted Bicep parameter before the narrow update keeps the next deployment
from silently returning to a drifted replica count.

Deleting the project resource group is a separate destructive approval. It does
not delete the shared environment, ACR, or Log Analytics workspace; container
images remain in the shared registry until separately reviewed.

## Official references

- [Microsoft identity platform access-token claims](https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference)
- [Secure applications and APIs by validating claims](https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation)
- [Application resource and `AzureADMyOrg`](https://learn.microsoft.com/en-us/graph/api/resources/application?view=graph-rest-1.0)
- [Add app roles and receive them in tokens](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps)
- [Grant an app-role assignment](https://learn.microsoft.com/en-us/graph/api/serviceprincipal-post-approleassignedto?view=graph-rest-1.0)
- [MSAL.js caching](https://learn.microsoft.com/en-us/entra/msal/javascript/browser/caching)
- [Acquire tokens silently, then redirect when interaction is required](https://learn.microsoft.com/en-us/entra/msal/javascript/browser/acquire-token)
- [OAuth 2.0 on-behalf-of flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow)
