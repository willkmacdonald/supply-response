#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:?Set AZURE_SUBSCRIPTION_ID to the separately confirmed target}"
EXPECTED_TENANT_ID="${AZURE_TENANT_ID:?Set AZURE_TENANT_ID to the separately confirmed target}"
EXPECTED_LOCATION="${AZURE_LOCATION:?Set AZURE_LOCATION to the separately confirmed target}"
EXPECTED_RESOURCE_GROUP="${SUPPLY_RESPONSE_RESOURCE_GROUP:?Set SUPPLY_RESPONSE_RESOURCE_GROUP to the separately confirmed target}"
EXPECTED_CONTAINER_APP_NAME="${SUPPLY_RESPONSE_CONTAINER_APP_NAME:?Set SUPPLY_RESPONSE_CONTAINER_APP_NAME to the confirmed bounded name}"
FINAL_PROVISION_MAX_ATTEMPTS="${FINAL_PROVISION_MAX_ATTEMPTS:-6}"
SMOKE_MAX_ATTEMPTS="${SMOKE_MAX_ATTEMPTS:-12}"
PLACEHOLDER_IMAGE='mcr.microsoft.com/k8se/quickstart:latest'
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

resource_group="$EXPECTED_RESOURCE_GROUP"
app_name="$EXPECTED_CONTAINER_APP_NAME"

app_coordinates() {
  app_url="https://$(az containerapp show --resource-group "$resource_group" --name "$app_name" --query properties.configuration.ingress.fqdn --output tsv)"
}

smoke_gate() {
  local smoke_dir attempt
  smoke_dir="$(mktemp -d)"
  chmod 700 "$smoke_dir"
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
The apply workflow creates a placeholder only when the app/identity is absent,
then waits for managed-identity RBAC, writes a protected-file secret, builds an
immutable tenant/config-specific image with four exact Vite build arguments, and
retries the declarative final revision. An existing healthy final revision is
never replaced by the placeholder. Fabric SQL grants remain a separate approval.
After those grants, --smoke parses /health and /api/runtime and requires live
Fabric plus pinned-Foundry readiness without invoking delegated Work IQ.
EOF
  exit 0
fi

[[ "${CONFIRM_SUBSCRIPTION_ID:-}" == "$EXPECTED_SUBSCRIPTION_ID" ]] || { printf 'CONFIRM_SUBSCRIPTION_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_TENANT_ID:-}" == "$EXPECTED_TENANT_ID" ]] || { printf 'CONFIRM_TENANT_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_LOCATION:-}" == "$EXPECTED_LOCATION" ]] || { printf 'CONFIRM_LOCATION does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_RESOURCE_GROUP:-}" == "$EXPECTED_RESOURCE_GROUP" ]] || { printf 'CONFIRM_RESOURCE_GROUP does not match.\n' >&2; exit 1; }

deployment_tmp="$(mktemp -d)"
chmod 700 "$deployment_tmp"
cleanup_deployment_tmp() {
  local status=$?
  if [[ "$status" == 0 ]]; then
    rm -rf "$deployment_tmp"
  else
    printf 'Protected raw diagnostics retained at %s (mode 0700); remove them after troubleshooting.\n' "$deployment_tmp" >&2
  fi
  return "$status"
}
trap cleanup_deployment_tmp EXIT

sanitized_provision_summary() {
  python3 - "$1" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
selected = [
    line.strip()
    for line in text.splitlines()
    if re.search(r"(?i)error|failed|denied|forbidden|unauthorized|not found", line)
]
if not selected:
    print("Provisioning failed; protected diagnostics contained no categorized error line.")
    raise SystemExit
for line in selected[:12]:
    line = re.sub(
        r"(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "[redacted-id]",
        line,
    )
    line = re.sub(r"(?i)/subscriptions/[^\s'\"]+", "[redacted-resource-id]", line)
    line = re.sub(r"https?://[^\s'\"]+", "[redacted-url]", line)
    line = re.sub(r"(?i)eyJ[a-z0-9_-]{20,}", "[redacted-token]", line)
    line = re.sub(
        r"(SUPPLY_RESPONSE_[A-Z0-9_]+)\s*[=:]\s*[^,;\s]+",
        r"\1=[redacted-value]",
        line,
    )
    print(line[:500])
PY
}

last_provision_log=''
run_provision() {
  local label="$1"
  last_provision_log="${deployment_tmp}/${label}.log"
  : >"$last_provision_log"
  chmod 600 "$last_provision_log"
  if azd provision --no-prompt >"$last_provision_log" 2>&1; then
    return 0
  fi
  printf 'Provisioning step %s failed. Sanitized summary follows; raw diagnostics remain only in a protected temporary file for this run.\n' "$label" >&2
  sanitized_provision_summary "$last_provision_log" >&2
  return 1
}

secret_file="${SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE:-}"
[[ -f "$secret_file" ]] || { printf 'SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE must identify a protected file.\n' >&2; exit 1; }
python3 - "$secret_file" <<'PY' || { printf 'secret file must contain exactly one line without a trailing newline; it must also be a nonsymlink regular file owned by the current user with no group/world permissions.\n' >&2; exit 1; }
import os
import stat
import sys

path = sys.argv[1]
if os.path.islink(path):
    raise SystemExit(1)
try:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
except OSError:
    raise SystemExit(1) from None
