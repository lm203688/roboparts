#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline.stages.gap — gap_classification 拆成 7 个纯函数算子。

对应关系（build_gap_classification.py → 算子）
------------------------------------------------
  _read_json + facts()        → gap.load_entities
  proprietary_set(items)      → gap.derive_proprietary
  classify_items(items)       → gap.classify_all（含 classify_entity 内联）
  build() 中的 crosscheck     → gap.crosscheck
  _signal_axis_stats()        → gap.signal_axis_stats
  _gap_leverage(items, ...)   → gap.gap_leverage
  build() 中的 output 组装     → gap.assemble

等价性约束
----------
gap.assemble 的输出必须与 build_gap_classification.py 的 build() 产出
**除 generated_at 时间戳外完全一致**。verify_pipeline.py 用 json 结构相等
断言这条约束（不是字符串相等，允许 indent 差异）。

若本文件任何算子改动导致 assemble 输出变化，就是**破坏等价性**——要么改
回，要么同步改 build_gap_classification.py 让两条路径保持等价。这是防止
"pipeline 与旧脚本悄悄分叉"的唯一闸门。
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from ..registry import operator

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 从 build_gap_classification.py 复用常量——单一真相源，禁止复制。
# 这里用 sys.path 导入避免相对导入失败。
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_gap_classification import PHYSICAL_MOUNT_CATEGORIES  # noqa: E402


def _read_json(path: str):
    """相对仓库根读取 JSON。fail-fast：任何 IO/JSON 错误原样抛出。"""
    full = os.path.join(ROOT, path)
    with open(full, encoding="utf-8") as f:
        return json.load(f)


@operator("gap.load_entities", "gap",
          "读 api/entities.json 并抓取 facts() 作交叉校验真相源")
def load_entities(path: str) -> Dict[str, Any]:
    """读实体清单 + facts()。两者都必须可读，否则抛错。"""
    if not path:
        raise ValueError("load_entities: path 不能为空")
    data = _read_json(path)
    items = data.get("entities") or []
    if not isinstance(items, list):
        raise TypeError(f"load_entities: entities 应为 list，收到 {type(items).__name__}")

    # facts() 是单一真相源（锚点 §5.3）——每次现读，不缓存、不假设。
    from onboarding_block import facts
    return {"items": items, "facts": facts()}


@operator("gap.derive_proprietary", "gap",
          "从 partial 实体的 manufacturer 反推「已知专有安装生态」制造商集合")
def derive_proprietary(items: List[Dict[str, Any]]) -> Set[str]:
    """等价于 build_gap_classification.proprietary_set。"""
    if not isinstance(items, list):
        raise TypeError(f"derive_proprietary: items 应为 list，收到 {type(items).__name__}")
    s: Set[str] = set()
    for e in items:
        mi = e.get("mechanical_interface")
        if isinstance(mi, dict) and mi.get("status") == "partial":
            m = e.get("manufacturer")
            if m:
                s.add(m)
    return s


@operator("gap.classify_all", "gap",
          "对每个实体应用分类判据，返回 buckets + per_category + examples + physical_open_gap")
def classify_all(
    items: List[Dict[str, Any]],
    proprietary_mfrs: Set[str],
) -> Dict[str, Any]:
    """等价于 build_gap_classification.classify_items + build() 中的 examples 收集。

    注意：classify_entity 是纯函数、可被 verifier 直接调用做变异/阴性对照。
    这里内联调用，避免算子边界引入额外开销。
    """
    if not isinstance(items, list):
        raise TypeError(f"classify_all: items 应为 list，收到 {type(items).__name__}")
    if not isinstance(proprietary_mfrs, (set, frozenset)):
        raise TypeError(
            f"classify_all: proprietary_mfrs 应为 set，收到 {type(proprietary_mfrs).__name__}")

    buckets = {"solved": 0, "na": 0,
               "proprietary_suspect": 0, "unpublished_suspect": 0, "ambiguous": 0}
    per_category = defaultdict(lambda: defaultdict(int))
    examples = defaultdict(list)
    physical_open_gap = 0

    for e in items:
        cls = _classify_entity(e, proprietary_mfrs)
        if cls is None:
            continue
        buckets[cls] += 1
        cat = e.get("category")
        per_category[cat][cls] += 1
        per_category[cat]["_total"] += 1

        if cls in ("proprietary_suspect", "unpublished_suspect", "ambiguous"):
            if cat in PHYSICAL_MOUNT_CATEGORIES:
                physical_open_gap += 1

        if len(examples[cls]) < 6 and e.get("id"):
            examples[cls].append(e["id"])

    return {
        "buckets": buckets,
        "per_category": dict(per_category),
        "examples": dict(examples),
        "physical_open_gap": physical_open_gap,
    }


