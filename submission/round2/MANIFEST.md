# Round 2 submission set

Team Forge-X · Kunal Choudhary · Aaruush'26

Regenerate deterministically: `./run_round2.sh`.

| # | section | file | size | SHA-256 | notes |
|---|---|---|---|---|---|
| 1 | Notebook (NLP model script) | `02_nlp_rebuild_semantic_layer.ipynb` | 1,239 KB | `513f621f518c9bd2…` | executed notebook; imports src/round2, reads metrics.json |
| 2 | Trained model: sentiment | `sentiment_best.pkl` | 2,042 KB | `7bedb6a433b0472d…` | TF-IDF + linear bundle w/ preprocessing |
| 3 | Trained model: topic | `topic_best.pkl` | 5,732 KB | `00bdf4663f159685…` | TF-IDF + linear bundle w/ preprocessing |
| 4 | Topic model: LDA | `topic_lda.pkl` | 235 KB | `724ab2c2a51bc8ca…` | bonus unsupervised agreement analysis |
| 5 | Topic model: NMF | `topic_nmf.pkl` | 149 KB | `5fce361204f54a3e…` | bonus unsupervised agreement analysis |
| 6 | Evaluation Metrics Report (PDF) | `Evaluation_Metrics_Report.pdf` | 1,240 KB | `8bcef9568cb212f3…` | test metrics, CV, ROC, calibration, slices |
| 7 | Round 2 Technical Report (PDF) | `Round2_Technical_Report.pdf` | 1,075 KB | `c3836c47fada12f2…` | rulebook sections + error analysis + bonuses |

Upload order follows the rulebook's section list: notebook, model files, evaluation metrics report, technical report.
