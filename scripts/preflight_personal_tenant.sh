#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/lib/safe_command.sh"
safe_init_diagnostics

EXPECTED_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:?Set AZURE_SUBSCRIPTION_ID to the separately confirmed target}"
EXPECTED_TENANT_ID="${AZURE_TENANT_ID:?Set AZURE_TENANT_ID to the separately confirmed target}"
EXPECTED_LOCATION="${AZURE_LOCATION:?Set AZURE_LOCATION to the separately confirmed target}"
EXPECTED_AZD_ENVIRONMENT="${SUPPLY_RESPONSE_AZD_ENVIRONMENT:?Set SUPPLY_RESPONSE_AZD_ENVIRONMENT to the selected azd environment}"
EXPECTED_CONTAINER_APP_NAME="${SUPPLY_RESPONSE_CONTAINER_APP_NAME:?Set the exact bounded Container App name}"
DEPLOYMENT_PRINCIPAL_ID="${SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_ID:?Set the confirmed current deployment principal object ID}"
DEPLOYMENT_PRINCIPAL_TYPE="${SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_TYPE:?Set User or ServicePrincipal for the current deployment principal}"
FOUNDRY_PROJECT_RESOURCE_ID="${SUPPLY_RESPONSE_FOUNDRY_PROJECT_RESOURCE_ID:?Set the canonical Foundry project resource ID}"
FOUNDRY_PROJECT_ENDPOINT="${SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT:?Set the canonical Foundry project endpoint}"
FABRIC_WORKSPACE_ID="${SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID:?Set the exact Fabric workspace ID}"
FABRIC_SQL_DATABASE_ID="${SUPPLY_RESPONSE_FABRIC_SQL_DATABASE_ID:?Set the exact Fabric SQL Database item ID}"
API_CLIENT_ID="${SUPPLY_RESPONSE_API_CLIENT_ID:?Set the exact API application client ID}"
WEB_CLIENT_ID="${SUPPLY_RESPONSE_WEB_CLIENT_ID:?Set the exact Web application client ID}"
REGISTERED_REDIRECT_URI="${SUPPLY_RESPONSE_REDIRECT_URI:?Set the exact registered SPA redirect URI}"
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
require_command azd
require_command python3

if ! valid_container_app_name "$EXPECTED_CONTAINER_APP_NAME"; then
  printf 'SUPPLY_RESPONSE_CONTAINER_APP_NAME must be 2-32 lowercase letters, numbers, or hyphens, starting with a letter, ending alphanumeric, and containing no consecutive hyphens.\n' >&2
  exit 1
fi
uuid_pattern='^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
[[ "$DEPLOYMENT_PRINCIPAL_ID" =~ $uuid_pattern ]] || { printf 'SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_ID must be a UUID.\n' >&2; exit 1; }
[[ "$DEPLOYMENT_PRINCIPAL_TYPE" == User || "$DEPLOYMENT_PRINCIPAL_TYPE" == ServicePrincipal ]] || { printf 'SUPPLY_RESPONSE_DEPLOYMENT_PRINCIPAL_TYPE must be User or ServicePrincipal.\n' >&2; exit 1; }

safe_capture active_subscription account-subscription az account show --query id --output tsv
safe_capture active_tenant account-tenant az account show --query tenantId --output tsv
safe_capture active_principal_type account-principal-type az account show --query user.type --output tsv
safe_capture_ephemeral arm_access_token current-arm-token az account get-access-token --resource https://management.azure.com/ --query accessToken --output tsv
current_principal_id="$(printf '%s' "$arm_access_token" | python3 -c 'import base64,json,sys; part=sys.stdin.read().split(".")[1]; claims=json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))); print(claims["oid"])')"
arm_token_tid="$(printf '%s' "$arm_access_token" | python3 -c 'import base64,json,sys; part=sys.stdin.read().split(".")[1]; claims=json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))); print(claims["tid"])')"
unset arm_access_token
safe_capture selected_azd_environment azd-environment azd env get-value AZURE_ENV_NAME
assert_equal subscription "$active_subscription" "$EXPECTED_SUBSCRIPTION_ID"
assert_equal tenant "$active_tenant" "$EXPECTED_TENANT_ID"
assert_equal 'azd environment' "$selected_azd_environment" "$EXPECTED_AZD_ENVIRONMENT"
case "$active_principal_type" in
  user|User)
    current_principal_type=User
    ;;
  servicePrincipal|serviceprincipal|ServicePrincipal)
    current_principal_type=ServicePrincipal
    ;;
  *)
    printf 'Azure CLI current principal type is unsupported.\n' >&2
    exit 1
    ;;
