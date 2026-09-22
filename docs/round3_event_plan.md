# Round 3 — Event Plan & Trigger Calendar

**Assigned topic (Team Forge-X, Round 3 allotment):**
*Public Reaction to a Major Sports/Event Result*

**Operating definition chosen:** the major results inside the collection window
are **India Women's cricket matches at the Aichi-Nagoya Asian Games 2026**
(India = defending Asian Games champions AND fresh off their 8th Women's Asia
Cup title, won 13 Sept 2026). This gives the study a clean experiment design:
one fan community, two high-stakes results, three days.

## Time window (decision D2, `src/round3/config.py`)

```
2026-09-20 00:00 IST  ->  2026-09-22 20:30 IST   (~68.5 h)
```

Deadline is 22 Sept 23:59 IST; the window closes at 20:30 to leave a fixed
build+QA slot for the report. Nothing outside the window enters the dataset
(`STRICT_WINDOW_FILTER`).

## Scheduled events inside the window (the trigger calendar)

| when (IST) | event | expected effect on the metrics |
|---|---|---|
| 20 Sept, 05:30 | SF1: Pakistan vs Sri Lanka | minor; context for final's opponent |
| **20 Sept, 10:30** | **SF2: India vs Bangladesh** | **shift candidate #1** — result lands ~13:30–14:00; reaction wave through the evening |
| 21 Sept | no India match | baseline day; residual SF reaction, preview chatter |
| 22 Sept, 05:30 | bronze-medal match | minor (only if India lost SF) |
| **22 Sept, 10:30** | **GOLD-MEDAL match (India qualified: beat Japan by 8 wkts in the 18 Sept QF)** | **shift candidate #2 + engagement spike** — result ~13:45–14:15, medal ceremony, record-chasing reaction till window close |

**Background triggers tracked alongside** (may modulate sentiment without a
match): the Asia Cup trophy standoff (India declined the trophy from the ACC
president; BCCI AGM statements filed 19 Sept), the Rohit–Kohli West Indies
ODI sellout buzz (series starts 27 Sept, outside the window), and the Indian
contingent's general Asian Games medal flow.

**Pre-window context (documented, not collected as data):** Asia Cup title
13 Sept; QF win over Japan 18 Sept; both are the baseline the in-window
reaction is measured against.

## Sources (all keyless, verified reachable from the collection host)

| source | what | per-sweep cap |
|---|---|---|
| Google News RSS (`IN` edition) | news headlines + summaries, 5 topic queries | 40 items × 5 queries |
| Mastodon (`mastodon.social`) | public hashtag timelines: `AsianGames2026`, `AsianGames`, `TeamIndia`, `cricket` | 40 posts × 4 tags |
| Hacker News (Algolia API) | global tech-audience cross-section, query "Asian Games" | 60 stories |
| GDELT doc API (best-effort) | global news monitor; 429s are logged, never fatal | 25 articles × 2 queries |

## Sweep protocol (decision D6 — honesty rules)

1. One sweep = fetch every source once; normalise to one schema; dedup by
   `(source, id)`; append new records to `posts.jsonl`; rewrite the CSV.
2. Every record keeps **both** the platform `created_at_utc` and
   `collected_at_utc`; activity analysis uses `created_at` only, so bursty
   sweep cadence cannot distort the time series.
3. Every HTTP outcome of every source-term is written to `sweep_log.jsonl` —
   no silent retries, no backfilled data.
