#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_derived_features.py — 应有特征推导层生成器（唯一真相源）

【是什么】
本层不采集任何数据，只**推导**：给一个 ISO 9409-1 标号，该标号按标准梯级
「应当」有什么孔数、什么螺纹、什么外径。它把 canonical_ladder_iso_9409_1
预先展开成一张可查的期望索引，于是：

  1. 已登记的标号 → 可与登记表里手写的 is_canonical_iso 做交叉验证
     （两个独立写法对同一事实下结论，不一致即数据错误）
  2. 有标号但无规范行的实体侧声明 → 也能给出「按标准应当如何」，
     而不是返回 unknown 让 agent 去猜
  3. 手写 note 里的「偏离 ISO 标准梯级为 X」→ 可被机械复算，不必相信人写的话

【方法学出处】
问题结构与 Cornell MS2KOSMOS（bioRxiv 2026.08）同构：它不检索原始谱图，
而是**先对已知小分子结构预计算出应有的观测谱图**（8 亿+ 预测谱）再入库，
于是连没测过的观测也能被比对。本层对法兰做同一件事：先按梯级预计算应有
几何，再拿声明值来比。

【必须诚实的边界（不是免责套话，是实测结论）】
canonical_ladder_iso_9409_1 在登记表里是一个**裸数组，没有独立出处引用**
（无 source 字段、无 source_tier）。所以本层：
  - 能做的事：内部一致性闸门（0 矛盾即通过）、声明缺失时的判定补位、
    手写 note 的机械复算。
  - 不能做的事：它**不是**独立的外部权威。期望值与 is_canonical_iso 标签
    最终都压在同一个未引用基准上。故本层 confidence 上限继承登记表的
    source_tier=B，绝不因「是算出来的」而自封 A。

【纪律】
- 幂等：重复运行产出字节一致（排序固定、不写部署时间戳）
- 不新增标准行：本层只查表与比对，绝不向 flange_designations 发明条目
  （L1.77：未读到 ISO 9409-1:2004 原文即不替标准发明条目）
- 只读两个源，只写 api/derived_features.json
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_MECH = os.path.join(ROOT, "api", "mechanical_interfaces.json")
SRC_ENT = os.path.join(ROOT, "api", "entities.json")
OUT = os.path.join(ROOT, "api", "derived_features.json")
ACCESS_TEMPLATE_SRC = os.path.join(ROOT, "api", "platforms.json")

# 标号解析：实体库侧用无 A 形式，登记表 id 用带 A 形式，二者同一孔位
TOK_RE = re.compile(r"^ISO9409-1-(\d+(?:\.\d+)?)-(\d+)-M(\d+)$")


def normalize(s: Any) -> str:
    """与登记表 grammar.designation_forms.normalize_rule 同一口径：
    去空格、大写、删除尺寸段前的 'A' 前缀。查表用，不承载等价断言。
    """
    return re.sub(r"ISO9409-1-A", "ISO9409-1-", str(s).upper().replace(" ", ""))


def read_bytes(path: str) -> bytes:
    with io.open(path, "rb") as f:
        return f.read()


def sha256_of(path: str) -> str:
    return hashlib.sha256(read_bytes(path)).hexdigest()


def load_json(path: str) -> Any:
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_access_block() -> Dict[str, Any]:
    """取站点标准「AI 领 key 入口」块。
    纪律同 build_negative_compat.py：不从本文件硬编码，否则站点各处领 key
    文案会各自漂移。注意 meta.access 是部署注入器的受管区域，会被整块覆盖，
    故本文件自己的边界声明一律写在 meta 顶层，不放 access 里。
    """
    access = load_json(ACCESS_TEMPLATE_SRC).get("meta", {}).get("access")
    if not access:
        raise SystemExit(f"{ACCESS_TEMPLATE_SRC} 缺少 meta.access，无法作为模板")
    return json.loads(json.dumps(access))


def ladder_index(ladder: List[Dict[str, Any]]) -> Dict[float, Dict[str, Any]]:
    """PCD → 梯级应有的几何。固定为 {pcd: row}，重复 PCD 会显式报错而非静默覆盖。"""
    idx: Dict[float, Dict[str, Any]] = {}
    for r in ladder:
        p = float(r["pcd"])
        if p in idx:
            raise SystemExit(f"canonical_ladder_iso_9409_1 中 PCD={p:g} 重复，索引不唯一，拒绝推导")
        idx[p] = r
    return idx


