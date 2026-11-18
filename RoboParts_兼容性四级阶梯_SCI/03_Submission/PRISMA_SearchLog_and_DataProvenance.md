# Supplementary Material — PRISMA Search Log and Data Provenance

**Status:** Supplementary material for the manuscript "How Compatible Is 'Compatible'? A Four-Level Decidability Ladder and a Taxonomy of Zeros for Robot End-Arm Interfaces". This document does not replace the manuscript; it records the search trail, the screening flow, and the provenance of every number used in the paper, so that a third party can re-run the search and the recomputation.

Search and verification date: **2026-11-09**.

Library accounting: the structured search (Section 3) entered 29 records; 9 further records were added through citation chasing and targeted verification (Section 4); the library therefore holds 38 records, of which 28 are cited in the manuscript.

---

## 1. Databases, platforms and access status

| Platform | Used? | Hit-count retrieval status |
|---|---|---|
| arXiv (abs pages, arxiv.org/abs/...) | yes | record pages opened; no numeric hit counter needed (known IDs) |
| HAL (hal.science) | yes (Zheng 2019 landing page) | opened; HAL bot-wall (Anubis) blocked the imt-mines-albi mirror of hal-04770758 |
| Crossref REST API (api.crossref.org) | yes, heavily | per-DOI record pages opened; bibliographic search returns index-wide fuzzy totals (e.g. 6,739,693 for one query) which are **not usable as hit counts** — recorded as NOT_RETRIEVABLE |
| CEUR-WS (ceur-ws.org) | yes (Vol-3812, Vol-2956) | title pages opened |
| OpenAlex API | yes (ConfWS record W4404166990) | record opened |
| Semantic Scholar Graph API | yes (abstracts) | record pages opened |
| Publisher pages (Springer Link, Elsevier shop, Taylor & Francis, ACM DL, ISO catalogue, IEEE via Crossref, vendor sites) | yes | opened where reachable; ScienceDirect robots.txt-blocked; GitHub robots.txt-blocked; HAL mirror bot-wall |
| Scopus / Web of Science / IEEE Xplore / ScienceDirect search UI | no subscription | NOT_RETRIEVABLE — no institutional credentials in this environment; no record-level hit counts obtainable |

## 2. Search strings (Boolean logic and field limits, verbatim as executed)

Family A — robot hardware information models and standards
- A1: `all:"hardware robot information model" OR all:HRIM` → target record arXiv:1802.01459
- A2: `all:"robot system" AND all:configur* AND all:(interfac* OR compatibility)` → Tola 2022 (SII), Tola 2021 RoboCIM, Tola 2024 thesis
- A3: `all:"interface model" AND all:configuration AND all:mechatronic` → Zheng et al. RCIM 2019
- A4: `all:"capability matchmaking" AND all:(resource* OR production)` → Siltala 2019, Järvenpää 2018/2017, Mital 2019, Siltala 2016
- A5: `all:"mechanical interface" AND all:("manipulating industrial robots" OR ISO 9409)` → ISO 9409-1:2004 catalogue record

Family B — reconfigurable assembly and tool changing
- B1: `all:"reconfigurable manufacturing" AND all:(trend* OR perspective*)` → Mehrabi et al. 2002
- B2: `all:"product architecture" AND all:manufacturing` → Ulrich 1995
- B3: vendor product pages: UR+ ecosystem (universal-robots.com/plus), OnRobot Quick Changer

Family C — partial constraints, three-valued / placeholder reasoning
- C1: `all:"partial constraint satisfaction"` → Freuder & Wallace 1992
- C2: `all:"valued constraint satisfaction"` → Schiex, Fargier, Verfaillie 1995
- C3: `all:"three-valued" AND all:("incomplete information" OR unknown)` → Ciucci & Dubois 2013
- C4: `all:"dynamic constraint satisfaction" AND all:configuration` → Mittal & Falkenhainer AAAI-90
- C5: `all:"answer set programming"` → Brewka, Eiter, Truszczyński 2011
- C6: `all:(possibility theory OR fuzzy) AND all:"constraint satisfaction"` → Dubois, Fargier, Prade 1996
- C7: `all:configuration AND all:knowledge-based AND all:(survey OR handbook)` → Felfernig et al. 2014; ConfWS 2024 proceedings

