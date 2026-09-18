# Round 2 — Google Form Submission Sheet

**Event:** Data Vortex 2026 · Round 2 (NLP — Rebuilding the Semantic Layer)
**Team:** Forge-X · **Deadline:** 18 September 2026, 11:59 PM

This folder holds the exact files to upload to the official Google Form,
one file per slot, every file under the 10 MB cap. `SUBMISSION_DETAILS.md`
itself is **not** uploaded — it is the answer sheet + audit record.

---

## 1 · Form answers (copy-paste)

| Form field | Answer |
|---|---|
| **Team Name*** | `Forge-X` |
| **Team Size*** | `1` |
| **Team Head Name*** | `Kunal Choudhary` |
| **Registered Email id.*** | `kunal.chwdry@gmail.com` |
| **Registered Mobile No.*** | `6375597110` |
| **Institute / organisation*** | `Keystone School of Engineering, Pune` |

## 2 · Upload slots (in form order)

| # | Form question | File to upload | Size | SHA-256 |
|---|---|---|---|---|
| 1 | NLP Model Script/Notebook* | `Slot1_NLP_Model_Script_Notebook.ipynb` | 1.27 MB | `513f621f518c9bd25be7576ebba34687cfa6b16396079c19f0fda3fb33be9bbd` |
| 2 | Trained Model Files (Optional: .pkl, .h5) | `Slot2_Trained_Model_Files.zip` | 5.04 MB | `58cb999e84da3e52bd0a75519e1a44c1c6567446511fdd1d02efbb2b79b47b3f` |
| 3 | Evaluation Metrics Report (in pdf)* | `Slot3_Evaluation_Metrics_Report.pdf` | 1.27 MB | `8bcef9568cb212f3c68122495e51ecb5a1d63b0e04d105b16d2469c66648d466` |
| 4 | Round 2 Technical Report (PDF) | `Slot4_Round2_Technical_Report.pdf` | 1.10 MB | `c3836c47fada12f2428d15829341c1ac2cd08ba51dbc1137b405e12daa84c7b0` |

> The form's model slot accepts **one** file, so all four trained models are
> bundled into `Slot2_Trained_Model_Files.zip` under `models_round2/`:
> `sentiment_best.pkl` (sentiment classifier), `topic_best.pkl` (topic
> classifier), `topic_lda.pkl` + `topic_nmf.pkl` (unsupervised topic models).

## 3 · Contents check

- [x] Notebook is the **executed** build (18 cells, 0 errors) — imports `src/round2`, reads `metrics.json`.
- [x] Both PDFs contain every rulebook section: problem definition, preprocessing, model selection, training methodology, evaluation metrics, confusion matrix, error analysis.
- [x] All 4 files re-derived deterministically from `data/round2/raw/Dataset2.csv` (seed 42) — `./run_round2.sh` regenerates byte-equivalent outputs.
- [x] 14/14 Round 2 invariant tests passing (`pytest tests/test_round2.py -q`).

## 4 · Headline numbers quoted on the reports

| Task | Model | Test accuracy | Test macro-F1 |
|---|---|---|---|
| Sentiment (3-class) | `logreg_union` (TF-IDF word(1,2) ∪ char_wb(3,5) → Logistic Regression) | 0.6133 | 0.6134 |
| Topic (4-class) | `svc_union` (TF-IDF union → calibrated LinearSVC) | 0.9677 | 0.8051 |

Regenerate everything: `./run_round2.sh` · Verify a file after download: `sha256sum <file>`
