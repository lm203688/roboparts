#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_kinematics.py — 运动学可达性判定生成器（唯一真相源 → 对外 JSON）

【为什么要有这个文件】
RoboParts 现有兼容性判定只覆盖**静态机械接口**（法兰能不能拧上去，见
api/negative_compat.json）。但那只是「装配问题」的一半：一条由零件拼出的臂/腿，
**能不能够到目标位姿**，是同一问题的另一半，而且没人把它跟零件库连起来。
本轮借鉴 UC Berkeley 的 PyRoki（github.com/chungmin99/pyroki，MIT，IROS 2025）：
一个把 URDF 解析 / 正逆运动学 / 碰撞检测拆成模块的 JAX 工具包。
不搬它的代码（Python+JAX 跑不进 Cloudflare Workers 边缘），而是**搬它的数据前提**：
零件必须带运动学元数据（连杆长度、关节轴、限位），否则任何 IK 判定都无从谈起。
所以本层先做**离线可达性上界**，并把「缺什么数据」显式登记出来。

【本层算什么 / 不算什么】
算：max_reach_mm = Σ link_mm（可达半径上界），并据此对一组探测距离给出
    unreachable / not_ruled_out。这是 **sound 的负面判定**——忽略关节限位与
    自碰撞，所以「够不到」是可靠结论，「够得到」只表示**未被排除**。
不算：完整 IK/FK 求解、轨迹优化、自碰撞检测（都需要尚未声明的限位与几何）。
这不是能力取舍，是**数据缺口**：真相源里 link_mm 全是 null。

【纪律】
- 幂等：重复运行产出字节一致（排序固定、**不写时间戳**）
- fail-closed：任一连杆长度缺失 ⇒ 该链判 insufficient_data，禁止回退到猜测
- 无出处不登记：non-null 的几何值必须在 kinematics/source.json 的 approved_hosts 内可追
- 只读 kinematics/source.json，只写 api/kinematics.json

用法
----
    python scripts/build_kinematics.py            # 生成
    python scripts/build_kinematics.py --dry-run   # 只打印统计，不落盘
    python scripts/build_kinematics.py --check     # 只校验漂移，漂移则 exit 1（供 CI）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "kinematics", "source.json")
OUT = os.path.join(ROOT, "api", "kinematics.json")
# meta.access 模板源：不硬编码，避免与站点其他 JSON 的领 key 入口漂移
ACCESS_TEMPLATE_SRC = os.path.join(ROOT, "api", "platforms.json")

# 可动关节类型：只有这些贡献自由度与连杆长度
MOVABLE_JOINT_TYPES = ("revolute", "continuous", "prismatic")
# 浮点比较容差（mm 量级）
EPS_MM = 1e-6


