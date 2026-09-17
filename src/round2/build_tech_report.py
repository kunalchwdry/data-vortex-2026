"""
Data Vortex -- Round 2: Technical Report (PDF).

Follows the rulebook's required sections (Problem Definition, Preprocessing
Pipeline, Model Selection, Training Methodology, Evaluation Metrics,
Confusion Matrix, Error Analysis) plus the team's bonus analyses. Numbers
come from metrics.json; preprocessing demos are computed live from real
train rows through the shipped normaliser.
"""
from __future__ import annotations

import functools
import json
import sys
from pathlib import Path

import pandas as pd
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from round2 import config as C
from round2 import text_clean as tc
from round2.build_eval_report import Paragraph_safe
from round2.report_common import (CAPTION, CONTENT_W, H1, H2, MARGIN, PAGE_H, PAGE_W,
                                  b, f4, footer, img, p, pct_share, styled_table,
                                  title_block)


# ---------------------------------------------------------------------------
# Live preprocessing demos on real train rows
# ---------------------------------------------------------------------------
def _pick_demo_texts(train: pd.DataFrame) -> list[tuple[str, str]]:
    """Find real posts exercising each normaliser path (social markers,
    negation, elongation/emoji, plain). Deterministic first-match search."""
    texts = train["post_text"].tolist()
    picks: list[tuple[str, str]] = []

    def _find(pred, tag):
        for t in texts:
            a = tc.attributes_for_analysis(t)
            if pred(a, t):
                picks.append((tag, t))
                return

    _find(lambda a, t: a["has_url"] or a["has_mention"] or a["has_hashtag"],
          "URLs / mentions / hashtags")
    _find(lambda a, t: a["has_negation"], "negation")
    _find(lambda a, t: a["has_emoji"] or a["has_elong"], "emoji / elongation")
    _find(lambda a, t: 8 <= a["n_tokens"] <= 25, "ordinary post")
    return picks


def _truncate(s: str, n: int) -> str:
    s = tc.base_clean(s)
    return s if len(s) <= n else s[:n - 1] + "…"


# ---------------------------------------------------------------------------
# Small computed helpers
# ---------------------------------------------------------------------------
def _top_pairs(rec: dict, k: int = 4) -> list[tuple[int, str, str]]:
    labels, cm = rec["labels"], rec["confusion"]
    pairs = sorted(((cm[i][j], labels[i], labels[j]) for i in range(len(labels))
                    for j in range(len(labels)) if i != j), reverse=True)
    return pairs[:k]


def _slice_delta_text(task: str, rec: dict) -> list[str]:
    """One honest sentence per slice comparison, computed from the numbers."""
    s = rec["slices"]
    out = []

    def _cmp(a: str, c: str, name: str) -> None:
        if a in s and c in s and s[a]["n"] and s[c]["n"]:
            d = (s[a]["accuracy"] or 0) - (s[c]["accuracy"] or 0)
            out.append(f"{name}: {a} {s[a]['accuracy']:.3f} (n={s[a]['n']:,}) vs "
                       f"{c} {s[c]['accuracy']:.3f} (n={s[c]['n']:,}) "
                       f"--> {d:+.3f}.")

    _cmp("negation_yes", "negation_no", "Negation present vs absent")
    _cmp("emoji_yes", "emoji_no", "Emoji/emoticon present vs absent")
    _cmp("url_yes", "url_no", "URL present vs absent")
    shorts = [k for k in s if k.startswith("len_")]
    if len(shorts) >= 2 and all(s[k]["n"] for k in shorts):
        accs = {k: s[k]["accuracy"] for k in shorts}
        lo, hi = min(accs, key=accs.get), max(accs, key=accs.get)
        out.append(f"Length extremes: {lo} {accs[lo]:.3f} vs {hi} {accs[hi]:.3f} "
                   f"--> spread {accs[hi] - accs[lo]:.3f}.")
    return out


def _error_rows(task_rec: dict, per_pair: int = 2) -> list[list]:
    """Real misclassified examples for the top confused pairs."""
    rows = [["true → pred", "post text (cleaned)", "id"]]
    by_pair: dict[tuple[str, str], list[dict]] = {}
    for e in task_rec["errors"]:
        by_pair.setdefault((e["true"], e["pred"]), []).append(e)
    for _, t, pr in _top_pairs(task_rec):
        for e in by_pair.get((t, pr), [])[:per_pair]:
            rows.append([f"{t} → {pr}", e["text"], e["text_id"]])
    return rows


