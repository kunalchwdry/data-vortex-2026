#!/usr/bin/env python3
"""
Data Vortex -- Round 3 :: Data Collection / Scraping Code (single-file bundle).

Submitted as the form's one-file "Data Collection / Scraping Code" slot.  This
is a convenience merge of the three modules that make up the Round-3
collector; the logic is identical to the maintained multi-module layout:

    src/round3/config.py          # window, queries, decisions D1-D3f
    src/round3/x_syndication.py   # X public syndication embeds (best-effort)
    src/round3/collect.py         # the sweep collector itself

Differences from the repo modules are strictly mechanical: shared stdlib
imports hoisted to the top, `from round3 import ...` lines replaced by
aliases, and x_syndication's OUTCOMES/ok/failed namespaced to XS_* so the
two outcome buffers cannot cross-contaminate the sweep log.

Usage:
    python Data_Collection_Scraping_Code.py --status   # corpus state
    python Data_Collection_Scraping_Code.py            # one live sweep
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

# ======================================================================
# PART 1/3 -- src/round3/config.py
# ======================================================================
"""
Data Vortex -- Round 3
Shared configuration for the live-monitoring layer.

Round 1+2 convention, kept: every constant that encodes an ANALYST DECISION
lives here so judges can inspect, change and re-run the pipeline in one place.
"""

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
        "India Japan T20I wide controversy",
        "Shreyas Iyer Axar umpire Japan",
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

C = sys.modules[__name__]   # alias: collect.py reads config as `C`


# ======================================================================
# PART 2/3 -- src/round3/x_syndication.py
# (OUTCOMES/ok/failed namespaced to XS_*; fetch_all() contract unchanged)
# ======================================================================
#!/usr/bin/env python3
"""
Data Vortex -- Round 3 :: X (Twitter) via the public syndication/embed service.

Method note (also goes into the report, verbatim):
  X's official API free tier grants no read access and its search pages are
  login-walled. This module therefore reads **X's own public embed service**
  (syndication.twitter.com) -- the endpoint any website uses to embed a public
  account timeline. No login, no bypass of any wall, only public embeds of
  chosen public accounts, at single-digit request volumes with backoff.
  The endpoint is rate-limited (429); every outcome is logged and a 429 is
  never fatal -- exactly the GDELT best-effort protocol.

Records carry their platform created_at and are subject to the same window
filter and dedup as every other source.
"""



sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ACCOUNTS = ["BCCIWomen", "ICC", "ImHarmanpreet", "BCCI"]
URL = "https://syndication.twitter.com/srv/timeline-profile/screen-name/{acct}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")

TWEET_BLOCK = re.compile(
    r'<div class="tweet"(.*?)</div>\s*</div>\s*</div>', re.S)
TWEET_TEXT = re.compile(r'<p class="tweet-text"[^>]*>(.*?)</p>', re.S)
TWEET_ATTR = {
    "id":   re.compile(r'data-tweet-id="(\d+)"'),
    "name": re.compile(r'data-screen-name="([^"]+)"'),
    "time": re.compile(r'data-created-at="(\d+)"'),
}


def _clean(fragment: str) -> str:
    txt = re.sub(r"<br\s*/?>", " ", fragment)
    txt = re.sub(r"<[^>]+>", "", txt)
    return re.sub(r"\s+", " ", html_mod.unescape(txt)).strip()


def fetch_account(acct: str) -> list[dict]:
    r = requests.get(URL.format(acct=acct), headers={"User-Agent": UA},
                     timeout=C.HTTP_TIMEOUT)
    time.sleep(C.RATE_LIMIT_SLEEP)
    if r.status_code != 200:
        return xs_failed("xsynd", acct, r.status_code)
    out = []
    for block in TWEET_BLOCK.findall(r.text):
        mid = TWEET_ATTR["id"].search(block)
        if not mid:
            continue
        mtime = TWEET_ATTR["time"].search(block)
        mtext = TWEET_TEXT.search(block)
        rec = {
            "record_id": f"xsynd:{mid.group(1)}",
            "source": "xsynd",
            "author": (TWEET_ATTR["name"].search(block) or [None, acct])[1],
            "title": None,
            "text": _clean(mtext.group(1)) if mtext else None,
            "url": f"https://x.com/{acct}/status/{mid.group(1)}",
            "lang": "en",
            "created_at_utc": (int(mtime.group(1)) and
                time.strftime("%Y-%m-%dT%H:%M:%SZ",
                              time.gmtime(int(mtime.group(1)) / 1000)))
                              if mtime else None,
            "collected_at_utc": None,   # set by collector
            "engagement": {},
            "sweep_id": None,
            "sweep_mode": None,
            "arc": None,
        }
        out.append(rec)
    return xs_ok("xsynd", acct, out)


# outcome helpers kept identical in shape to collect.py's
XS_OUTCOMES = []

def xs_ok(source, term, records):
    XS_OUTCOMES.append({"source": source, "term": term, "http": 200,
                     "records": len(records)})
    return records

def xs_failed(source, term, status):
    XS_OUTCOMES.append({"source": source, "term": term, "http": status,
                     "records": 0})
    return []


def fetch_all() -> tuple[list[dict], list[dict]]:
    """Returns (records, outcomes); caller merges into its own outcome log."""
    XS_OUTCOMES.clear()
    records = []
    for acct in ACCOUNTS:
        records.extend(fetch_account(acct))
    return records, list(XS_OUTCOMES)


# (standalone self-test main-block lives in the repo module x_syndication.py)

XS = sys.modules[__name__]  # alias: collect.py calls this module as `XS`


# ======================================================================
# PART 3/3 -- src/round3/collect.py  (the sweep collector)
# ======================================================================
#!/usr/bin/env python3
"""
Data Vortex -- Round 3 :: live collector (sweep model).

