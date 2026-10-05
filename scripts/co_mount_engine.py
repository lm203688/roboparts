#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""co_mount_engine — RoboParts 第三种关系类型：共装（co-mount）。

    co_mount(a, b, host, graph) -> CoMountResult
    verdict ∈ {mountable, port_exhausted, type_error, unknown}  （四态诚实）

── 为什么需要第三种关系类型 ────────────────────────────────────────
compose_engine 只有一种关系：**peer-to-peer（二段互插）**
    A 的连接器 ↔ B 的连接器
而 cobot EOAT 的真实工程关系是：**co-mount（三段共装）**
    A 的法兰 → 宿主工具法兰 ← B 的法兰
    A 的电气 → 宿主工具 I/O ← B 的电气
两者的判定对象根本不同：peer-to-peer 问「A 能不能插进 B」，
co-mount 问「A 和 B 能不能同时挂在同一台机器人的工具侧」。

这不是数据缺口，是**关系类型错配**。证据（api/compose_frontier.json）：
  L1 跨角色 28,310 对 / 393 节点
  L2 机械可判定 63 对 / 16 节点 —— 机械 63/63 通过、信号 63/63 通过
  L3 electrical compatible 0 对  ← composed 恒为 0 的唯一原因
且两侧均取证的配对里，判出结果的**全部 incompatible、0 compatible**
（EOAT 器件按设计就不互插：各占机器人侧一个电气端口）。

⇒ 若不新增关系类型，**补再多电气声明也不会让 composed>0**，
且这是 D5 范畴论路线的多年期工程（泛化关系类型需要重新做类型系统）。
本引擎是**最小可交付版本**：只覆盖「同一宿主工具侧共装」这一种关系，
不声称解决一般关系类型问题。

── 三段判据（与 peer-to-peer 的关键差异，全部 fail-closed）────────

机械段 mount_fit(a, host)：
    a 的机械端口类型 **≡** host 的工具法兰类型 ⇒ identity ⇒ 可装
    ⇒ 判据从「互插」变成「**同型**」。A50 配 A50 是同型公理，
       不需要任何几何比对——这正是 identity 的语义。
    共享同一法兰 ≠ 冲突（ISO 9409-1 定义的就是可重复装配的标准界面）。

电气段 port_budget(a, b, host)：
    这是 co-mount **独有**的一段，也是它区别于 peer-to-peer 的核心。
    A 和 B 各自要占宿主工具侧的一个电气端口。宿主端口数是**有限**的
    （UR5e = 1 个 8-pin M8 Tool I/O），所以：
      n_mounted + 1 ≤ host.tool_io_ports  ⇒  仍有余量
      否则 ⇒ **port_exhausted**（不是 incompatible，也不是 unknown）
    这个新状态是诚实的：它精确区分了「装不下」（工程约束）
    与「不知道能不能装」（证据缺口）。peer-to-peer 没有这个状态，
    因为二段关系里不存在「争抢同一个有限资源」。

信号段 signal_complementary(a, b)：
    沿用 compose_engine 的跨角色判据（OUTPUT ↔ INPUT 互补）。
    共装不改变信号语义——A 输出、B 感知正是共装的**目的**。

── 口径纪律 ──────────────────────────────────────────────────────
1. **宿主侧数据必须有一手出处**。本引擎不猜端口数：host.tool_io_ports
   为 null 时判 port_budget=unknown，**不按型号名推断**。
2. **不声称解决一般关系类型问题**。只覆盖「同一宿主工具侧共装」。
3. **端口预算判据必须区分 exhausted 与 unknown**——前者是工程结论，
   后者是证据缺口。混为一谈就是把「不知道」伪装成「不行」。
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

ENGINE_VERSION = "co_mount_engine/v1"

#: 共装裁决。与 peer-to-peer 的 composed/type_error/unknown 三态不同，
#: 多出 port_exhausted——它表示「机械与信号都成立，但宿主资源不够」。
VERDICTS: Tuple[str, ...] = ("mountable", "port_exhausted", "type_error", "unknown")

#: 三段判据的段名。机械段判「同型」，电气段判「资源」，信号段判「互补」。
STAGES: Tuple[str, ...] = ("mount_fit", "port_budget", "signal_complementary")

_STAGE_VERDICT: Dict[str, str] = {
    "fit": "compatible",
    "exhausted": "resource_conflict",
    "incompatible": "incompatible",
    "unknown": "unknown",
    "complementary": "compatible",
    "not_complementary": "incompatible",
}


