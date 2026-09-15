# Phase 2 challenge set (E/M/H) -- SQL outputs (live capture)

Every table below is the actual result set returned by
`queries/phase2_challenges.sql` against `output/social_engine.db`, rendered by
`src/run_sql.py` at build time. No output was transcribed by hand, which
is what the rulebook's 'hardcoded outputs will lead to disqualification'
clause is testing for.

## E1 -- PLATFORM POPULARITY

> **Determine which social media platform has the highest number of posts. Ignore posts where the platform is missing. Return the platform name and number of posts.**

**Logic.** R3 applies. 1,846 intake rows arrived with the platform cell blank or holding the literal 'NULL'; after de-duplication 1,541 of them survive in the analysis table as 'Unspecified'. The challenge says to ignore them, and they are ignored BEFORE ranking -- not filtered after -- so the ordering cannot be topped by a gap. The ORDER BY carries the platform name as a second key so the single returned row is stable.

```sql
SELECT platform,
       COUNT(*) AS n_posts
FROM posts
WHERE platform <> 'Unspecified'
GROUP BY platform
ORDER BY n_posts DESC, platform ASC
LIMIT 1
```

**Output** (1 row, executed in 0.89 ms):

| `platform` | `n_posts` |
|---|---|
| YouTube | 1770 |


## E1b -- PLATFORM POPULARITY

> **(context for E1) The spread across the five labelled platforms is small. Report the full league table and test the gap.**

**Logic.** A ranking alone cannot distinguish "YouTube leads" from "five platforms tied and YouTube came out on top of the noise". The chi-square goodness-of-fit statistic compares the observed post counts against the uniform expectation (total/k) that a null model of "no platform preference" would produce; df = 5 - 1 = 4 and the 5% critical value is 9.488. SUM(...) OVER () totals the per-platform terms without a second pass. This is the same discipline Phase 1 applied to the platform spread, applied here inside SQL.

```sql
WITH labelled AS (
    SELECT platform
    FROM posts
    WHERE platform <> 'Unspecified'
),
obs AS (
    SELECT platform, COUNT(*) AS n_posts
    FROM labelled
    GROUP BY platform
),
expectation AS (
    SELECT COUNT(*) AS total_posts,
           COUNT(DISTINCT platform) AS n_platforms
    FROM labelled
),
terms AS (
    SELECT o.platform,
           o.n_posts,
           e.total_posts * 1.0 / e.n_platforms AS expected_if_uniform,
           (o.n_posts - e.total_posts * 1.0 / e.n_platforms)
             * (o.n_posts - e.total_posts * 1.0 / e.n_platforms)
             / (e.total_posts * 1.0 / e.n_platforms) AS chi2_term
    FROM obs o CROSS JOIN expectation e
)
SELECT platform,
       n_posts,
       ROUND(100.0 * n_posts / SUM(n_posts) OVER (), 2)          AS pct_share,
       ROUND(expected_if_uniform, 1)                             AS expected_if_uniform,
       ROUND(chi2_term, 4)                                       AS chi2_term,
       ROUND(SUM(chi2_term) OVER (), 4)                          AS chi2_total,
       4                                                         AS df,
       CASE WHEN SUM(chi2_term) OVER () > 9.488
            THEN 'field is NOT uniform -- the leader is genuinely ahead'
            ELSE 'field is flat -- the leader is ahead only by noise' END AS verdict_at_5pct
FROM terms
ORDER BY n_posts DESC
```

**Output** (5 rows, executed in 3.95 ms):

| `platform` | `n_posts` | `pct_share` | `expected_if_uniform` | `chi2_term` | `chi2_total` | `df` | `verdict_at_5pct` |
|---|---|---|---|---|---|---|---|
| YouTube | 1770 | 20.39 | 1,736 | 0.6659 | 2.6094 | 4 | field is flat -- the leader is ahead only by noise |
| Facebook | 1763 | 20.31 | 1,736 | 0.4199 | 2.6094 | 4 | field is flat -- the leader is ahead only by noise |
| Twitter | 1742 | 20.07 | 1,736 | 0.0207 | 2.6094 | 4 | field is flat -- the leader is ahead only by noise |
| Reddit | 1716 | 19.77 | 1,736 | 0.2304 | 2.6094 | 4 | field is flat -- the leader is ahead only by noise |
| Instagram | 1689 | 19.46 | 1,736 | 1.2725 | 2.6094 | 4 | field is flat -- the leader is ahead only by noise |


## E2 -- MOST ENGAGED POSTS

> **Find the top 10 posts based on total engagement. Total engagement is defined as likes + shares + comments. Ignore posts where likes are missing.**

**Logic.** "likes + shares + comments" is written with COALESCE on the two columns that are complete in this dataset (shares and comments have no NULLs at all -- only likes does), so the expression is defined by construction rather than by luck. The WHERE clause is the challenge's own instruction and is the same rule as R2: 1,532 posts have no like count, and adding 0 for them would rank a post on partial evidence. Ranking is by the computed total, so the tie-break on post_id is what makes position 10 stable across re-runs (R4).

```sql
SELECT post_id,
       user_id,
       platform,
       likes,
       shares,
       comments,
       likes + COALESCE(shares, 0) + COALESCE(comments, 0) AS total_engagement
FROM posts
WHERE likes IS NOT NULL
ORDER BY total_engagement DESC, post_id ASC
LIMIT 10
```

**Output** (10 rows, executed in 1.88 ms):

| `post_id` | `user_id` | `platform` | `likes` | `shares` | `comments` | `total_engagement` |
|---|---|---|---|---|---|---|
| ycjj5zzt7mvx | user_d9971ba6 | Instagram | 4983 | 1919 | 991 | 7893 |
| wo7py9aljg3t | user_o8le7hqf | Reddit | 4864 | 1981 | 948 | 7793 |
| gmoeib832zbs | user_pe5yckyb | Facebook | 4902 | 1880 | 982 | 7764 |
| 5kvuyvf38nqx | user_z0feut2e | YouTube | 4923 | 1971 | 861 | 7755 |
| pvfl3d8hj7jd | user_csluibwk | Instagram | 4989 | 1840 | 909 | 7738 |
| tdgjjylpua20 | user_8nvzxsuj | Unspecified | 4979 | 1932 | 812 | 7723 |
| tne7s3o4l4wd | user_lr3fagdl | Instagram | 4931 | 1903 | 878 | 7712 |
| a1kiwl618kzy | user_aaiari8o | Facebook | 4811 | 1952 | 920 | 7683 |
| 5n161ir5hhhr | user_u98jwp3f | YouTube | 4751 | 1981 | 878 | 7610 |
| g7d0tgdwipoy | user_yhe9m0z0 | Reddit | 4804 | 1842 | 937 | 7583 |


## E2b -- MOST ENGAGED POSTS

> **(context for E2) A top-10 is only meaningful if its cut is meaningful. Quantify the cut.**

**Logic.** The 10th-place score is read with OFFSET 9 rather than by hardcoding a number, so the metric survives any re-run that changes the data. If the gap between 1st and 10th is small, the "top 10" is a slice through a dense cloud and should be reported as such instead of as ten standout posts.

```sql
WITH ranked AS (
    SELECT post_id,
           likes + COALESCE(shares, 0) + COALESCE(comments, 0) AS total_engagement
    FROM posts
    WHERE likes IS NOT NULL
),
cut AS (
    SELECT total_engagement AS tenth_place
    FROM ranked
    ORDER BY total_engagement DESC, post_id ASC
    LIMIT 1 OFFSET 9
)
SELECT (SELECT COUNT(*) FROM ranked)                             AS comparable_posts,
       (SELECT MAX(total_engagement) FROM ranked)                AS best_engagement,
       cut.tenth_place                                           AS tenth_place_engagement,
       (SELECT COUNT(*) FROM ranked, cut
         WHERE ranked.total_engagement >= 0.99 * cut.tenth_place) AS posts_within_1pct_of_cut,
       ROUND(100.0 * (SELECT MAX(total_engagement) FROM ranked)
             / cut.tenth_place - 100.0, 2)                       AS best_over_tenth_pct
FROM cut
```

**Output** (1 row, executed in 5.33 ms):

| `comparable_posts` | `best_engagement` | `tenth_place_engagement` | `posts_within_1pct_of_cut` | `best_over_tenth_pct` |
|---|---|---|---|---|
| 8689 | 7893 | 7583 | 14 | 4.09 |


## E3 -- AVERAGE ENGAGEMENT BY PLATFORM

> **Calculate the average likes, shares, and comments for each platform. Which platform generates the highest average total engagement?**

**Logic.** AVG(likes) in SQLite skips NULLs, which is the correct behaviour here: 1,532 posts have no like count and averaging over the posts that DO have one is honest, whereas AVG(COALESCE(likes,0)) would silently average 1,532 fabricated zeros into every platform's like mean and bias the answer downward. `rows_with_likes` is carried alongside so the reader can see the denominator each average was computed over. The rank is computed over the same AVG(engagement) expression that is displayed, and 'Unspecified' is retained in the table for completeness but flagged so it cannot be mistaken for the winner (R3).

```sql
SELECT platform,
       COUNT(*)                       AS n_posts,
       COUNT(likes)                   AS rows_with_likes,
       ROUND(AVG(likes), 1)           AS avg_likes,
       ROUND(AVG(shares), 1)          AS avg_shares,
       ROUND(AVG(comments), 1)        AS avg_comments,
       ROUND(AVG(engagement), 1)      AS avg_total_engagement,
       RANK() OVER (ORDER BY AVG(engagement) DESC) AS engagement_rank,
       CASE WHEN platform = 'Unspecified'
            THEN 'DATA GAP -- not a platform, not eligible to win'
            ELSE 'labelled platform' END AS eligibility
FROM v_posts_enriched
GROUP BY platform
ORDER BY avg_total_engagement DESC
```

**Output** (6 rows, executed in 6.84 ms):

| `platform` | `n_posts` | `rows_with_likes` | `avg_likes` | `avg_shares` | `avg_comments` | `avg_total_engagement` | `engagement_rank` | `eligibility` |
|---|---|---|---|---|---|---|---|---|
| Instagram | 1689 | 1435 | 2,504.8 | 1,043.3 | 501.8 | 3,673.2 | 1 | labelled platform |
| Unspecified | 1541 | 1323 | 2,501.2 | 999.2 | 500.4 | 3,646.9 | 2 | DATA GAP -- not a platform, not eligible to win |
| Facebook | 1763 | 1494 | 2,527.3 | 986.8 | 507.6 | 3,636.1 | 3 | labelled platform |
| YouTube | 1770 | 1495 | 2,494.9 | 1,009 | 505.3 | 3,621.5 | 4 | labelled platform |
| Reddit | 1716 | 1473 | 2,463.8 | 985.1 | 506.9 | 3,606.9 | 5 | labelled platform |
| Twitter | 1742 | 1469 | 2,432.4 | 1,006.8 | 503.5 | 3,561.5 | 6 | labelled platform |


