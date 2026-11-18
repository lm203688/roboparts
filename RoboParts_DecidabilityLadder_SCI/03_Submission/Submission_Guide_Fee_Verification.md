# Submission Guide & Fee Verification (zero-APC route)

Date of verification: 2026-11-09. Verifier: automated web check. Status legend:
- **VERIFIED** = the page was opened and the relevant statement read.
- **NOT_VERIFIED** = not opened in this pass; do not quote a number; follow the 30-second manual re-check path before submission.

## 1. The zero-APC principle (VERIFIED)

Elsevier's official pricing policy (https://www.elsevier.com/about/policies-and-standards/pricing, opened 2026-11-09) states that journals operate two models: subscription articles, funded by reading subscriptions, and open-access articles funded by APCs. Authors may publish under the subscription model at no cost in hybrid journals; the subscription price is set excluding open-access articles. The official position, quoted: *"Subscription articles funded by payments for reading made by subscribing individuals or institutions; Open access articles funded by payments for publishing made by authors…"* [V].

**Action at submission system:** when the system asks "Choose your publishing option", select **Subscription / Publish without open access** (sometimes worded "Traditional publication" or "No, I will not open my article"). Do NOT select gold OA / open access, which triggers the APC.

## 2. Four candidate journals

| Journal | Publisher | Model | Fee page status | Route |
|---|---|---|---|---|
| Advanced Engineering Informatics (AEIN) | Elsevier | Hybrid | NOT_VERIFIED (per-journal APC page not opened this pass) | Subscription route, no APC |
| Journal of Intelligent Manufacturing (JIM) | Springer Nature | Hybrid | NOT_VERIFIED | Subscription route, no APC; Springer hybrid also allows traditional no-APC publication |
| Robotics and Computer-Integrated Manufacturing (RCIM) | Elsevier | Hybrid | NOT_VERIFIED | Subscription route, no APC |
| Mechatronics | Elsevier | Hybrid | NOT_VERIFIED | Subscription route, no APC |

**30-second manual re-check path per journal (do this before clicking "submit"):**
1. Open the journal's homepage → "Guide for authors" → "Open access options" / "Publishing costs".
2. Confirm the journal is listed as a **hybrid** journal (two options offered).
3. Confirm the traditional/subscription option carries **no fee to the author**.
4. Screenshot the sentence and save it into this folder as `fee_<journal>.png`; update the row above from NOT_VERIFIED to VERIFIED with the date.

If any per-journal page is blocked by robots.txt / WAF / paywall, leave the row as NOT_VERIFIED and rely on the publisher-level hybrid policy documented in §1; never quote an unverified APC number.

## 3. Journal selection and错峰 (one paper, one submission at a time)

This manuscript must not be submitted to any journal that currently holds another of the author's papers (CBM / JBE / acoustic-power building, etc.). Recommended order, lowest-fit-first for a measurement+proposition paper:

1. **Robotics and Computer-Integrated Manufacturing (RCIM)** — best topical fit (robotics + manufacturing integration); Elsevier hybrid, no-APC subscription route.
2. **Mechatronics** — second fit (mechanical/electrical interface axis).
3. **Advanced Engineering Informatics (AEIN)** — third fit (engineering informatics / configurator angle).
4. **Journal of Intelligent Manufacturing (JIM, Springer)** — reserve; Springer hybrid traditional route is also no-APC.

Wait for a final decision (or a reject) from the first journal before submitting to the next. Do not parallel-submit.

## 4. Submission package contents (upload order)

1. Manuscript_EN.docx (main, double-spaced, numbered pages) — or the journal's LaTeX template if required.
2. Title Page (separate file, as required by single-anonymised review).
3. Highlights (as a separate text file, ≤ 85 chars each).
4. Cover Letter (as a separate file or in the cover-letter box).
5. Figures: Fig1/Fig2/Fig3 as 300 dpi PNG, also embedded in the manuscript.
6. Research data: ladder CSV, bootstrap CSV, reproducibility script, upper-bound calculation.
7. Suggested reviewers: 3–5 experts in robot configuration / product data / HRIM-adjacent work (to be filled by the author; do not invent names).

## 5. Open items for the author (cannot be resolved by the assistant)

- Legal affiliation full name (business-license exact string) before upload.
- CN byline confirmation.
- Per-journal fee-page screenshot (§2 re-check path).
- Suggested reviewer names and emails.
- Final choice among the four journals.
