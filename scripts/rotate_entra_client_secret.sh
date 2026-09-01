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
VAULT_NAME="${SUPPLY_RESPONSE_KEY_VAULT_NAME:?Set the exact Key Vault name}"
RESOURCE_GROUP="${SUPPLY_RESPONSE_RESOURCE_GROUP:?Set the exact app resource group}"
CONTAINER_APP_NAME="${SUPPLY_RESPONSE_CONTAINER_APP_NAME:?Set the exact Container App name}"
PRINCIPAL_ID="${SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_ID:?Set the confirmed current principal object ID}"
PRINCIPAL_TYPE="${SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_TYPE:?Set User or ServicePrincipal}"
REPLACEMENT_FILE="${SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE:?Set the replacement secret file}"

[[ "${CONFIRM_SUBSCRIPTION_ID:-}" == "$EXPECTED_SUBSCRIPTION_ID" ]] || { printf 'CONFIRM_SUBSCRIPTION_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_TENANT_ID:-}" == "$EXPECTED_TENANT_ID" ]] || { printf 'CONFIRM_TENANT_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_VAULT_ID:-}" == "$EXPECTED_VAULT_ID" ]] || { printf 'CONFIRM_VAULT_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_CONTAINER_APP_NAME:-}" == "$CONTAINER_APP_NAME" ]] || { printf 'CONFIRM_CONTAINER_APP_NAME does not match.\n' >&2; exit 1; }
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
  servicePrincipal|serviceprincipal|ServicePrincipal) normalized_principal_type=ServicePrincipal ;;
  *) printf 'Current Azure principal type is unsupported.\n' >&2; exit 1 ;;
esac
[[ "$active_subscription" == "$EXPECTED_SUBSCRIPTION_ID" ]] || { printf 'Active subscription mismatch.\n' >&2; exit 1; }
[[ "$active_tenant" == "$EXPECTED_TENANT_ID" && "$token_tenant_id" == "$EXPECTED_TENANT_ID" ]] || { printf 'Active tenant mismatch.\n' >&2; exit 1; }
[[ "$active_principal_id" == "$PRINCIPAL_ID" && "$normalized_principal_type" == "$PRINCIPAL_TYPE" ]] || { printf 'Current deployment principal mismatch.\n' >&2; exit 1; }

safe_capture actual_vault_id rotation-vault az keyvault show --name "$VAULT_NAME" --query id --output tsv
[[ "$actual_vault_id" == "$EXPECTED_VAULT_ID" ]] || { printf 'Exact Key Vault ID mismatch.\n' >&2; exit 1; }
safe_capture active_revision rotation-active-revision az containerapp revision list --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_APP_NAME" --query '[?properties.active].name | [0]' --output tsv
[[ -n "$active_revision" ]] || { printf 'No active Container App revision was found.\n' >&2; exit 1; }

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