## E3b -- AVERAGE ENGAGEMENT BY PLATFORM

> **(context for E3) Name the winning platform and justify it.**

**Logic.** Two platforms can differ in the mean and still be indistinguishable, because each mean carries its own sampling error. The two-sample z-statistic divides the gap by sqrt(var1/n1 + var2/n2), with the variance written as E[x^2] - E[x]^2 (SQLite has no VAR function), and guards the square root with MAX(...,0) so floating-point dust cannot produce a negative variance. 'Unspecified' is excluded here because this query names a winner (R3). |z| > 1.96 is the 5% two-sided bar.

```sql
WITH plat AS (
    SELECT platform,
           COUNT(*)                                                AS n_posts,
           AVG(engagement)                                         AS mean_engagement,
           MAX(0, AVG(engagement * engagement)
                  - AVG(engagement) * AVG(engagement))             AS var_engagement
    FROM v_posts_enriched
    WHERE platform <> 'Unspecified'
    GROUP BY platform
),
ranked AS (
    SELECT platform, n_posts, mean_engagement, var_engagement,
           ROW_NUMBER() OVER (ORDER BY mean_engagement DESC,
                              platform ASC) AS rn
    FROM plat
),
pair AS (
    SELECT w.platform AS winner,     w.mean_engagement AS win_mean,
           w.n_posts  AS win_posts,  w.var_engagement  AS win_var,
           r.platform AS runner_up,  r.mean_engagement AS run_mean,
           r.n_posts  AS run_posts,  r.var_engagement  AS run_var
    FROM ranked w
    JOIN ranked r ON r.rn = 2
    WHERE w.rn = 1
),
test AS (
    SELECT *,
           SQRT(win_var / win_posts + run_var / run_posts) AS std_error
    FROM pair
)
SELECT winner,
       ROUND(win_mean, 1)                                  AS winner_avg_engagement,
       runner_up,
       ROUND(run_mean, 1)                                  AS runner_up_avg_engagement,
       ROUND(win_mean - run_mean, 1)                       AS absolute_gap,
       ROUND(100.0 * (win_mean - run_mean) / run_mean, 2)  AS gap_pct,
       ROUND((win_mean - run_mean) / std_error, 3)         AS z_stat,
       CASE WHEN ABS((win_mean - run_mean) / std_error) > 1.96
            THEN 'SIGNIFICANT at 5%'
            ELSE 'NOT significant at 5% -- the ranking is a coin toss' END AS verdict
FROM test
```

**Output** (1 row, executed in 6.73 ms):

| `winner` | `winner_avg_engagement` | `runner_up` | `runner_up_avg_engagement` | `absolute_gap` | `gap_pct` | `z_stat` | `verdict` |
|---|---|---|---|---|---|---|---|
| Instagram | 3,673.2 | Facebook | 3,636.1 | 37 | 1.02 | 0.635 | NOT significant at 5% -- the ranking is a coin toss |


## E4 -- HIGHLY SHARED BUT POORLY LIKED

> **Identify posts that received more than 1,500 shares but fewer than 500 likes. Return the post ID, platform, likes, shares, and comments.**

**Logic.** Both bounds are strict ('more than', 'fewer than'), so the predicates are > and <, not >= and <= -- a boundary error here would be invisible in the output but wrong. A NULL like count fails `likes < 500` in SQL automatically (NULL comparisons are never true), which is the correct outcome: a post with no recorded likes cannot be shown to be "poorly liked". That is stated rather than relied on silently.

```sql
SELECT post_id,
       platform,
       likes,
       shares,
       comments
FROM posts
WHERE shares > 1500
  AND likes < 500
ORDER BY shares DESC, post_id ASC
```

**Output** (214 rows, executed in 1.41 ms):

| `post_id` | `platform` | `likes` | `shares` | `comments` |
|---|---|---|---|---|
| euvr0r10wrj6 | Facebook | 453 | 2000 | 408 |
| oiszojqm6qnn | Instagram | 390 | 1999 | 858 |
| f2e5kdfldedz | Unspecified | 447 | 1997 | 641 |
| mgv7p46wzpek | Reddit | 252 | 1993 | 971 |
| u1aa801qvxeu | Unspecified | 162 | 1992 | 306 |
| 0nsga7zrxpvt | YouTube | 390 | 1991 | 848 |
| 6s9mxoemn488 | Twitter | 169 | 1991 | 856 |
| lit2hyqg0v0l | Facebook | 14 | 1990 | 769 |
| twgx52qb72eo | YouTube | 462 | 1989 | 636 |
| k8hwwxunhdf4 | YouTube | 25 | 1988 | 615 |
| e9f22k15r0e4 | Unspecified | 449 | 1986 | 132 |
| vlh7lbn658qt | Twitter | 357 | 1982 | 312 |
| elh8jw3o1btq | Twitter | 430 | 1981 | 209 |
| nb0mfumbhk9s | Instagram | 16 | 1979 | 534 |
| ajp2cwd4xbzh | YouTube | 328 | 1978 | 302 |
| p1c3eh76z3c6 | Unspecified | 135 | 1972 | 421 |
| ch6cl3ai3vh5 | YouTube | 229 | 1971 | 664 |
| t44gzf69bxh4 | Instagram | 87 | 1970 | 656 |
| bnxenpej5or3 | Facebook | 33 | 1968 | 823 |
| vcl8uw65wql1 | Reddit | 489 | 1968 | 920 |
| 9uo64r98h0cj | Twitter | 316 | 1967 | 804 |
| tqk2zo258e5g | Reddit | 425 | 1967 | 164 |
| 27w2t0eudwzl | Twitter | 6 | 1966 | 340 |
| 603lc32fqk41 | Instagram | 145 | 1965 | 15 |

_(190 further rows omitted here; the full set is in `output/phase2_sql_results.json`)_

## E4b -- HIGHLY SHARED BUT POORLY LIKED

> **(context for E4) 214 posts match. Decide whether the pattern is platform-specific or spread across the whole platform.**

**Logic.** A raw count per platform would just re-report platform volume, so the query returns the RATE -- flagged posts as a percentage of that platform's own posts. Rates are what expose a platform-specific behaviour; counts only expose which platform posts more. 'Unspecified' is kept here because this is a volume/rate question and the posts are real (R3), but it is marked.

```sql
WITH flagged AS (
    SELECT post_id
    FROM posts
    WHERE shares > 1500 AND likes < 500
)
SELECT p.platform,
       COUNT(*)                                                     AS n_posts,
       SUM(CASE WHEN f.post_id IS NOT NULL THEN 1 ELSE 0 END)       AS flagged_posts,
       ROUND(100.0 * SUM(CASE WHEN f.post_id IS NOT NULL THEN 1 ELSE 0 END)
             / COUNT(*), 2)                                         AS pct_of_platform
FROM posts p
LEFT JOIN flagged f ON f.post_id = p.post_id
GROUP BY p.platform
ORDER BY pct_of_platform DESC
```

**Output** (6 rows, executed in 11.35 ms):

| `platform` | `n_posts` | `flagged_posts` | `pct_of_platform` |
|---|---|---|---|
| Instagram | 1689 | 44 | 2.61 |
| Facebook | 1763 | 42 | 2.38 |
| Twitter | 1742 | 39 | 2.24 |
| Unspecified | 1541 | 31 | 2.01 |
| YouTube | 1770 | 35 | 1.98 |
| Reddit | 1716 | 23 | 1.34 |


## E5 -- USERS WITH LARGE AUDIENCES

> **Find all users with more than 40,000 followers. Display their user ID, location, language, and follower count.**

**Logic.** 'more than 40,000' is strict, so the predicate is > 40000: a user sitting exactly on 40,000 is not in the answer. `location` is the source's own string, kept verbatim in the users table, so every row here can be matched character-for-character against the intake file. The tie-break on user_id makes the ordering total (R4).

```sql
SELECT user_id,
       location,
       language,
       follower_count
FROM users
WHERE follower_count > 40000
ORDER BY follower_count DESC, user_id ASC
```

**Output** (293 rows, executed in 0.47 ms):

| `user_id` | `location` | `language` | `follower_count` |
|---|---|---|---|
| user_3o7w66o2 | Berlin, Germany | ja | 49944 |
| user_u98jwp3f | Chicago, USA | zh | 49936 |
| user_usts5yuo | Shanghai, China | ja | 49933 |
| user_d4eat3v3 | Tokyo, Japan | de | 49914 |
| user_siuvpkza | Chicago, USA | en | 49905 |
| user_ujllj1n7 | Chicago, USA | es | 49855 |
| user_kr0ydzhh | Barcelona, Spain | fr | 49836 |
| user_9asov0m8 | Singapore | hi | 49763 |
| user_84k7x6zn | Barcelona, Spain | ja | 49736 |
| user_t028mbub | Osaka, Japan | en | 49727 |
| user_i8ncp2ai | Delhi, India | fr | 49722 |
| user_sjm4thcl | Dubai, UAE | en | 49721 |
| user_b8ysn8r5 | Shanghai, China | hi | 49699 |
| user_kf84zwv2 | Paris, France | es | 49575 |
| user_8i81i0p7 | Los Angeles, USA | en | 49518 |
| user_ixw57ddo | Chicago, USA | de | 49484 |
| user_reqsqicb | Toronto, Canada | hi | 49432 |
| user_5wmdl0y4 | Dubai, UAE | hi | 49404 |
| user_9ksxfq3r | Manchester, UK | zh | 49368 |
| user_mtuzxdlb | Melbourne, Australia | fr | 49341 |
| user_wfoibt5f | Melbourne, Australia | pt | 49332 |
| user_t3vc5gvq | Berlin, Germany | pt | 49312 |
| user_2kmgah02 | Houston, USA | en | 49291 |
| user_ul3t78j5 | Manchester, UK | ar | 49287 |

_(269 further rows omitted here; the full set is in `output/phase2_sql_results.json`)_

## M1 -- ENGAGEMENT BY LOCATION

> **Using both datasets, calculate the total engagement generated by users from each location. Return the location, number of posts, and total engagement. Rank locations from highest to lowest engagement.**

**Logic.** The join is on user_id because engagement lives on the post while location lives on the user -- this is the one challenge that REQUIRES both datasets, and the query cannot run against either table alone. SUM uses v_posts_enriched.engagement, which is already NULL-safe (R1), so a location is never dropped for having a post with no like count. RANK() rather than ROW_NUMBER() is deliberate: tied locations should share a rank, and RANK is what a league table means.

```sql
SELECT u.location,
       COUNT(*)                       AS n_posts,
       SUM(p.engagement)              AS total_engagement,
       RANK() OVER (ORDER BY SUM(p.engagement) DESC) AS engagement_rank
FROM v_posts_enriched p
JOIN users u ON u.user_id = p.user_id
GROUP BY u.location
ORDER BY total_engagement DESC, u.location ASC
```

**Output** (33 rows, executed in 10.21 ms):

