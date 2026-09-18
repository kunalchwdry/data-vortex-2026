"""
Data Vortex -- Round 2: Dataset 2 intake, audit and stratified split.

Mirrors the Round 1 Phase-1 contract: the raw file is never modified, every
excluded row is written to a named hold-out file, and the row arithmetic
closes exactly (raw = modeled + empty-held-out + duplicate-held-out).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from round2 import config as C
from round2 import text_clean as tc


# ---------------------------------------------------------------------------
# Load + validate
# ---------------------------------------------------------------------------
def load_raw(path: Path = C.RAW_DATASET2) -> pd.DataFrame:
    """Read Dataset 2 as pure strings and validate the schema.

    WHY ``dtype=str, keep_default_na=False``: post text legitimately contains
    tokens like "None" or "NA" (band names, abbreviations) that pandas would
    otherwise silently convert to NaN.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset 2 not found at {path}. Place the Round 2 CSV there "
            f"(columns: {', '.join(C.EXPECTED_COLUMNS)}).")
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(df.columns) != C.EXPECTED_COLUMNS:
        raise ValueError(f"Expected columns {C.EXPECTED_COLUMNS}, got {list(df.columns)}")
    for col in C.EXPECTED_COLUMNS:
        df[col] = df[col].map(lambda v: str(v).strip())
    return df