esac
assert_equal 'ARM access-token tenant' "$arm_token_tid" "$EXPECTED_TENANT_ID"
assert_equal 'current deployment principal type' "$current_principal_type" "$DEPLOYMENT_PRINCIPAL_TYPE"
assert_equal 'current deployment principal ID' "$current_principal_id" "$DEPLOYMENT_PRINCIPAL_ID"

safe_capture environment_json container-environment az containerapp env show --subscription "$EXPECTED_SUBSCRIPTION_ID" --resource-group "$SHARED_RESOURCE_GROUP" --name "$SHARED_ENVIRONMENT" --output json
environment_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$environment_json")"
environment_location="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["location"].lower().replace(" ", ""))' <<<"$environment_json")"
environment_internal="$(python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("properties", {}).get("vnetConfiguration", {}).get("internal", False)).lower())' <<<"$environment_json")"
environment_law_customer_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("properties", {}).get("appLogsConfiguration", {}).get("logAnalyticsConfiguration", {}).get("customerId", ""))' <<<"$environment_json")"
environment_default_domain="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("properties", {}).get("defaultDomain", ""))' <<<"$environment_json")"
consumption_profiles="$(python3 -c 'import json,sys; print(sum(1 for item in json.load(sys.stdin).get("properties", {}).get("workloadProfiles", []) if item.get("workloadProfileType") == "Consumption" or item.get("name") == "Consumption"))' <<<"$environment_json")"
unset environment_json
assert_equal location "$environment_location" "$EXPECTED_LOCATION"
assert_equal 'Container Apps environment network mode' "$environment_internal" false
[[ "$consumption_profiles" -ge 1 ]] || { printf 'Shared environment does not expose a Consumption workload profile.\n' >&2; exit 1; }
expected_redirect_uri="https://${EXPECTED_CONTAINER_APP_NAME}.${environment_default_domain}/auth/callback"
assert_equal 'registered Container App redirect' "$REGISTERED_REDIRECT_URI" "$expected_redirect_uri"

safe_capture web_app_json web-application az ad app show --id "$WEB_CLIENT_ID" --output json
web_app_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["appId"])' <<<"$web_app_json")"
web_redirects="$(python3 -c 'import json,sys; print("\n".join(json.load(sys.stdin).get("spa", {}).get("redirectUris", [])))' <<<"$web_app_json")"
unset web_app_json
assert_equal 'Web application client' "$web_app_id" "$WEB_CLIENT_ID"
assert_equal 'Web application redirect set' "$web_redirects" "$REGISTERED_REDIRECT_URI"

safe_capture api_app_json api-application az ad app show --id "$API_CLIENT_ID" --output json
api_app_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["appId"])' <<<"$api_app_json")"
api_scope_count="$(python3 -c 'import json,sys; print(sum(1 for scope in json.load(sys.stdin).get("api", {}).get("oauth2PermissionScopes", []) if scope.get("value") == "access_as_user" and scope.get("isEnabled") is True))' <<<"$api_app_json")"
unset api_app_json
assert_equal 'API application client' "$api_app_id" "$API_CLIENT_ID"
assert_equal 'enabled access_as_user scope count' "$api_scope_count" 1

safe_capture registry_id registry-id az acr show --subscription "$EXPECTED_SUBSCRIPTION_ID" --resource-group "$SHARED_RESOURCE_GROUP" --name "$SHARED_REGISTRY" --query id --output tsv
safe_capture registry_sku registry-sku az acr show --subscription "$EXPECTED_SUBSCRIPTION_ID" --resource-group "$SHARED_RESOURCE_GROUP" --name "$SHARED_REGISTRY" --query sku.name --output tsv
assert_equal 'ACR SKU' "$registry_sku" Standard

