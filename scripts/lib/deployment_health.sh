#!/usr/bin/env bash

validate_live_smoke_contract() {
  local health_file="$1" runtime_file="$2"
  HEALTH_FILE="$health_file" RUNTIME_FILE="$runtime_file" python3 - <<'PY'
import json
import os

with open(os.environ["HEALTH_FILE"], encoding="utf-8") as stream:
    health = json.load(stream)
with open(os.environ["RUNTIME_FILE"], encoding="utf-8") as stream:
    runtime = json.load(stream)

health_valid = (
    health.get("status") == "ok"
    and health.get("runtime_mode") == "live"
    and health.get("operational_store") == "fabric_sql"
    and type(health.get("schema_version")) is int
)
capabilities = runtime.get("capability_health", {})
runtime_valid = (
    runtime.get("runtime_mode") == "live"
    and capabilities.get("operational_store") == "ready"
    and capabilities.get("agent_runtime") == "ready"
)
if not (health_valid and runtime_valid):
    raise SystemExit(1)
PY
}

validate_existing_final_health_contract() {
  local health_file="$1"
  HEALTH_FILE="$health_file" python3 - <<'PY'
import json
import os

with open(os.environ["HEALTH_FILE"], encoding="utf-8") as stream:
    health = json.load(stream)
if not (health.get("status") == "ok" and health.get("runtime_mode") == "live"):
    raise SystemExit(1)
PY
}
