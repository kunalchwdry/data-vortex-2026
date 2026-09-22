#!/usr/bin/env bash
# Data Vortex -- Round 3 end-to-end reproduction (live monitoring layer).
# Safe to re-run: every stage is deterministic and overwrites its own outputs.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
say() { printf "\n\033[1;36m== %s\033[0m\n" "$1"; }

say "0 - dependency check"
$PY -c "import requests, pandas, sklearn, matplotlib, reportlab" 2>/dev/null \
  || { echo "Missing packages:  $PY -m pip install -r requirements-round3.txt"; exit 1; }

say "1 - live collection sweep"
# Set the assigned topic in src/round3/config.py (D1) first.
# SMOKE=1 ./run_round3.sh runs a plumbing test instead (no topic needed).
if [ "${SMOKE:-0}" = "1" ]; then
  $PY src/round3/collect.py --smoke
else
  $PY src/round3/collect.py
fi

say "2 - real-time analysis (sentiment / activity / topics / shifts)"
$PY src/round3/analyze.py

say "3 - notebook + Round 3 analytical report"
$PY src/round3/build_report.py
$PY src/round3/make_notebook.py

printf '\n\033[1;32mdone\033[0m\n'
echo "  raw      -> data/round3/live/posts.jsonl"
echo "  dataset  -> data/round3/round3_live_dataset.csv (deliverable #1)"
echo "  sweeplog-> data/round3/live/sweep_log.jsonl"
echo "  scores   -> output/round3/scored.csv"
echo "  figures  -> output/round3/figures/r3_*.png"
echo "  report   -> output/round3/Round3_Analytical_Report.pdf (deliverable #4)"
echo "  notebook -> notebooks/03_live_monitoring_real_time_analysis.ipynb (deliverable #3)"
