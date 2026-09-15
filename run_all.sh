#!/usr/bin/env bash
# Data Vortex -- end-to-end reproduction.
# Safe to re-run: every stage is deterministic and overwrites its own outputs.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
say() { printf '\n\033[1;36m== %s\033[0m\n' "$1"; }

say "0a · dependency check"
missing=""
for m in pandas numpy matplotlib; do
  $PY -c "import $m" 2>/dev/null || missing="$missing $m"
done
if [ -n "$missing" ]; then
  echo "Missing required packages:$missing"
  echo "Install them with:  $PY -m pip install -r requirements.txt"
  exit 1
fi
pdf_ok=1
$PY -c "import reportlab" 2>/dev/null || pdf_ok=0

say "0 · verify the recovered source against node_07"
$PY src/verify_source.py || echo "   (offline -- continuing with the copies in data/raw/)"

say "1 · clean + audit"
$PY src/clean_data.py

say "2 · exploratory analysis + figures"
$PY src/eda.py

say "3 · SQL schema, load, constraints"
$PY src/build_db.py

say "4 · run the analytical queries (Q1-Q12 and the E/M/H challenge set)"
$PY src/run_sql.py

say "5 · render output screenshots (both result sets)"
$PY src/make_screenshots.py

say "6 · tests / invariants"
$PY -m pytest tests -q || { echo "tests failed"; exit 1; }

say "6b · README claims vs artefacts"
$PY check_readme.py | tail -3

say "7 · build submission PDFs"
if [ "${pdf_ok:-1}" = 1 ]; then
  $PY src/build_report.py
  $PY src/build_phase2_report.py
else
  echo "SKIP - reportlab is not installed (pip install reportlab). Everything else ran."
fi

say "8 · build + execute the notebook"
$PY src/make_notebook.py

say "9 · assemble the form upload set"
$PY src/make_submission.py

printf '\n\033[1;32mdone\033[0m\n'
echo "  Phase 1 -> submission/  (upload set for the form)"
echo "            data/clean/Social_Engine_Posts_Clean.csv"
echo "            output/Phase1_EDA_Report.pdf"
echo "  Phase 2 -> output/Phase2_Insight_Report.pdf"
echo "            output/sql_outputs.md"
echo "  Phase 2 challenge set (E/M/H) ->"
echo "            output/Phase2_ChallengeSet_Report.pdf"
echo "            output/phase2_sql_outputs.md"
echo "            output/screenshots/E1.png ... H6b.png"
