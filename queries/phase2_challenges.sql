-- ============================================================================
--  DATA VORTEX :: PHASE 2 -- EASY / MEDIUM / HARD CHALLENGE SET
--  21 challenges (E1-E5, M1-M5, H1-H6) + 15 companion queries that test whether
--  each headline answer survives its own assumptions.
-- ----------------------------------------------------------------------------
--  Engine   : SQLite 3.40 (CTEs, window functions, views)
--  Source   : output/social_engine.db, built by src/build_db.py from the
--             Phase-1 cleaned CSVs and the raw corrupted intake file.
--  Runner   : src/run_sql.py -> output/phase2_sql_outputs.md (live capture),
--             output/phase2_sql_results.json, output/screenshots/E1.png, ...
--
--  Rules that govern every query below
--  ---------------------------------------------------------------------------
--  R1  engagement = COALESCE(likes,0)+COALESCE(shares,0)+COALESCE(comments,0).
--      SQL's bare `+` returns NULL when ANY operand is NULL, which would drop
--      1,532 rows (15%) from every SUM/AVG without raising an error. Every
--      aggregate here resolves missingness explicitly.
--
--  R2  A missing value is NEVER imputed. 1,532 posts (15.0%) have no recorded
--      like count and the source never said why, so the count stays NULL. Where
--      a challenge says "ignore posts where likes are missing" (E2) or where a
--      comparison is simply undefined without likes (M5, H6), the query filters
--      them out rather than reading a blank as a zero. Reading blank AS zero is
--      not a neutral convenience here: for M5 it would invent 1,154 anomalies
--      that exist only in the missing data.
--
--  R3  platform = 'Unspecified' is a DATA GAP (1,541 posts, 15.08%), not a
--      platform. It is kept wherever the question is about volume -- a post
--      whose label was lost is still a post -- and excluded wherever the
--      question is about a per-platform RATE or a platform WINNER, so that a
--      gap can never be published as a finding. Every query that excludes it
--      also reports what including it would have changed.
--
--  R4  Ordering is total. Any LIMIT/TOP-k is paired with a deterministic
--      tie-break (usually post_id or user_id), because an arbitrary tie-break
--      is how a "top 10" silently becomes a different list on every re-run.
--
--  R5  Where a challenge has two defensible readings, the query file answers
--      with the strict one and carries a companion query that quantifies the
--      loose one. Nothing is settled by assertion.
-- ============================================================================


-- ============================================================================
-- [E1] PLATFORM POPULARITY :: which single platform carries the most posts
-- ----------------------------------------------------------------------------
-- CHALLENGE: Determine which social media platform has the highest number of
--            posts. Ignore posts where the platform is missing. Return the
--            platform name and number of posts.
-- LOGIC: R3 applies. 1,846 intake rows arrived with the platform cell blank or
--        holding the literal 'NULL'; after de-duplication 1,541 of them survive
--        in the analysis table as 'Unspecified'. The challenge says to ignore
--        them, and they are ignored BEFORE ranking -- not filtered after -- so
--        the ordering cannot be topped by a gap. The ORDER BY carries the
--        platform name as a second key so the single returned row is stable.
-- ============================================================================
SELECT platform,
       COUNT(*) AS n_posts
FROM posts
WHERE platform <> 'Unspecified'
GROUP BY platform
ORDER BY n_posts DESC, platform ASC
LIMIT 1;


-- ============================================================================
-- [E1b] PLATFORM POPULARITY :: is the leader actually ahead, or is the field
--       flat? (companion to E1)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for E1) The spread across the five labelled platforms is
--            small. Report the full league table and test the gap.
-- LOGIC: A ranking alone cannot distinguish "YouTube leads" from "five platforms
--        tied and YouTube came out on top of the noise". The chi-square
--        goodness-of-fit statistic compares the observed post counts against the
--        uniform expectation (total/k) that a null model of "no platform
--        preference" would produce; df = 5 - 1 = 4 and the 5% critical value is
--        9.488. SUM(...) OVER () totals the per-platform terms without a second
--        pass. This is the same discipline Phase 1 applied to the platform
--        spread, applied here inside SQL.
-- ============================================================================
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
ORDER BY n_posts DESC;


