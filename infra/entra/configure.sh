#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mode=""
fixture=""

die() { echo "ERROR: $*" >&2; exit 1; }
require() { command -v "$1" >/dev/null 2>&1 || die "$1 is required"; }
is_uuid() { [[ "$1" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; }
need_uuid() { is_uuid "$2" || die "$1 must be a UUID"; }

while (($#)); do
  case "$1" in
    --dry-run|--check|--apply)
      [[ -z "$mode" ]] || die "choose exactly one of --dry-run, --check, or --apply"
      mode="${1#--}"
      ;;
    --fixture)
      shift
      (($#)) || die "--fixture requires a path"
      fixture="$1"
      ;;
    *) die "unknown argument: $1" ;;
  esac
  shift
done

[[ -n "$mode" ]] || die "choose --dry-run, --check, or --apply"
[[ "${SUPPLY_RESPONSE_CONFIRM_TENANT:-}" == "willmacdonald.com" ]] || die "set SUPPLY_RESPONSE_CONFIRM_TENANT=willmacdonald.com after confirming the directory"
expected_tenant="${SUPPLY_RESPONSE_EXPECTED_TENANT_ID:-}"
workiq_app_id="${SUPPLY_RESPONSE_WORKIQ_RESOURCE_APP_ID:-}"
redirect_uri="${SUPPLY_RESPONSE_REDIRECT_URI:-}"
need_uuid "SUPPLY_RESPONSE_EXPECTED_TENANT_ID" "$expected_tenant"
need_uuid "SUPPLY_RESPONSE_WORKIQ_RESOURCE_APP_ID" "$workiq_app_id"
[[ "$redirect_uri" =~ ^https:// || "$redirect_uri" =~ ^http://(localhost|127\.0\.0\.1)(:|/) ]] || die "SUPPLY_RESPONSE_REDIRECT_URI must be HTTPS or loopback HTTP"
require jq

if [[ "$mode" == "dry-run" ]]; then
  [[ -f "$fixture" ]] || die "--dry-run requires an existing --fixture file"
  active_tenant="$(jq -er '.activeTenantId' "$fixture")"
  organization_json="$(jq -c '{verifiedDomains: .verifiedDomains}' "$fixture")"
  workiq_json="$(jq -c '.workIqServicePrincipal' "$fixture")"
else
  [[ -z "$fixture" ]] || die "--fixture is valid only with --dry-run"
  require az
  active_tenant="$(az account show --query tenantId -o tsv)"
  organization_json="$(az rest --method GET --uri 'https://graph.microsoft.com/v1.0/organization?$select=id,verifiedDomains' --query 'value[0]' -o json)"
  workiq_json="$(az ad sp show --id "$workiq_app_id" -o json)"
fi

need_uuid "active Azure tenant" "$active_tenant"
[[ "$active_tenant" == "$expected_tenant" ]] || die "active tenant does not match SUPPLY_RESPONSE_EXPECTED_TENANT_ID"
jq -e '.verifiedDomains | map(select(.name == "willmacdonald.com" and (.isVerified == true or .isDefault == true))) | length == 1' <<<"$organization_json" >/dev/null || die "active tenant is not the verified willmacdonald.com directory"
[[ "$(jq -r '.appId' <<<"$workiq_json")" == "$workiq_app_id" ]] || die "Work IQ service principal app ID mismatch"
workiq_scope_count="$(jq '[.oauth2PermissionScopes[]? | select(.value == "WorkIQAgent.Ask" and .isEnabled == true)] | length' <<<"$workiq_json")"
[[ "$workiq_scope_count" == "1" ]] || die "WorkIQAgent.Ask scope is missing or ambiguous"
workiq_scope_id="$(jq -r '.oauth2PermissionScopes[] | select(.value == "WorkIQAgent.Ask" and .isEnabled == true) | .id' <<<"$workiq_json")"
need_uuid "WorkIQAgent.Ask scope ID" "$workiq_scope_id"

api_client_id="${SUPPLY_RESPONSE_API_CLIENT_ID:-}"
web_client_id="${SUPPLY_RESPONSE_WEB_CLIENT_ID:-}"
if [[ -f "$script_dir/.env.tenant" && "$mode" != "dry-run" ]]; then
  file_api_client_id="$(sed -n 's/^SUPPLY_RESPONSE_API_CLIENT_ID=//p' "$script_dir/.env.tenant")"
  file_web_client_id="$(sed -n 's/^SUPPLY_RESPONSE_WEB_CLIENT_ID=//p' "$script_dir/.env.tenant")"
  [[ "$(grep -c '^SUPPLY_RESPONSE_API_CLIENT_ID=' "$script_dir/.env.tenant")" == "1" ]] || die ".env.tenant API client ID is missing or ambiguous"
  [[ "$(grep -c '^SUPPLY_RESPONSE_WEB_CLIENT_ID=' "$script_dir/.env.tenant")" == "1" ]] || die ".env.tenant Web client ID is missing or ambiguous"
  api_client_id="${api_client_id:-$file_api_client_id}"
  web_client_id="${web_client_id:-$file_web_client_id}"
fi

if [[ "$mode" == "dry-run" ]]; then
  need_uuid "SUPPLY_RESPONSE_API_CLIENT_ID" "$api_client_id"
  need_uuid "SUPPLY_RESPONSE_WEB_CLIENT_ID" "$web_client_id"
  jq -e '.signInAudience == "AzureADMyOrg" and (.appRoles | length == 4) and (.api.oauth2PermissionScopes | map(select(.value == "access_as_user" and .isEnabled == true)) | length == 1)' "$script_dir/api-app.json" >/dev/null
  jq -e '.signInAudience == "AzureADMyOrg" and (.spa.redirectUris | length == 1)' "$script_dir/web-app.json" >/dev/null
  echo "DRY_RUN_VALID tenant=$active_tenant api=$api_client_id web=$web_client_id permission=WorkIQAgent.Ask scope=$workiq_scope_id"
  exit 0
fi

validate_apps() {
  need_uuid "SUPPLY_RESPONSE_API_CLIENT_ID" "$api_client_id"
  need_uuid "SUPPLY_RESPONSE_WEB_CLIENT_ID" "$web_client_id"
  api_json="$(az ad app show --id "$api_client_id" -o json)"
  web_json="$(az ad app show --id "$web_client_id" -o json)"
  jq -e --arg workiq "$workiq_app_id" --arg permission "$workiq_scope_id" '
    .signInAudience == "AzureADMyOrg"
    and ([.appRoles[] | select(.isEnabled == true) | .value] | sort == ["finance_approver","material_planner","quality_approver","response_approver"])
    and ([.api.oauth2PermissionScopes[] | select(.isEnabled == true) | .value] == ["access_as_user"])
    and ([.requiredResourceAccess[] | select(.resourceAppId == $workiq) | .resourceAccess[] | select(.id == $permission and .type == "Scope")] | length == 1)
  ' <<<"$api_json" >/dev/null || die "API registration does not match the required manifest"
  scope_id="$(jq -r '.api.oauth2PermissionScopes[] | select(.value == "access_as_user" and .isEnabled == true) | .id' <<<"$api_json")"
  jq -e --arg api "$api_client_id" --arg scope "$scope_id" --arg redirect "$redirect_uri" '
    .signInAudience == "AzureADMyOrg"
    and .spa.redirectUris == [$redirect]
    and ([.requiredResourceAccess[] | select(.resourceAppId == $api) | .resourceAccess[] | select(.id == $scope and .type == "Scope")] | length == 1)
  ' <<<"$web_json" >/dev/null || die "Web registration does not match the required manifest"
}

if [[ "$mode" == "check" ]]; then
  validate_apps
  echo "CHECK_VALID tenant=$active_tenant api=$api_client_id web=$web_client_id"
  exit 0
fi

create_or_get_app() {
  local client_id="$1" display_name="$2"
  if [[ -n "$client_id" ]]; then
    need_uuid "$display_name client ID" "$client_id"
    az ad app show --id "$client_id" -o json
  else
    az ad app create --display-name "$display_name" --sign-in-audience AzureADMyOrg -o json
  fi
}

api_record="$(create_or_get_app "$api_client_id" "Supply Response API")"
api_client_id="$(jq -r '.appId' <<<"$api_record")"
api_object_id="$(jq -r '.id' <<<"$api_record")"
web_record="$(create_or_get_app "$web_client_id" "Supply Response Web")"
web_client_id="$(jq -r '.appId' <<<"$web_record")"
web_object_id="$(jq -r '.id' <<<"$web_record")"
need_uuid "API client ID" "$api_client_id"
need_uuid "API object ID" "$api_object_id"
need_uuid "Web client ID" "$web_client_id"
need_uuid "Web object ID" "$web_object_id"

api_payload="$(mktemp)"
web_payload="$(mktemp)"
trap 'rm -f "$api_payload" "$web_payload"' EXIT
jq --arg api "$api_client_id" --arg workiq "$workiq_app_id" --arg permission "$workiq_scope_id" '
  .identifierUris = ["api://" + $api]
  | .requiredResourceAccess = [{resourceAppId: $workiq, resourceAccess: [{id: $permission, type: "Scope"}]}]
' "$script_dir/api-app.json" >"$api_payload"
jq --arg api "$api_client_id" --arg redirect "$redirect_uri" '
  .spa.redirectUris = [$redirect]
  | .requiredResourceAccess[0].resourceAppId = $api
' "$script_dir/web-app.json" >"$web_payload"
az rest --method PATCH --uri "https://graph.microsoft.com/v1.0/applications/$api_object_id" --headers Content-Type=application/json --body "@$api_payload" >/dev/null
az rest --method PATCH --uri "https://graph.microsoft.com/v1.0/applications/$web_object_id" --headers Content-Type=application/json --body "@$web_payload" >/dev/null
az ad sp show --id "$api_client_id" >/dev/null 2>&1 || az ad sp create --id "$api_client_id" >/dev/null
az ad sp show --id "$web_client_id" >/dev/null 2>&1 || az ad sp create --id "$web_client_id" >/dev/null

umask 077
env_file="$script_dir/.env.tenant"
printf '%s\n' \
  "SUPPLY_RESPONSE_EXPECTED_TENANT_ID=$active_tenant" \
  "SUPPLY_RESPONSE_API_CLIENT_ID=$api_client_id" \
  "SUPPLY_RESPONSE_WEB_CLIENT_ID=$web_client_id" \
  "SUPPLY_RESPONSE_WORKIQ_RESOURCE_APP_ID=$workiq_app_id" \
  "SUPPLY_RESPONSE_REDIRECT_URI=$redirect_uri" >"$env_file"
chmod 0600 "$env_file"
validate_apps
echo "APPLY_COMPLETE; admin consent and persona assignments remain separate approval-gated steps"
