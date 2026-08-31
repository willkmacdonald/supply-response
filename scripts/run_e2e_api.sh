#!/usr/bin/env bash
set -euo pipefail

script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "${script_directory}/.." && pwd)"
database_path="${SUPPLY_RESPONSE_E2E_DATABASE_PATH:?E2E database path is required}"

case "${database_path}" in
  "${repository_root}/.tmp/"e2e-*.db) ;;
  *)
    echo "Refusing to use an unrecognized E2E database path." >&2
    exit 2
    ;;
esac

api_pid=""
cleanup() {
  if [[ -n "${api_pid}" ]] && kill -0 "${api_pid}" 2>/dev/null; then
    kill "${api_pid}" 2>/dev/null || true
    wait "${api_pid}" 2>/dev/null || true
  fi
  rm -f -- "${database_path}" "${database_path}-shm" "${database_path}-wal"
}
trap cleanup EXIT INT TERM

cd "${repository_root}"
.venv/bin/uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000 &
api_pid="$!"
wait "${api_pid}"
