"""
Assemble submission/round2/ -- the Round 2 form upload set.

Copies the four required sections (notebook, trained models, evaluation
metrics report, technical report) plus a MANIFEST with sizes + SHA-256, so
what gets uploaded is provably what the repo ships. Mirrors Round 1's
submission/phase2/ convention.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from round2 import config as C


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    C.SUBMISSION_R2.mkdir(parents=True, exist_ok=True)
    items: list[tuple[str, Path, str]] = [
        ("Notebook (NLP model script)",
         C.NOTEBOOK_PATH, "executed notebook; imports src/round2, reads metrics.json"),
        ("Trained model: sentiment",
         C.MODELS_DIR / "sentiment_best.pkl", "TF-IDF + linear bundle w/ preprocessing"),
        ("Trained model: topic",
         C.MODELS_DIR / "topic_best.pkl", "TF-IDF + linear bundle w/ preprocessing"),
        ("Topic model: LDA",
         C.MODELS_DIR / "topic_lda.pkl", "bonus unsupervised agreement analysis"),
        ("Topic model: NMF",
         C.MODELS_DIR / "topic_nmf.pkl", "bonus unsupervised agreement analysis"),
        ("Evaluation Metrics Report (PDF)",
         C.EVAL_REPORT_PDF, "test metrics, CV, ROC, calibration, slices"),
        ("Round 2 Technical Report (PDF)",
         C.TECH_REPORT_PDF, "rulebook sections + error analysis + bonuses"),
    ]
    missing = [str(src) for _, src, _ in items if not src.exists()]
    if missing:
        raise FileNotFoundError(f"missing artefacts, run the pipeline first: {missing}")

    lines = ["# Round 2 submission set", "",
             f"Team {C.TEAM_NAME} · {', '.join(C.TEAM_MEMBERS)} · {C.EVENT}", "",
             "Regenerate deterministically: `./run_round2.sh`.", "",
             "| # | section | file | size | SHA-256 | notes |",
             "|---|---|---|---|---|---|"]
    for i, (section, src, notes) in enumerate(items, 1):
        dest = C.SUBMISSION_R2 / src.name
        shutil.copy2(src, dest)
        size_kb = dest.stat().st_size / 1024
        lines.append(f"| {i} | {section} | `{src.name}` | {size_kb:,.0f} KB | "
                     f"`{_sha256(dest)[:16]}…` | {notes} |")
    lines += ["", "Upload order follows the rulebook's section list: notebook, "
              "model files, evaluation metrics report, technical report.", ""]
    (C.SUBMISSION_R2 / "MANIFEST.md").write_text("\n".join(lines))
    total_kb = sum((C.SUBMISSION_R2 / src.name).stat().st_size for _, src, _ in items) / 1024
    print(f"  submission/round2/: {len(items)} files, {total_kb:,.0f} KB total + MANIFEST.md")


if __name__ == "__main__":
    main()
