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
require jq

if [[ -f "$script_dir/.env.tenant" && "$mode" != "dry-run" ]]; then
  [[ "$(grep -c '^SUPPLY_RESPONSE_EXPECTED_TENANT_ID=' "$script_dir/.env.tenant")" == "1" ]] || die ".env.tenant tenant ID is missing or ambiguous"
  [[ "$(grep -c '^SUPPLY_RESPONSE_API_CLIENT_ID=' "$script_dir/.env.tenant")" == "1" ]] || die ".env.tenant API client ID is missing or ambiguous"
  file_tenant_id="$(sed -n 's/^SUPPLY_RESPONSE_EXPECTED_TENANT_ID=//p' "$script_dir/.env.tenant")"
  file_api_client_id="$(sed -n 's/^SUPPLY_RESPONSE_API_CLIENT_ID=//p' "$script_dir/.env.tenant")"
fi
tenant_id="${SUPPLY_RESPONSE_EXPECTED_TENANT_ID:-${file_tenant_id:-}}"
api_client_id="${SUPPLY_RESPONSE_API_CLIENT_ID:-${file_api_client_id:-}}"
alex_id="${SUPPLY_RESPONSE_ALEX_OBJECT_ID:-}"
jordan_id="${SUPPLY_RESPONSE_JORDAN_OBJECT_ID:-}"
taylor_id="${SUPPLY_RESPONSE_TAYLOR_OBJECT_ID:-}"
need_uuid "SUPPLY_RESPONSE_EXPECTED_TENANT_ID" "$tenant_id"
need_uuid "SUPPLY_RESPONSE_API_CLIENT_ID" "$api_client_id"
need_uuid "SUPPLY_RESPONSE_ALEX_OBJECT_ID" "$alex_id"
need_uuid "SUPPLY_RESPONSE_JORDAN_OBJECT_ID" "$jordan_id"
need_uuid "SUPPLY_RESPONSE_TAYLOR_OBJECT_ID" "$taylor_id"
[[ "$alex_id" != "$jordan_id" && "$alex_id" != "$taylor_id" && "$jordan_id" != "$taylor_id" ]] || die "persona object IDs must be distinct"

if [[ -n "$fixture" ]]; then
  [[ "$mode" != "apply" ]] || die "--fixture cannot be used with --apply"
  [[ -f "$fixture" ]] || die "--fixture requires an existing file"
  active_tenant="$(jq -er '.activeTenantId' "$fixture")"
  api_sp_id="$(jq -er '.apiServicePrincipalId' "$fixture")"
  roles_json="$(jq -c '{appRoles: .appRoles}' "$fixture")"
  assignments_json="$(jq -c '.assignments' "$fixture")"
else
  [[ "$mode" != "dry-run" ]] || die "--dry-run requires --fixture"
  require az
  active_tenant="$(az account show --query tenantId -o tsv)"
  api_sp_json="$(az ad sp show --id "$api_client_id" -o json)"
  api_sp_id="$(jq -r '.id' <<<"$api_sp_json")"
  roles_json="$(az ad app show --id "$api_client_id" --query '{appRoles:appRoles}' -o json)"
  assignments_json="$(az rest --method GET --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$api_sp_id/appRoleAssignedTo" --query value -o json)"
fi
need_uuid "active Azure tenant" "$active_tenant"
need_uuid "API service principal ID" "$api_sp_id"
[[ "$active_tenant" == "$tenant_id" ]] || die "active tenant does not match the expected tenant"

role_id() {
  local role="$1" count value
  count="$(jq --arg role "$role" '[.appRoles[]? | select(.value == $role and .isEnabled == true and .allowedMemberTypes == ["User"])] | length' <<<"$roles_json")"
  [[ "$count" == "1" ]] || die "role $role is missing or ambiguous"
  value="$(jq -r --arg role "$role" '.appRoles[] | select(.value == $role and .isEnabled == true) | .id' <<<"$roles_json")"
  need_uuid "role $role ID" "$value"
  printf '%s' "$value"
}

material_role_id="$(role_id material_planner)"
response_role_id="$(role_id response_approver)"
quality_role_id="$(role_id quality_approver)"
finance_role_id="$(role_id finance_approver)"

exact_persona_assignments() {
  local comparison="${1:-exact}" expected actual
  expected="$(jq -nc \
    --arg alex "$alex_id" --arg jordan "$jordan_id" --arg taylor "$taylor_id" \
    --arg material "$material_role_id" --arg response "$response_role_id" \
    --arg quality "$quality_role_id" --arg finance "$finance_role_id" \
    '[{principalId:$alex,appRoleId:$material},{principalId:$alex,appRoleId:$response},{principalId:$jordan,appRoleId:$quality},{principalId:$taylor,appRoleId:$finance}] | sort_by(.principalId,.appRoleId)')"
  actual="$(jq -c \
    --arg resource "$api_sp_id" --arg alex "$alex_id" --arg jordan "$jordan_id" --arg taylor "$taylor_id" \
    '[.[]? | select(.resourceId == $resource and (.principalId == $alex or .principalId == $jordan or .principalId == $taylor)) | {principalId,appRoleId}] | sort_by(.principalId,.appRoleId)' <<<"$assignments_json")"
  if [[ "$comparison" == "exact" ]]; then
    [[ "$actual" == "$expected" ]] || die "persona role assignments do not exactly match the fixed mapping"
  else
    jq -e --argjson expected "$expected" 'all(.[]; . as $row | any($expected[]; . == $row))' <<<"$actual" >/dev/null || die "persona has an excess or unexpected role assignment"
  fi
}

if [[ "$mode" == "check" ]]; then
  exact_persona_assignments exact
  echo "CHECK_COMPLETE tenant=$tenant_id api_service_principal=$api_sp_id"
  exit 0
elif [[ "$mode" == "apply" ]]; then
  exact_persona_assignments subset
fi

missing=0
assign_role() {
  local principal_id="$1" role="$2" app_role_id="$3" count body
  count="$(jq --arg principal "$principal_id" --arg resource "$api_sp_id" --arg role "$app_role_id" '[.[]? | select(.principalId == $principal and .resourceId == $resource and .appRoleId == $role)] | length' <<<"$assignments_json")"
  [[ "$count" == "0" || "$count" == "1" ]] || die "assignment for $principal_id $role is ambiguous"
  if [[ "$count" == "1" ]]; then
    echo "PRESENT $principal_id $role"
    return
  fi
  missing=$((missing + 1))
  if [[ "$mode" == "dry-run" ]]; then
    echo "WOULD_ASSIGN $principal_id $role"
  elif [[ "$mode" == "check" ]]; then
    echo "MISSING $principal_id $role" >&2
  else
    body="$(jq -nc --arg principal "$principal_id" --arg resource "$api_sp_id" --arg role "$app_role_id" '{principalId:$principal,resourceId:$resource,appRoleId:$role}')"
    az rest --method POST --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$api_sp_id/appRoleAssignedTo" --headers Content-Type=application/json --body "$body" >/dev/null
    echo "ASSIGNED $principal_id $role"
  fi
}

assign_role "$alex_id" material_planner "$material_role_id"
assign_role "$alex_id" response_approver "$response_role_id"
assign_role "$jordan_id" quality_approver "$quality_role_id"
assign_role "$taylor_id" finance_approver "$finance_role_id"
[[ "$mode" != "check" || "$missing" == "0" ]] || die "$missing required persona role assignments are missing"
echo "${mode^^}_COMPLETE tenant=$tenant_id api_service_principal=$api_sp_id"
