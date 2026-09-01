#!/usr/bin/env bash

KV_OPERATOR_ROLE_ID='b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
KV_OPERATOR_SCOPE=''
KV_OPERATOR_PRINCIPAL_ID=''
KV_OPERATOR_PRINCIPAL_TYPE=''
KV_OPERATOR_ROLE_RESOURCE_ID=''
KV_OPERATOR_ASSIGNMENT_GUID=''
KV_OPERATOR_ASSIGNMENT_ID=''
KV_OPERATOR_CLEANUP_ACTIVE=false

configure_temporary_kv_operator_access() {
  KV_OPERATOR_SCOPE="$1"
  KV_OPERATOR_PRINCIPAL_ID="$2"
  KV_OPERATOR_PRINCIPAL_TYPE="$3"
  local subscription_id="${KV_OPERATOR_SCOPE#/subscriptions/}"
  subscription_id="${subscription_id%%/*}"
  [[ -n "$subscription_id" && "$subscription_id" != "$KV_OPERATOR_SCOPE" ]] || return 1
  [[ "$KV_OPERATOR_PRINCIPAL_TYPE" == User || "$KV_OPERATOR_PRINCIPAL_TYPE" == ServicePrincipal ]] || return 1
  KV_OPERATOR_ROLE_RESOURCE_ID="/subscriptions/${subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${KV_OPERATOR_ROLE_ID}"
  KV_OPERATOR_ASSIGNMENT_GUID="$(SCOPE="$KV_OPERATOR_SCOPE" PRINCIPAL_ID="$KV_OPERATOR_PRINCIPAL_ID" ROLE_ID="$KV_OPERATOR_ROLE_ID" python3 -c 'import os,uuid; material="|".join((os.environ["SCOPE"].lower(), os.environ["PRINCIPAL_ID"].lower(), os.environ["ROLE_ID"])); print(uuid.uuid5(uuid.NAMESPACE_URL, material))')"
  KV_OPERATOR_ASSIGNMENT_ID="${KV_OPERATOR_SCOPE}/providers/Microsoft.Authorization/roleAssignments/${KV_OPERATOR_ASSIGNMENT_GUID}"
  KV_OPERATOR_CLEANUP_ACTIVE=false
  export KV_OPERATOR_SCOPE KV_OPERATOR_PRINCIPAL_ID KV_OPERATOR_PRINCIPAL_TYPE
  export KV_OPERATOR_ROLE_RESOURCE_ID KV_OPERATOR_ASSIGNMENT_ID
}

verify_temporary_kv_operator_access() {
  local assignments_json status=0
  safe_capture_ephemeral assignments_json verify-temporary-kv-role az role assignment list --scope "$KV_OPERATOR_SCOPE" --output json || return 2
  ASSIGNMENT_ID="$KV_OPERATOR_ASSIGNMENT_ID" PRINCIPAL_ID="$KV_OPERATOR_PRINCIPAL_ID" PRINCIPAL_TYPE="$KV_OPERATOR_PRINCIPAL_TYPE" SCOPE="$KV_OPERATOR_SCOPE" ROLE_RESOURCE_ID="$KV_OPERATOR_ROLE_RESOURCE_ID" python3 -c 'import json,os,sys; items=json.load(sys.stdin); exact_id=[item for item in items if item.get("id", "").lower()==os.environ["ASSIGNMENT_ID"].lower()]; matches=[item for item in exact_id if item.get("principalId", "").lower()==os.environ["PRINCIPAL_ID"].lower() and item.get("principalType")==os.environ["PRINCIPAL_TYPE"] and item.get("scope", "").lower()==os.environ["SCOPE"].lower() and item.get("roleDefinitionId", "").lower()==os.environ["ROLE_RESOURCE_ID"].lower()]; raise SystemExit(0 if len(matches)==1 else (3 if not exact_id else 4))' <<<"$assignments_json" || status=$?
  unset assignments_json
  return "$status"
}

create_temporary_kv_operator_access() {
  [[ -n "$KV_OPERATOR_ASSIGNMENT_ID" ]] || return 1
  # Active before create: a timed-out create may still have committed remotely.
  KV_OPERATOR_CLEANUP_ACTIVE=true
  safe_run create-temporary-kv-role az role assignment create \
    --name "$KV_OPERATOR_ASSIGNMENT_GUID" \
    --assignee-object-id "$KV_OPERATOR_PRINCIPAL_ID" \
    --assignee-principal-type "$KV_OPERATOR_PRINCIPAL_TYPE" \
    --role "$KV_OPERATOR_ROLE_RESOURCE_ID" \
    --scope "$KV_OPERATOR_SCOPE" --output none || return 1
  verify_temporary_kv_operator_access
}

cleanup_temporary_kv_operator_access() {
  [[ "$KV_OPERATOR_CLEANUP_ACTIVE" == true ]] || return 0
  local state=0
  verify_temporary_kv_operator_access || state=$?
  if [[ "$state" == 3 ]]; then
    KV_OPERATOR_CLEANUP_ACTIVE=false
    return 0
  fi
  if [[ "$state" != 0 ]]; then
    printf 'Temporary Key Vault role could not be verified; refusing deletion.\n' >&2
    return 1
  fi
  safe_run delete-temporary-kv-role az role assignment delete --ids "$KV_OPERATOR_ASSIGNMENT_ID" || return 1
  KV_OPERATOR_CLEANUP_ACTIVE=false
}
