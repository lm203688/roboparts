# Contributing Data to RoboParts

> **Read the format spec first**: [`docs/part-annotation-spec.md`](./docs/part-annotation-spec.md)
> is the single authoritative format for "what a part entity should look like" (field table + minimal copyable JSON template + gate list).
> This file explains "what can be accepted and which channel to use"; the spec explains "what it looks like once accepted" — read both together and you can produce a gate-passing entity in one go.

The bottom line: **what this project lacks most is not code, but one piece of hole-pattern data with a source.**

As of 2026-09-15, among all 868 entities in the repo, only **81 (16.2%)** have any lead on a mechanical interface —
15 `declared` + 10 `partial`, with a denominator of 435 applicable entities (363 software/protocol entities do not apply).
In other words, for the question "can these two parts screw together", we currently cannot answer over 90% of the time.

So adding the PCD dimensions from a Robotiq manual is far more useful than refactoring the recommendation algorithm again.

## 为什么贡献？— 你图什么

**对贡献者的回报**：
- **署名**：每条贡献的 `source` 字段会记录你的 GitHub 用户名或提供的名称，永久留名于数据集
- **学术引用**：数据集的 `CITATION.cff` 支持自动引用，你的贡献可被论文引用
- **社区认可**：贡献排行榜（`/contributors`）按贡献数量排序，前 10 名获得「核心贡献者」徽章
- **实际价值**：你补充的孔位数据直接提升 868 个实体中超过 90% 的「可判定率」——这是重构算法 10 次都做不到的

**对供应商的回报**：
- **免费曝光**：你的产品出现在 868 个实体的兼容性矩阵中，被开源机器人构建者直接看到
- **兼容性背书**：经 RoboParts 判定的「compatible」结论可作为采购决策的第三方背书
- **不抽佣**：RoboParts 不销售、不代理任何零件，因此不会把选型结果导向自家产品——你的竞品同样在库里，判定保持中立
- **询价通道**：采购商可通过 BOM 导出功能直接联系你（如你选择开放联系方式）

**这不是慈善，是互利**：你提供数据，我们提供曝光与认可。RoboParts 的护城河不是代码，是数据——而数据来自你。

---

## I. Three Channels, Ordered by Barrier (Lowest to Highest)

