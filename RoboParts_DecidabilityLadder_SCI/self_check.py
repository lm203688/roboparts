#!/usr/bin/env python3
"""Self-check the package before zipping."""
import re, zipfile
from pathlib import Path
from docx import Document

BASE = Path(r"C:\Users\xing\Desktop\所有项目\RoboParts_DecidabilityLadder_SCI")

# 1. Identity red-line words across all text artifacts
red = ["院士", "外籍", "乌克兰", "Academician", "Ukrainian", "ukrainian", "academician"]
hits = []
for p in BASE.rglob("*"):
    if p.is_file() and p.suffix.lower() in {".md", ".py", ".csv", ".txt"}:
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for w in red:
            if w in t:
                hits.append((p.name, w))
print("[1] Identity red-line hits:", hits if hits else "NONE (good)")

# 2. TODO / TBD / XXX
todo = []
for p in BASE.rglob("*.md"):
    t = p.read_text(encoding="utf-8", errors="ignore")
    for w in ["TODO", "TBD", "XXX", "PLACEHOLDER_PENDING"]:
        if re.search(rf"\b{w}\b", t):
            # the manuscript uses 'pending' as prose; only flag literal TODO/TBD/XXX
            todo.append((p.name, w))
print("[2] TODO/TBD/XXX literal hits:", todo if todo else "NONE (good)")

# 3. Markdown residue inside docx XML: **, <sub>, <sup>
docx_files = list((BASE/"02_Manuscript").glob("*.docx"))
residue = []
for d in docx_files:
    with zipfile.ZipFile(d) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
        for tok in ["**", "<sub>", "</sub>", "<sup>", "</sup>"]:
            if tok in xml:
                residue.append((d.name, tok))
print(f"[3] docx read-back ({len(docx_files)} files) markdown residue:", residue if residue else "NONE (good)")

# 3b. python-docx read-back sanity: paragraph/table counts
for d in docx_files:
    doc = Document(d)
    print(f"    {d.name}: {len(doc.paragraphs)} paragraphs, {len(doc.tables)} tables")

# 4. Reference list continuity: count numbered refs in EN manuscript
en = (BASE/"02_Manuscript"/"Manuscript_EN.md").read_text(encoding="utf-8")
refs = re.findall(r"^\d+\.\s", en.split("## References")[-1], flags=re.M)
print(f"[4] Numbered reference entries in EN: {len(refs)} (expect 11)")

# 5. Forbidden hype words
hype = ["unlock", "breakthrough", "first proof", "game-changing", "首次证明", "解锁", "突破"]
hits2 = []
for p in (BASE/"02_Manuscript").glob("*.md"):
    t = p.read_text(encoding="utf-8", errors="ignore").lower()
    for w in hype:
        if w in t:
            hits2.append((p.name, w))
print("[5] Hype-word hits:", hits2 if hits2 else "NONE (good)")

# 6. File inventory
all_files = [p for p in BASE.rglob("*") if p.is_file()]
all_dirs = [p for p in BASE.rglob("*") if p.is_dir()]
print(f"[6] Package files: {len(all_files)}; directories: {len(all_dirs)}")
for p in sorted(all_files):
    print("   ", p.relative_to(BASE), p.stat().st_size)
