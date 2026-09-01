#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:?Set AZURE_SUBSCRIPTION_ID to the separately confirmed target}"
EXPECTED_TENANT_ID="${AZURE_TENANT_ID:?Set AZURE_TENANT_ID to the separately confirmed target}"
EXPECTED_LOCATION="${AZURE_LOCATION:?Set AZURE_LOCATION to the separately confirmed target}"
EXPECTED_RESOURCE_GROUP="${SUPPLY_RESPONSE_RESOURCE_GROUP:?Set SUPPLY_RESPONSE_RESOURCE_GROUP to the separately confirmed target}"
APPLY=false

if [[ "${1:-}" == "--apply" ]]; then APPLY=true; shift; fi
if (( $# )); then printf 'Usage: %s [--apply]\n' "$0" >&2; exit 2; fi

"$(dirname "$0")/preflight_personal_tenant.sh"

if [[ "$APPLY" != true ]]; then
  cat <<'EOF'
DRY RUN ONLY. No Azure resource was changed.
The apply workflow will: provision the placeholder app; wait for managed-identity
RBAC; write a secret from a protected file; bind Key Vault and ACR using system
identity; build/push the image; configure live settings; and smoke-test /health.
Re-run with --apply only after the separate cloud-mutation approval and exact
confirmation variables documented in docs/deployment/personal-tenant.md.
EOF
  exit 0
fi

[[ "${CONFIRM_SUBSCRIPTION_ID:-}" == "$EXPECTED_SUBSCRIPTION_ID" ]] || { printf 'CONFIRM_SUBSCRIPTION_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_TENANT_ID:-}" == "$EXPECTED_TENANT_ID" ]] || { printf 'CONFIRM_TENANT_ID does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_LOCATION:-}" == "$EXPECTED_LOCATION" ]] || { printf 'CONFIRM_LOCATION does not match.\n' >&2; exit 1; }
[[ "${CONFIRM_RESOURCE_GROUP:-}" == "$EXPECTED_RESOURCE_GROUP" ]] || { printf 'CONFIRM_RESOURCE_GROUP does not match.\n' >&2; exit 1; }
[[ -f "${SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE:-}" ]] || { printf 'SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE must identify a protected file.\n' >&2; exit 1; }
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
done

azd provision --no-prompt

resource_group="$(azd env get-value AZURE_RESOURCE_GROUP)"
app_name="$(azd env get-value SERVICE_API_NAME)"
vault_name="$(azd env get-value SUPPLY_RESPONSE_KEY_VAULT_NAME)"
registry_server="$(azd env get-value SUPPLY_RESPONSE_ACR_LOGIN_SERVER)"
registry_name="${registry_server%%.*}"

# Role assignments are idempotently created by Bicep. Poll exact roles and scopes.
principal_id="$(az containerapp identity show --resource-group "$resource_group" --name "$app_name" --query principalId --output tsv)"
registry_id="$(az acr show --name "$registry_name" --query id --output tsv)"
vault_id="$(az keyvault show --name "$vault_name" --query id --output tsv)"
for attempt in {1..12}; do
  acr_ready="$(az role assignment list --assignee-object-id "$principal_id" --scope "$registry_id" --role AcrPull --query 'length(@)' --output tsv)"
  vault_ready="$(az role assignment list --assignee-object-id "$principal_id" --scope "$vault_id" --role 'Key Vault Secrets User' --query 'length(@)' --output tsv)"
  if [[ "$acr_ready" -ge 1 && "$vault_ready" -ge 1 ]]; then break; fi
  if [[ "$attempt" == 12 ]]; then printf 'Managed-identity RBAC did not propagate in time; rerun safely.\n' >&2; exit 1; fi
  sleep 10
done

az keyvault secret set --vault-name "$vault_name" --name entra-client-secret --file "$SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET_FILE" --output none

image_tag="${SUPPLY_RESPONSE_IMAGE_TAG:-$(git rev-parse --short HEAD)}"
image="${registry_server}/supply-response:${image_tag}"
az acr build --registry "$registry_name" --image "supply-response:${image_tag}" . --output none
azd env set SUPPLY_RESPONSE_IMAGE_NAME "$image"
azd env set SUPPLY_RESPONSE_BOOTSTRAP_MODE false
azd provision --no-prompt
app_url="https://$(az containerapp show --resource-group "$resource_group" --name "$app_name" --query properties.configuration.ingress.fqdn --output tsv)"
runtime_env=(
  "SUPPLY_RESPONSE_FRONTEND_ORIGIN=${app_url}"
)
for setting in "${required_runtime_settings[@]}"; do runtime_env+=("${setting}=${!setting}"); done
az containerapp update --resource-group "$resource_group" --name "$app_name" --image "$image" --set-env-vars "${runtime_env[@]}" --output none

curl -fsS "${app_url}/health" >/dev/null
printf 'Deployment health check passed. Configure Fabric SQL grants and verify pinned Foundry agents using the separately approved procedures.\n'