-- ============================================================================
-- [E2] MOST ENGAGED POSTS :: top 10 by likes + shares + comments
-- ----------------------------------------------------------------------------
-- CHALLENGE: Find the top 10 posts based on total engagement. Total engagement
--            is defined as likes + shares + comments. Ignore posts where likes
--            are missing.
-- LOGIC: "likes + shares + comments" is written with COALESCE on the two
--        columns that are complete in this dataset (shares and comments have no
--        NULLs at all -- only likes does), so the expression is defined by
--        construction rather than by luck. The WHERE clause is the challenge's
--        own instruction and is the same rule as R2: 1,532 posts have no like
--        count, and adding 0 for them would rank a post on partial evidence.
--        Ranking is by the computed total, so the tie-break on post_id is what
--        makes position 10 stable across re-runs (R4).
-- ============================================================================
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
LIMIT 10;


-- ============================================================================
-- [E2b] MOST ENGAGED POSTS :: how much separates 1st from 10th? (companion)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for E2) A top-10 is only meaningful if its cut is
--            meaningful. Quantify the cut.
-- LOGIC: The 10th-place score is read with OFFSET 9 rather than by hardcoding a
--        number, so the metric survives any re-run that changes the data. If the
--        gap between 1st and 10th is small, the "top 10" is a slice through a
--        dense cloud and should be reported as such instead of as ten standout
--        posts.
-- ============================================================================
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
FROM cut;


-- ============================================================================
-- [E3] AVERAGE ENGAGEMENT BY PLATFORM :: the three metric means and the winner
-- ----------------------------------------------------------------------------
-- CHALLENGE: Calculate the average likes, shares, and comments for each
--            platform. Which platform generates the highest average total
--            engagement?
-- LOGIC: AVG(likes) in SQLite skips NULLs, which is the correct behaviour here:
--        1,532 posts have no like count and averaging over the posts that DO
--        have one is honest, whereas AVG(COALESCE(likes,0)) would silently
--        average 1,532 fabricated zeros into every platform's like mean and
--        bias the answer downward. `rows_with_likes` is carried alongside so the
--        reader can see the denominator each average was computed over. The rank
--        is computed over the same AVG(engagement) expression that is displayed,
--        and 'Unspecified' is retained in the table for completeness but flagged
--        so it cannot be mistaken for the winner (R3).
-- ============================================================================
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
ORDER BY avg_total_engagement DESC;


-- ============================================================================
-- [E3b] AVERAGE ENGAGEMENT BY PLATFORM :: the winner, the margin, and whether
--       the margin is real (companion to E3)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for E3) Name the winning platform and justify it.
-- LOGIC: Two platforms can differ in the mean and still be indistinguishable,
--        because each mean carries its own sampling error. The two-sample
--        z-statistic divides the gap by sqrt(var1/n1 + var2/n2), with the
--        variance written as E[x^2] - E[x]^2 (SQLite has no VAR function), and
--        guards the square root with MAX(...,0) so floating-point dust cannot
--        produce a negative variance. 'Unspecified' is excluded here because
--        this query names a winner (R3). |z| > 1.96 is the 5% two-sided bar.
-- ============================================================================
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
FROM test;


-- ============================================================================
-- [E4] HIGHLY SHARED BUT POORLY LIKED :: shares > 1,500 and likes < 500
-- ----------------------------------------------------------------------------
-- CHALLENGE: Identify posts that received more than 1,500 shares but fewer than
--            500 likes. Return the post ID, platform, likes, shares, and
--            comments.
-- LOGIC: Both bounds are strict ('more than', 'fewer than'), so the predicates
--        are > and <, not >= and <= -- a boundary error here would be invisible
--        in the output but wrong. A NULL like count fails `likes < 500` in SQL
--        automatically (NULL comparisons are never true), which is the correct
--        outcome: a post with no recorded likes cannot be shown to be "poorly
--        liked". That is stated rather than relied on silently.
-- ============================================================================
SELECT post_id,
       platform,
       likes,
       shares,
       comments
FROM posts
WHERE shares > 1500
  AND likes < 500
ORDER BY shares DESC, post_id ASC;