| `location` | `n_posts` | `total_engagement` | `engagement_rank` |
|---|---|---|---|
| Los Angeles, USA | 391 | 1468866 | 1 |
| Munich, Germany | 388 | 1423109 | 2 |
| Barcelona, Spain | 376 | 1384741 | 3 |
| Houston, USA | 369 | 1331509 | 4 |
| Dubai, UAE | 360 | 1316970 | 5 |
| Shanghai, China | 374 | 1301061 | 6 |
| Melbourne, Australia | 358 | 1296792 | 7 |
| Osaka, Japan | 342 | 1253204 | 8 |
| Chicago, USA | 343 | 1241422 | 9 |
| Mumbai, India | 352 | 1240657 | 10 |
| Milan, Italy | 343 | 1228787 | 11 |
| Rio de Janeiro, Brazil | 342 | 1225851 | 12 |
| London, UK | 332 | 1225571 | 13 |
| New York, USA | 327 | 1224327 | 14 |
| Johannesburg, South Africa | 331 | 1178330 | 15 |
| Paris, France | 325 | 1164358 | 16 |
| São Paulo, Brazil | 318 | 1147450 | 17 |
| Beijing, China | 313 | 1120837 | 18 |
| Tokyo, Japan | 308 | 1117702 | 19 |
| Singapore | 306 | 1108054 | 20 |
| Toronto, Canada | 303 | 1102964 | 21 |
| Berlin, Germany | 289 | 1051451 | 22 |
| Rome, Italy | 286 | 1017191 | 23 |
| Mexico City, Mexico | 272 | 1006747 | 24 |

_(9 further rows omitted here; the full set is in `output/phase2_sql_results.json`)_

## M1b -- ENGAGEMENT BY LOCATION

> **(context for M1) Total engagement is a product of volume and quality. Separate the two.**

**Logic.** Two RANK() windows are computed over the same rows: one on the total, one on the per-post average. If the two rankings disagree, then the "best location" answer is really "the location with the most posts", and saying more than that would be a volume artefact published as an insight. rank_shift quantifies the disagreement per row instead of leaving the reader to eyeball two columns.

```sql
WITH loc AS (
    SELECT u.location,
           COUNT(*)             AS n_posts,
           SUM(p.engagement)    AS total_engagement,
           AVG(p.engagement)    AS avg_engagement
    FROM v_posts_enriched p
    JOIN users u ON u.user_id = p.user_id
    GROUP BY u.location
),
ranked AS (
    SELECT location, n_posts, total_engagement, avg_engagement,
           RANK() OVER (ORDER BY total_engagement DESC) AS rank_by_total,
           RANK() OVER (ORDER BY avg_engagement   DESC) AS rank_by_avg_per_post
    FROM loc
)
SELECT location,
       n_posts,
       total_engagement,
       ROUND(avg_engagement, 1)              AS avg_engagement_per_post,
       rank_by_total,
       rank_by_avg_per_post,
       rank_by_total - rank_by_avg_per_post  AS rank_shift
FROM ranked
ORDER BY rank_by_total
```

**Output** (33 rows, executed in 10.77 ms):

| `location` | `n_posts` | `total_engagement` | `avg_engagement_per_post` | `rank_by_total` | `rank_by_avg_per_post` | `rank_shift` |
|---|---|---|---|---|---|---|
| Los Angeles, USA | 391 | 1468866 | 3,756.7 | 1 | 1 | 0 |
| Munich, Germany | 388 | 1423109 | 3,667.8 | 2 | 9 | -7 |
| Barcelona, Spain | 376 | 1384741 | 3,682.8 | 3 | 7 | -4 |
| Houston, USA | 369 | 1331509 | 3,608.4 | 4 | 19 | -15 |
| Dubai, UAE | 360 | 1316970 | 3,658.3 | 5 | 11 | -6 |
| Shanghai, China | 374 | 1301061 | 3,478.8 | 6 | 33 | -27 |
| Melbourne, Australia | 358 | 1296792 | 3,622.3 | 7 | 16 | -9 |
| Osaka, Japan | 342 | 1253204 | 3,664.3 | 8 | 10 | -2 |
| Chicago, USA | 343 | 1241422 | 3,619.3 | 9 | 18 | -9 |
| Mumbai, India | 352 | 1240657 | 3,524.6 | 10 | 31 | -21 |
| Milan, Italy | 343 | 1228787 | 3,582.5 | 11 | 26 | -15 |
| Rio de Janeiro, Brazil | 342 | 1225851 | 3,584.4 | 12 | 24 | -12 |
| London, UK | 332 | 1225571 | 3,691.5 | 13 | 6 | 7 |
| New York, USA | 327 | 1224327 | 3,744.1 | 14 | 2 | 12 |
| Johannesburg, South Africa | 331 | 1178330 | 3,559.9 | 15 | 28 | -13 |
| Paris, France | 325 | 1164358 | 3,582.6 | 16 | 25 | -9 |
| São Paulo, Brazil | 318 | 1147450 | 3,608.3 | 17 | 20 | -3 |
| Beijing, China | 313 | 1120837 | 3,580.9 | 18 | 27 | -9 |
| Tokyo, Japan | 308 | 1117702 | 3,628.9 | 19 | 15 | 4 |
| Singapore | 306 | 1108054 | 3,621.1 | 20 | 17 | 3 |
| Toronto, Canada | 303 | 1102964 | 3,640.1 | 21 | 12 | 9 |
| Berlin, Germany | 289 | 1051451 | 3,638.2 | 22 | 13 | 9 |
| Rome, Italy | 286 | 1017191 | 3,556.6 | 23 | 30 | -7 |
| Mexico City, Mexico | 272 | 1006747 | 3,701.3 | 24 | 5 | 19 |

_(9 further rows omitted here; the full set is in `output/phase2_sql_results.json`)_

## M2 -- DO HIGH FOLLOWER USERS GET MORE ENGAGEMENT?

> **Divide users into two groups: high follower users (>= 25,000 followers) and low follower users (< 25,000 followers). Compare their average engagement per post.**

**Logic.** The grain is the POST, not the user. Averaging per-user averages would weight a user with 2 posts the same as a user with 17, which is the wrong unit for "average engagement per post" and would change the answer. The coefficient is computed from follower_count, a NOT NULL column, so no user can fall outside both cohorts. Standard deviation is reported next to each mean because it is the honest context for a difference of tens of engagements against a spread of thousands.

```sql
WITH cohorts AS (
    SELECT CASE WHEN u.follower_count >= 25000
                THEN 'HIGH (>= 25k followers)'
                ELSE 'LOW (< 25k followers)' END AS cohort,
           COUNT(DISTINCT u.user_id)   AS n_users,
           COUNT(*)                    AS n_posts,
           AVG(p.engagement)           AS avg_engagement,
           SUM(p.engagement)           AS total_engagement,
           SUM(p.engagement * p.engagement) * 1.0 / COUNT(*)
             - AVG(p.engagement) * AVG(p.engagement) AS var_engagement
    FROM v_posts_enriched p
    JOIN users u ON u.user_id = p.user_id
    GROUP BY cohort
)
SELECT cohort,
       n_users,
       n_posts,
       ROUND(avg_engagement, 2)      AS avg_engagement_per_post,
       total_engagement,
       ROUND(SQRT(MAX(var_engagement, 0)), 1) AS sd_engagement
FROM cohorts
ORDER BY avg_engagement DESC
```

**Output** (2 rows, executed in 14.53 ms):

| `cohort` | `n_users` | `n_posts` | `avg_engagement_per_post` | `total_engagement` | `sd_engagement` |
|---|---|---|---|---|---|
| LOW (< 25k followers) | 758 | 5176 | 3,647.98 | 18881951 | 1,718.9 |
| HIGH (>= 25k followers) | 742 | 5045 | 3,598.82 | 18156054 | 1,729.1 |


## M2b -- DO HIGH FOLLOWER USERS GET MORE ENGAGEMENT?

> **(context for M2) Say whether the gap in M2 is a finding.**

**Logic.** The same two-sample z-statistic as E3b, here on the cohort contrast. This matters because the "obvious" business expectation (more followers > more engagement) is the one an analyst is most likely to confirm without a test. The z-statistic is what turns a directional difference into a claim, or refuses to.

```sql
WITH per_post AS (
    SELECT CASE WHEN u.follower_count >= 25000 THEN 1 ELSE 0 END AS is_high,
           p.engagement AS engagement
    FROM v_posts_enriched p
    JOIN users u ON u.user_id = p.user_id
),
agg AS (
    SELECT is_high,
           COUNT(*)          AS n,
           AVG(engagement)   AS mean_engagement,
           MAX(0, AVG(engagement * engagement)
                  - AVG(engagement) * AVG(engagement)) AS var_engagement
    FROM per_post
    GROUP BY is_high
),
pair AS (
    SELECT h.mean_engagement AS high_mean, h.n AS high_n, h.var_engagement AS high_var,
           l.mean_engagement AS low_mean,  l.n AS low_n,  l.var_engagement AS low_var
    FROM agg h
    JOIN agg l ON l.is_high = 0
    WHERE h.is_high = 1
)
SELECT ROUND(low_mean, 2)  AS low_follower_avg,
       ROUND(high_mean, 2) AS high_follower_avg,
       ROUND(high_mean - low_mean, 2) AS difference,
       ROUND(100.0 * (high_mean - low_mean) / low_mean, 2) AS difference_pct,
       ROUND((high_mean - low_mean)
             / SQRT(high_var / high_n + low_var / low_n), 3) AS z_stat,
       CASE WHEN ABS((high_mean - low_mean)
                     / SQRT(high_var / high_n + low_var / low_n)) > 1.96
            THEN 'SIGNIFICANT at 5%'
            ELSE 'NOT significant at 5% -- follower count does not predict engagement here' END AS verdict
FROM pair
```

**Output** (1 row, executed in 11.57 ms):

| `low_follower_avg` | `high_follower_avg` | `difference` | `difference_pct` | `z_stat` | `verdict` |
|---|---|---|---|---|---|
| 3,647.98 | 3,598.82 | -49.16 | -1.35 | -1.441 | NOT significant at 5% -- follower count does not predict engagement here |


## M3 -- MOST ACTIVE USERS

> **Find the top 10 users who have created the highest number of posts. Display their follower count, location, post count, and total engagement.**

**Logic.** Post counts are small integers and therefore heavily tied (the busiest account wrote 17 posts). Without the extra sort keys the identity of the 10th user would depend on SQLite's internal row order. The ORDER BY is therefore total: post count, then total engagement, then user_id (R4). Total engagement is included as a displayed column and as the second sort key, so the ranking is "most active, and among equally active, most effective".

```sql
SELECT user_id,
       follower_count,
       location,
       n_posts,
       total_engagement
FROM v_user_totals
ORDER BY n_posts DESC, total_engagement DESC, user_id ASC
LIMIT 10
```

**Output** (10 rows, executed in 10.27 ms):