safe_capture workspace_json log-analytics-workspace az monitor log-analytics workspace show --subscription "$EXPECTED_SUBSCRIPTION_ID" --resource-group "$SHARED_RESOURCE_GROUP" --workspace-name "$SHARED_WORKSPACE" --output json
workspace_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$workspace_json")"
workspace_customer_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["customerId"])' <<<"$workspace_json")"
unset workspace_json
assert_equal 'Container Apps Log Analytics binding' "$environment_law_customer_id" "$workspace_customer_id"

if [[ ! "$FOUNDRY_PROJECT_RESOURCE_ID" =~ ^/subscriptions/([^/]+)/resourceGroups/([^/]+)/providers/Microsoft\.CognitiveServices/accounts/([^/]+)/projects/([^/]+)$ ]]; then
  printf 'Foundry project ID must use the canonical Microsoft.CognitiveServices/accounts/projects resource path.\n' >&2
  exit 1
fi
foundry_subscription_id="${BASH_REMATCH[1]}"
foundry_account_name="${BASH_REMATCH[3]}"
foundry_project_name="${BASH_REMATCH[4]}"
assert_equal 'Foundry subscription' "$foundry_subscription_id" "$EXPECTED_SUBSCRIPTION_ID"
safe_capture foundry_type foundry-project az resource show --ids "$FOUNDRY_PROJECT_RESOURCE_ID" --api-version 2025-06-01 --query type --output tsv
assert_equal 'Foundry resource type' "$foundry_type" 'Microsoft.CognitiveServices/accounts/projects'
expected_foundry_endpoint="https://${foundry_account_name}.services.ai.azure.com/api/projects/${foundry_project_name}"
assert_equal 'Foundry project endpoint' "$FOUNDRY_PROJECT_ENDPOINT" "$expected_foundry_endpoint"

safe_capture fabric_workspace_id fabric-workspace az rest --method get --url "https://api.fabric.microsoft.com/v1/workspaces/${FABRIC_WORKSPACE_ID}" --query id --output tsv
fabric_item_contract=("type" "SQLDatabase")
safe_capture fabric_database_json fabric-database az rest --method get --url "https://api.fabric.microsoft.com/v1/workspaces/${FABRIC_WORKSPACE_ID}/items/${FABRIC_SQL_DATABASE_ID}" --output json
fabric_database_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$fabric_database_json")"
fabric_database_type="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["type"])' <<<"$fabric_database_json")"
unset fabric_database_json
assert_equal 'Fabric workspace' "$fabric_workspace_id" "$FABRIC_WORKSPACE_ID"
assert_equal 'Fabric SQL item' "$fabric_database_id" "$FABRIC_SQL_DATABASE_ID"
assert_equal "Fabric item ${fabric_item_contract[0]}" "$fabric_database_type" "${fabric_item_contract[1]}"

safe_capture_ephemeral fabric_access_token fabric-token az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken --output tsv
fabric_token_tid="$(printf '%s' "$fabric_access_token" | python3 -c 'import base64,json,sys; part=sys.stdin.read().split(".")[1]; print(json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))["tid"])')"
unset fabric_access_token
assert_equal 'Fabric access-token tenant' "$fabric_token_tid" "$EXPECTED_TENANT_ID"

printf 'Preflight passed: subscription=%s tenant=%s location=%s azd=%s\n' "$(redact "$active_subscription")" "$(redact "$active_tenant")" "$EXPECTED_LOCATION" "$EXPECTED_AZD_ENVIRONMENT"
printf 'Shared resources verified: environment=%s registry=%s workspace=%s\n' "$(redact "$environment_id")" "$(redact "$registry_id")" "$(redact "$workspace_id")"
printf 'Foundry project and Fabric SQL Database verified without printing credentials or tokens.\n'
printf 'No cloud resources were modified.\n'
