#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:?Set AZURE_SUBSCRIPTION_ID to the separately confirmed target}"
EXPECTED_TENANT_ID="${AZURE_TENANT_ID:?Set AZURE_TENANT_ID to the separately confirmed target}"
EXPECTED_LOCATION="${AZURE_LOCATION:?Set AZURE_LOCATION to the separately confirmed target}"
EXPECTED_RESOURCE_GROUP="${SUPPLY_RESPONSE_RESOURCE_GROUP:?Set SUPPLY_RESPONSE_RESOURCE_GROUP to the separately confirmed target}"
FINAL_PROVISION_MAX_ATTEMPTS="${FINAL_PROVISION_MAX_ATTEMPTS:-6}"
SMOKE_MAX_ATTEMPTS="${SMOKE_MAX_ATTEMPTS:-12}"
MODE=dry-run

[[ "$FINAL_PROVISION_MAX_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] || { printf 'FINAL_PROVISION_MAX_ATTEMPTS must be a positive integer.\n' >&2; exit 2; }
[[ "$SMOKE_MAX_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] || { printf 'SMOKE_MAX_ATTEMPTS must be a positive integer.\n' >&2; exit 2; }

case "${1:-}" in
  "") ;;
  --apply) MODE=apply ;;
  --smoke) MODE=smoke ;;
  *) printf 'Usage: %s [--apply|--smoke]\n' "$0" >&2; exit 2 ;;
esac
(( $# <= 1 )) || { printf 'Usage: %s [--apply|--smoke]\n' "$0" >&2; exit 2; }

"$(dirname "$0")/preflight_personal_tenant.sh"

app_coordinates() {
  resource_group="$(azd env get-value AZURE_RESOURCE_GROUP)"
  app_name="$(azd env get-value SERVICE_API_NAME)"
  app_url="https://$(az containerapp show --resource-group "$resource_group" --name "$app_name" --query properties.configuration.ingress.fqdn --output tsv)"
}

smoke_gate() {
  local smoke_dir health_file runtime_file attempt
  smoke_dir="$(mktemp -d)"
  for ((attempt=1; attempt<=SMOKE_MAX_ATTEMPTS; attempt++)); do
    if curl --connect-timeout 5 --max-time 10 -fsS "${app_url}/health" -o "${smoke_dir}/health.json" \
      && curl --connect-timeout 5 --max-time 10 -fsS "${app_url}/api/runtime" -o "${smoke_dir}/runtime.json" \
      && HEALTH_FILE="${smoke_dir}/health.json" RUNTIME_FILE="${smoke_dir}/runtime.json" python3 - <<'PY'
import json
import os

with open(os.environ["HEALTH_FILE"], encoding="utf-8") as stream:
    health = json.load(stream)
with open(os.environ["RUNTIME_FILE"], encoding="utf-8") as stream:
    runtime = json.load(stream)

assert health["status"] == "ok"
assert health["runtime_mode"] == "live"
assert health["operational_store"] == "fabric_sql"
assert isinstance(health["schema_version"], int)
assert runtime["runtime_mode"] == "live"
assert runtime["capability_health"]["operational_store"] == "ready"
assert runtime["capability_health"]["agent_runtime"] == "ready"
PY
    then
      rm -rf "$smoke_dir"
      printf 'Live Fabric and Foundry readiness gate passed; no delegated user operation was invoked.\n'
      return 0
    fi
    sleep $(( attempt * 5 ))
  done
  rm -rf "$smoke_dir"
  printf 'Live readiness did not pass after %s bounded attempts.\n' "$SMOKE_MAX_ATTEMPTS" >&2
  return 1
}

if [[ "$MODE" == smoke ]]; then
  app_coordinates
  smoke_gate
  exit 0
fi

if [[ "$MODE" == dry-run ]]; then
  cat <<'EOF'
DRY RUN ONLY. No Azure resource was changed.
The apply workflow will: provision the placeholder app; wait for managed-identity
RBAC; write a secret from a protected file; build the exact Entra-configured SPA;
and retry the declarative final revision while preserving the placeholder on
recognized identity-propagation failures. Fabric SQL grants remain a separate
approval. After those grants, --smoke parses /health and /api/runtime and requires
live Fabric plus pinned-Foundry readiness without invoking delegated Work IQ.
EOF
  exit 0
fi

[[ "${CONFIRM_SUBSCRIPTION_ID:-}" == "$EXPECTED_SUBSCRIPTION_ID" ]] || { printf 'CONFIRM_SUBSCRIPTION_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_TENANT_ID:-}" == "$EXPECTED_TENANT_ID" ]] || { printf 'CONFIRM_TENANT_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_LOCATION:-}" == "$EXPECTED_LOCATION" ]] || { printf 'CONFIRM_LOCATION does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_RESOURCE_GROUP:-}" == "$EXPECTED_RESOURCE_GROUP" ]] || { printf 'CONFIRM_RESOURCE_GROUP does not match.\n' >&2; exit 1; }
secret_file="${SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE:-}"
[[ -f "$secret_file" ]] || { printf 'SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE must identify a protected file.\n' >&2; exit 1; }
python3 -c 'import pathlib,sys; data=pathlib.Path(sys.argv[1]).read_bytes(); sys.exit(0 if data and b"\n" not in data and b"\r" not in data else 1)' "$secret_file" \
  || { printf 'secret file must contain exactly one line without a trailing newline.\n' >&2; exit 1; }

