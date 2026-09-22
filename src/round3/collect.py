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
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from round3 import config as C
from round3 import x_syndication as XS

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
