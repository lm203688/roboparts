#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_refs.py — cross-check the manuscript reference list against the verified ledger.

For each numbered entry in the manuscript this prints whether the entry carries a DOI or an
openable URL, and which DOI the ledger records for the same work, so a mismatch or a missing
link is visible instead of assumed.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MD = os.path.join(ROOT, "02_Manuscript", "Manuscript_EN.md")
LEDGER = os.path.join(ROOT, "04_ResearchData", "references_verified.md")

# manuscript number -> ledger key, as assigned when the list was numbered
MAP = {
    1: "Tola2022", 2: "Tola2024thesis", 3: "Tola2021RoboCIM", 4: "Sanneman2020",
    5: "Ulrich1995", 6: "Mehrabi2002", 7: "Chaumet2023", 8: "Felfernig2014",
    9: "Siltala2018interfaces", 10: "Siltala2019", 11: "Siltala2016", 12: "Jarvenpaa2017",
    13: "Jarvenpaa2018", 14: "Mital2019", 15: "Zheng2019", 16: "Zamalloa2018",
    17: "ISO9409-1:2004", 18: "URplus2026", 19: "OnRobotQC2024", 20: "WangStrong1996",
    21: "Redman1998", 22: "FreuderWallace1992", 23: "Schiex1995", 24: "Dubois1996",
    25: "CiucciDubois2013", 26: "MittalFalkenhainer1990", 27: "Brewka2011", 28: "ConfWS2024",
}
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")


def _dois(text):
    # the manuscript sets each reference as a sentence, so a DOI may be followed by a full stop
    return [d.rstrip(".") for d in DOI_RE.findall(text)]


def manuscript_entries():
    text = open(MD, encoding="utf-8").read()
    tail = text[text.index("## References"):]
    parts = re.split(r"\n\[(\d+)\]\s", "\n" + tail)
    out = {}
    for i in range(1, len(parts) - 1, 2):
        out[int(parts[i])] = parts[i + 1].strip()
    return out


def ledger_records():
    text = open(LEDGER, encoding="utf-8").read()
    blocks = re.split(r"\n###\s", "\n" + text)[1:]
    recs = {}
    for b in blocks:
        head = b.split("\n")[0]
        key = None
        for cand in MAP.values():
            if cand in head:
                key = cand
                break
        if not key:
            continue
        dois = DOI_RE.findall(b)
        urls = re.findall(r"https?://[^\s;,)]+", b)
        recs[key] = {"head": head.strip(), "dois": sorted(set(dois)), "urls": urls[:3]}
    return recs


def main():
    ents = manuscript_entries()
    recs = ledger_records()
    rows, problems = [], []
    for n in sorted(ents):
        body = ents[n]
        key = MAP.get(n, "?")
        mdoi = _dois(body)
        has_url = bool(re.search(r"https?://", body))
        ldoi = recs.get(key, {}).get("dois", [])
        if not mdoi and not has_url:
            problems.append("[%d] %s carries neither a DOI nor a URL" % (n, key))
        elif not mdoi and ldoi:
            problems.append("[%d] %s has no DOI in the manuscript but the ledger records %s"
                            % (n, key, ldoi[0]))
        if mdoi and ldoi and mdoi[0] not in ldoi:
            problems.append("[%d] %s DOI mismatch: manuscript %s vs ledger %s"
                            % (n, key, mdoi[0], ldoi[0]))
        if key == "?" or key not in recs:
            problems.append("[%d] key %s not found in the ledger" % (n, key))
        rows.append({"n": n, "key": key, "manuscript_doi": mdoi[:1], "url": has_url,
                     "ledger_doi": ldoi[:1]})
    nums = sorted(ents)
    if nums != list(range(1, max(nums) + 1)):
        problems.append("numbering is not continuous from 1 to %d" % max(nums))
    report = {"entries": len(nums), "max_number": max(nums),
              "numbering_continuous": nums == list(range(1, max(nums) + 1)),
              "problems": problems, "rows": rows, "pass": not problems}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