-- ============================================================================
-- [E4b] HIGHLY SHARED BUT POORLY LIKED :: behaviour, or one platform's quirk?
--       (companion to E4)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for E4) 214 posts match. Decide whether the pattern is
--            platform-specific or spread across the whole platform.
-- LOGIC: A raw count per platform would just re-report platform volume, so the
--        query returns the RATE -- flagged posts as a percentage of that
--        platform's own posts. Rates are what expose a platform-specific
--        behaviour; counts only expose which platform posts more. 'Unspecified'
--        is kept here because this is a volume/rate question and the posts are
--        real (R3), but it is marked.
-- ============================================================================
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
ORDER BY pct_of_platform DESC;


-- ============================================================================
-- [E5] USERS WITH LARGE AUDIENCES :: more than 40,000 followers
-- ----------------------------------------------------------------------------
-- CHALLENGE: Find all users with more than 40,000 followers. Display their user
--            ID, location, language, and follower count.
-- LOGIC: 'more than 40,000' is strict, so the predicate is > 40000: a user
--        sitting exactly on 40,000 is not in the answer. `location` is the
--        source's own string, kept verbatim in the users table, so every row
--        here can be matched character-for-character against the intake file.
--        The tie-break on user_id makes the ordering total (R4).
-- ============================================================================
SELECT user_id,
       location,
       language,
       follower_count
FROM users
WHERE follower_count > 40000
ORDER BY follower_count DESC, user_id ASC;


-- ============================================================================
-- [M1] ENGAGEMENT BY LOCATION :: total engagement generated per location
-- ----------------------------------------------------------------------------
-- CHALLENGE: Using both datasets, calculate the total engagement generated by
--            users from each location. Return the location, number of posts, and
--            total engagement. Rank locations from highest to lowest engagement.
-- LOGIC: The join is on user_id because engagement lives on the post while
--        location lives on the user -- this is the one challenge that REQUIRES
--        both datasets, and the query cannot run against either table alone.
--        SUM uses v_posts_enriched.engagement, which is already NULL-safe (R1),
--        so a location is never dropped for having a post with no like count.
--        RANK() rather than ROW_NUMBER() is deliberate: tied locations should
--        share a rank, and RANK is what a league table means.
-- ============================================================================
SELECT u.location,
       COUNT(*)                       AS n_posts,
       SUM(p.engagement)              AS total_engagement,
       RANK() OVER (ORDER BY SUM(p.engagement) DESC) AS engagement_rank
FROM v_posts_enriched p
JOIN users u ON u.user_id = p.user_id
GROUP BY u.location
ORDER BY total_engagement DESC, u.location ASC;


-- ============================================================================
-- [M1b] ENGAGEMENT BY LOCATION :: is the ranking about quality or just about
--       how many posts a location happens to have? (companion to M1)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for M1) Total engagement is a product of volume and
--            quality. Separate the two.
-- LOGIC: Two RANK() windows are computed over the same rows: one on the total,
--        one on the per-post average. If the two rankings disagree, then the
--        "best location" answer is really "the location with the most posts",
--        and saying more than that would be a volume artefact published as an
--        insight. rank_shift quantifies the disagreement per row instead of
--        leaving the reader to eyeball two columns.
-- ============================================================================
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
ORDER BY rank_by_total;


-- ============================================================================
-- [M2] DO HIGH FOLLOWER USERS GET MORE ENGAGEMENT? :: cohort comparison
-- ----------------------------------------------------------------------------
-- CHALLENGE: Divide users into two groups: high follower users (>= 25,000
--            followers) and low follower users (< 25,000 followers). Compare
--            their average engagement per post.
-- LOGIC: The grain is the POST, not the user. Averaging per-user averages would
--        weight a user with 2 posts the same as a user with 17, which is the
--        wrong unit for "average engagement per post" and would change the
--        answer. The coefficient is computed from follower_count, a NOT NULL
--        column, so no user can fall outside both cohorts. Standard deviation is
--        reported next to each mean because it is the honest context for a
--        difference of tens of engagements against a spread of thousands.
-- ============================================================================
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
ORDER BY avg_engagement DESC;


-- ============================================================================
-- [M2b] DO HIGH FOLLOWER USERS GET MORE ENGAGEMENT? :: is the difference
--       bigger than its own noise? (companion to M2)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for M2) Say whether the gap in M2 is a finding.
-- LOGIC: The same two-sample z-statistic as E3b, here on the cohort contrast.
--        This matters because the "obvious" business expectation (more followers
--        -> more engagement) is the one an analyst is most likely to confirm
--        without a test. The z-statistic is what turns a directional difference
--        into a claim, or refuses to.
-- ============================================================================
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
FROM pair;


