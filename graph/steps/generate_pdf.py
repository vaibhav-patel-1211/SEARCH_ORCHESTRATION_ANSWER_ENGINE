"""
generate_pdf.py - Converts markdown answer into a professionally formatted PDF.
Uses ReportLab to render:
  - Headings (H1-H4) with custom fonts and colors
  - Code blocks with syntax-friendly monospace font and background
  - Tables with alternating row colors
  - Bullet/numbered lists
  - Blockquotes
  - A title page with the query topic

Output is saved to static/reports/ and served via download endpoint.
"""

from __future__ import annotations

import os
import re
import uuid

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageBreak, PageTemplate,
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    HRFlowable,
)

OUTPUT_DIR = "static/reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

W, H = A4
MARGIN = 1.1 * inch

# ── Color Palette (professional dark blue theme) ──
C_TITLE      = colors.HexColor("#0f172a")
C_H1         = colors.HexColor("#1e3a5f")
C_H2         = colors.HexColor("#1e3a5f")
C_H3         = colors.HexColor("#334155")
C_BODY       = colors.HexColor("#1e293b")
C_MUTED      = colors.HexColor("#64748b")
C_CODE_BG    = colors.HexColor("#f1f5f9")
C_CODE_BORDER= colors.HexColor("#cbd5e1")
C_TABLE_HEAD = colors.HexColor("#1e3a5f")
C_TABLE_ALT  = colors.HexColor("#f8fafc")
C_RULE       = colors.HexColor("#e2e8f0")

# ── Paragraph Styles ──
def make_styles():
    """Create all the paragraph styles used throughout the PDF."""
    base = getSampleStyleSheet()
    N = base["Normal"]

    def S(name, **kw):
        return ParagraphStyle(name, parent=N, **kw)

    return {
        "h1": S("H1", fontName="Helvetica-Bold", fontSize=20, textColor=C_H1,
                 spaceBefore=18, spaceAfter=6, leading=26),
        "h2": S("H2", fontName="Helvetica-Bold", fontSize=15, textColor=C_H2,
                 spaceBefore=14, spaceAfter=4, leading=20),
        "h3": S("H3", fontName="Helvetica-Bold", fontSize=12, textColor=C_H3,
                 spaceBefore=10, spaceAfter=3, leading=16),
        "h4": S("H4", fontName="Helvetica-BoldOblique", fontSize=11, textColor=C_H3,
                 spaceBefore=8, spaceAfter=2, leading=14),
        "body": S("Body", fontName="Helvetica", fontSize=10.5, textColor=C_BODY,
                  leading=16, spaceAfter=6, alignment=TA_JUSTIFY),
        "bullet": S("Bullet", fontName="Helvetica", fontSize=10.5, textColor=C_BODY,
                    leading=15, spaceAfter=3, leftIndent=18, firstLineIndent=0),
        "bullet2": S("Bullet2", fontName="Helvetica", fontSize=10, textColor=C_BODY,
                     leading=14, spaceAfter=2, leftIndent=36, firstLineIndent=0),
        "code": S("Code", fontName="Courier", fontSize=8.5, textColor=C_BODY,
                  leading=12, spaceAfter=0, spaceBefore=0,
                  leftIndent=8, rightIndent=8, wordWrap="CJK"),
        "quote": S("Quote", fontName="Helvetica-Oblique", fontSize=10, textColor=C_MUTED,
                   leading=15, spaceAfter=4, leftIndent=24, rightIndent=12),
        "cell_head": S("CellH", fontName="Helvetica-Bold", fontSize=8.5,
                       textColor=colors.white, leading=12),
        "cell": S("Cell", fontName="Helvetica", fontSize=8.5,
                  textColor=C_BODY, leading=12),
        "footer": S("Footer", fontName="Helvetica", fontSize=8,
                    textColor=C_MUTED, alignment=TA_CENTER),
    }


# ── Text helpers (escape HTML entities and convert markdown inline formatting) ──

