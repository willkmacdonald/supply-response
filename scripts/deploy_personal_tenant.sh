#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
source "${script_dir}/lib/safe_command.sh"
source "${script_dir}/lib/key_vault_operator_access.sh"
source "${script_dir}/lib/deployment_health.sh"
source "${script_dir}/lib/workiq_binding.sh"
safe_init_diagnostics

EXPECTED_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:?Set AZURE_SUBSCRIPTION_ID to the separately confirmed target}"
EXPECTED_TENANT_ID="${AZURE_TENANT_ID:?Set AZURE_TENANT_ID to the separately confirmed target}"
EXPECTED_LOCATION="${AZURE_LOCATION:?Set AZURE_LOCATION to the separately confirmed target}"
EXPECTED_RESOURCE_GROUP="${SUPPLY_RESPONSE_RESOURCE_GROUP:?Set SUPPLY_RESPONSE_RESOURCE_GROUP to the separately confirmed target}"
EXPECTED_CONTAINER_APP_NAME="${SUPPLY_RESPONSE_CONTAINER_APP_NAME:?Set SUPPLY_RESPONSE_CONTAINER_APP_NAME to the confirmed bounded name}"
DEPLOYMENT_PRINCIPAL_TYPE="${SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_TYPE:?Set User for the current interactive deployment principal}"
FINAL_PROVISION_MAX_ATTEMPTS="${FINAL_PROVISION_MAX_ATTEMPTS:-6}"
SMOKE_MAX_ATTEMPTS="${SMOKE_MAX_ATTEMPTS:-12}"
PLACEHOLDER_IMAGE='mcr.microsoft.com/k8se/quickstart:latest'
MODE=dry-run

safe_before_diagnostics_cleanup() {
  if [[ "$KV_OPERATOR_CLEANUP_ACTIVE" == true ]]; then
    printf 'Interrupted bootstrap detected; attempting exact temporary operator-role removal.\n' >&2
    cleanup_temporary_kv_operator_access
  fi
}

[[ "$FINAL_PROVISION_MAX_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] || { printf 'FINAL_PROVISION_MAX_ATTEMPTS must be a positive integer.\n' >&2; exit 2; }
[[ "$SMOKE_MAX_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] || { printf 'SMOKE_MAX_ATTEMPTS must be a positive integer.\n' >&2; exit 2; }
[[ "$DEPLOYMENT_PRINCIPAL_TYPE" == User ]] || { printf 'This personal-tenant workflow supports only an interactive User deployment principal; ServicePrincipal is not supported.\n' >&2; exit 1; }

case "${1:-}" in
  "") ;;
  --apply) MODE=apply ;;
  --smoke) MODE=smoke ;;
  *) printf 'Usage: %s [--apply|--smoke]\n' "$0" >&2; exit 2 ;;