| Your situation | Use this channel |
|---|---|
| You have a vendor manual but don't want to touch JSON | [Mechanical interface declaration Issue](https://github.com/lm203688/roboparts/issues/new?template=mechanical-interface.yml) — paste the link, we record it for you and credit you |
| You found some data is wrong | [Data correction Issue](https://github.com/lm203688/roboparts/issues/new?template=data-correction.yml) |
| You can write JSON and want to edit directly | Fork → edit `api/entities.json` → run gates locally → PR |

**You don't need to know JSON.** The first channel is for people who "have the material but don't want to learn the format".

---

## II. The Only Hard Rule: No Source, No Entry

This is not a courtesy. The registry's `coverage_policy` original text:

> Only register specifications with publicly traceable sources. Never write dimensions without a source; rather leave blank than fabricate.

Specifically, four cases that will be rejected:

1. **Dimensions filled from memory.** Even if you're an engineer with ten years in this field, please provide a link.
2. **"Translating" a vendor spec into an ISO code for them.** This is the easiest to commit and the most harmful.
   When the vendor manual writes "P.C.D. 56, 8×M4", please **copy it verbatim**, do not write `ISO 9409-1-56-8-M4`.
   We are currently stuck on this very pitfall at ACT-028 (Robotiq 2F-85): the 2019 manual §6.1.1 records the shorthand,
   while Robotiq's current knowledge base records it as an ISO code; the two vendor sources disagree with each other, and it has not been verified whether the ISO 9409-1
   original actually includes the 56-8-M4 size — so this entry remains **suspended, not accepted**, with the reason written in the entity's `gap` field.
   Publishing a vendor shorthand as an ISO code could both invent a code out of thin air (picked up by crawlers) and produce false negatives against other parties' writings.
3. **Forum posts / distributor compilations / second-hand retellings.** Will be downgraded to Tier C (`confidence` cap 0.30),
   and in most cases simply not accepted.
4. **Filling in missing items with "this is how it should be".** If the manual doesn't give thread engagement depth, write it into `gap` and openly admit it can't be judged,
   don't push a value derived from a standard ladder.

The criterion is not self-assigned by the contributor: `source_tier` is derived from the evidence form, the only source being
`scripts/govern_source_tier.py`. The three tiers:

| Tier | Meaning |
|---|---|
| A | First-hand source that can be clicked open for verification (official spec sheet / standard text / vendor document with link) |
| B | Weak attribution (vendor catalog stated values, official homepage, no original link) |
| C | No traceability (historical import, source pending, `confidence` cap 0.30) |

---

## III. Minimal Verifiable Format for Mechanical Interface Declarations

Fields hang under the entity's `mechanical_interface`. Below is a **real, in-use** entry
(ACT-028 Robotiq 2F-85, excerpt, verifiable verbatim in `api/entities.json`):

```json
"mechanical_interface": {
  "status": "declared",
  "mount_type": "flange",
  "standard": [
    "ISO 9409-1-50-4-M6",
    "ISO 9409-1-31.5-4-M5",
    "ISO 9409-1-40-4-M6"
  ],
  "flange": null,
  "declared_note": "Hole pattern varies with official coupling; not a single flange: AGC-CPL-062-002=ISO 9409-1-50-4-M6…… coupling is a required part (integrates electronics and electrical contacts), so the premise of 'mountable' is selecting the corresponding coupling model.",
  "source": "Robotiq official manual 《2F-85 & 2F-140 Instruction Manual》 §6.1.1 Couplings",
  "source_url": "https://assets.robotiq.com/website-assets/support_documents/document/2F-85_2F-140_TM-OMRON_InstructionManual_20190206.pdf",
  "confidence": 0.95,
  "registry_ref": "/api/mechanical_interfaces.json",
  "gap": "PCD56(6×M4)/PCD60(4×M5) has no ISO code, not included in the auto-comparison set; the interface between the gripper body and the coupling (Ø63 F8 locating shoulder) is not separately listed as a comparable identifier.……"
}
```

### Field Rules

**`status`** —— four valid values; out-of-range will be flagged red by the gate:

| Value | When to use |
|---|---|
| `declared` | Vendor explicitly gives a comparable hole-pattern identifier (pitch circle + hole count + thread all present) |
| `partial` | Vendor states the mounting method but key dimensions are missing, so hole-level interchangeability cannot be judged |
| `not_declared` | Mechanical interface applies, but the vendor has not published it |
| `n_a` | Not applicable (software, protocols, AI models, and other entities with no physical interface) |

**`mount_type`** —— valid values follow
[`/api/mechanical_interfaces.json#mount_type_enum`](https://roboparts.cc/api/mechanical_interfaces.json)
(currently 10), in two groups: `standard_derived` has a standard source,
`roboparts_extension` is an internal platform key name, **not a standard term**.
`null` means not collected / not applicable — do not write the string `"N/A"` (`status` already carries this meaning).

**`standard`** —— an array. Format `ISO 9409-1-{pitch circle}-{hole count}-M{thread}` (no `A` form,
uniformly written this way in the repo). If one part fits multiple couplings, list multiple, as in ACT-028 above.

**`declared_note`** —— **write the prerequisites here, don't skip them.**
A prerequisite like "official coupling must be selected to mount" directly determines whether the conclusion "mountable" holds.
Omitting it turns useful data into misleading data.

**`gap`** —— **required, and you may not write "none".**
The purpose of this field is to openly admit "what this data cannot judge".
The gap in ACT-028 above honestly states two things it cannot judge.
A declaration with no gap will be sent back asking what exactly you verified.

**`confidence`** —— determined by the evidence form, not self-assigned. Reference the actual tiers in the repo:
official manual listing specs item by item → 0.92~0.95 (ACT-028 / SENS-31);
vendor states only mounting method with no dimensions → 0.7 (partial entries like SRI C025XX);
Tier C no traceability → cap 0.30.

---

## IV. If You're Submitting a PR

```bash
# 1. Edit api/entities.json (single source of truth; don't edit derived files)
# 2. Regenerate derived files
python scripts/normalize_categories.py

# 3. Run the gate self-check locally (CI runs the same set; go green locally before submitting)
python scripts/ci_gate.py
```

`ci_gate.py` validates: entity schema contract, `mount_type` enum, external dataset distribution consistency,
agent skill list consistency, JSON parseability, `meta` consistency with entities, Functions top-level security, no credential leak.
After your PR is pushed, GitHub Actions automatically runs the same set; if it goes red it tells you exactly which rule was violated and how to fix it.

**Do not hand-edit these files** (they are computed live by scripts from the source of truth; hand-edits will be flagged red by the gate):
`api/data.json`, `api/<category>.json`, any file under `data.js`, `roboparts-dataset-github/`,
and any numbers in the pages.

---

## V. How We Handle Your Data

- **Accepted with attribution**, licensed CC BY 4.0 (data).
- We will **open every link you provide and verify it one by one**. Anything we can't verify we'll reply on the thread and ask; we won't silently drop it.
- If we judge your source conflicts with another vendor source (as with ACT-028),
  we will write the **disagreement itself** into `gap` and hang it publicly, rather than unilaterally picking one to trust.
- Data changes leave a trail; we don't silently change numbers.

## VI. Code Contributions

Also welcome, but please get `python scripts/ci_gate.py` passing first.

One easy trap: inside Cloudflare Functions, calling
`Math.random()` / `Date.now()` / `crypto.getRandomValues()` / `crypto.randomUUID()` **at module top level** is forbidden.
Top-level evaluation happens during isolate startup; a violation makes the worker fail to start,
combined with `_routes.json`'s `/*` it causes **site-wide 404s** (this exact incident happened once on 2026-08-05).
Just move those calls inside the request handler. The gate will block it and the error will point to the exact file and line.

## License

Code MIT, data CC BY 4.0. See root [`LICENSE`](./LICENSE).
