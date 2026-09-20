#!/usr/bin/env bash
# Data Vortex -- Round 2 end-to-end reproduction (semantic/NLP layer).
# Safe to re-run: every stage is deterministic and overwrites its own outputs.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
say() { printf '\n\033[1;36m== %s\033[0m\n' "$1"; }

say "0 · dependency check"
missing=""
for m in pandas numpy matplotlib sklearn scipy reportlab PIL joblib; do
  $PY -c "import $m" 2>/dev/null || missing="$missing $m"
done
if [ -n "$missing" ]; then
  echo "Missing required packages:$missing"
  echo "Install them with:  $PY -m pip install -r requirements-round2.txt"
  exit 1
fi
if [ ! -f data/round2/raw/Dataset2.csv ]; then
  echo "Missing data/round2/raw/Dataset2.csv -- place the Round 2 CSV there."
  exit 1
fi

say "1 · intake: audit + stratified split"
$PY src/round2/data.py

say "2 · train: CV model selection + LDA/NMF"
$PY src/round2/train.py

say "3 · evaluate: metrics + figures"
$PY src/round2/evaluate.py

say "4 · build the two PDF reports"
$PY src/round2/build_eval_report.py
$PY src/round2/build_tech_report.py

say "5 · build + execute the notebook"
if $PY -c "import nbformat, nbclient" 2>/dev/null && command -v jupyter >/dev/null; then
  $PY src/round2/make_notebook.py
else
  echo "SKIP - jupyter/nbclient not installed (pip install -r requirements-round2.txt)."
fi

say "6 · assemble the form upload set"
$PY src/round2/make_submission.py

say "7 · Round 2 invariant tests"
$PY -m pytest tests/test_round2.py -q || { echo "round-2 tests failed"; exit 1; }

printf '\n\033[1;32mdone\033[0m\n'
echo "  metrics  -> output/round2/metrics.json"
echo "  figures  -> output/round2/figures/r2_*.png"
echo "  reports  -> output/round2/Evaluation_Metrics_Report.pdf"
echo "              output/round2/Round2_Technical_Report.pdf"
echo "  models   -> models/round2/*.pkl"
echo "  notebook -> notebooks/02_nlp_rebuild_semantic_layer.ipynb"
echo "  upload   -> submission/round2/ (see MANIFEST.md)"
