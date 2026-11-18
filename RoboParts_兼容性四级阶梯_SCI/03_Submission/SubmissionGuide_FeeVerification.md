# Submission Guide — Zero-Fee Verification across Four Candidate Journals

Prepared 2026-11-09 · author Xing Li · package `RoboParts_兼容性四级阶梯_SCI`
Manuscript: *How Compatible Is "Compatible"? A Four-Level Decidability Ladder and a Taxonomy of Zeros for Robot End-Arm Interfaces*

> Verification rule applied throughout (per spec §11 and §13): a journal entry is `verified` only where the journal's own landing / APC page was opened and the line was read. Where `sciencedirect.com` or the journal page returned a robots.txt disallow, a PHP error, or a WAF intercept, the entry is marked `NOT_VERIFIED` at journal-specific level. The zero-fee *conclusion* for the three Elsevier titles rests on the platform-level Elsevier statement (Evidence A below), which **was** read verbatim on 2026-11-09.

---

## 0. Platform-level anchor (VERIFIED, applies to all three Elsevier titles)

**URL opened 2026-11-09:** https://www.elsevier.com/researcher/author/open-access/choice

Verbatim line (section "Waivers"):

> "Our waiving policy does not apply to hybrid journals. **Authors publishing in hybrid journals can publish under the subscription model at no cost** and make use of the Elsevier sharing policy."

Reading: for any Elsevier hybrid title, the default submission route (subscription, non-OA) carries no article publishing charge on the author side. The APC is triggered **only** if the author elects Gold Open Access at the post-acceptance Rights & Access step. The submission form's OA checkbox must therefore be left unselected.

This anchor is what makes the three Elsevier entries below `verified` at the *route* level even where the journal-specific APC figure could not be scraped.

---

## 1. RCIM — Robotics and Computer-Integrated Manufacturing

- **Publisher / ISSN:** Elsevier. Print 0736-5845.
- **Hybrid?** Yes (Elsevier hybrid). Not a fully-OA title.
- **Official APC list price (Gold-OA, optional):** **NOT_VERIFIED at journal-specific level.**
  - Attempted URL https://www.elsevier.com/journals/robotics-and-computer-integrated-manufacturing/0736-5845 returned a stream of PHP warnings (undefined constants, charset errors) with no usable journal metadata in the rendered body on 2026-11-09.
  - Attempted URL https://www.sciencedirect.com/journal/robotics-and-computer-integrated-manufacturing/about/ returned `Access failed: This URL is disallowed for automated access by robots.txt.`
- **Subscription route cost:** **0 EUR / 0 USD** by the platform-level anchor (Evidence A). Select subscription; leave OA checkbox cleared.
- **Evidence URL (route-level, VERIFIED):** https://www.elsevier.com/researcher/author/open-access/choice
- **Verbatim citation:** "Authors publishing in hybrid journals can publish under the subscription model at no cost and make use of the Elsevier sharing policy."
- **Verification status:** route = `verified`; journal-specific APC figure = `NOT_VERIFIED`.
- **30-second manual completion path (if the editor or you want the exact Gold-OA number):**
  1. Open https://www.sciencedirect.com/journal/robotics-and-computer-integrated-manufacturing in a normal browser.
  2. Click "Publish" (top nav) → "Open access options".
  3. Read the line "Article publishing charge (APC): … USD" under "Gold open access". That number is the *optional* charge; it is **not** triggered by a subscription submission.
- **Risk flags:**
  - Watch for the invitation to a *special issue* that declares mandatory Gold OA. RCIM main line is hybrid; a special-issue guest-edited call may be framed as OA-only. If such a call lands in your inbox, open the call-for-papers PDF and search for "open access" / "APC" before accepting the invitation.
  - No evidence on 2026-11-09 that RCIM has transitioned to fully-OA.

---

## 2. Journal of Intelligent Manufacturing (JIM)

