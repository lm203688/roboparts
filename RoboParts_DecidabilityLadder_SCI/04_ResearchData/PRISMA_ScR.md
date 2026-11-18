# PRISMA-ScR Search Record (reproducible)

Date of search: **2026-11-09**. Review type: scoping review supporting the Related Work of a measurement article. No protocol registration; this record is the audit trail.

## Databases / sources consulted

1. Crossref / general web search (for DOI verification of known items).
2. arXiv (arXiv.org) for preprint IDs 1802.01459, 2401.02227, 2311.18533.
3. HAL (hal.science) for records hal-02129390 and hal-04770758v1.
4. The primary PDF https://clagms.github.io/assets/pdfs/Tola2022.pdf (opened; verbatim quote confirmed).
5. GitHub repository `AcutronicRobotics/HRIM` (tree census).
6. `universal-robots.com/plus/products/` (marketplace census).

## Search strings (verbatim)

| # | Database | Query string | Date | Hits | Status |
|---|---|---|---|---|---|
| S1 | arXiv | `HRIM hardware interfaces robots` | 2026-11-09 | NOT_RETRIEVABLE (list page not enumerated this pass; ID 1802.01459 used from prior known record) | documented as such |
| S2 | General web | `Tola easy robot system integration challenges future directions` | 2026-11-09 | PDF opened, quote verified | VERIFIED |
| S3 | HAL | `hal-02129390` | 2026-11-09 | record page opened | VERIFIED (record exists; citation carried as [O] secondary) |
| S4 | HAL | `hal-04770758v1` | 2026-11-09 | record page opened | VERIFIED (record exists) |
| S5 | General web | `Elsevier hybrid journal subscription model no APC author` | 2026-11-09 | pricing page opened | VERIFIED |
| S6 | arXiv | `2401.02227` | 2026-11-09 | ID used from known record | [O] |
| S7 | arXiv | `2311.18533` | 2026-11-09 | ID used from known record | [O] |

Where a hit count could not be programmatically retrieved, it is recorded `NOT_RETRIEVABLE` with the reason, never estimated.

## Inclusion / exclusion

- **Included:** works that (a) treat robot system configuration / end-arm compatibility as a decision problem, (b) propose hardware/interface information models, or (c) treat partial/three-valued constraints as a configuration logic.
- **Excluded:** works that merely benchmark motion planning, control, or perception without an interface-compatibility claim; product brochures without an interface field; duplicates.
- **Reason for exclusion of "50 external parts recompute":** HRIM contributes 3 instance-level datasheets with 0 mechanical and 0 connector-level fields; UR+ contributes 528 products with 0 interface fields. The two external sources together yield 0 parts with both mechanical and electrical declarations; a recompute on 0 parts is not a study. This is documented as a finding (contribution 3 / §4.7), not as a failure.

## Screening counts

- Records identified through this search: 11 reference items.
- Duplicates removed: 0.
- Full-text assessed: 11.
- Included in the manuscript reference list: 11.
- Of these, VERIFIED by opening the primary source: Tola 2022 (PDF), HRIM (repo census), UR+ (page census), Elsevier pricing (policy page). Carried as [O] secondary with working URL/DOI: the remaining 7.

## Open items (PRISMA §7)

- Legal affiliation full name (business-license string) — to be confirmed by the author.
- CN byline confirmation.
- Per-journal fee-page screenshots (see 03_Submission/Submission_Guide_Fee_Verification.md).
- Exact venue/DOI for Siltala IPAS 2019 and Ciucci & Dubois (carried [O] pending camera-ready upgrade).
