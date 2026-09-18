"""
Round 2 invariant tests.

Unit tests (preprocessing) always run. Integration tests verify the trained
artefacts and skip with a clear message when the Round 2 intake has not been
run yet (Dataset 2 lives behind the Round 2 links, not in git history).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from round2 import config as C
from round2 import text_clean as tc


def _needs_intake():
    if not C.TRAIN_CSV.exists() or not C.METRICS_JSON.exists():
        pytest.skip("Round 2 pipeline not run yet (./run_round2.sh)")


# ---------------------------------------------------------------------------
# Preprocessing units (no data needed)
# ---------------------------------------------------------------------------
def test_decode_unicode_escapes():
    assert tc.decode_unicode_escapes("it\\u2019s, ok\\u0021") == "it’s, ok!"
    assert tc.decode_unicode_escapes("plain \\ backslash") == "plain \\ backslash"
    assert tc.decode_unicode_escapes("\\uZZZZ stays") == "\\uZZZZ stays"


def test_normalize_masks_social_tokens():
    out = tc.normalize_text("Hey @User, see https://x.co/a and #StayHome!")
    assert "<user>" in out and "<url>" in out and "<hashtag>" in out
    assert "stayhome" in out and "@user" not in out and "https" not in out


def test_normalize_affect_and_elongation():
    out = tc.normalize_text("sooo happyyy :) :(")
    assert "<smile>" in out and "<sad>" in out and "<elong>" in out
    assert "sooo" not in out  # collapsed to "soo"


def test_negation_scope_prefixes_content_words():
    toks = tc.word_tokens("I do not love this boring update")
    assert "not" in toks and "NOT_love" in toks
    assert "love" not in toks  # bare form must not leak a positive vote


def test_negations_survive_stopwords_but_markers_untouched():
    toks = tc.word_tokens("this is not good :)")
    assert "not" in toks and "<smile>" in toks
    assert not any(t.startswith("NOT_<") for t in toks)


def test_empty_and_none_yield_empty_token():
    assert tc.word_tokens("") == ["<empty>"]
    assert tc.word_tokens(None) == ["<empty>"]
    assert tc.word_tokens("the a an") == ["<empty>"]  # all stopwords


def test_preprocessing_deterministic():
    sample = "Can't wait!!! @team https://t.co/x #GoGo :D loooong"
    assert tc.word_tokens(sample) == tc.word_tokens(sample)
    assert tc.normalize_text(sample) == tc.normalize_text(sample)
    assert tc.attributes_for_analysis(sample) == tc.attributes_for_analysis(sample)


def test_analyzers_agree_on_unigrams():
    uni = tc.word_token_analyzer_uni("quick brown fox")
    full = tc.word_token_analyzer("quick brown fox")
    assert uni == ["quick", "brown", "fox"]
    assert full[:3] == uni and "quick brown" in full  # bigrams appended


# ---------------------------------------------------------------------------
# Intake + split invariants
# ---------------------------------------------------------------------------
def test_row_arithmetic_closes():
    _needs_intake()
    import pandas as pd
    profile = json.loads(C.PROFILE_JSON.read_text())
    n_held = sum(1 for _ in open(C.EMPTY_HELDOUT_CSV)) - 1
    n_dup = sum(1 for _ in open(C.DUPE_HELDOUT_CSV)) - 1
    n_tr = sum(1 for _ in open(C.TRAIN_CSV)) - 1
    n_te = sum(1 for _ in open(C.TEST_CSV)) - 1
    assert profile["n_raw"] == profile["n_modeled"] + n_held + n_dup == n_tr + n_te + n_held + n_dup
    assert profile["n_raw"] > 1000  # Dataset 2 scale sanity


def test_split_disjoint_and_stratified():
    _needs_intake()
    import pandas as pd
    train = pd.read_csv(C.TRAIN_CSV, dtype=str, keep_default_na=False)
    test = pd.read_csv(C.TEST_CSV, dtype=str, keep_default_na=False)
    assert len(set(train["text_id"]) & set(test["text_id"])) == 0
    assert abs(len(test) / (len(train) + len(test)) - C.TEST_SIZE) < 0.01
    for col in ("sentiment_label", "topic_category"):
        for val in train[col].unique():
            diff = abs((train[col] == val).mean() - (test[col] == val).mean())
            assert diff < 0.05, f"{col}={val} drifted {diff:.3f} across split"


# ---------------------------------------------------------------------------
# Metrics + model artefacts
# ---------------------------------------------------------------------------
def test_metrics_schema_and_ranges():
    _needs_intake()
    metrics = json.loads(C.METRICS_JSON.read_text())
    assert metrics["seed"] == C.RANDOM_STATE
    for task in ("sentiment", "topic"):
        rec = metrics["tasks"][task]
        t = rec["test_recomputed"]
        assert 0.0 <= t["accuracy"] <= 1.0 and 0.0 <= t["f1_macro"] <= 1.0
        assert len(rec["confusion"]) == len(rec["labels"])
        assert all(len(row) == len(rec["labels"]) for row in rec["confusion"])
        assert sum(sum(row) for row in rec["confusion"]) == t["n"]
        assert rec["spec_name"] in rec["specs"]
        assert 0.0 <= rec["mcnemar"]["p_value"] <= 1.0
        assert rec["slices"]["overall"]["n"] == t["n"]
    for algo in ("lda", "nmf"):
        a = metrics["unsupervised"][algo]["agreement"]
        assert 0.0 <= a["nmi"] <= 1.0 and -1.0 <= a["ari"] <= 1.0


def test_winner_beats_dummy_on_cv():
    _needs_intake()
    metrics = json.loads(C.METRICS_JSON.read_text())
    for task in ("sentiment", "topic"):
        specs = metrics["tasks"][task]["specs"]
        best = max(specs.values(), key=lambda s: s["cv_mean"])["cv_mean"]
        assert best > specs["dummy"]["cv_mean"] + 0.05  # must clear chance by 5pp


def test_models_load_predict_deterministically():
    _needs_intake()
    import joblib
    texts = ["I love this!", "Terrible crash, furious.", "See you Sunday."]
    for task in ("sentiment", "topic"):
        bundle = joblib.load(C.MODELS_DIR / f"{task}_best.pkl")
        first = list(bundle["pipeline"].predict(texts))
        second = list(bundle["pipeline"].predict(texts))
        assert first == second
        assert set(first) <= set(bundle["labels"])
        if hasattr(bundle["pipeline"], "predict_proba"):
            proba = bundle["pipeline"].predict_proba(texts)
            assert abs(proba.sum(axis=1) - 1.0).max() < 1e-6


def test_reports_and_figures_exist():
    _needs_intake()
    assert C.EVAL_REPORT_PDF.exists() and C.EVAL_REPORT_PDF.stat().st_size > 50_000
    assert C.TECH_REPORT_PDF.exists() and C.TECH_REPORT_PDF.stat().st_size > 50_000
    figs = list(C.FIG_R2.glob("r2_*.png"))
    assert len(figs) >= 15, f"only {len(figs)} figures"
    assert all(f.stat().st_size > 3_000 for f in figs)
    assert C.NOTEBOOK_PATH.exists()
    nb = json.loads(C.NOTEBOOK_PATH.read_text())
    n_out = sum(len(c.get("outputs", [])) for c in nb["cells"] if c["cell_type"] == "code")
    assert n_out > 5, "notebook has no executed outputs"
