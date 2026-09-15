#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mode=""; fixture=""
die() { echo "ERROR: $*" >&2; exit 1; }
require() { command -v "$1" >/dev/null 2>&1 || die "$1 is required"; }
is_uuid() { [[ "$1" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; }
need_uuid() { is_uuid "$2" || die "$1 must be a UUID"; }

while (($#)); do
  case "$1" in
    --dry-run|--check|--apply) [[ -z "$mode" ]] || die "choose exactly one mode"; mode="${1#--}" ;;
    --fixture) shift; (($#)) || die "--fixture requires a path"; fixture="$1" ;;
    *) die "unknown argument: $1" ;;
  esac
  shift
done
[[ -n "$mode" ]] || die "choose --dry-run, --check, or --apply"
[[ "${SUPPLY_RESPONSE_CONFIRM_TENANT:-}" == "willmacdonald.com" ]] || die "set SUPPLY_RESPONSE_CONFIRM_TENANT=willmacdonald.com after confirming the directory"
expected_tenant="${SUPPLY_RESPONSE_EXPECTED_TENANT_ID:-}"
workiq_app_id="${SUPPLY_RESPONSE_WORKIQ_RESOURCE_APP_ID:-}"
graph_app_id="00000003-0000-0000-c000-000000000000"
redirect_uri="${SUPPLY_RESPONSE_REDIRECT_URI:-}"
need_uuid "SUPPLY_RESPONSE_EXPECTED_TENANT_ID" "$expected_tenant"
need_uuid "SUPPLY_RESPONSE_WORKIQ_RESOURCE_APP_ID" "$workiq_app_id"
[[ "$redirect_uri" != *\?* && "$redirect_uri" != *\#* ]] || die "SUPPLY_RESPONSE_REDIRECT_URI must not contain a query or fragment"
if [[ "$redirect_uri" =~ ^https://([a-z0-9.-]+)(:([0-9]+))?(/[^[:space:]]*)?$ ]]; then
  [[ "${BASH_REMATCH[3]:-}" != "443" ]] || die "SUPPLY_RESPONSE_REDIRECT_URI must use a canonical authority"
elif [[ "$redirect_uri" =~ ^http://(localhost|127\.0\.0\.1)(:([0-9]+))?(/[^[:space:]]*)?$ ]]; then
  [[ "${BASH_REMATCH[3]:-}" != "80" ]] || die "SUPPLY_RESPONSE_REDIRECT_URI must use a canonical authority"
else
  die "SUPPLY_RESPONSE_REDIRECT_URI must use canonical lowercase HTTPS or loopback HTTP"
fi
uri_after_scheme="${redirect_uri#*://}"
redirect_path=""
if [[ "$uri_after_scheme" == */* ]]; then redirect_path="/${uri_after_scheme#*/}"; fi
IFS='/' read -r -a redirect_path_segments <<<"${redirect_path,,}"
for segment in "${redirect_path_segments[@]}"; do
  [[ ! "$segment" =~ ^(\.|%2e)(\.|%2e)?$ ]] || die "SUPPLY_RESPONSE_REDIRECT_URI must use a canonical path without dot segments"
done
redirect_uri="${redirect_uri%/}"
[[ -n "$redirect_uri" ]] || die "SUPPLY_RESPONSE_REDIRECT_URI is invalid"
require jq

fake_adapter=0
az_command=(az)
if [[ -n "${SUPPLY_RESPONSE_TEST_AZ_ADAPTER:-}" ]]; then
  adapter="$SUPPLY_RESPONSE_TEST_AZ_ADAPTER"
  [[ "${SUPPLY_RESPONSE_TEST_MODE:-}" == "1" ]] || die "fake adapter requires explicit local test mode"
  [[ "$adapter" == /* && -x "$adapter" && "${adapter##*/}" == "supply-response-fake-az" ]] || die "fake adapter must be an absolute executable named supply-response-fake-az"
  [[ "$("$adapter" __supply_response_fake_adapter_probe__ 2>/dev/null)" == "SUPPLY_RESPONSE_FAKE_AZ_V1" ]] || die "fake adapter probe failed"
  fake_adapter=1
  az_command=("$adapter")
fi
[[ -z "${SUPPLY_RESPONSE_INJECT_FAILURE_AFTER:-}" || "$fake_adapter" == "1" ]] || die "fault injection requires the validated fake adapter"
az_run() { "${az_command[@]}" "$@"; }

state_file="$script_dir/.env.tenant"
if [[ -n "${SUPPLY_RESPONSE_ENTRA_STATE_FILE:-}" ]]; then
  [[ -n "$fixture" || "$fake_adapter" == "1" ]] || die "state-file override requires fixture mode or the validated fake adapter"
  state_file="$SUPPLY_RESPONSE_ENTRA_STATE_FILE"
fi
state_value() {
  local key="$1" count
  [[ -f "$state_file" ]] || return 0
  count="$(grep -c "^${key}=" "$state_file" || true)"
  [[ "$count" == "0" || "$count" == "1" ]] || die "$state_file contains ambiguous $key values"
  sed -n "s/^${key}=//p" "$state_file"
}
write_state() {
  local status="$1" state_temp
  umask 077; mkdir -p "$(dirname "$state_file")"
  state_temp="$(mktemp "${state_file}.tmp.XXXXXX")"
  printf '%s\n' \
    "SUPPLY_RESPONSE_ENTRA_STATE=$status" \
    "SUPPLY_RESPONSE_EXPECTED_TENANT_ID=$active_tenant" \
    "SUPPLY_RESPONSE_API_CLIENT_ID=${api_client_id:-}" \
    "SUPPLY_RESPONSE_WEB_CLIENT_ID=${web_client_id:-}" \
    "SUPPLY_RESPONSE_WORKIQ_RESOURCE_APP_ID=$workiq_app_id" \
    "SUPPLY_RESPONSE_REDIRECT_URI=$redirect_uri" >"$state_temp"
  chmod 0600 "$state_temp"
  mv "$state_temp" "$state_file"
}
maybe_inject_failure() {
  [[ "$fake_adapter" == "1" ]] || return 0
  [[ "${SUPPLY_RESPONSE_INJECT_FAILURE_AFTER:-}" != "$1" ]] || die "injected failure after $1"
}

if [[ -n "$fixture" ]]; then
  [[ "$mode" != "apply" ]] || die "--fixture cannot be used with --apply"
  [[ -f "$fixture" ]] || die "--fixture requires an existing file"
  active_tenant="$(jq -er '.activeTenantId' "$fixture")"
  organization_json="$(jq -c '{verifiedDomains: .verifiedDomains}' "$fixture")"
  workiq_json="$(jq -c '.workIqServicePrincipal' "$fixture")"
  graph_json='{"appId":"00000003-0000-0000-c000-000000000000","oauth2PermissionScopes":[{"id":"66666666-6666-4666-8666-666666666666","value":"Mail.ReadWrite","isEnabled":true},{"id":"77777777-7777-4777-8777-777777777777","value":"Mail.Send","isEnabled":true}]}'
else
  [[ "$mode" != "dry-run" ]] || die "--dry-run requires --fixture"
  [[ "$fake_adapter" == "1" ]] || require az
  active_tenant="$(az_run account show --query tenantId -o tsv)"
  organization_json="$(az_run rest --method GET --uri 'https://graph.microsoft.com/v1.0/organization?$select=id,verifiedDomains' --query 'value[0]' -o json)"
  workiq_json="$(az_run ad sp show --id "$workiq_app_id" -o json)"
  if [[ "$fake_adapter" == "1" ]]; then
    graph_json='{"appId":"00000003-0000-0000-c000-000000000000","oauth2PermissionScopes":[{"id":"66666666-6666-4666-8666-666666666666","value":"Mail.ReadWrite","isEnabled":true},{"id":"77777777-7777-4777-8777-777777777777","value":"Mail.Send","isEnabled":true}]}'
  else
    graph_json="$(az_run ad sp show --id "$graph_app_id" -o json)"
  fi
fi
need_uuid "active Azure tenant" "$active_tenant"
[[ "$active_tenant" == "$expected_tenant" ]] || die "active tenant does not match SUPPLY_RESPONSE_EXPECTED_TENANT_ID"
jq -e '.verifiedDomains | map(select(.name == "willmacdonald.com" and (.isVerified == true or .isDefault == true))) | length == 1' <<<"$organization_json" >/dev/null || die "active tenant is not the verified willmacdonald.com directory"
[[ "$(jq -r '.appId' <<<"$workiq_json")" == "$workiq_app_id" ]] || die "Work IQ service principal app ID mismatch"
workiq_scope_count="$(jq '[.oauth2PermissionScopes[]? | select(.value == "WorkIQAgent.Ask" and .isEnabled == true)] | length' <<<"$workiq_json")"
[[ "$workiq_scope_count" == "1" ]] || die "WorkIQAgent.Ask scope is missing or ambiguous"
workiq_scope_id="$(jq -r '.oauth2PermissionScopes[] | select(.value == "WorkIQAgent.Ask" and .isEnabled == true) | .id' <<<"$workiq_json")"
need_uuid "WorkIQAgent.Ask scope ID" "$workiq_scope_id"
[[ "$(jq -r '.appId' <<<"$graph_json")" == "$graph_app_id" ]] || die "Microsoft Graph service principal app ID mismatch"
graph_mail_readwrite_count="$(jq '[.oauth2PermissionScopes[]? | select(.value == "Mail.ReadWrite" and .isEnabled == true)] | length' <<<"$graph_json")"
[[ "$graph_mail_readwrite_count" == "1" ]] || die "Mail.ReadWrite scope is missing or ambiguous"
graph_mail_readwrite_scope_id="$(jq -r '.oauth2PermissionScopes[] | select(.value == "Mail.ReadWrite" and .isEnabled == true) | .id' <<<"$graph_json")"
need_uuid "Mail.ReadWrite scope ID" "$graph_mail_readwrite_scope_id"
graph_mail_send_count="$(jq '[.oauth2PermissionScopes[]? | select(.value == "Mail.Send" and .isEnabled == true)] | length' <<<"$graph_json")"
[[ "$graph_mail_send_count" == "1" ]] || die "Mail.Send scope is missing or ambiguous"
graph_mail_send_scope_id="$(jq -r '.oauth2PermissionScopes[] | select(.value == "Mail.Send" and .isEnabled == true) | .id' <<<"$graph_json")"
need_uuid "Mail.Send scope ID" "$graph_mail_send_scope_id"

api_client_id="${SUPPLY_RESPONSE_API_CLIENT_ID:-$(state_value SUPPLY_RESPONSE_API_CLIENT_ID)}"
web_client_id="${SUPPLY_RESPONSE_WEB_CLIENT_ID:-$(state_value SUPPLY_RESPONSE_WEB_CLIENT_ID)}"
make_payloads() {
  api_payload="$(mktemp)"; web_payload="$(mktemp)"
  jq --arg api "$api_client_id" --arg workiq "$workiq_app_id" --arg permission "$workiq_scope_id" --arg graph "$graph_app_id" --arg mailReadWrite "$graph_mail_readwrite_scope_id" --arg mailSend "$graph_mail_send_scope_id" '
    .identifierUris = ["api://" + $api]
    | .requiredResourceAccess = [
        {resourceAppId: $graph, resourceAccess: [{id: $mailReadWrite, type: "Scope"}, {id: $mailSend, type: "Scope"}]},
        {resourceAppId: $workiq, resourceAccess: [{id: $permission, type: "Scope"}]}
      ]
  ' "$script_dir/api-app.json" >"$api_payload"
  jq --arg api "$api_client_id" --arg redirect "$redirect_uri" '
    .spa.redirectUris = [$redirect] | .requiredResourceAccess[0].resourceAppId = $api
  ' "$script_dir/web-app.json" >"$web_payload"
  jq -e '[.. | objects | keys[]] | any(. == "origin" or . == "publisherDomain" or . == "verifiedPublisher" or . == "createdDateTime") | not' "$api_payload" >/dev/null || die "API PATCH payload contains a Graph read-only field"
}
canonical_api_contract() {
  jq -Sc '{signInAudience,identifierUris,api:{acceptMappedClaims:(.api.acceptMappedClaims // null),knownClientApplications:(.api.knownClientApplications|sort),preAuthorizedApplications:(.api.preAuthorizedApplications|map({appId,delegatedPermissionIds:(.delegatedPermissionIds|sort)})|sort_by(.appId)),requestedAccessTokenVersion:.api.requestedAccessTokenVersion,oauth2PermissionScopes:(.api.oauth2PermissionScopes|map({adminConsentDescription,adminConsentDisplayName,id,isEnabled,type,userConsentDescription,userConsentDisplayName,value})|sort_by(.id))},appRoles:(.appRoles|map({allowedMemberTypes,description,displayName,id,isEnabled,value})|sort_by(.id)),requiredResourceAccess:(.requiredResourceAccess|map(.resourceAccess|=sort_by(.id))|sort_by(.resourceAppId)),isFallbackPublicClient,web:{redirectUris:.web.redirectUris}}'
}
canonical_web_contract() {
  jq -Sc '{signInAudience,spa:{redirectUris:.spa.redirectUris},requiredResourceAccess:(.requiredResourceAccess|map(.resourceAccess|=sort_by(.id))|sort_by(.resourceAppId)),isFallbackPublicClient}'
}
validate_apps() {
  need_uuid "SUPPLY_RESPONSE_API_CLIENT_ID" "$api_client_id"; need_uuid "SUPPLY_RESPONSE_WEB_CLIENT_ID" "$web_client_id"
  local api_json web_json expected actual
  if [[ -n "$fixture" ]]; then
    api_json="$(jq -ce '.apiApplication' "$fixture")"; web_json="$(jq -ce '.webApplication' "$fixture")"
  else
    api_json="$(az_run ad app show --id "$api_client_id" -o json)"; web_json="$(az_run ad app show --id "$web_client_id" -o json)"
  fi
  make_payloads
  expected="$(canonical_api_contract <"$api_payload")"; actual="$(canonical_api_contract <<<"$api_json")"
  [[ "$actual" == "$expected" ]] || die "API registration does not exactly match the required manifest"
  expected="$(canonical_web_contract <"$web_payload")"; actual="$(canonical_web_contract <<<"$web_json")"
  [[ "$actual" == "$expected" ]] || die "Web registration does not exactly match the required manifest"
  rm -f "$api_payload" "$web_payload"
}

if [[ "$mode" == "dry-run" ]]; then
  need_uuid "SUPPLY_RESPONSE_API_CLIENT_ID" "$api_client_id"; need_uuid "SUPPLY_RESPONSE_WEB_CLIENT_ID" "$web_client_id"
  make_payloads; canonical_api_contract <"$api_payload" >/dev/null; canonical_web_contract <"$web_payload" >/dev/null
  rm -f "$api_payload" "$web_payload"
  echo "DRY_RUN_VALID tenant=$active_tenant api=$api_client_id web=$web_client_id permissions=WorkIQAgent.Ask,Mail.ReadWrite,Mail.Send redirect=$redirect_uri"
  exit 0
fi
if [[ "$mode" == "check" ]]; then
  [[ "$(state_value SUPPLY_RESPONSE_ENTRA_STATE)" == "COMPLETE" ]] || die "Entra configuration state is incomplete"
  validate_apps; echo "CHECK_VALID tenant=$active_tenant api=$api_client_id web=$web_client_id"; exit 0
fi

if [[ -n "$api_client_id" ]]; then
  need_uuid "API client ID" "$api_client_id"; api_record="$(az_run ad app show --id "$api_client_id" -o json)"
else
  api_record="$(az_run ad app create --display-name "Supply Response API" --sign-in-audience AzureADMyOrg -o json)"
  api_client_id="$(jq -r '.appId' <<<"$api_record")"; need_uuid "API client ID" "$api_client_id"
  write_state INCOMPLETE; maybe_inject_failure api_app
fi
api_object_id="$(jq -r '.id' <<<"$api_record")"; need_uuid "API object ID" "$api_object_id"
if [[ -n "$web_client_id" ]]; then
  need_uuid "Web client ID" "$web_client_id"; web_record="$(az_run ad app show --id "$web_client_id" -o json)"
else
  web_record="$(az_run ad app create --display-name "Supply Response Web" --sign-in-audience AzureADMyOrg -o json)"
  web_client_id="$(jq -r '.appId' <<<"$web_record")"; need_uuid "Web client ID" "$web_client_id"
  write_state INCOMPLETE; maybe_inject_failure web_app
fi
web_object_id="$(jq -r '.id' <<<"$web_record")"; need_uuid "Web object ID" "$web_object_id"

write_state INCOMPLETE; make_payloads
trap 'rm -f "${api_payload:-}" "${web_payload:-}"' EXIT
az_run rest --method PATCH --uri "https://graph.microsoft.com/v1.0/applications/$api_object_id" --headers Content-Type=application/json --body "@$api_payload" >/dev/null
maybe_inject_failure api_patch
az_run rest --method PATCH --uri "https://graph.microsoft.com/v1.0/applications/$web_object_id" --headers Content-Type=application/json --body "@$web_payload" >/dev/null
maybe_inject_failure web_patch
if ! az_run ad sp show --id "$api_client_id" >/dev/null 2>&1; then az_run ad sp create --id "$api_client_id" >/dev/null; fi
maybe_inject_failure api_sp
if ! az_run ad sp show --id "$web_client_id" >/dev/null 2>&1; then az_run ad sp create --id "$web_client_id" >/dev/null; fi
maybe_inject_failure web_sp
validate_apps
write_state COMPLETE
echo "APPLY_COMPLETE; admin consent and persona assignments remain separate approval-gated steps"
