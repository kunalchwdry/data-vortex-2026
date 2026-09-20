"""
Data Vortex -- Round 3
Shared configuration for the live-monitoring layer.

Round 1+2 convention, kept: every constant that encodes an ANALYST DECISION
lives here so judges can inspect, change and re-run the pipeline in one place.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Identity / reproducibility
# ---------------------------------------------------------------------------
TEAM_NAME = "Forge-X"
TEAM_MEMBERS = ["Kunal Choudhary"]
EVENT = "Aaruush'26"
IST = timezone(timedelta(hours=5, minutes=30))   # single display timezone

# ---------------------------------------------------------------------------
# D1 -- THE TOPIC.  Refuses to run a real sweep while unset, so nobody
#       accidentally ships data collected around the wrong subject.
#       Set by the organisers' assignment, e.g.:
#       TOPIC = "AI chatbots"       QUERIES driven off it below.
# ---------------------------------------------------------------------------
TOPIC: str | None = None          # <-- set the moment organisers assign it
TOPIC_SLUG: str | None = None     # short filesystem-safe tag, e.g. "ai_chatbots"

# ---------------------------------------------------------------------------
# D2 -- collection window (IST, closed interval).  Rulebook: 20-22 Sept.
# ---------------------------------------------------------------------------
# D2a -- collection spans the full results ARC: retro (13-19 Sept, events
#        already played: Asia Cup title 13th, trophy standoff, 18th QF win)
#        plus the live window (20-22 Sept, SF + gold-medal match).
#        ARC_SPLIT divides the dataset; every record is tagged with its arc,
#        and the report's Time Window section declares both explicitly.
WINDOW_START_IST = datetime(2026, 9, 13, 0, 0, tzinfo=IST)
ARC_SPLIT_IST    = datetime(2026, 9, 20, 0, 0, tzinfo=IST)
WINDOW_END_IST   = datetime(2026, 9, 22, 20, 30, tzinfo=IST)

# ---------------------------------------------------------------------------
# D3 -- query terms per source.  Derived from TOPIC once it is known; the
#       synonyms below are the pattern (main term + 2-3 surface variants +
#       hashtags for Mastodon).  Placeholder until D1 is set.
# ---------------------------------------------------------------------------
NEWS_QUERIES: list[str] = []      # Google News RSS search phrases
MASTODON_TAGS: list[str] = []     # hashtags, no '#'
HN_QUERIES: list[str] = []        # Algolia front-end query strings
GDELT_QUERIES: list[str] = []     # GDELT doc-api phrases (best-effort source)

def set_topic(topic: str, slug: str, news: list[str], tags: list[str],
              hn: list[str], gdelt: list[str] | None = None) -> None:
    """One-call topic bootstrap so a sweep can be launched with no code edits."""
    global TOPIC, TOPIC_SLUG, NEWS_QUERIES, MASTODON_TAGS, HN_QUERIES, GDELT_QUERIES
    TOPIC, TOPIC_SLUG = topic, slug
    NEWS_QUERIES, MASTODON_TAGS, HN_QUERIES = news, tags, hn
    GDELT_QUERIES = gdelt or news[:2]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_R3      = ROOT / "data" / "round3"
LIVE_DIR     = DATA_R3 / "live"                 # raw JSONL + exported CSV
SEEN_FILE    = LIVE_DIR / "seen_ids.json"       # dedup state (source -> ids)
POSTS_JSONL  = LIVE_DIR / "posts.jsonl"
DATASET_CSV  = DATA_R3 / "round3_live_dataset.csv"   # deliverable #1
SWEEP_LOG    = LIVE_DIR / "sweep_log.jsonl"          # one line per sweep
OUT_R3       = ROOT / "output" / "round3"
MODELS_DIR   = ROOT / "models" / "round2"        # Round 2 winners, reused (D6)

# ---------------------------------------------------------------------------
# D4 -- politeness / limits.  Every source is fetched with a timeout, a
#       descriptive User-Agent, and per-source error isolation: one flaky
#       source never kills a sweep.
# ---------------------------------------------------------------------------
USER_AGENT  = "ForgeX-DataVortex-R3/1.0 (academic competition data collection)"
HTTP_TIMEOUT = 15          # seconds per request
MAX_TAGS_MASTODON = 4      # per sweep
MAX_HITS_HN = 60           # per sweep, per query
MAX_NEWS_PER_QUERY = 40    # RSS <item> cap per query
GDELT_MAX = 25             # best-effort; 429s are logged, never fatal
RATE_LIMIT_SLEEP = 1.5     # seconds between any two requests

# D3c -- volume levers, all on-topic (added 20 Sept for corpus depth):
GNEWS_CAP_EN = 50          # per English query (feed offers up to 100)
GNEWS_CAP_HI = 100         # Hindi edition returns up to 100 per query
BING_CAP = 25              # per Bing News query (different index than Google)
HINDU_FEED_CAP = 60        # publisher feed; client-side topic filter below
HINDU_TOPIC_FILTER = ["asian games", "india women", "harmanpreet", "mandhana",
                      "shafali", "trophy", "naqvi", "kabaddi", "sindhu",
                      "hockey india", "asian games medal"]

# ---------------------------------------------------------------------------
# D5 -- Round 2 model reuse (the rulebook explicitly asks for it):
#       sentiment_best.pkl scores every live text; the Round-2 label set
#       (Negative/Neutral/Positive) is carried through unchanged.
# ---------------------------------------------------------------------------
SENTIMENT_MODEL = MODELS_DIR / "sentiment_best.pkl"
TOPIC_MODEL     = MODELS_DIR / "topic_best.pkl"   # bonus: round-2 topic classes

# ---------------------------------------------------------------------------
# D6 -- honesty rules for "self-collected":
#       - every record keeps its PLATFORM created_at (UTC) AND the sweep time
#       - the sweep log records HTTP outcomes per source; no silent retries
#       - dedup is by (source, id); edits/reposts of the same id never dup
#       - nothing outside [WINDOW_START, WINDOW_END] enters the dataset
# ---------------------------------------------------------------------------
STRICT_WINDOW_FILTER = True

# ---------------------------------------------------------------------------
# topic bootstrap (module level so every entry point inherits it)
# ---------------------------------------------------------------------------
# ---- ASSIGNED TOPIC (Team allotment, Round 3): ------------------------------
# "Public Reaction to a Major Sports/Event Result"
# -> the major results inside our window are India Women's cricket matches at
#    the Aichi-Nagoya Asian Games 2026 (defending champions, fresh off their
#    8th Asia Cup title on 13 Sept):
#      * 20 Sept, 10:30 IST  semi-final  India vs Bangladesh
#      * 22 Sept, 10:30 IST  GOLD-MEDAL match (India qualified by beating
#        Japan 8 wkts in the QF on 18 Sept)
#    Background triggers tracked alongside: the Asia Cup trophy standoff
#    (ongoing news), and the Rohit-Kohli West Indies ODI sellout buzz.
# D3d -- breadth additions (same topic, more index surface):
#   Hindi edition: cricket reaction in India is majority-Hindi online
NEWS_QUERIES_HI = [
    "भारत महिला क्रिकेट एशियाई खेल",
    "एशियाई खेल 2026 क्रिकेट",
    "हरमनप्रीत कौर",
    "एशिया कप ट्रॉफी नकवी",
    "एशियाई खेल भारत मेडल",
    "शफाली वर्मा शतक", "मंडाना रिकॉर्ड",
    "भारत श्रीलंका महिला फाइनल",
    "एशियाई खेल मेडल तालिका भारत",
    "एशियाई खेल भारत हॉकी कबड्डी",
    "टीम इंडिया महिला क्रिकेट", "एशियाई खेल भारत निशानेबाजी",
    "सिंधु बैडमिंटन एशियाई खेल", "भारत कबड्डी विश्व चैंपियन",
]
#   Bing News: independent index from Google -> new unique items per query
BING_QUERIES = [
    "India women cricket Asian Games",
    "Asian Games 2026 India medal",
    "Harmanpreet Kaur",
    "India hockey Asian Games",
    "India kabaddi Asian Games",
    "Sindhu badminton Asian Games",
    "Asia Cup trophy Naqvi",
    "India shooting Asian Games",
    "Shafali Verma century Asian Games", "Mandhana T20I record",
    "India Sri Lanka women final Asian Games", "India medal tally Asian Games",
]
# D3e -- GLOBAL comparison slice (bounded, scope-tagged): the same window
#   contains other nations' major results. Adding these lets the report place
#   the Indian reaction in comparative context (activity + sentiment profile),
#   which is exactly the literal assigned topic. NOT a second study - a slice.
GLOBAL_QUERIES = [
    "China Asian Games gold medal",
    "Japan Asian Games gold medal hosts",
    "South Korea Asian Games medal",
    "England One Day Cup final",
    "Pakistan Sri Lanka Asian Games semi final",
    "Asian Games medal table record",
    "Yu Zidi Asian Games swim",
    "Japan Korea basketball Asian Games final",
    "Korea archery Asian Games",
    "China swimming Asian Games record",
    "Middlesex One Day Cup Glamorgan Horley",
    "Athapaththu Sri Lanka women Asian Games",
    "Pakistan women cricket Asian Games",
    "Asian Games football result",
    "Asian Games volleyball result",
    "Chinese swimmer Asian Games record",
]
# D3f -- comparison-slice scaling: native-language editions so the global
#   slice is a usable stratified sample (per-nation), not a token gesture.
#   Full parity with the India slice is deliberately NOT pursued: the assigned
#   operating focus is the Indian fanbase reaction; parity-by-padding would
#   dilute topical relevance. Fair statistics instead: India is downsampled to
#   the global slice's n in the comparison tests (documented in the report).
GLOBAL_EDITIONS = [
    # (source_tag, queries, hl, gl, ceid, cap)
    ("gnews_ja",
     ["アジア競技大会 日本 代表", "アジア競技大会 メダル",
      "アジア競技大会 バスケットボール 決勝", "アジア競技大会 水泳"],
     "ja", "JP", "JP:ja", 60),
    ("gnews_ko",
     ["아시아경기대회 한국 금메달", "아시아경기대회 농구 우승",
      "아시아경기대회 메달 순위", "아시아경기대회 한국 대표팀"],
     "ko", "KR", "KR:ko", 60),
    ("gnews_zh",
     ["亞運會 中國 金牌", "亞運會 獎牌榜",
      "亞運會 中國 游泳", "亞運會 日本 韓國"],
     "zh-Hant", "TW", "TW:zh-Hant", 60),
]
GLOBAL_BING = [
    "Asian Games China gold record", "Japan Korea basketball final Asian Games",
    "Yu Zidi Chinese swimmer", "England One Day Cup final result",
]

#   Publisher feed (client-side topic-filtered to stay on-subject)
PUBLISHER_FEEDS = [
    ("thehindu_cricket", "https://www.thehindu.com/sport/cricket/feeder/default.rss"),
    ("sportstar_cricket", "https://sportstar.thehindu.com/cricket/feeder/default.rss"),
    ("ht_sports", "https://www.hindustantimes.com/feeds/rss/sports/rssfeed.xml"),
    ("espncricinfo", "https://www.espncricinfo.com/rss/content/story/feeds/1.xml"),
]

set_topic(
    topic="Public Reaction to a Major Sports/Event Result - "
          "India Women's Cricket at the Asian Games 2026",
    slug="asian_games_womens_cricket",
    news=[
        "India women cricket Asian Games",
        "Asian Games 2026 cricket India",
        "Harmanpreet Kaur Asian Games",
        "India women semi final Asian Games",
        "Asian Games India gold medal cricket",
        "Asia Cup trophy Mohsin Naqvi",
        "Smriti Mandhana record", "Shafali Verma century",
        "India Sri Lanka women cricket final", "Deepti Sharma India",
        "India women cricket team", "Asian Games medal tally India",
        "India athletics Asian Games", "India boxing Asian Games",
        "India table tennis Asian Games", "India wushu Asian Games",
        "Aichi Nagoya India Asian Games",
        "Jemimah Rodrigues India", "Richa Ghosh India",
        "Sree Charani India", "India women Sri Lanka final",
        "Asian Games India day", "India teqball Asian Games",
        "India rowing Asian Games", "India men cricket Asian Games",
        "India gymnastics Asian Games", "India tennis Asian Games",
        # multi-sport halo (same Games, same window - D3b):
        "India Asian Games medal",
        "India hockey Asian Games",
        "India kabaddi Asian Games",
        "India badminton Asian Games Sindhu",
        "Asian Games shooting India medal",
    ],
    tags=["AsianGames2026", "AsianGames", "TeamIndia", "cricket",
          "kabaddi", "badminton", "hockey",
          "Nagoya2026", "AichiNagoya", "womenscricket", "INDvSL"],
    hn=["Asian Games"],
    gdelt=["India women cricket Asian Games", "Asian Games cricket gold medal"],
)
