"""
Render each Phase-2 query result as a terminal-style PNG "output screenshot".

    python src/make_screenshots.py

The rulebook asks for output screenshots. These are rendered from the live
result sets in output/sql_results.json, i.e. by the same run that produced the
numbers -- so the image cannot disagree with the table, and nothing (including
an execution time) is invented.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
SHOTS = OUT / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

BG, HEAD, FG, DIM, ACC, WARN = ("#0b1220", "#141f38", "#dbe7ff", "#5f7590",
                                "#6fe3c8", "#ffc078")
MONO = "DejaVu Sans Mono"
FS = 7.4                      # pt
LH = 0.145                    # inches per text line
CHAR_W = 0.0625      # inches per glyph for DejaVu Sans Mono at FS pt


def fmt(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, float):
        if v != v:
            return "NaN"
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return str(v)


def render(qid, title, sql, cols, rows, elapsed_ms, max_rows=12) -> Path:
    n_total = len(rows)
    rows = rows[:max_rows]

    # column widths, with long prose values broken out underneath instead of
    # being truncated mid-word
    widths = {}
    for i, c in enumerate(cols):
        body = max([len(fmt(r[i])) for r in rows] or [0])
        widths[c] = min(max(len(c), body), 24)
    table_w = sum(widths.values()) + 3 * (len(cols) - 1) if cols else 60
    wrap_sql = 118

    lines: list[tuple[str, str]] = []
    lines.append(("cmd", f"sqlite> .read queries/challenges.sql   -- {qid}"))
    for ln in textwrap.dedent(sql).strip().splitlines():
        for piece in textwrap.wrap(ln, wrap_sql) or [""]:
            lines.append(("sql", piece))
    lines.append(("dim", "─" * min(max(table_w, 60), wrap_sql)))
    lines.append(("acc", " | ".join(c.ljust(widths[c])[:24] for c in cols)))
    for r in rows:
        lines.append(("fg", " | ".join(fmt(r[i]).ljust(widths[c])[:24]
                                        for i, c in enumerate(cols))))
    if not rows:
        lines.append(("dim", "(0 rows)"))
    lines.append(("dim", "─" * min(max(table_w, 60), wrap_sql)))
    for r in rows[:1]:
        for i, c in enumerate(cols):
            if len(fmt(r[i])) > 24:
                lines.append(("note", f"{c:>22}  {fmt(r[i])}"))
    more = "" if n_total == len(rows) else f" (showing first {len(rows)} of {n_total})"
    tail = (f"rows: {n_total}{more}  ·  {elapsed_ms:.2f} ms  ·  "
            f"output/social_engine.db")
    lines.append(("cmd", tail))

    body_h = LH * len(lines) + 1.05
    longest = max(len(t) for _, t in lines)
    fig_w = min(max(9.4, longest * CHAR_W + 0.55), 15.0)
    fig, ax = plt.subplots(figsize=(fig_w, body_h))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    # work in inches so line spacing is independent of figure size
    ax.set_xlim(0, fig_w); ax.set_ylim(0, body_h); ax.axis("off")

    ax.add_patch(Rectangle((0, body_h - 0.44), fig_w, 0.44,
                           color=HEAD, ec="#22304d", lw=.6, zorder=1))
    ax.text(0.16, body_h - 0.22, f"● ● ●   {qid} · {title}", color=FG,
            fontsize=8.4, family=MONO, va="center", zorder=3)
    ax.text(fig_w - 0.16, body_h - 0.22, "SQLite 3.46", color=DIM, fontsize=7.2,
            family=MONO, va="center", ha="right", zorder=3)

    col = {"sql": "#8fb0d6", "dim": "#2f4360", "acc": ACC, "fg": FG,
           "note": WARN, "cmd": "#7d94b8"}
    y = body_h - 0.70
    for kind, text in lines:
        ax.text(0.16, y, text, color=col[kind], fontsize=FS, family=MONO,
                va="center")
        y -= LH

    p = SHOTS / f"{qid}.png"
    fig.savefig(p, dpi=150, facecolor=BG, bbox_inches="tight", pad_inches=0.07)
    plt.close(fig)
    return p


def main() -> None:
    data = json.loads((OUT / "sql_results.json").read_text())
    for q in data:
        render(q["id"], q["title"], q["sql"], q["columns"], q["rows"],
               q.get("elapsed_ms", 0.0))
    print(f"[shots] {len(data)} rendered -> output/screenshots/")


if __name__ == "__main__":
    main()