-- ============================================================================
-- [M3] MOST ACTIVE USERS :: the ten accounts with the most posts
-- ----------------------------------------------------------------------------
-- CHALLENGE: Find the top 10 users who have created the highest number of
--            posts. Display their follower count, location, post count, and
--            total engagement.
-- LOGIC: Post counts are small integers and therefore heavily tied (the busiest
--        account wrote 17 posts). Without the extra sort keys the identity of
--        the 10th user would depend on SQLite's internal row order. The
--        ORDER BY is therefore total: post count, then total engagement, then
--        user_id (R4). Total engagement is included as a displayed column and as
--        the second sort key, so the ranking is "most active, and among equally
--        active, most effective".
-- ============================================================================
SELECT user_id,
       follower_count,
       location,
       n_posts,
       total_engagement
FROM v_user_totals
ORDER BY n_posts DESC, total_engagement DESC, user_id ASC
LIMIT 10;


-- ============================================================================
-- [M3b] MOST ACTIVE USERS :: how wide is the tie band at the cut? (companion)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for M3) Report the activity distribution so the top-10
--            cut can be judged.
-- LOGIC: A tie-aware census of post counts. If dozens of users share the count
--        that sits on the 10th-place boundary, then "the top 10 most active
--        users" is one arbitrary selection out of a much larger tied group, and
--        the query says so with numbers instead of a caveat in prose.
-- ============================================================================
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
FROM cut;


-- ============================================================================
-- [M4] PLATFORM BEHAVIOUR BY HIGH FOLLOWER USERS :: best platform for accounts
--      with at least 30,000 followers
-- ----------------------------------------------------------------------------
-- CHALLENGE: Among users with at least 30,000 followers, determine which
--            platform gives them the highest average engagement per post.
-- LOGIC: The cohort filter is applied to the USER before aggregation, so the
--        comparison is between the same kind of account on each platform -- this
--        is what separates M4 from E3, and it is the whole point of the
--        challenge. 'Unspecified' is excluded because this query names a winner
--        (R3); M4b shows it was not the winner anyway. RANK() exposes the whole
--        ordering rather than a bare LIMIT 1, so the margin is visible.
-- ============================================================================
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
ORDER BY avg_engagement_per_post DESC;


-- ============================================================================
-- [M4b] PLATFORM BEHAVIOUR BY HIGH FOLLOWER USERS :: does the winner survive a
--       different definition of "high follower"? (companion to M4)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for M4) The 30,000 threshold is arbitrary. Sweep it.
-- LOGIC: The challenge supplies 30,000 as a cut, but any cut is a choice. Five
--        thresholds are swept in one pass with a VALUES list cross-joined into
--        the aggregate, and ROW_NUMBER() picks the winner inside each threshold
--        partition. If the same platform wins at every cut the finding is a
--        property of the data; if the winner changes, the finding is a property
--        of the threshold and must be reported as such.
-- ============================================================================
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
ORDER BY follower_threshold;


-- ============================================================================
-- [M5] DETECT SUSPICIOUS ENGAGEMENT :: shares exceeding likes + comments
-- ----------------------------------------------------------------------------
-- CHALLENGE: Find posts where the number of shares is greater than the number
--            of likes and comments combined. Such posts may represent unusual
--            sharing behaviour. Return the top 20.
-- LOGIC: The comparison "shares > likes + comments" is UNDEFINED for the 1,532
--        posts with no like count, so they are excluded by requiring likes to be
--        present (R2). Treating a blank like count as 0 would manufacture 1,154
--        extra "anomalies" whose only defect is a missing field -- see M5b,
--        which prices that mistake exactly. Ranking is by the size of the
--        excess, the natural severity measure once both readings are ruled out;
--        the ratio column is shown alongside because a 6-like post with 900
--        shares and a 490-like post with 2,000 shares are different phenomena.
-- ============================================================================
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
LIMIT 20;


