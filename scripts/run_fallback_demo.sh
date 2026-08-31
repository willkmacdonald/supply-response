#!/usr/bin/env bash
set -euo pipefail

script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "${script_directory}/.." && pwd)"

cd "${repository_root}"

.venv/bin/pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e -- fallback-demo.spec.ts fallback-failures.spec.ts
