#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_numbers.py — numeric-consistency gate for the manuscript.

Three independent checks, all mechanical:

  1) BLACKLIST: strings that must never appear (retired claims and hype words).
  2) REQUIRED: the dozen numbers the argument cannot survive without.
  3) PERCENTAGE WHITELIST: every "x.y% " token in the document must be one of the
     values frozen in FROZEN_NUMBERS.json (plus an explicit, documented extra
     allowance). Anything else is either a typo or an unapproved number.
  4) TABLE ROW COUNTS: Table 1..6 must carry the row counts the text claims.

Usage:
    python check_numbers.py Manuscript_EN.md [FROZEN_NUMBERS.json]
Prints a JSON report and exits 1 on any hard failure.
"""
import json
import os
import re
import sys

BLACKLIST = [
    r"6\.57", r"0\.9384", r"13\.2657", r"0\.94\s?%", r"2,?016\s*(pairs|对)",
    r"K\s?=\s?2", r"unlock", r"breakthrough", r"revolutionary", r"first proof",
    r"game-changing", r"seamless", r"paradigm shift",
    r"\u9662\u58eb", r"\u5916\u7c4d", r"\u4e4c\u514b\u5170", "Acade" + "mician", "Ukra" + "inian",
]

# numbers the paper cannot be argued without
REQUIRED = [
    "139,139", "64.764", "0.00512", "0.00372", "0.00047",
    "528", "553", "95.48", "139,128", "99.992",
    "0.1373", "1.0291", "0.0796", "36.220",
    "297/360", "82.5", "1,268", "0.590",
    "12,650", "139,000",
]

# percentages allowed on top of the frozen set, each with a reason
EXTRA_PCT_REASONS = {
    "0.4636": "disclosed independent recomputation of the same-flange row (spec 9.3)",
    "35.0": "Z1 share 126/360, rounding of the frozen pair count",
    "47.5": "Z5/Z2 share 171/360",
    "17.5": "Z3/Z4 share 63/360",
    "5": "the CI upper bound statement 'never exceeds 5%'",
    "1": "the 1% band referenced in Table 6 verdict",
    "95": "confidence level of the reported interval",
    "6.6": "shrink of the pair universe when quarantining 22 placeholders (634/656, derived from frozen counts)",
    "6": "relative deviation between the frozen CI bands and the independent bootstrap re-run",
    "0.001": "lower limit of the logarithmic x-axis in Figure 2",
    "100": "upper limit of the logarithmic x-axis in Figure 2",
    "0.5": "inset span over the electrical row in Figure 2",
}

PCT_RE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s?%")
TABLE_CAPTION_RE = re.compile(r"^\s*(?:\*\*)?(?:#+\s*)?(?:Table|TABLE|\u8868)\s*(\d)")
EXPECTED_ROWS = {"1": (10, 20), "2": (3, 5), "3": (10, 12), "4": (4, 6), "5": (4, 6), "6": (5, 10)}


def frozen_percentages(path):
    with open(path, "r", encoding="utf-8") as fh:
        blob = fh.read()
    found = set()
    for m in re.finditer(r'[0-9]+(?:[.,][0-9]+)?%', blob):
        found.add(m.group(0).replace("%", "").strip())
    return found


def count_tables(lines):
    """Return {table_no: data_rows} for markdown tables preceded by a caption."""
    counts = {}
    i = 0
    pending = None
    while i < len(lines):
        m = TABLE_CAPTION_RE.match(lines[i])
        if m:
            pending = m.group(1)
        if lines[i].strip().startswith("|") and i + 1 < len(lines) \
                and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            rows = 0
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows += 1
                j += 1
            if pending is not None:
                counts[pending] = counts.get(pending, 0) + rows
                pending = None
            i = j
            continue
        i += 1
    return counts


def main(argv):
    md = argv[0]
    frozen = argv[1] if len(argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(md)), "..", "00_Spec", "FROZEN_NUMBERS.json")
    with open(md, "r", encoding="utf-8") as fh:
        text = fh.read()
    lines = text.split("\n")

    allowed = frozen_percentages(frozen)
    allowed |= set(EXTRA_PCT_REASONS)

    problems = []

    black = {}
    for pat in BLACKLIST:
        # the retired structural theorem is written with an upper-case K; the lower-case
        # k = 2 in the co-mount argument is a legitimate variable and must not be flagged
        flags = 0 if pat == r"K\s?=\s?2" else re.I
        hits = len(re.findall(pat, text, flags=flags))
        if hits:
            black[pat] = hits
            problems.append("blacklisted pattern %r hit %d time(s)" % (pat, hits))

    missing = [n for n in REQUIRED if n not in text]
    if missing:
        problems.append("required numbers missing: %s" % ", ".join(missing))

    pct_tokens = {}
    for m in PCT_RE.finditer(text):
        tok = m.group(1).replace(",", "")
        pct_tokens[tok] = pct_tokens.get(tok, 0) + 1
    rogue = {k: v for k, v in pct_tokens.items() if k not in allowed}
    if rogue:
        problems.append("percentages outside the frozen whitelist: %s" % rogue)

    tables = count_tables(lines)
    for tno, (lo, hi) in EXPECTED_ROWS.items():
        n = tables.get(tno)
        if n is None:
            problems.append("Table %s not found as a markdown table" % tno)
        elif not (lo <= n <= hi):
            problems.append("Table %s has %d data rows, expected %d-%d" % (tno, n, lo, hi))

    # author-year residue (only relevant once citations are converted to numbers)
    ay = len(re.findall(r"\([A-Z][A-Za-z]+(?: et al\.)?,\s?(?:19|20)\d\d\)", text))

    report = {
        "file": md,
        "bytes": len(text.encode("utf-8")),
        "words": len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", text)),
        "blacklist_hits": black,
        "required_missing": missing,
        "percentages_seen": len(pct_tokens),
        "percentages_rogue": rogue,
        "table_rows": tables,
        "author_year_citations_still_present": ay,
        "problems": problems,
        "pass": not problems,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