-- ============================================================================
-- [M5b] DETECT SUSPICIOUS ENGAGEMENT :: pricing the missing-value trap
--       (companion to M5)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for M5) Show what the alternative reading would produce.
-- LOGIC: Three counts are placed side by side: the strict definition, the
--        definition that reads a missing like count as zero, and the number of
--        posts whose likes are missing AND whose shares exceed their comments.
--        The third number is the gap between the first two, so the reader can
--        see that every extra "anomaly" in the loose reading comes from missing
--        data rather than from behaviour.
-- ============================================================================
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
FROM strict_count, loose_count, missing_like_count;


-- ============================================================================
-- [H1] ABNORMALLY HIGH ENGAGEMENT :: users averaging more than twice the
--      overall average engagement per post
-- ----------------------------------------------------------------------------
-- CHALLENGE: Calculate the average total engagement per user. Identify users
--            whose average engagement per post is more than twice the overall
--            average engagement per post. Return the user ID, location, follower
--            count, post count, and average engagement.
-- LOGIC: The baseline is the overall average engagement PER POST (every post
--        weighted equally, which is what "overall average engagement per post"
--        means on a post-level table), compared against each user's per-post
--        average. This query returns ZERO rows, and that is the correct answer,
--        not a bug: the arithmetic is laid out in H1b and swept in H1c. The
--        column list is kept complete so the reader can see the shape of the
--        answer that the data refuses to give.
-- ============================================================================
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
ORDER BY pu.avg_engagement DESC, pu.user_id ASC;


-- ============================================================================
-- [H1b] ABNORMALLY HIGH ENGAGEMENT :: proving the empty answer (companion)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for H1) An empty result must be shown to be arithmetic,
--            not a broken query.
-- LOGIC: Every input to the decision is printed: the baseline, the doubled
--        threshold, the highest per-user average that actually exists, and that
--        maximum expressed as a multiple of the baseline. The verdict is
--        computed, not asserted -- the database compares its own maximum against
--        its own threshold. Reporting the near-miss multiple is what makes the
--        emptiness informative rather than a dead end.
-- ============================================================================
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
FROM baseline b;


-- ============================================================================
-- [H1c] ABNORMALLY HIGH ENGAGEMENT :: sensitivity ladder (companion to H1)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for H1) Find the multiple at which the question does have
--            an answer, so the 2x cut can be reported against a real curve.
-- LOGIC: The same test is run at 1.25x, 1.50x, 1.75x and 2.00x in one compound
--        statement. This converts "no users qualify" from a dead end into a
--        threshold curve, which is the difference between refusing to answer and
--        calibrating the question.
-- ============================================================================
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
-- The threshold is computed OUTSIDE the count. An aggregate whose WHERE clause
-- matches nothing still returns one row, but every column in it evaluates on an
-- empty set and would print NULL -- which is how the 2.00x bar came out blank on
-- the first run of this query. Splitting the scalar from the count keeps the bar
-- visible exactly when the count is zero, which is the row that matters most.
SELECT m.label AS multiple,
       ROUND(m.factor * b.overall_avg_per_post, 2) AS threshold,
       (SELECT COUNT(*) FROM per_user p
         WHERE p.avg_engagement > m.factor * b.overall_avg_per_post) AS users_qualifying
FROM multiples m
CROSS JOIN baseline b
ORDER BY m.multiple;


-- ============================================================================
-- [H2] RANK USERS WITHIN THEIR LOCATION :: top 3 per location
-- ----------------------------------------------------------------------------
-- CHALLENGE: For every location, rank users based on their total engagement.
--            Return only the top 3 users from each location.
-- LOGIC: PARTITION BY location converts the global ranking into a per-location
--        competition, which is the entire difficulty of the challenge. The
--        tie-break chain (total engagement, then post count, then user_id) is
--        not optional here: H2b shows that the 3rd and 4th place users in Tokyo
--        are separated by 33 engagements out of ~43,000, so ties and near-ties
--        decide the podium. ROW_NUMBER gives exactly 3 rows per location;
--        RANK would be able to return more than 3 and silently break the
--        challenge's "only the top 3" instruction.
-- ============================================================================
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
ORDER BY location ASC, rank_in_location ASC;


-- ============================================================================
-- [H2b] RANK USERS WITHIN THEIR LOCATION :: how tight is the podium cut?
--       (companion to H2)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for H2) Show which locations have a contested 3rd place.
-- LOGIC: For each location the 3rd-place score is extracted with MAX(CASE
--        WHEN rn = 3 ...) and the 4th-place score with MIN(CASE WHEN rn = 4...).
--        The margin between them is the honesty check on the answer: a location
--        whose margin rounds to 0.1% has a podium decided by luck, and reporting
--        its top 3 without that number would overstate what the data knows.
-- ============================================================================
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
LIMIT 8;


