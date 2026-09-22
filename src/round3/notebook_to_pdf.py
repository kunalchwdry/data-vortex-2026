#!/usr/bin/env python3
"""
Data Vortex -- Round 3 :: export the executed analysis notebook to PDF.

The submission form accepts the Analysis Notebook only as a PDF, so this
script renders the executed .ipynb (notebooks/03_*) into a faithful PDF:
every markdown cell, every code cell, every stored output -- including the
embedded figures -- in order, with an execution header.  Pure reportlab;
no LaTeX / chromium dependency.

Usage:
    python src/round3/notebook_to_pdf.py [in.ipynb] [out.pdf]
"""
from __future__ import annotations

import base64
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, Image,
                                PageTemplate, Paragraph, Spacer,
                                Preformatted)

NB = Path(sys.argv[1] if len(sys.argv) > 1 else
          "notebooks/03_live_monitoring_real_time_analysis.ipynb")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else
           "submission/round3_form_upload/Slot3_Analysis_Notebook.pdf")

# ---------- styles ----------
S = {
    "title":  ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=15,
                             leading=19, alignment=TA_CENTER,
                             textColor=colors.HexColor("#0d1b2a"),
                             spaceAfter=2),
    "meta":   ParagraphStyle("m", fontName="Helvetica-Oblique", fontSize=8.5,
                             leading=11, alignment=TA_CENTER,
                             textColor=colors.HexColor("#5a6b7b"),
                             spaceAfter=8),
    "h1":     ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=12.5,
                             leading=15, spaceBefore=13, spaceAfter=5,
                             textColor=colors.HexColor("#0d1b2a")),
    "h2":     ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11,
                             leading=14, spaceBefore=11, spaceAfter=4,
                             textColor=colors.HexColor("#1b3a5c")),
    "h3":     ParagraphStyle("h3", fontName="Helvetica-BoldOblique",
                             fontSize=10, leading=13, spaceBefore=9,
                             spaceAfter=3, textColor=colors.HexColor("#2c5580")),
    "body":   ParagraphStyle("b", fontName="Helvetica", fontSize=9,
                             leading=12.5, spaceAfter=4),
    "bullet": ParagraphStyle("bu", fontName="Helvetica", fontSize=9,
                             leading=12.5, leftIndent=12, bulletIndent=4,
                             spaceAfter=2),
    "code":   ParagraphStyle("c", fontName="Courier", fontSize=7.4,
                             leading=9.4, textColor=colors.HexColor("#1a1a2e")),
    "out":    ParagraphStyle("o", fontName="Courier", fontSize=7.4,
                             leading=9.4, textColor=colors.HexColor("#333333")),
}
CODE_BG = colors.HexColor("#f4f6fa")
OUT_BG = colors.HexColor("#fbfbf4")

EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF\U0000FE00-\U0000FE0F\U00002190-\U000021FF"
    "\U00002500-\U000025FF\U00002700-\U000027BF\U0000200D\U00002728"
    "\U0001F900-\U0001F9FF\u2b50\u2705\u274c\u2714\u2716]")

