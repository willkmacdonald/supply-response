#!/usr/bin/env bash

# Shared fail-closed command capture for deployment scripts. Successful stdout
# is returned to the caller but never streamed; stderr always remains protected.

SAFE_DIAGNOSTICS_DIR=''
SAFE_LAST_STDOUT=''
SAFE_LAST_STDERR=''

safe_init_diagnostics() {
  [[ -z "$SAFE_DIAGNOSTICS_DIR" ]] || return 0
  SAFE_DIAGNOSTICS_DIR="$(mktemp -d)"
  chmod 700 "$SAFE_DIAGNOSTICS_DIR"
  trap safe_cleanup_diagnostics EXIT
}

safe_cleanup_diagnostics() {
  local status=$?
  if declare -F safe_before_diagnostics_cleanup >/dev/null; then
    if ! safe_before_diagnostics_cleanup; then
      status=1
    fi
  fi
  if [[ -n "$SAFE_DIAGNOSTICS_DIR" ]]; then
    if [[ "$status" == 0 ]]; then
      rm -rf "$SAFE_DIAGNOSTICS_DIR"
    else
      printf 'Protected raw diagnostics retained at %s (mode 0700); remove them after troubleshooting.\n' "$SAFE_DIAGNOSTICS_DIR" >&2
    fi
  fi
  return "$status"
}

safe_sanitized_summary() {
  python3 - "$1" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
categories = (
    (r"(?i)forbidden|unauthorized|denied|authentication|required", "authorization"),
    (r"(?i)not found|could not be found", "not-found"),
    (r"(?i)conflict|already exists", "conflict"),
    (r"(?i)invalid|validation", "validation"),
    (r"(?i)timeout|timed out|temporar|propagat", "transient-or-propagation"),
    (r"(?i)error|failed|failure", "error"),
)
detected = [label for pattern, label in categories if re.search(pattern, text)]
if not detected:
    print("Command failed; protected diagnostics contained no categorized error line.")
else:
    print("Command failed; " + ", ".join(detected) + " category detected.")
PY
}

safe_report_failure() {
  local label="$1"
  printf 'Command step %s failed. Sanitized summary follows; raw diagnostics remain protected.\n' "$label" >&2
  safe_sanitized_summary "$SAFE_LAST_STDERR" >&2
}

safe_capture_quiet() {
  local output_name="$1" label="$2" captured
  shift 2
  safe_init_diagnostics
  SAFE_LAST_STDOUT="${SAFE_DIAGNOSTICS_DIR}/${label}.stdout"
  SAFE_LAST_STDERR="${SAFE_DIAGNOSTICS_DIR}/${label}.stderr"
  : >"$SAFE_LAST_STDOUT"
  : >"$SAFE_LAST_STDERR"
  chmod 600 "$SAFE_LAST_STDOUT" "$SAFE_LAST_STDERR"
  if "$@" >"$SAFE_LAST_STDOUT" 2>"$SAFE_LAST_STDERR"; then
    captured="$(<"$SAFE_LAST_STDOUT")"
    printf -v "$output_name" '%s' "$captured"
    return 0
  fi
  printf -v "$output_name" '%s' ''
  return 1
}

safe_capture() {
  local output_name="$1" label="$2"
  shift 2
  if safe_capture_quiet "$output_name" "$label" "$@"; then
    return 0
  fi
  safe_report_failure "$label"
  return 1
}

safe_capture_ephemeral() {
  local output_name="$1" label="$2" status=0
  shift 2
  safe_capture_quiet "$output_name" "$label" "$@" || status=$?
  rm -f "$SAFE_LAST_STDOUT"
  SAFE_LAST_STDOUT=''
  if [[ "$status" == 0 ]]; then
    rm -f "$SAFE_LAST_STDERR"
    SAFE_LAST_STDERR=''
    return 0
  fi
  safe_report_failure "$label"
  return "$status"
}

safe_run() {
  local ignored_output=''
  safe_capture ignored_output "$@"
}

valid_container_app_name() {
  local name="$1"
  (( ${#name} >= 2 && ${#name} <= 32 )) \
    && [[ "$name" =~ ^[a-z][a-z0-9-]*[a-z0-9]$ ]] \
    && [[ "$name" != *--* ]]
}

valid_secret_file() {
  python3 - "$1" <<'PY'
import os
import stat
import sys

path = sys.argv[1]
if os.path.islink(path):
    raise SystemExit(1)
try:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
except OSError:
    raise SystemExit(1) from None
metadata = os.fstat(descriptor)
mode = stat.S_IMODE(metadata.st_mode)
valid = (
    stat.S_ISREG(metadata.st_mode)
    and metadata.st_uid == os.getuid()
    and mode & 0o077 == 0
)
with os.fdopen(descriptor, "rb") as stream:
    data = stream.read(4097)
if not valid or not data or len(data) > 4096 or b"\n" in data or b"\r" in data:
    raise SystemExit(1)
PY
}