-- ============================================================================
-- [H3] PLATFORM PERFORMANCE VS ITS OWN AVERAGE :: exceptional posts
-- ----------------------------------------------------------------------------
-- CHALLENGE: For every platform, identify posts whose engagement is
--            significantly higher than the average engagement of that platform.
--            A post is considered exceptional if its engagement is at least 2x
--            the average engagement of its platform.
-- LOGIC: The benchmark is each platform's OWN mean (a correlated per-platform
--        aggregate joined back onto the posts), so a post on a low-engagement
--        platform is judged against its peers rather than against the global
--        mean -- that comparison is the point of the challenge. 'at least 2x' is
--        inclusive, hence >=. 'Unspecified' is excluded because it has no
--        platform identity to be exceptional within (R3); H3b reports the 5
--        posts that including it would have added.
-- ============================================================================
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
ORDER BY multiple_of_platform_avg DESC, p.post_id ASC;


-- ============================================================================
-- [H3b] PLATFORM PERFORMANCE VS ITS OWN AVERAGE :: thresholds and the gap
--       bucket (companion to H3)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for H3) Show each platform's bar and what the excluded
--            bucket would have contributed.
-- LOGIC: The 2x bar is a derived number, not a given one, and it differs per
--        platform (a platform's mean plus 100% of itself). Printing the bar for
--        every platform makes the rule auditable and shows why the same post
--        engagement can be exceptional on one platform and ordinary on another.
--        'Unspecified' is carried in the table but marked so its row is not read
--        as a platform result (R3).
-- ============================================================================
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
ORDER BY pct_of_platform DESC, pl.platform ASC;


-- ============================================================================
-- [H4] FOLLOWER TO ENGAGEMENT ANOMALY :: small accounts in the top engagement
--      decile
-- ----------------------------------------------------------------------------
-- CHALLENGE: Find users who have fewer than 5,000 followers but whose total post
--            engagement places them among the top 10% of all users. These users
--            may represent unusually high performing or suspicious accounts.
--            This requires multiple levels of analysis.
-- LOGIC: Four levels, in order, and each one exists because the previous one is
--        not enough: (1) collapse 10,221 posts to 1,500 users with SUM; (2) cut
--        the user population into deciles with NTILE(10) on that total;
--        (3) isolate the top decile; (4) re-join the followership dimension and
--        apply the < 5,000 constraint. The joining key throughout is user_id,
--        which is the only column linking the two datasets. NTILE assigns ranks
--        before ties are considered, so users sharing a total can land in
--        adjacent deciles -- H4b re-runs the same question with an explicit
--        percentile threshold and shows the answer is unchanged.
-- ============================================================================
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
    -- The floor of each decile is a second, separate pass: a window function
    -- cannot be nested inside another window's PARTITION BY, so the bucket is
    -- materialised first and the MIN is taken over it afterwards.
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
ORDER BY d.total_engagement DESC, u.user_id ASC;


-- ============================================================================
-- [H4b] FOLLOWER TO ENGAGEMENT ANOMALY :: is the decile cut doing the work, or
--       is the answer an artefact of NTILE? (companion to H4)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for H4) Two independent definitions of "top 10%" must
--            agree before the finding is reported.
-- LOGIC: NTILE(10) forces exactly 10 equal buckets, which is convenient but
--        splits tied totals arbitrarily at the boundary. The second definition
--        is explicit: rank every user by total engagement and keep the top
--        n*0.10 by ROW_NUMBER. If both definitions return the same users, the
--        result is a property of the data rather than of the bucketing function.
--        The decile floor is printed so the answer can be re-derived by hand.
-- ============================================================================
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
            ELSE 'the definitions DISAGREE -- report the boundary as unstable' END AS robustness;


