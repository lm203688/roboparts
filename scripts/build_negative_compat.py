#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_negative_compat.py — 负面兼容裁决库生成器（唯一真相源）

【为什么要有这个文件】
借鉴灵初智能 PsiBot 的 Psi-W0：Psi-R2 只学"成功操作"，无法预测"苹果滑落"
这类失败场景，于是专门建一个含 30% 失败样本的世界模型来做反事实推理。
RoboParts 的兼容性引擎存在完全对称的缺陷：**只裁决"能配"，没有"配不上"的知识**。
对 AI Agent 而言，负面知识与正面知识同等重要——没有负面裁决，Agent 只能靠
猜测，会把 PCD 80 和 PCD 100 硬说成"可能兼容"。

【为什么是零成本】
负面裁决不需要新采集任何数据：法兰对接的硬约束是纯几何的，
从 api/mechanical_interfaces.json 的 flange_designations 现算即可穷举。

【裁决规则（机械硬约束）】
两片法兰能否直接对接，取决于三个量是否同时对齐：
  1. 节圆直径 PCD（pcd_mm）—— 不对齐，螺栓孔在圆周上对不上
  2. 孔数 bolt_count       —— 不对齐，必然有孔落空
  3. 螺纹 thread           —— 不对齐仍可装（换对应规格螺栓），只要螺栓能过孔
故：
  - PCD 相同 且 孔数相同            → direct（直接可装，可能需换螺栓）
  - PCD 不同 或 孔数不同            → adapter_required（必须转接盘）
  - 自身配对                        → identity

【纪律】
- 幂等：重复运行产出字节一致（排序固定、不写时间戳）
- 不写死：所有几何值现取自 mechanical_interfaces.json
- 只读输入，只写 api/negative_compat.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from itertools import combinations
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "api", "mechanical_interfaces.json")
OUT = os.path.join(ROOT, "api", "negative_compat.json")
# meta.access 模板源：不硬编码，避免与站点其他 JSON 的领 key 入口漂移
ACCESS_TEMPLATE_SRC = os.path.join(ROOT, "api", "platforms.json")

# gen_adapter.py 中已建预设、可直接生成转接盘的标号（adapter-generator.html 同步）
# 偏离尺寸的销孔几何未知 → pins=0，仍可生成，只是无定位销
ADAPTER_PRESET_LABELS = {
    "ISO9409-1-A20-4-M3",
    "ISO9409-1-A31.5-4-M5",
    "ISO9409-1-A40-4-M6",
    "ISO9409-1-A50-4-M6",
    "ISO9409-1-A63-6-M6",
    "ISO9409-1-A80-6-M8",
    "ISO9409-1-A100-4-M8",
    "ISO9409-1-A160-4-M12",
    "ISO9409-1-A250-4-M16",
}


