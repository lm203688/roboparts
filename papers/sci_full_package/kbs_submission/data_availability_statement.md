# Data Availability Statement

All data, code, evaluation sets, and continuous-integration artefacts
referenced in this paper are released under MIT (code) and CC BY 4.0
(data) licences at the project repository. The 48-case independent
evaluation set and its ISO 9409-1 source derivations are included
in-repo under `evaluation/independent_ground_truth/`. Every numeric
claim in the manuscript text is regenerated from source on every
continuous-integration run by a dedicated drift-detection gate
(G-S1), which flags any deviation between manuscript prose and
current artefacts. Frozen regression anchors (Golden Set L1-L3)
coexist with the independent ground-truth anchors (Golden Set L4);
L4 is derived from human annotation of ISO 9409-1 flange dimensions
without reference to engine output, providing external validity that
L1-L3 cannot supply.

**Repository**: `https://github.com/lm203688/roboparts`
**Golden evaluation set**: `api/eval/compatibility-golden.json` (48 cases, L1-L4)
**ISO 9409-1 derivation provenance**: `docs/iso9409-1-derivation.md`
**CI drift-detection gate**: `scripts/ci_gate.py::gate_paper_numbers_fresh`
