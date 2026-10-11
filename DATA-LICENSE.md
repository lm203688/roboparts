# Data License (DATA-LICENSE) — RoboParts

> RoboParts uses **dual-track licensing**: the **code** in this repo is covered by [`LICENSE`](./LICENSE) (MIT),
> the **data** is covered by this file (CC BY 4.0).
>
> 【Why split into two files】 Previously these two were written in the same `LICENSE` file; GitHub's license recognizer
> could not parse the custom mixed text, and the repo page's `license` field long showed **`NOASSERTION`** —
> a project that positions itself as an "open-source data layer" displayed no license at all on its own GitHub page,
> directly affecting trust and inclusion in the open-source community. Hence `LICENSE` holds only the **verbatim MIT full text** (recognizable),
> and the data line is moved to this file.

## Scope

All JSON datasets under `api/` (including `entities.json`, `mechanical_interfaces.json`,
and the per-category files), the `roboparts-dataset-github/` distribution directory, and the same-source data served via
<https://roboparts.cc/api/>.

## License

Creative Commons Attribution 4.0 International (CC BY 4.0)

- Full text: <https://creativecommons.org/licenses/by/4.0/legalcode>
- Summary: <https://creativecommons.org/licenses/by/4.0/>

You are free to use, modify, redistribute, and use commercially, provided you attribute the source. Suggested attribution format:

```
Data source: RoboParts (https://roboparts.cc), CC BY 4.0
```

This clause is consistent with the license declared in `roboparts-dataset-github/LICENSE` and in the API response's
`meta.access.license`.

## Notes on Data Use (not license terms, but an honest heads-up)

Before citing this repo's data, please be aware of the following facts, which are also publicly written in the API response's `meta`:

1. The parameters in this repo are **vendor public-stated values, not reproduced by our own testing**. Do not treat them as measured data.
2. The number of A-grade entries that can be directly compared across vendors is **0**.
3. For the question "can two parts be assembled together", this repo currently cannot answer in most cases —
   entities with a lead on the mechanical interface account for **16.2%** (declared 67 + partial 14 / 500 applicable,
   as of 2026-09-15, historical snapshot). **This percentage must not be hand-written in copy**;
   externally it must always use the live-computed value from `api/entities.json` → `meta.mechanical_interface_coverage.fill_pct`
   and <https://roboparts.cc/api/entities.json>;
   entities that cannot be found are labeled `not_declared`, rather than left blank or guessed.
4. Each data point carries `source_tier` (A/B/C) and `confidence`; please judge credibility accordingly.
   Tier C is historical import with no traceability, `confidence` cap 0.30.
5. In `api/mechanical_interfaces.json`, key names marked `authority` as `"roboparts_internal"`
   (such as the values under `mount_type_enum.roboparts_extension`) **are not terms of any standard**,
   but an internal modeling convention of this platform; please do not relay them downstream as standard codes.

This platform does not manufacture or act as an agent for any parts, and has no sales-interest relationship with the vendors it includes.