def audit_and_clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Validate ids/labels, hold out empties + exact duplicates, profile.

    Returns (modeled, empty_heldout, dupe_heldout, profile). ``modeled`` keeps
    the original row order (no shuffle here -- the split shuffles with a seed).
    """
    n_raw = len(df)

    # -- ids unique & non-empty -------------------------------------------
    if (df["text_id"] == "").any():
        raise ValueError("blank text_id found in Dataset 2")
    dup_ids = df["text_id"].duplicated(keep=False)
    if dup_ids.any():
        bad = sorted(df.loc[dup_ids, "text_id"].unique())[:10]
        raise ValueError(f"duplicate text_id values in Dataset 2, e.g. {bad}")

    # -- sentiment labels must be exactly the 3 known classes ---------------
    bad_sent = sorted(set(df["sentiment_label"]) - set(C.SENTIMENT_ORDER))
    if bad_sent:
        raise ValueError(f"unexpected sentiment_label values: {bad_sent}")
    topics = sorted(df["topic_category"].unique().tolist())
    if "" in topics:
        raise ValueError("blank topic_category found in Dataset 2")

    # -- empty-text hold-out (Round 1 precedent: held out, never deleted) ----
    df = df.copy()
    df["_clean"] = df["post_text"].map(tc.base_clean)
    empty_mask = df["_clean"] == ""
    empty_heldout = df.loc[empty_mask, C.EXPECTED_COLUMNS]
    modeled = df.loc[~empty_mask].copy()

    # -- exact-duplicate hold-out (leakage control, see config D4) -----------
    dupe_heldout = modeled.iloc[0:0][C.EXPECTED_COLUMNS]
    if C.HOLD_OUT_EXACT_DUPLICATES:
        dupe_mask = modeled.duplicated(subset=["post_text", "sentiment_label",
                                               "topic_category"], keep="first")
        dupe_heldout = modeled.loc[dupe_mask, C.EXPECTED_COLUMNS]
        modeled = modeled.loc[~dupe_mask].copy()

    # -- same text, conflicting labels: kept, but counted as label noise -----
    text_groups = modeled.groupby("post_text", sort=False)
    conflict_texts = sum(1 for _, g in text_groups
                         if g["sentiment_label"].nunique() > 1
                         or g["topic_category"].nunique() > 1)

    # -- profile ------------------------------------------------------------
    lengths = modeled["_clean"].str.len()
    profile = {
        "n_raw": int(n_raw),
        "n_empty_heldout": int(len(empty_heldout)),
        "n_dupe_heldout": int(len(dupe_heldout)),
        "n_modeled": int(len(modeled)),
        "n_conflicting_texts": int(conflict_texts),
        "sentiment_counts": {k: int((modeled["sentiment_label"] == k).sum())
                             for k in C.SENTIMENT_ORDER},
        "topic_counts": {t: int((modeled["topic_category"] == t).sum()) for t in topics},
        "topics": topics,
        "length_chars": {
            "min": int(lengths.min()), "p50": float(lengths.median()),
            "mean": round(float(lengths.mean()), 1), "max": int(lengths.max()),
        },
        "reconciliation": (f"{n_raw} raw - {len(empty_heldout)} empty - "
                           f"{len(dupe_heldout)} exact-duplicate = {len(modeled)} modeled"),
    }
    assert profile["n_raw"] == (profile["n_modeled"] + profile["n_empty_heldout"]
                                + profile["n_dupe_heldout"]), "row arithmetic must close"
    modeled = modeled[C.EXPECTED_COLUMNS].reset_index(drop=True)
    return modeled, empty_heldout, dupe_heldout, profile


# ---------------------------------------------------------------------------
# Stratified split (one shared split for both tasks -- config D5)
# ---------------------------------------------------------------------------
def stratified_split(df: pd.DataFrame, test_size: float = C.TEST_SIZE,
                     seed: int = C.RANDOM_STATE) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """80/20 split stratified by sentiment x topic, with a safe back-off.

    WHY the back-off: sklearn refuses to stratify when any stratum has < 2
    members. Rather than crash (or silently drop strata), we fall back to
    sentiment-only stratification and record which path was taken.
    """
    combo = df["sentiment_label"] + "||" + df["topic_category"]
    if C.STRATIFY_BY == "sentiment_x_topic" and int(combo.value_counts().min()) >= 2:
        strat, strat_name = combo, "sentiment_x_topic"
    else:
        strat, strat_name = df["sentiment_label"], "sentiment_only"
    train, test = train_test_split(df, test_size=test_size, random_state=seed,
                                   shuffle=True, stratify=strat)
    train, test = train.reset_index(drop=True), test.reset_index(drop=True)
    manifest = {
        "seed": seed, "test_size": test_size, "stratify": strat_name,
        "n_train": int(len(train)), "n_test": int(len(test)),
        "train_sentiment": train["sentiment_label"].value_counts().to_dict(),
        "test_sentiment": test["sentiment_label"].value_counts().to_dict(),
        "train_topic": train["topic_category"].value_counts().to_dict(),
        "test_topic": test["topic_category"].value_counts().to_dict(),
        "id_overlap": int(len(set(train["text_id"]) & set(test["text_id"]))),
    }
    assert manifest["id_overlap"] == 0, "train/test id leakage"
    return train, test, manifest


def cleaning_report_md(profile: dict, manifest: dict) -> str:
    """Human-readable audit note. All numbers passed in -- nothing hardcoded."""
    line = ["# Dataset 2 -- cleaning + split report", "",
            f"Source: `data/round2/raw/Dataset2.csv` (never modified)", "",
            "## Row reconciliation", "",
            f"`{profile['reconciliation']}`", "",
            f"Same-text conflicting labels kept as label noise: "
            f"**{profile['n_conflicting_texts']}** distinct texts", "",
            "## Label distribution (modeled rows)", "",
            "| sentiment | n |", "|---|---|"] + \
           [f"| {k} | {v} |" for k, v in profile["sentiment_counts"].items()] + \
           ["", "| topic | n |", "|---|---|"] + \
           [f"| {k} | {v} |" for k, v in profile["topic_counts"].items()] + \
           ["", "## Text length (chars, cleaned)", "",
            f"min {profile['length_chars']['min']} · median "
            f"{profile['length_chars']['p50']:.0f} · mean "
            f"{profile['length_chars']['mean']} · max {profile['length_chars']['max']}", "",
            "## Split", "",
            f"seed {manifest['seed']} · test {manifest['test_size']} · "
            f"stratify `{manifest['stratify']}` · "
            f"train {manifest['n_train']} / test {manifest['n_test']} · "
            f"id overlap {manifest['id_overlap']}", ""]
    return "\n".join(line)


def main() -> None:
    C.DATA_R2_CLEAN.mkdir(parents=True, exist_ok=True)
    raw = load_raw()
    modeled, empty_heldout, dupe_heldout, profile = audit_and_clean(raw)
    train, test, manifest = stratified_split(modeled)
    train.to_csv(C.TRAIN_CSV, index=False)
    test.to_csv(C.TEST_CSV, index=False)
    empty_heldout.to_csv(C.EMPTY_HELDOUT_CSV, index=False)
    dupe_heldout.to_csv(C.DUPE_HELDOUT_CSV, index=False)
    C.PROFILE_JSON.write_text(json.dumps(profile, indent=2))
    C.SPLIT_MANIFEST_JSON.write_text(json.dumps(manifest, indent=2))
    C.CLEANING_REPORT_MD.write_text(cleaning_report_md(profile, manifest))
    print(f"  intake: {profile['reconciliation']}")
    print(f"  split:  train {manifest['n_train']} / test {manifest['n_test']} "
          f"({manifest['stratify']})")


def load_splits() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    """Load train/test + profile + manifest (fails loudly if intake not run)."""
    for path in (C.TRAIN_CSV, C.TEST_CSV, C.PROFILE_JSON, C.SPLIT_MANIFEST_JSON):
        if not path.exists():
            raise FileNotFoundError(f"missing {path} -- run data.py (intake) first")
    train = pd.read_csv(C.TRAIN_CSV, dtype=str, keep_default_na=False)
    test = pd.read_csv(C.TEST_CSV, dtype=str, keep_default_na=False)
    profile = json.loads(C.PROFILE_JSON.read_text())
    manifest = json.loads(C.SPLIT_MANIFEST_JSON.read_text())
    return train, test, profile, manifest


if __name__ == "__main__":
    main()
