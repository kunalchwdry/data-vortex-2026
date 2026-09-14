# Recovery walkthrough — solving the Phase 1 puzzle from scratch

Reproducible steps for anyone who has to do this live (or defend it in a viva).
Nothing here needs a browser extension; `curl` and a text editor are enough.

---

## 0 · What the page actually is

```bash
curl -s https://datavortex-social-engine.vercel.app/
```

```html
<!doctype html>
<title>Data Vortex :: Social Engine Recovery Terminal</title>
<script type="module" src="/assets/index-B2FT5USN.js"></script>
<div id="root"></div>
```

An empty `<div>`. There is no data in the HTML, and every guess at a data URL
(`/dataset.csv`, `/api/data`, `/logs`, `/robots.txt`, …) returns `404 NOT_FOUND`.
**The page is a decoy generator; the logic is in the bundle.** This is what
"the system may not reveal everything at first glance" means: the five dashboard
modules you can see are, four of them, dead ends that render
"This module cannot be displayed".

## 1 · Read the bundle

```bash
curl -s .../assets/index-B2FT5USN.js -o app.js    # 2.3 MB, one file
```

It is a minified React app, so search it for the vocabulary of the hints rather
than reading it. Two greps do the work.

**(a) Every path-like string in the file:**

```
"/dataset/Social_Engine_Posts_Corrupted.csv"
"/dataset/Social_Engine_Users.csv"
"dataset-file-list" ... "log-console" ... "error-hint"
```

The dataset paths are *in the bundle*. That is the whole prize — but note the
files are unreachable until the archive view is unlocked, and knowing the path
from a minified string is not the route the organisers intend (nor the one that
survives a redeploy). Get the intended route:

**(b) The hint vocabulary — `recovery`, `logs`, `node`:**

```js
// the SYSTEM LOG, shown by the `logs` command
Oi = [
 "03:42:17  database.service    exited with code 137",
 "03:42:19  analytics.service   segfault, core not found",
 "03:42:21  live_signal.service carrier lost, retrying...",
 "03:42:21  live_signal.service retry failed, giving up",
 "03:42:23  node_07             responded 200 (intermittent)",
 "03:42:26  watchdog            last known good node: node_07",
 "03:42:31  watchdog            dashboard link to node_07: severed"
]
```

*"what appears at the beginning of each line"* → the `hh:mm:ss` prefix and the
service name in column two. Five lines name broken services; **two name
`node_07`**. *"a message hidden in plain sight"* → the UI also prints
`last known surviving node: node_07` under the log panel, in italics, which is
the only sentence in the app that is a clue rather than chrome.

## 2 · The trick the puzzle is actually testing

The shell advertises four commands:

```js
b === "help"  -> "available commands: help, status, scan, logs, clear"
```

None of them gives you the data. `status` reports everything OFFLINE/CORRUPTED;
`scan` reports *"7 modules detected, all unresponsive via dashboard link"* —
which is the puzzle telling you the visible route is closed. But the handler
before the fallthrough is:

```js
/(connect|access|restore|reconnect|link)/.test(b) && /(node.?0?7|archive)/.test(b)
  ? ["establishing manual link to node_07...", "link unstable -- retrying...",
     "connection stabilized.", "redirecting to archive interface..."]
  : [`command not recognized: "${b}"`]
```

**"Follow the pattern. Decode the connection. Find the node."** is a description
of that regex: a verb from the first set, plus the node from the second. The
archive opens for any string matching both — `connect node_07` is the natural
one. The gate is *semantic*, not syntactic: it is testing whether you read the
rule instead of brute-forcing the menu.

## 3 · Collect the data

`ARCHIVE NODE 07` lists DATASET 01 with two files, each behind a `[ RECOVER ]`
button (which downloads a Blob; both are marked `✓ RECOVERED` before
`CONTINUE` unlocks, so the site does verify that you fetched both). The same two
files are served statically, so they are equally obtainable with:

```bash
BASE=https://datavortex-social-engine.vercel.app
curl -s $BASE/dataset/Social_Engine_Users.csv             -o data/raw/Social_Engine_Users.csv
curl -s $BASE/dataset/Social_Engine_Posts_Corrupted.csv   -o data/raw/Social_Engine_Posts_Corrupted.csv
```

`python src/verify_source.py` re-fetches both, byte-compares against
`data/raw/`, and writes `output/provenance.json` with the SHA-256 of each file.

**Independent confirmation.** The bundle contains an organiser debug panel
enabled by `?test=true` in the URL. It renders a row labelled:

```
Real path          terminal: connect node_07
```

plus the two `/dataset/...` paths, `Clue status (logs): HIDDEN/REVEALED` and an
operator roster. So the intended route is confirmed by the app's own diagnostics,
not inferred from a minified string. (The panel also shows `ARCHIVE: UNKNOWN`
until you unlock it — the state is real, which is how you can tell you solved it
rather than worked around it.)

## 4 · What the two files look like

```
Social_Engine_Posts_Corrupted.csv   12,360 rows × 8 cols
  post_id, user_id, platform, text_content, timestamp, likes, shares, comments
Social_Engine_Users.csv               1,500 rows × 5 cols
  user_id, location, language, account_created, follower_count
```

Ten defect families, catalogued in `docs/cleaning_decisions.md` and quantified by
`python src/clean_data.py`'s reconciliation output. Two useful negative results,
found by checking and reporting rather than assuming:

* referential integrity is **already** intact — 0 posts reference an unknown
  user, 0 users never post. Say so, because a judge looks for whether you checked.
* no post predates its author's `account_created`, and nothing is dated in the
  future. The window is `2024-05-01 → 2025-04-30`, exactly one year.

## 5 · What to *not* do

* **Do not hand-write the dataset.** The rulebook bans fabrication; the organisers
  can diff your CSV against theirs.
* **Do not submit only the download path.** `?test=true` and the bundle strings
  both show the route, but the scored outcome is the *cleaning*, and the
  walkthrough above is what earns the "assumptions explained" marks.
* **Do not clean before profiling.** Write the defect inventory first; every
  cleaning rule should answer an observed fault, and the counts should reconcile.
* **Do not delete the awkward rows.** Hold them out to a file so
  `raw − dupes − hold-outs = analysis` closes. That single identity is the
  cheapest strong signal in the whole submission.
