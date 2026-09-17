"""
Data Vortex -- Round 2: test-set analysis of the shipped models.

Reads the trained bundles + test split, recomputes every metric from scratch
(never trusts a cached number), renders all figures, and writes the single
metrics.json that both PDF reports are built from. Deterministic: no
resampling except seeded CV inside the learning curve.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import binomtest
from sklearn.base import clone
from sklearn.calibration import calibration_curve
from sklearn.metrics import (accuracy_score, brier_score_loss, confusion_matrix,
                             f1_score, log_loss, matthews_corrcoef, precision_score,
                             recall_score, roc_auc_score, roc_curve)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from round2 import config as C
from round2 import figures as F
from round2 import text_clean as tc
from round2.data import load_splits


# ---------------------------------------------------------------------------
# Core metrics (pure functions -- easy to unit-test)
# ---------------------------------------------------------------------------
def classification_metrics(y_true, y_pred, y_proba, labels: list[str]) -> dict:
    """Accuracy, F1s, per-class P/R/F1, MCC + probabilistic scores.

    WHY OvR ROC-AUC and one-vs-rest Brier: both extend naturally to 3+ class
    problems and are reported per class in the metrics report, so a model
    that is great on Positive but coin-flip on Neutral cannot hide.
    """
    y_true = pd.Series(y_true).reset_index(drop=True)
    y_pred = pd.Series(y_pred).reset_index(drop=True)
    out: dict = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, labels=labels, average="macro",
                                   zero_division=0)),
        "f1_weighted": float(f1_score(y_true, y_pred, labels=labels, average="weighted",
                                     zero_division=0)),
        "f1_micro": float(f1_score(y_true, y_pred, labels=labels, average="micro",
                                   zero_division=0)),
        "mcc": float(matthews_corrcoef(y_true, y_pred)),
        "n": int(len(y_true)),
    }
    per_class = {}
    for i, lab in enumerate(labels):
        per_class[lab] = {
            "precision": float(precision_score(y_true, y_pred, labels=labels,
                                               average=None, zero_division=0)[i]),
            "recall": float(recall_score(y_true, y_pred, labels=labels,
                                         average=None, zero_division=0)[i]),
            "f1": float(f1_score(y_true, y_pred, labels=labels, average=None,
                                 zero_division=0)[i]),
            "support": int((y_true == lab).sum()),
        }
    out["per_class"] = per_class
    if y_proba is not None:
        proba = np.asarray(y_proba, dtype=float)
        code = {lab: i for i, lab in enumerate(labels)}
        y_idx = np.array([code[v] for v in y_true])
        try:
            out["roc_auc_ovr"] = float(roc_auc_score(y_idx, proba, multi_class="ovr"))
        except ValueError:
            out["roc_auc_ovr"] = None  # a class missing from test: report, don't crash
        try:
            out["log_loss"] = float(log_loss(y_idx, proba, labels=list(range(len(labels)))))
        except ValueError:
            out["log_loss"] = None
        briers = {}
        for i, lab in enumerate(labels):
            briers[lab] = float(brier_score_loss((y_idx == i).astype(int), proba[:, i]))
        out["brier_ovr_mean"] = float(np.mean(list(briers.values())))
        out["brier_per_class"] = briers
    else:
        out.update({"roc_auc_ovr": None, "log_loss": None,
                    "brier_ovr_mean": None, "brier_per_class": None})
    return out


def confusion_counts(y_true, y_pred, labels: list[str]) -> list[list[int]]:
    return confusion_matrix(pd.Series(y_true).tolist(), pd.Series(y_pred).tolist(),
                            labels=labels).tolist()


def mcnemar_exact(y_true: list, pred_a: list, pred_b: list,
                  name_a: str, name_b: str) -> dict:
    """McNemar's test (exact binomial) on the paired test predictions.

    WHY: CV means + stds compare averages; McNemar asks whether model A's
    wins over B exceed chance *on the same test rows*. b/c << n with p > .05
    means "A leads, but the gap is not significant" -- an honest sentence the
    report must be able to print either way.
    """
    b = sum(1 for t, a, c in zip(y_true, pred_a, pred_b) if a == t and c != t)
    c = sum(1 for t, a, c in zip(y_true, pred_a, pred_b) if a != t and c == t)
    p_value = float(binomtest(min(b, c), b + c, 0.5).pvalue) if (b + c) else 1.0
    return {"model_a": name_a, "model_b": name_b, "b_a_right_b_wrong": int(b),
            "c_a_wrong_b_right": int(c), "p_value": p_value,
            "significant_05": bool(p_value < 0.05)}


def error_samples(test_df: pd.DataFrame, y_true, y_pred, labels: list[str],
                  max_per_cell: int = 3, max_chars: int = 220) -> list[dict]:
    """Up to N real misclassified examples per confusion cell, for the report's
    error analysis. Deterministic: sorted by text_id, first N kept."""
    frame = test_df[["text_id", "post_text"]].copy().reset_index(drop=True)
    frame["true"] = pd.Series(y_true).reset_index(drop=True)
    frame["pred"] = pd.Series(y_pred).reset_index(drop=True)
    frame["shown"] = frame["post_text"].map(
        lambda s: (lambda c: c if len(c) <= max_chars else c[:max_chars - 1] + "…")
        (tc.base_clean(s)))
    out = []
    for true in labels:
        for pred in labels:
            if true == pred:
                continue
            cell = frame[(frame["true"] == true) & (frame["pred"] == pred)]
            cell = cell.sort_values("text_id").head(max_per_cell)
            for _, row in cell.iterrows():
                out.append({"text_id": row["text_id"], "true": true, "pred": pred,
                            "text": row["shown"]})
    return out


def slice_metrics(test_df: pd.DataFrame, y_true, y_pred, labels: list[str]) -> dict:
    """Accuracy + macro-F1 on interpretable slices (length, negation, emoji,
    url). WHY: a single test score hides *where* the model fails; slices turn
    the error analysis from anecdotes into measurements."""
    attrs = test_df["post_text"].map(tc.attributes_for_analysis)
    frame = pd.DataFrame({"true": pd.Series(y_true).reset_index(drop=True),
                          "pred": pd.Series(y_pred).reset_index(drop=True),
                          "n_tokens": [a["n_tokens"] for a in attrs],
                          "neg": [a["has_negation"] for a in attrs],
                          "emoji": [a["has_emoji"] for a in attrs],
                          "url": [a["has_url"] for a in attrs]})

    def _score(sub: pd.DataFrame) -> dict:
        if len(sub) == 0:
            return {"n": 0, "accuracy": None, "f1_macro": None}
        return {"n": int(len(sub)),
                "accuracy": round(float((sub["true"] == sub["pred"]).mean()), 4),
                "f1_macro": round(float(f1_score(sub["true"], sub["pred"], labels=labels,
                                                average="macro", zero_division=0)), 4)}

    slices: dict = {"overall": _score(frame)}
    try:
        frame["len_bin"] = pd.qcut(frame["n_tokens"], 4,
                                   labels=["short", "medium", "long", "very_long"],
                                   duplicates="drop")
    except ValueError:
        frame["len_bin"] = "all"
    for name, sub in frame.groupby("len_bin", observed=True):
        slices[f"len_{name}"] = _score(sub)
    for col, tag in (("neg", "negation"), ("emoji", "emoji"), ("url", "url")):
        slices[f"{tag}_yes"] = _score(frame[frame[col]])
        slices[f"{tag}_no"] = _score(frame[~frame[col]])
    return slices


def roc_data(y_true, y_proba, labels: list[str]) -> dict | None:
    """Per-class OvR ROC points for the figure (recomputed, not cached)."""
    if y_proba is None:
        return None
    proba = np.asarray(y_proba, dtype=float)
    code = {lab: i for i, lab in enumerate(labels)}
    y_idx = np.array([code[v] for v in pd.Series(y_true).tolist()])
    curves = {}
    for i, lab in enumerate(labels):
        try:
            fpr, tpr, _ = roc_curve((y_idx == i).astype(int), proba[:, i])
            auc = float(roc_auc_score((y_idx == i).astype(int), proba[:, i]))
        except ValueError:
            continue
        curves[lab] = {"fpr": [round(float(v), 4) for v in fpr],
                       "tpr": [round(float(v), 4) for v in tpr], "auc": round(auc, 4)}
    return curves or None


def calibration_data(y_true, y_proba, labels: list[str], n_bins: int = 10) -> dict | None:
    """Per-class reliability points (predicted vs empirical probability)."""
    if y_proba is None:
        return None
    proba = np.asarray(y_proba, dtype=float)
    code = {lab: i for i, lab in enumerate(labels)}
    y_idx = np.array([code[v] for v in pd.Series(y_true).tolist()])
    out = {}
    for i, lab in enumerate(labels):
        try:
            prob_true, prob_pred = calibration_curve((y_idx == i).astype(int),
                                                    proba[:, i], n_bins=n_bins)
        except ValueError:
            continue
        out[lab] = {"prob_true": [round(float(v), 4) for v in prob_true],
                    "prob_pred": [round(float(v), 4) for v in prob_pred]}
    return out or None


def learning_curve_data(pipeline, X, y, labels: list[str]) -> dict:
    """Macro-F1 vs train fraction (3-fold CV). WHY: answers "would more
    labels help?" -- a plateau says the model is saturated, a rising curve
    says data, not architecture, is the bottleneck."""
    from sklearn.model_selection import StratifiedKFold, learning_curve
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=C.RANDOM_STATE)
    sizes, train_scores, valid_scores = learning_curve(
        clone(pipeline), X, y, cv=cv, scoring="f1_macro", n_jobs=-1,
        train_sizes=np.linspace(0.1, 1.0, 5), shuffle=False)
    return {"train_sizes": [int(s) for s in sizes],
            "train_mean": [round(float(v), 4) for v in train_scores.mean(axis=1)],
            "train_std": [round(float(v), 4) for v in train_scores.std(axis=1)],
            "valid_mean": [round(float(v), 4) for v in valid_scores.mean(axis=1)],
            "valid_std": [round(float(v), 4) for v in valid_scores.std(axis=1)]}


# ---------------------------------------------------------------------------
# Full evaluation run
# ---------------------------------------------------------------------------
def run_evaluation() -> dict:
    t0 = time.time()
    C.FIG_R2.mkdir(parents=True, exist_ok=True)
    train_record = json.loads((C.OUT_R2 / "train_record.json").read_text())
    train_df, test_df, profile, manifest = load_splits()

    metrics: dict = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": C.RANDOM_STATE,
        "env": _env(),
        "profile": profile,
        "split": manifest,
        "train_seconds": train_record.get("train_seconds"),
        "tasks": {},
        "unsupervised": train_record["unsupervised"],
    }

    # -- dataset figures (shared by both reports) ------------------------------
    F.fig_label_distributions(profile, C.FIG_R2 / "r2_01_label_dist.png")
    F.fig_text_lengths(train_df, test_df, C.FIG_R2 / "r2_02_text_lengths.png")

    for task, (col, id_col) in (("sentiment", ("sentiment_label", "text_id")),
                                ("topic", ("topic_category", "text_id"))):
        rec = train_record["tasks"][task]
        labels: list[str] = rec["labels"]
        bundle = joblib.load(C.MODELS_DIR / f"{task}_best.pkl")
        pipe = bundle["pipeline"]
        X_test = test_df["post_text"]
        y_test = test_df[col]
        y_pred = pipe.predict(X_test)
        y_proba = pipe.predict_proba(X_test) if hasattr(pipe, "predict_proba") else None

        # recompute (never trust the cached number) + cross-check train.py
        test_m = classification_metrics(y_test, y_pred, y_proba, labels)
        cached = rec["test"]
        for key in ("accuracy", "f1_macro"):
            assert abs(test_m[key] - cached[key]) < 1e-9, \
                f"{task} {key} mismatch: train {cached[key]} vs eval {test_m[key]}"

        errors = error_samples(test_df, y_test, y_pred, labels)
        slices = slice_metrics(test_df, y_test, y_pred, labels)
        rocs = roc_data(y_test, y_proba, labels)
        calib = calibration_data(y_test, y_proba, labels)
        lcurve = learning_curve_data(pipe, train_df["post_text"], train_df[col], labels)

        tag = "sent" if task == "sentiment" else "top"
        F.fig_confusion(rec["confusion"], labels, f"{task} -- test confusion (counts)",
                        C.FIG_R2 / f"r2_03_confusion_{tag}.png", normalize=False)
        F.fig_confusion(rec["confusion"], labels, f"{task} -- test confusion (recall)",
                        C.FIG_R2 / f"r2_04_confusion_{tag}_norm.png", normalize=True)
        F.fig_cv_compare(rec["specs"], f"{task} -- 5-fold CV macro-F1 by model",
                         C.FIG_R2 / f"r2_05_cv_{tag}.png")
        if rocs:
            F.fig_roc(rocs, rec.get("roc_auc_ovr", test_m.get("roc_auc_ovr")),
                      f"{task} -- ROC (one-vs-rest, test)",
                      C.FIG_R2 / f"r2_06_roc_{tag}.png")
        if calib:
            F.fig_reliability(calib, f"{task} -- reliability (test)",
                              C.FIG_R2 / f"r2_07_reliability_{tag}.png")
        F.fig_learning_curve(lcurve, f"{task} -- learning curve (CV macro-F1)",
                             C.FIG_R2 / f"r2_08_learn_{tag}.png")
        F.fig_slices(slices, f"{task} -- test accuracy by slice",
                     C.FIG_R2 / f"r2_09_slices_{tag}.png")

        metrics["tasks"][task] = {
            **{k: v for k, v in rec.items() if k not in ("y_test", "y_pred")},
            "test_recomputed": test_m,
            "slices": slices,
            "errors": errors,
            "roc": rocs,
            "calibration": calib,
            "learning_curve": lcurve,
        }

    # -- unsupervised figures --------------------------------------------------
    F.fig_lda_top_words(train_record["unsupervised"],
                        C.FIG_R2 / "r2_10_lda_words.png")
    F.fig_agreement_heatmap(train_record["unsupervised"],
                            C.FIG_R2 / "r2_11_agreement.png")

    metrics["eval_seconds"] = round(time.time() - t0, 1)
    C.METRICS_JSON.write_text(json.dumps(metrics, indent=2))
    print(f"  metrics -> output/round2/metrics.json ({metrics['eval_seconds']}s)")
    return metrics


def _env() -> dict:
    import platform
    import sklearn, scipy, pandas, numpy, matplotlib
    return {"python": platform.python_version(),
            "sklearn": sklearn.__version__, "scipy": scipy.__version__,
            "pandas": pandas.__version__, "numpy": numpy.__version__,
            "matplotlib": matplotlib.__version__}


def main() -> None:
    run_evaluation()


if __name__ == "__main__":
    main()