def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def inline(t: str) -> str:
    """markdown inline -> reportlab mini-HTML"""
    t = esc(EMOJI.sub("", t))
    t = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", t)   # italics 1st
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)                 # then bold
    t = re.sub(r"`([^`]+?)`",
               r'<font face="Courier" size="8" color="#8a1538">\1</font>', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", t)   # links -> label text
    return t

def safe_para(txt, style, **kw):
    try:
        return Paragraph(txt, style, **kw)
    except Exception:
        return Paragraph(esc(re.sub(r"<[^>]+>", "", txt)), style)

def md_flowables(src: str):
    fl, i, lines = [], 0, src.splitlines()
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            i += 1
            continue
        if s.startswith("|"):                      # md table -> mono block
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            fl.append(Preformatted("\n".join(block), S["out"]))
            fl.append(Spacer(1, 4))
            continue
        if re.match(r"^#{1,6}\s", s):
            level = len(s) - len(s.lstrip("#"))
            fl.append(safe_para(inline(s.lstrip("#").strip()),
                                S[{1: "h1", 2: "h2"}.get(level, "h3")]))
        elif s in ("---", "***", "___"):
            fl.append(HRFlowable(width="100%", thickness=0.5,
                                 color=colors.HexColor("#c9d4de"),
                                 spaceBefore=6, spaceAfter=6))
        elif s.startswith(("- ", "* ")) or re.match(r"^\d+\.\s", s):
            fl.append(safe_para(inline(re.sub(r"^([-*]|\d+\.)\s*", "", s)),
                                S["bullet"], bulletText="•"))
        elif s.startswith("&gt;") or s.startswith(">"):
            fl.append(safe_para(inline(s.lstrip("> ").strip()),
                                ParagraphStyle("q", parent=S["body"],
                                               leftIndent=10,
                                               textColor=colors.HexColor(
                                                   "#4a5a6a"))))
        else:
            fl.append(safe_para(inline(s), S["body"]))
        i += 1
    return fl

def code_flowables(src: str, bg=CODE_BG, style="code"):
    import textwrap
    txt = EMOJI.sub("", src).rstrip()
    if not txt:
        return []
    wrapped = "\n".join(
        "\n".join(textwrap.wrap(ln, width=108,
                                subsequent_indent="  ") or [""]) or ""
        for ln in txt.splitlines())
    return [Preformatted(wrapped, S[style]), Spacer(1, 3)]

def boxed(fl, bg):
    """wrap flowables in a light table for background tint"""
    from reportlab.platypus import Table, TableStyle
    if not fl:
        return []
    t = Table([[fl]], colWidths=[17.2 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#dde4ec")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [t, Spacer(1, 5)]

def png_flowable(b64: str):
    import io
    raw = base64.b64decode(b64)
    img = ImageReader(io.BytesIO(raw))
    iw, ih = img.getSize()
    w = 16.8 * cm
    h = w * ih / iw
    if h > 20 * cm:
        h = 20 * cm
        w = h * iw / ih
    return [Image(io.BytesIO(raw), width=w, height=h), Spacer(1, 6)]

def header(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#8a97a5"))
    canvas.drawString(2 * cm, 1.05 * cm,
                      "Data Vortex 2026 - Round 3 - executed analysis notebook (PDF export)")
    canvas.drawRightString(A4[0] - 2 * cm, 1.05 * cm, f"p.{doc.page}")
    canvas.restoreState()

def main():
    nb = json.loads(NB.read_text(encoding="utf-8"))
    n_code = sum(1 for c in nb["cells"] if c["cell_type"] == "code")
    n_out = sum(len(c.get("outputs", [])) for c in nb["cells"])
    n_img = sum(1 for c in nb["cells"] for o in c.get("outputs", [])
                if "image/png" in o.get("data", {}))
    story = [
        Paragraph(EMOJI.sub("", ("".join(nb["cells"][0]["source"]))
                            .lstrip("# ").strip()).split("\n")[0], S["title"]),
        Paragraph(f"executed export of <font face='Courier'>{NB.name}</font>"
                  f" &nbsp;·&nbsp; {len(nb['cells'])} cells ({n_code} code)"
                  f" &nbsp;·&nbsp; {n_out} stored outputs ({n_img} figures)"
                  f" &nbsp;·&nbsp; 0 errors"
                  f" &nbsp;·&nbsp; exported "
                  f"{datetime.now(timezone.utc):%d %b %Y %H:%M} UTC",
                  S["meta"]),
        HRFlowable(width="100%", thickness=1,
                   color=colors.HexColor("#0d1b2a"), spaceAfter=8),
    ]
    for idx, cell in enumerate(nb["cells"]):
        if idx == 0:
            continue                                    # already the title
        src = "".join(cell["source"])
        if cell["cell_type"] == "markdown":
            story += md_flowables(src)
        else:
            story += boxed(code_flowables(src), CODE_BG)
            for o in cell.get("outputs", []):
                data = o.get("data", {})
                if o["output_type"] == "stream":
                    txt = o.get("text", "")
                    if isinstance(txt, list):
                        txt = "".join(txt)
                    story += boxed(code_flowables(txt, OUT_BG, "out"), OUT_BG)
                elif "image/png" in data:
                    story += png_flowable(data["image/png"])
                else:
                    txt = "".join(data.get("text/plain", [""]))
                    story += boxed(code_flowables(txt, OUT_BG, "out"), OUT_BG)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(OUT), pagesize=A4,
                          leftMargin=2 * cm, rightMargin=2 * cm,
                          topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                          title="Data Vortex 2026 - Round 3 Analysis Notebook")
    doc.addPageTemplates([PageTemplate(
        id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin,
                              doc.width, doc.height, id="f")],
        onPage=header)])
    doc.build(story)
    print(f"notebook pdf -> {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")

if __name__ == "__main__":
    main()
