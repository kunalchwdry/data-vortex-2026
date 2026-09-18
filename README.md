<div align="center">

#  Data Vortex — Round 1

### Rebuilding the Social Engine · Data Intake Restoration & Analytical Core

**Forge-X** · Kunal Choudhary

*Aaruush'26* · 13–16 September 2026 · Round 1 · Phase 1 + Phase 2

`12,360 raw rows → 10,221 analysis rows` · `27 justified repairs` · `45 SQL queries` · `42 tests passing`

</div>

---

| | |
|---|---|
| **Team** | **Forge-X** |
| **Member** | Kunal Choudhary |
| **Phase 1** | cleaned dataset + EDA report + this repo |
| **Phase 2** | `queries/challenges.sql` + `output/Phase2_Insight_Report.pdf` |
| **Phase 2 challenge set** | `queries/phase2_challenges.sql` + `output/Phase2_ChallengeSet_Report.pdf` |
| **Phase 2 form upload set** | [`submission/phase2/`](submission/phase2/MANIFEST.md) — 4 slots, 8 files, labelled E1–H6 |

> **Every number in this README is generated.** The tables and figures below are
> produced by `./run_all.sh` from the two recovered CSVs — nothing is typed by
> hand, because the rulebook disqualifies hardcoded outputs and prohibits
> fabricated data. Re-run it and you land on identical numbers.

---

## Contents

