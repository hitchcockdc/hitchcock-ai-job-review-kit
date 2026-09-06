#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_port="${GET_A_JOB_API_PORT:-8765}"
web_port="${GET_A_JOB_WEB_PORT:-5173}"
api_started=0

cleanup() {
  if [[ "${api_started}" -eq 1 ]]; then
    kill "${api_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if ! lsof -nP -iTCP:"${api_port}" -sTCP:LISTEN >/dev/null 2>&1; then
  (
    cd "${project_root}"
    PYTHONPATH=src python3 -m get_a_job.dashboard_server --port "${api_port}" --refresh-minutes "${GET_A_JOB_REFRESH_MINUTES:-180}"
  ) &
  api_pid=$!
  api_started=1
fi

cd "${project_root}/dashboard"
exec npm run dev -- --port "${web_port}"
