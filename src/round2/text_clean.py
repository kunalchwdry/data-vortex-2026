"""
Data Vortex -- Round 2: text normalisation + tokenisation.

WHY a hand-written normaliser instead of an off-the-shelf tweet tokenizer?
1. The file carries its own corruption: literal ``\\uXXXX`` escape sequences,
   HTML entities and quote doubling from a broken export -- handled first.
2. Social text needs masking (URLs, @mentions) and marker tokens (<emoji>,
   <hashtag>) so the model learns *that* an emoji was used, not 3,000 rare
   emoji codepoints.
3. Zero external data dependencies: no NLTK downloads, no spaCy models --
   the pipeline runs fully offline and deterministically.

Everything here is a pure function of its input (no randomness, no state),
so preprocessing cannot leak label information.
"""
from __future__ import annotations

import html
import re

from round2.config import WORD_NGRAMS

# ---------------------------------------------------------------------------
# 1. Export-corruption repair (runs before anything linguistic)
# ---------------------------------------------------------------------------
_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})")
_WS_RE = re.compile(r"\s+")


def decode_unicode_escapes(text: str) -> str:
    """Turn literal ``\\u2019`` sequences into the real character.

    WHY regex-targeted instead of ``.decode('unicode_escape')``: the global
    codec mangles genuine backslashes and non-ASCII bytes; the export only
    ever emitted ``\\uXXXX`` / ``\\UXXXXXXXX`` forms, so only those are fixed.
    """
    def _one(match: re.Match) -> str:
        code = match.group(1) or match.group(2)
        try:
            return chr(int(code, 16))
        except (ValueError, OverflowError):
            return match.group(0)  # leave malformed escapes untouched

    return _UNICODE_ESCAPE_RE.sub(_one, text)


def base_clean(text: object) -> str:
    """Decode escapes + HTML entities, collapse whitespace. No lowercasing,
    no masking -- this is the form used for length stats and error tables."""
    if text is None:
        return ""
    s = str(text)
    s = decode_unicode_escapes(s)
    s = html.unescape(html.unescape(s))  # twice: the export double-encoded some rows
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = _WS_RE.sub(" ", s).strip()
    return s


# ---------------------------------------------------------------------------
# 2. Social-text normalisation
# ---------------------------------------------------------------------------
URL_RE = re.compile(r"https?://\S+|www\.\S+")
MENTION_RE = re.compile(r"@([a-z0-9_]+)")
HASHTAG_RE = re.compile(r"#([a-z0-9_]+)")

_SMILES = [":-)", ":)", ";-)", ";)", ":-d", ":d", "=)", "(-:", "(:"]
_SADS = [":-(", ":(", ";-(", ";(", ":'(", ")-:", "):", "t_t", "d-:"]
_SMILE_RE = re.compile("|".join(re.escape(e) for e in sorted(_SMILES, key=len, reverse=True)))
_SAD_RE = re.compile("|".join(re.escape(e) for e in sorted(_SADS, key=len, reverse=True)))

EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF\u2B00-\u2BFF\uFE0F]")
ELONG_RE = re.compile(r"([a-z])\1{2,}")
PUNCT_RE = re.compile(r"[^a-z0-9\s<>]")

# Contractions are expanded (not dropped) so negation survives stopword
# removal: "don't like" -> "do not like" -> ["not", "NOT_like"].
_CONTRACTIONS = [
    (re.compile(r"\bcan't\b"), "can not"),
    (re.compile(r"\bwon't\b"), "will not"),
    (re.compile(r"n't\b"), " not"),
    (re.compile(r"'re\b"), " are"),
    (re.compile(r"'ve\b"), " have"),
    (re.compile(r"'ll\b"), " will"),
    (re.compile(r"'d\b"), " would"),
    (re.compile(r"'m\b"), " am"),
    (re.compile(r"'s\b"), ""),
]

NEGATIONS = frozenset({"not", "no", "never", "none", "nobody", "nothing",
                       "nowhere", "neither", "cannot"})
NEGATION_WINDOW = 3  # Pang & Lee style scope: prefix the next 3 content words


def normalize_text(text: object) -> str:
    """Full normalisation to a cleaned string (used by the char n-gram arm
    and as the base the word analyser tokenises). Deterministic."""
    s = base_clean(text).lower()
    s = URL_RE.sub(" <url> ", s)
    s = MENTION_RE.sub(" <user> ", s)
    # keep the tag words (they carry topic signal) + a marker that a tag existed
    s = HASHTAG_RE.sub(r"\1 <hashtag> ", s)
    s = _SMILE_RE.sub(" <smile> ", s)
    s = _SAD_RE.sub(" <sad> ", s)
    s = EMOJI_RE.sub(" <emoji> ", s)
    for pattern, replacement in _CONTRACTIONS:
        s = pattern.sub(replacement, s)
    if ELONG_RE.search(s):
        s = ELONG_RE.sub(r"\1\1", s) + " <elong>"
    s = PUNCT_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