Family D — catalogue audit and information completeness
- D1: `all:"data quality" AND all:(consumer* OR accuracy)` → Wang & Strong 1996; Redman 1998
- D2: `all:"industrial robotics" AND all:(challenges OR interview)` → Sanneman et al. 2020

Hit counts: **all NOT_RETRIEVABLE** — the subscription-bound platforms (Scopus, WoS, IEEE Xplore, ScienceDirect) expose no public record-level hit counter in this environment, and the open APIs (Crossref, Semantic Scholar) return index-wide fuzzy totals that are not semantically meaningful hit counts. Instead of fabricating counts, inclusion was anchored to (i) the 10 records mandated in the specification and (ii) verified title pages; see the flow below.

## 3. Screening flow (numbers as actually executed)

| Stage | Count | Note |
|---|---|---|
| Records identified across sources (mandated 10 + surfaced candidates) | 35 | mix of spec-mandated records, Crossref/S2 hits, publisher and vendor pages |
| After deduplication across mirrors (arXiv/HAL duplicate of Tola thesis; CEUR PDF vs. CEUR record of RoboCIM; two Procedia CIRP issue-81 hits for the same Siltala/Mital session; HRIM arXiv vs. its HAL mirror) | 31 | 4 duplicates removed |
| Excluded at title/abstract screening | 2 | reason class E1 (off-topic DOI-probe errors: "Design of high-bandwidth high-precision flexure-based nanopositioning modules" returned by DOI 10.1016/j.jmsy.2010.01.001 probe; wrong-record Koren RMS probe) |
| Remaining for eligibility (title page / PDF / publisher record opened) | 29 | |
| Opened to title-page / PDF / Crossref-record level = verified (core set) | 29 | the last open mandate item was resolved on this pass: the mis-recorded "IEEE Expert" title for Sabin & Freuder 1996 was corrected to the opened record "Configuration as Composite Constraint Satisfaction" (AAAI AI&M Research Planning Workshop 1996, pp. 153–161) |
| Added after structured screening via citation chasing and targeted verification (Section 4) | +9 | entries 30–38 of references_verified.md |
| **Library size: 29 core + 9 citation-chasing** | **38** | 28 of the 38 are cited in the manuscript; 10 are held in the library but not cited (Section 4) |

Exclusion reason classes:
- **E1 off-topic / wrong record returned by a DOI probe** (2 entries)
- **E2 cross-mirror duplicate** (4 entries, removed in dedup)
- **E3 dead or bot-walled landing pages not promoted to the reference list** (documented, not counted): Robotiq 2F-85 product link dead; UR e-Series manual link dead; ATI Axia80 page returned empty body; GitHub HRIM repository robots.txt-blocked; HAL imt-mines-albi mirror bot-walled (circumvented via CEUR-WS Vol-3812 title page and OpenAlex record for the same proceedings).

Two-round screening:
- Round 1 (title + abstract): 31 records screened; 2 excluded (E1).
- Round 2 (full title page / PDF / publisher record): the 29 core records opened; all 29 passed as verified after the Sabin & Freuder 1996 mandate re-check resolved the earlier wrong title (see table above). The 9 citation-chasing records were opened in a separate targeted pass documented in Section 4.

## 4. Library reference list (38 keys: 29 core from structured search + 9 citation-chasing)

Citation marks: `cited-as-[n]` = the key is reference [n] in the manuscript; keys without a mark are held in the library but not cited in the manuscript.

Core set (29 records, structured-search output; 28 of them are cited):

