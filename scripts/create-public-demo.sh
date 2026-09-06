#!/usr/bin/env bash
set -euo pipefail

demo_db="${1:-demo.db}"
rm -f "$demo_db"
PYTHONPATH=src python3 -m get_a_job --db "$demo_db" init-db
PYTHONPATH=src python3 -m get_a_job --db "$demo_db" import-profile examples/profile.example.json
PYTHONPATH=src python3 -m get_a_job --db "$demo_db" import-jobs examples/jobs.example.json
echo "Synthetic demo database created at $demo_db"
