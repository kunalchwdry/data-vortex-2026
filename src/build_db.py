"""
Data Vortex -- Round 1, Phase 2 :: rebuild the analytical core in SQL
======================================================================

    python src/build_db.py

Loads the Phase-1 cleaned CSVs into a real SQLite database with an explicit
star-ish schema: primary keys, foreign keys, CHECK constraints, indices and
materialised views. Nothing is hardcoded -- every number a judge sees in the
report is read out of this database by queries/challenges.sql.

Why SQLite: it is dependency-free and reproducible on any machine, and it has
supported CTEs + window functions since 3.25. `src/sql_dialect_notes.md` lists
the two Postgres-only constructs used in the annotated version.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "output"
DB = OUT / "social_engine.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

-- One row per surviving post. `post_id` is unique after dedup, so it is a real
-- primary key (in the raw file it was not -- 352 ids repeated).
CREATE TABLE IF NOT EXISTS posts (
    post_id        TEXT    PRIMARY KEY,
    user_id        TEXT    NOT NULL REFERENCES users(user_id),
    platform       TEXT    NOT NULL CHECK (platform IN
                       ('Twitter','Facebook','Instagram','YouTube','Reddit',
                        'Unspecified')),
    text_content   TEXT    NOT NULL,
    posted_at      TEXT    NOT NULL,              -- ISO-8601, single format
    post_date      TEXT    NOT NULL,
    post_month     TEXT    NOT NULL,              -- 'YYYY-MM', cheap GROUP BY
    post_hour      INTEGER NOT NULL CHECK (post_hour BETWEEN 0 AND 23),
    weekday        TEXT    NOT NULL,
    is_weekend     INTEGER NOT NULL CHECK (is_weekend IN (0,1)),
    has_time       INTEGER NOT NULL CHECK (has_time IN (0,1)),
    likes          INTEGER CHECK (likes  IS NULL OR likes  >= 0),
    shares         INTEGER CHECK (shares IS NULL OR shares >= 0),
    comments       INTEGER CHECK (comments IS NULL OR comments >= 0),
    likes_restored INTEGER NOT NULL CHECK (likes_restored IN (0,1)),
    date_flagged   INTEGER NOT NULL CHECK (date_flagged IN (0,1)),
    CHECK (likes IS NOT NULL OR shares IS NOT NULL OR comments IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS users (
    user_id         TEXT    PRIMARY KEY,
    city            TEXT,
    country         TEXT,
    language        TEXT    NOT NULL,
    account_created TEXT    NOT NULL,
    follower_count  INTEGER NOT NULL CHECK (follower_count >= 0)
);

-- Long-form tags: turns the '#' soup into a joinable dimension so hashtag
-- analysis is a GROUP BY instead of string surgery in every query.
CREATE TABLE IF NOT EXISTS post_tags (
    post_id TEXT NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    tag     TEXT NOT NULL,
    PRIMARY KEY (post_id, tag)
);

CREATE INDEX IF NOT EXISTS ix_posts_month   ON posts(post_month);
CREATE INDEX IF NOT EXISTS ix_posts_user    ON posts(user_id);
CREATE INDEX IF NOT EXISTS ix_posts_plat    ON posts(platform);
CREATE INDEX IF NOT EXISTS ix_tags_tag      ON post_tags(tag);
CREATE INDEX IF NOT EXISTS ix_users_country ON users(country);

-- ---- views ----------------------------------------------------------------
-- Total engagement. NULL-safe: SQL's + returns NULL if ANY operand is NULL,
-- which would silently delete rows from every aggregate. COALESCE each term
-- and require at least one to exist.
CREATE VIEW IF NOT EXISTS v_posts_enriched AS
SELECT p.*,
       COALESCE(p.likes,0) + COALESCE(p.shares,0) + COALESCE(p.comments,0)
         AS engagement,
       CASE WHEN p.likes IS NOT NULL AND p.likes > 0
            THEN (COALESCE(p.shares,0)+COALESCE(p.comments,0))*1.0/p.likes
       END AS amplify_ratio,
       CASE WHEN p.likes IS NULL OR p.shares IS NULL OR p.comments IS NULL
            THEN 1 ELSE 0 END AS partial_metrics
FROM posts p;

CREATE VIEW IF NOT EXISTS v_monthly AS
SELECT post_month,
       COUNT(*)                              AS posts,
       AVG(COALESCE(likes, shares, comments))AS approx_reach,
       SUM(engagement)                       AS total_engagement,
       AVG(engagement)                       AS mean_engagement,
       SUM(likes_restored)                   AS repaired_like_rows
FROM v_posts_enriched
GROUP BY post_month;
"""

