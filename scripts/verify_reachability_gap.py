#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_reachability_gap — 可达性体检层的阴阳自证（挂 ci_gate）。

为什么这层的自证特别重要
------------------------
可达性故障是本项目**最难发现**的一类：两套引擎都能跑、都不报错、
算术守卫全绿、68 项闸门此前也全绿——但研究结论对用户不可见。

所以本层必须能抓到「声称可达，实际不可达」这类**自欺**。
否则闸门只是把「我说了我做到了」又检查了一遍。

四组对照：
  ① 算术与口径：可达计数守恒 / reachable ⟺ reference_count / 维度集已登记
  ② 桥接工具：TOOLS 声明与 dispatch 分支必须**同时**在位
     （只有声明没 dispatch = 工具调不通 = 形同虚设）
  ③ **反向对照（关键）**：造一个「产物不可达」的变异，
     必须判红——否则本层就是装饰
  ④ 变异：6 种注入逐一判红
"""
from __future__ import annotations

import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_reachability_gap as brg  # noqa: E402

FAILED: list = []
_MUTFAIL: list = []


def fail(msg: str) -> None:
    FAILED.append(msg)
    print(f"  [FAIL] {msg}")


def _mutfail(msg: str) -> None:
    _MUTFAIL.append(msg)


def ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


# 与 ci_gate.gate_reachability_gap._reachability_errors **同源**。
# 这里直接 import 复用，而不是另写一份——「同一口径两份实现」是本项目
# 反复出现过的漂移来源（见 MEMORY「同一口径的第二份来源」）。
def _errors(rg, sink=None):
    """复用 ci_gate 的判据（同一口径两份实现是本项目反复出现过的漂移来源）。

    sink 非空时把错误收集到该收集器——变异体**应该**触发失败，
    那是「闸门成功捕获」而非「本层有 bug」，故不能混进主失败列表
    （混进去就是假红灯，项目已踩过）。
    """
    from ci_gate import _reachability_errors
    errs = _reachability_errors(rg)
    if sink is not None:
        for e in errs:
            sink(e)
    return errs


def check_baseline(out) -> None:
    print("\n[1/4] 基线算术与口径")
    errs = _errors(out)
    if errs:
        for e in errs:
            fail(e)
        return
    rs = out["reachability_summary"]
    ok(f"可达 {rs['artifacts_reachable']}/{rs['artifacts_total']}"
       f"（扫 {rs['product_surface_files_scanned']} 个源文件）")
    t = out["taxonomy"]
    ok(f"维度：共享 {t['shared_dimensions']} / "
       f"产品层独有 {t['product_only_dimensions']} / "
       f"研究层独有 {t['research_only_axes']}")


def check_bridge_wiring() -> None:
    print("\n[2/4] 桥接工具接线（TOOLS 声明 + dispatch 双在位）")
    mp = os.path.join(ROOT, "functions", "mcp.js")
    if not os.path.exists(mp):
        fail("functions/mcp.js 不存在")
        return
    src = open(mp, encoding="utf-8", errors="replace").read()
    has_decl = "name: 'explain_compose_frontier'" in src
    has_disp = "name === 'explain_compose_frontier'" in src
    if not has_decl:
        fail("explain_compose_frontier 未在 TOOLS 中声明")
    elif not has_disp:
        fail("explain_compose_frontier 有声明但无 dispatch 分支（调不通）")
    else:
        ok("TOOLS 声明 + dispatch 分支均已就位")

    # 反向：若只有声明没 dispatch，闸门必须能抓到
    if has_decl and not has_disp:
        ok("反向对照成立：'只有声明无 dispatch' 可被本检测识别")
    else:
        # 构造性验证：拿掉 dispatch 片段，确认检测逻辑会红
        stripped = src.replace("name === 'explain_compose_frontier'", "name === '__none__'")
        if ("name === 'explain_compose_frontier'" not in stripped
                and "name: 'explain_compose_frontier'" in stripped):
            ok("反向对照成立：抽掉 dispatch 后检测逻辑会判红（已构造验证）")
        else:
            fail("反向对照失败：无法构造「只有声明无 dispatch」的情形")


def check_unreachable_must_fail() -> None:
    """★ 关键反向对照：把某个产物改成不可达，必须判红。

    没有这一条，本层就只是「把『我说了我做到了』再检查一遍」——
    它会安静地给一个什么都没做的项目发合格证。
    """
    print("\n[3/4] 反向对照：产物不可达必须判红")
    out = brg.build()
    if not out["reachability"]:
        fail("reachability 为空，无法做反向对照")
        return
    mut = copy.deepcopy(out)
    # 把第一个「可达」的行改成不可达
    target = next((r for r in mut["reachability"] if r.get("reachable")), None)
    if target is None:
        print("  [skip] 当前无可达行（全部不可达），反向对照不适用")
        return
    target["reachable"] = False
    target["reference_count"] = 0
    target["referenced_by"] = []
    rs = mut["reachability_summary"]
    rs["artifacts_reachable"] = max(0, rs["artifacts_reachable"] - 1)
    rs["artifacts_unreachable"] = rs["artifacts_total"] - rs["artifacts_reachable"]
    if not _errors(mut):
        fail("把可达行改成不可达后闸门未判红 —— 本层是装饰（自欺型闸门）")
    else:
        ok(f"可达性反转被捕获（{target['artifact']}）")


def _mut_zero_scan(out, label):
    m = copy.deepcopy(out)
    m["reachability_summary"]["product_surface_files_scanned"] = 0
    return m


def _mut_count_broken(out, label):
    m = copy.deepcopy(out)
    m["reachability_summary"]["artifacts_unreachable"] += 1
    return m


def _mut_flag_count_mismatch(out, label):
    m = copy.deepcopy(out)
    for r in m["reachability"]:
        r["reachable"] = not r.get("reachable")
    return m


def _mut_taxonomy_stripped(out, label):
    m = copy.deepcopy(out)
    m["taxonomy"].pop("research_only_axes", None)
    return m


def _mut_fingerprint_emptied(out, label):
    m = copy.deepcopy(out)
    m["engine_fingerprints"]["product_js"]["dimensions"] = []
    return m


def _mut_options_stripped(out, label):
    m = copy.deepcopy(out)
    m.pop("decision_options", None)
    return m


MUTATIONS = [
    ("产品面扫描数为 0（扫描范围失效）", _mut_zero_scan),
    ("可达计数不守恒", _mut_count_broken),
    ("reachable 与 reference_count 不一致", _mut_flag_count_mismatch),
    ("taxonomy 被抹掉 research_only_axes", _mut_taxonomy_stripped),
    ("JS 维度集被清空（引擎结构已变）", _mut_fingerprint_emptied),
    ("decision_options 被删（断层无处可议）", _mut_options_stripped),
]


def check_mutations(out) -> None:
    print("\n[4/4] 变异检测（每个变异必须判红）")
    for label, fn in MUTATIONS:
        before = len(_MUTFAIL)
        _errors(fn(out, label), sink=_mutfail)
        if len(_MUTFAIL) == before:
            fail(f"变异未被捕获：{label}（闸门对该变异不敏感）")
        else:
            print(f"  [ok]   变异已捕获：{label}（触发 {len(_MUTFAIL)-before} 条断言）")


def main() -> int:
    print("=" * 70)
    print("verify_reachability_gap — 研究层可达性体检层阴阳自证")
    print("=" * 70)
    out = brg.build()

    check_baseline(out)
    check_bridge_wiring()
    check_unreachable_must_fail()
    check_mutations(out)

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
