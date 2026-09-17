"""
Data Vortex -- Round 2: model selection + training.

Protocol (per task -- sentiment, then topic):
  1. Grid-search every spec with stratified 5-fold CV on TRAIN, scoring
     macro-F1. The test set is not touched here.
  2. Winner = highest mean CV macro-F1 (ties -> simpler spec, spec order).
  3. Refit winner on full train (= GridSearchCV's refit), evaluate ONCE on
     test, save the model + full CV record.
  4. If the winner cannot output probabilities (LinearSVC), wrap it in
     sigmoid calibration (3-fold, fit on train only) so the shipped model
     supports predict_proba for ROC/calibration analysis.

Then unsupervised LDA + NMF (K = # labelled topics) for the
unsupervised-vs-human agreement analysis.

All randomness flows from config.RANDOM_STATE; all artefacts land in
models/round2/ (+ a JSON CV record beside them for the reports).
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
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.decomposition import LatentDirichletAllocation, NMF
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from round2 import config as C
from round2 import evaluate as E
from round2 import models as M
from round2.data import load_splits


def _jsonable(obj):
    """Recursively convert numpy scalars/arrays to plain Python for JSON."""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_jsonable(v) for v in obj.tolist()]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    return obj


def cv_folds(y: pd.Series) -> StratifiedKFold:
    """Stratified folds, defensively capped by the smallest class.

    WHY: a rare topic with < 5 train rows would make 5-fold CV impossible;
    capping keeps the protocol running instead of crashing, and the fold
    count is recorded in the output so the change is visible, not hidden.
    """
    smallest = int(y.value_counts().min())
    n = max(2, min(C.CV_FOLDS, smallest))
    return StratifiedKFold(n_splits=n, shuffle=True, random_state=C.RANDOM_STATE)


def run_task(task: str, target_col: str, labels: list[str],
             X_train: pd.Series, y_train: pd.Series,
             X_test: pd.Series, y_test: pd.Series) -> dict:
    """Grid-search all specs, ship the winner, evaluate once on test."""
    folds = cv_folds(y_train)
    print(f"  [{task}] CV: {folds.get_n_splits()} folds x {len(M.model_specs())} specs, "
          f"scoring {C.CV_SCORING}")
    spec_records: dict[str, dict] = {}
    fitted: dict[str, object] = {}
    for spec in M.model_specs():
        t0 = time.time()
        pipe = M.build_pipeline(spec)
        gs = GridSearchCV(pipe, spec["grid"], cv=folds, scoring=C.CV_SCORING,
                          refit=True, n_jobs=-1, return_train_score=False)
        gs.fit(X_train, y_train)
        fitted[spec["name"]] = gs.best_estimator_
        # per-fold scores of the winning params:
        per_fold = [float(gs.cv_results_[f"split{i}_test_score"][gs.best_index_])
                    for i in range(folds.get_n_splits())]
        spec_records[spec["name"]] = {
            "best_params": _jsonable(gs.best_params_),
            "cv_mean": float(np.mean(per_fold)),
            "cv_std": float(np.std(per_fold)),
            "cv_folds": per_fold,
            "fit_seconds": round(time.time() - t0, 1),
            "n_candidates": int(len(gs.cv_results_["params"])),
        }
        print(f"    {spec['name']:14s} cv macro-F1 "
              f"{np.mean(per_fold):.4f} ± {np.std(per_fold):.4f}  {gs.best_params_}")

    order = [s["name"] for s in M.model_specs()]
    ranked = sorted(order, key=lambda n: (-spec_records[n]["cv_mean"], order.index(n)))
    best_name, runner_name = ranked[0], ranked[1]
    margin = spec_records[best_name]["cv_mean"] - spec_records[runner_name]["cv_mean"]
    print(f"  [{task}] winner: {best_name} (margin over {runner_name}: {margin:+.4f})")

    best = fitted[best_name]
    calibrated = False
    if C.CALIBRATE_NON_PROBABILISTIC and not hasattr(best, "predict_proba"):
        # LinearSVC has no predict_proba; calibrate on train folds only.
        final = CalibratedClassifierCV(estimator=clone(best),
                                       method=C.CALIBRATION_METHOD,
                                       cv=C.CALIBRATION_CV)
        final.fit(X_train, y_train)
        calibrated = True
        print(f"  [{task}] wrapped in {C.CALIBRATION_METHOD} calibration "
              f"(cv={C.CALIBRATION_CV}) for probability outputs")
    else:
        final = best

    # The single sanctioned touch of the test set for this task.
    y_pred = final.predict(X_test)
    y_proba = final.predict_proba(X_test) if hasattr(final, "predict_proba") else None
    test_metrics = E.classification_metrics(y_test, y_pred, y_proba, labels)
    runner_pred = fitted[runner_name].predict(X_test)
    mcnemar = E.mcnemar_exact(
        pd.Series(y_test).tolist(), list(y_pred), list(runner_pred),
        name_a=f"{best_name}{'*' if calibrated else ''} (shipped)",
        name_b=f"{runner_name} (runner-up)")

    bundle = {"task": task, "target_col": target_col, "labels": labels,
              "spec_name": best_name, "calibrated": calibrated,
              "best_params": spec_records[best_name]["best_params"],
              "pipeline": final}
    model_path = C.MODELS_DIR / f"{task}_best.pkl"
    joblib.dump(bundle, model_path)
    print(f"  [{task}] test: acc {test_metrics['accuracy']:.4f} | "
          f"macro-F1 {test_metrics['f1_macro']:.4f} -> {model_path.name}")

    return {"labels": labels, "target_col": target_col,
            "spec_name": best_name, "runner_up": runner_name,
            "cv_margin": float(margin), "calibrated": calibrated,
            "model_file": model_path.name,
            "n_cv_folds": folds.get_n_splits(),
            "specs": spec_records,
            "test": test_metrics,
            "confusion": E.confusion_counts(y_test, y_pred, labels),
            "mcnemar": mcnemar,
            "y_test": list(pd.Series(y_test).tolist()),
            "y_pred": list(pd.Series(y_pred).tolist())}


def run_topic_models(X_train_texts: pd.Series, y_train_topics: pd.Series,
                     X_test_texts: pd.Series, y_test_topics: pd.Series,
                     topics: list[str]) -> dict:
    """Fit LDA + NMF with K = # labelled topics; measure agreement with the
    human labels (NMI / ARI / homogeneity) on the TEST texts.

    WHY on test: the topic models never see labels at all, so scoring their
    argmax-topic against human labels on held-out texts is the fair
    unsupervised-vs-human check -- train would flatter them.
    """
    from sklearn.metrics import (adjusted_rand_score, completeness_score,
                                 homogeneity_score,
                                 normalized_mutual_info_score)
    K = len(topics)
    print(f"  [topics] LDA + NMF with K={K} (one per labelled topic)")
    out: dict = {"K": K, "topics": topics}
    configs = {
        "lda": LatentDirichletAllocation(n_components=K, max_iter=C.LDA_MAX_ITER,
                                         learning_method="batch",
                                         random_state=C.RANDOM_STATE, n_jobs=-1),
        "nmf": NMF(n_components=K, max_iter=C.NMF_MAX_ITER,
                   random_state=C.RANDOM_STATE),
    }
    for name, estimator in configs.items():
        t0 = time.time()
        pipe = Pipeline([("vec", M.build_count_vectorizer()),
                         ("model", estimator)])
        doc_topic_train = pipe.fit_transform(X_train_texts)
        doc_topic_test = pipe.transform(X_test_texts)
        pred = [f"T{i}" for i in np.asarray(doc_topic_test).argmax(axis=1)]
        vocab = pipe.named_steps["vec"].get_feature_names_out()
        comps = pipe.named_steps["model"].components_
        top_words = {f"T{i}": [str(vocab[j]) for j in comps[i].argsort()[-10:][::-1]]
                     for i in range(K)}
        agreement = {
            "nmi": float(normalized_mutual_info_score(y_test_topics, pred)),
            "ari": float(adjusted_rand_score(y_test_topics, pred)),
            "homogeneity": float(homogeneity_score(y_test_topics, pred)),
            "completeness": float(completeness_score(y_test_topics, pred)),
        }
        rec = {"top_words": top_words, "agreement": agreement,
               "contingency": contingency_matrix(
                    y_test_topics, pred,
                    labels=[*topics]).tolist() if False else None,
               "fit_seconds": round(time.time() - t0, 1)}
        # contingency: rows = true topics, cols = discovered T0..TK-1
        cont = np.zeros((len(topics), K), dtype=int)
        t_index = {t: i for i, t in enumerate(topics)}
        for true, p in zip(y_test_topics, pred):
            cont[t_index[true], int(p[1:])] += 1
        rec["contingency"] = cont.tolist()
        if name == "lda":
            rec["perplexity_test"] = float(
                pipe.named_steps["model"].perplexity(
                    pipe.named_steps["vec"].transform(X_test_texts)))
        else:
            rec["reconstruction_err_train"] = float(
                pipe.named_steps["model"].reconstruction_err_)
        joblib.dump({"kind": name, "K": K, "pipeline": pipe},
                    C.MODELS_DIR / f"topic_{name}.pkl")
        out[name] = rec
        print(f"    {name}: NMI {agreement['nmi']:.4f} | ARI {agreement['ari']:.4f} "
              f"({rec['fit_seconds']}s)")
    return out


def main() -> None:
    t_start = time.time()
    C.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    C.OUT_R2.mkdir(parents=True, exist_ok=True)
    train, test, profile, manifest = load_splits()
    topics = profile["topics"]

    tasks = {
        "sentiment": ("sentiment_label", list(C.SENTIMENT_ORDER)),
        "topic": ("topic_category", list(topics)),
    }
    task_records = {}
    for task, (col, labels) in tasks.items():
        task_records[task] = run_task(task, col, labels,
                                      train["post_text"], train[col],
                                      test["post_text"], test[col])
    unsupervised = run_topic_models(train["post_text"], train["topic_category"],
                                    test["post_text"], test["topic_category"],
                                    topics)
    record = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": C.RANDOM_STATE,
        "train_seconds": round(time.time() - t_start, 1),
        "profile": profile,
        "split": manifest,
        "tasks": task_records,
        "unsupervised": unsupervised,
    }
    (C.OUT_R2 / "train_record.json").write_text(json.dumps(_jsonable(record), indent=2))
    print(f"  train record -> output/round2/train_record.json "
          f"({record['train_seconds']}s total)")


if __name__ == "__main__":
    main()
