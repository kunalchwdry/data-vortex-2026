# Phase-1 form — what goes in each field

Form: `docs.google.com/forms/d/e/1FAIpQLSeGdJapExSlif6ZFq0ys9OnW1uQNQDUmrUpT7Pynhl99Eb2bA`
Deadline: **14 September 2026, 23:59** (Phase 2 follows on 15 September, 23:59).

| # | Field on the form | Exactly what to enter |
|---|---|---|
| 1 | **Email** | tick *"Record `kunal.chwdry@gmail.com` as the email to be included with my response"* |
| 2 | **Team Name** | `Forge-X` |
| 3 | **Team Size** | `1` |
| 4 | **Team Head Name** | `Kunal Choudhary` |
| 5 | **Registered Email id** | `kunal.chwdry@gmail.com` — must be the address the team was registered with, not a second inbox |
| 6 | **Registered Mobile No.** | *(you fill this)* the number used at registration |
| 7 | **Cleaned Dataset** (.CSV or .JSON, 1 file, ≤ 10 MB) | `submission/Social_Engine_Posts_Clean.csv` — 2.46 MB, 10,221 rows × 17 cols |
| 8 | **EDA Report** (.PDF, 1 file, ≤ 10 MB) | `submission/Phase1_EDA_Report.pdf` — 0.67 MB, 6 pages |
| 9 | **Code Notebook** (public repo link) | `https://github.com/<your-username>/<repo>` — see below |

**Slot 7 alternative.** The form accepts a single file, so the users table, the
1,779 unrecoverable-text hold-out rows and the 27-line repair log live in the
repository rather than the upload. If you would rather reviewers get all of it
without opening the repo, upload
`submission/Social_Engine_Cleaned_AllTables.json` (6.06 MB) instead — same
posts table plus every other table and the cleaning summary, as strict JSON.
Do not upload both; pick one.

Both copies are produced by step 9 of `./run_all.sh`
(`src/make_submission.py`), which also writes `submission/MANIFEST.md` with each
file's size against the 10 MB cap and a SHA-256 proving the upload is
byte-identical to the file committed in the repo.

## Making the repo link valid

The form requires a **public** repository, and this workspace is not a git repo
yet, so there is no URL to paste until you do this:

```bash
cd datavortex
git init -b main
git add -A
git commit -m "Data Vortex Round 1: recovery, cleaning, EDA, SQL analytical core"
```

Then create an empty **public** repository on GitHub (no README, no .gitignore —
both already exist here) and push:

```bash
git remote add origin https://github.com/<your-username>/datavortex-r1.git
git push -u origin main
```

Open the URL in a private window before submitting: if GitHub shows a sign-in
prompt, the repository is private and the judges cannot read it.

Nothing sensitive is in the tree: `submission/`, caches and the SQLite database
are git-ignored, and the only files taken from the event site are the two
published CSVs plus the bundle/HTML used as recovery evidence.

## Before pressing submit

- [ ] `./run_all.sh` exits 0 — it re-runs cleaning, the 12 queries, 21 tests, the
      README claim check, both PDFs, the notebook and this upload set.
- [ ] `python3 src/verify_source.py` still reports `0 mismatched` — the recovered
      files match what the site publishes today.
- [ ] Repo is public and the pushed `HEAD` contains `notebooks/01_data_cleaning_eda.ipynb`
      with executed outputs (that link *is* the "Code Notebook" answer).
- [ ] PDF opens and shows the `Team Forge-X · Kunal Choudhary` byline on page 1.
- [ ] No fabricated rows or values anywhere: missing `likes` stayed `null`
      (1,532 rows), and both justified decisions are in `data/clean/repair_log.csv`.

## Not on this form, do not forget

**Phase 2** (SQL) closes 15 September 23:59 and is submitted separately:
`output/Phase2_Insight_Report.pdf` holds the 12 queries, their live outputs,
screenshots and the schema rationale; keep pushing to the same repository,
which the rules require you to maintain through the competition.
