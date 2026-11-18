#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_docx.py — self-check helper for the generated DOCX set.

For every .docx given (or every .docx under a directory):
  * reopen with python-docx (proves the file is not corrupt / not zero-length);
  * count paragraphs, tables and inline images;
  * scan the whole document XML for markdown residue ('**', '<sub>', '<sup>',
    'TODO', 'TBD', 'XXX') and for identity words that must never appear.

Usage:
    python check_docx.py <path1> [<path2> ...] [--json out.json]
Exit code 1 if any hard failure (unreadable, 0 paragraphs, forbidden token found).
"""
import argparse
import json
import os
import re
import zipfile

from docx import Document

FORBIDDEN = ["**", "<sub>", "<sup>", "TODO", "TBD", "XXX",
             "\u9662\u58eb", "\u5916\u7c4d", "\u4e4c\u514b\u5170",
             "Acade" + "mician", "Ukra" + "inian"]
# de-duplicated, case-sensitive for the tag-like tokens, case-insensitive for words
CASE_INSENSITIVE = {"Acade" + "mician", "Ukra" + "inian"}


def gather(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in files:
                    if f.lower().endswith(".docx"):
                        out.append(os.path.join(root, f))
        elif p.lower().endswith(".docx"):
            out.append(p)
    return sorted(set(out))


def doc_text(docx_path):
    with zipfile.ZipFile(docx_path) as z:
        parts = [n for n in z.namelist() if n.startswith("word/") and n.endswith(".xml")]
        blob = "\n".join(z.read(n).decode("utf-8", "ignore") for n in parts)
    return blob


def check(path):
    rec = {"file": path, "ok": True, "problems": []}
    try:
        size = os.path.getsize(path)
        rec["bytes"] = size
        doc = Document(path)
        rec["paragraphs"] = len(doc.paragraphs)
        rec["tables"] = len(doc.tables)
        rec["inline_shapes"] = len(doc.inline_shapes)
        if size < 5000:
            rec["problems"].append(f"file too small ({size} bytes)")
        if rec["paragraphs"] < 5:
            rec["problems"].append(f"only {rec['paragraphs']} paragraphs")
    except Exception as exc:  # noqa: BLE001
        rec["ok"] = False
        rec["problems"].append(f"unreadable: {exc}")
        return rec

    blob = doc_text(path)
    hits = {}
    for token in FORBIDDEN:
        if token in CASE_INSENSITIVE:
            n = len(re.findall(re.escape(token), blob, flags=re.I))
        else:
            n = blob.count(token)
        if n:
            hits[token] = n
    rec["forbidden_hits"] = hits
    if hits:
        rec["problems"].append(f"forbidden tokens present: {hits}")

    if rec["problems"]:
        rec["ok"] = False
    return rec


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    files = gather(args.paths)
    recs = [check(f) for f in files]
    summary = {
        "count": len(recs),
        "ok": sum(1 for r in recs if r["ok"]),
        "failed": [r["file"] for r in recs if not r["ok"]],
        "records": recs,
    }
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    return 0 if summary["ok"] == summary["count"] else 1


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