def _effective(node: Dict[str, Any], axis: str) -> List[Dict[str, Any]]:
    """有效端口 = status ∈ {declared, partial}（与 compose_engine 同源口径）。"""
    pre = {"mechanical": "MECH", "electrical": "ELEC", "signal": "SIG"}[axis]
    return [
        p for p in (node.get("ports") or [])
        if p["type"].startswith(pre + ":")
        and p.get("status") in ("declared", "partial")
    ]


def _type_index(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {t["id"]: t for t in (graph.get("port_types") or [])}


def mount_fit(
    dev: Dict[str, Any], host: Dict[str, Any], types: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """机械段：dev 的法兰与 host 的工具法兰**同型**即可装。

    与 peer-to-peer 的本质差异：这里问的是「是否同型」而不是「是否互插」。
    共享同一 ISO 9409-1 界面**不是冲突**——该标准的定义就是可重复装配。

    host.tool_flange 为 null 时判 unknown：宿主侧无一手数据，不按型号名猜。
    """
    h_flange = host.get("tool_flange")
    if not h_flange:
        return {
            "verdict": "unknown",
            "reason": "宿主未声明工具法兰（一手数据缺失）——不按型号名推断",
        }
    dev_mech = _effective(dev, "mechanical")
    if not dev_mech:
        return {
            "verdict": "unknown",
            "reason": "器件无已声明机械端口（not_declared）——证据缺口",
        }
    matched = [p["type"] for p in dev_mech if p["type"] == h_flange]
    if matched:
        t = types.get(h_flange) or {}
        return {
            "verdict": "fit",
            "reason": "器件机械端口与宿主工具法兰同型（%s）"
                      "—— ISO 9409-1 界面可重复装配，同型不冲突" % h_flange,
            "matched_type": h_flange,
            "flange_standard": t.get("standard") or t.get("token"),
        }
    have = sorted({p["type"] for p in dev_mech})
    return {
        "verdict": "incompatible",
        "reason": "器件机械端口 %s 与宿主工具法兰 %s 不同型" % (have, h_flange),
        "device_ports": have,
        "host_flange": h_flange,
    }


def port_budget(
    a: Dict[str, Any],
    b: Dict[str, Any],
    host: Dict[str, Any],
    mounting: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """电气段：共装**独有**的一段——宿主工具侧端口预算。

    判据：`已装数 + 本次拟装器件数 ≤ 宿主工具 I/O 位数`。

    ★ 实测踩过的建模错误（结论会完全相反，务必记住）：
      初版写成 `occupied + 1 <= n_ports`，即「每次只装 1 个」。
      但 co_mount 的语义是**同时装 a 和 b 两个器件**，
      它们**各占宿主工具侧一个位** ⇒ 应算 `occupied + 2`。
      错版会让 UR（工具侧只有 1 个 8-pin 位）判出「可共装两个器件」，
      而物理上 UR 只有一个工具位——**恰好把唯一正确的约束判反了**。
      这与「端口数 ≠ 针数」是同源错误：**位数、针数、器件数是三个不同的量**，
      任何两个混用都会得出反向结论。

    · 位数为 null ⇒ unknown（证据缺口，不是「装不下」）
    · 器件无已声明电气端口 ⇒ **保守计入 1 位**并单独登记：
      **「没取证」不等于「不需要电」**——EOAT 绝大多数都供电。
      若不计入会乐观高估容量（漏判 exhausted）；若按 2 计则过严。
      故取「未取证按 1 计」并在 reason 里显式说明，缺口可见不掩盖。
    """
    n_ports = host.get("tool_io_ports")
    stage_evidence = {
        "host_tool_io_ports": n_ports,
        "host_tool_io_connector": host.get("tool_io_connector"),
        "source_url": host.get("source_url"),
        "source_tier": host.get("source_tier"),
    }
    if n_ports is None:
        return dict(
            stage_evidence,
            verdict="unknown",
            reason="宿主工具 I/O 位数未取证（tool_io_ports=null）"
                   "——不按型号名推断「有几个位」",
        )

    # 本次拟装的器件**各占一位**。a 与 b 可能是同一 id（单件查询），
    # 那种情况只算一个位，否则单件查询会被误判为「要 2 位」。
    ids = []
    undeclared: List[str] = []
    for dev in (a, b):
        did = dev.get("id") or "?"
        ids.append(did)
        if not _effective(dev, "electrical"):
            undeclared.append(did)
    this_batch = len(set(ids))          # 同一 id 只算一次
    occupied = len(mounting)
    total_after = occupied + this_batch

    if total_after <= n_ports:
        note = ""
        if undeclared:
            note = ("；其中 %s 无已声明电气端口，按「未取证但需供电」"
                    "保守各计 1 位" % sorted(set(undeclared)))
        return dict(
            stage_evidence,
            verdict="fit",
            reason="宿主工具侧 %d 位，已占 %d，本次装 %d ⇒ 仍有余量%s"
                   % (n_ports, occupied, this_batch, note),
            ports_needed=this_batch,
            ports_available=n_ports,
            ports_occupied_before=occupied,
            ports_after=total_after,
            undeclared_electrical=undeclared,
        )
    return dict(
        stage_evidence,
        verdict="exhausted",
        reason="宿主工具侧仅 %d 位，已占 %d，本次装 %d ⇒ 位数耗尽"
               "（工程约束：需转接/换本体，不是数据缺口）"
               % (n_ports, occupied, this_batch),
        ports_needed=this_batch,
        ports_available=n_ports,
        ports_occupied_before=occupied,
        ports_after=total_after,
        undeclared_electrical=undeclared,
    )


def signal_complementary(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """信号段：共装不改变信号语义——A 输出、B 感知正是共装的目的。"""
    a_s = {p["type"] for p in _effective(a, "signal")}
    b_s = {p["type"] for p in _effective(b, "signal")}
    OUT, IN = "SIG:OUTPUT_SPIKE", "SIG:INPUT_SENSORY"
    if OUT in a_s and IN in b_s:
        return {"verdict": "complementary", "reason": "A 输出 → B 感知（跨角色互补）"}
    if OUT in b_s and IN in a_s:
        return {"verdict": "complementary", "reason": "B 输出 → A 感知（跨角色互补）"}
    if not a_s or not b_s:
        return {
            "verdict": "unknown",
            "reason": "任一侧无已声明信号端口（not_declared）——证据缺口",
        }
    return {
        "verdict": "not_complementary",
        "reason": "两侧信号角色不互补（%s vs %s）"
                  "——共装要求一方输出、另一方感知"
                  % (sorted(a_s), sorted(b_s)),
    }


def co_mount(
    a: Dict[str, Any],
    b: Dict[str, Any],
    host: Dict[str, Any],
    graph: Dict[str, Any],
    already_mounted: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """共装裁决。a/b 为器件，host 为宿主，already_mounted 为已占端口的器件。

    对称性：a/b 顺序不影响 mount_fit 与 port_budget（端口计数与身份无关），
    signal_complementary 的 reason 文案会随方向变化，故整体保持对称语义。
    """
    for name, node in (("a", a), ("b", b), ("host", host)):
        if not isinstance(node, dict) or "id" not in node:
            raise ValueError("co_mount: %s 缺 id" % name)
    types = _type_index(graph)
    mounting = already_mounted or []

    stages = {
        "mount_fit": {
            "a": mount_fit(a, host, types),
            "b": mount_fit(b, host, types),
        },
        "port_budget": port_budget(a, b, host, mounting),
        "signal_complementary": signal_complementary(a, b),
    }

    # 汇总：三段任一 incompatible ⇒ type_error；
    # exhausted ⇒ port_exhausted（工程约束，与证据缺口分开）；
    # 任一 unknown ⇒ unknown；否则 mountable。
    flat: List[Tuple[str, str]] = []
    for st in ("mount_fit", "port_budget", "signal_complementary"):
        v = stages[st]
        if st == "mount_fit":
            flat += [("mount_fit.a", v["a"]["verdict"]), ("mount_fit.b", v["b"]["verdict"])]
        else:
            flat.append((st, v["verdict"]))
    verdicts = [verdict for _, verdict in flat]

    if "incompatible" in verdicts or "not_complementary" in verdicts:
        overall = "type_error"
    elif "exhausted" in verdicts:
        overall = "port_exhausted"
    elif "unknown" in verdicts:
        overall = "unknown"
    else:
        overall = "mountable"

    return {
        "engine_version": ENGINE_VERSION,
        "relation": "co_mount",
        "device_a": a["id"],
        "device_b": b["id"],
        "host": host["id"],
        "overall": overall,
        "stages": stages,
        "already_mounted": [d.get("id") for d in mounting],
        "stage_verdicts": dict(flat),
    }
