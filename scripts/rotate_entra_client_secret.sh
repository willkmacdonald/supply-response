#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
source "${script_dir}/lib/safe_command.sh"
source "${script_dir}/lib/key_vault_operator_access.sh"
safe_init_diagnostics

MODE=dry-run
case "${1:-}" in
  '') ;;
  --apply) MODE=apply ;;
  *) printf 'Usage: %s [--apply]\n' "$0" >&2; exit 2 ;;
esac
(( $# <= 1 )) || { printf 'Usage: %s [--apply]\n' "$0" >&2; exit 2; }

if [[ "$MODE" == dry-run ]]; then
  cat <<'EOF'
DRY RUN ONLY. No Azure resource was read or changed.
The apply path verifies exact subscription, tenant, vault, app, and current
principal; creates one deterministic temporary Key Vault Secrets Officer role;
captures the old value in an owner-only rollback file; sets the validated new
value; restarts the exact active revision; runs the deployed live Playwright OBO
gate; rolls back on restart/gate failure; then removes the file and exact role.
EOF
  exit 0
fi

EXPECTED_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:?Set the confirmed subscription ID}"
EXPECTED_TENANT_ID="${AZURE_TENANT_ID:?Set the confirmed tenant ID}"
EXPECTED_VAULT_ID="${SUPPLY_RESPONSE_KEY_VAULT_ID:?Set the exact Key Vault resource ID}"
EXPECTED_VAULT_URI="${SUPPLY_RESPONSE_KEY_VAULT_URI:?Set the exact Key Vault URI}"
VAULT_NAME="${SUPPLY_RESPONSE_KEY_VAULT_NAME:?Set the exact Key Vault name}"
RESOURCE_GROUP="${SUPPLY_RESPONSE_RESOURCE_GROUP:?Set the exact app resource group}"
EXPECTED_CONTAINER_APP_ID="${SUPPLY_RESPONSE_CONTAINER_APP_ID:?Set the exact Container App resource ID}"
CONTAINER_APP_NAME="${SUPPLY_RESPONSE_CONTAINER_APP_NAME:?Set the exact Container App name}"
PRINCIPAL_ID="${SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_ID:?Set the confirmed current principal object ID}"
PRINCIPAL_TYPE="${SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_TYPE:?Set User for the current interactive deployment principal}"
REPLACEMENT_FILE="${SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE:?Set the replacement secret file}"
LIVE_BASE_URL="${SUPPLY_RESPONSE_LIVE_BASE_URL:?Set the exact deployed HTTPS origin}"
EXPECTED_DEPLOYMENT_ORIGIN="${SUPPLY_RESPONSE_EXPECTED_DEPLOYMENT_ORIGIN:?Set the exact expected deployment origin}"

[[ "${CONFIRM_SUBSCRIPTION_ID:-}" == "$EXPECTED_SUBSCRIPTION_ID" ]] || { printf 'CONFIRM_SUBSCRIPTION_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_TENANT_ID:-}" == "$EXPECTED_TENANT_ID" ]] || { printf 'CONFIRM_TENANT_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_VAULT_ID:-}" == "$EXPECTED_VAULT_ID" ]] || { printf 'CONFIRM_VAULT_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_CONTAINER_APP_ID:-}" == "$EXPECTED_CONTAINER_APP_ID" ]] || { printf 'CONFIRM_CONTAINER_APP_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_CONTAINER_APP_NAME:-}" == "$CONTAINER_APP_NAME" ]] || { printf 'CONFIRM_CONTAINER_APP_NAME does not match.\n' >&2; exit 1; }
[[ "$PRINCIPAL_TYPE" == User ]] || { printf 'Secret rotation supports only an interactive User deployment principal; ServicePrincipal is not supported.\n' >&2; exit 1; }
valid_secret_file "$REPLACEMENT_FILE" || { printf 'Replacement secret file is invalid.\n' >&2; exit 1; }

rollback_secret_file=''
rotation_needs_rollback=false
cleanup_rotation_lifecycle() {
  if [[ "$rotation_needs_rollback" == true && -n "$rollback_secret_file" && -f "$rollback_secret_file" ]]; then
    safe_run exit-restore-prior-secret az keyvault secret set --vault-name "$VAULT_NAME" --name entra-client-secret --file "$rollback_secret_file" --output none || true
    safe_run exit-restart-rollback az containerapp revision restart --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_APP_NAME" --revision "$active_revision" || true
    rotation_needs_rollback=false
  fi
  if [[ -n "$rollback_secret_file" ]]; then
    rm -f "$rollback_secret_file"
    rollback_secret_file=''
  fi
  cleanup_temporary_kv_operator_access
}
safe_before_diagnostics_cleanup() {
  cleanup_rotation_lifecycle
}
rotation_signal_exit() {
  exit 130
}
trap rotation_signal_exit INT TERM

safe_capture active_subscription rotation-subscription az account show --query id --output tsv
safe_capture active_tenant rotation-tenant az account show --query tenantId --output tsv
safe_capture active_principal_type rotation-principal-type az account show --query user.type --output tsv
safe_capture_ephemeral arm_access_token rotation-arm-token az account get-access-token --resource https://management.azure.com/ --query accessToken --output tsv
active_principal_id="$(printf '%s' "$arm_access_token" | python3 -c 'import base64,json,sys; part=sys.stdin.read().split(".")[1]; claims=json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))); print(claims["oid"])')"
token_tenant_id="$(printf '%s' "$arm_access_token" | python3 -c 'import base64,json,sys; part=sys.stdin.read().split(".")[1]; claims=json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))); print(claims["tid"])')"
unset arm_access_token
case "$active_principal_type" in
  user|User) normalized_principal_type=User ;;
  *) printf 'Azure CLI must be signed in interactively as a User; service-principal login is not supported for rotation.\n' >&2; exit 1 ;;