esac
(( $# <= 1 )) || { printf 'Usage: %s [--apply|--smoke]\n' "$0" >&2; exit 2; }

validate_workiq_binding
"${script_dir}/preflight_personal_tenant.sh"

resource_group="$EXPECTED_RESOURCE_GROUP"
app_name="$EXPECTED_CONTAINER_APP_NAME"

app_coordinates() {
  local app_fqdn
  safe_capture app_fqdn app-fqdn az containerapp show --resource-group "$resource_group" --name "$app_name" --query properties.configuration.ingress.fqdn --output tsv
  app_url="https://${app_fqdn}"
}

smoke_gate() {
  local smoke_dir attempt
  smoke_dir="$(mktemp -d)"
  chmod 700 "$smoke_dir"
  for ((attempt=1; attempt<=SMOKE_MAX_ATTEMPTS; attempt++)); do
    if safe_run smoke-health curl --connect-timeout 5 --max-time 10 -fsS "${app_url}/health" -o "${smoke_dir}/health.json" \
      && safe_run smoke-runtime curl --connect-timeout 5 --max-time 10 -fsS "${app_url}/api/runtime" -o "${smoke_dir}/runtime.json" \
      && validate_live_smoke_contract "${smoke_dir}/health.json" "${smoke_dir}/runtime.json"
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
then waits for managed-identity RBAC, seeds a protected-file secret only on a
true bootstrap with no existing version, builds an
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

build_context_changes="$(git -C "$repo_root" status --porcelain=v1 --untracked-files=all -- .dockerignore Dockerfile pyproject.toml uv.lock apps agents data integrations services migrations)"
if [[ -n "$build_context_changes" ]]; then
  printf 'Refusing to build: a tracked or untracked deployment build-context path is dirty. Commit or remove those changes first.\n' >&2
  exit 1
fi
unset build_context_changes

last_provision_log=''
run_provision() {
  local label="$1"
  if safe_run "$label" azd provision --no-prompt; then
    return 0
  fi
  last_provision_log="$SAFE_LAST_STDERR"
  return 1
}

required_runtime_settings=(
  SUPPLY_RESPONSE_API_CLIENT_ID SUPPLY_RESPONSE_ALEX_OBJECT_ID
  SUPPLY_RESPONSE_FABRIC_SQL_SERVER SUPPLY_RESPONSE_FABRIC_SQL_DATABASE
  SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SOURCE_ID SUPPLY_RESPONSE_WORKIQ_QUALITY_SOURCE_ID
  SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SENDER SUPPLY_RESPONSE_WORKIQ_QUALITY_AUTHOR_OBJECT_ID
  SUPPLY_RESPONSE_WORKIQ_TEAM_ID SUPPLY_RESPONSE_WORKIQ_CHANNEL_ID
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
  safe_run "azd-setting-${setting}" azd env set "$setting" "${!setting}"
done
# Acceptance is external to deployment; blank explicitly deactivates new links.
safe_run azd-setting-SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT azd env set SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT "${SUPPLY_RESPONSE_POWER_BI_REPORTING_RECEIPT:-}"
# Recognition and workflow activation are distinct. Legacy deployments stay off.
safe_run azd-setting-SUPPLY_RESPONSE_TAYLOR_OBJECT_ID azd env set SUPPLY_RESPONSE_TAYLOR_OBJECT_ID "${SUPPLY_RESPONSE_TAYLOR_OBJECT_ID:-}"
safe_run azd-setting-SUPPLY_RESPONSE_INDEPENDENT_FINANCE_ENABLED azd env set SUPPLY_RESPONSE_INDEPENDENT_FINANCE_ENABLED "${SUPPLY_RESPONSE_INDEPENDENT_FINANCE_ENABLED:-false}"
uuid_pattern='^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
[[ "${SUPPLY_RESPONSE_API_CLIENT_ID}" =~ $uuid_pattern ]] || { printf 'SUPPLY_RESPONSE_API_CLIENT_ID must be a UUID.\n' >&2; exit 1; }
[[ "${SUPPLY_RESPONSE_WEB_CLIENT_ID:-}" =~ $uuid_pattern ]] || { printf 'SUPPLY_RESPONSE_WEB_CLIENT_ID must be a UUID.\n' >&2; exit 1; }
api_scope="api://${SUPPLY_RESPONSE_API_CLIENT_ID}/access_as_user"

verify_existing_final_health() {
  local health_file="${SAFE_DIAGNOSTICS_DIR}/existing-health.json" attempt
  : >"$health_file"
  chmod 600 "$health_file"
  for attempt in {1..6}; do
    if safe_run existing-health curl --connect-timeout 5 --max-time 10 -fsS "${app_url}/health" -o "$health_file" \
      && validate_existing_final_health_contract "$health_file"
    then
      return 0
    fi
    sleep $(( attempt * 5 ))
  done
  return 1
}

existing_app_json=''
started_from_bootstrap=false
if safe_capture_quiet existing_app_json existing-app az containerapp show --resource-group "$resource_group" --name "$app_name" --output json; then
  existing_app_image="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["properties"]["template"]["containers"][0]["image"])' <<<"$existing_app_json")"
  existing_identity_type="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("identity", {}).get("type", ""))' <<<"$existing_app_json")"
  app_url="https://$(python3 -c 'import json,sys; print(json.load(sys.stdin)["properties"]["configuration"]["ingress"]["fqdn"])' <<<"$existing_app_json")"
  if [[ "$existing_app_image" == "$PLACEHOLDER_IMAGE" || "$existing_identity_type" != *SystemAssigned* ]]; then
    started_from_bootstrap=true
    safe_run azd-bootstrap-existing azd env set SUPPLY_RESPONSE_BOOTSTRAP_MODE true
    run_provision bootstrap-existing || exit 1
  else
    verify_existing_final_health || { printf 'Existing non-placeholder app is not a healthy live revision; refusing to replace it.\n' >&2; exit 1; }
  fi
else
  if ! grep -Eiq 'ResourceNotFound|not found|could not be found' "$SAFE_LAST_STDERR"; then
    printf 'Could not safely determine whether the Container App exists.\n' >&2
    safe_report_failure existing-app
    exit 1
  fi
  started_from_bootstrap=true
  safe_run azd-bootstrap-new azd env set SUPPLY_RESPONSE_BOOTSTRAP_MODE true
  run_provision bootstrap-new || exit 1
  app_coordinates
fi
unset existing_app_json

expected_redirect_uri="${app_url}/auth/callback"
[[ "${SUPPLY_RESPONSE_REDIRECT_URI:-}" == "$expected_redirect_uri" ]] || { printf 'SUPPLY_RESPONSE_REDIRECT_URI must exactly match the Container App callback.\n' >&2; exit 1; }

safe_capture vault_name vault-name azd env get-value SUPPLY_RESPONSE_KEY_VAULT_NAME
safe_capture registry_server registry-server azd env get-value SUPPLY_RESPONSE_ACR_LOGIN_SERVER
registry_name="${registry_server%%.*}"
safe_capture principal_id app-principal az containerapp identity show --resource-group "$resource_group" --name "$app_name" --query principalId --output tsv
safe_capture registry_id registry-resource az acr show --name "$registry_name" --query id --output tsv
safe_capture vault_id vault-resource az keyvault show --name "$vault_name" --query id --output tsv
for attempt in {1..12}; do
  safe_capture acr_ready acr-pull-role az role assignment list --assignee-object-id "$principal_id" --scope "$registry_id" --role AcrPull --query 'length(@)' --output tsv
  safe_capture vault_ready vault-user-role az role assignment list --assignee-object-id "$principal_id" --scope "$vault_id" --role 'Key Vault Secrets User' --query 'length(@)' --output tsv
  if [[ "$acr_ready" -ge 1 && "$vault_ready" -ge 1 ]]; then break; fi
  if [[ "$attempt" == 12 ]]; then printf 'Managed-identity role records did not appear in time; the existing active revision was preserved.\n' >&2; exit 1; fi
  sleep 10
done

wait_for_bootstrap_operator_access() {
  local secret_metadata_json attempt
  for attempt in {1..12}; do
    if safe_capture_ephemeral secret_metadata_json bootstrap-secret-metadata az keyvault secret list --vault-name "$vault_name" --query "[?name=='entra-client-secret']" --output json; then
      existing_secret_count="$(python3 -c 'import json,sys; print(len(json.load(sys.stdin)))' <<<"$secret_metadata_json")"
      unset secret_metadata_json
      return 0
    fi
    sleep 10
  done
  printf 'Temporary Key Vault Secrets Officer assignment or data-plane access did not propagate in time.\n' >&2
  return 1
}

validate_secret_file() {
  local secret_file="$1"
  [[ -f "$secret_file" ]] || { printf 'SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE must identify a protected file.\n' >&2; return 1; }
  valid_secret_file "$secret_file" || { printf 'secret file must contain exactly one line without a trailing newline; it must also be a nonsymlink regular file owned by the current user with no group/world permissions.\n' >&2; return 1; }
}

if [[ "$started_from_bootstrap" == true ]]; then
  configure_temporary_kv_operator_access "$vault_id" "$SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_ID" "$DEPLOYMENT_PRINCIPAL_TYPE"
  create_temporary_kv_operator_access
  wait_for_bootstrap_operator_access
  if [[ "$existing_secret_count" == 0 ]]; then
    secret_file="${SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE:-}"
    validate_secret_file "$secret_file"
    safe_run seed-entra-secret az keyvault secret set --vault-name "$vault_name" --name entra-client-secret --file "$secret_file" --output none
  elif [[ "$existing_secret_count" == 1 ]]; then
    printf 'Bootstrap detected an existing seed version; preserving it. Normal apply never rotates this secret.\n'
  else
    printf 'Secret metadata was ambiguous; refusing to select or create a version.\n' >&2
    cleanup_temporary_kv_operator_access || true
    exit 1
  fi
  cleanup_temporary_kv_operator_access
  printf 'Temporary bootstrap operator Key Vault role removed.\n'
fi
git_revision="$(git -C "$repo_root" rev-parse --short=12 HEAD)"
public_config_digest="$(printf '%s\n' "$EXPECTED_TENANT_ID" "${SUPPLY_RESPONSE_WEB_CLIENT_ID}" "$api_scope" "$expected_redirect_uri" | python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest()[:16])')"
image_tag="${git_revision}-${public_config_digest}"
safe_run acr-build az acr build --registry "$registry_name" --image "supply-response:${image_tag}" \
  --build-arg "VITE_ENTRA_TENANT_ID=${EXPECTED_TENANT_ID}" \
  --build-arg "VITE_ENTRA_WEB_CLIENT_ID=${SUPPLY_RESPONSE_WEB_CLIENT_ID}" \
  --build-arg "VITE_ENTRA_API_SCOPE=${api_scope}" \
  --build-arg "VITE_ENTRA_REDIRECT_URI=${expected_redirect_uri}" \
  "$repo_root" --output none
safe_capture image_digest acr-manifest-digest az acr repository show --name "$registry_name" --image "supply-response:${image_tag}" --query digest --output tsv
[[ "$image_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || { printf 'ACR returned an invalid manifest digest; refusing a mutable image reference.\n' >&2; exit 1; }
image="${registry_server}/supply-response@${image_digest}"
safe_run azd-image-digest azd env set SUPPLY_RESPONSE_IMAGE_NAME "$image"

recognized_identity_binding_failure() {
  grep -Eiq 'unauthorized|authentication required|pull access denied|failed to pull|key vault.*(not found|forbidden|denied)|secret.*(not found|forbidden|denied)|managed identity.*(not found|forbidden|denied|propagat|permission)|identity.*(propagat|permission)' "$1"
}

restore_bootstrap_revision() {
  safe_run azd-restore-bootstrap azd env set SUPPLY_RESPONSE_BOOTSTRAP_MODE true
  run_provision restore-bootstrap
}

for ((attempt=1; attempt<=FINAL_PROVISION_MAX_ATTEMPTS; attempt++)); do
  safe_run azd-final-mode azd env set SUPPLY_RESPONSE_BOOTSTRAP_MODE false
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
