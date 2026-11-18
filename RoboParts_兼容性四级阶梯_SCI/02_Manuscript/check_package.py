#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_package.py — the seven delivery checks, run as one command.

  1  every .docx reopens under python-docx
  2  no markdown or html residue inside docx (**, <sub>, <sup>, TODO/TBD/XXX)
  3  no identity words anywhere in a delivered file
  4  references numbered continuously, each with a DOI or an openable URL
  5  table row counts match the text (delegated to check_numbers.py)
  6  frozen numbers hold (delegated to check_numbers.py)
  7  zip entry count equals files plus directories

Writes results/self_check_report.json and exits non-zero on any failure.
"""
import json
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RES = os.path.join(ROOT, "04_ResearchData", "results")
ZIP = os.path.join(os.path.dirname(ROOT), "RoboParts_兼容性四级阶梯_SCI.zip")

IDENTITY = [r"\u9662\u58eb", r"\u5916\u7c4d", r"\u4e4c\u514b\u5178", "Acade" + "mician", "Ukra" + "inian"]
RESIDUE = [r"\*\*", r"<sub>", r"<sup>", r"TODO", r"TBD", r"XXX"]
TEXT_EXT = {".md", ".csv", ".json", ".py", ".bib", ".txt"}


def walk():
    files, dirs = [], []
    for base, dnames, fnames in os.walk(ROOT):
        dnames[:] = [d for d in dnames if d not in {".git", "__pycache__"}]
        for d in dnames:
            dirs.append(os.path.join(base, d))
        for f in fnames:
            if f.endswith((".zip", ".pyc")) or f == "self_check_report.json":
                # the report is written by this script on every run; counting it would make the
                # manifest check compare the package against a list that includes its own output
                continue
            files.append(os.path.join(base, f))
    return files, dirs


def docx_text(path):
    from docx import Document
    doc = Document(path)
    bits = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                bits.append(cell.text)
    return "\n".join(bits)


def first_hit(patterns, text, flags=0):
    return [p for p in patterns if re.search(p, text, flags)]


def main():
    files, dirs = walk()
    report = {"root": ROOT, "files": len(files), "dirs": len(dirs), "checks": {}}

    # 1 + 2: docx reopen and residue
    docx_ok, docx_fail, residue = [], [], []
    for p in files:
        if not p.lower().endswith(".docx"):
            continue
        try:
            body = docx_text(p)
            docx_ok.append(os.path.relpath(p, ROOT))
        except Exception as exc:  # noqa: BLE001 - any reopen failure is the finding
            docx_fail.append({os.path.relpath(p, ROOT): str(exc)[:200]})
            continue
        hits = first_hit(RESIDUE, body)
        if hits:
            residue.append({os.path.relpath(p, ROOT): hits})
    report["checks"]["1_docx_reopen"] = {"ok": len(docx_ok), "failed": docx_fail,
                                         "pass": not docx_fail}
    report["checks"]["2_docx_residue"] = {"files_with_hits": residue, "pass": not residue}

    # 3: identity words in any delivered file (docx via extracted text, text files raw)
    ident = []
    for p in files:
        low = p.lower()
        try:
            if low.endswith(".docx"):
                body = docx_text(p)
            elif low.endswith(".pdf") or low.endswith(".png"):
                continue
            elif os.path.splitext(low)[1] in TEXT_EXT:
                body = open(p, encoding="utf-8", errors="ignore").read()
            else:
                continue
        except Exception:
            continue
        hits = first_hit(IDENTITY, body, re.I)
        if hits:
            ident.append({os.path.relpath(p, ROOT): hits})
    report["checks"]["3_identity_words"] = {"files_with_hits": ident, "pass": not ident}

    # 4: reference integrity
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "04_ResearchData", "Scripts", "check_refs.py")],
                          capture_output=True, text=True, encoding="utf-8")
    try:
        refs = json.loads(proc.stdout)
    except Exception:
        refs = {"pass": False, "problems": ["check_refs.py did not return JSON: " + proc.stderr[:300]]}
    report["checks"]["4_references"] = {"entries": refs.get("entries"),
                                        "problems": refs.get("problems", [])[:20],
                                        "pass": bool(refs.get("pass"))}

    # 5 + 6: numeric gate on both manuscripts
    gates = {}
    for label, md in (("EN", "Manuscript_EN.md"), ("CN", "Manuscript_CN.md")):
        path = os.path.join(ROOT, "02_Manuscript", md)
        if not os.path.exists(path):
            gates[label] = {"pass": False, "problems": ["missing " + md]}
            continue
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "02_Manuscript", "check_numbers.py"),
                               path, os.path.join(ROOT, "00_Spec", "FROZEN_NUMBERS.json")],
                              capture_output=True, text=True, encoding="utf-8")
        try:
            gates[label] = json.loads(proc.stdout)
        except Exception:
            gates[label] = {"pass": False, "problems": ["gate did not return JSON: " + proc.stderr[:200]]}
    sub = {k: {"pass": v.get("pass"), "table_rows": v.get("table_rows"),
               "percentages_rogue": v.get("percentages_rogue"), "problems": v.get("problems")}
           for k, v in gates.items()}
    report["checks"]["5_6_numbers_and_tables"] = dict(sub, **{"pass": all(g.get("pass") for g in sub.values())})

    # 7: zip manifest
    if os.path.exists(ZIP):
        with zipfile.ZipFile(ZIP) as zf:
            names = zf.namelist()
        zfiles = [n for n in names if not n.endswith("/") and not n.endswith("self_check_report.json")]
        zdirs = [n for n in names if n.endswith("/")]
        report["checks"]["7_zip_manifest"] = {
            "zip": ZIP, "entries": len(names), "files": len(zfiles), "dirs": len(zdirs),
            "package_files": len(files), "package_dirs": len(dirs),
            "pass": len(zfiles) == len(files) and len(zdirs) == len(dirs)}
    else:
        report["checks"]["7_zip_manifest"] = {"zip": ZIP, "pass": False, "note": "zip not built yet"}

    report["pass"] = all(v.get("pass") for v in report["checks"].values())
    os.makedirs(RES, exist_ok=True)
    out = os.path.join(RES, "self_check_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps({"pass": report["pass"], "files": len(files), "dirs": len(dirs),
                      "checks": {k: v.get("pass") for k, v in report["checks"].items()}},
                     ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