Group A — robot hardware information models and standards:
`Tola2022` (cited-as-[1]), `Zamalloa2018` (cited-as-[16]), `Siltala2019` (cited-as-[10]), `Zheng2019` (cited-as-[15]), `Chaumet2023` (cited-as-[7]), `Tola2024thesis` (cited-as-[2]), `Tola2021RoboCIM` (cited-as-[3]), `Sanneman2020` (cited-as-[4]), `Jarvenpaa2018` (cited-as-[13]), `Mital2019` (cited-as-[14]), `Siltala2016` (cited-as-[11]), `Jarvenpaa2017` (cited-as-[12]), `Siltala2018interfaces` (cited-as-[9]), `ISO9409_1_2004` (cited-as-[17]), `URplus2026` (cited-as-[18]).

Group B — reconfigurable assembly and tool changing:
`Ulrich1995` (cited-as-[5]), `Mehrabi2002` (cited-as-[6]), `OnRobotQC2024` (cited-as-[19]).

Group C — partial constraints, three-valued / placeholder reasoning:
`SabinFreuder1996` (not cited — held after the mandate was satisfied), `CiucciDubois2013` (cited-as-[25]), `MittalFalkenhainer1990` (cited-as-[26]), `FreuderWallace1992` (cited-as-[22]), `Schiex1995` (cited-as-[23]), `Dubois1996` (cited-as-[24]), `Brewka2011` (cited-as-[27]), `Felfernig2014` (cited-as-[8]), `ConfWS2024` (cited-as-[28]).

Group D — catalogue audit and information completeness:
`WangStrong1996` (cited-as-[20]), `Redman1998` (cited-as-[21]).

Citation-chasing additions (9 records, all Group E, none cited in the manuscript):

`Jarvenpaa2019implementation` (chased from `Siltala2019`/`Mital2019`; software-implementation follow-up), `Jarvenpaa2019ontologyJIM` (chased from `Jarvenpaa2018`; MaRCO ontology journal extension), `Siltala2021interface` (chased from `Siltala2019`/`Siltala2018interfaces`; successor interface-matchmaking paper), `TolaCorke2024urdf` (chased from `Tola2024thesis`; URDF dataset audit), `TolaCorke2023urdfsurvey` (companion conference paper of `TolaCorke2024urdf`), `ISO11593_2022` (chased from `ISO9409_1_2004`/`OnRobotQC2024`; end-effector exchange vocabulary), `OnRobotHEXmanual` (chased from the flange-as-suite-attribute case evidence, Table T7), `UReseriesDatasheet` (chased from the host-port-budget p(h) rows), `CiucciDubois2012jelia` (chased from `CiucciDubois2013`; JELIA 2012 conference version).

Verification tally: 38 of 38 verified (29 core + 9 citation-chasing). Manuscript citation tally: 28 cited; 10 held but uncited (`SabinFreuder1996` plus the nine Group E records). Full bibliographic records, DOIs, opened URLs and per-entry verification method: `04_ResearchData/references_verified.md`. Verbatim quotes and intended manuscript section per entry: `04_ResearchData/literature_notes.md`. Machine-readable bibliography: `04_ResearchData/refs.bib`.

## 5. Reproducibility of the search

1. For each entry in `04_ResearchData/references_verified.md`, open the DOI URL (`https://doi.org/<doi>`) or the listed `url`. Open APIs used here require no subscription:
   - Crossref record: `https://api.crossref.org/works/<doi>`
   - arXiv: `https://arxiv.org/abs/<id>`
   - HAL: `https://hal.science/<halid>`
   - CEUR-WS: `https://ceur-ws.org/<Vol>/`
   - Semantic Scholar: `https://api.semanticscholar.org/graph/v1/paper/DOI:<doi>?fields=title,abstract`
