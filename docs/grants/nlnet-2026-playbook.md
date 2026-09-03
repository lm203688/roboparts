# NLnet / NGI Zero — Application Playbook (RoboParts)

> **Purpose.** This document synthesises first-hand research on how NLnet / NGI Zero
> actually evaluates and funds projects, what high-amount winners look like, exactly where
> RoboParts currently qualifies or falls short, the full submission process with timeline and
> pitfalls, and a step-by-step preparation plan. It is the strategic companion to the
> paste-ready draft `nlnet-2026-proposal.md`.
> Convention: all public-facing RoboParts deliverables are in English.

---

## 0. TL;DR — the honest summary for the applicant

1. **Fit is defensible, not automatic.** NLnet funds "building blocks for the open internet /
   digital commons" — open software, open hardware, open standards, open data, privacy,
   interoperability, decentralisation. Robotics *component compatibility* is a stretch from
   "internet" but defensible if framed as **open data + open standards + interoperability +
   right-to-repair / anti-vendor-lock-in**. The strongest framing is: *"an open, vendor-neutral
   compatibility layer that removes a gatekeeper (the manual spec-sheet archaeology / adapter
   tax) in the European robot-hardware ecosystem."*
2. **First-time ask cap = €50,000.** We are requesting **€25,000** — safe. Asking **>€50K**
   requires one or more *prior successful* NGI0 projects by the same beneficiary, so don't
   escalate the ask on a first application.
3. **Competition is brutal.** The February 2026 Commons Fund round funded **60 projects out of
   599 proposals (~10%)**. The bar is high; the proposal must be concrete and exceptional.
4. **Scoring weights:** Technical excellence/feasibility **30%** · Relevance/Impact/Strategic
   potential **40%** · Cost-effectiveness/value-for-money **30%**. Threshold to pass stage 1 is a
   **weighted score ≥ 5.0 / 7.0**. Strategic relevance is the biggest single lever — invest in it.
5. **🔴 THE make-or-break for us: European dimension.** NLnet is funded by European tax money;
   non-EU applicants face a higher bar. Per NLnet's own Office Hour: *"Applicants must always have
   a European dimension… given equal proposals, inhabitants of the EU … are given priority. However
   if the project is of exceptional quality and the proposer holds unique technical expertise,
   proposals from outside those geographic areas can be eligible as well — under the condition that
   there is a clear European dimension."* Crucially: *"Contributing to the vision does not generally
   qualify… potential adoption would represent a very light European dimension, and unlikely to
   fulfill the criteria unless there are adopters collaborating with you on the project."* → For a
   China-based solo applicant, **subject-matter-only European dimension is very likely insufficient.**
   We need either (a) a European co-applicant receiving ≥60% of the funds, or (b) 1–2 EU stakeholders
   who *genuinely collaborate* (validate data, adopt the API, co-present) — not mere endorsements.
6. **Process is transparent and milestone-based.** No equity, no loan. Donations paid against
   delivered milestones after a two-stage review + independent committee sign-off + MoU.

---

## 1. What high-amount (€25K–€50K) winners look like — research synthesis

Drawn from publicly announced NGI Zero / NLnet grantees (Arkin open microscope, LibreCellular 5G,
OpenBMS, RISC-V cores, WireGuard, Jitsi, Peertube, Tor, CryptPad, SCION, GNU Name System, NeTEx
transport standard, Typed Nix, OpenTough, and others). Recurring patterns:

| # | Trait of funded projects | Implication for RoboParts |
|---|---|---|
| 1 | **Concrete "building-block" deliverables**, not vague research. Reviewers fund artefacts they can point at (a working 5G config set, a BMS, a processor core). | Show the engine code, the live API, the ISO 9409-1 PCD matrix, the adapter generator — all real and demoable. |
| 2 | **Open standards / interoperability / open data centrality.** Many winners explicitly advance an open standard or knock down an interoperability wall. | Our ISO 9409-1 matrix + adapter-required derivation is squarely "interoperability + open data." Lead with it. |
| 3 | **Reusable infrastructure with real or clearly-anticipated users.** | Frame the dataset/API as a drop-in service for EU SMEs, ROS-Industrial tooling, sim-to-real. |
| 4 | **Established OSS credibility / track record.** Winners often have history (WireGuard, Tor, CryptPad). | We are newer — mitigate by showing a *live* repo + live site + rigorous governance (negative_compat engine, source_tier honesty). |
| 5 | **Right-to-repair / anti-vendor-lock-in / digital autonomy alignment.** NGI vision explicitly wants to "remove gatekeepers, choke points" and enable interoperability + right to repair. | RoboParts lowers the "adapter tax" and breaks marketplace lock-in — align the narrative here, not on "AI/ML." |
| 6 | **Frugal, realistic, milestone-based budgets** at cost-recovery rates. | €25K over 6 months part-time, concrete milestones. Avoid padding. |
| 7 | **Strategic relevance (40% weight) is the biggest lever.** Winners map clearly onto NGI's "human-centric, sovereign, resilient internet" vision. | Tie to EU digital autonomy (open data, not US-cloud marketplace), EU SME empowerment, EU right-to-repair. |

