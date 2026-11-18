# PRISMA-style Search Log — Robot End-Arm Interface Compatibility Reference Library

- Search date: **2026-11-09**
- Executed by: literature-verification subagent (web fetch of title pages / PDFs / publisher records / Crossref / arXiv / HAL / CEUR-WS / OpenAlex / Semantic Scholar Graph API)
- Scope: build the verifiable reference library for "How Compatible Is 'Compatible'? A Four-Level Decidability Ladder and a Taxonomy of Zeros for Robot End-Arm Interfaces". No manuscript, outline, figure or submission material is produced here.
- Verification rule applied (per task spec): `verified` = the title page / PDF / publisher or Crossref record was actually opened on 2026-11-09; search-abstract-only hits are `not_verified`. No DOI was invented; near-title substitutes were rejected.

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

Hit counts: **all NOT_RETRIEVABLE** — the subscription-bound platforms (Scopus, WoS, IEEE Xplore, ScienceDirect) expose no public record-level hit counter in this environment, and the open APIs (Crossref, Semantic Scholar) return index-wide fuzzy totals that are not semantically meaningful hit counts. Instead of fabricating counts, inclusion was anchored to (i) the 10 records mandated in spec §5 and (ii) verified title pages; see flow below.

## 3. Screening flow (numbers as actually executed)

| Stage | Count | Note |
|---|---|---|
| Records identified across sources (mandated 10 + surfaced candidates) | 35 | mix of spec-mandated records, Crossref/S2 hits, publisher and vendor pages |
| After deduplication across mirrors (arXiv/HAL duplicate of Tola thesis; CEUR PDF vs. CEUR record of RoboCIM; two Procedia CIRP issue-81 hits for the same Siltala/Mital session; HRIM arXiv vs. its HAL mirror) | 31 | 4 duplicates removed |
| Excluded at title/abstract screening | 2 | reason class E1 (off-topic DOI-probe errors: "Design of high-bandwidth high-precision flexure-based nanopositioning modules" returned by DOI 10.1016/j.jmsy.2010.01.001 probe; wrong-record Koren RMS probe) |
| Remaining for eligibility (title page / PDF / publisher record opened) | 29 | |
| Opened to title-page / PDF / Crossref-record level = `verified`, core set | 29 | the mandate re-check resolved the last open item: Sabin & Freuder 1996 had been mis-recorded as an IEEE Expert paper; the opened record "Configuration as Composite Constraint Satisfaction" (AAAI AI&M Research Planning Workshop 1996, pp. 153–161) is now entry 19 of references_verified.md |
| Added after structured screening via citation chasing and targeted verification (see Section 4) | +9 | entries 30–38 of references_verified.md |
| **Library size (structured search 29 + citation chasing 9)** | **38** | of which 28 are cited in the manuscript reference list; 10 are held in the library but not cited |

Exclusion reason classes used:
- **E1 off-topic / wrong record returned by a DOI probe** (2 entries)
- **E2 cross-mirror duplicate** (4 entries, removed in dedup)
- **E3 dead or bot-walled landing pages not promoted to the reference list** (documented, not counted): Robotiq 2F-85 product link dead; UR e-Series manual link dead; ATI Axia80 page returned empty body; GitHub HRIM repository robots.txt-blocked; HAL imt-mines-albi mirror bot-walled (circumvented via CEUR-WS Vol-3812 title page and OpenAlex record for the same proceedings).

Two-round screening:
- Round 1 (title + abstract): 31 records screened; 2 excluded (E1).
- Round 2 (full title page / PDF / publisher record): the 29 core records were opened; all 29 passed as verified after the Sabin & Freuder 1996 mandate was re-opened and the earlier wrong title (IEEE Expert) was corrected to the workshop paper "Configuration as Composite Constraint Satisfaction" — hence zero not_verified. The 9 records of the citation-chasing stage (Section 4) were opened in a separate targeted pass, not as part of the structured search flow.

## 4. Citation-chasing additions (post-search targeted verification)

The 29 records above are the whole output of the structured search (families A–D). Nine further records were added afterwards by citation chasing — reading the reference lists of already-opened records and following their bibliographic threads — and each was then opened first-hand. These are entries 30–38 of references_verified.md:

- `Jarvenpaa2019implementation` — chased from the Procedia CIRP 2019 matchmaking pair (`Siltala2019`, `Mital2019`): the same Tampere group's software-implementation follow-up; found on the Tampere ReCaM publication list and verbatim in the Taylor & Francis reference list of Järvenpää et al. 2023.
- `Jarvenpaa2019ontologyJIM` — chased from `Jarvenpaa2018`: the journal extension of the MaRCO capability ontology; found on the ReCaM list and Eeva Järvenpää's ORCID record.
- `Siltala2021interface` — chased from `Siltala2019` and `Siltala2018interfaces`: the successor "Resource Interface Matchmaking" paper; verbatim in the Taylor & Francis reference list and ORCID record.
- `TolaCorke2024urdf` — chased from `Tola2024thesis`: the URDF dataset-and-analysis study the thesis positions against; opened via the Aalborg University research portal manuscript PDF and the QUT ePrints profile.
- `TolaCorke2023urdfsurvey` — companion conference paper of `TolaCorke2024urdf`; record opened via OpenAlex (arXiv companion 2302.13442).
- `ISO11593_2022` — chased from `ISO9409_1_2004` and `OnRobotQC2024`: the automatic end-effector exchange vocabulary standard; opened on the ISO ICS 25.040.30 catalogue and the DIS 11593:2019 sample PDF.
- `OnRobotHEXmanual` — chased from the flange-as-suite-attribute case evidence (Table T7): the vendor manual as primary source.
- `UReseriesDatasheet` — chased from the host-port-budget p(h) rows in DataDossier: the official UR10e e-Series datasheet PDF.
- `CiucciDubois2012jelia` — chased from `CiucciDubois2013`: the JELIA 2012 conference version; verbatim in the Taylor & Francis page of the 2013 journal extension and cross-checked in PhilPeople.

Headline accounting: 29 (structured search) + 9 (citation chasing) = 38 records in the library. The manuscript cites 28 of the 38: the uncited 10 are `SabinFreuder1996` (entry 19, held after the mandate was satisfied) and the nine Group E records above. No text anywhere in the submission package claims the manuscript cites 38 records.

## 5. Reproducibility instructions for a third party

1. Re-run on any machine with outbound HTTPS: for each entry in references_verified.md, open the DOI URL (`https://doi.org/<doi>`) or the listed `url`. Open APIs used here require no subscription:
   - Crossref record: `https://api.crossref.org/works/<doi>`
   - arXiv: `https://arxiv.org/abs/<id>`
   - HAL: `https://hal.science/<halid>`
   - CEUR-WS: `https://ceur-ws.org/<Vol>/`
   - Semantic Scholar: `https://api.semanticscholar.org/graph/v1/paper/DOI:<doi>?fields=title,abstract`
2. Expected result: every `verified` entry resolves to a record whose title, authors, year and venue match references_verified.md verbatim. Sabin & Freuder 1996 resolves to the AAAI AI&M Research Planning Workshop record (pp. 153–161); the earlier mis-recorded "IEEE Expert" title was removed on 2026-11-09.
3. To obtain true database hit counts, run the family strings above against Scopus and/or Web of Science with an institutional subscription; record query translation, date range and interface used, because open APIs cannot reproduce those counts.
4. Nothing in this log depends on local closed corpora; the 528/553, HRIM 21/3/0/0 and UR+ 528 figures are main-agent corpus facts (FROZEN_NUMBERS.json), not literature hits.

## 6. Anti-claim register (literature that could have contradicted our thesis, and what we found)

- **HRIM (Zamalloa et al. 2018) itself claims** a plug-and-play horizontal-integration information model. Our audit of its published tree (FROZEN: 21 class models, 3 instance datasheets, 0 mechanical-mating fields, 0 connector-level electrical fields) shows the model is message/behavior-level: it does not supply interface-compatibility judgments. It is cited as the closest prior standard, not as a counterexample.
- **Siltala / Järvenpää / Mital capability-matchmaking line** assumes "the formalized interface information provided by the resource descriptions" exists as input. Our corpus finding (528/553 electrical ports = ELEC:UNKNOWN; 0/528 UR+ interface fields) shows that input premise is unmet in public catalogues. These works are the "what would change the answer" class (§9 of the manuscript), not counterexamples.
- **Tola et al. 2022** states verbatim that "no mature public robot system configurators exist"; this supports, rather than contradicts, our gap claim.
- **No entry found** in the searched record set claims that UR+, HRIM, or any surveyed ecosystem already declares both mechanical and connector-level electrical mating data on product entries. If such a paper surfaces at resubmission, it must be quoted with the concrete field schema before it can weigh against the FROZEN facts.