2. Expected result: every `verified` entry resolves to a record whose title, authors, year and venue match `references_verified.md` verbatim. `SabinFreuder1996` resolves to the AAAI AI&M Research Planning Workshop record ("Configuration as Composite Constraint Satisfaction", pp. 153–161); the earlier mis-recorded "IEEE Expert" title was removed on 2026-11-09.
3. To obtain true database hit counts, run the family strings above against Scopus and/or Web of Science with an institutional subscription; record query translation, date range and interface used, because open APIs cannot reproduce those counts.
4. Nothing in this log depends on local closed corpora; the 528/553, HRIM 21/3/0/0 and UR+ 528 figures are main-agent corpus facts (`00_Spec/FROZEN_NUMBERS.json`), not literature hits.

## 6. Data provenance of the manuscript numbers

Every number in the manuscript carries one of three tiers, defined in `04_ResearchData/DataDossier.md`:

- **[V]** verified first-hand — datasheet, manual or official page, quoted verbatim.
- **[O]** official or second-hand figure, not verbatim-checked.
- **[E]** computed in this study and reproducible from the shipped scripts.

The full 24-row support table (manuscript claim → value → section used → tier → source file → recompute status) is in `04_ResearchData/DataDossier.md`. Machine-readable consistency ledger: `04_ResearchData/results/frozen_checks.json` — 57 checks: 45 match, 3 mismatch, 9 not_recomputed; the three mismatches (vendor count 329 vs 328; same-flange bootstrap row 295 vs unfiltered 996 and its density consequence) are logged with cause, and the frozen values are retained.

Shipped recomputation artifacts:

- `04_ResearchData/results/ladder_recompute.json` — D0/D1 ladder and port-audit recompute.
- `04_ResearchData/results/upper_bound_recompute.json` — optimistic completion upper bound (1,268 pairs = 0.590% / 0.632%).
- `04_ResearchData/results/bootstrap_recomputed.json` — whole-cluster manufacturer bootstrap, B=1000, seed=20261109.
- `04_ResearchData/results/csv_lint.json` — table lint over `04_ResearchData/Tables/T1–T7`.
- `04_ResearchData/results/frozen_checks.json` — the 57-check frozen ledger.

Shortest third-party reproduction path (from the repository root, Python 3.13 with numpy, corpus present one level up):

```powershell
python 04_ResearchData/Scripts/rp_ladder_recompute.py     # writes results/ladder_recompute.json
python 04_ResearchData/Scripts/rp_upper_bound.py          # writes results/upper_bound_recompute.json
python 04_ResearchData/Scripts/rp_bootstrap.py          # writes results/bootstrap_recomputed.json (~1 s)
```

Expected outputs: the ladder script prints 13 lines with 12 `match` and 1 `MISMATCH` (vendors 329 vs 328); the upper-bound script prints 6 `match`; the bootstrap script prints five axis rows with point densities 0.4636% / 1.0291% / 1.5081% / 0.0796% / 36.2200%. Scope limits: D2=8 and D3=1 cannot be re-derived from the shipped files (engine verdict and manual locus, carried verbatim); the same-flange bootstrap row (295) cannot be reproduced without the original engine rule; all densities share the 214,840-pair denominator C(656,2).

## 7. Declarations and pending items

- Author legal affiliation full name pending confirmation (manuscript currently uses "Zhejiang Academy of Building Research & Design Co., Ltd."; to be corrected against the business licence — Chinese legal name placeholder: 浙江省建筑科学设计研究院有限公司，待按营业执照订正).
- Journal-level APC figures for the four candidate journals remain NOT_VERIFIED; the subscription route carries no charge, and this conclusion has been VERIFIED against Elsevier's official pricing page.
- Sabin & Freuder 1996 was verified on this pass ("Configuration as Composite Constraint Satisfaction", AAAI AI&M Research Planning Workshop 1996, pp. 153–161) after correcting an earlier mis-recorded title; it is held in the reference library but not cited in the manuscript.
- Reviewer suggestions not drafted.

---

Generated: 2026-11-09.