**What they do NOT reward:** why-the-problem-matters essays, 30-page dossiers, unsubstantiated
claims, ignoring the "compare with existing efforts" question, ignoring upstream projects,
submitting at 11:55 CEST.

---

## 2. RoboParts compliance scorecard

| Requirement (hard knock-out unless noted) | Status | Evidence / Action |
|---|---|---|
| All outputs under recognised free/open licence | ✅ | Code MIT + data CC BY 4.0 already in repo. |
| Scientific results open access | ✅ (to do) | We will publish the methodology brief open access. |
| R&D is the primary objective | ✅ | Building the engine + expanding the dataset. |
| Fits a fund theme (open data / standards / interop) | ✅ (defensible) | Frame as open-hardware interoperability + right-to-repair. |
| First-time ask ≤ €50,000 | ✅ | €25,000 requested. |
| **European dimension** | 🔴 **GAP** | No EU team, no EU adoption yet. **Must resolve (see §4 / proposal §DECISION).** |
| "Compare with existing/historical efforts" answered | ✅ | Already in proposal (orobot.io, ROS-Industrial, URDF, CAD libs, grasp datasets). |
| Upstream engaged / stated | ⚠️ | Standalone project; we should notify/indexed vendors + seek EU-org collaboration (see outreach email). |
| Track record / credibility | ⚠️ | Newer; mitigate with live artefacts + governance rigour. |
| Generative-AI disclosure | ✅ | Already disclosed in proposal. |
| Main application ≤ ~2 pages equivalent | ⚠️ | Current draft is longer; compress before paste. |
| Budget realism / frugality | ✅ (review) | Cost-recovery rates; no equipment. |
| Lead applicant can be individual or company | ✅ | Choice is the applicant's (see §DECISION in proposal). |

**Bottom line:** every hard requirement is met **except European dimension**, which is the single
item that can knock a strong technical proposal out. Fix that and the rest is a writing/packaging job.

---

## 3. The application process — step by step (timeline + details + pitfalls)

> Deadline note: multiple sources point to the autumn 2026 call opening **3 September 2026** with a
> hard deadline of **3 November 2026, 12:00 CEST**. ⚠️ **Verify on `nlnet.nl/propose` when it opens** —
> NLnet's own NGI0 overview says the Commons Fund's "final call has closed," so the open autumn fund
> may be a different NGI Zero sub-fund (e.g. a Commons extension or Fediversity). Confirm *which fund*
> is open and its *exact* deadline on the portal. Submit **one day early**, not at 11:55.

**Step 1 — Pre-submission (now → ~2 Nov).**
- Draft answers offline (the portal accepts attachments up to 50 MB total: HTML/PDF/ODF/text).
- **Attend a NLnet Office Hour** (last Wednesday of each month, 16:00 CET, NLnet Matrix room) to
  sanity-check fit and your European-dimension approach. Cheapest de-risking available.
- Engage upstream / EU stakeholders *before* submitting (see outreach email template). State this
  engagement in the proposal — reviewers explicitly ask "how does upstream feel about your application."

**Step 2 — Submit (portal, before deadline).**
- One **lead applicant** coordinates communication; co-applicants (e.g. an EU collaborator) are named
  in the form and receive their share of the donation directly. NLnet prefers paying the people who
  did the work.
- Main text self-contained, ≤ ~2 pages. One clear budget attachment. Disclose GenAI use (field + prompt log).
- Submit a day early; you may update before the deadline (last complete version is reviewed).

**Step 3 — Acknowledgement (few days post-deadline).** NLnet contacts all applicants.

**Step 4 — Stage 1 review (~weeks 1–2).**
- **Knock-out eligibility check**: alignment with NGI vision, R&D-primary objective, open licence,
  European dimension. Fail → notified, may reapply next call.
- **Scoring** on the three weighted criteria; need **weighted ≥ 5.0/7.0** to advance.

**Step 5 — Stage 2 (interactive, ~3 weeks).**
- Reviewers ask clarifying questions and may request revisions: typical ones — *"how do you differ
  from U/V/W?"*, *"back up claim Y"*, *"how will outcome be sustainable?"*, *"how does upstream feel?"*,
  *"your rate for task B seems high — explain?"*, *"clarify European dimension."* Budget may shift.
- Respond within the allotted time or the project is **pushed to the next call**.

**Step 6 — Independent review committee (week ~5+).**
- 2+ independent experts validate eligibility, frugality, no concerns. May push back if issues.

**Step 7 — MoU negotiation (weeks ~5–8).**
- Final amount, milestones, terms negotiated and recorded in a Memorandum of Understanding. You may
  **decline** if the offered amount is too low (no obligation pre-signature).

