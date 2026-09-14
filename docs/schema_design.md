# Schema design and dialect notes (Phase 2)

## 1. Why this shape

Phase 1 produced two flat CSVs. Loading them straight into a table and querying
`text_content LIKE '%#Tag%'` from five different places is the most common way
this round gets failed, because it makes the string format part of the analytic
logic. The schema therefore does three things before any query is written.

| Decision | Reason |
|---|---|
| `posts.post_id` is a real `PRIMARY KEY` | It was *not* a key in the raw file (352 ids repeated across 712 rows). Making it one now means a duplicate cannot be re-introduced later, and it forces the dedup claim in Phase 1 to be verifiable by the DB itself. |
| `platform` has a `CHECK (... IN (...))` constraint | The raw column held `''` and `'NULL'` as *values*. Enumerating the allowed set means a future bad export fails at INSERT instead of silently adding a sixth "platform". |
| `likes`/`shares`/`comments` are `INTEGER` with `CHECK (>= 0)` | The corruption produced negative counts. A `CHECK` encodes the domain rule in the schema, so restoring magnitudes in Phase 1 is enforced, not just asserted in prose. |
| NULL is preserved, never `0` | A `CHECK (likes IS NULL OR likes >= 0)` is deliberately permissive about NULL. Missing likes are a known unknown; `0` is a claim that nobody liked the post. |
| `users.user_id` is referenced by `posts.user_id` | Turns referential integrity from an EDA task into a constraint. `PRAGMA foreign_key_check` returning no rows is the proof. |
| `location` split into `city` + `country` | A single `"Berlin, Germany"` string cannot be grouped without parsing in every query, and it hid `UK` vs `United Kingdom`. |
| `post_tags` is a separate relation | Long-form beats a packed string: hashtag analysis becomes `GROUP BY tag` and the co-occurrence self-join becomes possible at all. |
| `has_time` flag carried into SQL | The date-only intake rows have no clock. Any hour-of-day query that ignores this fabricates a midnight peak. Keeping the flag *in the schema* means the guard is invisible to misuse — you have to use it. |
| `v_posts_enriched` view | `engagement` and `amplify_ratio` are defined once. If ten queries each write their own `COALESCE`, at least one of them gets it wrong. |

## 2. The one trap in this schema, and why it is written that way

SQL's `+` is NULL-propagating:

```sql
1 + NULL          -- NULL
likes + shares + comments   -- NULL for 1,535 rows
```

So `AVG(likes + shares + comments)` does not average all rows — it averages the
rows where likes happened to survive, i.e. it silently changes the population
*and* the metric in one step. The view therefore defines:

```sql
COALESCE(likes,0) + COALESCE(shares,0) + COALESCE(comments,0)
```

with a `CHECK` on the table guaranteeing at least one of the three is present.
The trade-off is explicit: a row whose likes went missing contributes
`shares + comments` and is therefore slightly *understated*. That is the honest
direction of error — understating is recoverable by filtering, inflating is not.
`partial_metrics = 1` marks those rows so any query can be rerun restricted to
complete rows; the Phase 2 report quotes both.

## 3. Dialect: SQLite first, Postgres equivalents inline

SQLite 3.25+ has CTEs and window functions, which is everything the rulebook's
"CTEs, Window Functions, Views, Procedures" line asks for. Three things it
lacks appear in these queries, and the `[PG]` alternative is marked at each use
so the same file can be moved to Postgres for the live round:

| Used here | Postgres equivalent |
|---|---|
| `SQRT(AVG(x*x) - AVG(x)*AVG(x))` (Q1) | `STDDEV_POP(x) OVER ()` |
| Pearson r from summed cross-products (Q8) | `CORR(x, y)` |
| `JULIANDAY(a) - JULIANDAY(b)` for day differences (Q7, Q11) | `(a::date - b::date)` |

Two further notes if the panel prefers Postgres:

* `CAST(... AS INTEGER)` truncates toward zero in SQLite; Postgres raises on
  casting a text date, so use `::date` explicitly.
* `SUM(COUNT(*)) OVER ()` (Q3, Q7, Q10) works in both — it is the window over an
  already-aggregated group set, which is the idiomatic way to get a share-of-
  total without a second scan or a CTE join.

## 4. Reproducibility

```
python src/clean_data.py     # raw CSV  -> data/clean/*.csv + repair_log.csv
python src/build_db.py       # clean CSV -> output/social_engine.db (schema + views)
python src/run_sql.py         # challenges.sql -> output/sql_outputs.md
```

`build_db.py` drops and rebuilds the database every run and asserts referential
integrity *before* loading, so the SQL phase cannot pass against a stale file.
