"""
Build and execute notebooks/02_nlp_rebuild_semantic_layer.ipynb.

    python src/round2/make_notebook.py

Round 1 contract, kept: the notebook imports the SAME functions the pipeline
runs (round2.data / text_clean / models) and reads the SAME metrics.json the
PDFs render -- it never re-implements a transformation, so the notebook, the
models and the reports cannot drift apart. Executed at build time via
``jupyter nbconvert --execute`` so every output cell is real captured output.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import nbformat as nbf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from round2 import config as C

ROOT = C.ROOT
NB = C.NOTEBOOK_PATH

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
nb = nbf.v4.new_notebook()
nb.metadata = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}
cells: list = []

# --------------------------------------------------------------------------
cells.append(md(
    "# Data Vortex · Round 2 — Rebuilding the Semantic (NLP) Layer\n\n"
    f"**Team:** {C.TEAM_NAME} · **Member:** {', '.join(C.TEAM_MEMBERS)}\n\n"
    "**Theme:** Rebuilding the Social Engine · **Dataset:** Dataset 2 (labelled posts)\n"
    "**Tasks:** sentiment classification (primary) + topic classification (secondary) "
    "+ unsupervised topic-model agreement (bonus).\n\n"
    "| Deliverable | Location |\n"
    "|---|---|\n"
    "| Model script / notebook | `src/round2/`, this notebook |\n"
    "| Trained models | `models/round2/*.pkl` |\n"
    "| Evaluation Metrics Report | `output/round2/Evaluation_Metrics_Report.pdf` |\n"
    "| Round 2 Technical Report | `output/round2/Round2_Technical_Report.pdf` |\n\n"
    "> **This notebook is the documented workflow, not a second implementation.**\n"
    "> It calls the functions in `src/round2/` and reads `output/round2/metrics.json`\n"
    "> -- the same file the PDFs render -- so notebook, models and reports share one\n"
    "> source of truth.\n"))

cells.append(md("## 1 · Data intake & split\n\n"
                "Raw file is never modified; empties and exact duplicates go to named "
                "hold-outs; one shared stratified 80/20 split feeds both tasks."))
cells.append(code('''import sys, json
from pathlib import Path
ROOT = Path.cwd() if (Path.cwd() / "src" / "round2").exists() else Path.cwd().parent
sys.path.insert(0, str(ROOT / "src"))
from round2.data import load_splits
from round2 import config as C

train, test, profile, manifest = load_splits()
print("reconciliation:", profile["reconciliation"])
print(f"split: train {len(train):,} / test {len(test):,} "
      f"({manifest['stratify']}, seed {manifest['seed']})")
print("sentiment:", profile["sentiment_counts"])
print("topics   :", profile["topic_counts"])
print("conflicting-label texts kept as noise:", profile["n_conflicting_texts"])
train.head(3)'''))

cells.append(md("## 2 · Preprocessing demo (the shipped normaliser)\n\n"
                "Same functions the fitted pipelines embed: export repair, masking, "
                "affect markers, negation scope."))
cells.append(code('''from round2 import text_clean as tc

demos = ["some1 come wait in line with me Thursday at 3@target bc briana is being a bitch",
         "I do NOT love waiting... loooove this update!!! :) http://x.co/a @user #blessed",
         "Can't believe the app crashed again -- worst Friday ever :("]
for raw in demos:
    print("RAW :", raw)
    print("NORM:", tc.normalize_text(raw))
    print("TOKS:", tc.word_tokens(raw))
    print("ATTR:", tc.attributes_for_analysis(raw))
    print("-" * 80)'''))

cells.append(md("## 3 · Model selection (CV on train only)\n\n"
                "Six-spec ladder, stratified 5-fold CV, macro-F1. Test set untouched."))
cells.append(code('''import pandas as pd
metrics = json.loads((ROOT / "output" / "round2" / "metrics.json").read_text())
for task in ("sentiment", "topic"):
    rec = metrics["tasks"][task]
    rows = [{"model": n + ("  <-- winner" if n == rec["spec_name"] else ""),
             "cv_mean": round(s["cv_mean"], 4), "cv_std": round(s["cv_std"], 4),
             "best_params": s["best_params"]}
            for n, s in sorted(rec["specs"].items(), key=lambda kv: -kv[1]["cv_mean"])]
    print(f"--- {task} (margin over runner-up: {rec['cv_margin']:+.4f}; "
          f"calibrated: {rec['calibrated']}) ---")
    display(pd.DataFrame(rows))
    mcn = rec["mcnemar"]
    print(f"McNemar on test: b={mcn['b_a_right_b_wrong']}, c={mcn['c_a_wrong_b_right']}, "
          f"p={mcn['p_value']:.4f} (significant: {mcn['significant_05']})\\n")'''))

cells.append(md("## 4 · Held-out test results"))
cells.append(code('''for task in ("sentiment", "topic"):
    t = metrics["tasks"][task]["test_recomputed"]
    print(f"--- {task} ({metrics['tasks'][task]['spec_name']}, n={t['n']:,}) ---")
    for k in ("accuracy", "f1_macro", "f1_weighted", "mcc", "roc_auc_ovr",
              "log_loss", "brier_ovr_mean"):
        print(f"  {k:14s} {t[k]}")
    display(pd.DataFrame(metrics["tasks"][task]["test_recomputed"]["per_class"]).T)
    print()'''))

cells.append(md("### Confusion matrices, ROC, CV detail, learning curves"))
cells.append(code('''from IPython.display import Image, display
for fig in ["r2_03_confusion_sent.png", "r2_04_confusion_sent_norm.png",
            "r2_03_confusion_top.png", "r2_04_confusion_top_norm.png",
            "r2_06_roc_sent.png", "r2_06_roc_top.png",
            "r2_08_learn_sent.png", "r2_08_learn_top.png",
            "r2_07_reliability_sent.png", "r2_07_reliability_top.png",
            "r2_09_slices_sent.png", "r2_09_slices_top.png"]:
    p = ROOT / "output" / "round2" / "figures" / fig
    if p.exists():
        print(f"### {fig}")
        display(Image(str(p), width=640))'''))

cells.append(md("## 5 · Error analysis: real mistakes + measured slices"))
cells.append(code('''errs = metrics["tasks"]["sentiment"]["errors"]
print(f"{len(errs)} sampled sentiment errors (up to 3 per confusion cell):")
display(pd.DataFrame(errs).head(10))
print("\\nSlice accuracy (sentiment test):")
display(pd.DataFrame(metrics["tasks"]["sentiment"]["slices"]).T)'''))

cells.append(md("## 6 · Bonus: unsupervised topics vs human labels"))
cells.append(code('''uns = metrics["unsupervised"]
print(f"K = {uns['K']} (one per human topic); agreement scored on TEST argmax-topics")
for algo in ("lda", "nmf"):
    a = uns[algo]["agreement"]
    print(f"{algo.upper()}: NMI {a['nmi']:.4f} | ARI {a['ari']:.4f} | "
          f"homogeneity {a['homogeneity']:.4f} | completeness {a['completeness']:.4f}")
display(Image(str(ROOT / "output/round2/figures/r2_11_agreement.png"), width=760))
display(Image(str(ROOT / "output/round2/figures/r2_10_lda_words.png"), width=760))'''))

cells.append(md("## 7 · Live inference with the shipped bundles"))
cells.append(code('''import joblib
bundles = {t: joblib.load(ROOT / "models" / "round2" / f"{t}_best.pkl")
           for t in ("sentiment", "topic")}
posts = ["I absolutely love the new update, best Friday ever!!",
         "This app keeps crashing and support never replies. Furious.",
         "Reminder: community meetup moved to Sunday, see you there."]
for post in posts:
    print("POST:", post)
    for task, b in bundles.items():
        pred = b["pipeline"].predict([post])[0]
        if hasattr(b["pipeline"], "predict_proba"):
            proba = b["pipeline"].predict_proba([post])[0]
            terms = ", ".join(f"{c}={p:.2f}"
                              for c, p in zip(b["pipeline"].classes_, proba))
            print(f"  {task:10s} -> {pred}   ({terms})")
        else:
            print(f"  {task:10s} -> {pred}")
    print()'''))

cells.append(md("## 8 · Reproduce everything\n\n"
                "```bash\n"
                "pip install -r requirements-round2.txt\n"
                "./run_round2.sh   # intake -> train -> evaluate -> PDFs -> notebook\n"
                "```\n\n"
                "| Artefact | Path |\n"
                "|---|---|\n"
                "| Metrics (renders both PDFs) | `output/round2/metrics.json` |\n"
                "| Figures | `output/round2/figures/r2_*.png` |\n"
                "| Models | `models/round2/*.pkl` |\n"
                "| Upload set | `submission/round2/` + `MANIFEST.md` |\n"))

nb.cells = cells
NB.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, str(NB))
print(f"[nb] wrote {NB.relative_to(ROOT)} ({len(cells)} cells)")

result = subprocess.run(
    ["jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
     "--ExecutePreprocessor.timeout=600", str(NB)],
    cwd=str(ROOT), capture_output=True, text=True)
if result.returncode != 0:
    print("[nb] EXECUTION FAILED\n", result.stdout[-3000:], result.stderr[-3000:])
    raise SystemExit(1)
executed = nbf.reads(NB.read_text(), as_version=4)
n_out = sum(len(c.get("outputs", [])) for c in executed.cells if c.cell_type == "code")
errors = [o for c in executed.cells if c.cell_type == "code"
          for o in c.get("outputs", []) if o.get("output_type") == "error"]
print(f"[nb] executed: {len(executed.cells)} cells, {n_out} outputs, {len(errors)} errors")
if errors:
    print(errors[0]["ename"], errors[0]["evalue"])
    raise SystemExit(1)
