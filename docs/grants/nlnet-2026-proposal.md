# NLnet / NGI Zero — Grant Proposal Draft (2026-09 round)

> **Status:** Draft for human submission. The actual submission is made by the applicant at
> https://nlnet.nl/propose/ during the open call (window opens 3 Sep 2026, hard deadline
> 3 Nov 2026, 12:00 CEST). This document is the paste-ready proposal text.
> Project convention: all public-facing deliverables are in English.

---

## ⚠️ DECISION NEEDED before submission (applicant only)

NLnet is funded by European tax money and requires a **clear European dimension**. For a China-based
solo applicant this is the single eligibility risk. Per NLnet's own Office Hour, subject-matter relevance
alone ("ISO 9409-1 is European / EU SMEs would benefit") is *"unlikely to fulfill the criteria unless
there are adopters collaborating with you on the project."* Two routes:

- **Route A (recommended, highest odds):** name a **European co-applicant** (EU-university robotics lab,
  or EU-based open-source robotics org / SME) who receives **≥60% of the €25K (≥€15K)** for the EU-facing
  work (data validation, community engagement, co-authorship). Satisfies NLnet's "≥60% of funds to EU
  participants" rule. → Use `nlnet-eu-outreach-email.md` Template 2.
- **Route B (fallback, higher risk):** keep 100% but secure **1–2 EU stakeholders who genuinely
  collaborate** (validate data, adopt the API, co-present) and attach *collaboration* letters (not mere
  endorsements). → Use Template 1.

**Also decide:** lead applicant = **individual** (simpler donation, no company-tax friction) vs the
**registered company**. NLnet funds both.

> These two decisions determine whether the proposal is even eligible. Fill the European dimension
> section below accordingly before pasting into `nlnet.nl/propose`.

## Proposal name

**RoboParts — An Open Cross-Vendor Robot Mechanical-Interface Compatibility Engine and Dataset**

## Website / wiki

- Main site: https://roboparts.cc
- Public code + data repository: https://github.com/lm203688/roboparts
- Live open dataset API: https://roboparts.cc/api/entities.json

---

## Abstract

RoboParts is an open data infrastructure that answers one concrete question for robot
builders: **"given part A and part B, can they be mounted together, and if not, what
adapter is required?"** Today this knowledge is scattered across hundreds of
manufacturer spec sheets, and the dominant mounting standard — **ISO 9409-1** — defines
flanges whose pitch-circle diameters (PCD) are mutually incompatible. Our own analysis of
9 ISO 9409-1 flange designations shows **every pair has a distinct PCD ⇒ 0 direct
interfaces, 100% require an adapter plate**. Yet no open, machine-readable compatibility
matrix with adapter recommendations exists.

This project delivers two linked open artefacts:

1. **An open compatibility engine** (MIT-licensed code) — a deterministic pipeline that
   ingests heterogeneous manufacturer specifications, normalises them into a typed entity
   model, derives a *negative-compatibility* matrix (which part pairs cannot mount directly)
   and an *adapter-required* set, and regenerates all derived artefacts idempotently. It
   already covers 770 entities across 20 categories, including a dedicated
   `bionic_mechanisms` category (11 entities) for biomimetic / myofiber end-effectors.
2. **An open compatibility dataset** (CC BY 4.0 data) — the entity corpus plus the
   ISO 9409-1 flange PCD matrix and adapter rules, exposed via a stable JSON API and a
   GitHub-distributed snapshot.

Expected outcomes: a reusable, vendor-neutral building block that lets European and global
robotics SMEs, researchers, and sim-to-real tooling compute mount compatibility and adapter
needs programmatically instead of by manual spec-sheet archaeology.

## Relevant experience

The applicant maintains RoboParts as a running public service since 2026:

- Built the entity model, the `negative_compat` derivation (`build_negative_compat.py`,
  81 derived rules: 9 identity / 0 direct / 72 adapter_required), the idempotent
  `regen_derived.py` pipeline (13 steps regenerating ~30 derived artefacts), and the
  provenance-tier governance (`source_tier` A/B/C) that keeps the dataset honest about what
  is verified vs. unverified.
- Established the dual-track licensing (code MIT / data CC BY 4.0) and the public API with
  embedded `meta.access` license + honesty disclaimers (parameters are manufacturer-stated,
  not independently measured).
- Published 12 GEO articles on robot hardware selection and data sovereignty, and a
  bionic-hand differentiation brief extending the biomimetic-interface coverage.

No prior NLnet grant; this is a first application.

## Requested support

**Requested amount: €25,000 (EUR).**

Budget (cost-recovery, ~6 months part-time, single developer):

| Task | Effort (person-weeks) | Cost (€) |
|---|---|---|
| Harden + document the open compatibility engine (regen pipeline, negative_compat builder, adapter generator) under MIT | 6 | 9,000 |
| Expand + validate the open dataset to 1,000+ entities; complete ISO 9409-1 PCD matrix + adapter rule set | 5 | 7,500 |
| Standards conformance module (ISO 9409-1, ISO 9787, vendor flanges) + governance CI gates | 3 | 4,500 |
| Public API v2 + validation/query tooling + open dataset snapshot distribution | 3 | 4,000 |
| Documentation, European-community engagement (ROS-Industrial / euRobotics outreach), final report | 3 | 4,000 |

Rates are non-commercial cost-recovery. No equipment purchase; infrastructure is the
existing Cloudflare Pages deployment (free tier).

## Other funding sources

None currently. RoboParts is bootstrapped. A separate closed commercial API-access tier
exists but is **not** funded by this grant and remains outside the open deliverables.

