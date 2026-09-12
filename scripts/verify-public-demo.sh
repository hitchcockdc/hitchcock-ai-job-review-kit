#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary_root="$(mktemp -d "${TMPDIR:-/tmp}/get-a-job-public-demo.XXXXXX")"
demo_db="${temporary_root}/demo.db"
api_port="${GET_A_JOB_DEMO_API_PORT:-$(python3 -c 'import socket; sock = socket.socket(); sock.bind(("127.0.0.1", 0)); print(sock.getsockname()[1]); sock.close()')}"
api_pid=""

cleanup() {
  if [[ -n "${api_pid}" ]]; then
    kill "${api_pid}" 2>/dev/null || true
  fi
  rm -rf -- "${temporary_root}"
}
trap cleanup EXIT INT TERM

"${project_root}/scripts/create-public-demo.sh" "${demo_db}" >/dev/null
PYTHONPATH="${project_root}/src" python3 -m get_a_job.dashboard_server \
  --db "${demo_db}" --port "${api_port}" --refresh-minutes 0 >"${temporary_root}/api.log" 2>&1 &
api_pid=$!

ready=0
for _ in {1..30}; do
  if python3 -c 'import json, sys; from urllib.request import urlopen; response = urlopen(f"http://127.0.0.1:{sys.argv[1]}/api/health", timeout=1); raise SystemExit(0 if json.load(response) == {"ok": True} else 1)' "${api_port}" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.2
done
if [[ "${ready}" -ne 1 ]]; then
  cat "${temporary_root}/api.log" >&2
  echo "Synthetic demo API did not start" >&2
  exit 1
fi

python3 - "${api_port}" <<'PY'
import json
import sys
from urllib.request import urlopen

base = f"http://127.0.0.1:{sys.argv[1]}"
with urlopen(f"{base}/api/jobs?status=new&limit=10", timeout=5) as response:
    jobs = json.load(response)["jobs"]
if not jobs:
    raise SystemExit("Synthetic demo returned no reviewable jobs")
with urlopen(f"{base}/api/config", timeout=5) as response:
    profile = json.load(response)["profile"]
if profile["name"] != "Your Name":
    raise SystemExit("Synthetic demo did not load the example candidate profile")
PY

echo "Synthetic public demo API check passed"
