#!/usr/bin/env python3
"""Convert the manuscript markdown files to docx with python-docx.
Handles: headings (#..###), tables (| ... |), bold **...**, italic *...*,
horizontal rules, paragraphs, and embeds the three figures at their callout lines.
"""
import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = Path(r"C:\Users\xing\Desktop\所有项目\RoboParts_DecidabilityLadder_SCI")
FIG = BASE / "05_Figures"

FIG_MAP = {
    "Fig. 1": FIG / "Fig1_ladder_waterfall.png",
    "Fig. 2": FIG / "Fig2_three_axis_forest.png",
    "Fig. 3": FIG / "Fig3_taxonomy_of_zeros.png",
}


def add_runs_with_inline(paragraph, text):
    """Render **bold** and *italic* inline markers."""
    # bold first
    parts = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = paragraph.add_run(part[2:-2]); r.bold = True
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            r = paragraph.add_run(part[1:-1]); r.italic = True
        else:
            paragraph.add_run(part)


def flush_table(doc, rows):
    """rows: list of list[str]; first row is header."""
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    t = doc.add_table(rows=len(rows), cols=ncols)
    t.style = "Light Grid Accent 1"
    for i, row in enumerate(rows):
        for j in range(ncols):
            cell = t.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            txt = row[j] if j < len(row) else ""
            add_runs_with_inline(p, txt)
            for r in p.runs:
                r.font.size = Pt(9)
                if i == 0:
                    r.bold = True


def convert(md_path: Path, out_path: Path, title: str):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(11)

    lines = md_path.read_text(encoding="utf-8").splitlines()
    i = 0
    table_buf = []
    while i < len(lines):
        line = lines[i].rstrip()
        # table block?
        if line.startswith("|") and line.endswith("|"):
            # collect
            tbl = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                # skip separator rows (---)
                if not all(re.fullmatch(r":?-{2,}:?", c or "---") for c in row):
                    tbl.append(row)
                i += 1
            flush_table(doc, tbl)
            continue
        if line.strip() == "---":
            doc.add_paragraph()
            i += 1
            continue
        if line.startswith("# "):
            h = doc.add_heading(line[2:].strip(), level=0)
        elif line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=1)
        elif line.startswith("### "):
            doc.add_heading(line[4:].strip(), level=2)
        elif line.strip() == "":
            pass
        else:
            p = doc.add_paragraph()
            add_runs_with_inline(p, line)
            # embed figure if this line names a figure callout we have
            for tag, fpath in FIG_MAP.items():
                if tag in line and fpath.exists():
                    doc.add_picture(str(fpath), width=Inches(5.6))
                    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        i += 1

    doc.save(out_path)
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    convert(BASE/"02_Manuscript"/"Manuscript_EN.md",
            BASE/"02_Manuscript"/"Manuscript_EN.docx",
            "EN")
    convert(BASE/"02_Manuscript"/"Manuscript_CN.md",
            BASE/"02_Manuscript"/"Manuscript_CN.docx",
            "CN")
