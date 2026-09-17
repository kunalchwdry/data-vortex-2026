"""
Data Vortex -- Round 2: Evaluation Metrics Report (PDF).

A pure rendering of output/round2/metrics.json -- this script computes
nothing new. If a number is in the PDF, it came from the metrics file, which
came from the models, which came from Dataset 2.
"""
from __future__ import annotations

import functools
import json
import sys
from pathlib import Path

from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from round2 import config as C
from round2.report_common import (BODY, CONTENT_W, H1, H2, MARGIN, PAGE_H, PAGE_W,
                                  b, cell, f4, footer, img, p, pct_share,
                                  styled_table, title_block, CAPTION)


def _task_story(story: list, metrics: dict, task: str) -> None:
    rec = metrics["tasks"][task]
    labels: list[str] = rec["labels"]
    tag = "sent" if task == "sentiment" else "top"
    test = rec["test_recomputed"]
    story.append(Paragraph_safe(f"Task: {task} classification", H1))

    # -- model selection --------------------------------------------------
    story.append(Paragraph_safe("Model selection (CV on train only)", H2))
    story.append(p(f"{rec['n_cv_folds']}-fold stratified cross-validation, scoring macro-F1. "
                   f"Winner: {rec['spec_name']} "
                   f"(CV {rec['specs'][rec['spec_name']]['cv_mean']:.4f} ± "
                   f"{rec['specs'][rec['spec_name']]['cv_std']:.4f}), margin "
                   f"{rec['cv_margin']:+.4f} over runner-up {rec['runner_up']}. "
                   f"{'Winner ships sigmoid-calibrated (LinearSVC has no native probabilities).' if rec['calibrated'] else 'Winner ships uncalibrated (native probabilities).'}"))
    rows = [["model", "CV macro-F1 (mean ± sd)", "best params", "fit (s)"]]
    for name in sorted(rec["specs"], key=lambda n: -rec["specs"][n]["cv_mean"]):
        s = rec["specs"][name]
        params = ", ".join(f"{k.replace('clf__', '')}={v}" for k, v in s["best_params"].items()) or "—"
        star = " ★" if name == rec["spec_name"] else ""
        rows.append([name + star, f"{s['cv_mean']:.4f} ± {s['cv_std']:.4f}", params,
                     f"{s['fit_seconds']}"])
    story.append(styled_table(rows, [34 * mm, 40 * mm, 62 * mm, 20 * mm],
                              center_cols={1, 3}))
    story.append(img(C.FIG_R2 / f"r2_05_cv_{tag}.png"))
    story.append(p(f"Figure: {task} -- mean CV macro-F1 per model (error bar = ±1 sd "
                   "across folds; winner in green).", CAPTION))
    mcn = rec["mcnemar"]
    story.append(p(f"Head-to-head on the test set ({mcn['model_a']} vs {mcn['model_b']}): "
                   f"b={mcn['b_a_right_b_wrong']} rows where shipped wins, "
                   f"c={mcn['c_a_wrong_b_right']} where runner-up wins, McNemar exact "
                   f"p={mcn['p_value']:.4f} -- "
                   f"{'significant at 5%: the gap is real.' if mcn['significant_05'] else 'not significant at 5%: the lead is within chance.'}"))

    # -- test metrics ------------------------------------------------------
    story.append(Paragraph_safe("Held-out test metrics", H2))
    story.append(styled_table(
        [["metric", "value"],
         ["accuracy", f4(test["accuracy"])],
         ["macro-F1 (primary)", f4(test["f1_macro"])],
         ["weighted-F1", f4(test["f1_weighted"])],
         ["micro-F1", f4(test["f1_micro"])],
         ["MCC", f4(test["mcc"])],
         ["ROC-AUC (OvR)", f4(test["roc_auc_ovr"])],
         ["log-loss", f4(test["log_loss"])],
         ["Brier (OvR mean)", f4(test["brier_ovr_mean"])],
         ["test rows", f"{test['n']:,}"]],
        [52 * mm, 40 * mm], center_cols={1}))
    story.append(Spacer(1, 2 * mm))
    pc_rows = [["class", "precision", "recall", "F1", "support"]]
    for lab in labels:
        d = test["per_class"][lab]
        pc_rows.append([lab, f4(d["precision"]), f4(d["recall"]), f4(d["f1"]),
                        f"{d['support']:,}"])
    story.append(styled_table(pc_rows, [52 * mm, 26 * mm, 26 * mm, 26 * mm, 26 * mm],
                              center_cols={1, 2, 3, 4}))
    story.append(img(C.FIG_R2 / f"r2_03_confusion_{tag}.png", max_width=CONTENT_W * 0.62))
    story.append(p(f"Figure: {task} -- test confusion matrix (counts).", CAPTION))
    story.append(img(C.FIG_R2 / f"r2_04_confusion_{tag}_norm.png", max_width=CONTENT_W * 0.62))
    story.append(p(f"Figure: {task} -- test confusion matrix (row-normalised = recall).",
                   CAPTION))
    roc_path = C.FIG_R2 / f"r2_06_roc_{tag}.png"
    if roc_path.exists():
        story.append(img(roc_path, max_width=CONTENT_W * 0.62))
        story.append(p(f"Figure: {task} -- ROC curves, one-vs-rest (test).", CAPTION))
    rel_path = C.FIG_R2 / f"r2_07_reliability_{tag}.png"
    if rel_path.exists():
        story.append(img(rel_path, max_width=CONTENT_W * 0.62))
        story.append(p(f"Figure: {task} -- reliability diagram (test). Points on the "
                       "diagonal = predicted probabilities match empirical rates.",
                       CAPTION))
    story.append(img(C.FIG_R2 / f"r2_08_learn_{tag}.png"))
    story.append(p(f"Figure: {task} -- learning curve (3-fold CV macro-F1 vs train size). "
                   "A plateauing validation curve means more labels would barely help.",
                   CAPTION))

    # -- slices --------------------------------------------------------------
    story.append(Paragraph_safe("Slice analysis (where it fails)", H2))
    story.append(p("Accuracy and macro-F1 on interpretable slices of the test set. "
                   "Slices are computed from the raw text only (length quartile, "
                   "negation / emoji / URL presence) -- no label leakage."))
    s_rows = [["slice", "n", "accuracy", "macro-F1"]]
    order = ["overall"] + [k for k in rec["slices"] if k.startswith("len_")] + \
            [k for k in rec["slices"] if k != "overall" and not k.startswith("len_")]
    for key in order:
        s = rec["slices"][key]
        s_rows.append([key, f"{s['n']:,}", f4(s["accuracy"]), f4(s["f1_macro"])])
    story.append(styled_table(s_rows, [44 * mm, 30 * mm, 40 * mm, 40 * mm],
                              center_cols={1, 2, 3}))
    story.append(img(C.FIG_R2 / f"r2_09_slices_{tag}.png"))
    story.append(p(f"Figure: {task} -- test accuracy by slice.", CAPTION))

    # -- most confused pairs ---------------------------------------------------
    story.append(Paragraph_safe("Most confused pairs", H2))
    cm = rec["confusion"]
    pairs = sorted(((cm[i][j], labels[i], labels[j])
                    for i in range(len(labels)) for j in range(len(labels)) if i != j),
                   reverse=True)[:5]
    story.append(styled_table(
        [["true → predicted", "rows"]] +
        [[f"{t} → {pr}", f"{n:,}"] for n, t, pr in pairs],
        [70 * mm, 30 * mm], center_cols={1}))


