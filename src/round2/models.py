"""
Data Vortex -- Round 2: model specifications.

WHY these six specs: they form a ladder -- chance floor (dummy), classic
baseline (Naive Bayes), linear workhorses (LogReg / LinearSVC on words),
then the same two on words+characters to isolate what character n-grams add
for noisy social text. The winner is chosen by CV, not by reputation.
"""
from __future__ import annotations

from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from round2 import config as C
from round2.text_clean import (normalize_text, word_token_analyzer,
                               word_token_analyzer_uni)


# ---------------------------------------------------------------------------
# Feature builders (fresh instance per call -- never share fitted state)
# ---------------------------------------------------------------------------
def build_word_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(analyzer=word_token_analyzer, lowercase=False,
                           min_df=C.MIN_DF, sublinear_tf=C.SUBLINEAR_TF)


def build_char_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(preprocessor=normalize_text, analyzer="char_wb",
                           ngram_range=C.CHAR_NGRAMS, lowercase=False,
                           min_df=C.MIN_DF, sublinear_tf=C.SUBLINEAR_TF)


def build_union_features() -> FeatureUnion:
    return FeatureUnion([("word", build_word_vectorizer()),
                         ("char", build_char_vectorizer())])


def build_count_vectorizer() -> CountVectorizer:
    """Unigram counts for LDA/NMF (topic models want raw counts, not TF-IDF --
    reweighting distorts the multinomial assumptions they are fit under)."""
    return CountVectorizer(analyzer=word_token_analyzer_uni, lowercase=False,
                           min_df=C.LDA_MIN_DF, max_df=0.9,
                           max_features=C.LDA_MAX_FEATURES)


# ---------------------------------------------------------------------------
# Spec ladder. Order = tie-break preference (simplest first).
# ---------------------------------------------------------------------------
def model_specs() -> list[dict]:
    """Each spec: name, features ('word'|'union'|'none'), fresh estimator,
    param grid. Char-only is omitted deliberately: the word-vs-union gap is
    the ablation that measures the character arm's contribution."""
    return [
        {"name": "dummy",
         "features": "none",
         "estimator": DummyClassifier(strategy="stratified",
                                      random_state=C.RANDOM_STATE),
         "grid": {}},
        {"name": "nb_word",
         "features": "word",
         "estimator": MultinomialNB(),
         "grid": {"clf__alpha": list(C.NB_ALPHA)}},
        {"name": "logreg_word",
         "features": "word",
         "estimator": LogisticRegression(max_iter=C.LOGREG_MAX_ITER,
                                         random_state=C.RANDOM_STATE),
         "grid": {"clf__C": list(C.LOGREG_C),
                  "clf__class_weight": list(C.CLASS_WEIGHTS)}},
        {"name": "svc_word",
         "features": "word",
         "estimator": LinearSVC(max_iter=C.SVC_MAX_ITER,
                                random_state=C.RANDOM_STATE),
         "grid": {"clf__C": list(C.SVC_C),
                  "clf__class_weight": list(C.CLASS_WEIGHTS)}},
        {"name": "logreg_union",
         "features": "union",
         "estimator": LogisticRegression(max_iter=C.LOGREG_MAX_ITER + 1000,
                                         random_state=C.RANDOM_STATE),
         "grid": {"clf__C": list(C.LOGREG_C),
                  "clf__class_weight": list(C.CLASS_WEIGHTS)}},
        {"name": "svc_union",
         "features": "union",
         "estimator": LinearSVC(max_iter=C.SVC_MAX_ITER,
                                random_state=C.RANDOM_STATE),
         "grid": {"clf__C": list(C.SVC_C),
                  "clf__class_weight": list(C.CLASS_WEIGHTS)}},
    ]


def build_pipeline(spec: dict) -> Pipeline:
    """Assemble an (unfitted) pipeline from a spec."""
    steps = []
    if spec["features"] == "word":
        steps.append(("features", build_word_vectorizer()))
    elif spec["features"] == "union":
        steps.append(("features", build_union_features()))
    elif spec["features"] != "none":
        raise ValueError(f"unknown features: {spec['features']}")
    steps.append(("clf", spec["estimator"]))
    return Pipeline(steps)