- **Publisher / ISSN:** **Springer** (not Elsevier — this corrects spec §11's "四刊均为 Elsevier hybrid" assumption). Print 0956-5515; electronic 1572-8145.
- **Hybrid?** Yes. Both the journal home page and the submission-guidelines page carry the line "Publishing model: **Hybrid**".
- **Official APC list price (Open Choice, optional):** **NOT_VERIFIED at the dollar level.** The submission-guidelines page states only: "Article processing charges (APCs) vary by journal – view the full list" (link to the Springer Nature APC list).
- **Subscription route cost:** **0 EUR / 0 USD** by Springer's standard hybrid model. The submission guidelines describe *Open Choice* as the only paid publishing route; the default (subscription) route grants the Publisher an exclusive licence to publish the article and involves no APC. This is consistent with, but not a verbatim "at no cost" line from, the page we opened.
- **Evidence URL (VERIFIED):**
  - https://link.springer.com/journal/10845 (home page, "Publishing model: Hybrid")
  - https://www.springer.com/journal/10845/submission-guidelines (section "Open Choice")
- **Verbatim citations (both read 2026-11-09):**
  - Home page: "Publishing model: Hybrid".
  - Guidelines, "Open Choice": "Open Choice allows you to publish open access in more than 1850 Springer Nature journals… Article processing charges (APCs) vary by journal – view the full list."
- **Verification status:** hybrid status = `verified`; free-subscription route = `verified by construction` (Open Choice is the only APC-bearing route described); explicit "no cost" sentence = `NOT_VERIFIED` (Springer does not print that sentence on the journal page the way Elsevier does).
- **30-second manual completion path (if you want the exact Open Choice number):**
  1. Open https://www.springer.com/journal/10845/submission-guidelines.
  2. Click "Open access publishing page" at the bottom of the "Open Choice" section.
  3. Read the APC for Journal of Intelligent Manufacturing. It is the *optional* Open Choice charge; do not tick Open Choice at submission.
- **Risk flags:**
  - JIM's scope is "application of artificial intelligence in manufacturing" (per the home page). The present manuscript is an interface-decidability / corpus measurement paper, not an AI-method paper. Scope fit is weaker than RCIM — see recommendation in §6.
  - Springer's special issues are typically also hybrid; no mandatory-OA risk visible on the home page, but check the call PDF if invited.

---

## 3. Mechatronics

- **Publisher / ISSN:** Elsevier. Print 0957-4158.
- **Hybrid?** Yes (Elsevier hybrid).
- **Official APC list price (Gold-OA, optional):** **NOT_VERIFIED at journal-specific level.**
  - https://www.elsevier.com/journals/mechatronics/0957-4158 returned `Access failed: This URL is disallowed for automated access by robots.txt.`
- **Subscription route cost:** **0 EUR / 0 USD** by the platform-level anchor (Evidence A).
- **Evidence URL (route-level, VERIFIED):** https://www.elsevier.com/researcher/author/open-access/choice
- **Verbatim citation:** "Authors publishing in hybrid journals can publish under the subscription model at no cost and make use of the Elsevier sharing policy."
- **Verification status:** route = `verified`; journal-specific APC figure = `NOT_VERIFIED`.
- **30-second manual completion path:**
  1. Open https://www.sciencedirect.com/journal/mechatronics in a normal browser.
  2. "Publish" → "Open access options".
  3. Read the APC figure under Gold open access; leave OA unselected at submission.
- **Risk flags:**
  - Mechatronics' readership is control-systems / actuation / sensor-fusion oriented. A pure corpus-decidability paper sits at the edge of scope; expect a possible desk-reject on scope even though the fee route is clean.
  - No evidence on 2026-11-09 that the title has flipped to fully-OA.

---

## 4. Advanced Engineering Informatics (AEI)

- **Publisher / ISSN:** Elsevier. Print 1474-0346.
- **Hybrid?** Yes (Elsevier hybrid).
- **Official APC list price (Gold-OA, optional):** **NOT_VERIFIED at journal-specific level.**
  - https://www.elsevier.com/journals/advanced-engineering-informatics/1474-0346 returned `Access failed: This URL is disallowed for automated access by robots.txt.`
- **Subscription route cost:** **0 EUR / 0 USD** by the platform-level anchor (Evidence A).
- **Evidence URL (route-level, VERIFIED):** https://www.elsevier.com/researcher/author/open-access/choice
- **Verbatim citation:** "Authors publishing in hybrid journals can publish under the subscription model at no cost and make use of the Elsevier sharing policy."
- **Verification status:** route = `verified`; journal-specific APC figure = `NOT_VERIFIED`.
- **30-second manual completion path:**
  1. Open https://www.sciencedirect.com/journal/advanced-engineering-informatics in a normal browser.
  2. "Publish" → "Open access options".
  3. Read the APC figure; leave OA unselected.
- **Risk flags:**
  - AEI's scope leans toward AI / informatics for engineering design and construction. The manuscript's robotics-interface angle is a weaker fit than RCIM; expect a scope-check.
  - **Disclosure for the record:** a distinct manuscript of mine (world-model building virtual testing) has been tracked for AEI in a previous package. That prior manuscript has no data, figures or text overlap with the present paper; the present submission does not collide with it in any way that would require withdrawal, but it is noted here so the record is complete.

---

## 5. Per-journal status summary

| # | Journal | Publisher | ISSN | Hybrid? | Subscription route = 0 fee? | Journal-specific APC figure | Route evidence |
|---|---|---|---|---|---|---|---|
| 1 | Robotics and Computer-Integrated Manufacturing | Elsevier | 0736-5845 | yes | **yes (0 fee)** | NOT_VERIFIED | platform anchor, verified 2026-11-09 |
| 2 | Journal of Intelligent Manufacturing | **Springer** (not Elsevier) | 0956-5515 | yes | **yes (0 fee, default route)** | NOT_VERIFIED (Open Choice figure) | journal home + guidelines, verified 2026-11-09 |
| 3 | Mechatronics | Elsevier | 0957-4158 | yes | **yes (0 fee)** | NOT_VERIFIED | platform anchor, verified 2026-11-09 |
| 4 | Advanced Engineering Informatics | Elsevier | 1474-0346 | yes | **yes (0 fee)** | NOT_VERIFIED | platform anchor, verified 2026-11-09 |

No mandatory-OA special-issue risk was verified on any of the four on 2026-11-09; no title has flipped to fully-OA on the pages we could open.

---

## 6. Recommended submission order

**RCIM → JIM → Mechatronics → AEI.**

Reason:
- **RCIM** is the strongest *topic* fit — its scope covers computer-integrated manufacturing, robotic assembly, and the kind of end-effector / workcell integration question this paper measures. It is also the cleanest zero-fee route: Elsevier hybrid, subscription anchor verified verbatim.
- **JIM** has the cleanest *hybrid* page on record (Springer's "Publishing model: Hybrid" line is on the home page and on the submission-guidelines page), but its AI-method scope is a weaker match for a corpus-decidability measurement paper; keep as a real fallback, not a first choice.
- **Mechatronics** has a clean fee route but a weaker scope match (control / actuation / sensing rather than manufacturing integration).
- **AEI** last: scope fit is the weakest of the four for this manuscript, and a prior distinct manuscript has already been tracked for that journal.

The single operational rule across all four: **at the post-acceptance Rights & Access step, select subscription / non-OA. Do not tick Gold Open Access / Open Choice.** That is the only step that can turn this zero-fee submission into a multi-thousand-EUR APC.

---

## 7. Manual execution checklist (not automated — do not submit on the author's behalf)

1. Open the RCIM Editorial Manager submission portal (the URL appears on https://www.sciencedirect.com/journal/robotics-and-computer-integrated-manufacturing under "Submit your article").
2. Article type: Research paper.
3. Paste title, abstract, keywords (6–8), Highlights (5 bullets, all ≤85 chars, verified by script), Cover Letter, Title Page, blinded manuscript, three figures at 300 dpi, tables.
4. At the OA / rights-and-access step, leave the open-access checkbox **unselected**.
5. Link ORCID 0009-0004-2152-7669 at the author step.
6. Declarations: funding none; competing interests none; data availability as on the Title Page.
7. Record the manuscript number and the confirmation date in this folder.
8. If desk-rejected at RCIM, revise the Cover Letter's scope paragraph for JIM (Springer Editorial Manager), and only then move to Mechatronics, then AEI. Do not submit to two journals in parallel.
