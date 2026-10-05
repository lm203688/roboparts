#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_research_progress — 核心目标完成度判据的阴阳自证（挂 ci_gate）。

为什么这个百分比需要闸门
------------------------
「完成了百分之多少」是本项目最容易变成**自欺**的一句话：
分项可以挑、权重可以调、口径可以混，于是报出 60% 也不难看。

所以本层守三件事：
  ① **分项口径自检**：每个分项必须带 `caliber`（分子分母怎么算的）。
     没有口径的百分比不可复现，不配叫完成度。
  ② **权重可争议性**：`weights` 与 `weight_rationale` 必须在场，
     且加权值必须等于「裸值 × 权重」的现算结果——
     防的是「改了裸值但忘了改权重」这种静默分叉。
  ③ **反向对照（关键）**：造一个「composed > 0」的假想态，
     完成度**必须**随之上升；若不上升，说明分项与核心目标脱钩，
     百分比再漂亮也是空的。

③ 是最重要的一条：它检验「这个百分比是否真的对核心目标敏感」。
一个对核心目标不敏感的完成度指标，测多少次都是废的。
"""
from __future__ import annotations

import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_research_progress as brp  # noqa: E402

FAILED: list = []
_MUTFAIL: list = []


def fail(msg: str) -> None:
    FAILED.append(msg)
    print(f"  [FAIL] {msg}")


def _mutfail(msg: str) -> None:
    _MUTFAIL.append(msg)


def ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


def _errors(rp, sink=None):
    """纯函数判据。ci_gate 与本自证共用（同一口径两份实现=漂移来源）。"""
    errs = []
    meta = rp.get("meta") or {}
    w = rp.get("weights") or {}
    raw = rp.get("raw_dimension_scores") or {}
    total = rp.get("weighted_total_pct")

    # ① 每个分项必须带 caliber
    for dim, items in (rp.get("dimensions") or {}).items():
        for it in items:
            if not (it.get("caliber") or "").strip():
                errs.append("%s/%s 缺 caliber（无口径的百分比不可复现）"
                            % (dim, it.get("item")))
            if not isinstance(it.get("pct"), (int, float)):
                errs.append("%s/%s 的 pct 非数值：%r" % (dim, it.get("item"), it.get("pct")))

    # ② 权重可争议性 + 加权值现算一致
    if not w:
        errs.append("weights 为空——加权口径不可争议")
    # weight_rationale 在**顶层**（与 weights 平级），不在 meta 里。
    # 2026-10-04 实测踩坑：判据读 meta.weight_rationale 而产物写在顶层 ⇒ 假红。
    # **判据与产物的字段位置也必须对齐**，口径对齐不止是数值对齐。
    if not (rp.get("weight_rationale") or "").strip():
        errs.append("weight_rationale 缺失（顶层字段）——权重必须可被质疑")
    for dim in (raw or {}):
        if dim not in w:
            errs.append("维度 %s 有裸值但无权重（加权口径有漏项）" % dim)
    if w and raw and isinstance(total, (int, float)):
        recomputed = round(sum(raw[k] * w[k] for k in w if k in raw), 1)
        if abs(recomputed - total) > 0.15:
            errs.append("加权值 %s ≠ 现算 %s（改了裸值忘了改权重，或反之）"
                        % (total, recomputed))
    if w and abs(sum(w.values()) - 1.0) > 0.01:
        errs.append("权重之和 %s ≠ 1.0" % round(sum(w.values()), 3))

    # ③ 四维必须都在场（缺一维 = 少报）
    for d in ("body", "neuron", "policy", "chain"):
        if d not in (rp.get("dimensions") or {}):
            errs.append("缺维度 %s（核心目标是「脑×体×智 + 链路溯源」，四维缺一不可）" % d)

    # ④ 加权值必须在 0..100
    if isinstance(total, (int, float)) and not (0.0 <= total <= 100.0):
        errs.append("加权完成度 %s 越界（0..100）" % total)

    # ⑤ 门控必须已现算：raw_dimension_scores 必须等于「门控逻辑现算」的结果。
    # 缺这条 ⇒ 可以把门控换成朴素值虚高，而闸门不报。
    # 门控的语义：核心判据 done==0 的维度，raw 必须为 0。
    sc = rp.get("scoring") or {}
    naive = sc.get("naive_dimension_scores") or {}
    gexp = sc.get("gate_explanation") or {}
    body_items = rp.get("dimensions", {}).get("body") or []

    def _gated(dim):
        """该维度是否处于「门控生效」状态。

        ★ 实测踩到第五次「变异打空」，且这次是**判据自身的缺陷**：
          初版用 `"门控生效" in why` 判别，而 co_mount 落地后 body 的说明
          写的是「门控**未生效**」——**它含有「门控生效」这个子串**
          ⇒ body 被误判为「已门控」⇒ 校验方向反了。
          **子串包含会跨语义边界命中。** 判别必须用无歧义标记。
        """
        return str(gexp.get(dim, "")).lstrip().startswith("门控生效")

    # ★★ 关键改进（第六次变异打空逼出来的）：**门控必须现算，不许信声明**。
    #   原判据只做「声明 vs 数值」的一致性检查，于是：
    #   变异体只要保持 gate_explanation 不变、只改 raw，
    #   两边就自洽地一起骗过闸门 —— **这是典型的自欺型闸门**
    #   （与「一致性守卫 + 自称状态 = 自欺」的教训同型，只是发生在门控上）。
    #   正确做法：从 dimensions 现算「核心判据是否全为 0」，
    #   再要求 raw 与现算结果一致。声明只用于**措辞审查**，不作判据。
    p2p_it = next((i for i in body_items
                   if "composed" in (i.get("item") or "")), None)
    cm_it = next((i for i in body_items
                  if "共装关系可判定" in (i.get("item") or "")), None)
    if p2p_it is not None and cm_it is not None:
        answered = (p2p_it.get("done", 0) > 0) or (cm_it.get("done", 0) > 0)
        recomputed_body = float(naive.get("body", 0)) if answered else 0.0
        if "body" in raw and abs(float(raw["body"]) - recomputed_body) > 0.15:
            errs.append(
                "body 门控值 %s ≠ 现算 %s（核心判据已回答=%s："
                "composed=%s / co_mount=%s）—— "
                "**门控必须现算，不许只信 gate_explanation 的声明**"
                "（只查声明与数值是否自洽 = 自欺型闸门）"
                % (raw["body"], round(recomputed_body, 1), answered,
                   p2p_it.get("done", 0), cm_it.get("done", 0)))
    if naive and raw:
        for dim, val in (raw or {}).items():
            if not _gated(dim):
                # 该维度未门控 ⇒ 门控值必须**等于**朴素值
                if abs(float(val) - float(naive.get(dim, val))) > 0.15:
                    errs.append("维度 %s 未门控但门控值 %s ≠ 朴素值 %s"
                                " —— 绕过门控会虚高或虚低"
                                % (dim, val, naive.get(dim)))
        # 反向：声明门控生效的维度，其值必须为 0
        for dim in gexp:
            if _gated(dim) and (raw.get(dim) or 0) != 0:
                errs.append("维度 %s 声明门控生效但 raw=%s ≠ 0"
                            % (dim, raw.get(dim)))

    # ⑥ honest_limits 必须声明「加权不等于客观完成度」
    hl = " ".join(meta.get("honest_limits") or [])
    if "权重" not in hl and "权重" not in (rp.get("weight_rationale") or ""):
        errs.append("honest_limits 未声明权重可争议——会把口径说成客观测量")
    if "口径" not in hl:
        errs.append("honest_limits 未声明「加权是口径不是客观测量」")
    if sc and ("两个口径" not in hl and "朴素" not in hl):
        errs.append("产物有门控/朴素两套口径，但 honest_limits 未同时报出"
                    "——藏一个口径等于让读者以为只有一个数字")

    if sink is not None:
        for e in errs:
            sink(e)
    return errs


def check_baseline(rp) -> None:
    print("\n[1/3] 基线：口径自检 + 权重可争议性")
    errs = _errors(rp)
    if errs:
        for e in errs:
            fail(e)
        return
    ok(f"加权完成度 {rp['weighted_total_pct']}%"
       f"（四维裸值 {rp['raw_dimension_scores']}）")
    ok(f"全部分项带 caliber（共 "
       f"{sum(len(v) for v in rp['dimensions'].values())} 项）")


def check_sensitivity(rp) -> None:
    """★ 反向对照：完成度必须对核心目标敏感。

    造一个「composed > 0」的假想态，重算——完成度**必须**上升。
    若不上升，说明这些分项与「机器可校验的组合」这个核心目标脱钩，
    百分比再漂亮也是空的。**这是本层最有价值的一条断言。**
    """
    print("\n[2/3] 反向对照：完成度必须对核心目标敏感")
    # 先在真实产物上确认 composed=0 时该分项也是 0（口径自洽）
    body_items = (rp.get("dimensions") or {}).get("body") or []
    composed_item = next((i for i in body_items
                          if "composed" in (i.get("item") or "")), None)
    if composed_item is None:
        fail("找不到 composed 对应的分项——核心目标的直接判据必须在场")
        return
    if composed_item["done"] != 0:
        ok(f"注意：当前 composed = {composed_item['done']}（非 0），"
           f"分项口径 {composed_item['caliber'][:60]}")
        return
    ok(f"基线正确：composed = 0/213,531 ⇒ 该分项 0.0%")

    # 构造假想态：composed 变成 1000（0.47%）
    mut = copy.deepcopy(rp)
    for it in mut["dimensions"]["body"]:
        if "composed" in (it.get("item") or ""):
            it["done"] = 1000
            it["pct"] = 0.5
    naive = {k: round(sum(i["pct"] for i in v) / len(v), 1)
             for k, v in mut["dimensions"].items()}
    # 门控逻辑：composed 从 0 变非 0 ⇒ body 门控**解除** ⇒ 用朴素值
    raw = dict(naive)
    mut["raw_dimension_scores"] = raw
    mut["weighted_total_pct"] = round(
        sum(raw[k] * mut["weights"][k] for k in mut["weights"]), 1)

    if mut["weighted_total_pct"] <= rp["weighted_total_pct"]:
        fail("把 composed 调高后完成度**未上升** ⇒ 分项与核心目标脱钩，"
             "这个百分比测的是别的东西（更严重的解释：它是自证型指标）")
    else:
        ok(f"敏感性成立：composed 0 → 1000 时，门控解除且完成度 "
           f"{rp['weighted_total_pct']}% → {mut['weighted_total_pct']}%")

    # 门控有效性：门控只会压低不会抬高
    sc = rp.get("scoring") or {}
    n_body = (sc.get("naive_dimension_scores") or {}).get("body")
    g_body = (sc.get("gated_dimension_scores") or {}).get("body")
    if isinstance(n_body, (int, float)) and isinstance(g_body, (int, float)):
        if g_body > n_body:
            fail("门控值高于朴素值——门控只会压低不会抬高，反了")
        elif g_body < n_body:
            ok(f"门控生效：body 朴素 {n_body}% → 门控 {g_body}%"
               f"（差额 {round(n_body - g_body, 1)} = 基础设施掩盖核心判据的量）")
        else:
            ok(f"门控未生效：body 门控 == 朴素 == {g_body}%"
               "（核心判据已被另一种关系类型回答，见下方反向对照）")

    # ══════════════════════════════════════════════════════════════
    # ★★★ 2026-10-05 新增：判据被扩展为「任一关系类型可判定」之后，
    # **最关键的风险是「借扩判据虚高」**。
    # 因此必须有一条硬反向对照：**把 co_mount 的判定数打到 0，
    # 门控必须重新生效、完成度必须回落**。
    # 若这条不成立，那 21.9% 就是我改判据偷来的，不是真进展。
    # ══════════════════════════════════════════════════════════════
    cm_item = next((i for i in rp["dimensions"]["body"]
                    if "共装关系可判定" in (i.get("item") or "")), None)
    if cm_item is None:
        fail("body 维缺「共装关系可判定」分项 —— "
             "第三种关系类型的进展不可见，则完成度无法反映它")
        return
    if cm_item["done"] == 0:
        fail("co_mount 判定数为 0 —— 共装层零可判定，"
             "此时 body 维门控应当重新生效")
        return
    ok(f"共装判定：{cm_item['done']}/{cm_item['total']}"
       f" = {cm_item['pct']}%")

    # 反向对照：co_mount 归零 ⇒ 门控必须重新生效 ⇒ body 记 0 ⇒ 总完成度回落
    m = copy.deepcopy(rp)
    for it in m["dimensions"]["body"]:
        if "共装关系可判定" in (it.get("item") or ""):
            it["done"] = 0
            it["pct"] = 0.0
        elif "composed" in (it.get("item") or ""):
            pass                      # composed 本来就是 0
    n2 = {k: round(sum(i["pct"] for i in v) / len(v), 1)
          for k, v in m["dimensions"].items()}
    # 门控逻辑现算：两种关系都没回答 ⇒ body = 0
    n2["body"] = 0.0
    m["raw_dimension_scores"] = n2
    m["weighted_total_pct"] = round(
        sum(n2[k] * m["weights"][k] for k in m["weights"]), 1)
    if m["weighted_total_pct"] >= rp["weighted_total_pct"]:
        fail("★ 把 co_mount 判定打到 0 后完成度**未回落**"
             f"（{rp['weighted_total_pct']}% → {m['weighted_total_pct']}%）"
             " ⇒ 门控被架空，21.9% 是改判据偷来的虚高，不是真进展")
    else:
        ok(f"★ 关键反向对照成立：co_mount 归零 ⇒ 门控重新生效 ⇒ "
           f"完成度 {rp['weighted_total_pct']}% → "
           f"{m['weighted_total_pct']}%（回落 "
           f"{round(rp['weighted_total_pct'] - m['weighted_total_pct'], 1)}）"
           " ⇒ 提升来自真实进展，不是判据放宽")

    # 反向对照 ②：composed 上升时完成度也必须上升（两个关系类型都敏感）
    m2 = copy.deepcopy(rp)
    for it in m2["dimensions"]["body"]:
        if "composed" in (it.get("item") or ""):
            it["done"] = 1000
            it["pct"] = 0.5
    n3 = {k: round(sum(i["pct"] for i in v) / len(v), 1)
          for k, v in m2["dimensions"].items()}
    m2["raw_dimension_scores"] = n3
    m2["weighted_total_pct"] = round(
        sum(n3[k] * m2["weights"][k] for k in m2["weights"]), 1)
    if m2["weighted_total_pct"] <= rp["weighted_total_pct"]:
        fail("把 composed 调高后完成度未上升 ⇒ 对 peer-to-peer 不敏感")
    else:
        ok(f"对 peer-to-peer 也敏感：composed ↑ ⇒ "
           f"{rp['weighted_total_pct']}% → {m2['weighted_total_pct']}%")


def _mut_caliber_stripped(rp, label):
    m = copy.deepcopy(rp)
    for it in m["dimensions"]["body"]:
        it["caliber"] = ""
    return m


def _mut_weight_mismatch(rp, label):
    m = copy.deepcopy(rp)
    m["weights"]["body"] = m["weights"]["body"] + 0.1
    return m


def _mut_weight_not_sum_one(rp, label):
    m = copy.deepcopy(rp)
    m["weights"]["chain"] = 0.5
    return m


def _mut_drop_dimension(rp, label):
    m = copy.deepcopy(rp)
    m["dimensions"].pop("neuron", None)
    m["raw_dimension_scores"].pop("neuron", None)
    return m


def _mut_total_out_of_range(rp, label):
    m = copy.deepcopy(rp)
    m["weighted_total_pct"] = 140.0
    return m


def _mut_drop_rationale(rp, label):
    """删掉权重理由。

    2026-10-04 实测修正：原变异只删 ``meta.weight_rationale``（该字段压根不在
    meta 里，删了也没作用）⇒ 变异打空。真实要测的是「权重不可质疑」，
    故必须删**顶层**的 weight_rationale，且 honest_limits 里也不能再提「权重」。
    两者任一还在，权重就仍可被质疑 ⇒ 判据不该判红。
    """
    m = copy.deepcopy(rp)
    m["weight_rationale"] = ""
    m["meta"]["honest_limits"] = [
        x for x in m["meta"]["honest_limits"] if "权重" not in x
    ]
    return m


def _mut_rationale_in_wrong_place(rp, label):
    """把 weight_rationale 挪进 meta（字段位置错位）。

    实测踩过：判据读 meta.weight_rationale 而产物写在顶层 ⇒ 假红。
    反向也要测：产物挪进 meta 而判据读顶层 ⇒ 同样应判红。
    """
    m = copy.deepcopy(rp)
    m["meta"]["weight_rationale"] = m.pop("weight_rationale", "")
    return m


def _mut_gate_removed(rp, label):
    """门控被绕过：把 body 的门控值改用朴素值。

    ★ 实测踩到第四次「变异打空」：co_mount 落地后 body 门控**未生效**，
      此时 naive == gated ⇒ 换成朴素值**数值完全不变** ⇒ 判据无从破防。
      这是变异体本身失效，不是判据失效。
    修法：构造一个**门控本该生效**的态（co_mount 与 composed 皆 0），
      再把 body 改成朴素值 —— 这时朴素≠门控，变异才有意义。
      **变异必须打在「判据与产物不同的地方」，否则测的是巧合。**
    """
    m = copy.deepcopy(rp)
    for it in m["dimensions"]["body"]:
        if "共装关系可判定" in (it.get("item") or ""):
            it["done"] = 0
            it["pct"] = 0.0
    n = {k: round(sum(i["pct"] for i in v) / len(v), 1)
         for k, v in m["dimensions"].items()}
    # 正确行为：门控生效 ⇒ body = 0
    correct = dict(n)
    correct["body"] = 0.0
    # 变异行为：绕过门控，用朴素值（基础设施得分掩盖核心判据零分）
    m["raw_dimension_scores"] = dict(n)
    m["weighted_total_pct"] = round(
        sum(n[k] * m["weights"][k] for k in m["weights"]), 1)
    m["scoring"] = dict(m.get("scoring") or {})
    m["scoring"]["gated_dimension_scores"] = dict(correct)
    m["scoring"]["naive_dimension_scores"] = dict(n)
    return m


def _mut_gate_forced_zero(rp, label):
    """反向：门控被滥用 —— 在核心判据已回答时仍强行记 0（压低自己）。

    这条守「门控不会被用来偷偷压低完成度」。门控是双向的：
    不能靠它虚高，也不能靠它把已完成的维度归零。
    """
    m = copy.deepcopy(rp)
    g = dict((m.get("scoring") or {}).get("gated_dimension_scores")
             or m.get("raw_dimension_scores") or {})
    n = (m.get("scoring") or {}).get("naive_dimension_scores") or {}
    if not g or not n:
        return m
    # 找一门控未生效的维度，强行记 0
    for dim in g:
        if abs(float(g.get(dim, 0)) - float(n.get(dim, 0))) < 0.15 and \
                float(n.get(dim, 0)) > 0:
            g[dim] = 0.0
            break
    m["raw_dimension_scores"] = g
    m["weighted_total_pct"] = round(
        sum(g[k] * m["weights"][k] for k in m["weights"] if k in g), 1)
    m["scoring"] = dict(m.get("scoring") or {})
    m["scoring"]["gated_dimension_scores"] = g
    m["scoring"]["naive_dimension_scores"] = dict(n)
    return m


MUTATIONS = [
    ("门控被绕过（在门控该生效时改用朴素值虚高）", _mut_gate_removed),
    ("门控被滥用（已回答的维度仍强行记 0）", _mut_gate_forced_zero),
    ("分项 caliber 被清空", _mut_caliber_stripped),
    ("权重与裸值分叉（加权≠现算）", _mut_weight_mismatch),
    ("权重之和 ≠ 1.0", _mut_weight_not_sum_one),
    ("缺一个维度（少报）", _mut_drop_dimension),
    ("加权值越界（>100）", _mut_total_out_of_range),
    ("weight_rationale 被删（权重不可质疑）", _mut_drop_rationale),
    ("weight_rationale 位置错位（挪进 meta）", _mut_rationale_in_wrong_place),
]


def check_mutations(rp) -> None:
    print("\n[3/3] 变异检测（每个变异必须判红）")
    for label, fn in MUTATIONS:
        before = len(_MUTFAIL)
        _errors(fn(rp, label), sink=_mutfail)
        if len(_MUTFAIL) == before:
            fail(f"变异未被捕获：{label}（闸门对该变异不敏感）")
        else:
            print(f"  [ok]   变异已捕获：{label}（触发 {len(_MUTFAIL)-before} 条断言）")


def main() -> int:
    print("=" * 70)
    print("verify_research_progress — 核心目标完成度判据自证")
    print("=" * 70)
    rp = brp.build()

    check_baseline(rp)
    check_sensitivity(rp)
    check_mutations(rp)

    print("\n" + "=" * 70)
    if FAILED:
        print(f"FAIL：{len(FAILED)} 项未通过")
        for m in FAILED:
            print(f"  - {m}")
        return 1
    print("PASS：全部自证通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
