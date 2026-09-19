#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_kinematics.py — 运动学层的阴阳自测 + 漂移闸门

【为什么要有这个文件】
`scripts/build_kinematics.py` 目前的真实状态是 **computed = 0**（真相源里连杆长度全是 null）。
一个「永远返回 insufficient_data」的引擎，跟一个写坏的引擎，在输出上**长得一模一样**。
所以必须做**阴阳自测**：构造一个参数齐全的假链，证明引擎在有数据时**真会算**；
再抽掉一个连杆长度，证明它**真会回 insufficient_data**。
只测「当前输出」是假绿——两者的区别只有靠正反样本才能锁住。

【三类判据】
1. 阳性对照：参数齐全 ⇒ computed，且 max_reach = Σ link_mm，矩阵按上界正确翻转
2. 阴性对照（fail-closed）：缺连杆长度 / 关节数不符 / 非正长度 ⇒ 一律 insufficient_data
3. 漂移与出处：api/kinematics.json 必须等于真相源现算；non-null 出处主机必须在白名单内

用法
----
    python scripts/verify_kinematics.py            # 全测，失败 exit 1
    python scripts/verify_kinematics.py --quiet     # 只在失败时输出
"""
from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_kinematics as bk  # noqa: E402

ROOT = bk.ROOT
SRC = bk.SRC
OUT = bk.OUT

PASSED = 0
FAILED = []


def check(name: str, cond: bool, detail: object = "") -> None:
    """detail 允许传任意对象（list/dict 常用于带出 missing_fields）——
    必须在此统一 str()，否则只在**判红分支**炸，绿路径永远掩盖该缺陷。"""
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}{(' — ' + str(detail)) if detail else ''}")


def chain(dof, joint_specs, **kw):
    joints = []
    for i, spec in enumerate(joint_specs):
        j = {"id": f"j{i + 1}", "type": spec.get("type", "revolute"),
             "link_mm": spec.get("link_mm")}
        joints.append(j)
    return {"id": kw.get("id", "TEST"), "build_ref": "TEST", "name": "t",
            "kind": "arm", "dof": dof, "joint_types": {"revolute": dof},
            "joints": joints, "spec_status": kw.get("spec_status", "declared"),
            "blocked_by": [], "provenance": {}}


PROBES = [150.0, 300.0]


def test_positive_control():
    """参数齐全 ⇒ 真会算：max_reach = 250，150 → not_ruled_out，300 → unreachable。"""
    c = chain(2, [{"link_mm": 100}, {"link_mm": 150}])
    r = bk.evaluate_chain(c, PROBES)
    check("阳性：参数齐全判 computed", r["status"] == "computed", r.get("missing_fields"))
    check("阳性：max_reach = Σ link_mm = 250", r.get("max_reach_mm") == 250.0,
          f"实得 {r.get('max_reach_mm')}")
    m = {cell["target_mm"]: cell["verdict"] for cell in r["reach_matrix"]}
    check("阳性：150mm 判 not_ruled_out", m.get(150.0) == "not_ruled_out", str(m))
    check("阳性：300mm 判 unreachable", m.get(300.0) == "unreachable", str(m))
    check("阳性：exact 上界不算 unreachable", (
        bk.evaluate_chain(chain(1, [{"link_mm": 300}]), [300.0])["reach_matrix"][0]["verdict"]
        == "not_ruled_out"))


def test_fail_closed():
    """缺一个连杆长度 ⇒ 必须 insufficient_data，且点名缺哪个关节。"""
    c = chain(2, [{"link_mm": 100}, {"link_mm": None}])
    r = bk.evaluate_chain(c, PROBES)
    check("阴性：缺 link_mm 判 insufficient_data", r["status"] == "insufficient_data",
          r.get("status"))
    check("阴性：点名 link_mm@j2", any("link_mm@j2" in x for x in r.get("missing_fields", [])),
          str(r.get("missing_fields")))
    check("阴性：矩阵全 unknown（不猜）",
          all(cell["verdict"] == "unknown" for cell in r["reach_matrix"]))
    check("阴性：max_reach 为 null", r.get("max_reach_mm") is None)


def test_reject_nonpositive_and_bool():
    """0 / 负值 / bool 都不得被当成有效长度（静默算成 0 或 1 = 假绿）。"""
    for bad in (0, -5, True, "100"):
        r = bk.evaluate_chain(chain(1, [{"link_mm": bad}]), PROBES)
        check(f"阴性：link_mm={bad!r} 被拒", r["status"] == "insufficient_data",
              f"实得 {r['status']} / max={r.get('max_reach_mm')}")


def test_dof_mismatch_and_fixed_joints():
    """声明 dof 与可动关节数不符 ⇒ insufficient_data；fixed 关节不得虚增可动数。"""
    r = bk.evaluate_chain(chain(3, [{"link_mm": 10}, {"link_mm": 10}]), PROBES)
    check("阴性：关节数 < dof 判 insufficient_data", r["status"] == "insufficient_data",
          str(r.get("missing_fields")))
    check("阴性：点名 joints_count(2/3)",
          any(x.startswith("joints_count") for x in r.get("missing_fields", [])),
          str(r.get("missing_fields")))

    c = chain(2, [{"link_mm": 10}, {"link_mm": 10, "type": "fixed"}])
    r2 = bk.evaluate_chain(c, PROBES)
    check("阴性：fixed 关节不计入可动数", r2["status"] == "insufficient_data",
          f"movable={r2.get('movable_joints')} dof={r2.get('dof')}")

    c3 = chain(2, [{"link_mm": 10}, {"link_mm": 10, "type": "fixed"}])
    c3["joints"].append({"id": "j3", "type": "revolute", "link_mm": 5})
    r3 = bk.evaluate_chain(c3, PROBES)
    check("阳性：fixed + 2 revolute = dof2 可算", r3["status"] == "computed",
          f"movable={r3.get('movable_joints')}")


def test_prismatic_counted():
    """prismatic（移动副）也是可动关节，必须计入。"""
    c = chain(1, [{"type": "prismatic", "link_mm": 200}])
    r = bk.evaluate_chain(c, PROBES)
    check("阳性：prismatic 计入可动关节", r["status"] == "computed" and r["max_reach_mm"] == 200.0,
          f"{r['status']} {r.get('max_reach_mm')}")


def test_drift_on_disk():
    """api/kinematics.json 必须等于真相源现算结果（防止手改派生物）。"""
    if not os.path.exists(OUT):
        check("产物存在", False, f"{os.path.relpath(OUT, ROOT)} 不存在")
        return
    doc = bk.build(SRC)
    with open(OUT, "r", encoding="utf-8") as f:
        old = json.load(f)
    check("漂移：产物 == 真相源现算", old == doc,
          "不一致 —— 跑 python scripts/build_kinematics.py")
    meta = doc["meta"]
    check("漂移：computed 计数与串一致性",
          meta["counts"]["computed"] == sum(1 for c in doc["chains"] if c["status"] == "computed"),
          f"meta={meta['counts']['computed']}")
    check("漂移：矩阵单元数 = 链数 × 探测数",
          meta["counts"]["matrix_cells"]
          == meta["counts"]["chains"] * meta["counts"]["probe_distances"])


def test_source_discipline():
    """真相源纪律：id/build_ref/provenance 必备；非 declared 必须列 blocked_by；
    non-null 出处主机必须在 approved_hosts 白名单内（无出处不登记）。"""
    src = bk.load_source(SRC)
    approved = set((src.get("meta") or {}).get("approved_hosts") or [])
    check("真相源：白名单非空", bool(approved))
    chains = src.get("chains") or []
    check("真相源：至少一条链", len(chains) >= 1, str(len(chains)))
    for c in chains:
        cid = c.get("id", "?")
        check(f"真相源[{cid}]：有 build_ref", bool(c.get("build_ref")))
        prov = c.get("provenance") or {}
        check(f"真相源[{cid}]：有 provenance.tier", bool(prov.get("tier")), str(prov))
        if c.get("spec_status") != "declared":
            check(f"真相源[{cid}]：非 declared 必须列 blocked_by",
                  bool(c.get("blocked_by")), str(c.get("blocked_by")))
        for j in (c.get("joints") or []):
            url = j.get("source_url")
            if not url:
                continue
            host = urlparse(url).hostname or ""
            check(f"真相源[{cid}/{j.get('id')}]：出处主机在白名单", host in approved,
                  f"越权主机 {host}")


def main() -> int:
    quiet = "--quiet" in sys.argv
    test_positive_control()
    test_fail_closed()
    test_reject_nonpositive_and_bool()
    test_dof_mismatch_and_fixed_joints()
    test_prismatic_counted()
    test_drift_on_disk()
    test_source_discipline()

    if FAILED:
        print(f"❌ verify_kinematics: {len(FAILED)} 项失败（通过 {PASSED}）")
        for f in FAILED:
            print(f"   - {f}")
        return 1
    if not quiet:
        print(f"✅ verify_kinematics: {PASSED} 项全过（含阳性/阴性对照与漂移判据）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