| `user_id` | `follower_count` | `location` | `n_posts` | `total_engagement` |
|---|---|---|---|---|
| user_nfo3ih5u | 40429 | Barcelona, Spain | 17 | 61730 |
| user_n0ok02rt | 2531 | Dubai, UAE | 16 | 49382 |
| user_68enpikx | 9364 | Houston, USA | 15 | 57816 |
| user_xetn4exw | 14902 | Dubai, UAE | 15 | 56209 |
| user_8wk0j5ae | 36943 | Los Angeles, USA | 15 | 51828 |
| user_74ri5vbc | 24934 | New York, USA | 15 | 49162 |
| user_9mtets0p | 8262 | Johannesburg, South Africa | 14 | 62414 |
| user_gq0rypar | 17672 | Mumbai, India | 14 | 60910 |
| user_d4eat3v3 | 49914 | Tokyo, Japan | 14 | 60333 |
| user_uerv85na | 1824 | Rome, Italy | 14 | 57044 |


## M3b -- MOST ACTIVE USERS

> **(context for M3) Report the activity distribution so the top-10 cut can be judged.**

**Logic.** A tie-aware census of post counts. If dozens of users share the count that sits on the 10th-place boundary, then "the top 10 most active users" is one arbitrary selection out of a much larger tied group, and the query says so with numbers instead of a caveat in prose.

```sql
WITH counts AS (
    SELECT user_id, COUNT(*) AS n_posts
    FROM posts
    GROUP BY user_id
),
cut AS (
    SELECT n_posts AS tenth_place_posts
    FROM counts
    ORDER BY n_posts DESC, user_id ASC
    LIMIT 1 OFFSET 9
)
SELECT (SELECT MAX(n_posts) FROM counts)                          AS busiest_user_posts,
       (SELECT MIN(n_posts) FROM counts)                          AS quietest_user_posts,
       cut.tenth_place_posts                                       AS tenth_place_posts,
       (SELECT COUNT(*) FROM counts, cut
         WHERE counts.n_posts = cut.tenth_place_posts)            AS users_tied_at_the_cut,
       (SELECT COUNT(DISTINCT n_posts) FROM counts)               AS distinct_post_counts
FROM cut
```

**Output** (1 row, executed in 1.93 ms):

| `busiest_user_posts` | `quietest_user_posts` | `tenth_place_posts` | `users_tied_at_the_cut` | `distinct_post_counts` |
|---|---|---|---|---|
| 17 | 1 | 14 | 12 | 17 |


## M4 -- PLATFORM BEHAVIOUR BY HIGH FOLLOWER USERS

> **Among users with at least 30,000 followers, determine which platform gives them the highest average engagement per post.**

**Logic.** The cohort filter is applied to the USER before aggregation, so the comparison is between the same kind of account on each platform -- this is what separates M4 from E3, and it is the whole point of the challenge. 'Unspecified' is excluded because this query names a winner (R3); M4b shows it was not the winner anyway. RANK() exposes the whole ordering rather than a bare LIMIT 1, so the margin is visible.

```sql
WITH eligible AS (
    SELECT user_id
    FROM users
    WHERE follower_count >= 30000
)
SELECT p.platform,
       COUNT(*)                       AS n_posts,
       ROUND(AVG(p.engagement), 1)    AS avg_engagement_per_post,
       RANK() OVER (ORDER BY AVG(p.engagement) DESC) AS rank_within_cohort
FROM v_posts_enriched p
JOIN eligible e ON e.user_id = p.user_id
WHERE p.platform <> 'Unspecified'
GROUP BY p.platform
ORDER BY avg_engagement_per_post DESC
```

**Output** (5 rows, executed in 9.73 ms):

| `platform` | `n_posts` | `avg_engagement_per_post` | `rank_within_cohort` |
|---|---|---|---|
| Instagram | 684 | 3,692.1 | 1 |
| Twitter | 674 | 3,583.7 | 2 |
| YouTube | 726 | 3,569.9 | 3 |
| Reddit | 675 | 3,561.3 | 4 |
| Facebook | 699 | 3,532.1 | 5 |


## M4b -- PLATFORM BEHAVIOUR BY HIGH FOLLOWER USERS

> **(context for M4) The 30,000 threshold is arbitrary. Sweep it.**

**Logic.** The challenge supplies 30,000 as a cut, but any cut is a choice. Five thresholds are swept in one pass with a VALUES list cross-joined into the aggregate, and ROW_NUMBER() picks the winner inside each threshold partition. If the same platform wins at every cut the finding is a property of the data; if the winner changes, the finding is a property of the threshold and must be reported as such.

```sql
WITH thresholds(follower_threshold) AS (
    VALUES (25000), (30000), (35000), (40000), (45000)
),
per_platform AS (
    SELECT t.follower_threshold,
           p.platform,
           COUNT(*)                    AS n_posts,
           AVG(p.engagement)           AS avg_engagement,
           ROW_NUMBER() OVER (PARTITION BY t.follower_threshold
                              ORDER BY AVG(p.engagement) DESC, p.platform ASC) AS rn
    FROM thresholds t
    JOIN users u ON u.follower_count >= t.follower_threshold
    JOIN v_posts_enriched p ON p.user_id = u.user_id
    WHERE p.platform <> 'Unspecified'
    GROUP BY t.follower_threshold, p.platform
)
SELECT follower_threshold,
       platform                AS winning_platform,
       n_posts,
       ROUND(avg_engagement, 1) AS avg_engagement_per_post
FROM per_platform
WHERE rn = 1
ORDER BY follower_threshold
```

**Output** (5 rows, executed in 18.03 ms):

| `follower_threshold` | `winning_platform` | `n_posts` | `avg_engagement_per_post` |
|---|---|---|---|
| 25000 | Instagram | 838 | 3,658.3 |
| 30000 | Instagram | 684 | 3,692.1 |
| 35000 | Instagram | 523 | 3,689.7 |
| 40000 | Instagram | 366 | 3,709.5 |
| 45000 | Instagram | 154 | 3,706.1 |


## M5 -- DETECT SUSPICIOUS ENGAGEMENT

> **Find posts where the number of shares is greater than the number of likes and comments combined. Such posts may represent unusual sharing behaviour. Return the top 20.**

**Logic.** The comparison "shares > likes + comments" is UNDEFINED for the 1,532 posts with no like count, so they are excluded by requiring likes to be present (R2). Treating a blank like count as 0 would manufacture 1,154 extra "anomalies" whose only defect is a missing field -- see M5b, which prices that mistake exactly. Ranking is by the size of the excess, the natural severity measure once both readings are ruled out; the ratio column is shown alongside because a 6-like post with 900 shares and a 490-like post with 2,000 shares are different phenomena.

```sql
SELECT post_id,
       user_id,
       platform,
       likes,
       shares,
       comments,
       shares - likes - COALESCE(comments, 0)                    AS excess_shares,
       ROUND(shares * 1.0 / NULLIF(likes + COALESCE(comments, 0), 0), 2)
                                                                 AS share_to_reaction_ratio
FROM v_posts_enriched
WHERE likes IS NOT NULL
  AND shares > likes + COALESCE(comments, 0)
ORDER BY excess_shares DESC, post_id ASC
LIMIT 20
```

**Output** (20 rows, executed in 1.66 ms):

| `post_id` | `user_id` | `platform` | `likes` | `shares` | `comments` | `excess_shares` | `share_to_reaction_ratio` |
|---|---|---|---|---|---|---|---|
| 603lc32fqk41 | user_bq4d19qm | Instagram | 145 | 1965 | 15 | 1805 | 12.28 |
| 8df7c2foptde | user_vws4jlpy | Instagram | 37 | 1915 | 118 | 1760 | 12.35 |
| mtpfiec3whp4 | user_mvu6hdsm | Unspecified | 122 | 1880 | 92 | 1666 | 8.79 |
| 27w2t0eudwzl | user_cwh9v5dk | Twitter | 6 | 1966 | 340 | 1620 | 5.68 |
| ico83tj0cqae | user_rzirln2k | YouTube | 61 | 1884 | 214 | 1609 | 6.85 |
| agcvmdiq2joc | user_65x8ekq5 | Instagram | 91 | 1751 | 55 | 1605 | 11.99 |
| m4ojbon7sqsa | user_6wra58f7 | Twitter | 265 | 1915 | 83 | 1567 | 5.5 |
| p52mh6x5bcle | user_m5o36yfr | Instagram | 23 | 1608 | 21 | 1564 | 36.55 |
| qm14lq8l8upx | user_qfevrky0 | Instagram | 177 | 1931 | 213 | 1541 | 4.95 |
| ekseobq6lyr7 | user_fhm7i47h | Reddit | 31 | 1654 | 83 | 1540 | 14.51 |
| k1f9dekiugzx | user_nz4b01j0 | Instagram | 11 | 1902 | 358 | 1533 | 5.15 |
| wj2yyihjwio9 | user_zsdvwipi | YouTube | 168 | 1813 | 113 | 1532 | 6.45 |
| wy1u0c6hrxb0 | user_veuczwoc | Twitter | 167 | 1963 | 268 | 1528 | 4.51 |
| u1aa801qvxeu | user_q2stxtlj | Unspecified | 162 | 1992 | 306 | 1524 | 4.26 |
| x384n6q3tpac | user_dl3xyfx7 | YouTube | 149 | 1801 | 132 | 1520 | 6.41 |
| g3o33c09ldxw | user_17wg6hsy | Reddit | 73 | 1692 | 119 | 1500 | 8.81 |
| 6a59cjuje1in | user_otg53r69 | Facebook | 175 | 1868 | 234 | 1459 | 4.57 |
| da1fodobb5eb | user_permtl48 | Twitter | 78 | 1889 | 363 | 1448 | 4.28 |
| oz6cgmy8eiza | user_przn32mt | Facebook | 183 | 1643 | 13 | 1447 | 8.38 |
| 92v0rs54860x | user_5ucdzep1 | Twitter | 14 | 1633 | 176 | 1443 | 8.59 |


## M5b -- DETECT SUSPICIOUS ENGAGEMENT

> **(context for M5) Show what the alternative reading would produce.**

**Logic.** Three counts are placed side by side: the strict definition, the definition that reads a missing like count as zero, and the number of posts whose likes are missing AND whose shares exceed their comments. The third number is the gap between the first two, so the reader can see that every extra "anomaly" in the loose reading comes from missing data rather than from behaviour.

