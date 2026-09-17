"""
Data Vortex -- Round 2
Shared configuration for the semantic-layer rebuild (NLP module).

Round 1 convention, kept: every constant that encodes an ANALYST DECISION
lives here (not buried in code) so judges can inspect, change and re-run the
pipeline with different assumptions and see the effect in one place.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Identity / reproducibility
# ---------------------------------------------------------------------------
RANDOM_STATE = 42          # one seed drives splits, CV folds, LDA/NMF, shuffles
TEAM_NAME = "Forge-X"
TEAM_MEMBERS = ["Kunal Choudhary"]
EVENT = "Aaruush'26"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]

DATA_R2_RAW = ROOT / "data" / "round2" / "raw"
DATA_R2_CLEAN = ROOT / "data" / "round2" / "clean"
RAW_DATASET2 = DATA_R2_RAW / "Dataset2.csv"

TRAIN_CSV = DATA_R2_CLEAN / "train.csv"
TEST_CSV = DATA_R2_CLEAN / "test.csv"
EMPTY_HELDOUT_CSV = DATA_R2_CLEAN / "empty_text_heldout.csv"
DUPE_HELDOUT_CSV = DATA_R2_CLEAN / "exact_duplicate_heldout.csv"
PROFILE_JSON = DATA_R2_CLEAN / "profile.json"
SPLIT_MANIFEST_JSON = DATA_R2_CLEAN / "split_manifest.json"
CLEANING_REPORT_MD = DATA_R2_CLEAN / "cleaning_report.md"

MODELS_DIR = ROOT / "models" / "round2"

OUT_R2 = ROOT / "output" / "round2"
FIG_R2 = OUT_R2 / "figures"
METRICS_JSON = OUT_R2 / "metrics.json"
EVAL_REPORT_PDF = OUT_R2 / "Evaluation_Metrics_Report.pdf"
TECH_REPORT_PDF = OUT_R2 / "Round2_Technical_Report.pdf"

NOTEBOOK_PATH = ROOT / "notebooks" / "02_nlp_rebuild_semantic_layer.ipynb"
SUBMISSION_R2 = ROOT / "submission" / "round2"

# ---------------------------------------------------------------------------
# Intake decisions
# ---------------------------------------------------------------------------

# D1 -- expected schema of Dataset 2. The pipeline refuses to run on anything
#       else rather than silently misreading columns.
EXPECTED_COLUMNS = ["text_id", "post_text", "sentiment_label", "topic_category"]

# D2 -- canonical sentiment order. Fixed (not alphabetical, not data order) so
#       confusion-matrix rows/columns are identical across every figure/table.
SENTIMENT_ORDER = ["Negative", "Neutral", "Positive"]

# D3 -- empty posts are HELD OUT, not imputed and not silently dropped: an
#       empty string carries no sentiment signal, and Round 1 set the precedent
#       (1,779 empty-text hold-outs) that the row arithmetic must close.
HOLD_OUT_EMPTY_TEXT = True

# D4 -- exact (text, sentiment, topic) duplicates are held out (keep first).
#       WHY: duplicates straddling train/test leak answers and inflate scores.
#       Same text with CONFLICTING labels is instead kept everywhere and
#       reported as label noise -- deleting disagreement would hide it.
HOLD_OUT_EXACT_DUPLICATES = True

# ---------------------------------------------------------------------------
# Split + model-selection decisions
# ---------------------------------------------------------------------------

# D5 -- one shared 80/20 split, stratified, for both tasks. A single split
#       keeps sentiment and topic results comparable; stratification keeps the
#       minority classes represented in test.
TEST_SIZE = 0.20
STRATIFY_BY = "sentiment_x_topic"   # back off to sentiment-only if a combo < 2 rows

# D6 -- model selection by 5-fold stratified CV (macro-F1) on train; the held-
#       out test set is touched exactly once, by the refit winner. No test
#       peeking, no seed hacking: one seed, declared above.
CV_FOLDS = 5
CV_SCORING = "f1_macro"

# D7 -- grids are deliberately small and linear-only. WHY: 9k short texts do
#       not justify a GPU model; TF-IDF + linear models are reproducible on any
#       machine, inspectable (feature weights), and the honest baseline the
#       rulebook's "model selection & justification" criterion asks for.
LOGREG_C = [0.5, 1.0, 2.0, 4.0]
SVC_C = [0.25, 0.5, 1.0, 2.0]
NB_ALPHA = [0.1, 0.5, 1.0]
CLASS_WEIGHTS = [None, "balanced"]   # compare, don't assume, on imbalance
LOGREG_MAX_ITER = 2000
SVC_MAX_ITER = 5000

# D8 -- word n-grams (1,2) + char_wb (3,5): words carry sentiment, character
#       n-grams carry robustness to the typos/elongations/slang in the data
#       ("sooo", "gr8", "luv"). min_df=2 drops one-off typos from the vocab.
WORD_NGRAMS = (1, 2)
CHAR_NGRAMS = (3, 5)
MIN_DF = 2
SUBLINEAR_TF = True

# D9 -- topic models use unigrams only (bigrams make topics noisier) with a
#       capped vocabulary; K is set to the number of labelled topics so the
#       agreement analysis (NMI/ARI) is a fair unsupervised-vs-human check.
LDA_MAX_FEATURES = 8000
LDA_MIN_DF = 5
LDA_MAX_ITER = 25
NMF_MAX_ITER = 300

# D10 -- calibration: a LinearSVC winner gets sigmoid calibration (3-fold) so
#        the shipped model can output probabilities; a LogReg winner already
#        can. The report shows whether calibration helped or hurt log-loss.
CALIBRATE_NON_PROBABILISTIC = True
CALIBRATION_CV = 3
CALIBRATION_METHOD = "sigmoid"