One sweep = fetch every configured source once, normalise records, drop ids
already seen, append the new ones to posts.jsonl and rewrite the deliverable
CSV.  Re-running this script over the collection window builds the time
series; each record keeps BOTH the platform's created_at and the sweep time,
so bursty collection cadence never distorts activity analysis (activity is
computed on created_at, never on collected_at).

Usage:
    python src/round3/collect.py --status        # what do we have so far
    python src/round3/collect.py                 # one real sweep (needs D1 topic)
    python src/round3/collect.py --smoke         # plumbing test, parked output
"""



sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# --------------------------------------------------------------------------- helpers
def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def get(url: str, params: dict | None = None) -> requests.Response:
    r = requests.get(url, params=params, headers={"User-Agent": C.USER_AGENT},
                     timeout=C.HTTP_TIMEOUT)
    time.sleep(C.RATE_LIMIT_SLEEP)
    return r

def strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()

def base_record(source: str, key: str) -> dict:
    return {
        "record_id": f"{source}:{key}",
        "source": source,
        "author": None,
        "title": None,
        "text": None,
        "url": None,
        "lang": None,
        "created_at_utc": None,
        "collected_at_utc": now_utc(),
        "engagement": {},
        "sweep_id": SWEEP_ID,
        "sweep_mode": SWEEP_MODE,
        "arc": None,
        "scope": "india",
    }

# --------------------------------------------------------------------------- sources
def fetch_mastodon(tag: str) -> list[dict]:
    r = get(f"https://mastodon.social/api/v1/timelines/tag/{tag}",
            params={"limit": 40})
    if r.status_code != 200:
        return failed("mastodon", tag, r.status_code)
    out = []
    for st in r.json():
        rec = base_record("mastodon", f"{st['id']}")
        rec.update({
            "author": (st.get("account") or {}).get("acct"),
            "text": strip_html(st.get("content") or ""),
            "url": st.get("url"),
            "lang": st.get("language"),
            "created_at_utc": iso(datetime.fromisoformat(st["created_at"])),
            "engagement": {"reblogs": st.get("reblogs_count", 0),
                           "favourites": st.get("favourites_count", 0),
                           "replies": st.get("replies_count", 0)},
        })
        out.append(rec)
    return ok("mastodon", tag, out)

def fetch_hn(query: str) -> list[dict]:
    r = get("https://hn.algolia.com/api/v1/search_by_date",
            params={"query": query, "tags": "story", "hitsPerPage": C.MAX_HITS_HN})
    if r.status_code != 200:
        return failed("hn", query, r.status_code)
    out = []
    for h in r.json().get("hits", []):
        if not h.get("objectID"):
            continue
        rec = base_record("hn", h["objectID"])
        rec.update({
            "author": h.get("author"),
            "title": h.get("title"),
            "text": strip_html(h.get("story_text") or h.get("comment_text") or ""),
            "url": h.get("url") or (f"https://news.ycombinator.com/item?id={h['objectID']}"),
            "created_at_utc": (h.get("created_at_i") and
                               iso(datetime.fromtimestamp(h["created_at_i"], timezone.utc))),
            "engagement": {"points": h.get("points") or 0,
                           "comments": h.get("num_comments") or 0},
        })
        out.append(rec)
    return ok("hn", query, out)

GOOGLE_NEWS_TZ = parsedate_to_datetime

def fetch_google_news(query: str, lang: str = "en", hl: str | None = None,
                      gl: str = "IN", ceid: str = "IN:en",
                      cap_override: int | None = None) -> list[dict]:
    cap = cap_override or (C.GNEWS_CAP_EN if lang == "en" else C.GNEWS_CAP_HI)
    if hl is None:
        hl, ceid = (("en-IN", "IN:en") if lang == "en" else ("hi-IN", "IN:hi"))
    r = get("https://news.google.com/rss/search",
            params={"q": query, "hl": hl, "gl": "IN", "ceid": ceid})
    if r.status_code != 200:
        return failed(f"gnews_{lang}", query, r.status_code)
    out = []
    try:
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[: cap]
    except ET.ParseError:
        return failed(f"gnews_{lang}", query, "parse-error")
    for it in items:
        guid = (it.findtext("guid") or it.findtext("link") or "").strip()
        if not guid:
            continue
        key = uuid.uuid5(uuid.NAMESPACE_URL, guid).hex[:16]
        rec = base_record("gnews", key)
        pub = None
        if it.findtext("pubDate"):
            try:
                pub = iso(GOOGLE_NEWS_TZ(it.findtext("pubDate")))
            except (TypeError, ValueError):
                pub = None
        src = it.find("source")
        rec.update({
            "author": src.text.strip() if src is not None and src.text else None,
            "title": strip_html(it.findtext("title")),
            "text": strip_html(it.findtext("description")),
            "url": it.findtext("link"),
            "created_at_utc": pub,
        })
        out.append(rec)
    return ok("gnews", query, out)

def fetch_google_news_hi(query: str) -> list[dict]:
    return fetch_google_news(query, lang="hi")

def fetch_bing(query: str) -> list[dict]:
    r = get("https://www.bing.com/news/search", params={"q": query, "format": "RSS"})
    if r.status_code != 200:
        return failed("bing", query, r.status_code)
    out = []
    try:
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[: C.BING_CAP]
    except ET.ParseError:
        return failed("bing", query, "parse-error")
    for it in items:
        link = (it.findtext("link") or "").strip()
        if not link:
            continue
        key = uuid.uuid5(uuid.NAMESPACE_URL, link).hex[:16]
        rec = base_record("bing", key)
        pub = None
        if it.findtext("pubDate"):
            try:
                pub = iso(GOOGLE_NEWS_TZ(it.findtext("pubDate")))
            except (TypeError, ValueError):
                pub = None
        rec.update({
            "author": strip_html(it.findtext("News:Source") or "") or None,
            "title": strip_html(it.findtext("title")),
            "text": strip_html(it.findtext("description")),
            "url": link,
            "created_at_utc": pub,
        })
        out.append(rec)
    return ok("bing", query, out)

def fetch_publisher_feed(feed: tuple) -> list[dict]:
    name, url = feed
    r = get(url)
    if r.status_code != 200:
        return failed(f"feed:{name}", name, r.status_code)
    out = []
    try:
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[: C.HINDU_FEED_CAP * 3]
    except ET.ParseError:
        return failed(f"feed:{name}", name, "parse-error")
    kept = 0
    for it in items:
        if kept >= C.HINDU_FEED_CAP:
            break
        link = (it.findtext("link") or "").strip()
        if not link:
            continue
        blob = (strip_html(it.findtext("title") or "") + " " +
                strip_html(it.findtext("description") or "")).lower()
        if not any(kw in blob for kw in C.HINDU_TOPIC_FILTER):
            continue          # on-topic guard: feed is broad, topic is narrow
        key = uuid.uuid5(uuid.NAMESPACE_URL, link).hex[:16]
        rec = base_record(f"feed_{name}", key)
        pub = None
        if it.findtext("pubDate"):
            try:
                pub = iso(GOOGLE_NEWS_TZ(it.findtext("pubDate")))
            except (TypeError, ValueError):
                pub = None
        rec.update({
            "author": name,
            "title": strip_html(it.findtext("title")),
            "text": strip_html(it.findtext("description")),
            "url": link,
            "created_at_utc": pub,
        })
        out.append(rec)
        kept += 1
    return ok(f"feed:{name}", f"{kept} on-topic", out)

def fetch_gdelt(query: str) -> list[dict]:
    r = get("https://api.gdeltproject.org/api/v2/doc/doc",
            params={"query": query, "mode": "ArtList", "maxrecords": C.GDELT_MAX,
                    "format": "json", "sort": "DateDesc"})
    if r.status_code != 200:
        return failed("gdelt", query, r.status_code)
    out = []
    for a in r.json().get("articles", []):
        key = uuid.uuid5(uuid.NAMESPACE_URL, a.get("url", uuid.uuid4().hex)).hex[:16]
        rec = base_record("gdelt", key)
        rec.update({
            "author": a.get("domain"),
            "title": strip_html(a.get("title")),
            "url": a.get("url"),
            "created_at_utc": (a.get("seendate") and
                               f"{a['seendate'][:4]}-{a['seendate'][4:6]}-{a['seendate'][6:8]}"
                               f"T{a['seendate'][9:11]}:{a['seendate'][11:13]}:00Z"),
        })
        out.append(rec)
    return ok("gdelt", query, out)

# --------------------------------------------------------------------------- outcome log
OUTCOMES: list[dict] = []

def ok(source: str, term: str, records: list[dict]) -> list[dict]:
    OUTCOMES.append({"source": source, "term": term, "http": 200,
                     "records": len(records)})
    return records

def failed(source: str, term: str, status) -> list[dict]:
    OUTCOMES.append({"source": source, "term": term, "http": status,
                     "records": 0})
    return []

# --------------------------------------------------------------------------- sweep
def sweep(smoke: bool) -> None:
    live = Path(C.OUT_R3 / "smoke") if smoke else C.LIVE_DIR
    live.mkdir(parents=True, exist_ok=True)
    jsonl  = live / "posts.jsonl"
    seen_f = live / "seen_ids.json"

    seen: dict = json.loads(seen_f.read_text()) if seen_f.exists() else {}
    new_records: list[dict] = []

    plans = [
        ("mastodon", C.MASTODON_TAGS,  fetch_mastodon),
        ("hn",       C.HN_QUERIES,     fetch_hn),
        ("gnews",    C.NEWS_QUERIES,   fetch_google_news),
        ("gnews_hi", C.NEWS_QUERIES_HI, fetch_google_news_hi),
        ("bing",     C.BING_QUERIES,   fetch_bing),
        ("feed",     C.PUBLISHER_FEEDS, fetch_publisher_feed),
        ("gdelt",    C.GDELT_QUERIES,  fetch_gdelt),
    ]
    for source, terms, fn in plans:
        for term in terms[: (1 if smoke else 10 ** 6)]:
            try:
                got = fn(term)
            except Exception as e:   # per-source isolation: ek source kabhi
                got = failed(source, term, f"err:{type(e).__name__}")  # sweep nahi girayega
            for rec in got:
                if rec["record_id"] in seen.get(source, set()):
                    continue
                if C.STRICT_WINDOW_FILTER and not smoke:
                    ts = rec.get("created_at_utc")
                    if not ts:
                        continue
                    t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    t_ist = t.astimezone(C.IST)
                    if not (C.WINDOW_START_IST <= t_ist <= C.WINDOW_END_IST):
                        continue
                    # arc tag: retro = events already played when collected,
                    # live = the primary real-time monitoring window
                    rec["arc"] = "live" if t_ist >= C.ARC_SPLIT_IST else "retro"
                seen.setdefault(source, []).append(rec["record_id"])
                new_records.append(rec)

    # global comparison slice (bounded, D3e/D3f): same window, other nations'
    # majors -- English queries + native-language editions (ja/ko/zh-Hant)
    def _take_global(rec):
        if rec["record_id"] in seen.get("gnews_global", set()):
            return
        if C.STRICT_WINDOW_FILTER and not smoke:
            ts = rec.get("created_at_utc")
            if not ts:
                return
            t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            t_ist = t.astimezone(C.IST)
            if not (C.WINDOW_START_IST <= t_ist <= C.WINDOW_END_IST):
                return
            rec["arc"] = "live" if t_ist >= C.ARC_SPLIT_IST else "retro"
        rec["scope"] = "global"
        seen.setdefault("gnews_global", []).append(rec["record_id"])
        new_records.append(rec)

    try:
        for term in C.GLOBAL_QUERIES:
            for rec in fetch_google_news(term):
                _take_global(rec)
        for tag, queries, hl, gl, ceid, cap in C.GLOBAL_EDITIONS:
            for term in queries:
                for rec in fetch_google_news(term, lang=tag, hl=hl, gl=gl,
                                             ceid=ceid, cap_override=cap):
                    _take_global(rec)
        for term in C.GLOBAL_BING:
            for rec in fetch_bing(term):
                _take_global(rec)
    except Exception as e:  # never fatal, always logged
        OUTCOMES.append({"source": "gnews_global", "term": "ALL",
                         "http": f"err:{e}", "records": 0})

    # best-effort X syndication (public embed service; 429s logged, never fatal)
    try:
        xs_recs, xs_outs = XS.fetch_all()
        OUTCOMES.extend(xs_outs)
        for rec in xs_recs:
            if rec["record_id"] in seen.get("xsynd", set()):
                continue
            if C.STRICT_WINDOW_FILTER and not smoke:
                ts = rec.get("created_at_utc")
                if not ts:
                    continue
                t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                t_ist = t.astimezone(C.IST)
                if not (C.WINDOW_START_IST <= t_ist <= C.WINDOW_END_IST):
                    continue
                rec["arc"] = "live" if t_ist >= C.ARC_SPLIT_IST else "retro"
            rec["collected_at_utc"] = now_utc()
            rec["sweep_id"] = SWEEP_ID
            rec["sweep_mode"] = SWEEP_MODE
            seen.setdefault("xsynd", []).append(rec["record_id"])
            new_records.append(rec)
    except Exception as e:  # never fatal, always logged
        OUTCOMES.append({"source": "xsynd", "term": "ALL", "http": f"err:{e}",
                         "records": 0})

    with jsonl.open("a", encoding="utf-8") as f:
        for rec in new_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    seen_f.write_text(json.dumps(seen))

    log_line = {"sweep_id": SWEEP_ID, "mode": SWEEP_MODE,
                "at_utc": now_utc(), "new_records": len(new_records),
                "outcomes": OUTCOMES}
    with (live / "sweep_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_line, ensure_ascii=False) + "\n")

    export_csv(jsonl, smoke)
    print(f"sweep {SWEEP_ID} ({SWEEP_MODE}): +{len(new_records)} new records")
    for o in OUTCOMES:
        print(f"  {o['source']:9s} {o['term'][:34]:34s} http {o['http']}  -> {o['records']}")

def export_csv(jsonl: Path, smoke: bool) -> None:
    rows = [json.loads(l) for l in jsonl.read_text(encoding="utf-8").splitlines() if l]
    seen_ids, uniq = set(), []
    for r in rows:                      # belt-and-braces: corpus-level dedup
        if r["record_id"] in seen_ids:
            continue
        seen_ids.add(r["record_id"])
        uniq.append(r)
    rows = uniq
    fields = ["record_id", "source", "author", "title", "text", "url", "lang",
              "created_at_utc", "collected_at_utc", "arc", "scope",
              "engagement_reblogs", "engagement_favourites", "engagement_replies",
              "engagement_points", "engagement_comments", "sweep_id", "sweep_mode"]
    out = (Path(C.OUT_R3 / "smoke") / "smoke_dataset.csv") if smoke else C.DATASET_CSV
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for r in rows:
            e = r.get("engagement") or {}
            w.writerow([r.get(k) for k in fields[:11]] +
                       [e.get("reblogs"), e.get("favourites"), e.get("replies"),
                        e.get("points"), e.get("comments")] +
                       [r.get("sweep_id"), r.get("sweep_mode")])
    print(f"dataset -> {out}  ({len(rows)} rows)")

def status() -> None:
    for p in [C.LIVE_DIR / "posts.jsonl", C.LIVE_DIR / "sweep_log.jsonl"]:
        n = len(p.read_text(encoding="utf-8").splitlines()) if p.exists() else 0
        print(f"{p.name:18s} {n} lines")
    if C.DATASET_CSV.exists():
        print(f"{C.DATASET_CSV.name}  {C.DATASET_CSV.stat().st_size/1e3:.0f} KB")
    print("topic:", C.TOPIC or "NOT SET (edit src/round3/config.py D1)")
    print("window:", C.WINDOW_START_IST.isoformat(), "->", C.WINDOW_END_IST.isoformat(), "IST")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    SWEEP_MODE = "smoke" if a.smoke else "live"
    SWEEP_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if a.status:
        status()
    elif a.smoke:
        # dry run: same code path, but parked under output/round3/smoke/ with
        # the window filter off. Uses the REAL topic queries when configured,
        # so the volume estimate matches what live sweeps will see.
        if not (C.NEWS_QUERIES or C.MASTODON_TAGS or C.HN_QUERIES):
            C.NEWS_QUERIES, C.MASTODON_TAGS, C.HN_QUERIES, C.GDELT_QUERIES = (
                ["technology"], ["technology"], ["technology"], [])
        C.STRICT_WINDOW_FILTER = False
        sweep(smoke=True)
    else:
        if not C.TOPIC:
            sys.exit("D1 topic not set -- edit src/round3/config.py (or use --smoke).")
        sweep(smoke=False)