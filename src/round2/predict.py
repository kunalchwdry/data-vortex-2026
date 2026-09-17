"""
Data Vortex -- Round 2: inference CLI for the shipped models.

Single text:
    python src/round2/predict.py --text "I love the new update!"

Batch CSV (adds pred_sentiment / pred_topic + probability columns):
    python src/round2/predict.py --csv posts.csv --text-col post_text --out scored.csv

The bundles embed the full preprocessing pipeline, so inference applies
byte-identical normalisation to training -- there is no second,
possibly-diverged cleaning implementation.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from round2 import config as C


def load_bundles(models_dir: Path = C.MODELS_DIR) -> dict:
    bundles = {}
    for task in ("sentiment", "topic"):
        path = models_dir / f"{task}_best.pkl"
        if not path.exists():
            raise FileNotFoundError(f"missing {path} -- run train.py first")
        bundles[task] = joblib.load(path)
    return bundles


def predict_texts(texts: list[str], bundles: dict) -> pd.DataFrame:
    rows = []
    for text in texts:
        row = {"text": text}
        for task, bundle in bundles.items():
            pipe, labels = bundle["pipeline"], bundle["labels"]
            pred = pipe.predict([text])[0]
            row[f"pred_{task}"] = pred
            if hasattr(pipe, "predict_proba"):
                proba = pipe.predict_proba([text])[0]
                order = list(pipe.classes_)
                for lab in labels:
                    row[f"prob_{task}_{lab}"] = round(float(proba[order.index(lab)]), 4)
        rows.append(row)
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Round 2 inference CLI")
    parser.add_argument("--text", help="single post to classify")
    parser.add_argument("--csv", help="input CSV for batch scoring")
    parser.add_argument("--text-col", default="post_text",
                        help="text column in --csv (default: post_text)")
    parser.add_argument("--out", help="output CSV path for batch scoring")
    parser.add_argument("--models-dir", default=str(C.MODELS_DIR))
    args = parser.parse_args(argv)

    if not args.text and not args.csv:
        parser.error("pass --text ... or --csv ... [--out ...]")
    bundles = load_bundles(Path(args.models_dir))

    if args.text:
        frame = predict_texts([args.text], bundles)
        for task in ("sentiment", "topic"):
            print(f"{task:10s} -> {frame.iloc[0][f'pred_{task}']}")
            for col in sorted(c for c in frame.columns if c.startswith(f"prob_{task}_")):
                print(f"             {col.replace(f'prob_{task}_', ''):22s} "
                      f"{frame.iloc[0][col]:.4f}")
        return 0

    df = pd.read_csv(args.csv, dtype=str, keep_default_na=False)
    if args.text_col not in df.columns:
        print(f"column '{args.text_col}' not in {args.csv}", file=sys.stderr)
        return 2
    scored = predict_texts(df[args.text_col].tolist(), bundles)
    out = pd.concat([df.reset_index(drop=True),
                     scored.drop(columns=["text"]).reset_index(drop=True)], axis=1)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(args.out, index=False)
        print(f"scored {len(out)} rows -> {args.out}")
    else:
        print(out.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