def main() -> Path:
    metrics = json.loads(C.METRICS_JSON.read_text())
    prof, split = metrics["profile"], metrics["split"]
    train = pd.read_csv(C.TRAIN_CSV, dtype=str, keep_default_na=False)
    sent, top = metrics["tasks"]["sentiment"], metrics["tasks"]["topic"]
    story: list = []

    title_block(
        story, "Round 2 Technical Report",
        "Data Vortex 2026 · Rebuilding the Social Engine's Semantic Layer",
        [f"Team {C.TEAM_NAME} · {', '.join(C.TEAM_MEMBERS)} · {C.EVENT}",
         f"Sentiment: {sent['spec_name']} -- acc "
         f"{sent['test_recomputed']['accuracy']:.4f}, macro-F1 "
         f"{sent['test_recomputed']['f1_macro']:.4f}",
         f"Topic: {top['spec_name']} -- acc {top['test_recomputed']['accuracy']:.4f}, "
         f"macro-F1 {top['test_recomputed']['f1_macro']:.4f}"])
    story.append(PageBreak())

    # -- 1. Problem definition -------------------------------------------------
    story.append(Paragraph_safe("1 · Problem definition", H1))
    story.append(p("Round 1 restored the Social Engine's structured analytics; the "
                   "semantic layer -- understanding tone and intent -- is still down. "
                   f"Dataset 2 provides {prof['n_modeled']:,} labelled social posts "
                   "(text_id, post_text, sentiment_label, topic_category). We rebuild "
                   "two supervised classifiers:"))
    for line in [
            f"Primary -- sentiment classification into {', '.join(prof['sentiment_counts'])}.",
            f"Secondary -- topic classification into {len(prof['topics'])} categories: "
            + ", ".join(prof["topics"]) + ".",
            "Bonus (our addition) -- unsupervised topic discovery (LDA/NMF) checked "
            "against the human topic labels, plus calibration, learning-curve and "
            "slice analyses."]:
        story.append(b(line))
    story.append(p("Success criterion, fixed before training: macro-F1 on a held-out "
                   "20% test set -- macro (not accuracy) because the minority classes "
                   "are the ones a semantic layer must not ignore. The test set is "
                   "touched exactly once per task, by the refit CV winner."))

    # -- 2. Preprocessing -------------------------------------------------------
    story.append(Paragraph_safe("2 · Preprocessing pipeline", H1))
    story.append(p("One normaliser serves every model and ships inside the saved "
                   "bundles, so inference can never diverge from training. Stages:"))
    story.append(styled_table(
        [["#", "stage", "what it does", "why"],
         ["1", "export repair", "decode literal \\uXXXX escapes; unescape HTML entities (2x); fold curly quotes", "the file carries its own corruption -- fixed before any linguistics"],
         ["2", "masking", "URLs -> <url>, @mentions -> <user>, #tags -> words + <hashtag>", "learn that a link existed, not 3,000 rare URL tokens"],
         ["3", "affect markers", "emoticons -> <smile>/<sad>; emoji -> <emoji>; elongation -> doubled + <elong>", "affect signals survive as features instead of punctuation noise"],
         ["4", "contractions", "can't -> can not, 're -> are, ...", "negation must survive stopword removal"],
         ["5", "stopwords", "compact list, negations explicitly kept", "noise out, sentiment in"],
         ["6", "negation scope", "prefix next 3 content words after not/no/never/... with NOT_", "not good must not vote positive (Pang & Lee style)"],
         ["7", "features", "word TF-IDF (1,2-grams, min_df=2, sublinear) +/- char_wb TF-IDF (3-5)", "words carry sentiment; characters carry typo/elongation robustness"]],
        [8 * mm, 26 * mm, 66 * mm, 74 * mm], fontsize=7.5))
    story.append(Spacer(1, 2 * mm))
    story.append(p("Live demonstration -- real train posts through the shipped "
                   "normaliser (raw -> normalised -> first tokens):"))
    demo_rows = [["case", "raw", "normalised"]]
    for tag, raw in _pick_demo_texts(train):
        demo_rows.append([tag, _truncate(raw, 150), _truncate(tc.normalize_text(raw), 150)])
    story.append(styled_table(demo_rows, [30 * mm, 72 * mm, 72 * mm], fontsize=7.5))
    story.append(Spacer(1, 2 * mm))
    toks = [f"{tag}: {' '.join(tc.word_tokens(raw)[:12])}{' …' if len(tc.word_tokens(raw)) > 12 else ''}"
            for tag, raw in _pick_demo_texts(train)]
    story.append(styled_table([["case", "word tokens (first 12)"]] +
                              [[t.split(':')[0], t.split(': ', 1)[1]] for t in toks],
                              [30 * mm, 144 * mm], fontsize=7.5))

    # -- 3. Model selection -------------------------------------------------------
    story.append(Paragraph_safe("3 · Model selection", H1))
    story.append(p("Six specs form a ladder: chance floor (stratified dummy), classic "
                   "baseline (MultinomialNB on words), linear workhorses (LogReg / "
                   "LinearSVC on words), then the same two on words+characters. The "
                   "word-vs-union gap is the ablation that prices the character arm. "
                   "Why linear-only: 9k short texts do not justify a GPU model; "
                   "linear TF-IDF models are reproducible anywhere, inspectable, and "
                   "the honest baseline this task asks for. Grids are small "
                   f"(C in {C.LOGREG_C} / {C.SVC_C}, NB alpha in {C.NB_ALPHA}, "
                   "class_weight in {None, balanced}) -- compared, not assumed."))
    for task, rec in (("sentiment", sent), ("topic", top)):
        story.append(Paragraph_safe(f"CV results -- {task}", H2))
        rows = [["model", "CV macro-F1", "best params"]]
        for name in sorted(rec["specs"], key=lambda n: -rec["specs"][n]["cv_mean"]):
            s = rec["specs"][name]
            params = ", ".join(f"{k.replace('clf__', '')}={v}"
                               for k, v in s["best_params"].items()) or "—"
            star = " ★ winner" if name == rec["spec_name"] else ""
            rows.append([name + star, f"{s['cv_mean']:.4f} ± {s['cv_std']:.4f}", params])
        story.append(styled_table(rows, [40 * mm, 40 * mm, 94 * mm], center_cols={1}))
        tag = "sent" if task == "sentiment" else "top"
        story.append(img(C.FIG_R2 / f"r2_05_cv_{tag}.png", max_width=CONTENT_W * 0.85))
        story.append(p(f"Figure: {task} CV macro-F1 by model.", CAPTION))

    # -- 4. Training methodology ---------------------------------------------------
    story.append(Paragraph_safe("4 · Training methodology", H1))
    for line in [
            f"One shared stratified split ({split['stratify']}, seed {split['seed']}): "
            f"{split['n_train']:,} train / {split['n_test']:,} test, id overlap "
            f"{split['id_overlap']}. Both tasks share it, so their scores are comparable.",
            f"Grid search with {sent['n_cv_folds']}/{top['n_cv_folds']}-fold stratified CV "
            f"(sentiment/topic) on train only, scoring macro-F1; ties broken toward the "
            "simpler spec.",
            "Winner refit on full train (GridSearchCV refit), evaluated ONCE on test.",
            ("Sentiment winner ships sigmoid-calibrated (3-fold, train only) because "
             "LinearSVC has no native probabilities; topic winner "
             + ("likewise." if top["calibrated"] else "has native probabilities already.")),
            f"Unsupervised LDA/NMF (K={metrics['unsupervised']['K']}) fit on train texts "
            "with no labels; agreement scored on test.",
            f"Total train time {metrics.get('train_seconds')}s; one seed ({metrics['seed']}) "
            "drives splits, folds and samplers; environment recorded in the metrics report."]:
        story.append(b(line))

    # -- 5. Evaluation metrics ------------------------------------------------------
    story.append(Paragraph_safe("5 · Evaluation metrics", H1))
    story.append(styled_table(
        [["metric (test)", "sentiment", "topic"]] +
        [[m, f4(sent["test_recomputed"][k]), f4(top["test_recomputed"][k])]
         for m, k in [("accuracy", "accuracy"), ("macro-F1 ★ primary", "f1_macro"),
                      ("weighted-F1", "f1_weighted"), ("MCC", "mcc"),
                      ("ROC-AUC OvR", "roc_auc_ovr"), ("log-loss", "log_loss"),
                      ("Brier OvR", "brier_ovr_mean")]],
        [52 * mm, 61 * mm, 61 * mm], center_cols={1, 2}))
    story.append(Spacer(1, 2 * mm))
    for task, rec in (("sentiment", sent), ("topic", top)):
        story.append(Paragraph_safe(f"Per-class -- {task} ({rec['spec_name']})", H2))
        rows = [["class", "precision", "recall", "F1", "support"]]
        for lab in rec["labels"]:
            d = rec["test_recomputed"]["per_class"][lab]
            rows.append([lab, f4(d["precision"]), f4(d["recall"]), f4(d["f1"]),
                         f"{d['support']:,}"])
        story.append(styled_table(rows, [52 * mm, 26 * mm, 26 * mm, 26 * mm, 26 * mm],
                                  center_cols={1, 2, 3, 4}))
        tag = "sent" if task == "sentiment" else "top"
        roc_path = C.FIG_R2 / f"r2_06_roc_{tag}.png"
        if roc_path.exists():
            story.append(img(roc_path, max_width=CONTENT_W * 0.62))
            story.append(p(f"Figure: {task} ROC, one-vs-rest (test).", CAPTION))

    # -- 6. Confusion matrix ----------------------------------------------------------
    story.append(Paragraph_safe("6 · Confusion matrix", H1))
    story.append(p("Counts show where the errors are; row-normalised (recall) shows "
                   "which classes the model refuses to predict. Read with the "
                   "per-class table above: a rare class with high precision but low "
                   "recall is being under-predicted, not mispredicted."))
    for task in ("sentiment", "topic"):
        tag = "sent" if task == "sentiment" else "top"
        story.append(img(C.FIG_R2 / f"r2_03_confusion_{tag}.png", max_width=CONTENT_W * 0.6))
        story.append(p(f"Figure: {task} confusion (counts, test).", CAPTION))
        story.append(img(C.FIG_R2 / f"r2_04_confusion_{tag}_norm.png", max_width=CONTENT_W * 0.6))
        story.append(p(f"Figure: {task} confusion (row-normalised = recall).", CAPTION))

    # -- 7. Error analysis ----------------------------------------------------------------
    story.append(Paragraph_safe("7 · Error analysis", H1))
    for task, rec in (("sentiment", sent), ("topic", top)):
        story.append(Paragraph_safe(f"7.{'1' if task == 'sentiment' else '2'} · {task} -- "
                                    "measured slices", H2))
        for sentence in _slice_delta_text(task, rec):
            story.append(b(sentence))
        tag = "sent" if task == "sentiment" else "top"
        story.append(img(C.FIG_R2 / f"r2_09_slices_{tag}.png"))
        story.append(p(f"Figure: {task} accuracy by slice (test).", CAPTION))
        story.append(Paragraph_safe(f"{task} -- real mistakes (top confused pairs)", H2))
        story.append(p(" verbatim cleaned posts the shipped model got wrong -- the "
                       "qualitative half of the analysis. IDs let judges re-find each "
                       "row in the test split."))
        story.append(styled_table(_error_rows(rec), [30 * mm, 112 * mm, 32 * mm],
                                  fontsize=7.5))

    # -- 8. Bonus analyses -------------------------------------------------------------------
    story.append(Paragraph_safe("8 · Bonus analyses (our additions)", H1))
    story.append(Paragraph_safe("8.1 · Do discovered topics match human topics?", H2))
    uns = metrics["unsupervised"]
    story.append(p("LDA and NMF discover topics with no labels; we check them against "
                   "the human topic_category on test texts. NMI/ARI near 0 would mean "
                   "the human taxonomy is invisible to word co-occurrence; high values "
                   "validate it."))
    story.append(styled_table(
        [["model", "NMI", "ARI", "homogeneity", "completeness"]] +
        [[algo.upper(), f4(uns[algo]["agreement"]["nmi"]), f4(uns[algo]["agreement"]["ari"]),
          f4(uns[algo]["agreement"]["homogeneity"]), f4(uns[algo]["agreement"]["completeness"])]
         for algo in ("lda", "nmf")],
        [26 * mm, 32 * mm, 32 * mm, 42 * mm, 42 * mm], center_cols={1, 2, 3, 4}))
    story.append(img(C.FIG_R2 / "r2_11_agreement.png"))
    story.append(p("Figure: human vs discovered topic agreement.", CAPTION))
    story.append(img(C.FIG_R2 / "r2_10_lda_words.png"))
    story.append(p("Figure: LDA top-10 words per discovered topic.", CAPTION))
    story.append(Paragraph_safe("8.2 · Would more labels help?", H2))
    story.append(p("Learning curves (3-fold CV macro-F1 vs train size) separate a data "
                   "bottleneck (rising validation curve) from model saturation "
                   "(plateau)."))
    story.append(img(C.FIG_R2 / "r2_08_learn_sent.png"))
    story.append(p("Figure: sentiment learning curve.", CAPTION))
    story.append(img(C.FIG_R2 / "r2_08_learn_top.png"))
    story.append(p("Figure: topic learning curve.", CAPTION))
    story.append(Paragraph_safe("8.3 · Can we trust the probabilities?", H2))
    story.append(p("Reliability diagrams plot predicted vs empirical probability per "
                   "class; the Brier scores are in §5. Well-calibrated probabilities "
                   "are what let the Social Engine threshold (act only when confident) "
                   "instead of argmaxing blindly."))
    for task in ("sentiment", "topic"):
        tag = "sent" if task == "sentiment" else "top"
        rel = C.FIG_R2 / f"r2_07_reliability_{tag}.png"
        if rel.exists():
            story.append(img(rel, max_width=CONTENT_W * 0.62))
            story.append(p(f"Figure: {task} reliability (test).", CAPTION))
    story.append(Paragraph_safe("8.4 · Surface entity census (regex baseline)", H2))
    attrs = train["post_text"].map(tc.attributes_for_analysis).tolist()
    n = len(attrs)
    census = [["signal", "posts", "share"]] + [
        [name, f"{c:,}", pct_share(c, n)] for name, c in
        [("URL", sum(a["has_url"] for a in attrs)),
         ("@mention", sum(a["has_mention"] for a in attrs)),
         ("#hashtag", sum(a["has_hashtag"] for a in attrs)),
         ("emoji/emoticon", sum(a["has_emoji"] for a in attrs)),
         ("negation word", sum(a["has_negation"] for a in attrs))]]
    story.append(styled_table(census, [52 * mm, 40 * mm, 40 * mm], center_cols={1, 2}))
    story.append(p("Framed honestly: this is a pattern-based entity census over train, "
                   "not a trained NER -- it quantifies what a future NER layer would "
                   "have to recognise (handles, tags, links). A supervised NER head is "
                   "listed under future work, not claimed as done."))

    # -- 9. Limitations -------------------------------------------------------------------------
    story.append(Paragraph_safe("9 · Limitations & threats to validity", H1))
    for line in [
            f"Label noise: {prof['n_conflicting_texts']:,} distinct texts appear with "
            "conflicting labels -- an upper bound on achievable accuracy no model can cross.",
            "Short-text ambiguity: one-liners with no context (names, scores, event "
            "mentions) are genuinely hard; the length slices in §7 quantify it.",
            "No external pretraining by design: linear TF-IDF cannot resolve sarcasm or "
            "world knowledge; misclassified examples in §7 show the boundary.",
            "Domain shift: trained on this export's style (escapes, entities); new "
            "corruption modes would need the normaliser extended, not the models retuned.",
            "Topics are imbalanced (see §5 support column); macro-F1 keeps the rare "
            "topics honest, but their confidence intervals are wide."]:
        story.append(b(line))

    # -- 10. Reproducibility + conclusion -------------------------------------------------------------
    story.append(Paragraph_safe("10 · Reproducibility", H1))
    for line in [
            "Reproduce: pip install -r requirements-round2.txt && ./run_round2.sh",
            "Pipeline: src/round2/{data,train,evaluate,figures,build_eval_report,"
            "build_tech_report,predict}.py -- one seed (42) throughout.",
            "Artefacts: models/round2/*.pkl, output/round2/metrics.json + figures + PDFs, "
            "notebooks/02_nlp_rebuild_semantic_layer.ipynb (executed).",
            "Inference demo: python src/round2/predict.py --text \"...\""]:
        story.append(b(line))
    story.append(Paragraph_safe("11 · Conclusion", H1))
    story.append(p(f"The semantic layer is rebuilt: {sent['spec_name']} for sentiment "
                   f"(test macro-F1 {sent['test_recomputed']['f1_macro']:.4f}) and "
                   f"{top['spec_name']} for topic (test macro-F1 "
                   f"{top['test_recomputed']['f1_macro']:.4f}), selected by CV on train, "
                   "confirmed once on held-out test, with calibrated probabilities, "
                   "measured failure slices and published mistakes. Every claim above "
                   "traces to output/round2/metrics.json."))

    out = C.TECH_REPORT_PDF
    doc = SimpleDocTemplate(str(out), pagesize=(PAGE_W, PAGE_H),
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title="Round 2 Technical Report -- Data Vortex",
                            author=C.TEAM_NAME)
    doc.build(story, onFirstPage=functools.partial(footer, short_title="Tech Report"),
              onLaterPages=functools.partial(footer, short_title="Tech Report"))
    print(f"  tech report -> {out} ({out.stat().st_size / 1024:.0f} KB)")
    return out


if __name__ == "__main__":
    main()
