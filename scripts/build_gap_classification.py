#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_gap_classification — RoboParts 缺口成因分类器（D-GAP）。

方向锚点：docs/PROJECT_DIRECTIONS_V2.md §6.1（"把缺口的成因分类当研究"）。
路线图：docs/direction-evolution-roadmap-20260923.md 三·存量资产下一跳（5.69% → 主动 gap 研究）。

背景（为什么这是"创新"而非"统计"）
------------------------------------
机械接口声明率 5.69%（declared 15 + partial 10 / applicable 439）此前被当"短板"。
锚点 §6.1 把它收窄为：低值的成因有两种**未区分**的可能——
  (i) 厂商未公开规格（真数据缺口）
  (ii) 零件本就采用自研/专有接口（生态碎片化，非缺口）
在 (i)/(ii) 分类完成之前，不得把它单独当标准覆盖边界的实证证据。
本脚本做的正是这步分类，且**只在使用正向信号时落判，绝不猜测**：

  - status == n_a → `na`（锚点口径：非可判定粒度，不是缺口）
  - status ∈ {declared, partial} → `solved`（已有线索）
  - status == not_declared（真缺口，414 条）→ 按正向信号细分：
      * 制造商落在「已知专有安装生态」集合（由 partial 实体的 manufacturer 反推）→
        `proprietary_suspect`（成因 ii 嫌疑，有正向证据）
      * 有制造商但不在专有集合 → `unpublished_suspect`（成因 i 嫌疑，有明确抓取目标）
      * 连制造商都不知 → `ambiguous`（无法定位「谁没公开」，fail-closed）

计数口径与 facts() 完全一致（锚点 §5.3 单一真相源）：
  solved + na + open_gap == total_entities，且 solved == facts().mech_declared。
不一致即 SystemExit（fail-fast，宁可构建失败也不发布错数字）。
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 有机械安装面的物理零件品类——用于"哪些品类的开放缺口是物理安装缺口"的次级洞察。
PHYSICAL_MOUNT_CATEGORIES = {
    "actuators", "flexible_actuators", "grippers", "sensors", "platforms",
    "bionic_mechanisms", "reducers", "structural",
}


