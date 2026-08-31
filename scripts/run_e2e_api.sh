#!/usr/bin/env bash
set -euo pipefail

script_directory="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repository_root="$(cd -P -- "${script_directory}/.." && pwd -P)"
database_path="${SUPPLY_RESPONSE_E2E_DATABASE_PATH:?E2E database path is required}"

validate_database_path() {
  local database_parent database_basename physical_parent
  database_parent="${database_path%/*}"
  database_basename="${database_path##*/}"

  [[ "${database_path}" == /* ]] || return 1
  [[ "${database_parent}" == "${repository_root}/.tmp" ]] || return 1
  [[ "${database_basename}" =~ ^e2e-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.db$ ]] || return 1
  [[ -d "${database_parent}" && ! -L "${database_parent}" ]] || return 1
  physical_parent="$(cd -P -- "${database_parent}" && pwd -P)" || return 1
  [[ "${physical_parent}" == "${repository_root}/.tmp" ]] || return 1
  [[ ! -L "${database_path}" ]] || return 1
}

if ! validate_database_path; then
  echo "Refusing to use an unrecognized E2E database path." >&2
  exit 2
fi

if [[ "${SUPPLY_RESPONSE_E2E_VALIDATE_ONLY:-false}" == "true" ]]; then
  exit 0
fi

api_pid=""
cleanup() {
  if [[ -n "${api_pid}" ]] && kill -0 "${api_pid}" 2>/dev/null; then
    kill "${api_pid}" 2>/dev/null || true
    wait "${api_pid}" 2>/dev/null || true
  fi
  if validate_database_path; then
    rm -f -- "${database_path}" "${database_path}-shm" "${database_path}-wal"
  else
    echo "Refusing to clean an unrecognized E2E database path." >&2
  fi
}
trap cleanup EXIT INT TERM

cd "${repository_root}"
.venv/bin/uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000 &
api_pid="$!"
wait "${api_pid}"
