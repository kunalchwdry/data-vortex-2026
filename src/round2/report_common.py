"""
Data Vortex -- Round 2: shared reportlab helpers for the two PDF reports.

One style source so both PDFs look like they came from the same team (they
did). All content flows from metrics.json -- these helpers only format.
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from round2 import config as C

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

ACCENT = colors.HexColor("#1f3a5f")
ACCENT_LIGHT = colors.HexColor("#e8eef6")
GRID = colors.HexColor("#9aa5b1")
ZEBRA = colors.HexColor("#f5f7fa")

_STYLES = getSampleStyleSheet()
TITLE_S = ParagraphStyle("R2Title", parent=_STYLES["Title"], fontSize=26,
                         leading=30, textColor=ACCENT, spaceAfter=4)
SUBTITLE_S = ParagraphStyle("R2Subtitle", parent=_STYLES["Normal"], fontSize=12,
                            leading=15, textColor=colors.HexColor("#4a5a70"),
                            alignment=1, spaceAfter=2)
H1 = ParagraphStyle("R2H1", parent=_STYLES["Heading1"], fontSize=15, leading=18,
                    textColor=ACCENT, spaceBefore=14, spaceAfter=6,
                    keepWithNext=True)
H2 = ParagraphStyle("R2H2", parent=_STYLES["Heading2"], fontSize=11.5, leading=14,
                    textColor=ACCENT, spaceBefore=10, spaceAfter=4,
                    keepWithNext=True)
BODY = ParagraphStyle("R2Body", parent=_STYLES["Normal"], fontSize=9.5,
                      leading=13.5, spaceAfter=5)
SMALL = ParagraphStyle("R2Small", parent=_STYLES["Normal"], fontSize=8.5,
                       leading=11.5, spaceAfter=4)
BULLET = ParagraphStyle("R2Bullet", parent=BODY, leftIndent=14, spaceAfter=2,
                        bulletIndent=6)
CAPTION = ParagraphStyle("R2Caption", parent=_STYLES["Normal"], fontSize=8,
                         leading=10.5, alignment=1, textColor=colors.HexColor("#4a5a70"),
                         spaceBefore=2, spaceAfter=8)
CELL = ParagraphStyle("R2Cell", parent=_STYLES["Normal"], fontSize=8, leading=10)
CELL_H = ParagraphStyle("R2CellH", parent=CELL, textColor=colors.white,
                        fontName="Helvetica-Bold")
CELL_C = ParagraphStyle("R2CellC", parent=CELL, alignment=1)
CELL_HC = ParagraphStyle("R2CellHC", parent=CELL_H, alignment=1)
TITLE_CENTER = ParagraphStyle("R2TitleC", parent=TITLE_S, alignment=1)
FOOT_S = ParagraphStyle("R2Foot", parent=_STYLES["Normal"], fontSize=7.5,
                        leading=10, textColor=colors.HexColor("#5a6a80"))


def p(text: object, style: ParagraphStyle = BODY) -> Paragraph:
    """Body paragraph with XML-escaping (error samples contain <>&)."""
    return Paragraph(escape(str(text)), style)


def b(text: object) -> Paragraph:
    return Paragraph(escape(str(text)), BULLET, bulletText="•")


def cell(text: object, header: bool = False, center: bool = False) -> Paragraph:
    style = CELL_HC if (header and center) else CELL_H if header \
        else CELL_C if center else CELL
    return Paragraph(escape(str(text)), style)


def styled_table(rows: list[list], col_widths: list[float] | None = None,
                 center_cols: set[int] | None = None, fontsize: int = 8,
                 repeat_header: bool = True) -> Table:
    """Header-shaded, gridded, zebra-banded table. First row = header.

    Cells may be plain values (auto-wrapped) or ready Paragraphs/Flows.
    """
    center_cols = center_cols or set()
    body: list[list] = []
    for r, row in enumerate(rows):
        out = []
        for c, val in enumerate(row):
            if hasattr(val, "wrap"):  # already a flowable (Paragraph/Image)
                out.append(val)
            else:
                style = CELL_HC if (r == 0 and c in center_cols) \
                    else CELL_H if r == 0 else CELL_C if c in center_cols else CELL
                if fontsize != 8:
                    style = ParagraphStyle(f"{style.name}{fontsize}{c}{r}",
                                           parent=style, fontSize=fontsize,
                                           leading=fontsize + 2)
                out.append(Paragraph(escape(str(val)), style))
        body.append(out)
    table = Table(body, colWidths=col_widths, repeatRows=1 if repeat_header else 0)
    style_cmds: list = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(body)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    table.setStyle(TableStyle(style_cmds))
    return table


def img(path: Path | str, max_width: float = CONTENT_W,
        max_height: float = 200 * mm) -> Image:
    """Figure scaled to fit, aspect preserved (size read from the file)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"figure missing: {path}")
    with PILImage.open(path) as im:
        w, h = im.size
    scale = min(max_width / w, max_height / h)
    return Image(str(path), width=w * scale, height=h * scale)


def title_block(story: list, title: str, subtitle: str, lines: list[str]) -> None:
    story.append(Spacer(1, 34 * mm))
    story.append(Paragraph(escape(title), TITLE_CENTER))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(escape(subtitle), SUBTITLE_S))
    story.append(Spacer(1, 10 * mm))
    for line in lines:
        story.append(Paragraph(escape(line), SUBTITLE_S))
    story.append(Spacer(1, 12 * mm))
    story.append(p("Every number in this report is computed by the Round 2 pipeline "
                   "from Dataset 2 and the trained models -- nothing is typed by hand. "
                   "Re-run ./run_round2.sh to reproduce this PDF byte-for-byte "
                   "(modulo timestamps).", SMALL))


def footer(canvas, doc, short_title: str) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#5a6a80"))
    canvas.drawString(MARGIN, 12 * mm,
                      f"{C.TEAM_NAME} · Data Vortex Round 2 · {short_title}")
    canvas.drawRightString(PAGE_W - MARGIN, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def f4(value: object) -> str:
    """Format a float metric or show em-dash for missing."""
    if value is None:
        return "—"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def pct_share(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "—"