required_runtime_settings=(
  SUPPLY_RESPONSE_API_CLIENT_ID SUPPLY_RESPONSE_ALEX_OBJECT_ID
  SUPPLY_RESPONSE_FABRIC_SQL_SERVER SUPPLY_RESPONSE_FABRIC_SQL_DATABASE
  SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SOURCE_ID SUPPLY_RESPONSE_WORKIQ_QUALITY_SOURCE_ID
  SUPPLY_RESPONSE_WORKIQ_CORPUS_VERSION SUPPLY_RESPONSE_WORKIQ_DEPLOYMENT_RECEIPT
  SUPPLY_RESPONSE_TENANT_SHAREPOINT_HOST SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT
  SUPPLY_RESPONSE_FOUNDRY_SIGNAL_AGENT_NAME SUPPLY_RESPONSE_FOUNDRY_SIGNAL_AGENT_VERSION
  SUPPLY_RESPONSE_FOUNDRY_CONTEXT_AGENT_NAME SUPPLY_RESPONSE_FOUNDRY_CONTEXT_AGENT_VERSION
  SUPPLY_RESPONSE_FOUNDRY_DECISION_AGENT_NAME SUPPLY_RESPONSE_FOUNDRY_DECISION_AGENT_VERSION
  SUPPLY_RESPONSE_FOUNDRY_DEPLOYMENT_RECEIPT SUPPLY_RESPONSE_POWER_BI_REPORT_URL
  SUPPLY_RESPONSE_POWER_BI_DEPLOYMENT_RECEIPT SUPPLY_RESPONSE_FABRIC_CITATION_BASE_URL
)
for setting in "${required_runtime_settings[@]}"; do
  [[ -n "${!setting:-}" ]] || { printf 'Missing required runtime setting: %s\n' "$setting" >&2; exit 1; }
  azd env set "$setting" "${!setting}" >/dev/null
done
uuid_pattern='^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
[[ "${SUPPLY_RESPONSE_API_CLIENT_ID}" =~ $uuid_pattern ]] || { printf 'SUPPLY_RESPONSE_API_CLIENT_ID must be a UUID.\n' >&2; exit 1; }
[[ "${SUPPLY_RESPONSE_WEB_CLIENT_ID:-}" =~ $uuid_pattern ]] || { printf 'SUPPLY_RESPONSE_WEB_CLIENT_ID must be a UUID.\n' >&2; exit 1; }

azd env set SUPPLY_RESPONSE_BOOTSTRAP_MODE true >/dev/null
azd provision --no-prompt
app_coordinates
expected_redirect_uri="${app_url}/auth/callback"
[[ "${SUPPLY_RESPONSE_REDIRECT_URI:-}" == "$expected_redirect_uri" ]] || { printf 'SUPPLY_RESPONSE_REDIRECT_URI must exactly match the bootstrapped app callback.\n' >&2; exit 1; }
api_scope="api://${SUPPLY_RESPONSE_API_CLIENT_ID}/access_as_user"