**Step 8 — Sign MoU → possible advance payment** (within ~1 week of signing).

**Step 9 — Milestone payments.**
- After each milestone, submit a **Request for Payment**; NLnet verifies (~2 weeks) then pays. Final
  payment after all results are publicly released under the open licence.

**Step 10 — Non-financial support (grantees only).** Security/accessibility audits, mentoring,
licensing advice, packaging help via NGI Zero Review.

**Pitfalls to avoid (from NLnet's own guidance + Office Hour):**
- Writing *why* instead of *what + how*. Reviewers already believe the internet needs fixing.
- Leaving the comparison question blank — weak proposals collapse here.
- Ignoring upstream / not stating engagement.
- Padding attachments; one budget attachment beats a dossier.
- Treating AI disclosure as optional.
- Submitting at the 11:55 deadline (browser sessions fail; hard cutoff).
- **Assuming subject-matter European dimension is enough for a non-EU applicant** — it isn't, without
  collaborating EU adopters/co-applicants.

---

## 4. Targeted preparation plan — step by step

**Phase A — Resolve the European-dimension blocker (owner: applicant; AI assists with materials).**
- **A1. Decide the route:**
  - *Route A (recommended, highest odds):* recruit a **European co-applicant** (EU-university robotics
    researcher, or EU-based open-source robotics org / SME). They receive **≥60% of the €25K (≥€15K)**
    for their share (EU-standards validation, community engagement, co-authorship). Satisfies "≥60% of
    funds to EU participants" + "European contributors in the work." This is the known winning pattern
    for non-EU leads.
  - *Route B (fallback, higher risk):* keep 100% but secure **1–2 EU stakeholders who genuinely
    collaborate** (validate dataset, adopt API, co-present) and write letters of *collaboration*, not
    mere endorsement. Office Hour warns this alone is "unlikely to fulfill" — only pursue if Route A
    is truly impossible.
- **A2. Send the EU outreach email** (template: `nlnet-eu-outreach-email.md`) to euRobotics,
  ROS-Industrial, and 2–3 European robot SMEs (e.g. Franka, a KUKA/UR integrator). Goal: a
  collaboration letter + a data-validation contact.
- **A3. Attend the next NLnet Office Hour** (24 Sep or 28 Oct 2026, 16:00 CET) to validate the
  European-dimension approach with NLnet staff before spending days writing.

**Phase B — Harden the proposal (owner: AI drafts, applicant reviews).**
- **B1. Compress** the main text to ≤ ~2 pages; keep the comparison + technical-challenge sections
  (they are strong).
- **B2. Fill the European-dimension section** with the chosen route (co-applicant named, or
  collaboration letters attached).
- **B3. Add an upstream-engagement statement** (vendors notified; EU orgs collaborating).
- **B4. Re-confirm budget frugality** and milestone mapping (each milestone = a payable deliverable).

**Phase C — Submit (owner: applicant).**
- **C1.** Create/login `nlnet.nl/propose` account; enter lead + co-applicant; paste compressed text;
  attach budget + (if Route B) collaboration letters.
- **C2.** Submit ~1 day before the verified deadline.

**Phase D — Stage-2 readiness (owner: both).**
- **D1.** Pre-write answers to the likely questions (comparison depth, EU-dimension proof,
  sustainability, rate justification) so responses are fast and precise.
- **D2.** On MoU: confirm milestone split matches the co-applicant's share if Route A.

**Phase E — Delivery (owner: applicant, post-award).**
- **E1.** Hit milestones → Request for Payment → public release of open outputs.
- **E2.** Use NGI Zero Review support services (security/accessibility audit) to raise quality.

---

## 5. Open decisions for the applicant (blockers)

1. **European dimension route** — Route A (EU co-applicant, ~60% of funds) vs Route B (collaboration
   letters only). **This decides whether the proposal is even eligible.** Recommend Route A.
2. **Lead applicant entity** — individual (simpler donation, no company tax friction) vs the registered
   company. NLnet funds both; choice is the applicant's.
3. **EU outreach targets** — who to email first (suggested list in the outreach template).

---

## 6. Sources (first-hand, 2026-09-03)

- NLnet Guide for Applicants (scoring weights, two-stage process, ≥5/7 threshold).
- NLnet Open Application process (MoU, milestone payments, donations).
- NLnet Office Hour transcripts (European dimension rules, non-EU bar, co-applicant 60% rule, AI disclosure).
- NGI Zero Commons Fund call spec (€5K–€50K first-time cap, eligibility, fund themes).
- NLnet news: 60 projects / 599 proposals (Feb 2026) — competitiveness.
- Funded-project announcements (Arkin, LibreCellular, OpenBMS, RISC-V, WireGuard, Jitsi, Peertube, Tor, CryptPad, SCION, NeTEx, Typed Nix) — winner traits.
- FindMyMoney / Subsdy call analyses — process pitfalls, common mistakes.
