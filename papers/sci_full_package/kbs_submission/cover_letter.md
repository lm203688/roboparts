# Cover Letter to Knowledge-Based Systems

**Manuscript title:** Three-State Honesty in Robotic Hardware
Compatibility: A Vendor-Neutral Determination Layer

**Suggested category:** Original Research Article

Dear Editor,

We are pleased to submit our manuscript for consideration as an
Original Research Article in *Knowledge-Based Systems*. The paper
introduces a novel knowledge-based decision-support framework for
robotic hardware compatibility, with a formal theory of abstention
that optimizes decision accuracy under uncertainty, a knowledge
acquisition prioritisation theorem (MVC), and a continuous-integration
harness ensuring reproducibility against evolving artefacts.

We believe the manuscript is a strong fit for KBS because it directly
addresses the journal's core objectives: it advances knowledge
representation through a three-valued compatibility logic, provides
an uncertainty-aware decision-support mechanism, and delivers a
practical system architecture for knowledge-based reasoning under
incomplete evidence. Our work contributes foundational theory (when
abstention is optimal), methodological innovation (MVC prioritisation),
and engineering practice (78-gate CI harness) to the KBS community.

## JAAMAS-style information sheet

### 1. What is the main claim of the paper? Why is this an important
contribution to knowledge-based decision-support research?

**Main claim.** Knowledge-based decision-support systems operating on
physical-world compatibility should adopt a three-valued semantics
("compatible" / "incompatible" / "abstain") to eliminate costly
binary errors. Under AND-convergence of $k \ge 2$ evidence axes,
three-state reasoning is provably optimal (Theorem 1), and knowledge
acquisition must prioritize homogeneous evidence sets (MVC) rather
than individual declarations, since the marginal value of any single
new declaration is zero (Theorem 2).

**Why it matters.** This work addresses a fundamental limitation in
knowledge-based decision-support: binary decisions incur irreversible
errors in high-stakes domains (medical devices, industrial systems,
supply chains). Our three-state theory provides the first formal
framework for determining when abstention is optimal, establishes
MVC as the correct prioritization strategy, and delivers a
reproducible CI architecture that prevents knowledge drift from
compromising decision quality. These contributions generalize beyond
robotics to all KBS domains requiring honest uncertainty-aware reasoning.

### 2. What is the evidence you provide to support your claim?
Be precise.

- **Formal.** Theorem 1 (three-state optimal under $k \ge 2$
  AND-convergence) and Theorem 2 (single-declaration marginal
  value = 0), stated and proved in the paper.
- **Empirical.** On 868 robotic entities (46.5M pairs), the system
  abstains in 100% of pairs that would be binary-decided with
  incomplete evidence — establishing an "honesty baseline" impossible
  for binary classifiers. The 46.5M-pair decision space reports
  composed = 0 as a factual snapshot, not a target metric.
- **External validity.** A 48-case independent ground-truth set
  derived from ISO 9409-1 flange tables via human annotation,
  completely independent of engine output. L4 evaluation anchors
  are strictly separated from L1-L3 regression anchors. The L4 set
  caught nine false-green judgments that L1-L3 missed, proving that
  independent validation is essential for detecting production defects
  that regression-based testing cannot expose.
- **Defect found.** The independent anchors detect a
  production false-green bug in the compatibility engine:
  two distinct ISO 9409-1 flange objects are stringified to the
  same `"[object Object]"` token under `idValues` normalization,
  causing Ø250 flange to be reported compatible with a Ø100
  interface. The fix and its verification are described in
  §5.11.
- **Reproducibility.** A 78-gate continuous-integration harness recomputes
  every reported metric from source code on every commit, failing the build
  on any drift. This creates machine-checked reproducibility between
  paper claims and evolving artefacts, eliminating the reproducibility crisis
  in knowledge-based systems evaluation.

### 3. What papers by other authors make the most closely related
contributions, and how is your paper related to them?

- **Open-source hardware and BOM semantics.** Projects such as
  roboxdb and ROS Component Description publish robot-part metadata,
  but as data dictionaries. RoboParts is a decision layer on top
  of any such dictionary: it defines the semantics of "compatible"
  and refuses to answer when evidence is missing.
- **Assembly graphs and interface geometry.** Works such as [ref]
  learn assembly-graph embeddings for robotic assembly; our
  contribution is complementary, focused on the knowledge layer
  that decides whether a pair is even a valid candidate for
  assembly.
- **Uncertainty-aware robot learning.** Probabilistic-programming
  and conformal-prediction lines [ref] address abstention in learned
  policies; our three-state semantics is a decision-theoretic
  abstention at the knowledge layer, not a policy layer, and it is
  defined without probabilities.
- **ISO 9409-1, ISO 3025, ISO 9653.** These standards define the
  mechanical interface axis but leave the signal axis undefined;
  RoboParts extends them with a signal-level type system.

### 4. Have you published parts of your paper before?

No. The manuscript has not been published, nor is any preprint
version publicly available at the time of submission. The
underlying implementation and data are open source at the
repository URL given in the Data Availability Statement, and are
released under MIT (code) and CC BY 4.0 (data). The manuscript is
not under consideration elsewhere.

### 5. Page length justification

The manuscript is approximately 28 double-spaced pages, exceeding
KBS's suggested 12-15 page limit for full-length articles. This
extended length is justified by: (1) the external-validity protocol
requiring a 48-case independent ground-truth set; (2) the 78-gate
continuous-integration architecture ensuring reproducibility; and
(3) the comprehensive evaluation across mechanical, electrical, and
signal axes. We request consideration for the full length as these
components are essential for establishing the three-state honesty
framework and cannot be meaningfully compressed without losing
methodological rigor.

## Declaration

- The manuscript has not been published previously and no
  preprint version has been posted.
- The manuscript is not under consideration for publication
  elsewhere.
- The manuscript has been approved and will be submitted by all
  authors.
- There are no conflicts of interest to declare.
- Use of generative AI tools in the writing of the manuscript is
  disclosed in the corresponding declaration section.
- The corresponding author holds a CRediT authorship contribution
  statement.

Thank you for considering our submission.

Sincerely,

**Xing Li** (corresponding author)
Zhejiang Academy of Building Research & Design Co., Ltd.
Email: 463102527@qq.com

**Enclosures**:
- Manuscript (LaTeX source + PDF)
- Highlights (5 bullets, ≤85 characters each)
- Data Availability Statement
- CRediT authorship contribution statement
- Declaration of competing interests
- Declaration of generative AI use
