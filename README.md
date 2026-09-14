<div align="center">

# 🌀 Data Vortex — Round 1

### Rebuilding the Social Engine · Data Intake Restoration & Analytical Core

**Forge-X** · Kunal Choudhary

*Aaruush'26* · 13–16 September 2026 · Round 1 · Phase 1 + Phase 2

`12,360 raw rows → 10,221 analysis rows` · `27 justified repairs` · `12 SQL queries` · `21 tests passing`

</div>

---

| | |
|---|---|
| **Team** | **Forge-X** |
| **Member** | Kunal Choudhary |
| **Phase 1** | cleaned dataset + EDA report + this repo |
| **Phase 2** | `queries/challenges.sql` + `output/Phase2_Insight_Report.pdf` |

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
8. [What we tested and rejected](#what-we-tested-and-rejected)
9. [Repo structure](#repo-structure)
10. [Assumptions and limitations](#assumptions-and-limitations)
11. [Rulebook compliance](#rulebook-compliance)

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
src/               10 scripts: config, clean_data, eda, build_db, run_sql,
                   make_screenshots, build_report, make_notebook,
                   verify_source, make_submission
queries/           challenges.sql        -- 12 queries, each with a logic note
notebooks/         01_data_cleaning_eda.ipynb   -- executed, outputs attached
docs/              cleaning_decisions.md · schema_design.md · recovery_walkthrough.md
tests/             test_pipeline.py      -- 21 invariant tests
forensic/          app.js + index.html captured from the site (evidence)
output/            figures/ · screenshots/ · social_engine.db · both PDFs · sql_outputs.md
submission/        the form-upload set + MANIFEST.md (regenerated, git-ignored)
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