# ---------------------------------------------------------------------------
# 3. Tokenisation + stopwords + negation scope
# ---------------------------------------------------------------------------

# Compact English stoplist. Deliberately EXCLUDES every negation word (they
# are sentiment-bearing) and every <marker> (markers bypass filtering anyway).
STOPWORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into",
    "is", "it", "its", "itself", "just", "like", "me", "more", "most",
    "my", "myself", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while",
    "who", "whom", "why", "will", "with", "you", "your", "yours",
    "yourself", "yourselves", "one", "also", "get", "got", "would",
    "could", "may", "might", "must", "shall", "us",
})

_MARKER_RE = re.compile(r"^<[a-z]+>$")


def _is_marker(token: str) -> bool:
    return bool(_MARKER_RE.match(token)) or token == "<empty>"


def apply_negation_scope(tokens: list[str], window: int = NEGATION_WINDOW) -> list[str]:
    """Prefix content words after a negation with ``NOT_`` (bounded scope).

    WHY: it turns "not good" from [not, good] -- where "good" votes positive --
    into [not, NOT_good], the standard linear-model fix for negation.
    Markers (<url>, <emoji>, ...) are never prefixed: "<emoji>" after "not"
    is not a negated emoji, it is just an emoji.
    """
    out: list[str] = []
    scope = 0
    for tok in tokens:
        if tok in NEGATIONS:
            out.append(tok)
            scope = window
        elif scope > 0 and not _is_marker(tok) and not tok.startswith("NOT_"):
            out.append("NOT_" + tok)
            scope -= 1
        else:
            out.append(tok)
            if scope > 0 and not _is_marker(tok):
                scope -= 1
    return out


def word_tokens(text: object) -> list[str]:
    """Unigrams after normalisation + stopword removal + negation scope."""
    toks = [t for t in normalize_text(text).split()
            if t and (_is_marker(t) or t in NEGATIONS or t not in STOPWORDS)]
    toks = apply_negation_scope(toks)
    return toks or ["<empty>"]


def word_token_analyzer(text: object) -> list[str]:
    """Module-level analyser for TfidfVectorizer (word uni+bigrams).

    Must stay module-level (not a closure/factory): the fitted vectorizer is
    pickled by reference to this function, and closures do not pickle.
    """
    uni = word_tokens(text)
    if len(uni) < 2 or WORD_NGRAMS[1] < 2:
        return uni
    return uni + [uni[i] + " " + uni[i + 1] for i in range(len(uni) - 1)]


def word_token_analyzer_uni(text: object) -> list[str]:
    """Unigram-only variant for the LDA/NMF count vectorizers.

    WHY separate: bigrams sharpen classifiers but smear topic-word
    distributions, so the topic models get a cleaner unigram stream.
    """
    return word_tokens(text)


# ---------------------------------------------------------------------------
# 4. Per-text attributes for slice/error analysis (computed on raw text)
# ---------------------------------------------------------------------------
_URL_RAW_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MENTION_RAW_RE = re.compile(r"@[A-Za-z0-9_]+")
_HASHTAG_RAW_RE = re.compile(r"#[A-Za-z0-9_]+")
_NEG_WORD_RE = re.compile(r"\b(not|no|never|none|nobody|nothing|nowhere|neither|cannot|can't|won't|n't)\b",
                          re.IGNORECASE)


def attributes_for_analysis(text: object) -> dict:
    """Cheap, deterministic attributes used to slice test accuracy
    (short vs long, negation present, emoji present, ...)."""
    raw = str(text or "")
    toks = word_tokens(text)
    return {
        "n_chars": len(base_clean(text)),
        "n_tokens": 0 if toks == ["<empty>"] else len(toks),
        "has_url": bool(_URL_RAW_RE.search(raw)),
        "has_mention": bool(_MENTION_RAW_RE.search(raw)),
        "has_hashtag": bool(_HASHTAG_RAW_RE.search(raw)),
        "has_emoji": bool(EMOJI_RE.search(raw) or _SMILE_RE.search(raw.lower())
                          or _SAD_RE.search(raw.lower())),
        "has_negation": bool(_NEG_WORD_RE.search(raw)),
        "has_elong": bool(re.search(r"([a-zA-Z])\1{2,}", raw)),
    }
