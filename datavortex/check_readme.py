"""
Verify README.md against the artefacts it describes.

Checks, in order:
  1. every local link/image path resolves
  2. every (#anchor) matches a heading slug
  3. markdown tables are rectangular (counting only UNESCAPED pipes, since
     `\\|` is legal inside a cell)
  4. every numeric claim in the README is recomputed from data/clean +
     output/*.json and compared -- so the doc cannot drift from the data
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

R = pathlib.Path(__file__).resolve().parent
S = (R / "README.md").read_text()
fails: list[str] = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{(' :: ' + detail) if detail and not ok else ''}")
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------- 1. paths
refs = [r for r in re.findall(r'\[[^\]]*\]\(([^)]+)\)', S) + re.findall(r'<img src="([^"]+)"', S)
        if not r.startswith(("http", "#"))]
broken = [r for r in refs if not (R / r).exists()]
check(f"local links/images resolve ({len(refs)} refs)", not broken, ", ".join(broken))

# ---------------------------------------------------------------- 2. anchors
slugs = [h.lower().replace(" ", "-") for h in re.findall(r"^## (.+)$", S, re.M)]
anchor_links = re.findall(r"\]\(#[^)]+\)", S)
bad_anchors = [a for a in re.findall(r"\]\(#([^)]+)\)", S) if a not in slugs]
check(f"TOC/inline anchors resolve ({len(anchor_links)} links)",
      not bad_anchors, ", ".join(bad_anchors))

# ---------------------------------------------------------------- 3. tables
def pipes(line):  # unescaped | only
    return len(re.findall(r"(?<!\\)\|", line))


lines = S.split("\n")
i = ragged = ntab = 0
while i < len(lines):
    if lines[i].strip().startswith("|"):
        blk = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            blk.append(lines[i])
            i += 1
        ntab += 1
        counts = [pipes(l) for l in blk if not re.match(r"^\s*\|[\s:\-|\\]+\|\s*$", l)]
        if len(set(counts)) > 1:
            ragged += 1
            print(f"        ragged: {blk[0][:60]} -> {set(counts)}")
    else:
        i += 1
check(f"markdown tables rectangular ({ntab} tables)", ragged == 0, f"{ragged} ragged")

# ---------------------------------------------------------------- 4. numbers
summ = json.loads((R / "data/clean/cleaning_summary.json").read_text())
fx = summ["facts"]
eda = json.loads((R / "output/eda_stats.json").read_text())
sql = {q["id"]: q for q in json.loads((R / "output/sql_results.json").read_text())}
raw = None
import csv as _csv
with open(R / "data/raw/Social_Engine_Posts_Corrupted.csv", newline="") as fh:
    raw = list(_csv.DictReader(fh))


def col(q, c):
    return [r[sql[q]["columns"].index(c)] for r in sql[q]["rows"]]


pos = [x for x in raw if x["likes"] not in ("", "NULL") and float(x["likes"]) > 0]
neg = [x for x in raw if x["likes"] not in ("", "NULL") and float(x["likes"]) < 0]
nullish = [x for x in raw if x["likes"].strip() in ("", "NULL")]
dmy = [x["timestamp"].strip() for x in raw if re.fullmatch(r"\d{2}-\d{2}-\d{4}", x["timestamp"].strip())]
gt12a = sum(1 for x in dmy if int(x[:2]) > 12)
gt12b = sum(1 for x in dmy if int(x[3:5]) > 12)
posts12 = col("Q1", "posts")
mu = sum(posts12) / len(posts12)
sd = (sum((x - mu) ** 2 for x in posts12) / len(posts12)) ** 0.5
zs = [z for z in col("Q1", "z_volume") if z is not None]
q5 = sql["Q5"]["rows"][0]
q5c = sql["Q5"]["columns"]
reps = len((R / "data/clean/repair_log.csv").read_text().strip().split("\n")) - 1

claims = {
    "12,360 raw rows":               (fx["raw_rows"], 12360),
    "10,221 analysis rows":          (fx["analysis_rows"], 10221),
    "360 exact duplicates":          (fx["raw_dup_rows"], 360),
    "1,779 empty-text hold-outs":    (summ["held_out_rows"], 1779),
    "27 logged repairs":             (reps, 27),
    "525 negative likes":            (len(neg), 525),
    "9,976 positive likes":          (len(pos), 9976),
    "1,858 blank/NULL likes (raw)":  (len(nullish), 1858),
    "430 sign-repairs survive":      (fx["analysis_sign_restored"], 430),
    "2,172 first field > 12":        (gt12a, 2172),
    "0 second field > 12":           (gt12b, 0),
    "3,622 dd-mm-yyyy raw rows":     (len(dmy), 3622),
    "1,450 ambiguous dates":         (fx["dayfirst_ambiguous"], 1450),
    "316 double-encoded rows":       (fx["mojibake_rows_raw"], 316),
    "663 injected tags":             (fx["tags_raw"], 663),
    "341 trailing entities":         (fx["entities_raw"], 341),
    "1,532 NULL likes (analysis)":   (fx["analysis_likes_missing"], 1532),
    "3,325 naive midnight":          (eda["time"]["artefact_midnight_naive_rows"], 3325),
    "3,002 artefact rows":          (eda["time"]["artefact_midnight_from_dateonly_format"], 3002),
    "32.53% naive peak":             (eda["time"]["artefact_midnight_naive_pct"], 32.53),
    "4.63% valid peak":              (eda["time"]["peak_hour_pct"], 4.63),
    "3.80% valid trough":            (eda["time"]["trough_hour_pct"], 3.8),
    "1.22 spread ratio":             (round(eda["time"]["hour_spread_ratio"], 2), 1.22),
    "3.8% platform spread":          (eda["platform"]["spread_mean_likes_pct"], 3.8),
    "15.08% Unspecified":            (eda["platform"]["unspecified_share_pct"], 15.08),
    "r = -0.0433 followers":         (eda["users"]["corr_followers_engagement"], -0.0433),
    "18.4% top-decile share":        (eda["users"]["gini_like_check_top10_share_pct"], 18.4),
    "sentiment r = -0.0142":         (eda["sentiment"]["corr_sentiment_likes"], -0.0142),
    "neg likes 2,509.8":             (eda["sentiment"]["mean_likes_by_sentiment"]["negative"], 2509.8),
    "pos likes 2,454.8":             (eda["sentiment"]["mean_likes_by_sentiment"]["positive"], 2454.8),
    "40.95/31.91/27.14 split":       ((eda["sentiment"]["pct"]["positive"],
                                       eda["sentiment"]["pct"]["neutral"],
                                       eda["sentiment"]["pct"]["negative"]), (40.95, 31.91, 27.14)),
    "Q4 846 anomalies":              (sql["Q4"]["rows"][0][0], 846),
    "Q5 obs 31":                     (q5[q5c.index("obs_ge3")], 31),
    "Q5 expected 29.6":              (q5[q5c.index("expected_ge3_by_chance")], 29.6),
    "Q5 O/E 1.05":                   (round(q5[q5c.index("observed_over_expected")], 2), 1.05),
    "Q5 lambda 0.564":               (q5[q5c.index("poisson_lambda")], 0.564),
    "Q12 all zeros":                 ([r[1] for r in sql["Q12"]["rows"]], [0] * 5),
    "12 queries":                    (len(sql), 12),
    "Q1 mean 852":                   (round(mu), 852),
    "Q1 sd 24.5":                    (round(sd, 1), 24.5),
    "Q1 z min -2.36":                (round(min(zs), 2), -2.36),
    "Q1 z max +1.07":                (round(max(zs), 2), 1.07),
    "Q1 3 of 12 beyond 1 SD":        (sum(1 for z in zs if abs(z) >= 1), 3),
}
print()
for k, (actual, claimed) in claims.items():
    check(f"{k:32} = {claimed}", actual == claimed, f"actual {actual}")

# the claim must also literally appear in the README
print()
sys.path.insert(0, str(R / "src"))
from config import TEAM_MEMBERS, TEAM_NAME  # noqa: E402
for needle in [TEAM_NAME, *TEAM_MEMBERS, "12,360", "10,221", "1,779", "2,172", "4.63%", "32.53%", "-0.0433",
               "1.05", "24.5", "18.4%", "3.8%", "15.08%"]:
    check(f"README mentions {needle}", needle in S)

print("\n" + ("README VERIFIED - all claims match the artefacts"
              if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