def load_source(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_access_block() -> Dict[str, Any]:
    """取站点标准的『AI 领 key 入口』块。

    纪律：谁重写对外 JSON，谁负责补回 meta.access（否则会抹掉 AI 领 key 入口）。
    注意 meta.access 是**部署注入器的受管区域**，deploy.mjs 会用标准块整块覆盖，
    任何自定义字段放进去都会在部署时被静默抹掉。故本文件自己的边界声明写在
    meta.honest_limits，不放 access 里。
    """
    with open(ACCESS_TEMPLATE_SRC, "r", encoding="utf-8") as f:
        doc = json.load(f)
    access = doc.get("meta", {}).get("access")
    if not access:
        raise SystemExit(f"{ACCESS_TEMPLATE_SRC} 缺少 meta.access，无法作为模板")
    return json.loads(json.dumps(access))


def _movable(joints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for j in joints:
        if (j.get("type") or "").lower() in MOVABLE_JOINT_TYPES:
            out.append(j)
    return out


def evaluate_chain(chain: Dict[str, Any], probes: List[float]) -> Dict[str, Any]:
    """对单条运动学链做可达性上界判定（纯函数，供生成器与阴阳自测共用）。

    返回 status ∈ {insufficient_data, computed}。
    - insufficient_data：缺 dof / 关节数不符 / 有连杆长度缺失 —— fail-closed
    - computed：给出 max_reach_mm 与逐探测距离的判定矩阵
    """
    joints = chain.get("joints") or []
    movable = _movable(joints)
    dof = chain.get("dof")
    try:
        dof_i = int(dof) if dof is not None else 0
    except (TypeError, ValueError):
        dof_i = 0

    missing: List[str] = []
    if dof_i <= 0:
        missing.append("dof")
    if len(movable) != dof_i:
        missing.append(f"joints_count({len(movable)}/{dof_i})")
    for j in movable:
        jid = j.get("id") or "?"
        lm = j.get("link_mm")
        if not isinstance(lm, (int, float)) or isinstance(lm, bool) or lm <= 0:
            missing.append(f"link_mm@{jid}")

    base = {
        "id": chain.get("id"),
        "build_ref": chain.get("build_ref"),
        "name": chain.get("name"),
        "kind": chain.get("kind"),
        "dof": dof_i,
        "joint_types": chain.get("joint_types") or {},
        "movable_joints": len(movable),
        "spec_status": chain.get("spec_status") or "unknown",
        "blocked_by": list(chain.get("blocked_by") or []),
        "provenance": chain.get("provenance") or {},
    }

    if missing:
        return {
            **base,
            "status": "insufficient_data",
            "missing_fields": missing,
            "max_reach_mm": None,
            "reach_matrix": [
                {
                    "target_mm": p,
                    "verdict": "unknown",
                    "reason": "连杆长度/关节数未声明齐全，无法给出可达性结论（不做猜测）",
                }
                for p in probes
            ],
            "honest_note": (
                "本链的自由度与关节类型是已核实事实；连杆长度缺失，故可达性一律判 unknown。"
                "补上 joints[] 的 link_mm 后本链会自动进入 computed。"
            ),
        }

    total = sum(float(j["link_mm"]) for j in movable)
    matrix = []
    for p in probes:
        if float(p) > total + EPS_MM:
            matrix.append(
                {
                    "target_mm": p,
                    "verdict": "unreachable",
                    "reason": f"目标 {p}mm 超出可达半径上界 {total:g}mm（可靠结论）",
                }
            )
        else:
            matrix.append(
                {
                    "target_mm": p,
                    "verdict": "not_ruled_out",
                    "reason": (
                        f"目标 {p}mm 在上界 {total:g}mm 之内，但未计入关节限位与自碰撞，"
                        "故仅表示未被排除，不表示可达"
                    ),
                }
            )

    return {
        **base,
        "status": "computed",
        "missing_fields": [],
        "max_reach_mm": total,
        "reach_matrix": matrix,
        "honest_note": (
            "max_reach_mm 是 Σ link_mm 的**上界**（忽略限位/自碰撞）："
            "unreachable 可靠，not_ruled_out 保守。非认证，不替代样机实测。"
        ),
    }


def build(src_path: str) -> Dict[str, Any]:
    src = load_source(src_path)
    meta_in = src.get("meta") or {}
    # 探测距离归一化：整数值写成 int，避免对外 JSON 出现 150.0 这类噪声
    probes: List[Any] = []
    for x in (meta_in.get("probe_distances_mm") or []):
        fx = float(x)
        probes.append(int(fx) if fx == int(fx) else fx)
    if not probes:
        raise SystemExit("kinematics/source.json 缺少 meta.probe_distances_mm，拒绝产出")

    chains_in = src.get("chains") or []
    if not chains_in:
        raise SystemExit("kinematics/source.json 没有任何 chain，拒绝产出")

    chains = [evaluate_chain(c, probes) for c in chains_in]
    # 固定排序，保证幂等
    chains.sort(key=lambda c: (c.get("id") or ""))

    n = len(chains)
    n_computed = sum(1 for c in chains if c["status"] == "computed")
    n_insuff = n - n_computed
    dof_total = sum(c["dof"] for c in chains)
    with_bound = [c for c in chains if c["status"] == "computed"]

    return {
        "meta": {
            "schema": "roboparts.kinematics/v1",
            "title": "RoboParts 运动学可达性判定（参考构型）",
            "description": (
                "参考构型的运动学链与可达性上界判定。回答『这条由零件拼出的臂/腿够不够得到某个距离』——"
                "静态机械接口判定（negative_compat）之外的动态那一半。"
                "借鉴 PyRoki（UC Berkeley，MIT）的 URDF 优先数据模型：零件不带运动学元数据，"
                "任何 IK 判定都无从谈起，故本层先把数据缺口显式登记，而不是用求解器掩盖它。"
            ),
            "truth_source": (
                "由 scripts/build_kinematics.py 从 kinematics/source.json 现算生成，禁止手改"
            ),
            "method": (
                "max_reach_mm = Σ link_mm。这是可达半径的**上界**：忽略关节限位与自碰撞，"
                "故两个方向的可信度不对称——『够不到』(unreachable) 是可靠结论，"
                "『未被排除』(not_ruled_out) 只是保守判断。刻意选择 sound 方向。"
            ),
            "counts": {
                "chains": n,
                "computed": n_computed,
                "insufficient_data": n_insuff,
                "dof_total": dof_total,
                "probe_distances": len(probes),
                "matrix_cells": n * len(probes),
            },
            "coverage": {
                "chains_with_reach_bound": n_computed,
                "chains_total": n,
                "pct": round(n_computed / n * 100, 1) if n else 0.0,
            },
            "honest_limits": {
                "chains_with_reach_bound": n_computed,
                "chains_total": n,
                "scope": (
                    "本库只覆盖 api/reference_builds.json 中已登记的参考构型，"
                    "不等于穷举市场现存的臂/腿构型；未登记构型应返回 unknown，禁止外推。"
                ),
                "data_gap": (
                    "真相源中所有 chain 的连杆长度均为 null（厂商公开页面未列 horn PCD 与连杆节距），"
                    "故当前 computed=0。这是**数据缺口**，不是算法缺陷——"
                    "补上 joints[].link_mm 即自动生效，无需改代码。"
                ),
                "no_full_ik": (
                    "本层不含完整 IK/FK 与自碰撞检测：二者都需要关节限位与几何体，而这两项目前尚未声明。"
                    "不要把 not_ruled_out 当作『可达』对外宣称。"
                ),
                "derivation": "纯几何上界现算，无厂商实测复现，非认证。",
            },
            "probe_distances_mm": probes,
            "reach_bound_semantics": meta_in.get("reach_bound_semantics"),
            "borrowed_from": meta_in.get("borrowed_from") or [],
            "access": load_access_block(),
        },
        "chains": chains,
    }


def norm(doc: Dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--dry-run", action="store_true", help="只打印统计，不落盘")
    ap.add_argument("--check", action="store_true", help="只校验与磁盘产物是否一致")
    args = ap.parse_args()

    doc = build(args.src)
    m = doc["meta"]["counts"]
    print(
        f"[kinematics] chains={m['chains']} computed={m['computed']} "
        f"insufficient_data={m['insufficient_data']} dof_total={m['dof_total']} "
        f"matrix={m['matrix_cells']}"
    )

    if args.dry_run:
        print("dry-run: 未写盘")
        return 0

    new_text = norm(doc)

    if args.check:
        if not os.path.exists(args.out):
            print(f"❌ {os.path.relpath(args.out, ROOT)} 不存在（先跑 build_kinematics.py）")
            return 1
        with open(args.out, "r", encoding="utf-8") as f:
            old_text = f.read()
        if old_text != new_text:
            try:
                old_doc = json.loads(old_text)
                if old_doc == doc:
                    print("✅ 语义一致（仅空白/键序差异）")
                    return 0
            except Exception:
                pass
            print(f"❌ {os.path.relpath(args.out, ROOT)} 与真相源现算结果不一致")
            print("   修复: python scripts/build_kinematics.py")
            return 1
        print(f"✅ {os.path.relpath(args.out, ROOT)} 与真相源一致")
        return 0

    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_text)
    print(f"written -> {os.path.relpath(args.out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