def nearest_rungs(ladder: List[Dict[str, Any]], pcd: float, k: int = 2) -> List[Dict[str, Any]]:
    """离目标 PCD 最近的 k 档，用于「非标准梯级」时给出最近可行解。
    排序键：距离 → PCD 值，保证幂等（距离并列时不依赖 list 顺序）。
    """
    return sorted(
        ({"pcd": float(r["pcd"]), "holes": int(r["holes"]), "thread": r["thread"],
          "iso_outer_diameter": float(r["iso_outer_diameter"])} for r in ladder
     ),
        key=lambda x: (abs(x["pcd"] - pcd), x["pcd"]),
    )[:k]


def derive(ladder: List[Dict[str, Any]],
           row: Dict[str, Any]) -> Dict[str, Any]:
    """对一个已登记标号推导「应有几何」并判定偏差类型。"""
    pcd = float(row["d1_mm"])
    holes = int(row["bolt_count"])
    thread = str(row["thread"]).upper()
    idx = ladder_index(ladder)
    rung = idx.get(pcd)

    if rung is None:
        near = nearest_rungs(ladder, pcd)
        # residual（无梯级档）：PCD 与外径都相对最近一档。转接盘必须同时补偿这两维。
        nearest = near[0] if near else None
        residual = None
        if nearest is not None:
            residual = {
                "target_rung_pcd_mm": nearest["pcd"],
                "pcd_delta_mm": pcd - nearest["pcd"],
                "bolt_count_delta": holes - int(nearest["holes"]),
                "thread_declared": thread,
                "thread_expected": nearest["thread"],
                "thread_delta": (thread != nearest["thread"]),
                "iso_outer_diameter_delta_mm": None,
                "min_correction_dims": [d for d, on in [
                    ("pcd", residual_pcd_differs(pcd, nearest["pcd"])),
                    ("bolt_count", holes != int(nearest["holes"])),
                    ("thread", thread != nearest["thread"]),
                ] if on],
                "compensation_path": "adapter_plate_to_nearest_rung",
            }
        return {
            "pcd_mm": pcd,
            "bolt_count": holes,
            "thread": thread,
            "on_standard_ladder": False,
            "expected": None,
            "nearest_rungs": near,
            "classification": "no_standard_rung",
            "deviation_dims": [],
            "derived_is_canonical": False,
            "residual": residual,
        }

    eh, et = int(rung["holes"]), str(rung["thread"]).upper()
    dims = []
    if holes != eh:
        dims.append("bolt_count")
    if thread != et:
        dims.append("thread")

    if not dims:
        cls = "matches_canonical"
    elif dims == ["thread"]:
        cls = "deviates_thread_only"
    else:
        cls = "deviates_holes_and_thread"

    # residual：转接盘的最小几何修正量（PPS 哲学——冻结 base 不动，只量化差异）
    # 相对当前档 expected：转接盘必须补偿的实际 mm / 颗数 / 螺纹规格。
    outer_delta = _row_iso_outer_diameter_delta(row, float(rung["iso_outer_diameter"]))
    residual = {
        "target_rung_pcd_mm": pcd,
        "pcd_delta_mm": 0.0,  # 已在梯级上，PCD 无修正
        "bolt_count_delta": holes - eh,
        "thread_declared": thread,
        "thread_expected": et,
        "thread_delta": (thread != et),
        "iso_outer_diameter_delta_mm": outer_delta,
        "min_correction_dims": list(dims),
        "compensation_path": "adapter_plate" if dims else "direct",
    }

    return {
        "pcd_mm": pcd,
        "bolt_count": holes,
        "thread": thread,
        "on_standard_ladder": True,
        "expected": {
            "bolt_count": eh,
            "thread": et,
            "iso_outer_diameter": float(rung["iso_outer_diameter"]),
        },
        "nearest_rungs": None,
        "classification": cls,
        "deviation_dims": dims,
        "derived_is_canonical": cls == "matches_canonical",
        "residual": residual,
    }


