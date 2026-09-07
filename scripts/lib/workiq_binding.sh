#!/usr/bin/env bash

WORKIQ_BINDING_SETTING_NAMES=(
  SUPPLY_RESPONSE_WORKIQ_CORPUS_VERSION
  SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SOURCE_ID
  SUPPLY_RESPONSE_WORKIQ_QUALITY_SOURCE_ID
  SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SENDER
  SUPPLY_RESPONSE_WORKIQ_QUALITY_AUTHOR_OBJECT_ID
  SUPPLY_RESPONSE_WORKIQ_TEAM_ID
  SUPPLY_RESPONSE_WORKIQ_CHANNEL_ID
  SUPPLY_RESPONSE_WORKIQ_DEPLOYMENT_RECEIPT
)

workiq_binding_receipt() {
  local workiq_receipt_parts=(
    workiq-binding-v2
    "$SUPPLY_RESPONSE_WORKIQ_CORPUS_VERSION"
    "$SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SOURCE_ID"
    "$SUPPLY_RESPONSE_WORKIQ_QUALITY_SOURCE_ID"
    "$SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SENDER"
    "$SUPPLY_RESPONSE_WORKIQ_QUALITY_AUTHOR_OBJECT_ID"
    "$SUPPLY_RESPONSE_WORKIQ_TEAM_ID"
    "$SUPPLY_RESPONSE_WORKIQ_CHANNEL_ID"
  )
  python3 -c 'import hashlib,sys; print(hashlib.sha256("\n".join(sys.argv[1:]).encode("utf-8")).hexdigest())' "${workiq_receipt_parts[@]}"
}

validate_workiq_binding() {
  local setting expected_workiq_receipt
  local uuid_pattern='^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
  if ! command -v python3 >/dev/null; then
    printf 'Missing required command: python3\n' >&2
    return 1
  fi
  for setting in "${WORKIQ_BINDING_SETTING_NAMES[@]}"; do
    if [[ -z "${!setting:-}" ]]; then
      printf 'Missing required Work IQ binding setting: %s\n' "$setting" >&2
      return 1
    fi
  done
  if [[ ! "$SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SENDER" =~ ^[^[:space:]@]+@[^[:space:]@]+$ ]]; then
    printf 'Work IQ supplier sender binding is malformed.\n' >&2
    return 1
  fi
  if [[ ! "$SUPPLY_RESPONSE_WORKIQ_QUALITY_AUTHOR_OBJECT_ID" =~ $uuid_pattern ]]; then
    printf 'Work IQ Quality author object ID binding is malformed.\n' >&2
    return 1
  fi
  if [[ ! "$SUPPLY_RESPONSE_WORKIQ_TEAM_ID" =~ $uuid_pattern ]]; then
    printf 'Work IQ Team ID binding is malformed.\n' >&2
    return 1
  fi
  if [[ ! "$SUPPLY_RESPONSE_WORKIQ_CHANNEL_ID" =~ ^19:[^[:space:]/?#]+@thread\.tacv2$ ]]; then
    printf 'Work IQ channel ID binding is malformed.\n' >&2
    return 1
  fi
  if [[ ! "$SUPPLY_RESPONSE_WORKIQ_DEPLOYMENT_RECEIPT" =~ ^[0-9a-f]{64}$ ]]; then
    printf 'Work IQ deployment receipt is malformed.\n' >&2
    return 1
  fi
  expected_workiq_receipt="$(workiq_binding_receipt)" || return 1
  if [[ "$SUPPLY_RESPONSE_WORKIQ_DEPLOYMENT_RECEIPT" != "$expected_workiq_receipt" ]]; then
    printf 'Work IQ deployment receipt does not match trusted bindings.\n' >&2
    return 1
  fi
}
