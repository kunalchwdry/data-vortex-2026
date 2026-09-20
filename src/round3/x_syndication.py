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
from __future__ import annotations

import re
import sys
import time
import html as html_mod
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from round3 import config as C

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
        return failed("xsynd", acct, r.status_code)
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
    return ok("xsynd", acct, out)


# outcome helpers kept identical in shape to collect.py's
OUTCOMES = []

def ok(source, term, records):
    OUTCOMES.append({"source": source, "term": term, "http": 200,
                     "records": len(records)})
    return records

def failed(source, term, status):
    OUTCOMES.append({"source": source, "term": term, "http": status,
                     "records": 0})
    return []


def fetch_all() -> tuple[list[dict], list[dict]]:
    """Returns (records, outcomes); caller merges into its own outcome log."""
    OUTCOMES.clear()
    records = []
    for acct in ACCOUNTS:
        records.extend(fetch_account(acct))
    return records, list(OUTCOMES)


if __name__ == "__main__":
    recs, outs = fetch_all()
    for o in outs:
        print(f"  {o['source']:6s} {o['term']:16s} http {o['http']} -> {o['records']}")
    for r in recs[:5]:
        print(f"[{r['created_at_utc']}] @{r['author']}: {(r['text'] or '')[:70]}")