def residual_pcd_differs(a: float, b: float) -> bool:
    """PCD 是否真的不同（浮点容差 0.01mm，避免 31.5000000001 判为偏离）。"""
    return abs(a - b) > 1e-3


def _row_iso_outer_diameter_delta(row: Dict[str, Any], expected: float) -> Optional[float]:
    """row 是否显式声明了 iso_outer_diameter；有则算 delta，无则 None（诚实边界）。"""
    v = row.get("iso_outer_diameter") or row.get("d2_mm")
    if v is None:
        return None
    try:
        return float(v) - expected
    except (TypeError, ValueError):
        return None


def entity_tokens(ents: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """从实体库现算 ISO 9409 标号的使用面。
    单值/多值双吃：mechanical_interface.standard 既可能是字符串也可能是数组
    （L1.74 p4 纪律——多孔位条目写成数组，单孔位写成标量，两种都必须吃）。
    """
    out: Dict[str, Dict[str, Any]] = {}
    for e in ents:
        mi = e.get("mechanical_interface") or {}
        eid = e.get("id")
        for key in ("standard", "flange", "tool_side", "tool_side_flange"):
            v = mi.get(key)
            if not v:
                continue
            vals = v if isinstance(v, list) else [v]
            for tok in vals:
                if not isinstance(tok, str):
                    continue
                if "9409" not in tok:
                    continue
                slot = out.setdefault(tok, {"entity_ids": set(), "sides": set(), "fields": set()})
                slot["entity_ids"].add(eid)
                slot["fields"].add(key)
                slot["sides"].add("tool" if key.startswith("tool_side") else "robot")
    return {k: {
        "entity_ids": sorted(v["entity_ids"]),
        "sides": sorted(v["sides"]),
        "fields": sorted(v["fields"]),
    } for k, v in out.items()}


def note_corroborates(row: Dict[str, Any], d: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """机械复算手写 note：note 声称「标准梯级为 N×Mk」或「最近为 PCDx」时，能否被推导复现。

    返回 None 表示该 note 不含可复算的断言（不强行判定，避免假绿）。
    recomputable=False 表示有断言但写法无法解析（同样不判绿）。

    判据是「note 是否提及推导所得的应有模式」——比「note 是否只写那一个」宽松，
    因为 note 通常同时写了实测值与标准值（如 A31.5 同时出现 4×M5 与 4×M6），
    取交集判断是保守的：推导出 4×M6 而 note 确实写了 4×M6，即算佐证。
    """
    note = row.get("note")
    if not note:
        return None
    # 归一化：乘号统一为 x，且**不做 upper**（upper 会把 x 变 X，
    # 与大小写敏感的正则叠加即恒空匹配 —— 正是「闸门恒真」那类静默假绿）
    flat = str(note).replace("\u00d7", "x")
    claimed = set(re.findall(r"(\d+)\s*x\s*m(\d+)", flat, re.IGNORECASE))
    mentioned_pcds = {float(p) for p in re.findall(r"pcd\s*(\d+(?:\.\d+)?)", flat, re.IGNORECASE)}

    d_exp = d["expected"]
    if d_exp is not None:
        exp_claim = (str(d_exp["bolt_count"]), str(int(d_exp["thread"].lstrip("M"))))
        has_exp = exp_claim in claimed
        if not claimed:
            return {"kind": "expected_pattern", "recomputable": False,
                    "note_claims": [],
                    "derived_expected": f"{d_exp['bolt_count']}xM{int(d_exp['thread'].lstrip('M'))}",
                    "detail": "note 未含可解析的 N×Mk 模式，无法机械复算"}
        return {"kind": "expected_pattern", "recomputable": True, "agrees": has_exp,
                "note_claims": [f"{n}xM{m}" for n, m in sorted(claimed, key=lambda x: (int(x[0]), int(x[1])))],
                "derived_expected": f"{d_exp['bolt_count']}xM{int(d_exp['thread'].lstrip('M'))}"}

    # 无梯级档：改判 note 是否提到推导给出的最近档 PCD
    if not mentioned_pcds:
        return {"kind": "nearest_rung", "recomputable": False,
                "note_claims": [],
                "detail": "note 提到偏离/非梯级但未给出可解析的最近档 PCD，无法机械复算"}
    near_pcds = {r["pcd"] for r in (d.get("nearest_rungs") or [])}
    agree = bool(mentioned_pcds & near_pcds)
    return {"kind": "nearest_rung", "recomputable": True, "agrees": agree,
            "note_claims": sorted(mentioned_pcds),
            "derived_nearest": sorted(near_pcds)}


def build() -> Dict[str, Any]:
    mech = load_json(SRC_MECH)
    ents_doc = load_json(SRC_ENT)
    ladder = mech.get("canonical_ladder_iso_9409_1") or []
    rows = mech.get("flange_designations") or []
    ents = ents_doc.get("entities") or []

    if len(ladder) < 2:
        raise SystemExit(f"canonical_ladder_iso_9409_1 档位不足 2（{len(ladder)}），拒绝产出")
    if len(rows) < 2:
        raise SystemExit(f"flange_designations 不足 2 条（{len(rows)}），拒绝产出")

    # ── 期望索引：每个梯级档 + 最近档指引 ─────────────────────────────────
    expectation_index = []
    idx = ladder_index(ladder)
    for pcd in sorted(idx):
        r = idx[pcd]
        expectation_index.append({
            "pcd_mm": pcd,
            "expected_bolt_count": int(r["holes"]),
            "expected_thread": r["thread"],
            "iso_outer_diameter": float(r["iso_outer_diameter"]),
        })

    # ── 逐标号推导 + 与手写标签/note 交叉验证 ──────────────────────────────
    derivations = []
    agree_flag = disagree_flag = 0
    note_recomp = note_agree = notes_with_assertion = note_unparseable = 0
    for row in sorted(rows, key=lambda x: (float(x["d1_mm"]), x["id"])):
        d = derive(ladder, row)
        stored = row.get("is_canonical_iso")
        flag_match = (stored == d["derived_is_canonical"])
        if stored is None:
            agree_flag = -1  # 未标注，不计入一致率
        elif flag_match:
            agree_flag += 1
        else:
            disagree_flag += 1
        nc = note_corroborates(row, d)
        if nc is not None:
            notes_with_assertion += 1
            if nc.get("recomputable"):
                note_recomp += 1
                if nc.get("agrees"):
                    note_agree += 1
            else:
                note_unparseable += 1
        derivations.append({
            "id": row["id"],
            "registry_source_tier": row.get("source_tier", "C"),
            **d,
            "stored_is_canonical_iso": stored,
            "flag_agrees_with_derivation": flag_match,
            "note_corroboration": nc,
            "handwritten_note": row.get("note"),
        })

    # ── 实体侧标号裁决 ────────────────────────────────────────────────────
    by_alias: Dict[str, str] = {}
    for row in rows:
        for a in (row.get("aliases") or []):
            by_alias[normalize(a)] = row["id"]
        by_alias.setdefault(normalize(row["id"]), row["id"])

    tok_map = entity_tokens(ents)
    dmap = {x["id"]: x for x in derivations}
    token_verdicts = []
    for tok in sorted(tok_map):
        info = tok_map[tok]
        norm = normalize(tok)
        m = TOK_RE.match(norm)
        if not m:
            verdict = "unparseable_bare_standard"
            detail = ("标号只到标准号本身，未给出 (PCD, 孔数, 螺纹)，无从推导应有几何；"
                      "这不是数据缺口可补，而是厂商未声明到可判定粒度。")
            token_verdicts.append({
                "token_as_written": tok, "normalized": norm, "parsed": None,
                "registry_row": by_alias.get(norm),
                "classification": None, "verdict": verdict, "detail": detail,
                "entity_count": len(info["entity_ids"]),
                "entity_ids": info["entity_ids"], "sides": info["sides"], "fields": info["fields"],
            })
            continue
        parsed = {"d1_mm": float(m.group(1)), "bolt_count": int(m.group(2)),
                  "thread": "M" + m.group(3)}
        rrow = by_alias.get(norm)
        if rrow is None:
            verdict = "derivable_not_registered"
            detail = ("实体在引用、登记表无对应行。但按标准梯级可推导应有几何，"
                      "故仍可给出「应当如何」，不必返回 unknown 让 agent 猜。")
            syn = {"d1_mm": parsed["d1_mm"], "bolt_count": parsed["bolt_count"],
                   "thread": parsed["thread"]}
            d = derive(ladder, syn)
            cls = d["classification"]
        else:
            d = dmap[rrow]
            cls = d["classification"]
            if cls == "matches_canonical":
                verdict = "registered_and_canonical"
                detail = "已登记，且实测几何与标准梯级期望一致——两个独立写法得出同一结论。"
            elif cls == "no_standard_rung":
                verdict = "registered_off_ladder"
                detail = ("已登记，但该 PCD 不在标准梯级上（实测存在的厂商专用尺寸）。"
                          "推导给出最近档，便于转接与选型。")
            else:
                verdict = "registered_documented_deviation"
                _r = d.get("residual") or {}
                _dim_desc = []
                if _r.get("bolt_count_delta", 0) != 0:
                    _dim_desc.append(f"孔数{_r['bolt_count_delta']:+d}颗")
                if _r.get("thread_delta"):
                    _dim_desc.append(f"螺纹 {parsed['thread']}→{_r.get('thread_expected','?')}")
                _outer = _r.get("iso_outer_diameter_delta_mm")
                if _outer is not None:
                    _dim_desc.append(f"外径{_outer:+.1f}mm")
                detail = (f"已登记，但偏离标准梯级（转接盘最小修正量：{'；'.join(_dim_desc) or '无'}）。"
                          f"ISO 期望 {d['expected']['bolt_count']}x"
                          f"{d['expected']['thread']}，实测 {parsed['bolt_count']}x{parsed['thread']}。")

        token_verdicts.append({
            "token_as_written": tok, "normalized": norm, "parsed": parsed,
            "registry_row": rrow, "classification": cls,
            "expected": d["expected"], "nearest_rungs": d["nearest_rungs"],
            "verdict": verdict, "detail": detail,
            "entity_count": len(info["entity_ids"]),
            "entity_ids": info["entity_ids"], "sides": info["sides"], "fields": info["fields"],
        })

    # ── 诚实边界：梯级基准本身有没有出处？ ──────────────────────────────────
    ladder_has_source = bool(
        isinstance(mech.get("canonical_ladder_iso_9409_1"), dict)
        or any(k in str(mech.get("canonical_ladder_iso_9409_1")) for k in ("source",))
    )
    ladder_provenance = {
        "ladder_block_type": type(mech.get("canonical_ladder_iso_9409_1")).__name__,
        "has_independent_citation": False,
        "note": (
            "canonical_ladder_iso_9409_1 是裸数组，无 source / source_tier 字段。"
            "本层的全部期望值都压在这个未引用基准上，因此它只能作为内部一致性闸门与"
            "判定补位，不构成独立外部权威；confidence 上限继承登记表 tier=B。"
        ),
    }
    if ladder_has_source:
        ladder_provenance["has_independent_citation"] = True

    n_match = sum(1 for x in derivations if x["classification"] == "matches_canonical")
    n_dev = sum(1 for x in derivations if x["classification"].startswith("deviates"))
    n_norun = sum(1 for x in derivations if x["classification"] == "no_standard_rung")
    judged = sum(1 for t in token_verdicts if t["verdict"] != "unparseable_bare_standard")

    # residual 汇总：所有 deviation / off-ladder 标号的转接盘最小几何修正量分布
    _residuals = [x.get("residual") for x in derivations if x.get("residual")]
    _hole_deltas = sorted({abs(r.get("bolt_count_delta", 0)) for r in _residuals
                           if isinstance(r.get("bolt_count_delta"), (int, float))})
    _thread_delta_count = sum(1 for r in _residuals if r.get("thread_delta"))
    _has_outer = sum(1 for r in _residuals if r.get("iso_outer_diameter_delta_mm") is not None)
    _dim_dist = {}
    for r in _residuals:
        key = "+".join(sorted(r.get("min_correction_dims") or ["none"])) or "none"
        _dim_dist[key] = _dim_dist.get(key, 0) + 1

    return {
        "meta": {
            "schema": "derived_features/v1",
            "name": "RoboParts 应有特征推导层 (Predicted-Feature Index)",
            "description": (
                "不采集数据，只推导：给一个 ISO 9409-1 标号，它按标准梯级应当有什么孔数、"
                "什么螺纹、什么外径。于是已登记标号可与手写标签交叉验证，有标号但无规范行的"
                "声明也能给出「应当如何」而不是 unknown，手写 note 里的偏离断言可被机械复算。"
                "deviation / off-ladder 的 residual 字段量化「转接盘的最小几何修正量」"
                "（PPS 哲学：冻结 base 不动，只量化差异），工程师拿到本表即可直接算出所需转接盘参数。"
            ),
            "methodology": {
                "isomorphism": (
                    "问题结构与 Cornell MS2KOSMOS (bioRxiv 2026.08) 同构：它不检索原始谱图，"
                    "而是先对已知小分子结构预计算出应有的观测谱图（8 亿+ 预测谱）再入库，"
                    "使未测过的观测也能被比对。本层对法兰做同一件事：先按梯级预计算应有几何，"
                    "再拿声明值来比。"
                ),
                "why_it_matters": (
                    "只做「收集厂商声明」时，声明率就是判定天花板——厂商不写就无从判断。"
                    "加一层「按标准应当如何」的推导，未声明/无规范行的标号也能被判定，"
                    "天花板从「厂商愿意写多少」抬到「标准定义了多少」。"
                ),
                "does_not_do": [
                    "不向 flange_designations 发明任何标准条目（L1.77：未读到 ISO 9409-1:2004 原文即不替标准发明条目）",
                    "不把 A{n} 的 n 当 ISO 外径读（行业 de-facto 中 n=PCD）",
                    "不裁决两种书写形式所指的法兰可否互装（查表与裁决分离，见 grammar.designation_forms.join_scope）",
                ],
            },
            "truth_source": (
                "由 scripts/build_derived_features.py 从 api/mechanical_interfaces.json + "
                "api/entities.json 现算生成，禁止手改"
            ),
            "derivation_rule": {
                "lookup": "以 d1_mm 为键查 canonical_ladder_iso_9409_1 得应有 (holes, thread, iso_outer_diameter)",
                "matches_canonical": "实测孔数与螺纹同时等于梯级期望",
                "deviates_thread_only": "孔数相同、仅螺纹不同",
                "deviates_holes_and_thread": "孔数不同（螺纹可能同时不同）",
                "no_standard_rung": "该 PCD 不在标准梯级上，给出最近 2 档供转接与选型",
            },
            "counts": {
                "ladder_rungs": len(ladder),
                "registry_designations": len(rows),
                "matches_canonical": n_match,
                "deviations": n_dev,
                "no_standard_rung": n_norun,
                "entity_tokens_in_use": len(token_verdicts),
                "entity_tokens_judged_by_derivation": judged,
                "entities_covered_by_judged_tokens": sum(
                    len(t["entity_ids"]) for t in token_verdicts
                    if t["verdict"] != "unparseable_bare_standard"),
                "undecidable_tokens": sum(
                    1 for t in token_verdicts if t["verdict"] == "unparseable_bare_standard"),
                # residual 分布：量化「转接盘最小几何修正量」的样本面
                "residual_entries": len(_residuals),
                "residual_with_thread_delta": _thread_delta_count,
                "residual_with_outer_delta_declared": _has_outer,
                "hole_delta_magnitudes_seen": _hole_deltas,
            },
            "adapter_residual_index": {
                "why_it_exists": (
                    "PPS 哲学落地：base（ISO 9409-1 梯级）冻结不动，只量化厂商声明与梯级的"
                    "差异向量——这就是「转接盘的最小几何修正量」。工程师拿到本表可直接算出"
                    "所需转接盘参数（孔数修正 / 螺纹规格 / 外径补偿），不必再回查 ISO 原文。"
                ),
                "reference": "arXiv:2609.09148 (Proxy Policy Steering) — v_pps = v_base + γ·(v_task − v_ref)",
                "dim_distributions": _dim_dist,
                "residual_scope_note": (
                    "residual 只描述几何差，不裁决「能否互装」。互装判断仍走 build_negative_compat.py"
                    "（本层与判定层分离，与 grammar.designation_forms.join_scope 的查表/裁决分离同构）。"
                ),
            },
            "cross_validation": {
                "is_canonical_iso_reproduced": {
                    "agreement": f"{agree_flag}/{agree_flag + disagree_flag}"
                    if agree_flag >= 0 else "not_applicable",
                    "disagreements": disagree_flag,
                    "meaning": (
                        "推导层独立复现登记表手写的 is_canonical_iso 标签。这是**内部一致性**校验："
                        "两个独立写法对同一事实下结论，不一致即登记数据有错。"
                    ),
                },
                "handwritten_note_recomputed": {
                    "notes_with_assertion": notes_with_assertion,
                    "machine_checkable": note_recomp,
                    "agrees": note_agree,
                    "unparseable": note_unparseable,
                    "meaning": (
                        "note 里「偏离 ISO 标准梯级为 N×Mk」「最近为 PCDx」这类断言可被机械复算，"
                        "不必相信人写的话。不可解析的断言计为 unparseable 而非通过，避免假绿。"
                    ),
                },
            },
            "freshness": {
                "basis": "锚定源内容哈希而非部署时间：内容不变则本层不变（幂等），内容一变本层必变。",
                "mechanical_interfaces_sha256": sha256_of(SRC_MECH)[:16],
                "entities_sha256": sha256_of(SRC_ENT)[:16],
            },
            "ladder_provenance": ladder_provenance,
            "honest_limits": {
                "derivation_confidence_cap": "B",
                "not_an_independent_authority": (
                    "期望值与 is_canonical_iso 标签最终压在同一份未引用梯级上，"
                    "所以本层能证「内部自洽」，不能证「符合 ISO 原文」。"
                ),
                "third_party_input_risk": (
                    "抓取第三方厂商规格表属不可信输入，进 agent 上下文存在提示注入风险。"
                    "本层只消费仓库内已核验落地的 JSON，不直连任何外部页面。"
                ),
                "agpl_boundary": (
                    "方法学参考 Shannon (KeygraphHQ/shannon, AGPL-3.0) 的「无漏洞利用，不报告」原则："
                    "只报告可复现的结论。AGPL 具网络传染性，仅借鉴原则，未复制任何代码。"
                ),
            },
            "source_tier_summary": {
                t: sum(1 for x in derivations if x["registry_source_tier"] == t)
                for t in sorted({x["registry_source_tier"] for x in derivations})
            },
            "access": load_access_block(),
        },
        "expectation_index": expectation_index,
        "designation_derivations": derivations,
        "entity_token_verdicts": token_verdicts,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--dry-run", action="store_true", help="只打印统计，不落盘")
    args = ap.parse_args()

    doc = build()
    m = doc["meta"]
    c = m["counts"]
    print(
        f"[derived_features] ladder={c['ladder_rungs']} rungs · designations={c['registry_designations']} "
        f"(canonical={c['matches_canonical']} deviates={c['deviations']} off-ladder={c['no_standard_rung']})"
    )
    cv = m["cross_validation"]
    print(
        f"  cross-validate: is_canonical_iso 复现 {cv['is_canonical_iso_reproduced']['agreement']}"
        f"（分歧 {cv['is_canonical_iso_reproduced']['disagreements']}）"
        f" · note 可复算 {cv['handwritten_note_recomputed']['agrees']}"
        f"/{cv['handwritten_note_recomputed']['machine_checkable']} 一致"
        f"（含断言 {cv['handwritten_note_recomputed']['notes_with_assertion']}，"
        f"不可解析 {cv['handwritten_note_recomputed']['unparseable']}）"
    )
    print(
        f"  entity tokens: {c['entity_tokens_in_use']} in use, {c['entity_tokens_judged_by_derivation']} "
        f"judged by derivation, {c['undecidable_tokens']} undecidable "
        f"(覆盖 {c['entities_covered_by_judged_tokens']} 实体)"
    )
    if args.dry_run:
        print("dry-run: 未写盘")
        return 0
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"written -> {os.path.relpath(args.out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