def _read_json(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


def _signal_axis_stats():
    """信号轴声明口径——**必须现算，不得手填**。

    2026-09-24 修正：本字段原为硬编码 ``declared_signal_ports: 0`` 加硬编码 note
    （声称「全库 0 条实体声明信号端口」）。信号轴改为按品类定向赋值后该口径已失效。
    这是锚点 §5.3「生成器模板里的裸数字是双盲区」的具体实例：锚点扫描与回归
    都不覆盖生成器**内部**的字面量，只会随时间静默失修。

    真相源只能是形态图——entities.json 没有 signal_interface 字段，信号角色
    是由品类映射（SIG_ROLE_BY_CATEGORY）派生的，不属于实体层字段。
    """
    try:
        g = _read_json(os.path.join("api", "morphology_graph.json"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "declared_signal_ports": None,
            "note": "形态图不可读，信号轴口径不可判定（fail-closed，不猜）。",
        }
    declared = []
    for n in g.get("nodes") or []:
        for p in n.get("ports") or []:
            if p["type"].startswith("SIG") and p.get("status") in ("declared", "partial"):
                declared.append(p)
    total_sig = sum(
        1 for n in (g.get("nodes") or []) for p in (n.get("ports") or [])
        if p["type"].startswith("SIG"))
    roles = {}
    for p in declared:
        roles[p["type"]] = roles.get(p["type"], 0) + 1
    return {
        "signal_ports_total": total_sig,
        "declared_signal_ports": len(declared),
        "declared_pct": round(100.0 * len(declared) / total_sig, 2) if total_sig else 0.0,
        "roles": roles,
        "note": (
            "信号角色由品类映射派生（SIG_ROLE_BY_CATEGORY），非实体层字段——"
            "entities.json 无 signal_interface 键。此计数现读形态图，禁止手填。"
            "composed 仍为 0 的归因不要看本节，看 api/compose_semantics.json 的"
            " aggregates.gap_distance / d1_bottleneck（配对级瓶颈定位）。"),
    }


def _gap_leverage(items, buckets):
    """缺口能否批量攻：按制造商聚合看头部集中度。

    这个判断直接决定声明率提上来的路径——若缺口集中在少数制造商，抓它们的
    datasheet 就能大幅提声明率；若高度分散，「按制造商批量抓」这条路就不成立，
    得换策略（用户提交、OSS BOM 反喂、社区 PR）。

    必须现算，不得手填——否则就变成「我们觉得缺口很集中」的自我暗示。
    """
    cnt = Counter()
    for e in items:
        mi = e.get("mechanical_interface")
        if isinstance(mi, dict) and mi.get("status") == "not_declared":
            cnt[e.get("manufacturer") or None] += 1
    total = sum(cnt.values())
    if not total:
        return {"open_gap_total": 0, "note": "无开放缺口，集中度不可判定。"}
    top = cnt.most_common(10)
    unknown = cnt.get(None, 0)
    return {
        "open_gap_total": total,
        "distinct_manufacturers": len(cnt),
        "top10_share_pct": round(100.0 * sum(c for _, c in top) / total, 1),
        "share_without_manufacturer_pct": round(100.0 * unknown / total, 1),
        "top10": [{"manufacturer": (m if m else "(无制造商)"), "count": c}
                  for m, c in top],
        "note": (
            "头部 10 家仅占 %s%%、独立制造商 %d 家、%s%% 的缺口连制造商都不知——"
            "「抓少数制造商 datasheet」是**必要但不充分**的手段，"
            "主缺口只能靠用户提交 / OSS BOM 反喂 / 社区 PR 收敛。"
            % (round(100.0 * sum(c for _, c in top) / total, 1),
               len(cnt), round(100.0 * unknown / total, 1))),
    }


def proprietary_set(items):
    """已知采用专有安装体系的制造商集合（由 partial 实体的 manufacturer 反推）。"""
    s = set()
    for e in items:
        mi = e.get("mechanical_interface")
        if isinstance(mi, dict) and mi.get("status") == "partial":
            m = e.get("manufacturer")
            if m:
                s.add(m)
    return s


def classify_entity(e, proprietary_mfrs):
    """纯函数：单个实体 → 桶名。fail-closed，绝不猜测。供验证器做变异/阴性对照。"""
    mi = e.get("mechanical_interface")
    if not isinstance(mi, dict):
        return None
    st = mi.get("status")
    mfr = e.get("manufacturer")
    if st == "n_a":
        return "na"
    if st in ("declared", "partial"):
        return "solved"
    # not_declared —— 真缺口，按正向信号细分
    if mfr in proprietary_mfrs:
        return "proprietary_suspect"
    # 只有**知道是谁**才能说「厂商未公开」——判据必须有制造商落点，否则无从谈起。
    if mfr:
        return "unpublished_suspect"
    # 连制造商都不知：无法定位「谁没公开」，也归不进专有集合。
    # 2026-09-24 修正：原判据是 `if mfr or src`，把「有出处但无制造商」也算
    # unpublished——但 59 条实体无制造商却有 source_tier，被推成「厂商未公开」
    # 是过度推断（既不知道厂商是谁，也就不知道它公开没公开）。退回 ambiguous。
    return "ambiguous"


def classify_items(items):
    """纯函数：返回 buckets 与 per_category（供 builder 与 verifier 共用，避免判据漂移）。"""
    prop = proprietary_set(items)
    buckets = {"solved": 0, "na": 0,
               "proprietary_suspect": 0, "unpublished_suspect": 0, "ambiguous": 0}
    per_category = defaultdict(lambda: defaultdict(int))
    for e in items:
        cls = classify_entity(e, prop)
        if cls is None:
            continue
        buckets[cls] += 1
        cat = e.get("category")
        per_category[cat][cls] += 1
        per_category[cat]["_total"] += 1
    return buckets, dict(per_category)


def build():
    ents = _read_json("api/entities.json")
    items = ents.get("entities") or []

    # facts() 作为交叉校验真相源（禁止手填计数）。
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from onboarding_block import facts  # noqa: E402
    f = facts()

    buckets, per_category = classify_items(items)
    prop = proprietary_set(items)

    physical_open_gap = 0  # 次级洞察：开放缺口中属"物理安装面"的部分
    examples = defaultdict(list)
    for e in items:
        cls = classify_entity(e, prop)
        if cls is None:
            continue
        if cls in ("proprietary_suspect", "unpublished_suspect", "ambiguous"):
            if e.get("category") in PHYSICAL_MOUNT_CATEGORIES:
                physical_open_gap += 1
        if len(examples[cls]) < 6 and e.get("id"):
            examples[cls].append(e["id"])

    # 交叉校验：solved 必须与 facts().mech_declared 一致（25）；
    # 各桶求和必须等于全库实体数（802，每个实体都带 mechanical_interface）。
    if buckets["solved"] != f["mech_declared"]:
        raise SystemExit(
            "!! gap_classification.solved(%d) != facts().mech_declared(%d)，拒绝生成"
            % (buckets["solved"], f["mech_declared"]))
    total_all = f["total_entities"]
    if sum(buckets.values()) != total_all:
        raise SystemExit(
            "!! gap_classification 各桶求和(%d) != 全库实体数(%d)，拒绝生成"
            % (sum(buckets.values()), total_all))

    open_gap = (buckets["proprietary_suspect"]
                + buckets["unpublished_suspect"] + buckets["ambiguous"])

    per_cat_out = {}
    for cat, d in sorted(per_category.items()):
        per_cat_out[cat] = {
            "total": d["_total"],
            "solved": d.get("solved", 0),
            "na": d.get("na", 0),
            "proprietary_suspect": d.get("proprietary_suspect", 0),
            "unpublished_suspect": d.get("unpublished_suspect", 0),
            "ambiguous": d.get("ambiguous", 0),
        }

    out = {
        "meta": {
            "schema": "roboparts/gap_classification/v1",
            "title": "RoboParts 机械接口缺口成因分类（Gap-Cause Taxonomy）",
            "anchor": "docs/PROJECT_DIRECTIONS_V2.md §6.1（方向锚点 v2.2 · D-GAP）",
            "generated_by": "scripts/build_gap_classification.py",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open_standard_alignment": (
                "分类维度可映射为 Croissant 1.1 数据集的 declaration_gap 属性"
                "（solved / na / proprietary / unpublished / ambiguous），"
                "PROV-O 溯源可由 source_tier 字段补出。"),
        },
        "totals": {
            "entities_total": total_all,
            "mech_applicable": f["mech_applicable"],
            "mech_declared": f["mech_declared"],
            "mech_not_declared": f["mech_not_declared"],
            "mech_n_a": f["mech_n_a"],
            "declared_pct": f["mech_pct"],
        },
        "buckets": {
            "solved": buckets["solved"],
            "na": buckets["na"],
            "open_gap": {
                "proprietary_suspect": buckets["proprietary_suspect"],
                "unpublished_suspect": buckets["unpublished_suspect"],
                "ambiguous": buckets["ambiguous"],
                "open_gap_total": open_gap,
                "physical_mount_open_gap": physical_open_gap,
            },
        },
        "cause_interpretation": {
            "solved": "已有公开可判定接口线索（declared/partial）。",
            "na": "锚点口径：非可判定粒度（status=n_a），不构成缺口。",
            "proprietary_suspect": "成因(ii)嫌疑：制造商已知采用专有安装体系"
                                  "（正向信号来自 partial 实体证据）。需补「专有转接盘」几何。",
            "unpublished_suspect": "成因(i)嫌疑：厂商存在但未公开法兰规格"
                                   "（真数据缺口）。需爬取厂商 datasheet。",
            "ambiguous": "现有数据无法区分 (i)/(ii)：缺制造商与出处。"
                         "fail-closed，标记证据缺失，等待用户提交/抓取。",
        },
        "evidence_required": {
            # 这两桶是飞轮可立即推进的"证据缺口"——去爬 datasheet / 收用户提交即可收敛。
            "targets": ["unpublished_suspect", "ambiguous"],
            "count": buckets["unpublished_suspect"] + buckets["ambiguous"],
            "note": "proprietary_suspect 亦需确认（补专有转接盘几何），"
                    "但动作是「记录专有形态」而非「等厂商公开」。",
        },
        "per_category": per_cat_out,
        "examples": dict(examples),
        "signal_axis": _signal_axis_stats(),
        "gap_leverage": _gap_leverage(items, buckets),
        "honest_limits": [
            "(i)/(ii) 的拆分是**嫌疑**而非**确认**：仅 proprietary_suspect 使用正向信号"
            "（制造商落在已知专有生态），unpublished_suspect / ambiguous 均为开放缺口，"
            "需进一步证据（厂商文档抓取或用户提交）才能定论。分类器**不猜测**。",
            "5.69% 在此框架下是「公开可判定粒度上的标准登记率」，其低值由 (i)/(ii) 两类"
            "未区分成因构成；本分类是把它拆开的第一步，不是标准覆盖边界的实证证据。",
            "na 桶不是缺口，请勿并入缺口率分母。",
            "unpublished_suspect 的判据是**排除法**：「有制造商但不落专有集合」→ 推定"
            "厂商有规格未公开。它无法区分「厂商真没公开」与「我们没爬到」——后者同样判"
            "published 嫌疑。故该桶是**抓取目标清单**，不是「厂商不公开」的实证。",
            "2026-09-24 判据收紧：原判据为 `manufacturer ∨ source`，把 59 条**无制造商**"
            "但有 source_tier 的实体推成 unpublished——但不知厂商是谁就谈不上「厂商未公开」，"
            "属过度推断，已退回 ambiguous。收紧后 unpublished 350 / ambiguous 59。",
        ],
        "rule_transparency": {
            "proprietary_ecosystem_size": len(prop),
            "proprietary_ecosystem_sample": sorted(list(prop))[:8],
            "classification": [
                "status==n_a → na",
                "status∈{declared,partial} → solved",
                "status==not_declared ∧ manufacturer∈PROPRIETARY → proprietary_suspect",
                "status==not_declared ∧ manufacturer≠∅ → unpublished_suspect",
                "status==not_declared ∧ manufacturer=∅ → ambiguous",
            ],
            "caveat": "unpublished 与 ambiguous 的分界是「制造商字段是否有值」，"
                      "不是「厂商是否公开」。source_tier 单独不足以判定成因。",
        },
    }
    return out


def main():
    out = build()
    dest = os.path.join(ROOT, "api", "gap_classification.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    b = out["buckets"]
    og = b["open_gap"]
    print("gap_classification 生成:", dest)
    print("  solved=%d  na=%d  open_gap=%d (proprietary=%d / unpublished=%d / ambiguous=%d)"
          % (b["solved"], b["na"], og["open_gap_total"],
              og["proprietary_suspect"], og["unpublished_suspect"], og["ambiguous"]))
    print("  evidence_required(count)=%d  physical_mount_open_gap=%d"
          % (out["evidence_required"]["count"], og["physical_mount_open_gap"]))


if __name__ == "__main__":
    main()