def _classify_entity(e: Dict[str, Any], proprietary_mfrs: Set[str]) -> str:
    """单实体分类判据。与 build_gap_classification.classify_entity 判据一致。

    这是内部工具函数（不加 @operator 装饰），因为它是 classify_all 的实现细节，
    不是 DAG 里的一步。想改判据只能改这里 + 同步改 build_gap_classification.py，
    保持两条路径等价。
    """
    mi = e.get("mechanical_interface")
    if not isinstance(mi, dict):
        return None
    st = mi.get("status")
    mfr = e.get("manufacturer")
    if st == "n_a":
        return "na"
    if st in ("declared", "partial"):
        return "solved"
    if mfr in proprietary_mfrs:
        return "proprietary_suspect"
    if mfr:
        return "unpublished_suspect"
    return "ambiguous"


@operator("gap.crosscheck", "gap",
          "buckets 与 facts() 交叉校验；不一致即 SystemExit（fail-fast）")
def crosscheck(
    buckets: Dict[str, int],
    facts: Dict[str, int],
) -> Dict[str, Any]:
    """两条硬约束：
    1. buckets["solved"] == facts["mech_declared"]
    2. sum(buckets.values()) == facts["total_entities"]

    任一违反即 SystemExit——宁可构建失败也不发布错数字（锚点纪律）。
    """
    if not isinstance(buckets, dict):
        raise TypeError(f"crosscheck: buckets 应为 dict，收到 {type(buckets).__name__}")
    if not isinstance(facts, dict):
        raise TypeError(f"crosscheck: facts 应为 dict，收到 {type(facts).__name__}")

    solved = buckets.get("solved")
    declared = facts.get("mech_declared")
    if solved != declared:
        raise SystemExit(
            f"!! crosscheck: buckets.solved({solved}) != facts.mech_declared({declared})")

    total = sum(buckets.values())
    expected = facts.get("total_entities")
    if total != expected:
        raise SystemExit(
            f"!! crosscheck: sum(buckets.values())({total}) != facts.total_entities({expected})")

    return {"solved": solved, "total": total, "ok": True}


@operator("gap.signal_axis_stats", "gap",
          "从形态图现算信号轴声明口径——禁止手填")
def signal_axis_stats(path: str) -> Dict[str, Any]:
    """等价于 build_gap_classification._signal_axis_stats。

    2026-09-24 修正点已固化：本函数不再接受任何硬编码计数参数，
    只能现读 morphology_graph.json。形态图不可读则 fail-closed 返回
    declared_signal_ports=None + note。
    """
    if not path:
        raise ValueError("signal_axis_stats: path 不能为空")
    try:
        g = _read_json(path)
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


@operator("gap.gap_leverage", "gap",
          "按制造商聚合看缺口头部集中度——决定批量攻还是分布式攻")
def gap_leverage(
    items: List[Dict[str, Any]],
    buckets: Dict[str, int],
) -> Dict[str, Any]:
    """等价于 build_gap_classification._gap_leverage。"""
    if not isinstance(items, list):
        raise TypeError(f"gap_leverage: items 应为 list，收到 {type(items).__name__}")
    cnt: Counter = Counter()
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


@operator("gap.assemble", "gap",
          "把前面所有步骤的产物组装为最终 JSON（等价于 build_gap_classification.build 的返回体）")
def assemble(
    items: List[Dict[str, Any]],
    buckets: Dict[str, int],
    per_category: Dict[str, Any],
    examples: Dict[str, List[str]],
    physical_open_gap: int,
    proprietary_mfrs: Set[str],
    signal_axis: Dict[str, Any],
    gap_leverage: Dict[str, Any],
    facts: Dict[str, int],
) -> Dict[str, Any]:
    """等价于 build_gap_classification.build() 的 output 组装。

    输出结构与 build_gap_classification.py 完全一致——verify_pipeline.py 会
    逐字段比对。任何键名/嵌套变化都会被等价性断言抓住。
    """
    total_all = facts["total_entities"]
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
            "generated_by": "scripts/pipeline/stages/gap.py (assemble)",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open_standard_alignment": (
                "分类维度可映射为 Croissant 1.1 数据集的 declaration_gap 属性"
                "（solved / na / proprietary / unpublished / ambiguous），"
                "PROV-O 溯源可由 source_tier 字段补出。"),
        },
        "totals": {
            "entities_total": total_all,
            "mech_applicable": facts["mech_applicable"],
            "mech_declared": facts["mech_declared"],
            "mech_not_declared": facts["mech_not_declared"],
            "mech_n_a": facts["mech_n_a"],
            "declared_pct": facts["mech_pct"],
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
            "targets": ["unpublished_suspect", "ambiguous"],
            "count": buckets["unpublished_suspect"] + buckets["ambiguous"],
            "note": "proprietary_suspect 亦需确认（补专有转接盘几何），"
                    "但动作是「记录专有形态」而非「等厂商公开」。",
        },
        "per_category": per_cat_out,
        "examples": dict(examples),
        "signal_axis": signal_axis,
        "gap_leverage": gap_leverage,
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
            "proprietary_ecosystem_size": len(proprietary_mfrs),
            "proprietary_ecosystem_sample": sorted(list(proprietary_mfrs))[:8],
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