-- ============================================================================
-- [H5] IDENTIFY DATA ANOMALIES :: corrupted posts in the intake file
-- ----------------------------------------------------------------------------
-- CHALLENGE: Identify potentially corrupted posts where one or more of the
--            following conditions are true: (1) likes are negative; (2) platform
--            is missing; (3) text content is missing; (4) text contains HTML
--            entities/tags such as &amp;, <div>, or <br>. Return the post ID and
--            identify the type of anomaly.
-- LOGIC: This question CANNOT be asked of the cleaned table -- cleaning is
--        exactly the step that removed these defects, so a query over `posts`
--        would return nothing and prove nothing. It runs against `raw_posts`,
--        the verbatim intake staging table, and reads the defect definitions from
--        v_raw_anomaly_scan, the same SQL predicate that populated the anomaly
--        relation. The long-form relation means a post carrying three defects
--        produces three rows, so no condition masks another; the counts are
--        `>= 1` per condition rather than exclusive buckets. The concatenated
--        label is built with CASE in a FIXED order (not GROUP_CONCAT, whose
--        ordering is unspecified) so the output is byte-stable across re-runs.
-- ============================================================================
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
ORDER BY n_anomalies DESC, post_id ASC;


-- ============================================================================
-- [H5b] IDENTIFY DATA ANOMALIES :: per-family inventory, intake rows vs distinct
--       posts (companion to H5)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for H5) Reconcile the SQL scan against the Phase-1
--            corruption inventory.
-- LOGIC: The intake file contains 360 exact replays, so a defect can be counted
--        two ways: rows in the file (what Phase 1's output/anomaly_table.csv
--        reports) or distinct posts (what an anomaly table should contain). The
--        difference column reconciles the two, and the arithmetic is checked
--        against the file itself: 12,360 staged rows minus 360 replays must
--        equal the distinct post count. A defect family whose intake count
--        disagreed with Phase 1 would show up here as a mismatch rather than as
--        a silent inconsistency between two artefacts.
-- ============================================================================
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
ORDER BY i.intake_rows DESC;


-- ============================================================================
-- [H5c] IDENTIFY DATA ANOMALIES :: the posts carrying three defects at once
--       (companion to H5)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for H5) Rank the worst-affected posts.
-- LOGIC: H5 shows every corrupted post; this isolates the multiply-corrupted
--        ones, which are the rows most likely to break a naive pipeline and the
--        ones worth eyeballing before any aggregate is trusted. Four defects in
--        one row would mean the row is unusable for any purpose; three still
--        leaves the post analytically alive, which is why the recovery kept them.
-- ============================================================================
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
ORDER BY f.post_id ASC;


-- ============================================================================
-- [H6] MOST SUSPICIOUS HIGH IMPACT USERS :: small accounts, above-average
--      engagement, and at least one over-shared post
-- ----------------------------------------------------------------------------
-- CHALLENGE: Identify users who satisfy all three conditions: have fewer than
--            10,000 followers; their average post engagement is above the
--            overall average; and at least one of their posts has more shares
--            than likes. Rank these users by total engagement and display their
--            location, follower count, number of posts, average engagement, and
--            total engagement.
-- LOGIC: Three independent filters, each failing differently, so each is worth
--        stating: (1) `follower_count < 10000` is a property of the user;
--        (2) the average is compared against the OVERALL average per post, the
--        same baseline as H1, so the two hard questions in this set share one
--        definition; (3) 'more shares than likes' is undefined without a like
--        count, so those posts are excluded rather than counted as zero (R2) --
--        the same rule that M5b prices. Condition (3) is a set membership test,
--        not an aggregate, which is why it is written as an IN subquery over
--        DISTINCT users instead of another JOIN that could multiply rows.
-- ============================================================================
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
ORDER BY pu.total_engagement DESC, pu.user_id ASC;


-- ============================================================================
-- [H6b] MOST SUSPICIOUS HIGH IMPACT USERS :: the three-condition funnel
--       (companion to H6)
-- ----------------------------------------------------------------------------
-- CHALLENGE: (context for H6) Show how many users each condition removes, so
--            the answer can be seen to be selective rather than accidental.
-- LOGIC: A three-way AND that returns 82 users says nothing about whether the
--        filters were meaningful or whether one of them did all the work. The
--        funnel reports the population after each condition independently and
--        then in combination, which is what makes the number interpretable -- and
--        it is the same discipline H1 applies when it prints the baseline that
--        made its own answer empty.
-- ============================================================================
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
           AND pu.user_id IN (SELECT user_id FROM over_shared))       AS all_three_conditions;