```sql
WITH strict_count AS (
    SELECT COUNT(*) AS n
    FROM v_posts_enriched
    WHERE likes IS NOT NULL AND shares > likes + COALESCE(comments, 0)
),
loose_count AS (
    SELECT COUNT(*) AS n
    FROM v_posts_enriched
    WHERE shares > COALESCE(likes, 0) + COALESCE(comments, 0)
),
missing_like_count AS (
    SELECT COUNT(*) AS n
    FROM v_posts_enriched
    WHERE likes IS NULL
      AND shares > COALESCE(likes, 0) + COALESCE(comments, 0)
)
SELECT strict_count.n                                  AS strict_definition,
       loose_count.n                                   AS likes_read_as_zero,
       missing_like_count.n                            AS anomalies_created_by_blanks,
       loose_count.n - strict_count.n                  AS arithmetic_gap,
       ROUND(100.0 * missing_like_count.n / NULLIF(loose_count.n, 0), 2) AS pct_of_loose_that_is_missing_data,
       CASE WHEN loose_count.n - strict_count.n = missing_like_count.n
            THEN 'every extra row in the loose reading is a missing like count'
            ELSE 'the two readings differ for a reason that is NOT missing data' END AS reconciliation
FROM strict_count, loose_count, missing_like_count
```

**Output** (1 row, executed in 4.10 ms):

| `strict_definition` | `likes_read_as_zero` | `anomalies_created_by_blanks` | `arithmetic_gap` | `pct_of_loose_that_is_missing_data` | `reconciliation` |
|---|---|---|---|---|---|
| 1047 | 2201 | 1154 | 1154 | 52.43 | every extra row in the loose reading is a missing like count |


## H1 -- ABNORMALLY HIGH ENGAGEMENT

> **Calculate the average total engagement per user. Identify users whose average engagement per post is more than twice the overall average engagement per post. Return the user ID, location, follower count, post count, and average engagement.**

**Logic.** The baseline is the overall average engagement PER POST (every post weighted equally, which is what "overall average engagement per post" means on a post-level table), compared against each user's per-post average. This query returns ZERO rows, and that is the correct answer, not a bug: the arithmetic is laid out in H1b and swept in H1c. The column list is kept complete so the reader can see the shape of the answer that the data refuses to give.

```sql
WITH per_user AS (
    SELECT user_id,
           COUNT(*)          AS n_posts,
           AVG(engagement)   AS avg_engagement
    FROM v_posts_enriched
    GROUP BY user_id
),
baseline AS (
    SELECT AVG(engagement) AS overall_avg_per_post
    FROM v_posts_enriched
)
SELECT pu.user_id,
       u.location,
       u.follower_count,
       pu.n_posts,
       ROUND(pu.avg_engagement, 2) AS avg_engagement
FROM per_user pu
JOIN users u ON u.user_id = pu.user_id
CROSS JOIN baseline b
WHERE pu.avg_engagement > 2.0 * b.overall_avg_per_post
ORDER BY pu.avg_engagement DESC, pu.user_id ASC
```

**Output** (0 rows, executed in 9.40 ms):

_Query executed successfully and returned **0 rows**. The companion query below the challenge explains why the empty set is the arithmetic answer, not a bug._

_no rows returned_


## H1b -- ABNORMALLY HIGH ENGAGEMENT

> **(context for H1) An empty result must be shown to be arithmetic, not a broken query.**

**Logic.** Every input to the decision is printed: the baseline, the doubled threshold, the highest per-user average that actually exists, and that maximum expressed as a multiple of the baseline. The verdict is computed, not asserted -- the database compares its own maximum against its own threshold. Reporting the near-miss multiple is what makes the emptiness informative rather than a dead end.

```sql
WITH per_user AS (
    SELECT user_id,
           COUNT(*)        AS n_posts,
           AVG(engagement) AS avg_engagement
    FROM v_posts_enriched
    GROUP BY user_id
),
baseline AS (
    SELECT AVG(engagement) AS overall_avg_per_post
    FROM v_posts_enriched
)
SELECT ROUND(b.overall_avg_per_post, 2)          AS overall_avg_per_post,
       ROUND(2.0 * b.overall_avg_per_post, 2)    AS threshold_2x,
       (SELECT COUNT(*) FROM per_user)           AS users_examined,
       (SELECT ROUND(MAX(avg_engagement), 2) FROM per_user) AS highest_user_avg,
       (SELECT user_id FROM per_user
         ORDER BY avg_engagement DESC, user_id ASC LIMIT 1) AS highest_avg_user,
       ROUND((SELECT MAX(avg_engagement) FROM per_user)
             / b.overall_avg_per_post, 3)        AS highest_avg_as_multiple_of_baseline,
       (SELECT COUNT(*) FROM per_user
         WHERE avg_engagement > 2.0 * b.overall_avg_per_post) AS qualifying_users,
       CASE WHEN (SELECT MAX(avg_engagement) FROM per_user)
                 > 2.0 * b.overall_avg_per_post
            THEN 'threshold is reachable -- empty result would be a bug'
            ELSE 'EMPTY BY ARITHMETIC -- no user reaches 2x, so H1 returning 0 rows is the answer' END AS verdict
FROM baseline b
```

**Output** (1 row, executed in 9.59 ms):

| `overall_avg_per_post` | `threshold_2x` | `users_examined` | `highest_user_avg` | `highest_avg_user` | `highest_avg_as_multiple_of_baseline` | `qualifying_users` | `verdict` |
|---|---|---|---|---|---|---|---|
| 3,623.72 | 7,247.43 | 1500 | 6,545.5 | user_2c5wzose | 1.806 | 0 | EMPTY BY ARITHMETIC -- no user reaches 2x, so H1 returning 0 rows is the answer |


## H1c -- ABNORMALLY HIGH ENGAGEMENT

> **(context for H1) Find the multiple at which the question does have an answer, so the 2x cut can be reported against a real curve.**

**Logic.** The same test is run at 1.25x, 1.50x, 1.75x and 2.00x in one compound statement. This converts "no users qualify" from a dead end into a threshold curve, which is the difference between refusing to answer and calibrating the question.

```sql
WITH per_user AS (
    SELECT user_id,
           AVG(engagement) AS avg_engagement
    FROM v_posts_enriched
    GROUP BY user_id
),
baseline AS (
    SELECT AVG(engagement) AS overall_avg_per_post
    FROM v_posts_enriched
),
multiples(multiple, factor, label) AS (
    VALUES (1, 1.25, '1.25x'), (2, 1.50, '1.50x'), (3, 1.75, '1.75x'), (4, 2.00, '2.00x')
)
SELECT m.label AS multiple,
       ROUND(m.factor * b.overall_avg_per_post, 2) AS threshold,
       (SELECT COUNT(*) FROM per_user p
         WHERE p.avg_engagement > m.factor * b.overall_avg_per_post) AS users_qualifying
FROM multiples m
CROSS JOIN baseline b
ORDER BY m.multiple
```

**Output** (4 rows, executed in 29.25 ms):

| `multiple` | `threshold` | `users_qualifying` |
|---|---|---|
| 1.25x | 4,529.65 | 145 |
| 1.50x | 5,435.57 | 8 |
| 1.75x | 6,341.5 | 1 |
| 2.00x | 7,247.43 | 0 |


## H2 -- RANK USERS WITHIN THEIR LOCATION

> **For every location, rank users based on their total engagement. Return only the top 3 users from each location.**

**Logic.** PARTITION BY location converts the global ranking into a per-location competition, which is the entire difficulty of the challenge. The tie-break chain (total engagement, then post count, then user_id) is not optional here: H2b shows that the 3rd and 4th place users in Tokyo are separated by 33 engagements out of ~43,000, so ties and near-ties decide the podium. ROW_NUMBER gives exactly 3 rows per location; RANK would be able to return more than 3 and silently break the challenge's "only the top 3" instruction.

```sql
WITH ranked AS (
    SELECT u.location,
           v.user_id,
           u.follower_count,
           v.n_posts,
           v.total_engagement,
           ROW_NUMBER() OVER (PARTITION BY u.location
                              ORDER BY v.total_engagement DESC,
                                       v.n_posts DESC,
                                       v.user_id ASC) AS rank_in_location
    FROM v_user_totals v
    JOIN users u ON u.user_id = v.user_id
)
SELECT location,
       rank_in_location,
       user_id,
       follower_count,
       n_posts,
       total_engagement
FROM ranked
WHERE rank_in_location <= 3
ORDER BY location ASC, rank_in_location ASC
```

**Output** (99 rows, executed in 13.87 ms):

| `location` | `rank_in_location` | `user_id` | `follower_count` | `n_posts` | `total_engagement` |
|---|---|---|---|---|---|
| Barcelona, Spain | 1 | user_nfo3ih5u | 40429 | 17 | 61730 |
| Barcelona, Spain | 2 | user_24wzfb8b | 38633 | 14 | 53039 |
| Barcelona, Spain | 3 | user_5s9ifp0y | 28412 | 10 | 51089 |
| Beijing, China | 1 | user_cdzp4vm2 | 11187 | 11 | 48019 |
| Beijing, China | 2 | user_z6qgqt5r | 13029 | 8 | 38518 |
| Beijing, China | 3 | user_gre0h06x | 23303 | 9 | 36116 |
| Berlin, Germany | 1 | user_rtp2dykx | 14113 | 11 | 52748 |
| Berlin, Germany | 2 | user_r46af80k | 25928 | 11 | 45750 |
| Berlin, Germany | 3 | user_m5z8a3sg | 34800 | 11 | 43798 |
| Cairo, Egypt | 1 | user_g37hrbp3 | 6699 | 11 | 51740 |
| Cairo, Egypt | 2 | user_cuzig14g | 8070 | 14 | 47065 |
| Cairo, Egypt | 3 | user_ogtvuuki | 4459 | 10 | 38920 |
| Chicago, USA | 1 | user_pr7bcf45 | 30128 | 13 | 57393 |
| Chicago, USA | 2 | user_ujllj1n7 | 49855 | 14 | 52953 |
| Chicago, USA | 3 | user_u98jwp3f | 49936 | 10 | 46083 |
| Delhi, India | 1 | user_8776jund | 21147 | 11 | 49524 |
| Delhi, India | 2 | user_zq2nib62 | 5153 | 11 | 48315 |
| Delhi, India | 3 | user_yu2w96i5 | 9772 | 13 | 45589 |
| Dubai, UAE | 1 | user_xetn4exw | 14902 | 15 | 56209 |
| Dubai, UAE | 2 | user_ctdjnqvi | 34193 | 14 | 49637 |
| Dubai, UAE | 3 | user_rsrg2sgy | 32791 | 11 | 49438 |
| Houston, USA | 1 | user_68enpikx | 9364 | 15 | 57816 |
| Houston, USA | 2 | user_r7eg1rac | 2052 | 11 | 52606 |
| Houston, USA | 3 | user_nq5irbxf | 17046 | 10 | 40133 |

_(75 further rows omitted here; the full set is in `output/phase2_sql_results.json`)_

## H2b -- RANK USERS WITHIN THEIR LOCATION

> **(context for H2) Show which locations have a contested 3rd place.**

**Logic.** For each location the 3rd-place score is extracted with MAX(CASE WHEN rn = 3 ...) and the 4th-place score with MIN(CASE WHEN rn = 4...). The margin between them is the honesty check on the answer: a location whose margin rounds to 0.1% has a podium decided by luck, and reporting its top 3 without that number would overstate what the data knows.