metadata = os.fstat(descriptor)
mode = stat.S_IMODE(metadata.st_mode)
valid = (
    stat.S_ISREG(metadata.st_mode)
    and metadata.st_uid == os.getuid()
    and mode & 0o077 == 0
)
with os.fdopen(descriptor, "rb") as stream:
    data = stream.read(4097)
if not valid or not data or len(data) > 4096 or b"\n" in data or b"\r" in data:
    raise SystemExit(1)
PY

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
api_scope="api://${SUPPLY_RESPONSE_API_CLIENT_ID}/access_as_user"

verify_existing_final_health() {
  local health_file="${deployment_tmp}/existing-health.json" attempt
  : >"$health_file"
  chmod 600 "$health_file"
  for attempt in {1..6}; do
    if curl --connect-timeout 5 --max-time 10 -fsS "${app_url}/health" -o "$health_file" \
      && HEALTH_FILE="$health_file" python3 - <<'PY'
import json
import os

with open(os.environ["HEALTH_FILE"], encoding="utf-8") as stream:
    health = json.load(stream)
assert health["status"] == "ok"
assert health["runtime_mode"] == "live"
PY
    then
      return 0
    fi
    sleep $(( attempt * 5 ))
  done
  return 1
}

existing_app_stderr="${deployment_tmp}/existing-app.stderr"
: >"$existing_app_stderr"
chmod 600 "$existing_app_stderr"
existing_app_json=''
started_from_bootstrap=false
if existing_app_json="$(az containerapp show --resource-group "$resource_group" --name "$app_name" --output json 2>"$existing_app_stderr")"; then
  existing_app_image="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["properties"]["template"]["containers"][0]["image"])' <<<"$existing_app_json")"
  existing_identity_type="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("identity", {}).get("type", ""))' <<<"$existing_app_json")"
  app_url="https://$(python3 -c 'import json,sys; print(json.load(sys.stdin)["properties"]["configuration"]["ingress"]["fqdn"])' <<<"$existing_app_json")"
  if [[ "$existing_app_image" == "$PLACEHOLDER_IMAGE" || "$existing_identity_type" != *SystemAssigned* ]]; then
    started_from_bootstrap=true
    azd env set SUPPLY_RESPONSE_BOOTSTRAP_MODE true >/dev/null
    run_provision bootstrap-existing || exit 1
  else
    verify_existing_final_health || { printf 'Existing non-placeholder app is not a healthy live revision; refusing to replace it.\n' >&2; exit 1; }
  fi
else
  if ! grep -Eiq 'ResourceNotFound|not found|could not be found' "$existing_app_stderr"; then
    printf 'Could not safely determine whether the Container App exists.\n' >&2
    exit 1
  fi
  started_from_bootstrap=true
  azd env set SUPPLY_RESPONSE_BOOTSTRAP_MODE true >/dev/null
  run_provision bootstrap-new || exit 1
  app_coordinates
fi
unset existing_app_json

expected_redirect_uri="${app_url}/auth/callback"
[[ "${SUPPLY_RESPONSE_REDIRECT_URI:-}" == "$expected_redirect_uri" ]] || { printf 'SUPPLY_RESPONSE_REDIRECT_URI must exactly match the Container App callback.\n' >&2; exit 1; }

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
  if [[ "$attempt" == 12 ]]; then printf 'Managed-identity role records did not appear in time; the existing active revision was preserved.\n' >&2; exit 1; fi
  sleep 10
done

az keyvault secret set --vault-name "$vault_name" --name entra-client-secret --file "$secret_file" --output none
git_revision="$(git rev-parse --short=12 HEAD)"
public_config_digest="$(printf '%s\n' "$EXPECTED_TENANT_ID" "${SUPPLY_RESPONSE_WEB_CLIENT_ID}" "$api_scope" "$expected_redirect_uri" | python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest()[:16])')"
image_tag="${git_revision}-${public_config_digest}"
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
  run_provision restore-bootstrap
}

for ((attempt=1; attempt<=FINAL_PROVISION_MAX_ATTEMPTS; attempt++)); do
  azd env set SUPPLY_RESPONSE_BOOTSTRAP_MODE false >/dev/null
  if run_provision "final-${attempt}"; then
    printf 'Final declarative revision activated.\n'
    break
  fi
  if ! recognized_identity_binding_failure "$last_provision_log"; then
    printf 'Final deployment failed for a non-propagation reason; only the sanitized summary above was emitted.\n' >&2
    exit 1
  fi
  if [[ "$started_from_bootstrap" == true ]]; then
    restore_bootstrap_revision || { printf 'Could not restore the bootstrap revision; use the protected diagnostics from this run.\n' >&2; exit 1; }
  fi
  if [[ "$attempt" == "$FINAL_PROVISION_MAX_ATTEMPTS" ]]; then
    if [[ "$started_from_bootstrap" == true ]]; then
      printf 'Identity binding did not propagate; the Microsoft placeholder remains active. Rerun safely later.\n' >&2
    else
      printf 'Identity binding did not propagate; the prior healthy final revision remains active. Rerun safely later.\n' >&2
    fi
    exit 1
  fi
  sleep $(( attempt * 10 ))
done

printf 'Deployment prepared. STOP for the separately approved Fabric SQL identity grant and Foundry verification in docs/deployment/personal-tenant.md; then run --smoke under its own live-check approval.\n'
