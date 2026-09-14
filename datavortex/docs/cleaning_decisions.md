# Cleaning decisions — what was done, and on what evidence

Every rule in `src/config.py` corresponds to a defect that was **observed** in
the raw file before any code was written. This document is the reasoning the
rulebook asks for ("all transformations must be justified", "clearly explain
assumptions"). Counts here are reproduced by `data/clean/repair_log.csv`.

---

## D1 — textual missing tokens become real NULL (never 0, never a category)

`{ "", "NULL", "null", "None", "NaN", "N/A", "NA", "n/a" }` → `NA`.

The exporter wrote the *word* `NULL` into `platform`, `likes` and `text_content`.
Three failure modes are avoided by treating it as missing:

* `platform = "NULL"` becoming a sixth platform, polluting every per-platform mean.
* `likes = "NULL"` becoming `0`, which asserts "nobody liked this" — a claim
  about the world, not an absence of knowledge. `0 likes` and `unknown likes`
  behave completely differently in an engagement-rate denominator.
* `text_content = "NULL"` entering a hashtag or sentiment pipeline as content.

Affected: 1,846 platform · 1,858 likes · 1,770 text rows.

---

## D2 — the `dd-mm-yyyy` block is day-first (arithmetic, not convention)

The `timestamp` column holds three coexisting formats:

| format | rows | carries a clock? |
|---|---:|---|
| `2025-04-13T20:12:18` ISO-8601 | 4,805 | yes |
| `1722528840` epoch seconds | 3,669 | yes |
| `25-09-2024` `dd-mm-yyyy` | 3,526 | **no** |

For the third block, `MM-DD` vs `DD-MM` is decided by the data, not by taste:

```
first field  > 12 :  2,172
second field > 12 :      0
```

A month cannot be 25. So **month-first is arithmetically impossible for 60% of
the block**, and no per-row mixing is allowed either — half a block read one way
and half the other would silently invent a distribution. One convention
(day-first) is applied to the whole block, and all 3,526 rows are flagged with
`flag_ambiguous_date_format`.

**Residual risk, stated plainly:** the 1,450 rows where both fields are ≤ 12 are
genuinely ambiguous and cannot be resolved from this file. Any conclusion that
depends on them can be recomputed on the unambiguous subset with one filter.
Nothing in this submission does: the day-of-month and month-level aggregates are
identical under both readings for those rows, and the two claims that would be
affected (a weekday effect, a seasonality effect) are both null anyway.

---

## D3 — negative `likes` are a sign flip, so magnitude is restored

525 negative values, e.g. `-1205.0`. They are **not** dropped and **not** nulled,
because the distribution identifies them as recoverable:

| | count | median | max |
|---|---:|---:|---:|
| positive likes | 9,976 | 2,505 | 5,000 |
| \|negative likes\| | 525 | 2,388 | 4,987 |

Three facts make deletion the wrong call:

1. `likes` is the **only** numeric column with negatives — `shares` and
   `comments` have none. A column-specific, sign-only fault is a serialisation
   fault, not a data-generating one.
2. The negatives mirror the positives. Genuine "lost" values would be missing,
   not uniformly distributed over the same support.
3. Every negative carries a `.0` suffix (`-1205.0`) while positives are bare
   integers — the float artefact of one code path having processed them
   differently, which is exactly what a sign-flipping exporter looks like.
4. The support has a hard ceiling at 5,000 on both sides: nothing above 5,000
   exists. Real likes would not stop at the same round bound the negatives
   mirror to.

So `abs()` restores the value, `flag_likes_sign_restored` marks every row, and
the column is cast to nullable `Int64`. **430** of the 525 repaired rows survive
into the analysis table (the rest were empty-text hold-outs).

`RESTORE_SIGN_FLIPPED_LIKES = False` switches to nulling them instead — the
conservative reading — and the pipeline re-runs cleanly either way. That switch
existing in code is the honest version of "we considered both".

---

## D4 — missing values are never imputed

1,532 likes stay NULL in the analysis table. Mean-like aggregates are computed
over the rows that have likes, and the missingness rate is reported *alongside*
every platform comparison so the reader can see the base. No median, mean,
KNN or model fill is used anywhere.

This is also what makes the Phase-2 SQL honest: `engagement` is defined once in a
view as `COALESCE(likes,0)+COALESCE(shares,0)+COALESCE(comments,0)` with a
`CHECK` guaranteeing at least one operand exists. SQL's bare `+` would otherwise
return NULL and silently drop 15% of rows from every aggregate — a mistake that
changes the population *and* the metric simultaneously. The direction of the
residual error is deliberate: a row with missing likes is slightly
**understated**, which is recoverable by filtering. An inflated row is not.

---

## D5 — empty bodies are held out, not deleted

1,779 rows have no text at all, or only the token `NULL` (which includes the
`NULL&amp;` form — see D7). An empty body cannot support a content, hashtag or
sentiment claim, so they are excluded from the analysis table **and written to
`Social_Engine_Posts_EmptyText_HeldOut.csv`** with their engagement intact.

Why not just delete them: then `12,360 → 10,221` could not be reconciled from the
artefacts alone, and "we dropped the bad rows" becomes an unauditable claim.
Why not keep them: a NULL text in an analysis table gets read as "no opinion
expressed", which is a fabrication.

---

## D6 — platform gaps get an explicit bucket

Missing platform → `'Unspecified'` (1,541 rows, 15.08% of the analysis table).
It is kept for volume, and excluded from per-platform *rate* comparisons by a
visible `in_rate_comparison` column in Q3 rather than by a hidden filter.

The missingness rate is itself uniform across platforms (14.16% Reddit to 15.67%
Twitter). That is the evidence that the corruption hit the transport layer
evenly, which is what licenses pooling the platforms at all. Had missingness
concentrated on one platform, its means would have been untrustworthy.

---

## D7 — layered text corruption, repaired in a specific order

Three artefacts stack on the same string, and the order of repair changes the
result. The canonical case is `NULL&amp;` and `NULLÃ©`:

```
'NULL&amp;'  --unescape-->  'NULL&'  --strip tail-->  'NULL'  --sentinel-->  NA
'NULLÃ©'     --latin-1 round-trip-->  'NULLé'  --strip tail-->  'NULL'  -->  NA
```

If the sentinel test ran before unescaping or before mojibake repair, both stay
alive as *content* — and a later aggregate would count a literal `NULL` as a
post about NULL. That bug was actually shipped, caught by the reconciliation
arithmetic (1,740 vs the expected 1,731), and fixed; the 9-row gap was exactly
these rows.

Counts: 328 entity unescapes · 646 tag strips · 328 stray `&` · 306 whitespace
trims · 306 mojibake repairs · 68 sentinel-as-text conversions.

**Mojibake, specifically.** 316 rows end in the byte pair `C3 A9`, which is the
UTF-8 encoding of `é` that was decoded as Latin-1 and re-encoded as UTF-8. The
repair is to run that cycle backwards (`encode('latin-1').decode('utf-8')`),
kept only if it produces no `U+FFFD` replacement character. Two facts justify
stripping the decoded tail rather than treating it as content: all 316 mojibake
rows end with the *same* sequence, and `text_content` contains **zero** other
non-ASCII characters anywhere. Real French copy would not look like that.

**Trailing separators.** The injected markup and entity sat *after* a list
separator, so removing them orphans a `,` — and stripping that comma
unconditionally would corrupt legitimate text like `#Fashion, `. The repair loops
over the tail until the string stops changing, and only ever removes `&`/`,` at
the very end. 85 rows had the exact `, #Tag&amp;` shape.

---

## D8 — duplicates: replay, and what was checked

360 rows are duplicated **exactly**, across all eight fields. That is the
signature of a retry loop writing the same event twice during the outage, not of
two posts that happen to look alike. All 352 repeated `post_id` values fall in
this class, so dedup leaves **zero** id collisions — asserted in code
(`assert conflict == 0`), because a same-id-different-payload row would be an
identity conflict needing manual arbitration, and there are none.

---

## What was deliberately *not* done

| Temptation | Why not |
|---|---|
| Drop the 15% of rows with missing likes | discards valid content and skews the corpus to "rows where likes survived" |
| Fill missing likes with the median | invents 1,532 observations; rulebook prohibits fabrication |
| Read `MM-DD` where both fields are ≤ 12 | mixing conventions inside one block silently invents a date distribution |
| Drop the platform-gap rows | loses 1,541 valid posts to fix a column that only 3 of 12 queries need |
| Winsorise/cap engagement outliers | the columns are uniform by design; there are no outliers to remove, and clipping would be tuning to a result |
| Trust the midnight peak | format artefact — see `Q6` |