1. [The result in 30 seconds](#the-result-in-30-seconds)
2. [Reproduce it](#reproduce-it)
3. [How the dataset was recovered](#how-the-dataset-was-recovered)
4. [Corruption inventory and repairs](#corruption-inventory-and-repairs)
5. [The two decisions that needed proof](#the-two-decisions-that-needed-proof)
6. [Exploratory analysis](#exploratory-analysis)
7. [The SQL analytical core](#the-sql-analytical-core)
8. [The Phase 2 challenge set](#the-phase-2-challenge-set)
9. [What we tested and rejected](#what-we-tested-and-rejected)
10. [Repo structure](#repo-structure)
11. [Assumptions and limitations](#assumptions-and-limitations)
12. [Rulebook compliance](#rulebook-compliance)

---

## The result in 30 seconds

The task: a social platform's data pipeline has collapsed. Recover the dataset
(it is **not** given — it is hidden behind a broken website), clean it, explain
every repair, then rebuild the analytics in SQL.

**What we did**

- Solved the site puzzle and recovered `Dataset 01` — **12,360** post rows + **1,500** user rows, provenance-verified against the live site.
- Found **10 distinct corruption families**, applied **27 logged repairs**, and closed the row arithmetic exactly: `12,360 - 360 duplicate replays - 1,779 empty-text hold-outs = 10,221`.
- Caught the trap the event buried: the "**midnight posting culture**" is fake — see [Exploratory analysis](#exploratory-analysis).
- Built a schema'd SQLite core (PK/FK/CHECK constraints, 2 views, long-form hashtag relation) and answered **12 challenges** with CTEs, `NTILE`, `LAG/LEAD`, `RANK` and windowed aggregates — every output captured live.
- **Refuted five plausible-sounding findings** with statistics instead of publishing them ([§8](#what-we-tested-and-rejected)).

---

## Reproduce it

```bash
git clone <this-repo> && cd <this-repo>
pip install -r requirements.txt
./run_all.sh
```

Ends with `21 passed` and two PDFs. Stages, if you want them one at a time:

| Command | Produces |
|---|---|
| `python src/verify_source.py` | re-downloads both files, byte-compares to `data/raw/`, records SHA-256 |
| `python src/clean_data.py` | `data/clean/` — clean CSVs, JSON, `repair_log.csv`, `data_quality_report.md` |
| `python src/eda.py` | `output/figures/*.png` + `output/eda_stats.json` (every number the report quotes) |
| `python src/build_db.py` | `output/social_engine.db` — schema, constraints, views |
| `python src/run_sql.py` | runs `queries/challenges.sql`, writes `output/sql_outputs.md` |
| `python src/make_screenshots.py` | `output/screenshots/Q1..Q12.png` |
| `python src/build_report.py` | both submission PDFs |
| `python src/make_notebook.py` | builds **and executes** `notebooks/01_data_cleaning_eda.ipynb` |
| `python -m pytest tests -q` | `21 passed` |

Deterministic: no random seeds, no sampling, no model, no network at run time
(`verify_source` is optional and offline-tolerant).

---

## How the dataset was recovered

The rulebook says the corrupted dataset "will not be given directly". The site
serves an empty `<div>` — every guessed data URL (`/dataset.csv`, `/api/data`,
`/logs`) 404s. The logic lives in its JS bundle, so the bundle was read and the
four hints resolved 1:1:

| Rulebook hint | What it pointed at in the bundle |
|---|---|
| "may not reveal everything at first glance" | 4 of the 5 dashboard modules are deliberate dead ends rendering *"this module cannot be displayed"* |
| "look closely at the recovery logs … beginning of each line" | SYSTEM LOG lines are prefixed `hh:mm:ss  service  …`; two of seven name **`node_07`** |
| "a message hidden in plain sight" | the italic line under the log panel: `last known surviving node: node_07` |
| "follow the pattern. Decode the connection. Find the node." | `help` advertises only `help/status/scan/logs/clear`, but the handler matches free text against `(connect\|access\|restore\|reconnect\|link)` **and** `(node.?0?7\|archive)` |

**No advertised command can win** — the archive opens only through that regex
branch. Typing:

```
connect node_07
```

unlocks `ARCHIVE NODE 07`, which serves the two files from `/dataset/`. An
organiser debug panel at `?test=true` prints a field literally named
`Real path → terminal: connect node_07`, independently confirming the route.

📄 Full step-by-step (for the viva): [`docs/recovery_walkthrough.md`](docs/recovery_walkthrough.md)

> **Provenance.** Both files are downloaded verbatim. `src/verify_source.py`
> re-fetches them and reports `2 matched · 0 mismatched`, writing SHA-256s to
> `output/provenance.json`. As a bonus check, the same two CSVs are also embedded
> as string literals in the app bundle for the in-browser download buttons — and
> they parse to **identical rows** (12,361 and 1,501 incl. header), so we know we
> have the real dataset and not a decoy.

---

## Corruption inventory and repairs

Profiling came first; every rule below answers a defect that was observed, not a
checklist item. Counts are from `data/clean/repair_log.csv`.

| Defect in the raw intake | Rows | Treatment | Justification |
|---|---:|---|---|
| exact duplicate rows | **360** | dropped; `post_id` made a real PK | identical across all 8 fields = outage retry replay |
| negative `likes` | **525** | `abs()` restore, row-flagged | mirrored distribution, one column only (see [the proof section](#the-two-decisions-that-needed-proof)) |
| `likes` as float strings (`-1205.0`) | 525 | cast to nullable `Int64` | keeps NULL ≠ 0 |
| blank / `NULL` likes | 1,858 | real NULL, **never imputed** | fabrication is prohibited |
| blank / `NULL` platform | 1,846 | explicit `Unspecified` bucket | not an invented platform |
| blank or `NULL` text body | 1,779 | held out to a separate CSV | count must reconcile |
| injected `<br>` / `<div>` | 663 | markup stripped, text kept | renderer artefact |
| trailing `&amp;` entity | 341 | unescaped, orphaned `&`/`,` trimmed | layered corruption |
| double-encoded UTF-8 (`C3 A9`) | 316 | latin-1 round-trip reversed | see [the proof section](#the-two-decisions-that-needed-proof) |
| three timestamp formats | 4,805 / 3,669 / 3,526 | one UTC datetime, ambiguity flagged | see [the proof section](#the-two-decisions-that-needed-proof) |

**Reconciliation** — the single most auditable line in this submission:

```
12,360 raw  -  360 exact duplicates  -  1,779 empty-text hold-outs  =  10,221 analysis rows
```

Held-out rows are written to `data/clean/Social_Engine_Posts_EmptyText_HeldOut.csv`
rather than deleted, so the identity closes from files on disk.

---

## The two decisions that needed proof

**Day-first dates.** `timestamp` holds ISO-8601, epoch-seconds **and**
`dd-mm-yyyy`. For that last block, `MM-DD` vs `DD-MM` is settled arithmetically:

```
of the 3,622 raw dd-mm-yyyy rows:
   first field  > 12 :  2,172      <- a day
   second field > 12 :      0      <- a month can never be 25
```

Month-first is impossible for most of the block, so one convention (day-first)
is applied to all of it; mixing readings per row would invent a distribution. The
1,450 rows where both fields are ≤ 12 are genuinely ambiguous — all flagged with
`flag_ambiguous_date_format`, and no claim in this repo depends on them.

**Negative likes are a sign flip, not lost data.**

| | count | median | max |
|---|---:|---:|---:|
| positive `likes` | 9,976 | 2,505 | 5,000 |
| \|negative `likes`\| | 525 | 2,388 | 4,987 |

`likes` is the *only* numeric column with negatives (`shares`, `comments` have
zero), every negative carries a `.0` suffix while positives are bare integers,
and the negatives mirror the positives' distribution and their 5,000 ceiling.
Lost data would be *missing*, not a mirror image — so magnitude is restored and
every row flagged. `RESTORE_SIGN_FLIPPED_LIKES = False` in `src/config.py`
switches to the conservative reading (null them) and the pipeline still runs.

📄 All 10 rules with reasoning: [`docs/cleaning_decisions.md`](docs/cleaning_decisions.md)

---

## Exploratory analysis

### The finding that matters most: the midnight peak does not exist

A naive hour-of-day histogram on the **cleaned** table shows **3,325 posts at
00:00 = 32.53%** of the corpus — an impressive "night-owl community" signal.

It is entirely an artefact. **3,002 of those rows come from the `dd-mm-yyyy`
intake block, which carries a date but no clock.** Restricted to rows that
genuinely have a time, the busiest hour holds **4.63%** against a trough of
3.80% — a spread ratio of 1.22. There is no circadian pattern; there is a
serialisation bug.

The `has_time` guard is therefore carried **into the SQL schema**, not just the
cleaning script, so no downstream query can repeat the mistake.

![naive vs valid hour-of-day](output/figures/03_time.png)

### Volume is flat, so the story is not growth

![monthly volume vs engagement](output/figures/01_trend.png)

Monthly volume mean 852, population SD 24.5; z-scores run -2.36 (2025-02) to
+1.07 (2024-05) with 3 of 12 months beyond ±1 SD. That oscillates around a flat
mean — no monotone component, so "the platform is growing" is unsupported.

### Platform differences are inside the noise band

![platform comparison](output/figures/02_platform.png)

Mean likes vary just **3.8%** across the five real platforms, and the rate at
which likes went missing is near-identical everywhere (14.16% Reddit → 15.67%
Twitter). That uniformity is the evidence that corruption hit the **transport
layer, not the sampling** — which is what licenses pooling platforms at all.
`Unspecified` (15.08%) is shown as its own grey bar, never hidden inside a rate.

### Users: reach ≠ resonance

![followers vs engagement](output/figures/07_users.png)

Follower count vs mean per-post engagement is **r = -0.0433** (r² = 0.19%) — and
the follower-quintile view (centre) is flat, which proves that's a real null and
not a missed non-linearity. Top decile of authors holds 18.4% of total
engagement, driven by volume, not by per-post quality.

![sentiment mix](output/figures/05_sentiment.png)

Corpus leans positive (40.95% / 31.91% neutral / 27.14% negative on a published
keyword lexicon — chosen over a model so any row can be recomputed by hand), but
correlation with likes is r = -0.0142. Negative posts even average slightly
*more* likes (2,509.8 vs 2,454.8) — the classic complaint-gets-engagement shape,
at an r that must honestly be reported as **no relationship**.

---

## The SQL analytical core

`output/social_engine.db`, built by `src/build_db.py`: `posts`, `users`,
`post_tags` with **primary keys, a foreign key, `CHECK` constraints and four
indices**, plus `v_posts_enriched` / `v_monthly` views. Schema choices encode
reasoning rather than describing it — e.g. `CHECK (likes IS NULL OR likes >= 0)`
puts the domain rule in the database, and `platform` is a `CHECK`-enumerated set
so a future bad export fails at INSERT instead of becoming a sixth platform.

**12 challenges, all executing**, across the four named categories:

| | |
|---|---|
| **Trend detection** | Q1 momentum + z-score vs the series' own SD · Q2 centred moving average and inflection points · Q10 hashtag momentum on share-of-month |
| **Anomaly discovery** | Q4 ratio-based amplification anomalies · Q5 Poisson attribution test · Q11 gap-and-islands posting streaks |
| **Behavioural grouping** | Q3 platform league table with missingness exposed · Q7 rank-based RFM · Q12 integrity gate |
| **Correlation** | Q8 Pearson r assembled from raw sums · Q9 the same relation bucketed |

Uses CTEs, `NTILE`, `LAG/LEAD`, `RANK`, `SUM(COUNT(*)) OVER ()`, `ROWS BETWEEN`,
views — as the rulebook invites.

<p align="center">
  <img src="output/screenshots/Q5.png" width="820" alt="Q5 Poisson attribution test"/>
</p>

**Q5 is the query we're proudest of**, and it's the one that *removes* a finding
(see [What we tested and rejected](#what-we-tested-and-rejected)). Two traps are documented in the SQL itself: SQL's bare `+` is
NULL-propagating, so `AVG(likes+shares+comments)` would silently drop 1,532 rows
and change the population and the metric at once — hence `COALESCE` in a view,
defined once.

📄 Design rationale + SQLite↔Postgres dialect notes: [`docs/schema_design.md`](docs/schema_design.md)
📄 Every query, its logic and its live output: [`output/sql_outputs.md`](output/sql_outputs.md)

---

## The Phase 2 challenge set

21 challenges — `E1`–`E5`, `M1`–`M5`, `H1`–`H6` — answered in
[`queries/phase2_challenges.sql`](queries/phase2_challenges.sql) against the same
database, plus **17 companion queries** that attack each headline answer before it
is published. Nothing here is a separate analysis: it reads the same
`v_posts_enriched` view and the same users table as the twelve queries above.

Live capture: [`output/phase2_sql_outputs.md`](output/phase2_sql_outputs.md) ·
screenshots: `output/screenshots/E1.png` … `H6b.png` ·
report: [`output/Phase2_ChallengeSet_Report.pdf`](output/Phase2_ChallengeSet_Report.pdf)

| # | Challenge | Answer |
|---|---|---|
| **E1** | Highest-volume platform (missing labels ignored) | **YouTube** — 1,770 posts |
| **E1b** | …and the field is flat | χ² 2.6094 vs 9.488 critical, df 4 — no platform preference |
| **E2** | Top 10 posts by likes + shares + comments | 7,893 at #1 (`ycjj5zzt7mvx`); 1,532 posts with no like count excluded |
| **E2b** | …how tight the cut is | 1st is only 4.09% above 10th; 14 posts within 1% of the cut |
| **E3** | Average likes / shares / comments per platform, highest average total | **Instagram** — 3,673.2 per post |
| **E3b** | …and the win is inside the noise | gap 1.02%, z = 0.635 — not significant |
| **E4** | Shared > 1,500 but liked < 500 | **214 posts**, both bounds strict |
| **E4b** | …is it one platform's quirk? | no — it appears on all six at 2.61% (densest) down to 1.34% |
| **E5** | Users with more than 40,000 followers | **293 users**, top follower count 49,944 |
| **M1** | Total engagement by location (needs both datasets) | **Los Angeles, USA** — 1,468,866 across 391 posts, 33 locations ranked |
| **M1b** | …but that ranking is volume, not quality | Shanghai is 6 by total and 33 by engagement per post — a 27-place shift |
| **M2** | High (≥ 25k) vs low (< 25k) follower cohorts | 3,598.8 vs 3,648.0 — the low cohort is ahead |
| **M2b** | …and not significantly so | z = -1.441 — follower count does not predict engagement |
| **M3** | Most active users | top 10 accounts; the leader wrote 17 posts |
| **M3b** | …but the 10th place is a tie band | 12 users share the 14-post count on the cut |
| **M4** | Best platform among ≥ 30,000-follower accounts | **Instagram** — 3,692.1 per post |
| **M4b** | …and it survives every threshold | Instagram wins at 25k, 30k, 35k, 40k and 45k |
| **M5** | Shares greater than likes + comments combined | **1,047 posts**; top 20 returned, worst excess 1,805 shares |
| **M5b** | …and the trap this question sets | reading a blank like count as 0 reports 2,201 instead — 1,154 of them exist only in the missing data |
| **H1** | Users averaging > 2× the overall average engagement | **no user qualifies** — the best is 1.806× the 3,623.72 baseline |
| **H1c** | …so where does the question have an answer? | 145 users clear 1.25×, 8 clear 1.5×, 1 clears 1.75×, 0 clear 2× |
| **H2** | Top 3 users by total engagement, in every location | **99 rows** — 3 for each of 33 locations |
| **H2b** | …and how contested the podium is | Tokyo's 3rd place beats 4th by 0.08% |
| **H3** | Posts at ≥ 2× their own platform's average engagement | **56 posts**, each judged against its own platform mean |
| **H3b** | …the bar is derived, not given | it ranges from 7,346 (Instagram) to 7,123 (Twitter) |
| **H4** | Under-5,000-follower users in the top engagement decile | **17 users**; decile floor 38,765 |
| **H4b** | …is that an artefact of NTILE? | no — an explicit percentile gives the same 17 users |
| **H5** | Potentially corrupted posts, by defect family | **4,418 posts** from the raw intake file (4 families) |
| **H5b** | …reconciling with the Phase-1 inventory | 525 negative likes · 1,846 missing platforms · 1,770 blank text bodies · 1,004 HTML rows — the same counts Phase 1 recorded |
| **H5c** | …the worst rows | 20 posts carry three defects at once |
| **H6** | Small accounts, above-average engagement, one over-shared post | **82 users** from a 1,500-user funnel |
| **H6b** | …the funnel | 287 have < 10k followers · 748 beat the overall average · 1045 own an over-shared post → 82 satisfy all three |

**Three things in this set are worth more than the answers.**

- **H1 returns zero rows, and that is the answer.** The 2× bar is
  7,247.43 against a best user average of
  6,545.50. Rather than reach for a friendlier
  definition, the query prints its own baseline and threshold, proves the gap is
  arithmetic, and adds a threshold ladder so the reader can see where the
  question *does* have an answer.
- **M5 is a trap with a price tag.** 2,201 "anomalies"
  appear if a blank like count is read as zero; 1,154
  of them exist only because the field is missing, and the reconciliation query
  proves the arithmetic gap equals that count exactly.
- **H5 cannot be asked of the cleaned table.** Cleaning is the step that removed
  the corruption, so the anomalies are detected on a verbatim staging table of
  the 12,360 intake rows, using the same SQL predicate that populated the
  inventory. The per-family counts match the Phase-1 corruption log exactly.

Six findings were produced and then **rejected by their own companions**: the
platform leader (E1b), the platform ranking (E3b), the follower advantage (M2b),
the location ranking (M1b), the over-sharing alarm (M5b) and the 2× power users
(H1b/H1c). They are listed in full in
[the report](output/Phase2_ChallengeSet_Report.pdf) — the rejections are the work.

### Form upload set

`submission/phase2/` holds the four slots the submission form asks for, each
labelled with the question numbers it answers:

| Slot | File | Format |
|---|---|---|
| SQL query | `Phase2_Slot1_SQL_Queries.pdf` | PDF |
| Output screenshots | `Phase2_Slot2_Output_Screenshots_1of5.jpeg` … `_5of5.jpeg` | JPEG ×5 |
| Explanation of logic | `Phase2_Slot3_Logic_Explanation.pdf` | PDF |
| Insight report | `Phase2_Slot4_Insight_Report.pdf` | PDF |

The form accepts at most five image files, so the 33 result sets are composited
into five labelled sheets rather than uploaded individually — every sheet names
the question (E1, M3, H6 …) above its result. Sizes, SHA-256 prefixes and the
upload order are in [`submission/phase2/MANIFEST.md`](submission/phase2/MANIFEST.md);
five tests assert the form's own constraints (JPEG only, ≤ 5 images, ≤ 10 MB,
declared format matches the bytes).

---

## What we tested and rejected

The most useful thing a data engineer does is kill their own nice-looking
findings. All five were plausible and all five failed:

| Tempting claim | Verdict | How it was refuted |
|---|---|---|
| "Night-owl audience — a third of posts at midnight" | **Artefact** | 3,002 of 3,325 are date-only rows; real peak is 4.63% (Q6) |
| "A coordinated amplification ring is gaming engagement" | **Not a ring** | 846 anomalous posts tested against a Poisson null (λ = n_anom/n_users): observed 31 vs 29.6 expected, **O/E = 1.05 → diffuse** (Q5) |
| "Bigger audiences engage more" | **Null** | r = -0.0433, and flat across follower quintiles — a real null, not a missed curve (Q8/Q9) |
| "Sentiment drives engagement" | **Null** | r = -0.0142 |
| "Instagram/YouTube outperform" | **Noise** | 3.8% spread, uniform missingness across platforms |

Q5 is the one to defend: **a per-user leaderboard would have "found" a bot ring
in any diffuse anomaly.** Testing the tail against chance is what stops a
fabricated insight from reaching the report — and the negative result is
published as a negative result.

---

## Repo structure

```
data/raw/          the two recovered files, byte-identical to the site
data/clean/        clean CSVs + JSON · repair_log.csv · data_quality_report.md
                   cleaning_summary.json · the empty-text hold-out CSV
src/               11 scripts: config, clean_data, eda, build_db, run_sql,
                   make_screenshots, build_report, build_phase2_report,
                   make_notebook, verify_source, make_submission
queries/           challenges.sql        -- 12 queries, each with a logic note
                   phase2_challenges.sql -- 16 E/M/H challenges + 17 companions
notebooks/         01_data_cleaning_eda.ipynb   -- executed, outputs attached
docs/              cleaning_decisions.md · schema_design.md · recovery_walkthrough.md
tests/             test_pipeline.py      -- 49 invariant tests
forensic/          app.js + index.html captured from the site (evidence)
output/            figures/ · screenshots/ · social_engine.db · three PDFs ·
                   sql_outputs.md · phase2_sql_outputs.md
submission/        phase1 = form-upload set (git-ignored)
submission/phase2/ the Phase-2 upload set: 3 PDFs + 5 JPEG sheets + MANIFEST.md
```

**Form upload set** — `./run_all.sh` builds `submission/`: the cleaned dataset,
the EDA PDF, and `MANIFEST.md` recording each file's size against the form's
10 MB cap and its SHA-256, so what gets uploaded is provably what the repo ships.
The form takes one file per slot, so the users table, the unrecoverable-text
hold-out and the repair log travel in this repo — or all at once in
`submission/Social_Engine_Cleaned_AllTables.json`.

Field-by-field answers for the intake form:
[`docs/form_submission_phase1.md`](docs/form_submission_phase1.md)
Phase 2: `output/Phase2_Insight_Report.pdf` (queries + screenshots + logic +
insight report in one PDF).

The notebook **imports the same functions the pipeline runs** rather than
re-implementing them, so it cannot drift from the shipped CSV.

---

## Assumptions and limitations

Stated up front because "clearly explain assumptions" is a scored criterion:

- **Single naive timezone.** No offset exists anywhere in the file; UTC assumed.
  If one is supplied later, only `post_hour` moves — no count changes.
- **1,450 dates stay genuinely ambiguous** (day ≤ 12 and month ≤ 12). Flagged,
  not hidden; any result can be recomputed on the unambiguous subset.
- **`abs()` on likes is a repair, not an imputation.** One config flag reverses
  it; it affects 525 raw rows, 430 of which survive into the analysis table.
- **Nothing is imputed.** 1,532 likes remain NULL and are excluded per metric.
- **Sentiment is a published keyword lexicon**, not a model — deliberately, so
  any single row can be verified by hand.
- **Held-out ≠ deleted.** 1,779 empty-body rows stay on disk so the arithmetic closes.
- We cannot validate against the organisers' reference "true" dataset; our
  standard is that every repair is justified by evidence *in* the file.

---

## Rulebook compliance

| Rule | How this repo satisfies it |
|---|---|
| Cleaned dataset (CSV/JSON) | `data/clean/*.csv` + `.json` |
| EDA report | `output/Phase1_EDA_Report.pdf` |
| Code notebook + docs + reproducible workflow | executed `.ipynb`, `run_all.sh`, README |
| All transformations justified | `repair_log.csv` — 27 actions with counts + reasons |
| Assumptions explained | [Assumptions and limitations](#assumptions-and-limitations) and `docs/cleaning_decisions.md` |
| Fabrication prohibited | zero imputation; both CSVs verbatim from the site, SHA-256 recorded |
| Code documented | every function states *why*, not just *what* |
| Any language/tool allowed | Python + SQLite |
| Schema design explained | [`docs/schema_design.md`](docs/schema_design.md) - primary key chosen *after* deduplication, normalisation rationale, `CHECK` constraints, and what was deliberately denormalised |
| Query logic documented | each query carries a `LOGIC:` block, auto-copied into the report |
| CTEs / window functions / views | Q1, Q2, Q7, Q10, Q11; two views |
| Hardcoded outputs → DQ | PDFs and screenshots render from live result sets at build time |
| Original work; repo maintained | this repo, one-command rebuild, tests to keep it honest |

---

<div align="center">

*"The data survived. Now rebuild it."*

— ARCHIVE NODE 07

</div>

<div align="center">

# 🌀 Data Vortex

### Rebuilding the Social Engine · Round 1: Data Restoration & Analytical Core · Round 2: The Semantic Layer (NLP)

**Forge-X** · Kunal Choudhary

*Aaruush'26* · Round 1: 13–16 September 2026 · Round 2: 17–18 September 2026

Round 1 — `12,360 raw rows → 10,221 analysis rows` · `27 justified repairs` · `45 SQL queries`
Round 2 — `9,000 labelled texts → 7,900 modelled` · `sentiment macro-F1 0.613` · `topic macro-F1 0.805` · `14 tests passing`

</div>

---

| | |
|---|---|
| **Team** | **Forge-X** |
| **Member** | Kunal Choudhary |
| **Phase 1** | cleaned dataset + EDA report + this repo |
| **Phase 2** | `queries/challenges.sql` + `output/Phase2_Insight_Report.pdf` |
| **Phase 2 challenge set** | `queries/phase2_challenges.sql` + `output/Phase2_ChallengeSet_Report.pdf` |
| **Phase 2 form upload set** | [`submission/phase2/`](submission/phase2/MANIFEST.md) — 4 slots, 8 files, labelled E1–H6 |
| **Round 2** | NLP semantic layer: executed notebook + 4 trained models + 2 PDFs (see [Part II](#part-ii--round-2-rebuilding-the-semantic-layer-nlp)) |
| **Round 2 form upload set** | [`submission/round2_form_upload/`](submission/round2_form_upload/SUBMISSION_DETAILS.md) — 4 slots, one file each, all < 10 MB |

> **Every number in this README is generated.** The Round-1 tables and figures
> are produced by `./run_all.sh` from the two recovered CSVs; the Round-2 tables
> by `./run_round2.sh` from Dataset 2 — nothing is typed by hand, because the
> rulebook disqualifies hardcoded outputs and prohibits fabricated data. Re-run
> them and you land on identical numbers.

---

## Contents

1. [The result in 30 seconds](#the-result-in-30-seconds)
2. [Round 2 in 30 seconds](#round-2-in-30-seconds)
3. [Reproduce it](#reproduce-it)
4. [How the dataset was recovered](#how-the-dataset-was-recovered)
5. [Corruption inventory and repairs](#corruption-inventory-and-repairs)
6. [The two decisions that needed proof](#the-two-decisions-that-needed-proof)
7. [Exploratory analysis](#exploratory-analysis)
8. [The SQL analytical core](#the-sql-analytical-core)
9. [The Phase 2 challenge set](#the-phase-2-challenge-set)
10. [Part II — Round 2: rebuilding the semantic layer](#part-ii--round-2-rebuilding-the-semantic-layer-nlp)
11. [What we tested and rejected](#what-we-tested-and-rejected)
12. [Repo structure](#repo-structure)
13. [Assumptions and limitations](#assumptions-and-limitations)
14. [Rulebook compliance](#rulebook-compliance)

---

## The result in 30 seconds

The task: a social platform's data pipeline has collapsed. Recover the dataset
(it is **not** given — it is hidden behind a broken website), clean it, explain
every repair, then rebuild the analytics in SQL.

**What we did**

- Solved the site puzzle and recovered `Dataset 01` — **12,360** post rows + **1,500** user rows, provenance-verified against the live site.
- Found **10 distinct corruption families**, applied **27 logged repairs**, and closed the row arithmetic exactly: `12,360 - 360 duplicate replays - 1,779 empty-text hold-outs = 10,221`.
- Caught the trap the event buried: the "**midnight posting culture**" is fake — see [Exploratory analysis](#exploratory-analysis).
- Built a schema'd SQLite core (PK/FK/CHECK constraints, 2 views, long-form hashtag relation) and answered **12 challenges** with CTEs, `NTILE`, `LAG/LEAD`, `RANK` and windowed aggregates — every output captured live.
- **Refuted five plausible-sounding findings** with statistics instead of publishing them ([§8](#what-we-tested-and-rejected)).

---

## Round 2 in 30 seconds

The task: the Social Engine's semantic comprehension layer has failed — it
cannot read meaning, tone or intent. Dataset 2 (9,000 labelled texts) must
teach it again, with the full NLP trail: preprocessing, model selection,
training methodology, evaluation, confusion matrix, error analysis.

**What we did**

- Audited Dataset 2 and closed the row arithmetic exactly:
  `9,000 raw − 0 empty − 1,100 exact duplicates = 7,900 modelled` — duplicates
  are held out, not deleted (Round 1 doctrine: hold-outs must reconcile).
- One stratified 80/20 split (`sentiment × topic`, seed 42 → 6,320 / 1,580)
  shared by both tasks; the test set is touched exactly once, by the CV winner.
- Ran a 6-spec bake-off per task (dummy · Naive Bayes · LogReg · LinearSVC ·
  word-only TF-IDF · word+char TF-IDF union) under 5-fold stratified CV:
  **TF-IDF + linear models win** — `logreg_union` for sentiment
  (margin +0.0081 over `svc_union`), `svc_union` sigmoid-calibrated for topic
  (+0.0134 over `logreg_union`).
- Test results — sentiment: **acc 0.6133 · macro-F1 0.6134 · ROC-AUC OvR 0.792**;
  topic: **acc 0.9677 · macro-F1 0.8051 · MCC 0.864**.
- Error analysis with receipts: topic macro-F1 is capped by the two rare
  classes (Account_Security recall 0.50 at n=26, Feature_Feedback recall 0.44
  at n=50) while the head is near-perfect (Community_Discussion F1 0.982,
  Technical_Issues 0.961); sentiment's confusion concentrates in Neg↔Neu.
- Honesty bonus: unsupervised LDA/NMF topics (K=4) agree with the human labels
  at **NMI ≈ 0.002** — published as a finding, not hidden: the topic signal is
  lexical-supervised, not clusterable.
- Shipped all four rulebook deliverables: executed notebook (18 cells, 0
  errors), 4 `.pkl` models, a 14-page Evaluation Metrics Report and a 13-page
  Technical Report — every number generated by `./run_round2.sh`.

---

## Reproduce it

```bash
git clone <this-repo> && cd <this-repo>
pip install -r requirements.txt
./run_all.sh
```

Ends with `21 passed` and two PDFs. Stages, if you want them one at a time:

| Command | Produces |
|---|---|
| `python src/verify_source.py` | re-downloads both files, byte-compares to `data/raw/`, records SHA-256 |
| `python src/clean_data.py` | `data/clean/` — clean CSVs, JSON, `repair_log.csv`, `data_quality_report.md` |
| `python src/eda.py` | `output/figures/*.png` + `output/eda_stats.json` (every number the report quotes) |
| `python src/build_db.py` | `output/social_engine.db` — schema, constraints, views |
| `python src/run_sql.py` | runs `queries/challenges.sql`, writes `output/sql_outputs.md` |
| `python src/make_screenshots.py` | `output/screenshots/Q1..Q12.png` |
| `python src/build_report.py` | both submission PDFs |
| `python src/make_notebook.py` | builds **and executes** `notebooks/01_data_cleaning_eda.ipynb` |
| `python -m pytest tests -q` | `21 passed` |

Deterministic: no random seeds, no sampling, no model, no network at run time
(`verify_source` is optional and offline-tolerant).

**Round 2** (`pip install -r requirements-round2.txt` first):

```bash
./run_round2.sh
```

Ends with `14 passed` and both Round-2 PDFs. Stages, if you want them one at a
time:

| Command | Produces |
|---|---|
| `python src/round2/data.py` | `data/round2/clean/` — audit, hold-outs, stratified split, manifest |
| `python src/round2/train.py` | CV model selection, winners → `models/round2/*.pkl`, LDA/NMF |
| `python src/round2/evaluate.py` | `output/round2/metrics.json` + 19 figures |
| `python src/round2/build_eval_report.py` | `output/round2/Evaluation_Metrics_Report.pdf` |
| `python src/round2/build_tech_report.py` | `output/round2/Round2_Technical_Report.pdf` |
| `python src/round2/make_notebook.py` | builds **and executes** `notebooks/02_nlp_rebuild_semantic_layer.ipynb` |
| `python src/round2/make_submission.py` | `submission/round2/` (regenerated locally; kept untracked) |
| `python -m pytest tests/test_round2.py -q` | `14 passed` |

Deterministic here too: one seed (42, declared in `src/round2/config.py`)
drives the split, the CV folds, the calibration and LDA/NMF — re-run and every
number in the Round-2 reports lands identically. `src/round2/predict.py` loads
any shipped `.pkl` and scores raw text from the command line.

---

## How the dataset was recovered

The rulebook says the corrupted dataset "will not be given directly". The site
serves an empty `<div>` — every guessed data URL (`/dataset.csv`, `/api/data`,
`/logs`) 404s. The logic lives in its JS bundle, so the bundle was read and the
four hints resolved 1:1:

| Rulebook hint | What it pointed at in the bundle |
|---|---|
| "may not reveal everything at first glance" | 4 of the 5 dashboard modules are deliberate dead ends rendering *"this module cannot be displayed"* |
| "look closely at the recovery logs … beginning of each line" | SYSTEM LOG lines are prefixed `hh:mm:ss  service  …`; two of seven name **`node_07`** |
| "a message hidden in plain sight" | the italic line under the log panel: `last known surviving node: node_07` |
| "follow the pattern. Decode the connection. Find the node." | `help` advertises only `help/status/scan/logs/clear`, but the handler matches free text against `(connect\|access\|restore\|reconnect\|link)` **and** `(node.?0?7\|archive)` |

**No advertised command can win** — the archive opens only through that regex
branch. Typing:

```
connect node_07
```

unlocks `ARCHIVE NODE 07`, which serves the two files from `/dataset/`. An
organiser debug panel at `?test=true` prints a field literally named
`Real path → terminal: connect node_07`, independently confirming the route.

📄 Full step-by-step (for the viva): [`docs/recovery_walkthrough.md`](docs/recovery_walkthrough.md)

> **Provenance.** Both files are downloaded verbatim. `src/verify_source.py`
> re-fetches them and reports `2 matched · 0 mismatched`, writing SHA-256s to
> `output/provenance.json`. As a bonus check, the same two CSVs are also embedded
> as string literals in the app bundle for the in-browser download buttons — and
> they parse to **identical rows** (12,361 and 1,501 incl. header), so we know we
> have the real dataset and not a decoy.

---

## Corruption inventory and repairs

Profiling came first; every rule below answers a defect that was observed, not a
checklist item. Counts are from `data/clean/repair_log.csv`.

| Defect in the raw intake | Rows | Treatment | Justification |
|---|---:|---|---|
| exact duplicate rows | **360** | dropped; `post_id` made a real PK | identical across all 8 fields = outage retry replay |
| negative `likes` | **525** | `abs()` restore, row-flagged | mirrored distribution, one column only (see [the proof section](#the-two-decisions-that-needed-proof)) |
| `likes` as float strings (`-1205.0`) | 525 | cast to nullable `Int64` | keeps NULL ≠ 0 |
| blank / `NULL` likes | 1,858 | real NULL, **never imputed** | fabrication is prohibited |
| blank / `NULL` platform | 1,846 | explicit `Unspecified` bucket | not an invented platform |
| blank or `NULL` text body | 1,779 | held out to a separate CSV | count must reconcile |
| injected `<br>` / `<div>` | 663 | markup stripped, text kept | renderer artefact |
| trailing `&amp;` entity | 341 | unescaped, orphaned `&`/`,` trimmed | layered corruption |
| double-encoded UTF-8 (`C3 A9`) | 316 | latin-1 round-trip reversed | see [the proof section](#the-two-decisions-that-needed-proof) |
| three timestamp formats | 4,805 / 3,669 / 3,526 | one UTC datetime, ambiguity flagged | see [the proof section](#the-two-decisions-that-needed-proof) |

**Reconciliation** — the single most auditable line in this submission:

```
12,360 raw  -  360 exact duplicates  -  1,779 empty-text hold-outs  =  10,221 analysis rows
```

Held-out rows are written to `data/clean/Social_Engine_Posts_EmptyText_HeldOut.csv`
rather than deleted, so the identity closes from files on disk.

---

## The two decisions that needed proof

**Day-first dates.** `timestamp` holds ISO-8601, epoch-seconds **and**
`dd-mm-yyyy`. For that last block, `MM-DD` vs `DD-MM` is settled arithmetically:

```
of the 3,622 raw dd-mm-yyyy rows:
   first field  > 12 :  2,172      <- a day
   second field > 12 :      0      <- a month can never be 25
```

Month-first is impossible for most of the block, so one convention (day-first)
is applied to all of it; mixing readings per row would invent a distribution. The
1,450 rows where both fields are ≤ 12 are genuinely ambiguous — all flagged with
`flag_ambiguous_date_format`, and no claim in this repo depends on them.

**Negative likes are a sign flip, not lost data.**

| | count | median | max |
|---|---:|---:|---:|
| positive `likes` | 9,976 | 2,505 | 5,000 |
| \|negative `likes`\| | 525 | 2,388 | 4,987 |

`likes` is the *only* numeric column with negatives (`shares`, `comments` have
zero), every negative carries a `.0` suffix while positives are bare integers,
and the negatives mirror the positives' distribution and their 5,000 ceiling.
Lost data would be *missing*, not a mirror image — so magnitude is restored and
every row flagged. `RESTORE_SIGN_FLIPPED_LIKES = False` in `src/config.py`
switches to the conservative reading (null them) and the pipeline still runs.

📄 All 10 rules with reasoning: [`docs/cleaning_decisions.md`](docs/cleaning_decisions.md)

---

## Exploratory analysis

### The finding that matters most: the midnight peak does not exist

A naive hour-of-day histogram on the **cleaned** table shows **3,325 posts at
00:00 = 32.53%** of the corpus — an impressive "night-owl community" signal.

It is entirely an artefact. **3,002 of those rows come from the `dd-mm-yyyy`
intake block, which carries a date but no clock.** Restricted to rows that
genuinely have a time, the busiest hour holds **4.63%** against a trough of
3.80% — a spread ratio of 1.22. There is no circadian pattern; there is a
serialisation bug.

The `has_time` guard is therefore carried **into the SQL schema**, not just the
cleaning script, so no downstream query can repeat the mistake.

![naive vs valid hour-of-day](output/figures/03_time.png)

### Volume is flat, so the story is not growth

![monthly volume vs engagement](output/figures/01_trend.png)

Monthly volume mean 852, population SD 24.5; z-scores run -2.36 (2025-02) to
+1.07 (2024-05) with 3 of 12 months beyond ±1 SD. That oscillates around a flat
mean — no monotone component, so "the platform is growing" is unsupported.

### Platform differences are inside the noise band

![platform comparison](output/figures/02_platform.png)

Mean likes vary just **3.8%** across the five real platforms, and the rate at
which likes went missing is near-identical everywhere (14.16% Reddit → 15.67%
Twitter). That uniformity is the evidence that corruption hit the **transport
layer, not the sampling** — which is what licenses pooling platforms at all.
`Unspecified` (15.08%) is shown as its own grey bar, never hidden inside a rate.

### Users: reach ≠ resonance

![followers vs engagement](output/figures/07_users.png)

Follower count vs mean per-post engagement is **r = -0.0433** (r² = 0.19%) — and
the follower-quintile view (centre) is flat, which proves that's a real null and
not a missed non-linearity. Top decile of authors holds 18.4% of total
engagement, driven by volume, not by per-post quality.

![sentiment mix](output/figures/05_sentiment.png)

Corpus leans positive (40.95% / 31.91% neutral / 27.14% negative on a published
keyword lexicon — chosen over a model so any row can be recomputed by hand), but
correlation with likes is r = -0.0142. Negative posts even average slightly
*more* likes (2,509.8 vs 2,454.8) — the classic complaint-gets-engagement shape,
at an r that must honestly be reported as **no relationship**.

---

## The SQL analytical core

`output/social_engine.db`, built by `src/build_db.py`: `posts`, `users`,
`post_tags` with **primary keys, a foreign key, `CHECK` constraints and four
indices**, plus `v_posts_enriched` / `v_monthly` views. Schema choices encode
reasoning rather than describing it — e.g. `CHECK (likes IS NULL OR likes >= 0)`
puts the domain rule in the database, and `platform` is a `CHECK`-enumerated set
so a future bad export fails at INSERT instead of becoming a sixth platform.

**12 challenges, all executing**, across the four named categories:

| | |
|---|---|
| **Trend detection** | Q1 momentum + z-score vs the series' own SD · Q2 centred moving average and inflection points · Q10 hashtag momentum on share-of-month |
| **Anomaly discovery** | Q4 ratio-based amplification anomalies · Q5 Poisson attribution test · Q11 gap-and-islands posting streaks |
| **Behavioural grouping** | Q3 platform league table with missingness exposed · Q7 rank-based RFM · Q12 integrity gate |
| **Correlation** | Q8 Pearson r assembled from raw sums · Q9 the same relation bucketed |

Uses CTEs, `NTILE`, `LAG/LEAD`, `RANK`, `SUM(COUNT(*)) OVER ()`, `ROWS BETWEEN`,
views — as the rulebook invites.

<p align="center">
  <img src="output/screenshots/Q5.png" width="820" alt="Q5 Poisson attribution test"/>
</p>

**Q5 is the query we're proudest of**, and it's the one that *removes* a finding
(see [What we tested and rejected](#what-we-tested-and-rejected)). Two traps are documented in the SQL itself: SQL's bare `+` is
NULL-propagating, so `AVG(likes+shares+comments)` would silently drop 1,532 rows
and change the population and the metric at once — hence `COALESCE` in a view,
defined once.

📄 Design rationale + SQLite↔Postgres dialect notes: [`docs/schema_design.md`](docs/schema_design.md)
📄 Every query, its logic and its live output: [`output/sql_outputs.md`](output/sql_outputs.md)

---

## The Phase 2 challenge set

21 challenges — `E1`–`E5`, `M1`–`M5`, `H1`–`H6` — answered in
[`queries/phase2_challenges.sql`](queries/phase2_challenges.sql) against the same
database, plus **17 companion queries** that attack each headline answer before it
is published. Nothing here is a separate analysis: it reads the same
`v_posts_enriched` view and the same users table as the twelve queries above.

Live capture: [`output/phase2_sql_outputs.md`](output/phase2_sql_outputs.md) ·
screenshots: `output/screenshots/E1.png` … `H6b.png` ·
report: [`output/Phase2_ChallengeSet_Report.pdf`](output/Phase2_ChallengeSet_Report.pdf)

| # | Challenge | Answer |
|---|---|---|
| **E1** | Highest-volume platform (missing labels ignored) | **YouTube** — 1,770 posts |
| **E1b** | …and the field is flat | χ² 2.6094 vs 9.488 critical, df 4 — no platform preference |
| **E2** | Top 10 posts by likes + shares + comments | 7,893 at #1 (`ycjj5zzt7mvx`); 1,532 posts with no like count excluded |
| **E2b** | …how tight the cut is | 1st is only 4.09% above 10th; 14 posts within 1% of the cut |
| **E3** | Average likes / shares / comments per platform, highest average total | **Instagram** — 3,673.2 per post |
| **E3b** | …and the win is inside the noise | gap 1.02%, z = 0.635 — not significant |
| **E4** | Shared > 1,500 but liked < 500 | **214 posts**, both bounds strict |
| **E4b** | …is it one platform's quirk? | no — it appears on all six at 2.61% (densest) down to 1.34% |
| **E5** | Users with more than 40,000 followers | **293 users**, top follower count 49,944 |
| **M1** | Total engagement by location (needs both datasets) | **Los Angeles, USA** — 1,468,866 across 391 posts, 33 locations ranked |
| **M1b** | …but that ranking is volume, not quality | Shanghai is 6 by total and 33 by engagement per post — a 27-place shift |
| **M2** | High (≥ 25k) vs low (< 25k) follower cohorts | 3,598.8 vs 3,648.0 — the low cohort is ahead |
| **M2b** | …and not significantly so | z = -1.441 — follower count does not predict engagement |
| **M3** | Most active users | top 10 accounts; the leader wrote 17 posts |
| **M3b** | …but the 10th place is a tie band | 12 users share the 14-post count on the cut |
| **M4** | Best platform among ≥ 30,000-follower accounts | **Instagram** — 3,692.1 per post |
| **M4b** | …and it survives every threshold | Instagram wins at 25k, 30k, 35k, 40k and 45k |
| **M5** | Shares greater than likes + comments combined | **1,047 posts**; top 20 returned, worst excess 1,805 shares |
| **M5b** | …and the trap this question sets | reading a blank like count as 0 reports 2,201 instead — 1,154 of them exist only in the missing data |
| **H1** | Users averaging > 2× the overall average engagement | **no user qualifies** — the best is 1.806× the 3,623.72 baseline |
| **H1c** | …so where does the question have an answer? | 145 users clear 1.25×, 8 clear 1.5×, 1 clears 1.75×, 0 clear 2× |
| **H2** | Top 3 users by total engagement, in every location | **99 rows** — 3 for each of 33 locations |
| **H2b** | …and how contested the podium is | Tokyo's 3rd place beats 4th by 0.08% |
| **H3** | Posts at ≥ 2× their own platform's average engagement | **56 posts**, each judged against its own platform mean |
| **H3b** | …the bar is derived, not given | it ranges from 7,346 (Instagram) to 7,123 (Twitter) |
| **H4** | Under-5,000-follower users in the top engagement decile | **17 users**; decile floor 38,765 |
| **H4b** | …is that an artefact of NTILE? | no — an explicit percentile gives the same 17 users |
| **H5** | Potentially corrupted posts, by defect family | **4,418 posts** from the raw intake file (4 families) |
| **H5b** | …reconciling with the Phase-1 inventory | 525 negative likes · 1,846 missing platforms · 1,770 blank text bodies · 1,004 HTML rows — the same counts Phase 1 recorded |
| **H5c** | …the worst rows | 20 posts carry three defects at once |
| **H6** | Small accounts, above-average engagement, one over-shared post | **82 users** from a 1,500-user funnel |
| **H6b** | …the funnel | 287 have < 10k followers · 748 beat the overall average · 1045 own an over-shared post → 82 satisfy all three |

**Three things in this set are worth more than the answers.**

- **H1 returns zero rows, and that is the answer.** The 2× bar is
  7,247.43 against a best user average of
  6,545.50. Rather than reach for a friendlier
  definition, the query prints its own baseline and threshold, proves the gap is
  arithmetic, and adds a threshold ladder so the reader can see where the
  question *does* have an answer.
- **M5 is a trap with a price tag.** 2,201 "anomalies"
  appear if a blank like count is read as zero; 1,154
  of them exist only because the field is missing, and the reconciliation query
  proves the arithmetic gap equals that count exactly.
- **H5 cannot be asked of the cleaned table.** Cleaning is the step that removed
  the corruption, so the anomalies are detected on a verbatim staging table of
  the 12,360 intake rows, using the same SQL predicate that populated the
  inventory. The per-family counts match the Phase-1 corruption log exactly.

Six findings were produced and then **rejected by their own companions**: the
platform leader (E1b), the platform ranking (E3b), the follower advantage (M2b),
the location ranking (M1b), the over-sharing alarm (M5b) and the 2× power users
(H1b/H1c). They are listed in full in
[the report](output/Phase2_ChallengeSet_Report.pdf) — the rejections are the work.

### Form upload set

`submission/phase2/` holds the four slots the submission form asks for, each
labelled with the question numbers it answers:

| Slot | File | Format |
|---|---|---|
| SQL query | `Phase2_Slot1_SQL_Queries.pdf` | PDF |
| Output screenshots | `Phase2_Slot2_Output_Screenshots_1of5.jpeg` … `_5of5.jpeg` | JPEG ×5 |
| Explanation of logic | `Phase2_Slot3_Logic_Explanation.pdf` | PDF |
| Insight report | `Phase2_Slot4_Insight_Report.pdf` | PDF |

The form accepts at most five image files, so the 33 result sets are composited
into five labelled sheets rather than uploaded individually — every sheet names
the question (E1, M3, H6 …) above its result. Sizes, SHA-256 prefixes and the
upload order are in [`submission/phase2/MANIFEST.md`](submission/phase2/MANIFEST.md);
five tests assert the form's own constraints (JPEG only, ≤ 5 images, ≤ 10 MB,
declared format matches the bytes).

---

---

# PART II — ROUND 2: REBUILDING THE SEMANTIC LAYER (NLP)

*Rulebook: the Social Engine "still struggles to understand the meaning, tone,
and intent behind human language because its semantic comprehension layer has
failed." Dataset 2 — 9,000 labelled social-media texts — is the training corpus.
Deadline: 18 September 2026, 11:59 PM.*

## The dataset and the intake decisions

`data/round2/raw/Dataset2.csv` — byte-identical to the official download
(MD5-verified against the freshly fetched copy before anything ran). Four
columns: `text_id`, `post_text`, `sentiment_label`, `topic_category`.

| Intake fact | Value | Decision |
|---|---:|---|
| raw rows | 9,000 | — |
| empty texts | **0** | nothing to hold out (Round 1 had 1,779) |
| exact duplicate texts | **1,100** | held out, keep-first — duplicates straddling a split leak answers |
| conflicting labels on same text | **0** | the noisy case the pipeline was built to surface never occurs |
| **modelled rows** | **7,900** | `9,000 − 0 − 1,100 = 7,900` — the arithmetic closes on files on disk |

```
 9,000 raw  -  0 empty-text  -  1,100 exact duplicates  =  7,900 modelled rows
                                        split:  6,320 train  /  1,580 test
```

Sentiment is perfectly balanced (≈2,430/2,748/2,722 across Neg/Neu/Pos after
hold-outs). Topics are not: Community_Discussion 6,803 · Technical_Issues 718 ·
Feature_Feedback 250 · Account_Security 129. That 53× imbalance is why
**macro-F1 is the headline metric** — accuracy would let a majority-class
classifier score 0.86 while learning nothing.

## Preprocessing and features

- Text normalisation (`src/round2/text_clean.py`): HTML unescape, URL/email
  masking, lowercasing, elongation collapsing ("sooo" → "soo"), whitespace
  repair — deliberately conservative, because slang and punctuation *are*
  sentiment signal.
- Features (decision D8): word n-grams (1,2) **union** char n-grams (3,5),
  `min_df=2`, sublinear TF. Words carry semantics; character n-grams carry
  robustness to the typos and elongations in the data ("gr8", "luv"); `min_df=2`
  drops one-off misspellings from the vocabulary.
- Topics get unigrams only (D9: bigrams made topics noisier), capped vocab.

## Model selection and justification

Six specifications per task, scored by 5-fold stratified CV **on the train
split only** (`f1_macro`). The grids are small and declared up front in
`src/round2/config.py` (D7) — the point is a defensible comparison, not a
grid-search trophy.

| Spec (sentiment) | CV macro-F1 | Spec (topic) | CV macro-F1 |
|---|---|---|---|
| dummy (most-frequent) | 0.3240 ± 0.007 | dummy | 0.2397 ± 0.011 |
| Naive Bayes · word | 0.5709 ± 0.012 | Naive Bayes · word | 0.3768 ± 0.045 |
| LogReg · word | 0.5915 ± 0.016 | LogReg · word | 0.5791 ± 0.028 |
| LinearSVC · word | 0.5893 ± 0.014 | LinearSVC · word | 0.6042 ± 0.036 |
| LogReg · word+char **← winner** | **0.6110 ± 0.015** | LogReg · word+char | 0.7666 ± 0.034 |
| LinearSVC · word+char | 0.6028 ± 0.009 | LinearSVC · word+char **← winner** | **0.7800 ± 0.037** |

Why linear models and no transformer: ~9k short texts do not justify a GPU
model (D7); TF-IDF + linear classifiers reproduce on any machine, and their
feature weights are inspectable in the viva. The char-ngram union is what buys
the +0.02 on sentiment and +0.18 on topic over word-only features — measurable
in the table above, not asserted. The SVC winner is wrapped in sigmoid
calibration (3-fold, D10) so the shipped `topic_best.pkl` outputs honest
probabilities; log-loss before/after is reported in the metrics PDF.

## Training methodology

One seed (42) drives the split, the CV folds, the calibration and LDA/NMF.
Selection happens entirely inside train; the 1,580-row test set is scored
**once** by each refit winner — no test peeking, no seed hacking (D5/D6).
Total training: 273 s on CPU. Every choice above is a named constant in
`src/round2/config.py` (D1–D10), so a judge can change an assumption and re-run
in one place.

## Results

| | sentiment (3-class) | topic (4-class) |
|---|---|---|
| winner | `logreg_union` | `svc_union` (+ sigmoid calibration) |
| test accuracy | 0.6133 | 0.9677 |
| test macro-F1 | **0.6134** | **0.8051** |
| MCC | 0.4201 | 0.8645 |
| ROC-AUC (OvR) | 0.7916 | — |
| log-loss | 0.8621 | — |

| sentiment | precision | recall | F1 | n | | topic | precision | recall | F1 | n |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|
| Negative | 0.634 | 0.673 | 0.653 | 486 | | Community_Discussion | 0.965 | 0.999 | 0.982 | 1360 |
| Neutral | 0.565 | 0.519 | 0.541 | 549 | | Technical_Issues | 0.985 | 0.938 | 0.961 | 144 |
| Positive | 0.638 | 0.655 | 0.646 | 545 | | Feature_Feedback | 1.000 | 0.440 | 0.611 | 50 |
| | | | | | | Account_Security | 1.000 | 0.500 | 0.667 | 26 |

<p align="center">
  <img src="output/round2/figures/r2_03_confusion_sent.png" width="420" alt="sentiment confusion"/>
  <img src="output/round2/figures/r2_03_confusion_top.png" width="420" alt="topic confusion"/>
</p>

## Error analysis

- **The topic "gap" is a sample-size story, not a model failure.** The two rare
  classes have perfect precision but recall 0.44/0.50: the model finds them only
  when the lexicon is unambiguous. Arithmetic: with the head at 0.982/0.961,
  macro-F1 = 0.805 is exactly the mean of {0.982, 0.961, 0.611, 0.667}. Fixing
  it needs more labelled tail data or threshold tuning — not a bigger model; and
  class-weight sweeps were already inside the CV comparison.
- **Sentiment's confusion is Neg↔Neu.** Neutral is the catch-all class
  (precision 0.565, recall 0.519): factual-sounding complaints land in Neutral,
  hedged positives stay Positive. Meanwhile ROC-AUC OvR = 0.792 shows the
  ranking signal is real — the 3-class decision boundary is what blurs, the
  classic short-text sentiment ceiling without transformers.
- **Errors were read, not just counted.** Misclassification slices by text
  length, by class and by confidence are in the Evaluation Metrics Report
  (figures `r2_09_*`), and the Technical Report quotes representative misses.

## The unsupervised cross-check — reported even though it "failed"

LDA and NMF were fitted with K=4 (one topic per labelled class) as an
unsupervised sanity check against the human labels:

| model | NMI | ARI |
|---|---:|---:|
| LDA | 0.0020 | −0.0030 |
| NMF | 0.0027 | 0.0068 |

Near-zero agreement: the labelled topics do not fall out of raw co-occurrence
statistics — Community_Discussion is defined by *absence* of the other topics'
vocabulary. The semantic layer is therefore built **supervised**, and this
disagreement is published instead of buried. (`output/round2/figures/r2_10_*`
shows what each unsupervised topic actually latched onto.)

## Deliverables — rulebook → file

| Rulebook requirement | File |
|---|---|
| NLP Model Script/Notebook | `notebooks/02_nlp_rebuild_semantic_layer.ipynb` (executed, 18 cells, 0 errors) + `src/round2/` |
| Trained Model Files | `models/round2/`: `sentiment_best.pkl`, `topic_best.pkl`, `topic_lda.pkl`, `topic_nmf.pkl` |
| Evaluation Metrics Report | `output/round2/Evaluation_Metrics_Report.pdf` (14 pp) |
| Round 2 Technical Report | `output/round2/Round2_Technical_Report.pdf` (13 pp — problem definition, preprocessing, model selection, training methodology, metrics, confusion matrix, error analysis) |

### Form upload set

The Google Form takes **one file per slot, max 10 MB**, so
[`submission/round2_form_upload/`](submission/round2_form_upload/SUBMISSION_DETAILS.md)
holds one renamed file per slot — the four `.pkl` models bundled into a single
`Slot2_Trained_Model_Files.zip` (5.0 MB) — plus `SUBMISSION_DETAILS.md` with
SHA-256 checksums for every upload. Regenerate with `./run_round2.sh`.

---

## What we tested and rejected

The most useful thing a data engineer does is kill their own nice-looking
findings. All five were plausible and all five failed:

| Tempting claim | Verdict | How it was refuted |
|---|---|---|
| "Night-owl audience — a third of posts at midnight" | **Artefact** | 3,002 of 3,325 are date-only rows; real peak is 4.63% (Q6) |
| "A coordinated amplification ring is gaming engagement" | **Not a ring** | 846 anomalous posts tested against a Poisson null (λ = n_anom/n_users): observed 31 vs 29.6 expected, **O/E = 1.05 → diffuse** (Q5) |
| "Bigger audiences engage more" | **Null** | r = -0.0433, and flat across follower quintiles — a real null, not a missed curve (Q8/Q9) |
| "Sentiment drives engagement" | **Null** | r = -0.0142 |
| "Instagram/YouTube outperform" | **Noise** | 3.8% spread, uniform missingness across platforms |

Q5 is the one to defend: **a per-user leaderboard would have "found" a bot ring
in any diffuse anomaly.** Testing the tail against chance is what stops a
fabricated insight from reaching the report — and the negative result is
published as a negative result.

---

## Repo structure

```
data/raw/          the two recovered files, byte-identical to the site
data/clean/        clean CSVs + JSON · repair_log.csv · data_quality_report.md
                   cleaning_summary.json · the empty-text hold-out CSV
data/round2/raw/   Dataset2.csv -- 9,000 labelled texts, byte-identical to the
                   official download (MD5-verified)
data/round2/clean/ audit profile · train/test split · hold-outs · manifest
src/               Round 1: config, clean_data, eda, build_db, run_sql,
                   make_screenshots, build_report, build_phase2_report,
                   make_notebook, verify_source, make_submission
src/round2/        Round 2: config (all analyst decisions D1-D10), data,
                   text_clean, models, train, evaluate, figures, predict,
                   build_eval_report, build_tech_report, make_notebook,
                   make_submission
queries/           challenges.sql        -- 12 queries, each with a logic note
                   phase2_challenges.sql -- 16 E/M/H challenges + 17 companions
notebooks/         01_data_cleaning_eda.ipynb          -- executed, outputs attached
                   02_nlp_rebuild_semantic_layer.ipynb -- executed, outputs attached
docs/              cleaning_decisions.md · schema_design.md · recovery_walkthrough.md
tests/             test_pipeline.py (49 invariant tests) · test_round2.py (14)
forensic/          app.js + index.html captured from the site (evidence)
output/            figures/ · screenshots/ · social_engine.db · three PDFs ·
                   sql_outputs.md · phase2_sql_outputs.md
output/round2/     metrics.json · train_record.json · figures/ (19) ·
                   Evaluation_Metrics_Report.pdf · Round2_Technical_Report.pdf
models/round2/     sentiment_best.pkl · topic_best.pkl ·
                   topic_lda.pkl · topic_nmf.pkl
submission/        phase1 = form-upload set (git-ignored)
submission/phase2/ the Phase-2 upload set: 3 PDFs + 5 JPEG sheets + MANIFEST.md
submission/round2_form_upload/  the Round-2 form set: Slot1-4 + checksums
```

**Form upload set** — `./run_all.sh` builds `submission/`: the cleaned dataset,
the EDA PDF, and `MANIFEST.md` recording each file's size against the form's
10 MB cap and its SHA-256, so what gets uploaded is provably what the repo ships.
The form takes one file per slot, so the users table, the unrecoverable-text
hold-out and the repair log travel in this repo — or all at once in
`submission/Social_Engine_Cleaned_AllTables.json`.

Field-by-field answers for the intake form:
[`docs/form_submission_phase1.md`](docs/form_submission_phase1.md)
Phase 2: `output/Phase2_Insight_Report.pdf` (queries + screenshots + logic +
insight report in one PDF).

The notebook **imports the same functions the pipeline runs** rather than
re-implementing them, so it cannot drift from the shipped CSV.

---

## Assumptions and limitations

Stated up front because "clearly explain assumptions" is a scored criterion:

- **Single naive timezone.** No offset exists anywhere in the file; UTC assumed.
  If one is supplied later, only `post_hour` moves — no count changes.
- **1,450 dates stay genuinely ambiguous** (day ≤ 12 and month ≤ 12). Flagged,
  not hidden; any result can be recomputed on the unambiguous subset.
- **`abs()` on likes is a repair, not an imputation.** One config flag reverses
  it; it affects 525 raw rows, 430 of which survive into the analysis table.
- **Nothing is imputed.** 1,532 likes remain NULL and are excluded per metric.
- **Sentiment is a published keyword lexicon**, not a model — deliberately, so
  any single row can be verified by hand.
- **Held-out ≠ deleted.** 1,779 empty-body rows stay on disk so the arithmetic closes.
- We cannot validate against the organisers' reference "true" dataset; our
  standard is that every repair is justified by evidence *in* the file.
- **Round 2 — duplicates are held out, conflicts would be kept.** Exact
  (text, label) duplicates straddle any split and inflate scores; 1,100 were
  quarantined. The same text with *conflicting* labels is label noise and would
  be kept and reported everywhere — the data contained none (0 conflicts).
- **Round 2 — one split, one seed, one test touch.** Selection lives inside
  the train folds (5-fold CV); the 1,580-row test set is scored once by each
  winner. Seed 42 is declared in `src/round2/config.py` before any run.
- **Round 2 — linear models over deep nets, on purpose** (see the CV table):
  the alternatives were measured, not assumed away.
- **Round 2 — macro-F1 is the headline** because the topic classes are
  imbalanced 53:1; accuracy would flatter a majority-class classifier.
- **Round 2 — the unsupervised check disagreed (NMI ≈ 0.002) and is published
  as a disagreement**, which is why the shipped models are supervised.

---

## Rulebook compliance

| Rule | How this repo satisfies it |
|---|---|
| Cleaned dataset (CSV/JSON) | `data/clean/*.csv` + `.json` |
| EDA report | `output/Phase1_EDA_Report.pdf` |
| Code notebook + docs + reproducible workflow | executed `.ipynb`, `run_all.sh`, README |
| All transformations justified | `repair_log.csv` — 27 actions with counts + reasons |
| Assumptions explained | [Assumptions and limitations](#assumptions-and-limitations) and `docs/cleaning_decisions.md` |
| Fabrication prohibited | zero imputation; both CSVs verbatim from the site, SHA-256 recorded |
| Code documented | every function states *why*, not just *what* |
| Any language/tool allowed | Python + SQLite |
| Schema design explained | [`docs/schema_design.md`](docs/schema_design.md) - primary key chosen *after* deduplication, normalisation rationale, `CHECK` constraints, and what was deliberately denormalised |
| Query logic documented | each query carries a `LOGIC:` block, auto-copied into the report |
| CTEs / window functions / views | Q1, Q2, Q7, Q10, Q11; two views |
| Hardcoded outputs → DQ | PDFs and screenshots render from live result sets at build time |
| Original work; repo maintained | this repo, one-command rebuild, tests to keep it honest |
| R2: NLP model script/notebook | executed `notebooks/02_nlp_rebuild_semantic_layer.ipynb` + `src/round2/` |
| R2: trained model files | `models/round2/*.pkl` — winners + LDA/NMF, bundled for the form with SHA-256s |
| R2: evaluation metrics report | `output/round2/Evaluation_Metrics_Report.pdf` — test + CV + ROC + calibration + slices |
| R2: technical report | `output/round2/Round2_Technical_Report.pdf` — all seven rulebook sections |
| R2: model selection & justification | 6-spec CV bake-off per task, margins reported, config decisions D1–D10 |
| R2: confusion matrix + error analysis | both PDFs; rare-class recall traced to sample size, not model choice |
