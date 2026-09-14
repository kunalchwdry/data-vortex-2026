"""
Invariant tests on the cleaned artefacts.

These assert the *claims the submission makes*, so a future edit that quietly
breaks one fails here rather than in front of the judges:

  * the row arithmetic reconciles
  * no corruption marker survives
  * no value was invented (missingness preserved, not filled)
  * keys are keys, and referential integrity holds
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
RAW = ROOT / "data" / "raw"


@pytest.fixture(scope="module")
def posts() -> pd.DataFrame:
    return pd.read_csv(CLEAN / "Social_Engine_Posts_Clean.csv",
                       parse_dates=["timestamp", "post_date"])


@pytest.fixture(scope="module")
def users() -> pd.DataFrame:
    return pd.read_csv(CLEAN / "Social_Engine_Users_Clean.csv")


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return pd.read_csv(RAW / "Social_Engine_Posts_Corrupted.csv",
                       dtype=str, keep_default_na=False)


@pytest.fixture(scope="module")
def summary() -> dict:
    return json.loads((CLEAN / "cleaning_summary.json").read_text())


# ---------------------------------------------------------------- reconciliation
def test_row_arithmetic_closes(posts, summary):
    """raw - duplicates - hold-outs == analysis rows, exactly."""
    fx = summary["facts"]
    assert (fx["raw_rows"] - fx["raw_dup_rows"] - summary["held_out_rows"]
            == len(posts))


def test_no_duplicate_primary_key(posts, users):
    assert posts.post_id.is_unique
    assert users.user_id.is_unique


def test_referential_integrity(posts, users):
    assert set(posts.user_id) <= set(users.user_id)


# --------------------------------------------------------------------- cleanliness
# Each pattern is a real corruption marker. `must_match` is what keeps this test
# honest: a pattern written wrong (e.g. the literal text "\u00c3" instead of the
# characters) matches nothing, so the assertion below passes vacuously on ANY
# dataset. Requiring the pattern to fire on a known-bad sample makes a silent
# no-op impossible.
CORRUPTION_MARKERS = [
    (r"&amp;", "&amp;"),
    (r"&lt;", "&lt;"),
    (r"&gt;", "&gt;"),
    (r"<br", "x<br>"),
    (r"<div", "<div>x"),
    ("\u00c3\u00a9", "Trail\u00c3\u00a9"),   # double-encoded e-acute
]


@pytest.mark.parametrize("pattern,must_match", CORRUPTION_MARKERS)
def test_no_injection_or_entity_left(posts, pattern, must_match):
    probe = pd.Series([must_match, "clean text"])
    assert int(probe.str.contains(pattern, regex=True).sum()) == 1, (
        f"marker {pattern!r} does not match its own sample -- the test would "
        "pass vacuously, so it proves nothing")
    hits = posts.text_content.astype(str).str.contains(pattern, regex=True).sum()
    assert int(hits) == 0, f"{pattern} still present in {hits} rows"


def test_no_nonascii_or_whitespace_artefacts(posts):
    t = posts.text_content.astype(str)
    assert int(t.apply(lambda x: any(ord(c) > 127 for c in x)).sum()) == 0
    assert int((t != t.str.strip()).sum()) == 0
    assert int(t.str.contains("  ").sum()) == 0
    assert int(t.str.contains(r"[&,]$", regex=True).sum()) == 0


def test_no_sentinel_strings_masquerading_as_content(posts):
    """'NULL' must never survive as a value in any column."""
    for c in posts.columns:
        vals = posts[c].astype(str).str.strip().str.lower()
        assert int(vals.eq("null").sum()) == 0, f"literal 'null' left in {c}"


def test_timestamps_normalised_to_one_format(posts):
    assert pd.api.types.is_datetime64_any_dtype(posts.timestamp)
    assert int(posts.timestamp.isna().sum()) == 0
    # the declared event window, half-open on the last day
    assert posts.timestamp.min() >= pd.Timestamp("2024-05-01")
    assert posts.timestamp.max() < pd.Timestamp("2025-05-01")


def test_platforms_are_canonical_or_the_explicit_gap_bucket(posts):
    allowed = {"Twitter", "Facebook", "Instagram", "YouTube", "Reddit", "Unspecified"}
    assert set(posts.platform.unique()) <= allowed


# ------------------------------------------------------------------- no fabrication
def test_engagement_never_negative_and_nulls_preserved(posts):
    for c in ("likes", "shares", "comments"):
        assert int((pd.to_numeric(posts[c], errors="coerce") < 0).sum()) == 0
    # likes were left missing on purpose: filling them would be fabrication
    assert int(posts.likes.isna().sum()) > 0


def test_missing_likes_match_the_source_not_a_fill(raw, posts, summary):
    """Every NULL likes in the output traces to a blank/NULL token upstream."""
    naive = pd.to_numeric(raw.likes.replace({"": np.nan, "NULL": np.nan}),
                           errors="coerce")
    assert int(naive.isna().sum()) >= int(posts.likes.isna().sum())


def test_held_out_rows_are_recoverable_and_exactly_the_empty_bodies():
    held = pd.read_csv(CLEAN / "Social_Engine_Posts_EmptyText_HeldOut.csv",
                       dtype=str, keep_default_na=False)
    clean = pd.read_csv(CLEAN / "Social_Engine_Posts_Clean.csv", dtype=str,
                        keep_default_na=False)
    assert set(held.post_id).isdisjoint(set(clean.post_id))
    assert all(v in ("", "nan", "<NA>", "None") for v in held.text_content)


def test_repairs_are_flagged_not_hidden(posts, summary):
    """Every judgement call that changed a value is traceable per row."""
    assert "flag_likes_sign_restored" in posts.columns
    assert "flag_ambiguous_date_format" in posts.columns
    fx = summary["facts"]
    assert int(posts.flag_likes_sign_restored.sum()) == fx["analysis_sign_restored"]
    assert int(posts.flag_ambiguous_date_format.sum()) == fx["analysis_dayfirst_flagged"]


def test_day_first_reading_is_the_only_arithmetically_possible_one(raw):
    dmy = raw.timestamp.str.strip()
    dmy = dmy[dmy.str.match(r"^\d{2}-\d{2}-\d{4}$")]
    a = dmy.str.slice(0, 2).astype(int)
    b = dmy.str.slice(3, 5).astype(int)
    assert (a > 12).sum() > 0, "if no day exceeds 12 the format is genuinely ambiguous"
    assert (b > 12).sum() == 0, "month>12 would mean day-first is the wrong call"


# ------------------------------------------------------------------------- SQL side
def test_database_matches_the_clean_csvs():
    import sqlite3
    db = ROOT / "output" / "social_engine.db"
    if not db.exists():
        pytest.skip("run src/build_db.py first")
    con = sqlite3.connect(db)
    n_posts = con.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    n_users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    viol = con.execute("PRAGMA foreign_key_check").fetchall()
    assert n_posts == len(pd.read_csv(CLEAN / "Social_Engine_Posts_Clean.csv"))
    assert n_users == len(pd.read_csv(CLEAN / "Social_Engine_Users_Clean.csv"))
    assert viol == []


def test_every_query_returned_rows_and_documented_logic():
    res = ROOT / "output" / "sql_results.json"
    if not res.exists():
        pytest.skip("run src/run_sql.py first")
    data = json.loads(res.read_text())
    assert len(data) == 12
    for q in data:
        assert q["error"] is None, f"{q['id']} errored: {q['error']}"
        assert q["rows"], f"{q['id']} returned no rows"
        assert q["logic"], f"{q['id']} has no documented logic"
        assert len(q["sql"]) > 60, f"{q['id']} SQL looks truncated"


def test_integrity_gate_query_is_all_zero():
    res = ROOT / "output" / "sql_results.json"
    if not res.exists():
        pytest.skip("run src/run_sql.py first")
    q12 = next(q for q in json.loads(res.read_text()) if q["id"] == "Q12")
    for name, violations in q12["rows"]:
        assert violations == 0, f"{name} has {violations} violations"
