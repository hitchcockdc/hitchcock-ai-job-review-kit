#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 || ! -d "$1/.git" ]]; then
  echo "Usage: $0 /path/to/clean/public-repository-checkout" >&2
  exit 2
fi

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -n "$(git -C "${project_root}" status --porcelain --untracked-files=all)" ]]; then
  echo "Private working tree must be clean before creating a public release." >&2
  exit 2
fi

git -C "${project_root}" diff --check
PYTHONPATH="${project_root}/src" python3 -m unittest discover -s "${project_root}/tests" -v
(
  cd "${project_root}/dashboard"
  npm run verify:release
)
"${project_root}/scripts/verify-public-demo.sh"
"${project_root}/scripts/verify-public-export.sh" "$1"

echo "Release verification passed"