vault_name="$(azd env get-value SUPPLY_RESPONSE_KEY_VAULT_NAME)"
registry_server="$(azd env get-value SUPPLY_RESPONSE_ACR_LOGIN_SERVER)"
registry_name="${registry_server%%.*}"
principal_id="$(az containerapp identity show --resource-group "$resource_group" --name "$app_name" --query principalId --output tsv)"
registry_id="$(az acr show --name "$registry_name" --query id --output tsv)"
vault_id="$(az keyvault show --name "$vault_name" --query id --output tsv)"
for attempt in {1..12}; do
  acr_ready="$(az role assignment list --assignee-object-id "$principal_id" --scope "$registry_id" --role AcrPull --query 'length(@)' --output tsv)"
  vault_ready="$(az role assignment list --assignee-object-id "$principal_id" --scope "$vault_id" --role 'Key Vault Secrets User' --query 'length(@)' --output tsv)"
  if [[ "$acr_ready" -ge 1 && "$vault_ready" -ge 1 ]]; then break; fi
  if [[ "$attempt" == 12 ]]; then printf 'Managed-identity role records did not appear in time; the placeholder remains active.\n' >&2; exit 1; fi
  sleep 10
done

az keyvault secret set --vault-name "$vault_name" --name entra-client-secret --file "$secret_file" --output none
image_tag="${SUPPLY_RESPONSE_IMAGE_TAG:-$(git rev-parse --short HEAD)}"
image="${registry_server}/supply-response:${image_tag}"
az acr build --registry "$registry_name" --image "supply-response:${image_tag}" \
  --build-arg "VITE_ENTRA_TENANT_ID=${EXPECTED_TENANT_ID}" \
  --build-arg "VITE_ENTRA_WEB_CLIENT_ID=${SUPPLY_RESPONSE_WEB_CLIENT_ID}" \
  --build-arg "VITE_ENTRA_API_SCOPE=${api_scope}" \
  --build-arg "VITE_ENTRA_REDIRECT_URI=${expected_redirect_uri}" \
  . --output none
azd env set SUPPLY_RESPONSE_IMAGE_NAME "$image" >/dev/null

recognized_identity_binding_failure() {
  grep -Eiq 'unauthorized|authentication required|pull access denied|failed to pull|key vault.*(not found|forbidden|denied)|secret.*(not found|forbidden|denied)|managed identity.*(not found|forbidden|denied|propagat|permission)|identity.*(propagat|permission)' "$1"
}

restore_bootstrap_revision() {
  azd env set SUPPLY_RESPONSE_BOOTSTRAP_MODE true >/dev/null
  azd provision --no-prompt >/dev/null
}

final_log="$(mktemp)"
for ((attempt=1; attempt<=FINAL_PROVISION_MAX_ATTEMPTS; attempt++)); do
  azd env set SUPPLY_RESPONSE_BOOTSTRAP_MODE false >/dev/null
  if azd provision --no-prompt >"$final_log" 2>&1; then
    rm -f "$final_log"
    printf 'Final declarative revision activated.\n'
    break
  fi
  if ! recognized_identity_binding_failure "$final_log"; then
    sed -n '1,120p' "$final_log" >&2
    rm -f "$final_log"
    printf 'Final deployment failed for a non-propagation reason; inspect the redacted error.\n' >&2
    exit 1
  fi
  restore_bootstrap_revision
  if [[ "$attempt" == "$FINAL_PROVISION_MAX_ATTEMPTS" ]]; then
    rm -f "$final_log"
    printf 'Identity binding did not propagate; the Microsoft placeholder was restored. Rerun safely later.\n' >&2
    exit 1
  fi
  sleep $(( attempt * 10 ))
done

printf 'Deployment prepared. STOP for the separately approved Fabric SQL identity grant and Foundry verification in docs/deployment/personal-tenant.md; then run --smoke under its own live-check approval.\n'
