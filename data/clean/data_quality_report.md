# Social Engine -- Data Quality Report (Phase 1)

Dataset 01 restored from `node_07`. Counts below are produced by
`src/clean_data.py` and reconcile exactly with `repair_log.csv`.

## 1. Reconciliation

| stage | rows |
|---|---|
| raw intake file | 12360 |
| exact duplicate replays removed | -360 |
| empty-text rows held out | -1779 |
| **analysis table** | **10221** |

## 2. Integrity checks (all must pass)

- PASS `orphan_posts` = 0
- PASS `dup_post_id` = 0
- PASS `dup_user_id` = 0
- PASS `negative_likes_after` = 0
- PASS `out_of_window` = 0
- PASS `future_timestamps` = 0
- NOTICE `empty_text_after` = 1779
- PASS `users_never_posting` = 0

## 3. Repairs applied

| action | table | column | rows | why |
|---|---|---|---|---|
| cast comments int64 -> Int64 (nullable int) | posts | comments | 12000 | kept consistent with likes so all three engagement counts share one type; a nullable integer keeps NULL distinct from 0, which matters because 0 likes is a real signal and NULL is not |
| cast shares int64 -> Int64 (nullable int) | posts | shares | 12000 | kept consistent with likes so all three engagement counts share one type; a nullable integer keeps NULL distinct from 0, which matters because 0 likes is a real signal and NULL is not |
| cast likes float64 -> Int64 (nullable int) | posts | likes | 12000 | the crash had serialised this column as float strings ('-1205.0'); a nullable integer keeps NULL distinct from 0, which matters because 0 likes is a real signal and NULL is not |
| parse timestamp from 'iso8601' | posts | timestamp | 4805 | 3 intake formats coexisted; all normalised to tz-naive UTC datetime (event data carries no offset) |
| parse timestamp from 'epoch_seconds' | posts | timestamp | 3669 | 3 intake formats coexisted; all normalised to tz-naive UTC datetime (event data carries no offset) |
| parse timestamp from 'dayfirst_dmy' | posts | timestamp | 3526 | 3 intake formats coexisted; all normalised to tz-naive UTC datetime (event data carries no offset) |
| flag day-first dates (flag_ambiguous_date_format) | posts | timestamp | 3526 | day-first because 2113/3526 have first field >12 and 0 have second field >12 -- month-first is arithmetically impossible for that share of the block |
| textual_NULL -> real NULL | posts | likes | 1858 | ['', 'N/A', 'NA', 'NULL']… treated as missing, not as a category or as 0 |
| textual_NULL -> real NULL | posts | platform | 1846 | ['', 'N/A', 'NA', 'NULL']… treated as missing, not as a category or as 0 |
| missing engagement left NULL (no imputation) | posts | likes | 1814 | rulebook forbids fabricating data; a missing count stays missing and is excluded from aggregates rather than filled with 0 |
| unify platform spelling; missing -> 'Unspecified' | posts | platform | 1784 | rows that lost their platform at intake are bucketed as 'Unspecified' -- a transparent sentinel, NOT an invented platform; excluded from per-platform rate comparisons in SQL |
| empty text_content after full repair | posts | text_content | 1779 | blank bodies plus bodies that were only ever a missing-value token ('NULL', 'NULL&amp;') once decoded |
| empty-text rows held out of the analysis table | posts | text_content | 1779 | an empty body cannot support a content claim; retained in the held-out CSV so the count reconciles |
| textual_NULL -> real NULL | posts | text_content | 1770 | ['', 'N/A', 'NA', 'NULL']… treated as missing, not as a category or as 0 |
| parse account_created (ISO, single format) | users | account_created | 1500 | users table kept one clean format; no repair needed |
| normalise language code to lowercase | users | language | 1500 | already clean in this extract; step kept so the pipeline is idempotent if a later export drifts |
| split location -> city / country, ISO-style country names | users | location | 1500 | single-string geo breaks GROUP BY; normalising UK/USA prevents the same country appearing under two labels |
| collapse repeated spaces | posts | text_content | 680 | tokeniser left repeated spaces between words |
| strip injected HTML tags | posts | text_content | 646 | markup injected by the crashed renderer (<br>, <div>) |
| restore sign-flipped likes with abs() | posts | likes | 509 | likes is the only numeric col with negatives; /neg/ median 2388 vs pos median 2505 and /neg/ max 4987 vs pos max 5000 -> negatives are a mirrored copy of the same distribution, i.e. a sign bit flipped in the crash, not unknown data |
| drop exact duplicate row | posts | * | 360 | retry-loop replay during the outage; identical in every field, so dropping keeps the analytic record intact |
| unescape HTML entities | posts | text_content | 328 | escaped entity left by the XML writer (&amp;) |
| drop stray trailing '&' | posts | text_content | 328 | '&' left at end of body once the entity was unescaped |
| trim whitespace | posts | text_content | 306 | leading/trailing whitespace from the broken CSV writer |
| strip decoded mojibake tail mark | posts | text_content | 306 | all 316 mojibake bodies end in the same decoded 'é' and the column has zero other non-ASCII chars -> trailing mark, stripped; content is untouched elsewhere |
| repair double-encoded UTF-8 | posts | text_content | 306 | double-encoded UTF-8 reversed via a latin-1 round-trip; kept only when it yields no U+FFFD replacement char |
| missing-value word -> missing | posts | text_content | 68 | body written as a missing-value word is missing data |

## 4. Residual missingness (deliberately not imputed)

- `text_content`: 0 missing (0.00%)
- `likes`: 1532 missing (14.99%)
- `platform`: 0 missing (0.00%)

These stay NULL. Filling them would be fabricating data, which the
rulebook prohibits. SQL queries in Phase 2 exclude them per metric
instead of treating an unknown as a zero.

## 5. Post-clean schema

```
post_id: object
user_id: object
platform: string
text_content: object
timestamp: datetime64[ns]
likes: Int64
shares: Int64
comments: Int64
timestamp_format: object
flag_ambiguous_date_format: bool
post_date: datetime64[ns]
post_month: object
post_hour: int32
weekday: object
is_weekend: bool
flag_likes_sign_restored: bool
user_record_exists: bool
```

### users
```
user_id: object
location: object
language: string
account_created: datetime64[ns]
follower_count: float64
city: object
country: object
```
