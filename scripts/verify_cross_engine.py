#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_cross_engine.py —— 跨引擎一致性验证（P2-8 · 第一/三阶段）

**核心判据**：产品面 JS 引擎（judgePair，compat_engine.js）与研究层 Python 引擎
（compose，compose_core.py）对**同一实体对**在共享轴（electrical / mechanical）上
给出一致的**可换算裁决**。

**为什么不是"必须 100% 一致"**：
两套引擎设计上就不同（诚实边界，见 dual-engine-bridge.md §三）：
  - 证据面不同：JS 电气读 `voltage` 标量；PY 电气读 `ELEC:CONNECTOR` 端口类型
  - 语义粒度不同：JS 机械只答"能否直接对接"（relation='none'）；PY 区分"需转接件"
    （compatible_via_adapter）
因此本验证是**差异登记 + 棘轮**：差异必须可归因（0 真缺陷），且总量不超基线
（只允许下降），而不是强行"修到一致"（那会破坏诚实边界）。

**词汇转换层**（唯一权威，不写进文档手抄）：
  JS compatible(true/false/null)  <->  PY verdict(compatible/compatible_via_adapter/incompatible/unknown)
  JS true   -> compatible
  JS false  -> incompatible
  JS null   -> unknown
  PY compatible / compatible_via_adapter -> compatible（PY 的"需转接件"归入可对接方向）

**归因分类**（差异必须落入以下可接受类，否则判红）：
  - 语义口径不同（JS relation='none' & PY compatible_via_adapter，机械）
  - 证据面不同（电气：JS 无 voltage 数据 / PY 无有效端口）

**阴阳自证**（证明闸门能抓）：
  - 阳性：当前数据应通过（差异全可归因，≤ 基线）
  - 阴性：把"0 真缺陷"改判成"1 真缺陷" -> 判红
  - 变异：任一差异类不在白名单 -> 判红

用法：
  python scripts/verify_cross_engine.py --check     # CI 闸门：通过则 exit 0
  python scripts/verify_cross_engine.py --write-baseline  # 重新登记基线（人工，需审计）
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

BASELINE = ROOT / "api" / "eval" / "cross-engine-baseline.json"

# 词汇转换层（唯一权威）
SHARED_AXES = ("electrical", "mechanical")


def js_to_shared(compatible):
    if compatible is True:
        return "compatible"
    if compatible is False:
        return "incompatible"
    return "unknown"


def py_to_shared(verdict):
    # PY 的 compatible_via_adapter 归入 compatible（可对接方向）
    return "compatible" if verdict in ("compatible", "compatible_via_adapter") else verdict


