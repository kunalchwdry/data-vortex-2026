# Round 3 — Historical Trigger Catalog: India's Big Results, WC 2023 -> Asian Games 2026

*Why this file exists: the Round-3 rubric scores "Interpretation & Real-world
Understanding" and "Trigger Explanations". The public reaction we are
live-monitoring (13–22 Sept 2026) does not happen in a vacuum — it is the
latest beat of a two-year drumroll of high-stakes India results. This catalog
documents that drumroll with verified facts and dates, and maps each past
event onto the behavioural patterns our dataset should expose.*

> **Honesty boundary (the report repeats this):** everything below is
> **documented background** — published match records and news reporting,
> cited per row. It is **not** part of the self-collected dataset. The
> dataset spans **13–22 Sept 2026 only** (`data/round3/round3_live_dataset.csv`);
> the catalog exists so the report can *interpret* the collected reaction,
> never so the two get mixed.

---

## 1. The verified timeline

| # | Date | Event | Result (verified) | Public-reaction signature |
|---|---|---|---|---|
| H1 | 15 Nov 2023 | **ODI World Cup semi-final**, Wankhede, Mumbai | India 397/4 (Kohli 117 — his **50th ODI century**, passing Sachin's 49; Iyer 105 off 70; Shami **7/57**) beat NZ 327 by **70 runs** | Ecstatic, record-gasm night; Kohli bowing to Tendulkar's box became the defining image |
| H2 | 19 Nov 2023 | **ODI World Cup final**, Ahmedabad | India 240 lost to Australia by **6 wickets** (Head 137). India had won **10 straight** coming in | A 1,30,000-seat stadium silenced; nationwide heartbreak; the template for "peak-hope -> overnight grief" the fanbase still remembers |
| H3 | 29 Jun 2024 | **T20 World Cup final**, Bridgetown | India 176/7 (Kohli 76) beat South Africa 169/8 by **7 runs** (Hardik 3/20 incl. the last over; Suryakumar's boundary catch) | Ended an **11-year ICC-title drought**; open-bus Mumbai parade (4 Jul 2024); Kohli + Rohit T20I farewells — the fandom's happiest mass memory of the decade |
| H4 | 9 Mar 2025 | **Champions Trophy final**, Dubai | India beat New Zealand by **4 wickets** (Rohit 76*), unbeaten through the tournament | Back-to-back ICC titles, 2024->2025; Dubai-as-fortress narrative begins |
| H5 | Sep 2025 | **Men's Asia Cup (T20), UAE** — handshake row | India refused handshakes vs Pakistan (group + Super Four); skipper dedicated wins to the armed forces; Pakistan threatened withdrawal, played on | Political sport officially entered the Asia Cup; set the stage for H6 |
| H6 | 28 Sep 2025 | **Men's Asia Cup FINAL: India v Pakistan**, Dubai | India beat Pakistan by **5 wickets** (Tilak Varma 50; Abhishek Sharma player-of-tournament). India then **refused the trophy** from ACC/PCB chief Mohsin Naqvi — lifted an "invisible trophy", took no medals | Viral "invisible trophy" memes; pride-vs-optics split; Naqvi locked the trophy in the ACC office ("only I will hand it over in person") — the origin of the standoff still running today |
| H7 | 5 Sep 2026 | Women's Asia Cup group: **India v Pakistan**, Dubai | India won by **7 wickets** (bowled Pak out 55; chased in 8.4 ov; Harmanpreet's 150th game as captain, finished with a six) | Routine-win dominance, minimal drama — the rivalry as backdrop |
| H8 | **13 Sep 2026** | **Women's Asia Cup FINAL v Sri Lanka**, Dubai — *inside our collected arc* | India 183/5 beat SL 111 — **8th Women's Asia Cup title**; team **refused the trophy from Naqvi again** (he waited, handed SL the runners-up cheque, left); India celebrated with an in-dressing-room ceremony | **THE trigger that opens our dataset**: elation (title #8) + anger/pride (second snub in 12 months) in the same night — a designed-in two-polarity reaction |
| H9 | 18 Sep 2026 | Asian Games QF: **India v Japan**, Nisshin | India won by **8 wickets** (Charani stars) | Calm, routine-advance coverage; previews pivot to "medal secured?" |
| H10 | 20–22 Sep 2026 | **Asian Games SF (v Bangladesh, 20th) & gold-medal match (22nd)** | **LIVE — being collected now** | The study's primary window |

Sources (row-mapped, for the report's citation list): BBC Sport (H1),
Sky Sports (H1), India Today OTD (H1), Forbes (H6, H5 context), NDTV/PTI
(H6), Moneycontrol (H5–H8 overview), India Today (H8, H6 recap), News18 /
Indian Express / Cricinfo (H7, H8), Times of India / Business Standard /
olympics.com (H9–H10 schedules + results).

## 2. The two-year pattern library (what the report will test the live data against)

1. **The trophy-refusal arc (H5->H6->H8).** What began as a handshake boycott
   in Sept 2025 became a trophy boycott, then a *repeat* in 2026. Reaction
   pattern to expect: a pride/anger polarity split ("principled stand" vs
   "just take the trophy") instead of uniform celebration — detectable as
   bimodal sentiment on 13–14 Sept and around every BCCI/ACC statement
   (19 Sept AGM quotes landed mid-arc).
2. **Peak-hope heartbreak (H2) vs clutch-joy (H3).** The 2023 final loss is
   the fandom's reference point for expectation-collapse; 2024's last-over
   title is its counter-memory. A close Asian-Games SF/gold match should
   therefore produce *sharper* swings than a blowout — swing magnitude vs
   match-competitiveness is an analysable hypothesis.
3. **The Dubai fortress narrative (H4, H5, H6, H8).** Four straight title
   nights in Dubai prime "kuch bhi ho, India jeetega" confidence going into
   a neutral-venue Asian Games campaign in Japan.
4. **Rituals of victory (H3).** Open-bus parades, dressing-room ceremonies
   (H8), invisible-trophy poses (H6) — celebration *formats* are themselves
   memetic content the entity analysis should catch (trophy, podium, Naqvi,
   BCCI, Harmanpreet).
5. **The dominance baseline (H7, H9).** Wins by 7–8 wickets barely move the
   needle — establishing the "engagement needs stakes, not just wins"
   contrast the live SF/gold spikes will be measured against.

## 3. Mapping catalog -> collected data -> report sections

| Report section | fed by |
|---|---|
| Data Collection Method | event plan (`round3_event_plan.md`), sweep log |
| Time Window | live window (20–22 Sept) + retro arc (13–19 Sept), D2/D2a |
| Sentiment Analysis | Round-2 model scores over `posts.jsonl`, split by arc/day |
| Activity Analysis | hourly `created_at` counts; spikes vs the trigger calendar |
| Topic/Entity Analysis | entities: Harmanpreet, Mandhana, Charani, Deepti, BCCI, Naqvi, trophy, Asian Games, Asia Cup |
| Trigger Explanations | this catalog (H1–H9) + in-window events (H10) + scheduled-event timestamps |
| Interpretation | the pattern library above, tested against the live curves |

*The catalog gives the report its "why": the fanbase entering 20 Sept is two
years deep in title nights, one unresolved trophy feud, and zero doubts about
the team — the reaction we measure is shaped by all three.*

---

## 4. THE DECADE ARC — India Women, 2017 → 2026 (the spine team's full story)

*Added 20 Sept after a decade-context request. Every row verified against
published scorecards/reporting (cited). This is DOCUMENTED CONTEXT for the
report's Interpretation section — never part of the self-collected dataset.*

| W# | date | event | result | why it matters to the reaction we measure |
|---|---|---|---|---|
| W1 | 23 Jul 2017 | Women's World Cup final, Lord's | **lost by 9 runs** to England (219 chasing 228/7; Shrubsole 6/46; India's last 7 wickets fell for 28; Harmanpreet 51) | the heartbreak that first made India watch women's cricket |
| W2 | 8 Mar 2020 | WT20 World Cup final, MCG | lost by 85 runs to Australia, before **86,174** — a world-record crowd for women's cricket | the scale proof: the audience exists, ready to show up |
| W3 | 7 Aug 2022 | Commonwealth Games final, Birmingham | lost by 9 runs to Australia — **silver** | another near-miss to the same final-boss |
| W4 | Oct 2023 (2022 edition) | Asian Games, Hangzhou | **GOLD** — beat Sri Lanka by 8 wickets | the title India defends at Aichi-Nagoya this week |
| W5 | 2 Nov 2025 | Women's ODI World Cup final, Navi Mumbai | **WON by 52 runs vs South Africa — FIRST-EVER world title** (Shafali 87 & Player-of-the-Match as a late injury call-up; Deepti 5/39 & Player-of-the-Tournament; Jemimah's 127* chased down 339 vs Australia in the SF; BCCI prize ₹51 crore) | buried the "ghosts of the 2005 and 2017 finals"; team's defining night |
| W6 | 13 Sep 2026 | Asia Cup final (8th title) + trophy refusal #2 | won, trophy declined | inside our collected arc — elation + anger the same night |
| W7 | 22 Sep 2026 | **Asian Games gold-medal match** | **LIVE — being collected now** | a 9-year arc converging on one match |

**The one-sentence version for the report:** nine years, four lost finals,
then three trophies in eleven months — the fanbase watching the 22 Sept gold
defence is not reacting to one match; it is reacting to the closing chapter
of a decade-long story it personally suffered through.

**Data-boundary note (honest):** pre-2026 social-media *reaction* data is not
collectable by any legal keyless route (platform APIs truncate history);
GDELT's 2015+ news timeline was attempted for a coverage-history figure and
was refused from this host (rate-limit, 20 Sept, logged — retryable from a
residential IP). The decade context therefore lives in this sourced catalog,
which is exactly what "Trigger Explanations" and "Interpretation" need.
