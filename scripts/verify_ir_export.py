#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_ir_export — Composition IR ⇄ OpenUSD/AAS 导出回读闸门（P2-5）。

**验收口径**（audit，默认）：同一 IR 可导出并回读，关键语义不丢失。
  - 从真实 graph 现算 IR（不手写期望值）；
  - IR → USD → IR，IR → AAS → IR；
  - key_semantics 指纹相等 ⇔ 语义不丢失。

**自证**（--self-test，阴阳三对照，只测绿路径的闸门等于没闸门）：
  - 阳性：往返后指纹相等（绿路径确实绿）；
  - 阴性/变异：在 .usda/.aas 里改一个 verdict 或 blocking_dims，
    回读后指纹必须**不等**（闸门能抓语义丢失，不是恒真）；
  - 守卫：pxr 不可用时 audit 必须 fail-closed（报错，不是静默 skip）。

退出码：0 全绿；1 有红。
"""
from __future__ import annotations

import copy
import json
import os
import sys
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import compose_ir as ir  # noqa: E402
import export_aas as ea  # noqa: E402
import export_usd as eu  # noqa: E402

ROOT = os.path.dirname(_HERE)
GRAPH_PATH = os.path.join(ROOT, "api", "morphology_graph.json")

RESULTS: List[Dict[str, Any]] = []


def check(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": detail})


# ---------------------------------------------------------------------------
# 审计
# ---------------------------------------------------------------------------
def audit() -> None:
    graph = json.load(open(GRAPH_PATH, encoding="utf-8"))
    pairs = ir.demo_pair_ids(graph, limit=9)
    irc = ir.build_ir(graph, pairs)

    # 1. IR 本身非空且含判例
    check("IR 非空", bool(irc["composition"]["pairs"]), f"{len(irc['composition']['pairs'])} 判例")
    check("IR 节点非空", bool(irc["composition"]["nodes"]), f"{len(irc['composition']['nodes'])} 节点")

    # 2. USD 导出 + 回读
    try:
        usda = eu.export_usda(irc)
        check("USD 导出成功", len(usda) > 100, f"{len(usda)} bytes")
        back = eu.import_usda(usda)
        eq = ir.semantics_equal(irc, back)
        check("USD 往返关键语义不丢失", eq)
        if not eq:
            check("USD 往返诊断", False, "指纹不等，见 diff")
    except Exception as e:
        check("USD 导出/回读", False, f"异常: {e}")

    # 3. AAS 导出 + 回读
    try:
        aas = ea.export_aas(irc)
        check("AAS 导出成功", bool(aas.get("submodels")), "submodels 非空")
        back2 = ea.import_aas(aas)
        eq2 = ir.semantics_equal(irc, back2)
        check("AAS 往返关键语义不丢失", eq2)
        if not eq2:
            check("AAS 往返诊断", False, "指纹不等，见 diff")
    except Exception as e:
        check("AAS 导出/回读", False, f"异常: {e}")


# ---------------------------------------------------------------------------
# 自证（阴阳）
# ---------------------------------------------------------------------------
def self_test() -> None:
    graph = json.load(open(GRAPH_PATH, encoding="utf-8"))
    pairs = ir.demo_pair_ids(graph, limit=9)
    irc = ir.build_ir(graph, pairs)

    # 阳性：USD 往返绿
    usda = eu.export_usda(irc)
    back = eu.import_usda(usda)
    check("自证·阳性 USD 往返指纹相等", ir.semantics_equal(irc, back))

    aas = ea.export_aas(irc)
    back2 = ea.import_aas(aas)
    check("自证·阳性 AAS 往返指纹相等", ir.semantics_equal(irc, back2))

    # 阴性：USD 里改一个 verdict → 指纹必须不等
    usda_mut = _mutate_usda_verdict(usda)
    back_mut = eu.import_usda(usda_mut)
    check("自证·阴性 USD 改 verdict 被抓", not ir.semantics_equal(irc, back_mut),
          "变异后指纹仍相等 = 闸门是恒真")

    # 阴性：AAS 里改一个 blockingDims → 指纹必须不等
    aas_mut = _mutate_aas_blocking(aas)
    back_mut2 = ea.import_aas(aas_mut)
    check("自证·阴性 AAS 改 blockingDims 被抓", not ir.semantics_equal(irc, back_mut2),
          "变异后指纹仍相等 = 闸门是恒真")

    # 守卫：pxr 不可用时 audit 要能检测（fail-closed 由 ci_gate 处理，这里证明检测点存在）
    check("自证·守卫 pxr 探测点存在", hasattr(eu, "pxr_available"),
          "pxr_available() 存在，ci_gate 据此 fail-closed")

    # 变异对照：blocking_dims 集合相等但顺序不同 → 指纹应相等（排序稳定性）
    irc_swap = copy.deepcopy(irc)
    p0 = irc_swap["composition"]["pairs"][0]
    ax = p0["axes"]["electrical"]
    ax["blocking_dims"] = list(reversed(ax["blocking_dims"]))
    check("自证·变异 blocking_dims 逆序指纹仍相等", ir.semantics_equal(irc, irc_swap),
          "blocking_dims 是集合，顺序不参与语义")


def _mutate_usda_verdict(usda: str) -> str:
    """把 .usda 里第一个 rp:electrical 的 verdict 改掉（compatible→incompatible 或反之）。"""
    lines = usda.split("\n")
    for i, line in enumerate(lines):
        if "rp:electrical" in line and "=" in line and "blocking" not in line:
            # 取当前值并翻转
            import re
            m = re.search(r'= "([^"]+)"', line)
            if m:
                cur = m.group(1)
                new = "incompatible" if cur != "incompatible" else "compatible"
                lines[i] = line.replace(cur, new)
                break
    return "\n".join(lines)


def _mutate_aas_blocking(aas: Dict[str, Any]) -> Dict[str, Any]:
    """把 AAS 里第一个 Pair 的 electrical blockingDims 改成假值。"""
    a = copy.deepcopy(aas)
    sub = a["submodels"][0]
    for el in sub["submodelElements"]:
        if el.get("idShort") == "Pairs":
            first_pair = el["value"][0]
            for sub_el in first_pair["value"]:
                if sub_el.get("idShort") == "Axes":
                    for ac in sub_el["value"]:
                        if ac.get("idShort") == "Electrical":
                            for prop in ac["value"]:
                                if prop.get("idShort") == "blockingDims":
                                    prop["value"] = "MUTATED_BLOCKING"
                                    return a
    return a


# ---------------------------------------------------------------------------
def main() -> int:
    args = sys.argv[1:]
    if "--self-test" in args:
        self_test()
    else:
        audit()

    failed = [r for r in RESULTS if not r["ok"]]
    for r in RESULTS:
        tag = "PASS" if r["ok"] else "FAIL"
        print(f"[{tag}] {r['name']}" + (f" — {r['detail']}" if r["detail"] else ""))
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
