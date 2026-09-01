#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:?Set AZURE_SUBSCRIPTION_ID to the separately confirmed target}"
EXPECTED_TENANT_ID="${AZURE_TENANT_ID:?Set AZURE_TENANT_ID to the separately confirmed target}"
EXPECTED_LOCATION="${AZURE_LOCATION:?Set AZURE_LOCATION to the separately confirmed target}"
SHARED_RESOURCE_GROUP="${SUPPLY_RESPONSE_SHARED_RESOURCE_GROUP:-shared-services-rg}"
SHARED_ENVIRONMENT="${SUPPLY_RESPONSE_SHARED_CONTAINER_APPS_ENVIRONMENT:-shared-services-env}"
SHARED_REGISTRY="${SUPPLY_RESPONSE_SHARED_REGISTRY:-wkmsharedservicesacr}"
SHARED_WORKSPACE="${SUPPLY_RESPONSE_SHARED_LOG_ANALYTICS_WORKSPACE:-shared-services-logs}"

redact() {
  local value="$1"
  if (( ${#value} < 9 )); then printf '%s' '[redacted]'; else printf '%s…%s' "${value:0:4}" "${value: -4}"; fi
}

require_command() {
  command -v "$1" >/dev/null || { printf 'Missing required command: %s\n' "$1" >&2; exit 1; }
}

assert_equal() {
  local label="$1" actual="$2" expected="$3"
  if [[ "$actual" != "$expected" ]]; then
    printf '%s mismatch (actual %s, expected %s).\n' "$label" "$(redact "$actual")" "$(redact "$expected")" >&2
    exit 1
  fi
}

require_command az
active_subscription="$(az account show --query id --output tsv)"
active_tenant="$(az account show --query tenantId --output tsv)"
assert_equal subscription "$active_subscription" "$EXPECTED_SUBSCRIPTION_ID"
assert_equal tenant "$active_tenant" "$EXPECTED_TENANT_ID"

environment_id="$(az containerapp env show --subscription "$EXPECTED_SUBSCRIPTION_ID" --resource-group "$SHARED_RESOURCE_GROUP" --name "$SHARED_ENVIRONMENT" --query id --output tsv)"
registry_id="$(az acr show --subscription "$EXPECTED_SUBSCRIPTION_ID" --resource-group "$SHARED_RESOURCE_GROUP" --name "$SHARED_REGISTRY" --query id --output tsv)"
workspace_id="$(az monitor log-analytics workspace show --subscription "$EXPECTED_SUBSCRIPTION_ID" --resource-group "$SHARED_RESOURCE_GROUP" --workspace-name "$SHARED_WORKSPACE" --query id --output tsv)"
environment_location="$(az containerapp env show --subscription "$EXPECTED_SUBSCRIPTION_ID" --resource-group "$SHARED_RESOURCE_GROUP" --name "$SHARED_ENVIRONMENT" --query location --output tsv | tr '[:upper:]' '[:lower:]' | tr -d ' ')"
assert_equal location "$environment_location" "$EXPECTED_LOCATION"

if [[ -n "${SUPPLY_RESPONSE_FOUNDRY_PROJECT_RESOURCE_ID:-}" ]]; then
  foundry_id="$(az resource show --ids "$SUPPLY_RESPONSE_FOUNDRY_PROJECT_RESOURCE_ID" --query id --output tsv)"
  foundry_subscription="$(cut -d/ -f3 <<<"$foundry_id")"
  assert_equal 'Foundry subscription' "$foundry_subscription" "$EXPECTED_SUBSCRIPTION_ID"
fi

if [[ -n "${SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID:-}" ]]; then
  [[ -n "${SUPPLY_RESPONSE_FABRIC_SQL_DATABASE_ID:-}" ]] || { printf 'Fabric workspace is configured but Fabric SQL item ID is missing.\n' >&2; exit 1; }
  fabric_workspace_id="$(az rest --method get --url "https://api.fabric.microsoft.com/v1/workspaces/${SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID}" --query id --output tsv)"
  fabric_database_id="$(az rest --method get --url "https://api.fabric.microsoft.com/v1/workspaces/${SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID}/items/${SUPPLY_RESPONSE_FABRIC_SQL_DATABASE_ID}" --query id --output tsv)"
  assert_equal 'Fabric workspace' "$fabric_workspace_id" "$SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID"
  assert_equal 'Fabric SQL item' "$fabric_database_id" "$SUPPLY_RESPONSE_FABRIC_SQL_DATABASE_ID"
fi

printf 'Preflight passed: subscription=%s tenant=%s location=%s\n' "$(redact "$active_subscription")" "$(redact "$active_tenant")" "$EXPECTED_LOCATION"
printf 'Shared resources verified: environment=%s registry=%s workspace=%s\n' "$(redact "$environment_id")" "$(redact "$registry_id")" "$(redact "$workspace_id")"
printf 'No cloud resources were modified.\n'