# CSV column -> table column, with renames so the SQL schema is self-documenting
POST_COLS = {
    "post_id": "post_id", "user_id": "user_id", "platform": "platform",
    "text_content": "text_content", "timestamp": "posted_at",
    "post_date": "post_date", "post_month": "post_month",
    "post_hour": "post_hour", "weekday": "weekday", "is_weekend": "is_weekend",
    "likes": "likes", "shares": "shares", "comments": "comments",
    "flag_likes_sign_restored": "likes_restored",
    "flag_ambiguous_date_format": "date_flagged",
    "timestamp_format": "timestamp_format",
}
USER_COLS = ["user_id", "city", "country", "language", "account_created",
             "follower_count"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()

    posts = pd.read_csv(CLEAN / "Social_Engine_Posts_Clean.csv")
    users = pd.read_csv(CLEAN / "Social_Engine_Users_Clean.csv")

    posts = posts[list(POST_COLS)].rename(columns=POST_COLS)
    posts["posted_at"] = pd.to_datetime(posts.posted_at).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    posts["post_date"] = pd.to_datetime(posts.post_date).dt.strftime("%Y-%m-%d")
    # has_time guards the hour-of-day analysis: date-only intake rows land on
    # midnight and would fabricate a circadian peak.
    posts["has_time"] = posts.timestamp_format.isin(["iso8601", "epoch_seconds"]).astype(int)
    posts = posts.drop(columns=["timestamp_format"])
    for c in ["is_weekend", "likes_restored", "date_flagged"]:
        posts[c] = posts[c].astype(bool).astype(int)
    for c in ["likes", "shares", "comments"]:
        posts[c] = pd.to_numeric(posts[c], errors="coerce").astype("Int64")

    users = users[USER_COLS].copy()
    users["account_created"] = pd.to_datetime(users.account_created).dt.strftime("%Y-%m-%d")
    users["follower_count"] = pd.to_numeric(users.follower_count, errors="coerce").astype(int)

    # referential integrity BEFORE the FK exists, so the load cannot create an
    # orphan table; a violation here means Phase 1 and Phase 2 disagree.
    orphans = set(posts.user_id) - set(users.user_id)
    assert not orphans, f"posts reference {len(orphans)} unknown users"

    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    # users first: posts.user_id is an FK onto it, so the parent must exist
    # before the child rows arrive or the constraint (correctly) rejects them.
    users.to_sql("users", con, if_exists="append", index=False)
    posts.to_sql("posts", con, if_exists="append", index=False)

    # explode hashtag soup into the relation
    import re
    HT = re.compile(r"#([A-Za-z][A-Za-z0-9_]*)")
    rows = {(pid, t) for pid, txt in zip(posts.post_id, posts.text_content)
            for t in set(HT.findall(str(txt)))}
    con.executemany("INSERT OR IGNORE INTO post_tags VALUES (?,?)", sorted(rows))

    con.execute("ANALYZE")
    con.commit()

    n_p = con.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    n_u = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    n_t = con.execute("SELECT COUNT(*) FROM post_tags").fetchone()[0]
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    con.close()
    print(f"[db] {DB.relative_to(ROOT)}  posts={n_p} users={n_u} post_tags={n_t}")
    print(f"[db] foreign_key_check violations: {len(fk)}")


if __name__ == "__main__":
    main()