esac
[[ "$active_subscription" == "$EXPECTED_SUBSCRIPTION_ID" ]] || { printf 'Active subscription mismatch.\n' >&2; exit 1; }
[[ "$active_tenant" == "$EXPECTED_TENANT_ID" && "$token_tenant_id" == "$EXPECTED_TENANT_ID" ]] || { printf 'Active tenant mismatch.\n' >&2; exit 1; }
[[ "$active_principal_id" == "$PRINCIPAL_ID" && "$normalized_principal_type" == "$PRINCIPAL_TYPE" ]] || { printf 'Current deployment principal mismatch.\n' >&2; exit 1; }

canonical_app_id="/subscriptions/${EXPECTED_SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.App/containerApps/${CONTAINER_APP_NAME}"
[[ "$EXPECTED_CONTAINER_APP_ID" == "$canonical_app_id" ]] || { printf 'Configured Container App ID is not the canonical confirmed subscription/resource-group/name binding.\n' >&2; exit 1; }
canonical_vault_id="/subscriptions/${EXPECTED_SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.KeyVault/vaults/${VAULT_NAME}"
[[ "$EXPECTED_VAULT_ID" == "$canonical_vault_id" ]] || { printf 'Configured Key Vault ID is not the canonical confirmed subscription/resource-group/name binding.\n' >&2; exit 1; }
[[ "$EXPECTED_VAULT_URI" == https://*.vault.azure.net/ ]] || { printf 'Configured Key Vault URI is not canonical.\n' >&2; exit 1; }

safe_capture vault_json rotation-vault az keyvault show --subscription "$EXPECTED_SUBSCRIPTION_ID" --name "$VAULT_NAME" --output json
actual_vault_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$vault_json")"
actual_vault_uri="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["properties"]["vaultUri"])' <<<"$vault_json")"
unset vault_json
[[ "$actual_vault_id" == "$EXPECTED_VAULT_ID" && "$actual_vault_uri" == "$EXPECTED_VAULT_URI" ]] || { printf 'Exact Key Vault ID/URI binding mismatch.\n' >&2; exit 1; }

safe_capture container_app_json rotation-container-app az containerapp show --subscription "$EXPECTED_SUBSCRIPTION_ID" --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_APP_NAME" --output json
APP_JSON="$container_app_json" EXPECTED_APP_ID="$EXPECTED_CONTAINER_APP_ID" EXPECTED_APP_NAME="$CONTAINER_APP_NAME" EXPECTED_SECRET_URL="${EXPECTED_VAULT_URI}secrets/entra-client-secret" python3 - <<'PY' || { printf 'Container App identity or Key Vault secret-reference binding mismatch.\n' >&2; exit 1; }
import json
import os

app = json.loads(os.environ["APP_JSON"])
if app.get("id") != os.environ["EXPECTED_APP_ID"]:
    raise SystemExit(1)
if app.get("name") != os.environ["EXPECTED_APP_NAME"]:
    raise SystemExit(1)
if "SystemAssigned" not in app.get("identity", {}).get("type", "").split(", "):
    raise SystemExit(1)
matches = [
    item
    for item in app.get("properties", {}).get("configuration", {}).get("secrets", [])
    if item.get("name") == "entra-client-secret"
]
if len(matches) != 1:
    raise SystemExit(1)
if matches[0].get("keyVaultUrl") != os.environ["EXPECTED_SECRET_URL"]:
    raise SystemExit(1)
if matches[0].get("identity") != "system":
    raise SystemExit(1)
PY
app_fqdn="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["properties"]["configuration"]["ingress"]["fqdn"])' <<<"$container_app_json")"
latest_ready_revision="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["properties"]["latestReadyRevisionName"])' <<<"$container_app_json")"
unset container_app_json
deployment_origin="https://${app_fqdn}"
[[ "$LIVE_BASE_URL" == "$deployment_origin" && "$EXPECTED_DEPLOYMENT_ORIGIN" == "$deployment_origin" ]] || { printf 'Live base URL and expected deployment origin must equal the exact Container App HTTPS origin.\n' >&2; exit 1; }

safe_capture active_revisions_json rotation-active-revision az containerapp revision list --subscription "$EXPECTED_SUBSCRIPTION_ID" --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_APP_NAME" --output json
active_revision="$(APP_ID="$EXPECTED_CONTAINER_APP_ID" APP_NAME="$CONTAINER_APP_NAME" EXPECTED_REVISION="$latest_ready_revision" python3 -c 'import json,os,sys; items=[item for item in json.load(sys.stdin) if item.get("properties", {}).get("active") is True]; expected_id=os.environ["APP_ID"]+"/revisions/"+os.environ["EXPECTED_REVISION"]; matches=[item["name"] for item in items if item.get("id")==expected_id and item.get("name")==os.environ["EXPECTED_REVISION"] and item.get("name", "").startswith(os.environ["APP_NAME"]+"--")]; print(matches[0] if len(matches)==1 and len(items)==1 else "")' <<<"$active_revisions_json")"
unset active_revisions_json
[[ -n "$active_revision" ]] || { printf 'The exact app does not have one active latest-ready revision belonging to it.\n' >&2; exit 1; }

configure_temporary_kv_operator_access "$EXPECTED_VAULT_ID" "$PRINCIPAL_ID" "$PRINCIPAL_TYPE"
create_temporary_kv_operator_access

secret_metadata=''
for attempt in {1..12}; do
  if safe_capture_ephemeral secret_metadata rotation-secret-metadata az keyvault secret list --vault-name "$VAULT_NAME" --query "[?name=='entra-client-secret']" --output json; then
    break
  fi
  [[ "$attempt" != 12 ]] || { printf 'Temporary Key Vault data-plane access did not propagate.\n' >&2; exit 1; }
  sleep 10
done
secret_count="$(python3 -c 'import json,sys; print(len(json.load(sys.stdin)))' <<<"$secret_metadata")"
unset secret_metadata
[[ "$secret_count" == 1 ]] || { printf 'Rotation requires exactly one current secret metadata record.\n' >&2; exit 1; }

safe_capture_ephemeral old_secret_id rotation-old-secret az keyvault secret show --vault-name "$VAULT_NAME" --name entra-client-secret --query id --output tsv
[[ -n "$old_secret_id" ]] || { printf 'Current secret version ID was empty.\n' >&2; exit 1; }
old_version="${old_secret_id##*/}"
[[ -n "$old_version" && "$old_version" != "$old_secret_id" ]] || { printf 'Current secret version ID was malformed.\n' >&2; exit 1; }
rollback_secret_file="${SAFE_DIAGNOSTICS_DIR}/rotation-rollback-secret"
install -m 600 /dev/null "$rollback_secret_file"
safe_run download-rotation-rollback az keyvault secret download --vault-name "$VAULT_NAME" --name entra-client-secret --version "$old_version" --file "$rollback_secret_file" --encoding utf-8 --output none
valid_secret_file "$rollback_secret_file" || { printf 'Downloaded rollback secret failed validation.\n' >&2; exit 1; }

rotation_needs_rollback=true
if ! safe_capture_ephemeral new_secret_id rotation-new-secret az keyvault secret set --vault-name "$VAULT_NAME" --name entra-client-secret --file "$REPLACEMENT_FILE" --query id --output tsv; then
  printf 'New secret version was not confirmed; restoring the captured prior credential.\n' >&2
  exit 1
fi
[[ -n "$new_secret_id" && "$new_secret_id" != "$old_secret_id" ]] || { printf 'New secret version did not advance.\n' >&2; exit 1; }

rotation_failed=false
safe_run restart-rotated-revision az containerapp revision restart --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_APP_NAME" --revision "$active_revision" || rotation_failed=true
if [[ "$rotation_failed" == false ]]; then
  safe_run deployed-workiq-obo npm --prefix "${repo_root}/apps/web" run test:e2e -- --project=live || rotation_failed=true
fi
if [[ "$rotation_failed" == true ]]; then
  safe_run restore-prior-secret az keyvault secret set --vault-name "$VAULT_NAME" --name entra-client-secret --file "$rollback_secret_file" --output none
  safe_run restart-rollback-revision az containerapp revision restart --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_APP_NAME" --revision "$active_revision"
  safe_run verify-rollback-obo npm --prefix "${repo_root}/apps/web" run test:e2e -- --project=live
  rotation_needs_rollback=false
  printf 'Rotation failed; the prior credential was restored and verified.\n' >&2
  cleanup_rotation_lifecycle
  exit 1
fi

rotation_needs_rollback=false
cleanup_rotation_lifecycle
printf 'Rotation completed; deployed Work IQ/OBO passed and temporary access was removed.\n'
