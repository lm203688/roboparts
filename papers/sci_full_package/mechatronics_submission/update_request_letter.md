# 致 Mechatronics 编辑的信：请求更新已提交稿件

**用途**：Editorial Manager 里 Send Email 的正文。请求对象是期刊办公室（Manuscript Handling Manager），不是主编辑或审稿人。**动作是 Send Email 请求 update，不是点 Withdraw**。

**投递路径**：
1. 登录 https://www.editorialmanager.com/MECH
2. Author Main Menu → 找到稿件 `MECH-D-26-XXXXX`（Manuscript ID: `b3827f4c-4443-4dff-ba5f-65741ac70a78`）
3. 点 "Send Email" → 收件人默认 "Manuscript Handling Manager"
4. Subject 填下面 Subject 那行，正文全粘贴
5. 如果系统里 Send Email 只允许在特定状态下用，先查当前状态

---

## Subject

Request to update manuscript MECH-D-26-XXXXX with material corrections before review

## Body

Dear Editorial Office,

I am the submitting author of manuscript **MECH-D-26-XXXXX** ("Three-State Honesty in Robotic Hardware Compatibility: A Vendor-Neutral Determination Layer"), submitted on **15 October 2026**.

I am writing to request an **in-place update of the manuscript** rather than a withdrawal and resubmission. Within four days of submission, our internal validation pipeline (the same codebase that produces the paper's reported numbers) uncovered a **material defect in the evaluation protocol** described in Section 5 of the manuscript, together with a **substantive body of new evidence** that we are now able to include. I would like to provide the corrected manuscript to the reviewing team rather than have it enter review with a known defect.

### What changed (four items, all material)

1. **Independent ground-truth evaluation layer added (Section 5.11, new).** The submitted manuscript relied on 28 regression anchors generated from the judge engine itself. We now include a **20-case hand-crafted ground truth set** (Golden L4) whose expected values are derived independently from ISO 9409-1 flange dimensional tables and manufacturer datasheets, without reference to engine output. Section 5.11 explains the two-tier evidence structure, the dual-annotator Cohen's κ protocol, and the honest boundary of the current single-annotator version.

2. **A material false-green bug found by the new layer, and fixed.** The L4 set's first run uncovered a normalization bug in the mechanical-compatibility axis: structured `flange` objects were being `String()`-coerced to `"[object Object]"`, causing any two different ISO 9409-1 flanges to compare as identical and be reported as mechanically compatible. Nine cases of Ø250 flange being declared compatible with a Ø100 interface were correctly flagged. The fix and its verification are described in Section 5.11 and shipped in the same commit as the evaluation-set expansion. **We consider this the strongest reason for the update request**: the submitted manuscript describes an evaluation protocol that we now know was reporting false positives on this axis.

3. **Snapshot numbers refreshed against current corpus.** Vendor counts and concentration percentages in the paper (358 vendors, 37.33% top-10) reflect the state of the corpus at the time of writing. The corpus has since grown and those figures now read 348 vendors and 18.72% top-10. All five in-text instances and the concentration curve denominator have been updated so that the paper matches its own artifact on any re-run.

4. **New contribution paragraph added to Section 5.** A fourth contribution (C4) is now stated explicitly, describing the evaluation-discipline contribution that the L4 layer instantiates.

### What is unchanged

The scientific claim of the paper is unchanged: **composed = 0** on the full 46.5 M-pair decision space remains the central honest result, and the paper's central argument (three-valued reasoning is a discipline, not a metric) is unchanged. All figures are regenerated from source at commit time and are byte-identical except where the L4 fix required a recomputation.

### Why we are not submitting as a new manuscript

The corrected manuscript is a **strict refinement of the submitted one**: every page of the submitted manuscript has a corresponding page in the update, and the update adds 20 evaluation cases plus one new subsection while correcting two snapshot numbers. It is not a new submission, and it is not submitted simultaneously to another journal.

We would like to request that the manuscript be placed in a status that allows us to upload the corrected files while retaining the existing review queue, and that any editorial decision (send-to-review / R&R / other) be based on the corrected version. If the journal office prefers a formal withdrawal and resubmission workflow instead, please advise and we will follow that route.

Thank you for your time and consideration.

Yours sincerely,

Xing Li
Zhejiang Academy of Building Research & Design Co., Ltd.
Email: [通讯作者邮箱]

**Attachments (to upload after office confirmation):**
- Updated `main.pdf` (28 pages)
- Updated `title_page.pdf`
- Updated `graphical_abstract.pdf`
- Updated `highlights.pdf`
- Updated `cover.pdf`
- Change summary (this letter, exported to PDF)
