#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2docx.py — Markdown -> DOCX converter for this paper package.

Design goals (they are the reasons this exists rather than a generic converter):
  * no markdown residue in the output: '**', '*', '`', '<sub>', '<sup>' must not survive
    as literal characters anywhere in the produced XML;
  * pipe tables become real Word tables with a three-line (booktabs-like) look;
  * images referenced by ![](path) are embedded and centred, with the caption line
    that follows kept as a caption paragraph;
  * English documents use Times New Roman 12 pt / 1.5 spacing (submission style);
    Chinese documents use SimSun 10.5 pt with the East-Asian font set properly.

Usage:
    python md2docx.py <input.md> <output.docx> [--lang en|zh] [--title "Title"] [--no-page-numbers]
"""

import argparse
import os
import re
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


# ----------------------------------------------------------------------------- helpers

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def has_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text or ""))


def set_run_font(run, latin="Times New Roman", cjk="SimSun", size=None, bold=None,
                 italic=None):
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    run.font.name = latin
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    rfonts.set(qn("w:eastAsia"), cjk)
    rfonts.set(qn("w:cs"), latin)


def add_page_number_footer(section, latin="Times New Roman"):
    footer = section.footer
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    set_run_font(run, latin=latin, size=9)
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._element.append(fld_begin)
    run._element.append(instr)
    run._element.append(fld_end)


def set_cell_borders(cell, top=False, bottom=False):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge, on in (("top", top), ("bottom", bottom)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single" if on else "nil")
        el.set(qn("w:sz"), "8" if on else "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tcPr.append(borders)


# ------------------------------------------------------------------- inline tokenizer

INLINE_RE = re.compile(
    r"(<sub>(?P<sub>.*?)</sub>)|(<sup>(?P<sup>.*?)</sup>)|(\*\*(?P<bold>.*?)\*\*)|"
    r"(?<!\*)\*(?P<ital>[^*\n]+?)\*(?!\*)|(`(?P<code>[^`]+)`)",
    re.S,
)


def add_inline(paragraph, text, latin, cjk, size, default_bold=False, default_italic=False):
    """Write text into paragraph, turning markdown/HTML-ish inline markup into real runs."""
    text = text or ""
    pos = 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            head = text[pos:m.start()]
            if head:
                r = paragraph.add_run(head)
                set_run_font(r, latin, cjk, size, bold=default_bold, italic=default_italic)
        if m.group("sub"):
            r = paragraph.add_run(m.group("sub"))
            set_run_font(r, latin, cjk, size, bold=default_bold)
            r.font.subscript = True
        elif m.group("sup"):
            r = paragraph.add_run(m.group("sup"))
            set_run_font(r, latin, cjk, size, bold=default_bold)
            r.font.superscript = True
        elif m.group("bold"):
            r = paragraph.add_run(m.group("bold"))
            set_run_font(r, latin, cjk, size, bold=True, italic=default_italic)
        elif m.group("ital"):
            r = paragraph.add_run(m.group("ital"))
            set_run_font(r, latin, cjk, size, bold=default_bold, italic=True)
        elif m.group("code"):
            r = paragraph.add_run(m.group("code"))
            set_run_font(r, "Courier New", cjk, size - 1 if size else None,
                         bold=default_bold)
        pos = m.end()
    tail = text[pos:]
    if tail:
        r = paragraph.add_run(tail)
        set_run_font(r, latin, cjk, size, bold=default_bold, italic=default_italic)


# ------------------------------------------------------------------------ md parsing

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
NUMBER_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
IMAGE_RE = re.compile(r"^\s*!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)\s*$")
HR_RE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")


def split_table_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def is_table_start(lines, i):
    return ("|" in lines[i] and i + 1 < len(lines) and TABLE_SEP_RE.match(lines[i + 1]))


def convert(md_path, docx_path, lang="en", title=None, page_numbers=True):
    with open(md_path, "r", encoding="utf-8") as fh:
        raw = fh.read()

    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    doc = Document()

    latin = "Times New Roman"
    cjk = "SimSun" if lang == "zh" else "SimSun"
    body_size = 12 if lang == "en" else 10.5
    line_spacing = 1.5 if lang == "en" else 1.35

    # page setup: A4, 2.54 cm top/bottom, 2.2 cm left/right
    for section in doc.sections:
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)
        if page_numbers:
            add_page_number_footer(section, latin=latin)

    normal = doc.styles["Normal"]
    normal.font.name = latin
    normal.font.size = Pt(body_size)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), cjk)
    pf = normal.paragraph_format
    pf.line_spacing = line_spacing
    pf.space_after = Pt(6 if lang == "en" else 4)

    if title:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(14)
        r = p.add_run(title)
        set_run_font(r, latin, cjk, body_size + 6, bold=True)

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if HR_RE.match(line):
            # horizontal rule -> thin empty paragraph (never a line of dashes in the docx)
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            i += 1
            continue

        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            p = doc.add_paragraph()
            pf_h = p.paragraph_format
            pf_h.space_before = Pt(14 if level <= 2 else 10)
            pf_h.space_after = Pt(6 if level <= 2 else 4)
            pf_h.keep_with_next = True
            size = {1: body_size + 6, 2: body_size + 3, 3: body_size + 1,
                    4: body_size, 5: body_size, 6: body_size}[level]
            add_inline(p, text, latin, cjk, size, default_bold=True)
            i += 1
            continue

        m = IMAGE_RE.match(line)
        if m:
            path = m.group("path")
            if not os.path.isabs(path):
                path = os.path.join(os.path.dirname(os.path.abspath(md_path)), path)
            if os.path.exists(path):
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(4)
                run = p.add_run()
                width = Cm(16.0) if lang == "en" else Cm(15.5)
                run.add_picture(path, width=width)
            else:
                p = doc.add_paragraph()
                add_inline(p, f"[missing image: {path}]", latin, cjk, body_size,
                           default_italic=True)
            i += 1
            continue

        if is_table_start(lines, i):
            header = split_table_row(lines[i])
            i += 2  # skip header + separator
            rows = []
            while i < n and lines[i].strip() and "|" in lines[i]:
                rows.append(split_table_row(lines[i]))
                i += 1
            ncols = len(header)
            table = doc.add_table(rows=1, cols=ncols)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.autofit = True
            hdr = table.rows[0].cells
            for c, text in enumerate(header[:ncols]):
                hdr[c].text = ""
                p = hdr[c].paragraphs[0]
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.line_spacing = 1.0
                add_inline(p, text, latin, cjk, body_size - 1, default_bold=True)
                set_cell_borders(hdr[c], top=True, bottom=True)
            for r_values in rows:
                cells = table.add_row().cells
                last = r_values == rows[-1]
                for c in range(ncols):
                    text = r_values[c] if c < len(r_values) else ""
                    cells[c].text = ""
                    p = cells[c].paragraphs[0]
                    p.paragraph_format.space_after = Pt(2)
                    p.paragraph_format.line_spacing = 1.0
                    add_inline(p, text, latin, cjk, body_size - 1)
                    if last:
                        set_cell_borders(cells[c], bottom=True)
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            continue

        m = BULLET_RE.match(line)
        if m:
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = line_spacing
            add_inline(p, m.group(1).strip(), latin, cjk, body_size)
            i += 1
            continue

        m = NUMBER_RE.match(line)
        if m:
            p = doc.add_paragraph(style="List Number")
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = line_spacing
            add_inline(p, m.group(2).strip(), latin, cjk, body_size)
            i += 1
            continue

        # blockquote -> indented, italic-less paragraph
        if stripped.startswith(">"):
            body = stripped.lstrip(">").strip()
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            p.paragraph_format.space_after = Pt(4)
            add_inline(p, body, latin, cjk, body_size - 1, default_italic=False)
            i += 1
            continue

        # caption lines (Table N / Fig. N / 表 N / 图 N) get a compact style
        is_caption = bool(re.match(r"^(Table\s+\d|Fig\.?\s*\d|Figure\s+\d|表\s*\d|图\s*\d)", stripped))

        # ordinary paragraph: gather until blank / structural line
        buf = [stripped]
        i += 1
        while i < n:
            nxt = lines[i]
            s = nxt.strip()
            if (not s or HEADING_RE.match(nxt) or is_table_start(lines, i)
                    or BULLET_RE.match(nxt) or NUMBER_RE.match(nxt)
                    or IMAGE_RE.match(nxt) or HR_RE.match(nxt) or s.startswith(">")):
                break
            buf.append(s)
            i += 1

        text = " ".join(buf)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if not is_caption else WD_ALIGN_PARAGRAPH.LEFT
        if is_caption:
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(10)
            p.paragraph_format.line_spacing = 1.15
            add_inline(p, text, latin, cjk, body_size - 1.5, default_bold=False)
        else:
            p.paragraph_format.first_line_indent = Cm(0)
            add_inline(p, text, latin, cjk, body_size)

    doc.save(docx_path)
    return docx_path


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--lang", default="en", choices=["en", "zh"])
    ap.add_argument("--title", default=None)
    ap.add_argument("--no-page-numbers", action="store_true")
    args = ap.parse_args(argv)
    out = convert(args.src, args.dst, lang=args.lang, title=args.title,
                  page_numbers=not args.no_page_numbers)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1:])