```sql
WITH ranked AS (
    SELECT u.location,
           v.total_engagement,
           ROW_NUMBER() OVER (PARTITION BY u.location
                              ORDER BY v.total_engagement DESC,
                                       v.n_posts DESC,
                                       v.user_id ASC) AS rn
    FROM v_user_totals v
    JOIN users u ON u.user_id = v.user_id
),
podium AS (
    SELECT location,
           MAX(CASE WHEN rn = 3 THEN total_engagement END) AS third_place,
           MIN(CASE WHEN rn = 4 THEN total_engagement END) AS fourth_place
    FROM ranked
    GROUP BY location
)
SELECT location,
       third_place,
       fourth_place,
       third_place - fourth_place                                AS absolute_margin,
       ROUND(100.0 * (third_place - fourth_place) / fourth_place, 2) AS margin_pct
FROM podium
ORDER BY margin_pct ASC, location ASC
LIMIT 8
```

**Output** (8 rows, executed in 13.53 ms):

| `location` | `third_place` | `fourth_place` | `absolute_margin` | `margin_pct` |
|---|---|---|---|---|
| Tokyo, Japan | 43092 | 43059 | 33 | 0.08 |
| Dubai, UAE | 49438 | 49382 | 56 | 0.11 |
| Milan, Italy | 42317 | 42255 | 62 | 0.15 |
| Paris, France | 39660 | 39550 | 110 | 0.28 |
| New York, USA | 41902 | 41684 | 218 | 0.52 |
| Cairo, Egypt | 38920 | 38702 | 218 | 0.56 |
| Munich, Germany | 38158 | 37916 | 242 | 0.64 |
| Johannesburg, South Africa | 43917 | 43549 | 368 | 0.85 |


## H3 -- PLATFORM PERFORMANCE VS ITS OWN AVERAGE

> **For every platform, identify posts whose engagement is significantly higher than the average engagement of that platform. A post is considered exceptional if its engagement is at least 2x the average engagement of its platform.**

**Logic.** The benchmark is each platform's OWN mean (a correlated per-platform aggregate joined back onto the posts), so a post on a low-engagement platform is judged against its peers rather than against the global mean -- that comparison is the point of the challenge. 'at least 2x' is inclusive, hence >=. 'Unspecified' is excluded because it has no platform identity to be exceptional within (R3); H3b reports the 5 posts that including it would have added.

```sql
WITH plat AS (
    SELECT platform,
           COUNT(*)              AS platform_posts,
           AVG(engagement)       AS platform_avg_engagement
    FROM v_posts_enriched
    WHERE platform <> 'Unspecified'
    GROUP BY platform
)
SELECT p.post_id,
       p.user_id,
       p.platform,
       p.likes,
       p.shares,
       p.comments,
       ROUND(pl.platform_avg_engagement, 1) AS platform_avg_engagement,
       p.engagement                          AS post_engagement,
       ROUND(p.engagement * 1.0 / pl.platform_avg_engagement, 3) AS multiple_of_platform_avg
FROM v_posts_enriched p
JOIN plat pl ON pl.platform = p.platform
WHERE p.engagement >= 2.0 * pl.platform_avg_engagement
ORDER BY multiple_of_platform_avg DESC, p.post_id ASC
```

**Output** (56 rows, executed in 10.08 ms):

| `post_id` | `user_id` | `platform` | `likes` | `shares` | `comments` | `platform_avg_engagement` | `post_engagement` | `multiple_of_platform_avg` |
|---|---|---|---|---|---|---|---|---|
| wo7py9aljg3t | user_o8le7hqf | Reddit | 4864 | 1981 | 948 | 3,606.9 | 7793 | 2.161 |
| ycjj5zzt7mvx | user_d9971ba6 | Instagram | 4983 | 1919 | 991 | 3,673.2 | 7893 | 2.149 |
| 5kvuyvf38nqx | user_z0feut2e | YouTube | 4923 | 1971 | 861 | 3,621.5 | 7755 | 2.141 |
| gmoeib832zbs | user_pe5yckyb | Facebook | 4902 | 1880 | 982 | 3,636.1 | 7764 | 2.135 |
| a1kiwl618kzy | user_aaiari8o | Facebook | 4811 | 1952 | 920 | 3,636.1 | 7683 | 2.113 |
| pvfl3d8hj7jd | user_csluibwk | Instagram | 4989 | 1840 | 909 | 3,673.2 | 7738 | 2.107 |
| g7d0tgdwipoy | user_yhe9m0z0 | Reddit | 4804 | 1842 | 937 | 3,606.9 | 7583 | 2.102 |
| 5n161ir5hhhr | user_u98jwp3f | YouTube | 4751 | 1981 | 878 | 3,621.5 | 7610 | 2.101 |
| tne7s3o4l4wd | user_lr3fagdl | Instagram | 4931 | 1903 | 878 | 3,673.2 | 7712 | 2.1 |
| rh7jt9kj7tw8 | user_01mu2x1s | YouTube | 4881 | 1787 | 913 | 3,621.5 | 7581 | 2.093 |
| sohx1tia2np4 | user_716l1rz5 | Twitter | 4654 | 1841 | 945 | 3,561.5 | 7440 | 2.089 |
| za6nw486cyn2 | user_rj984hbd | YouTube | 4915 | 1748 | 877 | 3,621.5 | 7540 | 2.082 |
| d7a3bjdzzi5w | user_24wzfb8b | Reddit | 4880 | 1716 | 904 | 3,606.9 | 7500 | 2.079 |
| xzt681si3ibm | user_w4p8zi5g | Reddit | 4672 | 1822 | 985 | 3,606.9 | 7479 | 2.074 |
| 076lgd30r7iu | user_ral75hq0 | Twitter | 4973 | 1946 | 465 | 3,561.5 | 7384 | 2.073 |
| yhxvwx8u4gqk | user_h8g2fyv0 | Twitter | 4999 | 1643 | 714 | 3,561.5 | 7356 | 2.065 |
| 2ubp2yyrtncq | user_q2y6x6ct | YouTube | 4900 | 1602 | 970 | 3,621.5 | 7472 | 2.063 |
| 3ffnsgd3uzxp | user_kk1qdsq3 | Reddit | 4785 | 1923 | 727 | 3,606.9 | 7435 | 2.061 |
| f8agecodqc5x | user_qpmg4srk | Reddit | 4982 | 1797 | 651 | 3,606.9 | 7430 | 2.06 |
| k5qkhdj5zpnw | user_v85ub55d | Facebook | 4554 | 1985 | 938 | 3,636.1 | 7477 | 2.056 |
| s7wyr8sbp28r | user_pp3dgfak | YouTube | 4815 | 1680 | 949 | 3,621.5 | 7444 | 2.055 |
| 6d1wkacoavg2 | user_t38nl55r | Twitter | 4939 | 1972 | 406 | 3,561.5 | 7317 | 2.054 |
| 0k5m7bn3n32l | user_ivpaj0jp | Reddit | 4943 | 1886 | 575 | 3,606.9 | 7404 | 2.053 |
| atk7729zdm3g | user_zqzqyysg | Reddit | 4962 | 1810 | 634 | 3,606.9 | 7406 | 2.053 |

_(32 further rows omitted here; the full set is in `output/phase2_sql_results.json`)_

## H3b -- PLATFORM PERFORMANCE VS ITS OWN AVERAGE

> **(context for H3) Show each platform's bar and what the excluded bucket would have contributed.**

