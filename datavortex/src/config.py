"""
Data Vortex -- Round 1, Phase 1
Shared configuration for the recovery + cleaning pipeline.

Every constant that encodes an ANALYST DECISION lives here (not buried in the
code) so that judges can inspect, change and re-run the pipeline with different
assumptions and see the effect in one place.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]

DATA_RAW = ROOT / "data" / "raw"
DATA_CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "output"
FIGS = OUT / "figures"

RAW_POSTS = DATA_RAW / "Social_Engine_Posts_Corrupted.csv"
RAW_USERS = DATA_RAW / "Social_Engine_Users.csv"

CLEAN_POSTS = DATA_CLEAN / "Social_Engine_Posts_Clean.csv"
CLEAN_USERS = DATA_CLEAN / "Social_Engine_Users_Clean.csv"
CLEAN_POSTS_JSON = DATA_CLEAN / "Social_Engine_Posts_Clean.json"
REPAIR_LOG = DATA_CLEAN / "repair_log.csv"
QUALITY_REPORT = DATA_CLEAN / "data_quality_report.md"

DB_PATH = OUT / "social_engine.db"

# ---------------------------------------------------------------------------
# Provenance of the dataset (needed to justify "no fabrication")
# ---------------------------------------------------------------------------
SOURCE_BASE = "https://datavortex-social-engine.vercel.app"
DATASET_PATHS = [
    "/dataset/Social_Engine_Users.csv",
    "/dataset/Social_Engine_Posts_Corrupted.csv",
]

# ---------------------------------------------------------------------------
# Cleaning decisions  (each one is explained in docs/cleaning_decisions.md)
# ---------------------------------------------------------------------------

# D1 -- tokens that mean "this value is missing" but are written as text.
#       All of them are normalised to a real NULL, never to 0 or "Unknown"
#       at parse time.
MISSING_TOKENS = {"", "NULL", "null", "None", "NaN", "nan", "N/A", "NA", "n/a"}

# D2 -- the `dd-mm-yyyy` block is day-first.
#       PROOF, not assumption: 2172 of the 3622 such rows have a first field
#       > 12, and 0 of them have a second field > 12. A month-first reading is
#       therefore arithmetically impossible for a fifth of the block. We apply
#       one convention to the whole block for consistency and flag it.
DAY_FIRST_FORMATS = ("%d-%m-%Y",)
AMBIGUOUS_DATE_FLAG = "flag_ambiguous_date_format"

# D3 -- negative `likes`.
#       likes is the ONLY corrupted numeric column (shares/comments are clean)
#       and 100% of its non-integer values are negative with a `.0` suffix.
#       |neg| median 2388 vs positive median 2505; |neg| max 4987 vs positive
#       max 5000 -- the negatives are a mirrored copy of the same distribution.
#       That is the signature of a sign-flip during the crash, not of data that
#       is genuinely unknown. We therefore restore magnitude with abs() and
#       keep a flag so nothing is hidden. Set to False to null them instead.
RESTORE_SIGN_FLIPPED_LIKES = True
SIGN_FLIP_FLAG = "flag_likes_sign_restored"

# D4 -- missing values are NEVER imputed in Phase 1.
#       Fabrication of data is prohibited by the rulebook, so a missing text or
#       a missing like count stays missing and is marked, not guessed.
IMPUTE_ENGAGEMENT = False

# D5 -- rows whose post text is entirely missing are dropped from the analysis
#       table, because an empty text cannot support any content or sentiment
#       claim. They are written out separately, not discarded.
DROP_EMPTY_TEXT_ROWS = True
DROPPED_POSTS = DATA_CLEAN / "Social_Engine_Posts_EmptyText_HeldOut.csv"

# D6 -- business-date window of the dataset (used for validation, not for
#       silently trimming).
EXPECTED_MIN_DATE = "2024-05-01"
EXPECTED_MAX_DATE = "2025-04-30"

# D7 -- canonical platform spellings. The source uses Title Case already; the
#       mapping exists so a future re-run tolerates casing/spacing drift.
PLATFORM_CANONICAL = {
    "twitter": "Twitter",
    "x": "Twitter",
    "facebook": "Facebook",
    "fb": "Facebook",
    "instagram": "Instagram",
    "insta": "Instagram",
    "youtube": "YouTube",
    "reddit": "Reddit",
}
PLATFORM_UNKNOWN = "Unspecified"   # explicit sentinel, not an invented platform


# ---------------------------------------------------------------------------
# Submission identity. Kept here so the README, the notebook and both report
# PDFs all take the team name from one place - change it once, every
# artefact re-renders (./run_all.sh rebuilds them).
# ---------------------------------------------------------------------------
TEAM_NAME = "Forge-X"
TEAM_MEMBERS = ["Kunal Choudhary"]
EVENT = "Aaruush'26"