def _esc(text: str) -> str:
    """Escape special XML characters for ReportLab."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _inline(text: str) -> str:
    """Convert markdown inline formatting (bold, italic, code) to ReportLab XML tags."""
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
    text = re.sub(r"\*\*(.+?)\*\*",     r"<b>\1</b>",         text)
    text = re.sub(r"\*(.+?)\*",         r"<i>\1</i>",          text)
    text = re.sub(r"__(.+?)__",         r"<b>\1</b>",          text)
    text = re.sub(r"_(.+?)_",           r"<i>\1</i>",          text)
    text = re.sub(r"`([^`]+)`",         lambda m: f'<font name="Courier">{_esc(m.group(1))}</font>', text)
    # Markdown links → plain text with URL in parentheses
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    return text

def _prep(text: str) -> str:
    """Escape then apply inline formatting."""
    return _inline(_esc(text))


# ── Code block renderer ──
def _code_block(lines: list[str], styles: dict) -> list:
    """Render a fenced code block as a table with gray background."""
    inner = "<br/>".join(_esc(l) for l in lines) or " "
    para = Paragraph(
        f'<font name="Courier" size="8.5">{inner}</font>',
        styles["code"],
    )
    data = [[para]]
    t = Table(data, colWidths=[W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), C_CODE_BG),
        ("BOX",          (0, 0), (-1, -1), 0.75, C_CODE_BORDER),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
    ]))
    return [t, Spacer(1, 6)]


# ── Table renderer ──
def _md_table(rows: list[list[str]], styles: dict) -> list:
    """Render a markdown table with header styling and alternating row colors."""
    if not rows:
        return []
    col_count = max(len(r) for r in rows)
    padded = [r + [""] * (col_count - len(r)) for r in rows]
    col_w = (W - 2 * MARGIN) / col_count

    para_rows = []
    for ri, row in enumerate(padded):
        st = styles["cell_head"] if ri == 0 else styles["cell"]
        para_rows.append([Paragraph(_prep(c), st) for c in row])

    t = Table(para_rows, colWidths=[col_w] * col_count, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_TABLE_HEAD),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, C_TABLE_ALT]),
        ("GRID",          (0, 0), (-1, -1), 0.4, C_RULE),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return [t, Spacer(1, 10)]


# ── Page header/footer ──
def _make_page_template(doc, title: str, styles: dict):
    """Creates page template with footer showing title and page number."""
    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(C_RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 0.7 * inch, W - MARGIN, 0.7 * inch)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(C_MUTED)
        canvas.drawString(MARGIN, 0.45 * inch, title[:80])
        canvas.drawRightString(W - MARGIN, 0.45 * inch, f"Page {doc.page}")
        canvas.restoreState()

    frame = Frame(MARGIN, 0.9 * inch, W - 2 * MARGIN, H - MARGIN - 0.9 * inch, id="body")
    return PageTemplate(id="main", frames=[frame], onPage=on_page)


# ── Main markdown-to-PDF parser ──
def _parse(content: str, styles: dict) -> list:
    """
    Parses markdown content line by line and converts each element
    into ReportLab flowables (Paragraph, Table, Spacer, etc.)
    """
    story = []
    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Fenced code block
        if stripped.startswith("```"):
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            story.extend(_code_block(code_lines, styles))
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", stripped):
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", thickness=0.5, color=C_RULE, spaceAfter=6))
            i += 1
            continue

        # Headings (# to ####)
        hm = re.match(r"^(#{1,4})\s+(.*)", line)
        if hm:
            level = len(hm.group(1))
            text = _prep(hm.group(2).strip())
            s = styles[f"h{level}"] if level <= 4 else styles["h4"]
            story.append(Paragraph(text, s))
            if level == 1:
                story.append(HRFlowable(width="100%", thickness=1.5, color=C_H1, spaceAfter=4))
            elif level == 2:
                story.append(HRFlowable(width="40%", thickness=0.75, color=C_RULE, spaceAfter=4))
            i += 1
            continue

        # Markdown table (lines containing |)
        if "|" in line:
            table_lines: list[str] = []
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            rows = []
            for tl in table_lines:
                if re.match(r"^\|?[\s\-:|]+\|", tl):
                    continue  # skip separator row
                cells = [c.strip() for c in tl.strip().strip("|").split("|")]
                rows.append(cells)
            story.extend(_md_table(rows, styles))
            continue

        # Bullet list (- / * / +)
        bm = re.match(r"^(\s*)([-*+])\s+(.*)", line)
        if bm:
            indent = len(bm.group(1))
            text = _prep(bm.group(3))
            s = styles["bullet2"] if indent >= 2 else styles["bullet"]
            story.append(Paragraph(f"• &nbsp;{text}", s))
            i += 1
            continue

        # Numbered list
        nm = re.match(r"^(\s*)\d+\.\s+(.*)", line)
        if nm:
            indent = len(nm.group(1))
            text = _prep(nm.group(2))
            s = styles["bullet2"] if indent >= 2 else styles["bullet"]
            story.append(Paragraph(f"• &nbsp;{text}", s))
            i += 1
            continue

        # Blockquote
        if stripped.startswith(">"):
            text = _prep(stripped.lstrip("> ").strip())
            story.append(Paragraph(text, styles["quote"]))
            i += 1
            continue

        # Empty line = spacer
        if not stripped:
            story.append(Spacer(1, 5))
            i += 1
            continue

        # Normal paragraph
        text = _prep(stripped)
        story.append(Paragraph(text, styles["body"]))
        i += 1

    return story


# ── Node entry point ──
def generate_pdf_node(state: dict) -> dict:
    """
    Graph node that generates a PDF from the final_answer.
    Creates a title page + formatted content, saves to static/reports/.
    Returns the file path and filename for the download endpoint.
    """
    topic   = state.get("prompt", "Report")[:120]
    content = state.get("final_answer", "").strip()
    if not content:
        return {"pdf_path": None, "pdf_filename": None}

    file_id  = uuid.uuid4().hex[:10]
    filename = f"report_{file_id}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)

    styles = make_styles()

    doc = BaseDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=0.9 * inch,
        title=topic,
    )
    doc.addPageTemplates([_make_page_template(doc, topic, styles)])

    story: list = []

    # Title page
    story.append(Spacer(1, 1.8 * inch))
    story.append(Paragraph(_esc(topic), ParagraphStyle(
        "DocTitle", fontName="Helvetica-Bold", fontSize=28,
        textColor=C_TITLE, alignment=TA_CENTER, leading=36, spaceAfter=10,
    )))
    story.append(HRFlowable(width="60%", thickness=2, color=C_H1,
                             hAlign="CENTER", spaceAfter=12))
    story.append(Paragraph("Generated by Horizon AI", ParagraphStyle(
        "DocSub", fontName="Helvetica", fontSize=13,
        textColor=C_MUTED, alignment=TA_CENTER,
    )))
    story.append(PageBreak())

    # Main content (parsed from markdown)
    story.extend(_parse(content, styles))

    doc.build(story)
    print(f"✅ PDF generated: {filepath}")
    return {"pdf_path": filepath, "pdf_filename": filename}