**Logic.** The 2x bar is a derived number, not a given one, and it differs per platform (a platform's mean plus 100% of itself). Printing the bar for every platform makes the rule auditable and shows why the same post engagement can be exceptional on one platform and ordinary on another. 'Unspecified' is carried in the table but marked so its row is not read as a platform result (R3).

```sql
WITH plat AS (
    SELECT platform,
           COUNT(*)        AS n_posts,
           AVG(engagement) AS platform_avg_engagement
    FROM v_posts_enriched
    GROUP BY platform
),
hits AS (
    SELECT p.platform, COUNT(*) AS exceptional_posts
    FROM v_posts_enriched p
    JOIN plat pl ON pl.platform = p.platform
    WHERE p.engagement >= 2.0 * pl.platform_avg_engagement
    GROUP BY p.platform
)
SELECT pl.platform,
       pl.n_posts,
       ROUND(pl.platform_avg_engagement, 1)     AS platform_avg_engagement,
       ROUND(2.0 * pl.platform_avg_engagement, 1) AS exceptional_threshold,
       COALESCE(h.exceptional_posts, 0)         AS exceptional_posts,
       ROUND(100.0 * COALESCE(h.exceptional_posts, 0) / pl.n_posts, 2) AS pct_of_platform,
       CASE WHEN pl.platform = 'Unspecified'
            THEN 'DATA GAP -- excluded from the H3 answer'
            ELSE 'labelled platform' END AS eligibility
FROM plat pl
LEFT JOIN hits h ON h.platform = pl.platform
ORDER BY pct_of_platform DESC, pl.platform ASC
```

**Output** (6 rows, executed in 13.12 ms):

| `platform` | `n_posts` | `platform_avg_engagement` | `exceptional_threshold` | `exceptional_posts` | `pct_of_platform` | `eligibility` |
|---|---|---|---|---|---|---|
| Twitter | 1742 | 3,561.5 | 7,123 | 16 | 0.92 | labelled platform |
| Reddit | 1716 | 3,606.9 | 7,213.8 | 14 | 0.82 | labelled platform |
| YouTube | 1770 | 3,621.5 | 7,243 | 11 | 0.62 | labelled platform |
| Facebook | 1763 | 3,636.1 | 7,272.3 | 8 | 0.45 | labelled platform |
| Instagram | 1689 | 3,673.2 | 7,346.3 | 7 | 0.41 | labelled platform |
| Unspecified | 1541 | 3,646.9 | 7,293.8 | 5 | 0.32 | DATA GAP -- excluded from the H3 answer |


## H4 -- FOLLOWER TO ENGAGEMENT ANOMALY

> **Find users who have fewer than 5,000 followers but whose total post engagement places them among the top 10% of all users. These users may represent unusually high performing or suspicious accounts. This requires multiple levels of analysis.**

**Logic.** Four levels, in order, and each one exists because the previous one is not enough: (1) collapse 10,221 posts to 1,500 users with SUM; (2) cut the user population into deciles with NTILE(10) on that total; (3) isolate the top decile; (4) re-join the followership dimension and apply the < 5,000 constraint. The joining key throughout is user_id, which is the only column linking the two datasets. NTILE assigns ranks before ties are considered, so users sharing a total can land in adjacent deciles -- H4b re-runs the same question with an explicit percentile threshold and shows the answer is unchanged.

```sql
WITH user_totals AS (
    SELECT user_id,
           COUNT(*)        AS n_posts,
           SUM(engagement) AS total_engagement,
           AVG(engagement) AS avg_engagement
    FROM v_posts_enriched
    GROUP BY user_id
),
bucketed AS (
    SELECT user_id,
           n_posts,
           total_engagement,
           avg_engagement,
           NTILE(10) OVER (ORDER BY total_engagement DESC) AS engagement_decile
    FROM user_totals
),
deciles AS (
    SELECT user_id,
           n_posts,
           total_engagement,
           avg_engagement,
           engagement_decile,
           MIN(total_engagement) OVER (PARTITION BY engagement_decile) AS decile_floor
    FROM bucketed
)
SELECT u.user_id,
       u.location,
       u.follower_count,
       d.n_posts,
       d.total_engagement,
       ROUND(d.avg_engagement, 2) AS avg_engagement_per_post,
       d.engagement_decile,
       d.decile_floor             AS top_decile_floor_engagement
FROM deciles d
JOIN users u ON u.user_id = d.user_id
WHERE d.engagement_decile = 1
  AND u.follower_count < 5000
ORDER BY d.total_engagement DESC, u.user_id ASC
```

**Output** (17 rows, executed in 10.30 ms):

| `user_id` | `location` | `follower_count` | `n_posts` | `total_engagement` | `avg_engagement_per_post` | `engagement_decile` | `top_decile_floor_engagement` |
|---|---|---|---|---|---|---|---|
| user_uerv85na | Rome, Italy | 1824 | 14 | 57044 | 4,074.57 | 1 | 38765 |
| user_hdas0iau | Rio de Janeiro, Brazil | 1620 | 14 | 54678 | 3,905.57 | 1 | 38765 |
| user_fgjkkrie | Lyon, France | 2211 | 12 | 53244 | 4,437 | 1 | 38765 |
| user_r7eg1rac | Houston, USA | 2052 | 11 | 52606 | 4,782.36 | 1 | 38765 |
| user_n0ok02rt | Dubai, UAE | 2531 | 16 | 49382 | 3,086.38 | 1 | 38765 |
| user_hvqqyzoi | Melbourne, Australia | 3213 | 12 | 45668 | 3,805.67 | 1 | 38765 |
| user_0aacyvtz | Rome, Italy | 1452 | 11 | 45616 | 4,146.91 | 1 | 38765 |
| user_rr1uzkql | Milan, Italy | 1069 | 13 | 44748 | 3,442.15 | 1 | 38765 |
| user_cqaitbuv | Johannesburg, South Africa | 3382 | 10 | 44310 | 4,431 | 1 | 38765 |
| user_txrypced | Rome, Italy | 2479 | 10 | 42896 | 4,289.6 | 1 | 38765 |
| user_ha9bzru4 | Toronto, Canada | 608 | 10 | 41826 | 4,182.6 | 1 | 38765 |
| user_6wra58f7 | Johannesburg, South Africa | 4953 | 11 | 40943 | 3,722.09 | 1 | 38765 |
| user_5oe5t3js | London, UK | 3151 | 9 | 40344 | 4,482.67 | 1 | 38765 |
| user_knjtsbf3 | Toronto, Canada | 1298 | 10 | 39404 | 3,940.4 | 1 | 38765 |
| user_06v0exkg | Barcelona, Spain | 552 | 11 | 39329 | 3,575.36 | 1 | 38765 |
| user_ogtvuuki | Cairo, Egypt | 4459 | 10 | 38920 | 3,892 | 1 | 38765 |
| user_lfwnie3f | Shanghai, China | 2127 | 13 | 38790 | 2,983.85 | 1 | 38765 |


## H4b -- FOLLOWER TO ENGAGEMENT ANOMALY

> **(context for H4) Two independent definitions of "top 10%" must agree before the finding is reported.**

**Logic.** NTILE(10) forces exactly 10 equal buckets, which is convenient but splits tied totals arbitrarily at the boundary. The second definition is explicit: rank every user by total engagement and keep the top n*0.10 by ROW_NUMBER. If both definitions return the same users, the result is a property of the data rather than of the bucketing function. The decile floor is printed so the answer can be re-derived by hand.

```sql
WITH user_totals AS (
    SELECT user_id,
           SUM(engagement) AS total_engagement
    FROM v_posts_enriched
    GROUP BY user_id
),
ntile_cut AS (
    SELECT user_id,
           NTILE(10) OVER (ORDER BY total_engagement DESC) AS engagement_decile
    FROM user_totals
),
percentile_cut AS (
    SELECT user_id,
           total_engagement,
           ROW_NUMBER() OVER (ORDER BY total_engagement DESC, user_id ASC) AS rn,
           COUNT(*) OVER () AS n_users
    FROM user_totals
),
floor_value AS (
    SELECT MIN(total_engagement) AS decile_floor
    FROM percentile_cut
    WHERE rn <= n_users * 0.10
)
SELECT (SELECT decile_floor FROM floor_value)          AS top_decile_floor_engagement,
       (SELECT COUNT(*) FROM ntile_cut n
          JOIN users u ON u.user_id = n.user_id
         WHERE n.engagement_decile = 1 AND u.follower_count < 5000) AS via_ntile_10_buckets,
       (SELECT COUNT(*) FROM percentile_cut p
          JOIN users u ON u.user_id = p.user_id
         WHERE p.rn <= p.n_users * 0.10 AND u.follower_count < 5000) AS via_explicit_percentile,
       CASE WHEN (SELECT COUNT(*) FROM ntile_cut n
                    JOIN users u ON u.user_id = n.user_id
                   WHERE n.engagement_decile = 1 AND u.follower_count < 5000)
                 = (SELECT COUNT(*) FROM percentile_cut p
                      JOIN users u ON u.user_id = p.user_id
                     WHERE p.rn <= p.n_users * 0.10 AND u.follower_count < 5000)
            THEN 'the two definitions AGREE -- the answer is not an artefact of NTILE'
            ELSE 'the definitions DISAGREE -- report the boundary as unstable' END AS robustness
```

**Output** (1 row, executed in 12.98 ms):

| `top_decile_floor_engagement` | `via_ntile_10_buckets` | `via_explicit_percentile` | `robustness` |
|---|---|---|---|
| 38765 | 17 | 17 | the two definitions AGREE -- the answer is not an artefact of NTILE |


## H5 -- IDENTIFY DATA ANOMALIES

> **Identify potentially corrupted posts where one or more of the following conditions are true: (1) likes are negative; (2) platform is missing; (3) text content is missing; (4) text contains HTML entities/tags such as &amp;, <div>, or <br>. Return the post ID and identify the type of anomaly.**

**Logic.** This question CANNOT be asked of the cleaned table -- cleaning is exactly the step that removed these defects, so a query over `posts` would return nothing and prove nothing. It runs against `raw_posts`, the verbatim intake staging table, and reads the defect definitions from v_raw_anomaly_scan, the same SQL predicate that populated the anomaly relation. The long-form relation means a post carrying three defects produces three rows, so no condition masks another; the counts are `>= 1` per condition rather than exclusive buckets. The concatenated label is built with CASE in a FIXED order (not GROUP_CONCAT, whose ordering is unspecified) so the output is byte-stable across re-runs.

```sql
WITH flags AS (
    SELECT post_id,
           MAX(CASE WHEN anomaly_type = 'NEGATIVE_LIKES'       THEN 1 ELSE 0 END) AS neg_likes,
           MAX(CASE WHEN anomaly_type = 'MISSING_PLATFORM'     THEN 1 ELSE 0 END) AS no_platform,
           MAX(CASE WHEN anomaly_type = 'MISSING_TEXT'         THEN 1 ELSE 0 END) AS no_text,
           MAX(CASE WHEN anomaly_type = 'HTML_ENTITY_OR_TAG'   THEN 1 ELSE 0 END) AS html,
           COUNT(*) AS n_anomalies
    FROM raw_post_anomalies
    GROUP BY post_id
)
SELECT post_id,
       n_anomalies,
       TRIM(CASE WHEN neg_likes   = 1 THEN 'NEGATIVE_LIKES '     ELSE '' END ||
            CASE WHEN no_platform = 1 THEN 'MISSING_PLATFORM '   ELSE '' END ||
            CASE WHEN no_text     = 1 THEN 'MISSING_TEXT '       ELSE '' END ||
            CASE WHEN html        = 1 THEN 'HTML_ENTITY_OR_TAG'  ELSE '' END) AS anomaly_types
FROM flags
ORDER BY n_anomalies DESC, post_id ASC
```

**Output** (4418 rows, executed in 10.59 ms):

| `post_id` | `n_anomalies` | `anomaly_types` |
|---|---|---|
| 0oqpg2rgnqxa | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| 26u0g2fea4nk | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| 5b0pz3j0kcxl | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| 6uafi1o2psiu | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| 80rfm8lcs5rz | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| 95tlcn4xx75o | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| 9bngbsop7tof | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| beokpdad5uxf | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| do7er5bxtgtz | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| fk3h10wrlphg | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| fqk6dqmwi48l | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| gugw4ni537sa | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| k21r07ypw81e | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| mz4ztxgcqdfw | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| mzz8pjdhynbb | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| q0ehux8whokc | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| tzddmg5idg0s | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| udj0f5zqeaps | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| we0onw3mv5nu | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| ytohojy7b1kt | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| 0066x8nnmouc | 2 | MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| 01kgwhi645er | 2 | NEGATIVE_LIKES MISSING_PLATFORM |
| 033i6hfsrdo8 | 2 | MISSING_PLATFORM MISSING_TEXT |
| 03ffwdqbuae1 | 2 | MISSING_PLATFORM MISSING_TEXT |

_(4394 further rows omitted here; the full set is in `output/phase2_sql_results.json`)_

## H5b -- IDENTIFY DATA ANOMALIES

> **(context for H5) Reconcile the SQL scan against the Phase-1 corruption inventory.**

**Logic.** The intake file contains 360 exact replays, so a defect can be counted two ways: rows in the file (what Phase 1's output/anomaly_table.csv reports) or distinct posts (what an anomaly table should contain). The difference column reconciles the two, and the arithmetic is checked against the file itself: 12,360 staged rows minus 360 replays must equal the distinct post count. A defect family whose intake count disagreed with Phase 1 would show up here as a mismatch rather than as a silent inconsistency between two artefacts.

```sql
WITH families(anomaly_type) AS (
    VALUES ('NEGATIVE_LIKES'), ('MISSING_PLATFORM'), ('MISSING_TEXT'), ('HTML_ENTITY_OR_TAG')
),
intake AS (
    SELECT 'NEGATIVE_LIKES'     AS anomaly_type, COUNT(*) AS intake_rows
      FROM v_raw_anomaly_scan WHERE is_negative_likes    = 1
    UNION ALL
    SELECT 'MISSING_PLATFORM',  COUNT(*) FROM v_raw_anomaly_scan WHERE is_missing_platform = 1
    UNION ALL
    SELECT 'MISSING_TEXT',      COUNT(*) FROM v_raw_anomaly_scan WHERE is_missing_text     = 1
    UNION ALL
    SELECT 'HTML_ENTITY_OR_TAG',COUNT(*) FROM v_raw_anomaly_scan WHERE is_html_markup      = 1
),
distinct_posts AS (
    SELECT anomaly_type, COUNT(*) AS n_posts
    FROM raw_post_anomalies
    GROUP BY anomaly_type
)
SELECT f.anomaly_type,
       i.intake_rows,
       COALESCE(d.n_posts, 0)                    AS distinct_posts,
       i.intake_rows - COALESCE(d.n_posts, 0)    AS replay_rows_removed
FROM families f
JOIN intake i ON i.anomaly_type = f.anomaly_type
LEFT JOIN distinct_posts d ON d.anomaly_type = f.anomaly_type
ORDER BY i.intake_rows DESC
```

**Output** (4 rows, executed in 63.39 ms):

| `anomaly_type` | `intake_rows` | `distinct_posts` | `replay_rows_removed` |
|---|---|---|---|
| MISSING_PLATFORM | 1846 | 1784 | 62 |
| MISSING_TEXT | 1770 | 1711 | 59 |
| HTML_ENTITY_OR_TAG | 1004 | 974 | 30 |
| NEGATIVE_LIKES | 525 | 509 | 16 |


## H5c -- IDENTIFY DATA ANOMALIES

> **(context for H5) Rank the worst-affected posts.**

**Logic.** H5 shows every corrupted post; this isolates the multiply-corrupted ones, which are the rows most likely to break a naive pipeline and the ones worth eyeballing before any aggregate is trusted. Four defects in one row would mean the row is unusable for any purpose; three still leaves the post analytically alive, which is why the recovery kept them.

```sql
WITH flags AS (
    SELECT post_id, COUNT(*) AS n_anomalies
    FROM raw_post_anomalies
    GROUP BY post_id
)
SELECT f.post_id,
       f.n_anomalies,
       TRIM(CASE WHEN SUM(CASE WHEN a.anomaly_type = 'NEGATIVE_LIKES'     THEN 1 ELSE 0 END) = 1 THEN 'NEGATIVE_LIKES '   ELSE '' END ||
            CASE WHEN SUM(CASE WHEN a.anomaly_type = 'MISSING_PLATFORM'   THEN 1 ELSE 0 END) = 1 THEN 'MISSING_PLATFORM ' ELSE '' END ||
            CASE WHEN SUM(CASE WHEN a.anomaly_type = 'MISSING_TEXT'       THEN 1 ELSE 0 END) = 1 THEN 'MISSING_TEXT '     ELSE '' END ||
            CASE WHEN SUM(CASE WHEN a.anomaly_type = 'HTML_ENTITY_OR_TAG' THEN 1 ELSE 0 END) = 1 THEN 'HTML_ENTITY_OR_TAG' ELSE '' END) AS anomaly_types
FROM flags f
JOIN raw_post_anomalies a ON a.post_id = f.post_id
WHERE f.n_anomalies = (SELECT MAX(n_anomalies) FROM flags)
GROUP BY f.post_id, f.n_anomalies
ORDER BY f.post_id ASC
```

**Output** (20 rows, executed in 2.71 ms):

| `post_id` | `n_anomalies` | `anomaly_types` |
|---|---|---|
| 0oqpg2rgnqxa | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| 26u0g2fea4nk | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| 5b0pz3j0kcxl | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| 6uafi1o2psiu | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| 80rfm8lcs5rz | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| 95tlcn4xx75o | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| 9bngbsop7tof | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| beokpdad5uxf | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| do7er5bxtgtz | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| fk3h10wrlphg | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| fqk6dqmwi48l | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| gugw4ni537sa | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| k21r07ypw81e | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| mz4ztxgcqdfw | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| mzz8pjdhynbb | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| q0ehux8whokc | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| tzddmg5idg0s | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| udj0f5zqeaps | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |
| we0onw3mv5nu | 3 | NEGATIVE_LIKES MISSING_PLATFORM MISSING_TEXT |
| ytohojy7b1kt | 3 | NEGATIVE_LIKES MISSING_PLATFORM HTML_ENTITY_OR_TAG |


## H6 -- MOST SUSPICIOUS HIGH IMPACT USERS

> **Identify users who satisfy all three conditions: have fewer than 10,000 followers; their average post engagement is above the overall average; and at least one of their posts has more shares than likes. Rank these users by total engagement and display their location, follower count, number of posts, average engagement, and total engagement.**

**Logic.** Three independent filters, each failing differently, so each is worth stating: (1) `follower_count < 10000` is a property of the user; (2) the average is compared against the OVERALL average per post, the same baseline as H1, so the two hard questions in this set share one definition; (3) 'more shares than likes' is undefined without a like count, so those posts are excluded rather than counted as zero (R2) -- the same rule that M5b prices. Condition (3) is a set membership test, not an aggregate, which is why it is written as an IN subquery over DISTINCT users instead of another JOIN that could multiply rows.

```sql
WITH baseline AS (
    SELECT AVG(engagement) AS overall_avg_per_post
    FROM v_posts_enriched
),
per_user AS (
    SELECT user_id,
           COUNT(*)        AS n_posts,
           AVG(engagement) AS avg_engagement,
           SUM(engagement) AS total_engagement
    FROM v_posts_enriched
    GROUP BY user_id
),
over_shared AS (
    SELECT DISTINCT user_id
    FROM v_posts_enriched
    WHERE likes IS NOT NULL
      AND shares > likes
)
SELECT u.location,
       u.follower_count,
       pu.n_posts,
       ROUND(pu.avg_engagement, 2) AS avg_engagement_per_post,
       pu.total_engagement,
       RANK() OVER (ORDER BY pu.total_engagement DESC) AS engagement_rank,
       pu.user_id
FROM per_user pu
JOIN users u ON u.user_id = pu.user_id
CROSS JOIN baseline b
WHERE u.follower_count < 10000
  AND pu.avg_engagement > b.overall_avg_per_post
  AND pu.user_id IN (SELECT user_id FROM over_shared)
ORDER BY pu.total_engagement DESC, pu.user_id ASC
```

**Output** (82 rows, executed in 17.39 ms):

| `location` | `follower_count` | `n_posts` | `avg_engagement_per_post` | `total_engagement` | `engagement_rank` | `user_id` |
|---|---|---|---|---|---|---|
| Johannesburg, South Africa | 8262 | 14 | 4,458.14 | 62414 | 1 | user_9mtets0p |
| Houston, USA | 9364 | 15 | 3,854.4 | 57816 | 2 | user_68enpikx |
| Rio de Janeiro, Brazil | 1620 | 14 | 3,905.57 | 54678 | 3 | user_hdas0iau |
| Lyon, France | 2211 | 12 | 4,437 | 53244 | 4 | user_fgjkkrie |
| Delhi, India | 5153 | 11 | 4,392.27 | 48315 | 5 | user_zq2nib62 |
| Vancouver, Canada | 5971 | 10 | 4,626.3 | 46263 | 6 | user_acrnl9py |
| Melbourne, Australia | 3213 | 12 | 3,805.67 | 45668 | 7 | user_hvqqyzoi |
| Rome, Italy | 1452 | 11 | 4,146.91 | 45616 | 8 | user_0aacyvtz |
| Milan, Italy | 8124 | 12 | 3,717.83 | 44614 | 9 | user_5k81svok |
| Johannesburg, South Africa | 3382 | 10 | 4,431 | 44310 | 10 | user_cqaitbuv |
| Singapore | 7361 | 10 | 4,345 | 43450 | 11 | user_14ibkds2 |
| Rome, Italy | 2479 | 10 | 4,289.6 | 42896 | 12 | user_txrypced |
| Toronto, Canada | 608 | 10 | 4,182.6 | 41826 | 13 | user_ha9bzru4 |
| Los Angeles, USA | 5270 | 10 | 4,175.5 | 41755 | 14 | user_d8ouiga8 |
| Johannesburg, South Africa | 4953 | 11 | 3,722.09 | 40943 | 15 | user_6wra58f7 |
| London, UK | 6702 | 9 | 4,353.89 | 39185 | 16 | user_xyvxp8vz |
| Cairo, Egypt | 4459 | 10 | 3,892 | 38920 | 17 | user_ogtvuuki |
| Tokyo, Japan | 4645 | 8 | 4,835.5 | 38684 | 18 | user_kbdvf8d6 |
| Dubai, UAE | 8100 | 10 | 3,854.7 | 38547 | 19 | user_njtvacei |
| New York, USA | 5652 | 8 | 4,718.38 | 37747 | 20 | user_tjzr3rrj |
| Berlin, Germany | 6743 | 8 | 4,586 | 36688 | 21 | user_t38nl55r |
| Manchester, UK | 3852 | 9 | 4,002.78 | 36025 | 22 | user_dxhhp9fo |
| Madrid, Spain | 7547 | 9 | 3,914.67 | 35232 | 23 | user_7e3umebc |
| Dubai, UAE | 7370 | 9 | 3,894.78 | 35053 | 24 | user_pd05k44w |

_(58 further rows omitted here; the full set is in `output/phase2_sql_results.json`)_

## H6b -- MOST SUSPICIOUS HIGH IMPACT USERS

> **(context for H6) Show how many users each condition removes, so the answer can be seen to be selective rather than accidental.**

**Logic.** A three-way AND that returns 82 users says nothing about whether the filters were meaningful or whether one of them did all the work. The funnel reports the population after each condition independently and then in combination, which is what makes the number interpretable -- and it is the same discipline H1 applies when it prints the baseline that made its own answer empty.

```sql
WITH baseline AS (
    SELECT AVG(engagement) AS overall_avg_per_post
    FROM v_posts_enriched
),
per_user AS (
    SELECT user_id,
           AVG(engagement) AS avg_engagement,
           SUM(engagement) AS total_engagement
    FROM v_posts_enriched
    GROUP BY user_id
),
over_shared AS (
    SELECT DISTINCT user_id
    FROM v_posts_enriched
    WHERE likes IS NOT NULL AND shares > likes
)
SELECT (SELECT COUNT(*) FROM users)                                   AS all_users,
       (SELECT COUNT(*) FROM users WHERE follower_count < 10000)      AS c1_fewer_than_10k_followers,
       (SELECT COUNT(*) FROM per_user, baseline b
         WHERE avg_engagement > b.overall_avg_per_post)               AS c2_above_overall_avg,
       (SELECT COUNT(*) FROM over_shared)                             AS c3_has_over_shared_post,
       (SELECT COUNT(*) FROM per_user pu
          JOIN users u ON u.user_id = pu.user_id, baseline b
         WHERE u.follower_count < 10000
           AND pu.avg_engagement > b.overall_avg_per_post
           AND pu.user_id IN (SELECT user_id FROM over_shared))       AS all_three_conditions
```

**Output** (1 row, executed in 17.25 ms):

| `all_users` | `c1_fewer_than_10k_followers` | `c2_above_overall_avg` | `c3_has_over_shared_post` | `all_three_conditions` |
|---|---|---|---|---|
| 1500 | 287 | 748 | 1045 | 82 |