def load_designations(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    items = doc.get("flange_designations") or []
    out = []
    for it in items:
        pcd = it.get("d1_mm")
        holes = it.get("bolt_count")
        thread = it.get("thread")
        if pcd is None or holes is None or not thread:
            continue  # 几何不全的条目不参与裁决，宁缺勿假
        out.append(
            {
                "id": it["id"],
                "pcd_mm": float(pcd),
                "bolt_count": int(holes),
                "thread": thread,
                "is_canonical_iso": bool(it.get("is_canonical_iso")),
                "source_tier": it.get("source_tier", "C"),
                "confidence": it.get("confidence"),
            }
        )
    # 固定排序，保证幂等
    out.sort(key=lambda x: (x["pcd_mm"], x["bolt_count"], x["id"]))
    return out


def judge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """对一对法兰做机械裁决。返回裁决字典。"""
    same_pcd = abs(a["pcd_mm"] - b["pcd_mm"]) < 1e-9
    same_holes = a["bolt_count"] == b["bolt_count"]
    same_thread = a["thread"].upper() == b["thread"].upper()

    if a["id"] == b["id"]:
        return {
            "verdict": "identity",
            "reason": "同一标号，自配对，必然可装",
            "adapter_required": False,
            "adapter_available": False,
            "fastener_note": None,
            "blocking_dims": [],
        }

    if same_pcd and same_holes:
        note = None
        if not same_thread:
            # 螺栓降级/升级：只要螺栓能穿过孔即可，标称直径取小者
            da = thread_nominal(a["thread"])
            db = thread_nominal(b["thread"])
            if da is not None and db is not None:
                smaller = a["thread"] if da <= db else b["thread"]
                note = (
                    f"PCD 与孔数一致，螺纹不同（{a['thread']} vs {b['thread']}）："
                    f"可用 {smaller} 螺栓直接紧固，无需转接盘"
                )
            else:
                note = f"螺纹规格不同（{a['thread']} vs {b['thread']}），需按较小标称选配螺栓"
        return {
            "verdict": "direct",
            "reason": "节圆直径与螺栓孔数一致，可直接对接",
            "adapter_required": False,
            "adapter_available": False,
            "fastener_note": note,
            "blocking_dims": [],
        }

    blocking = []
    if not same_pcd:
        blocking.append("pcd_mm")
    if not same_holes:
        blocking.append("bolt_count")

    reason_parts = []
    if not same_pcd:
        reason_parts.append(f"节圆直径不同（{a['pcd_mm']:g}mm vs {b['pcd_mm']:g}mm）")
    if not same_holes:
        reason_parts.append(f"螺栓孔数不同（{a['bolt_count']} vs {b['bolt_count']}）")

    adapter_available = a["id"] in ADAPTER_PRESET_LABELS and b["id"] in ADAPTER_PRESET_LABELS

    return {
        "verdict": "adapter_required",
        "reason": "；".join(reason_parts) + "，螺栓孔无法对齐，必须经转接盘",
        "adapter_required": True,
        "adapter_available": adapter_available,
        "fastener_note": (
            "转接盘两侧分别按各自 PCD/孔数/螺纹开孔"
            if adapter_available
            else "该组合超出已建转接盘预设，需定制"
        ),
        "blocking_dims": blocking,
    }


def thread_nominal(thread: str) -> Optional[float]:
    """从 'M8' / 'M10' 提取标称直径。解析不出返回 None（不猜）。"""
    t = (thread or "").strip().upper()
    if not t.startswith("M"):
        return None
    try:
        return float(t[1:])
    except ValueError:
        return None


def load_access_block() -> Dict[str, Any]:
    """取站点标准的『AI 领 key 入口』块。

    纪律：谁重写对外 JSON，谁负责补回 meta.access（否则会抹掉 AI 领 key 入口，
    回归 L1.x 会拦）。这里不从本文件硬编码，而是从 platforms.json 现取，
    保证站点各处领 key 文案永远一致、不会各自漂移。
    """
    with open(ACCESS_TEMPLATE_SRC, "r", encoding="utf-8") as f:
        doc = json.load(f)
    access = doc.get("meta", {}).get("access")
    if not access:
        raise SystemExit(f"{ACCESS_TEMPLATE_SRC} 缺少 meta.access，无法作为模板")
    # 深拷贝，避免改动污染模板对象
    out = json.loads(json.dumps(access))
    # 本文件自己的诚实边界（覆盖模板里的全站口径）
    hl = out.get("honest_limits") or {}
    hl["negative_compat_scope"] = (
        "本裁决库只覆盖已登记的 ISO 9409-1 法兰标号之间的几何组合，"
        "不等于穷举市场现存的法兰；未登记标号查询应返回 unknown，禁止按标号字面猜测。"
    )
    out["honest_limits"] = hl
    return out


def build(src_path: str) -> Dict[str, Any]:
    designations = load_designations(src_path)
    if len(designations) < 2:
        raise SystemExit(f"mechanical_interfaces.json 中可用的法兰标号不足 2 条（{len(designations)}），拒绝产出")

    rulings: List[Dict[str, Any]] = []
    for a, b in combinations(designations, 2):
        r = judge(a, b)
        rulings.append(
            {
                "pair": [a["id"], b["id"]],
                "side_a": {"pcd_mm": a["pcd_mm"], "bolt_count": a["bolt_count"], "thread": a["thread"]},
                "side_b": {"pcd_mm": b["pcd_mm"], "bolt_count": b["bolt_count"], "thread": b["thread"]},
                **r,
            }
        )
        # 反向对也生成，方便 Agent 按任意顺序查询
        rulings.append(
            {
                "pair": [b["id"], a["id"]],
                "side_a": {"pcd_mm": b["pcd_mm"], "bolt_count": b["bolt_count"], "thread": b["thread"]},
                "side_b": {"pcd_mm": a["pcd_mm"], "bolt_count": a["bolt_count"], "thread": a["thread"]},
                **r,
            }
        )

    # identity 自身配对（Agent 查同标号时也要有确定答案，而不是 NOT_FOUND）
    for a in designations:
        r = judge(a, a)
        rulings.append(
            {
                "pair": [a["id"], a["id"]],
                "side_a": {"pcd_mm": a["pcd_mm"], "bolt_count": a["bolt_count"], "thread": a["thread"]},
                "side_b": {"pcd_mm": a["pcd_mm"], "bolt_count": a["bolt_count"], "thread": a["thread"]},
                **r,
            }
        )

    rulings.sort(key=lambda x: (x["pair"][0], x["pair"][1]))

    n_direct = sum(1 for r in rulings if r["verdict"] == "direct")
    n_adapter = sum(1 for r in rulings if r["verdict"] == "adapter_required")
    n_identity = sum(1 for r in rulings if r["verdict"] == "identity")

    return {
        "meta": {
            "schema": "negative_compat/v1",
            "description": (
                "法兰对接的负面/条件裁决库。正面知识（哪些能配）回答不了的问题在这里："
                "哪些配不上、为什么配不上、有没有解药。借鉴 PsiBot Psi-W0 的失败样本思路——"
                "只学成功操作的模型无法预测失败，只给正面裁决的目录同样无法阻止 Agent 幻觉式推荐。"
            ),
            "truth_source": "由 scripts/build_negative_compat.py 从 api/mechanical_interfaces.json 现算生成，禁止手改",
            "geometry_basis": (
                "法兰对接硬约束：节圆直径 PCD 与螺栓孔数必须同时对齐；"
                "螺纹不同不阻塞（换对应规格螺栓即可）。故 PCD 或孔数任一不同即判 adapter_required。"
            ),
            "designation_naming_warning": (
                "ISO 9409-1 的 A{n} 在机器人行业 de-facto 指节圆直径 PCD，而非 ISO 外径 D。"
                "同一 A 标号在不同厂商可能对应不同几何（如 A100 既可能 6×M10 标准，也可能 KUKA 4×M8），"
                "裁决一律以本文件的 pcd_mm / bolt_count 实测值为准，不认标号字面。"
            ),
            "counts": {
                "designations": len(designations),
                "rulings": len(rulings),
                "identity": n_identity,
                "direct": n_direct,
                "adapter_required": n_adapter,
            },
            "coverage_note": (
                "本库穷举的是「已登记标号的几何组合」，不等于穷举市场现存的法兰。"
                "未登记标号查询应返回 unknown，禁止回退到标号字面猜测。"
            ),
            "source_tier_summary": {
                t: sum(1 for d in designations if d["source_tier"] == t)
                for t in sorted({d["source_tier"] for d in designations})
            },
            "access": load_access_block(),
        },
        "rulings": rulings,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--dry-run", action="store_true", help="只打印将要写入的统计，不落盘")
    args = ap.parse_args()

    doc = build(args.src)
    m = doc["meta"]["counts"]
    print(
        f"[negative_compat] designations={m['designations']} rulings={m['rulings']} "
        f"(identity={m['identity']} direct={m['direct']} adapter_required={m['adapter_required']})"
    )
    if args.dry_run:
        print("dry-run: 未写盘")
        return 0

    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"written -> {os.path.relpath(args.out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