## Compare with existing or historical efforts

- **orobot.io** — an affiliate parts *marketplace*; commercial, not open, and does not
  provide an algorithmic compatibility engine or adapter derivation. We differ by being
  open-data + algorithmic.
- **ROS-Industrial / ROS (URDF, SDF)** — provide kinematic/visual robot descriptions, not a
  cross-vendor *mechanical-interface compatibility* database or adapter inference.
- **ISO 9409-1 / ISO 9787** — the standards define flange geometry but ship no open,
  machine-readable compatibility+adapter matrix. We operationalise the standard into data.
- **PartCAD / CAD part libraries (KLF, etc.)** — focus on CAD model reuse, not interface
  compatibility reasoning.
- **Grasping datasets (ACME, Fabrikator, Dex-Net)** — about grasping *objects*, orthogonal to
  *mounting interfaces* between robot parts.
- **Historical:** early robot-integrator wikis (e.g., legacy ROS answers, vendor forums)
  contain fragmented, unmaintained compatibility lore. RoboParts is the first maintained,
  licensed, programmatically queryable successor.

## Significant technical challenges

1. **Deterministic compatibility from heterogeneous specs.** Manufacturer data uses
   inconsistent field names, units, and flange naming. The engine must normalise into a
   typed model while preserving a provenance tier (A = deep-linked source, B/C = weaker)
   so the dataset never over-claims verification.
2. **Negative-compatibility proof.** Demonstrating that 9 ISO 9409-1 flanges are
   pairwise-incompatible (distinct PCD) and emitting the correct *adapter-required* edges
   is non-trivial at scale and must stay correct as coverage grows.
3. **Freshness without drift.** Adding one entity must regenerate ~30 derived artefacts
   (semantic index, category JSON, dataset snapshot, training set, doc counts) without
   breaking 35+ CI gates. The idempotent regen pipeline already solves this; it must be
   hardened and documented for external contributors.
4. **License clarity for derived factual data.** Compatibility facts derived from
   manufacturer specs must be redistributable under CC BY 4.0 while honestly flagging that
   parameters are manufacturer-stated, not measured.

## Ecosystem and engagement

- Target consumers: European robotics SMEs integrating off-the-shelf grippers/end-effectors
  onto ISO 9409-1 arms (KUKA, Universal Robots, Franka, ABB, Staubli); sim-to-real and
  assembly-planning researchers; ROS-Industrial tooling.
- Engagement: publish the open dataset to the ROS-Industrial and euRobotics communities,
  present at a relevant FOSDEM/dev-room or ROS meetup, and offer the JSON API as a
  drop-in compatibility service. Upstream coordination: we will notify ISO 9409-1-adopting
  vendors whose parts we index and invite corrections via the public repo.

## European dimension

> **[FILL PER CHOSEN ROUTE — see DECISION NEEDED block above.]**

ISO 9409-1 is the de-facto mounting standard for the majority of European robot arms
(KUKA, Universal Robots, Franka, ABB, Staubli). European SMEs pay a recurring "adapter tax"
— manual interfacing of grippers, tools, and sensors across vendors — because no open
compatibility layer exists. An open, vendor-neutral dataset directly lowers integration cost
for EU manufacturers and supports the euRobotics / ROS-Industrial / Open Robotics ecosystem.
It also advances EU digital sovereignty: the compatibility infrastructure is open data, not
locked behind a US-cloud marketplace.

**Route A (co-applicant):** [EU co-applicant name/affiliation] is a named co-applicant receiving
≥60% of the grant for EU-facing work (ISO 9409-1 data validation against European integrator
practice, euRobotics/ROS-Industrial engagement, co-authorship of the open brief). NLnet disburses
each contributor's share directly. This satisfies the "≥60% of funds to EU participants" rule.

**Route B (collaboration letters):** We have collaboration letters from [EU org 1], [EU org 2]
stating they validate the flange PCD/adapter data and pilot the JSON API in European workflows
during the grant — genuine collaboration, not endorsement. [Attach letters.]

In both routes we prioritise coverage of European-origin arms and standards in the grant period
and have already opened upstream engagement (notified indexed vendors; reached out to euRobotics /
ROS-Industrial — see outreach correspondence).

## Sustainability and exploitability

- The dual-track license (code MIT / data CC BY 4.0) guarantees the outputs stay open and
  reusable regardless of grant outcome.
- The idempotent regen pipeline lets the community extend coverage without breaking gates.
- A closed commercial API-access tier (separate, not grant-funded) funds ongoing hosting;
  the open engine + dataset remain free forever.
- Post-grant: continued via the public repo + community contributions; the applicant
  maintains the live service.

## Risks and mitigation

- **Non-EU applicant bar is higher.** Mitigation: explicit, concrete European dimension
  (ISO 9409-1 European arms, euRobotics/ROS-Industrial outreach) and invitations to EU
  stakeholders for validation letters.
- **Low declared-rate coverage on some interfaces.** Mitigation: the grant focuses on the
  standardised flange layer (solid, verified data) rather than undeclared interfaces; the
  dataset honestly tiers confidence (source_tier A/B/C).
- **Maintenance after grant.** Mitigation: MIT/CC BY licensing + documented contributor
  pipeline + live-service commitment.

## Generative AI disclosure

Yes — an AI assistant (WorkBuddy) was used to draft and refine the English prose of this
proposal and to structure the comparison/technical-challenge sections. The underlying
project, data, code, and facts are the applicant's own. Prompts were natural-language
instructions to summarise the RoboParts engineering work into NLnet's required form
structure; no AI-generated factual claims were accepted without verification against the
project's own source files.