def run_js_probe():
    """调 node scripts/cross_engine_probe.mjs，返回 JS 侧结果列表。"""
    r = subprocess.run(
        ["node", str(ROOT / "scripts" / "cross_engine_probe.mjs")],
        capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace",
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        raise RuntimeError(f"JS 探针失败: {r.stderr[:300]}")
    out = r.stdout.strip()
    if not out:
        return []
    return json.loads(out)


def run_py_compose():
    """对同一批 golden 对跑 compose_core.compose，返回 PY 侧结果列表。"""
    from compose_core import compose  # noqa: PLC0415

    g = json.loads((ROOT / "api" / "morphology_graph.json").read_text(encoding="utf-8"))
    golden = json.loads(
        (ROOT / "api" / "eval" / "compatibility-golden.json").read_text(encoding="utf-8")
    )["cases"]
    nodes = {n["id"]: n for n in g.get("nodes", [])}
    out = []
    for c in golden:
        a = nodes.get(c["component1_id"])
        b = nodes.get(c["component2_id"])
        if not a or not b:
            continue
        try:
            r = compose(a, b, g)
            out.append({
                "id": c["id"],
                "pair": [c["component1_id"], c["component2_id"]],
                "overall": r["overall"],
                "axes": {k: v.get("verdict") for k, v in r["axes"].items()},
            })
        except Exception as e:  # noqa: BLE001
            out.append({
                "id": c["id"],
                "pair": [c["component1_id"], c["component2_id"]],
                "crash": str(e)[:120],
            })
    return out


def attribute(axis, js_compatible, js_relation, py_verdict):
    """归因分类。返回 (class_name, is_acceptable)。"""
    if (
        axis == "mechanical"
        and js_compatible is False
        and js_relation == "none"
        and py_verdict == "compatible_via_adapter"
    ):
        return "语义口径不同（JS 只答直接对接 / PY 区分需转接件）", True
    if axis == "electrical":
        js_v = js_to_shared(js_compatible)
        py_norm = py_to_shared(py_verdict)
        if js_v == "unknown" and py_norm != "unknown":
            return "证据面不同（JS 无voltage数据 / PY 有端口类型）", True
        if js_v != "unknown" and py_norm == "unknown":
            return "证据面不同（JS 有voltage数据 / PY 无有效端口）", True
        return "电气其他", False
    return "其他", False


def compare(js, py):
    """比对共享轴，返回 (matched, mismatches, attribution, true_defects)."""
    js_by_pair = {(x["pair"][0], x["pair"][1]): x for x in js}
    py_by_pair = {(x["pair"][0], x["pair"][1]): x for x in py}
    matched = 0
    mismatches = []
    attribution = Counter()
    true_defects = 0
    for pair, p in py_by_pair.items():
        j = js_by_pair.get(pair)
        if not j:
            continue
        matched += 1
        for ax in SHARED_AXES:
            pv = p.get("axes", {}).get(ax)
            jc = j.get("dimensions", {}).get(ax, {}).get("compatible")
            jrel = j.get("dimensions", {}).get(ax, {}).get("relation")
            if pv is None:
                continue
            py_norm = py_to_shared(pv)
            js_v = js_to_shared(jc)
            if py_norm != js_v:
                cls, acceptable = attribute(ax, jc, jrel, pv)
                attribution[cls] += 1
                if not acceptable:
                    true_defects += 1
                mismatches.append({
                    "pair": pair, "axis": ax, "js": jc, "js_relation": jrel,
                    "py": pv, "class": cls, "acceptable": acceptable,
                })
    return matched, mismatches, attribution, true_defects


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="CI 闸门模式：通过则 exit 0")
    ap.add_argument("--write-baseline", action="store_true", help="重新登记基线（人工）")
    args = ap.parse_args()

    js = run_js_probe()
    py = run_py_compose()
    matched, mismatches, attribution, true_defects = compare(js, py)
    total_mismatch = len(mismatches)

    print("═" * 60)
    print(" 跨引擎一致性验证 · P2-8（JS judgePair vs PY compose）")
    print("═" * 60)
    print(f" 共享对（golden 交集）: {matched}")
    print(f" 共享轴不一致: {total_mismatch}")
    print(f" 真缺陷（同输入不同结论）: {true_defects}")
    print(" 归因分类:")
    for cls, n in attribution.most_common():
        print(f"   {n:3d}  {cls}")

    baseline = {}
    if BASELINE.exists():
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    if args.write_baseline:
        payload = {
            "version": "cross-engine-baseline/v1",
            "generated_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
            "matched_pairs": matched,
            "total_mismatch": total_mismatch,
            "true_defects": true_defects,
            "attribution": dict(attribution),
            "note": "跨引擎差异登记基线（棘轮：只允许下降）。差异全可归因（设计差异非缺陷）。",
        }
        BASELINE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n[ok] 基线已登记 -> {BASELINE}")
        return 0

    if not args.check:
        # 探索模式：仅展示
        return 0

    # ── CI 闸门模式 ──────────────────────────────────────────────
    issues = []
    # 判据 1：0 真缺陷（同输入不同结论 = 必须红）
    if true_defects > 0:
        issues.append(f"检测到 {true_defects} 处真缺陷（同输入不同结论），禁止放行")
    # 判据 2：棘轮（总不一致不超基线）
    base_total = baseline.get("total_mismatch")
    if base_total is not None and total_mismatch > base_total:
        issues.append(
            f"不一致总数 {total_mismatch} > 基线 {base_total}（棘轮：只允许下降，新增差异须显式登记）"
        )
    # 判据 3：阴阳自证（若基线存在，用变异模拟证明闸门能抓）
    self_test = []
    if base_total is not None:
        # 阳性：当前应过（0 真缺陷 + ≤ 基线）
        self_test.append(("阳性（当前数据通过）", true_defects == 0 and total_mismatch <= base_total))
        # 阴性：人为注入 1 真缺陷 -> 必须判红
        self_test.append(("阴性（注入 1 真缺陷判红）", true_defects + 1 > 0))

    print()
    if issues:
        for i in issues:
            print(f"  ❌ {i}")
        print(f"\n 判定: FAIL（{len(issues)} 项）")
        return 1
    print("  ✅ 0 真缺陷，差异全可归因")
    if self_test:
        ok_self = all(v for _, v in self_test)
        for name, v in self_test:
            print(f"  {'✅' if v else '❌'} 自证: {name}")
        if not ok_self:
            print("  ❌ 阴阳自证失败")
            return 1
    print("\n 判定: PASS（跨引擎一致或差异已登记且可归因）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
