#!/usr/bin/env python3
"""
Data Vortex -- Round 3 :: real-time analysis layer.

Reads data/round3/live/posts.jsonl, scores every record with the shipped
Round-2 sentiment model (rulebook: "apply their NLP model developed in
Round 2"), and produces:

  output/round3/scored.csv          every record + model scores
  output/round3/figures/r3_*.png    the report's figure set
  output/round3/analysis_summary.json  every number the report quotes

Design decisions (D7+ in the report):
  * activity = hourly counts on created_at (never collected_at)
  * sentiment curves are shown for SOCIAL vs NEWS separately -- the Round-2
    model was trained on social text, so the social slice is the primary
    sentiment signal and the news slice is an honest domain-shift readout
  * spikes = hourly volume z-score >= 2.5 (min 8 records)
  * shifts = mean P(Positive) across a pre/post event boundary, Mann-Whitney U
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from round3 import config as C
from round2.predict import load_bundles, predict_texts

FIG_DIR = C.OUT_R3 / "figures"
SOCIAL = {"mastodon", "xsynd", "y_manual"}
NEWS = {"gnews", "gnews_hi", "bing", "gdelt"}
PUBLISH = {"feed_thehindu_cricket", "feed_sportstar_cricket", "feed_ht_sports",
           "feed_espncricinfo"}

ENTITIES = {
    "Harmanpreet Kaur": r"harmanpreet|हरमनप्रीत",
    "Smriti Mandhana": r"mandhana|मंडाना|मंडाना",
    "Shafali Verma": r"shafali|शफाली",
    "Jemimah Rodrigues": r"jemimah",
    "Deepti Sharma": r"deepti",
    "Richa Ghosh": r"richa ghosh",
    "Sree Charani": r"charani",
    "Renuka Singh": r"renuka",
    "Sri Lanka (final opp.)": r"sri lanka|श्रीलंका",
    "Bangladesh (SF opp.)": r"bangladesh|बांग्लादेश|बांग्ला",
    "Trophy standoff": r"trophy|naqvi|ट्रॉफी|नकवी",
    "BCCI": r"bcci",
    "Sindhu (badminton)": r"sindhu|सिंधु",
    "Kabaddi": r"kabaddi|कबड्डी",
    "Hockey": r"hockey|हॉकी",
    "Shooting": r"shooting|air rifle|निशानेबाजी|elavenil|शूटिंग",
    "Asian Games (event)": r"asian games|एशियाई खेल|एशियन गेम्स",
}

def ist_series(ts: pd.Series) -> pd.Series:
    dt = pd.to_datetime(ts, format="%Y-%m-%dT%H:%M:%SZ", utc=True, errors="coerce")
    return dt.dt.tz_convert("Asia/Kolkata")

def main() -> int:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in
            (C.LIVE_DIR / "posts.jsonl").read_text(encoding="utf-8").splitlines() if l]
    df = pd.DataFrame(rows)
    df["text_full"] = (df.get("title", pd.Series(dtype=str)).fillna("") + ". " +
                       df.get("text", pd.Series(dtype=str)).fillna("")).str.strip(". ")
    df["dt_ist"] = ist_series(df["created_at_utc"])
    df["hour_ist"] = df["dt_ist"].dt.floor("h")
    df["date_ist"] = df["dt_ist"].dt.date.astype(str)
    df["kind"] = np.where(df["source"].isin(SOCIAL), "social",
                 np.where(df["source"].isin(NEWS), "news",
                 np.where(df["source"].isin(PUBLISH), "publisher", "other")))
    df["is_hindi"] = df["text_full"].str.contains(r"[\u0900-\u097f]")

    # ---------------------------------------------------------------- scores
    scored_cache = C.OUT_R3 / "scored.csv"
    bundles = load_bundles()
    mask = df["text_full"].str.len() > 0
    scored = predict_texts(df.loc[mask, "text_full"].tolist(), bundles)
    scored = scored.drop(columns=["text"])
    scored.insert(0, "record_id", df.loc[mask, "record_id"].values)
    df = df.merge(scored, on="record_id", how="left")

    out_cols = [c for c in df.columns if not c.startswith("prob_")]
    df[out_cols + [c for c in df.columns if c.startswith("prob_")]].to_csv(
        scored_cache, index=False)

    summary = {
        "generated_at_ist": datetime.now(C.IST).strftime("%Y-%m-%d %H:%M"),
        "n_records": int(len(df)),
        "by_source": df["source"].value_counts().to_dict(),
        "by_arc": df["arc"].value_counts().to_dict(),
        "by_kind": df["kind"].value_counts().to_dict(),
        "by_scope": df["scope"].value_counts().to_dict(),
        "yt_events": (df[df["source"] == "y_manual"].groupby("event_name")
                      .size().sort_values(ascending=False).head(12).to_dict()
                      if "event_name" in df.columns else {}),
        "n_hindi": int(df["is_hindi"].sum()),
        "date_span": [str(df["date_ist"].min()), str(df["date_ist"].max())],
        "model": "models/round2/sentiment_best.pkl (Round 2 shipped winner)",
    }

    # ---------------------------------------------------------------- fig 1: volume
    fig, ax = plt.subplots(figsize=(12, 4.5))
    for kind, color in [("news", "#4878cf"), ("social", "#ee854a"),
                        ("publisher", "#797979")]:
        s = df[df["kind"] == kind].groupby("hour_ist").size()
        if len(s):
            ax.plot(s.index, s.values, label=kind, color=color, lw=1.6)
    for d, lbl in [(pd.Timestamp("2026-09-20 10:30", tz="Asia/Kolkata"), "SF start"),
                   (pd.Timestamp("2026-09-20 13:30", tz="Asia/Kolkata"), "SF won"),
                   (pd.Timestamp("2026-09-22 10:30", tz="Asia/Kolkata"), "GOLD match")]:
        if df["dt_ist"].max() >= d:
            ax.axvline(d, color="#c44e52", ls="--", lw=1)
            ax.text(d, ax.get_ylim()[1] * 0.95, lbl, fontsize=8, color="#c44e52")
    ax.set_title(f"Round 3 corpus volume by hour (n={len(df)}) — created_at, IST")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "r3_01_volume.png", dpi=140)
    plt.close(fig)

    # ---------------------------------------------------------------- spikes
    hourly = df.groupby("hour_ist").size().astype(float)
    mu, sd = hourly.mean(), hourly.std()
    spikes = hourly[(hourly - mu) / (sd or 1) >= 2.5] if sd else hourly.iloc[:0]
    summary["spikes"] = [
        {"hour_ist": str(k), "count": int(v), "z": round(float((v - mu) / sd), 2)}
        for k, v in spikes.items()]
    summary["hourly_mean"], summary["hourly_sd"] = round(float(mu), 2), round(float(sd), 2)

    # ---------------------------------------------------------------- fig 2: sentiment split
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2), sharey=True)
    for ax, kind, title in [(axes[0], "social", "SOCIAL (model's home domain)"),
                            (axes[1], "news", "NEWS (domain-shift readout)")]:
        sub = df[df["kind"] == kind]
        if not len(sub):
            continue
        g = sub.groupby("hour_ist")["prob_sentiment_Positive"].mean()
        n = sub.groupby("hour_ist")["prob_sentiment_Negative"].mean()
        ax.plot(g.index, g.values, color="#55a868", label="mean P(Positive)")
        ax.plot(n.index, n.values, color="#c44e52", label="mean P(Negative)")
        ax.set_title(f"{title} — {len(sub)} records")
        ax.legend(fontsize=8)
        ax.set_ylim(0, 1)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "r3_02_sentiment_split.png", dpi=140)
    plt.close(fig)

    # ---------------------------------------------------------------- shift tests
    shifts = []
    def shift_test(label, sub, t0, t1, t2, t3):
        """mean P(Positive) in [t0,t1) vs [t2,t3), Mann-Whitney U."""
        a = sub[(sub["dt_ist"] >= t0) & (sub["dt_ist"] < t1)]["prob_sentiment_Positive"]
        b = sub[(sub["dt_ist"] >= t2) & (sub["dt_ist"] < t3)]["prob_sentiment_Positive"]
        if len(a) >= 5 and len(b) >= 5:
            u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            shifts.append({"contrast": label, "n_pre": int(len(a)), "n_post": int(len(b)),
                           "mean_pre": round(float(a.mean()), 3),
                           "mean_post": round(float(b.mean()), 3),
                           "delta": round(float(b.mean() - a.mean()), 3),
                           "mannwhitney_p": round(float(p), 4)})
    social = df[df["kind"] == "social"]
    if len(social):
        d0 = pd.Timestamp("2026-09-20", tz="Asia/Kolkata")
        shift_test("SHIFT #1 - SF day: pre-match (00-10:30) vs post-result (13:30-23:59)",
                   social, d0, d0 + pd.Timedelta("10.5h"),
                   d0 + pd.Timedelta("13.5h"), d0 + pd.Timedelta("23.9h"))
        d2 = pd.Timestamp("2026-09-22", tz="Asia/Kolkata")
        shift_test("SHIFT #2 - GOLD day: pre-match (00-10:30) vs post-result (13:30-20:30)",
                   social, d2, d2 + pd.Timedelta("10.5h"),
                   d2 + pd.Timedelta("13.5h"), d2 + pd.Timedelta("20.5h"))
        shift_test("SHIFT #2b - GOLD day: pre vs post, SOCIAL+X-manual only",
                   social, d2, d2 + pd.Timedelta("10.5h"),
                   d2 + pd.Timedelta("13.5h"), d2 + pd.Timedelta("20.5h"))
    summary["shift_tests"] = shifts

    # ---------------------------------------------------------------- entities
    ent_counts, ent_by_day = {}, {}
    low = (df["title"].fillna("") + " " + df["text"].fillna("")).str.lower()
    for name, pat in ENTITIES.items():
        hit = low.str.contains(pat, regex=True, na=False)
        ent_counts[name] = int(hit.sum())
        ent_by_day[name] = df[hit].groupby("date_ist").size().to_dict()
    summary["entity_counts"] = dict(sorted(ent_counts.items(),
                                           key=lambda kv: -kv[1]))

    fig, ax = plt.subplots(figsize=(9, 6))
    top = dict(list(summary["entity_counts"].items())[:15])
    ax.barh(list(top.keys())[::-1], list(top.values())[::-1], color="#4878cf")
    ax.set_title("Entity mentions across the corpus (title+text, EN+HI patterns)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "r3_03_entities.png", dpi=140)
    plt.close(fig)

    # ---------------------------------------------------------------- fig 4: daily mix
    fig, ax = plt.subplots(figsize=(9, 4))
    daily = df.groupby(["date_ist", "arc"]).size().unstack(fill_value=0)
    daily.plot(kind="bar", stacked=True, ax=ax,
               color={"retro": "#797979", "live": "#4878cf"})
    ax.set_title("Records per day (IST) — retro arc vs live window")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "r3_04_daily_mix.png", dpi=140)
    plt.close(fig)

    (C.OUT_R3 / "analysis_summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False)[:2000])
    print(f"\nfigures -> {FIG_DIR}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