def Paragraph_safe(text: str, style) -> object:
    from reportlab.platypus import Paragraph
    from xml.sax.saxutils import escape
    return Paragraph(escape(text), style)


def main() -> Path:
    metrics = json.loads(C.METRICS_JSON.read_text())
    prof, split = metrics["profile"], metrics["split"]
    story: list = []

    sent = metrics["tasks"]["sentiment"]
    top = metrics["tasks"]["topic"]
    title_block(
        story, "Evaluation Metrics Report",
        "Data Vortex 2026 · Round 2 · Rebuilding the Semantic Layer",
        [f"Team {C.TEAM_NAME} · {', '.join(C.TEAM_MEMBERS)} · {C.EVENT}",
         f"Dataset 2: {prof['n_modeled']:,} modeled rows "
         f"(train {split['n_train']:,} / test {split['n_test']:,}, seed {metrics['seed']})",
         f"Sentiment: {sent['spec_name']} -- test macro-F1 "
         f"{sent['test_recomputed']['f1_macro']:.4f} · "
         f"Topic: {top['spec_name']} -- test macro-F1 "
         f"{top['test_recomputed']['f1_macro']:.4f}"])
    story.append(PageBreak())

    # -- dataset ------------------------------------------------------------
    story.append(Paragraph_safe("Dataset & split", H1))
    story.append(p(f"Row reconciliation: {prof['reconciliation']}. Empty-text rows "
                   f"({prof['n_empty_heldout']:,}) and exact (text, labels) duplicates "
                   f"({prof['n_dupe_heldout']:,}) are held out in named files under "
                   "data/round2/clean/ -- never silently dropped, never imputed. "
                   f"{prof['n_conflicting_texts']:,} distinct texts carry conflicting "
                   "labels across rows and are kept as-is (reported label noise)."))
    rows = [["sentiment", "rows", "share"]] + \
           [[k, f"{v:,}", pct_share(v, prof["n_modeled"])]
            for k, v in prof["sentiment_counts"].items()]
    story.append(styled_table(rows, [44 * mm, 36 * mm, 36 * mm], center_cols={1, 2}))
    story.append(Spacer(1, 2 * mm))
    rows = [["topic", "rows", "share"]] + \
           [[k, f"{v:,}", pct_share(v, prof["n_modeled"])]
            for k, v in sorted(prof["topic_counts"].items(), key=lambda kv: -kv[1])]
    story.append(styled_table(rows, [64 * mm, 36 * mm, 36 * mm], center_cols={1, 2}))
    story.append(p(f"Split: {split['n_train']:,} train / {split['n_test']:,} test "
                   f"(stratified: {split['stratify']}, seed {split['seed']}, "
                   f"id overlap {split['id_overlap']}). Text length: median "
                   f"{prof['length_chars']['p50']:.0f} chars, mean "
                   f"{prof['length_chars']['mean']:.1f}, max {prof['length_chars']['max']:,}."))
    story.append(img(C.FIG_R2 / "r2_01_label_dist.png"))
    story.append(p("Figure: label distributions over modeled rows.", CAPTION))
    story.append(img(C.FIG_R2 / "r2_02_text_lengths.png"))
    story.append(p("Figure: post-length distributions -- train vs test overlap shows "
                   "the split did not segregate short/long posts.", CAPTION))

    # -- tasks ----------------------------------------------------------------
    _task_story(story, metrics, "sentiment")
    _task_story(story, metrics, "topic")

    # -- unsupervised ----------------------------------------------------------
    story.append(Paragraph_safe("Unsupervised topic-model agreement (bonus)", H1))
    uns = metrics["unsupervised"]
    story.append(p(f"LDA and NMF, K={uns['K']} (= number of human topic labels), fit on "
                   "train texts without labels; agreement scored on TEST texts by "
                   "comparing each post's argmax topic against its human topic label."))
    u_rows = [["model", "NMI", "ARI", "homogeneity", "completeness", "fit quality"]]
    for algo in ("lda", "nmf"):
        a = uns[algo]["agreement"]
        fit = (f"perplexity {uns[algo]['perplexity_test']:.1f}" if algo == "lda"
               else f"recon err {uns[algo]['reconstruction_err_train']:.1f}")
        u_rows.append([algo.upper(), f4(a["nmi"]), f4(a["ari"]), f4(a["homogeneity"]),
                       f4(a["completeness"]), fit])
    story.append(styled_table(u_rows, [22 * mm, 24 * mm, 24 * mm, 30 * mm, 30 * mm, 34 * mm],
                              center_cols={1, 2, 3, 4}))
    story.append(img(C.FIG_R2 / "r2_11_agreement.png"))
    story.append(p("Figure: human topic (rows) vs discovered topic (columns); "
                   "cell = row share with raw count.", CAPTION))
    for algo in ("lda", "nmf"):
        story.append(img(C.FIG_R2 / f"r2_10_{algo}_words.png"))
        story.append(p(f"Figure: {algo.upper()} discovered topics -- top-10 words "
                       "per topic, ranked by component weight.", CAPTION))

    # -- reproducibility ---------------------------------------------------------
    story.append(Paragraph_safe("Reproducibility", H1))
    env = metrics["env"]
    story.append(styled_table(
        [["component", "version"]] +
        [[k, v] for k, v in env.items()] +
        [["seed", str(metrics["seed"])],
         ["train time (s)", str(metrics.get("train_seconds"))],
         ["eval time (s)", str(metrics.get("eval_seconds"))],
         ["generated (UTC)", str(metrics["generated"])]],
        [52 * mm, 100 * mm]))
    story.append(Spacer(1, 2 * mm))
    for line in [
            "Reproduce: pip install -r requirements-round2.txt && ./run_round2.sh",
            "Models: models/round2/{sentiment_best,topic_best,topic_lda,topic_nmf}.pkl",
            "Metrics source: output/round2/metrics.json (this PDF renders it)",
            "Inference: python src/round2/predict.py --text \"...\""]:
        story.append(b(line))

    out = C.EVAL_REPORT_PDF
    doc = SimpleDocTemplate(str(out), pagesize=(PAGE_W, PAGE_H),
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title="Evaluation Metrics Report -- Data Vortex Round 2",
                            author=C.TEAM_NAME)
    doc.build(story, onFirstPage=functools.partial(footer, short_title="Eval Metrics"),
              onLaterPages=functools.partial(footer, short_title="Eval Metrics"))
    print(f"  eval report -> {out} ({out.stat().st_size / 1024:.0f} KB)")
    return out


if __name__ == "__main__":
    main()