4. Round 2's trained `sentiment_best.pkl` scores every live text unchanged
   (the rulebook's "apply their NLP model developed in Round 2").

## Planned sweep times (IST)

| day | sweeps |
|---|---|
| 20 Sept | ~09:00 (pre-SF), ~14:15 (post-SF result), ~21:00 (evening wave) |
| 21 Sept | ~10:00 (baseline morning), ~21:00 (previews/night) |
| 22 Sept | ~09:30 (pre-gold), ~14:30 (result), ~17:30 (peak reaction), ~20:15 (window close) |

Contingency: if any sweep is missed, `created_at` timestamps keep the series
valid; if the gold match is rained out / India loses the semi, the bronze
match (22 Sept 05:30) and the SF result become shift candidates #2 and #1
respectively — the design does not depend on India winning.

## Known limitations (declared up front)

- X/Twitter and Reddit are excluded: X's free API tier has no read access and
  Reddit blocks datacenter IPs (403 verified 19 Sept); both were probed, the
  failures are on record. Sources above are the honest keyless frontier.
- HN's "Asian Games" query drags some off-topic stories; the analysis layer
  scores and reports them rather than silently dropping them.
- Google News items are headlines+summaries — short texts, exactly the regime
  the Round 2 sentiment model was trained for (24–158 chars).

## RETRO EXTENSION (adopted 20 Sept): the full results arc

The collection was widened backwards to capture public reaction to the major
results that ALREADY happened before the live window, giving a 10-day
behavioural arc on one fan community:

| date | event | arc |
|---|---|---|
| 13 Sept | Asia Cup final won (8th title) + trophy-standoff begins | retro |
| 14–17 Sept | trophy-controversy news cycle, squad/preview chatter | retro |
| 18 Sept | Asian Games QF: India beat Japan by 8 wkts | retro |
| 19 Sept | SF previews, "India aim to secure cricket medal" cycle | retro |
| **20 Sept, 10:30** | **SF: India vs Bangladesh** | **live** |
| **22 Sept, 10:30** | **gold-medal match** | **live** |

Every record carries `created_at_utc` (when the post/article was published)
and `collected_at_utc` (when our sweep fetched it) plus an `arc` tag
(`retro` / `live`, split at 2026-09-20 00:00 IST, config D2a). The report's
Time Window section declares both windows explicitly: the live monitoring
window is primary (the rulebook's real-time mandate); the retro arc is a
clearly-labelled retrospective extension collected with the same code, same
sources, same schema — no third-party datasets involved.

Sentiment-shift candidates now span the arc: title elation (13th) ->
controversy anger (14–17th) -> routine QF calm (18th) -> pre-SF tension
(19th) -> in-window live shifts on the SF and final results.

## Historical trigger catalog (background, not collected data)

The full two-year context — WC 2023 SF/F, T20 WC 2024 final, Champions Trophy
2025 final, the 2025 men's Asia Cup final v Pakistan + first trophy refusal,
and the 2026 women's repeat — is documented with sources in
[`round3_past_events.md`](round3_past_events.md) (H1–H10). The report's
Trigger Explanations and Interpretation sections lean on it; the dataset
itself remains 13–22 Sept only.

## MULTI-SPORT HALO (added 20 Sept, D3b): one Games, every India result

The assigned topic is "Public Reaction to a Major Sports/Event Result". The
Aichi-Nagoya Asian Games ARE that event-complex: ~35 sports, hundreds of
events. The women's cricket gold race is the SPINE of our study; around it we
capture India's full in-window medal flow via breadth queries ("India Asian
Games medal", hockey, kabaddi, badminton/Sindhu, shooting) and three extra
Mastodon tags. In-window sports already surfacing in the data:

| in window | sports |
|---|---|
| 20 Sept | cricket SF, hockey (M+W openers), women's 10m air rifle final, badminton team opener (Sindhu), teqball bronzes, table tennis, wushu final, swimming, MMA |
| 21 Sept | kabaddi begins (M+W, defending champs), men's 10m air rifle, boxing, badminton team QFs, rowing, karate |
| 22 Sept | cricket medal match, mixed 10m air rifle final, kabaddi group stage, gymnastics AA, shooting finals |

Every India medal/result inside the window is therefore a potential mini-
trigger in the SAME dataset — breadth without scope drift. (Boundary: this is
not 100 separate event datasets; it is one event complex, one topic, one
schema. Athletics/Neeraj-era contexts and past multi-sport events stay in the
historical catalog as background only.)

## Platform exclusion log (verified 20 Sept 2026) -- why IG and X-search are out

| platform / route | probe result | verdict |
|---|---|---|
| X API free tier | HTTP 401; read access not included in free tier (verified 19 Sept) | excluded |
| X web search (anonymous) | HTTP 200 but login-wall shell (298 KB, no tweets) | excluded -- no bypass attempted |
| X public syndication/embed service | HTTP 429 "Rate limit exceeded" x7 over 40 min; CDN timeline 200-empty; tweet-result `{}` | excluded from this host; module kept (`src/round3/x_syndication.py`) as best-effort -- residential IPs may succeed, logged in every sweep either way |
| Instagram hashtag page | HTTP 200 but login-wall shell (628 KB, no posts) | excluded -- no bypass attempted |
| Instagram Graph API | requires user-owned Business/Creator account + app review; Basic Display API retired by Meta (Dec 2024) | infeasible within round window; excluded |
| Reddit JSON API | HTTP 403 from datacenter IP (verified 19 Sept) | excluded from sandbox; documented laptop alternative |

Principle: no login-wall bypass, no unofficial scraping of walled platforms.
Every exclusion is probe-dated so the panel can verify the attempts. The
keyless frontier actually used: Google News RSS, Mastodon, Hacker News,
GDELT (best-effort), X syndication (best-effort).

## GLOBAL COMPARISON SLICE (added 20 Sept evening, D3e): other nations, same window

The assigned topic is generic ("a major sports/event result"); India is our
spine study. To place the Indian reaction in comparative context, a bounded,
scope-tagged slice (`scope=global`, 6 queries) captures OTHER nations' major
results inside the same window:

| nation | in-window majors (already surfacing) |
|---|---|
| China | record-start gold sweep incl. swimmer Yu Zidi's Games record |
| Japan (hosts) | basketball final loss to Korea "spoils host's bid" — the hosts' heartbreak mirror of our 2017 Lord's |
| South Korea | basketball gold over Japan; first-ever modern-pentathlon gold |
| England | One Day Cup final — Middlesex beat Glamorgan (Saskia Horley 100) |
| Pakistan/Sri Lanka | SF1: SL won — Athapaththu 83* |

Analysis use: comparative activity + sentiment profile (India slice vs global
slice per hour). Boundary declared: the comparison slice is context for
Interpretation, not a co-equal study.

**TRIGGER UPGRADE — the gold match is a REMATCH:** SF1 confirmed Sri Lanka
beat Pakistan; the 22 Sept gold-medal match is therefore **India vs Sri
Lanka — the exact fixture of the 13 Sept Asia Cup final** (which India won,
then refused Naqvi's trophy). The decade arc now converges on a repeat
fixture: the report's central trigger narrative writes itself.

## UPDATE (22 Sept): X IS IN — via manual logged-in collection (team member)

The exclusion-log entry for X changes today: a team member manually collected
public X posts during the window (browser, logged-in session) and delivered
two CSVs — India Asian Games reactions (82 rows) and a comparison-set from a
same-window NFL major (Rams v Giants, Aaron Donald's return, 57 rows). Import
protocol (documented, rerunnable):

- **authenticity gate:** every X snowflake id was decoded (id>>22 + Twitter
  epoch) and required to match the stated timestamp within 5 minutes —
  100% of kept rows pass; the timestamp column is UTC.
- **6 placeholder rows (ag_* ids) dropped** — unverifiable provenance; their
  facts are already covered by verified Google-News records.
- merged as `source=x_manual`, engagement (likes/reposts/replies/views)
  carried; India slice -> scope=india, NFL set -> scope=global.
- corpus integrity re-audited: 200 cross-query gnews duplicates found by the
  same audit and removed; an export-level dedup guard is now permanent.

The X-search/syndication exclusion stands for AUTOMATED access; manual
logged-in collection by the team is a different, documented route.

## BONUS TRIGGER (22 Sept): IND v JAPAN one-off T20I — "Wide-gate"

Same evening as the women's gold: India MEN played a historic first-ever
one-off T20I v Japan (Sano) and won by 2 runs amid an umpiring storm —
a wide call in the final over was reversed after Iyer/Axar confronted the
umpires; "Japan robbed" trended on X. Added as in-window trigger #3
(pride/shame bimodal — same shape as the trophy standoff). Queries added;
the evening sweeps capture the reaction wave.
