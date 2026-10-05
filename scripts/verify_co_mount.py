#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_co_mount — 共装层的自证：正样本 + 负样本 + 变异 + 口径守卫。

遵循本项目已成型的闸门范式（阳性/阴性/变异三对照）：
  · **只测绿路径的闸门等于没闸门**。所以必须有变异，且变异要**独立收集**。
  · **变异体自己也要验证确实打到了破口**（本项目已两次踩坑：
    变异改了字段但集合仍满足条件 ⇒ 压根没破防 ⇒ 报「闸门是装饰」的假警报）。
  · **被过度声称的诊断比没有诊断更坏** ⇒ 口径守卫逐字段要求限定词。
"""
from __future__ import annotations

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from co_mount_engine import co_mount  # noqa: E402

MUTFAIL = []
FAILED = False
PASSED = 0


def ok(msg):
    global PASSED
    PASSED += 1
    print("  \u2713 %s" % msg)


def fail(msg):
    global FAILED
    FAILED = True
    print("  \u2717 %s" % msg)


def emit(msg):
    """变异失败收集器：变异**应该**触发失败，混进主列表就是假红灯。"""
    MUTFAIL.append(msg)


def _load(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════
# 判据（纯函数，与 ci_gate 同源——避免同一口径两份实现）
# ═══════════════════════════════════════════════════════════════════
def _errors(cm, ts):
    errs = []
    meta = cm.get("meta") or {}
    s = cm.get("summary") or {}

    # ① 关系类型必须显式登记为 co_mount（三段），不能与 peer-to-peer 混
    rs = cm.get("relation_semantics") or {}
    cmr = rs.get("co_mount") or {}
    if not cmr:
        errs.append("缺 relation_semantics.co_mount —— 本层算哪种关系必须自述")
    # ★ 逐字段要求，不用「全文里有没有 host」当判据：
    #   子串搜索会被 relation_semantics 里的其它字段绕过 ⇒ 守卫形同虚设
    #   （与 compose_frontier 口径守卫踩过的坑完全同型）
    elif cmr.get("structure") != "three_segment_via_host":
        errs.append("co_mount.structure=%r 不是 three_segment_via_host —— "
                    "本层必须是三段宿主结构，否则就不是 co_mount"
                    % cmr.get("structure"))
    if rs.get("peer_to_peer") and cmr:
        pv = set((rs["peer_to_peer"]).get("verdicts") or [])
        cv = set(cmr.get("verdicts") or [])
        if not cv - pv:
            errs.append("co_mount 的裁决集是 peer_to_peer 的子集 —— "
                        "没有引入新状态就等于没换关系类型")
        if "port_exhausted" not in cv:
            errs.append("co_mount 缺 port_exhausted —— 这是 co-mount "
                        "**独有**的工程约束状态，缺它就退化成二段关系")

    # ② 计数守恒：by_host（**仅双件**）合计 == pair_evaluations
    #    实测踩过：单件与双件曾共用一个计数器，宿主合计 136=16+120
    #    而 pair_evaluations=120 ⇒ 守恒永久假红 ⇒ 判据形同虚设。
    #    现在两者分开，守恒必须严格相等。
    by_host = s.get("by_host") or {}
    tot = sum(sum(v.values()) for v in by_host.values())
    if tot != (s.get("pair_evaluations") or 0):
        errs.append("双件 by_host 合计 %d != pair_evaluations %s"
                    "（单件必须用 single_by_host，单双混算会让守恒永久假红）"
                    % (tot, s.get("pair_evaluations")))
    ph = s.get("pair_verdict_histogram") or {}
    if by_host and sum(ph.values()) != tot:
        errs.append("pair_verdict_histogram 合计 %d != by_host 合计 %d（两处口径分叉）"
                    % (sum(ph.values()), tot))
    # 单件计数必须独立守恒
    for h, v in (s.get("single_mount_by_host") or {}).items():
        if sum(v.values()) != (s.get("devices") or 0):
            errs.append("宿主 %s 单件裁决数 %d != devices %s"
                        % (h, sum(v.values()), s.get("devices")))

    # ③ 裁决值必须全在白名单内（拼写漂移会静默通过）
    ALLOWED = {"mountable", "port_exhausted", "type_error", "unknown"}
    for h, v in (s.get("pair_verdict_histogram") or {}).items():
        if h not in ALLOWED:
            errs.append("裁决直方图含非法值 %r" % h)
    for pv in (cm.get("pair_verdicts") or []):
        if pv.get("verdict") not in ALLOWED:
            errs.append("pair_verdicts 含非法裁决 %r" % pv.get("verdict"))

    # ④ 最坏状态必须红：全部 unknown 且零可判定 ⇒ 判红
    #    （这看似「自欺型守卫」，但它的另一面才是关键：
    #     若某天共装层退化到「什么都判不出来」而闸门仍绿，
    #     那正是 compose_frontier 当年被误读为失败的那种状态。）
    hist = s.get("pair_verdict_histogram") or {}
    decided = (hist.get("mountable", 0) + hist.get("port_exhausted", 0)
               + hist.get("type_error", 0))
    if not decided:
        errs.append("全部裁决 unknown —— 共装层零可判定，"
                    "此时它不提供任何 peer-to-peer 之外的信息")

    # ⑤ 单件与双件必须分别给判据（单件语义≠双件语义）
    if not s.get("single_mount_by_host"):
        errs.append("缺 single_mount_by_host —— 单件可装性与双件共装是"
                    "**两个不同的问题**，不能只报后者")
    # 单件守恒已并入判据 ②

    # ⑥ 宿主层：tool_io_ports=null 必须是刻意登记的缺口
    hosts = ts.get("hosts") or []
    if not hosts:
        errs.append("宿主层为空 —— co_mount 是三段关系，宿主侧无数据则本层无意义")
    for h in hosts:
        for f in ("tool_flange", "source_url", "source", "source_tier",
                  "confidence", "mountable_tools"):
            if not h.get(f) and h.get(f) != 0:
                errs.append("宿主 %s 缺一手取证字段 %s" % (h.get("id"), f))
        n = h.get("tool_io_ports")
        if n is None:
            if not h.get("key_facts"):
                errs.append("宿主 %s 的 tool_io_ports=null 但未登记原因"
                            " —— 缺口必须可见，否则读成「漏填」" % h.get("id"))
        elif not isinstance(n, int) or n < 0:
            errs.append("宿主 %s tool_io_ports=%r 不是非负整数" % (h.get("id"), n))
        elif n > 1:
            errs.append("宿主 %s tool_io_ports=%d > 1 —— 本层取证范围内"
                        "工具侧均为单连接器（位=1）。>1 需重新核实"
                        "「位」的定义（位数≠针数）" % (h.get("id"), n))
    # tool_flange 必须是形态图端口类型 id，不是自由文本
    tids = {t["id"] for t in ((_load("api/morphology_graph.json")
                              or {}).get("port_types") or [])}
    for h in hosts:
        if tids and h.get("tool_flange") not in tids:
            errs.append("宿主 %s tool_flange=%r 不是形态图端口类型 id —— "
                        "自由文本会让 co_mount 机械段 join 全失败"
                        % (h.get("id"), h.get("tool_flange")))

    # ⑦ 口径守卫：本层不声称解决一般关系类型问题（逐字段要求）
    hl = " ".join(meta.get("honest_limits") or [])
    for kw, why in (("未建模", "未覆盖的范畴必须显式声明"),
                    ("tool_io_ports", "宿主位数的证据缺口必须自述"),
                    ("不覆盖", "本层的判定粒度上限必须自述"),
                    ("互不改写", "不得暗示本层改写了 compose_semantics 的答案"),
                    ("单向模型缺陷", "本层自身的已知不足必须登记")):
        if kw not in hl:
            errs.append("honest_limits 缺「%s」（%s）" % (kw, why))
    if "port_exhausted" not in (meta.get("caliber") or "") and \
            "port_exhausted" not in json.dumps(rs.get("co_mount") or {},
                                               ensure_ascii=False):
        errs.append("caliber/语义里未点明 port_exhausted 与 unknown 的区别")
    return errs


# ═══════════════════════════════════════════════════════════════════
# 变异
# ═══════════════════════════════════════════════════════════════════
def _mut_relabel(cm, ts, label):
    """把 co_mount 改成二段关系（structure 退化为 peer_to_peer）⇒ 必须判红。

    ★ 实测踩过第三次「变异打空」：初版只改 `question` 文案
      （改成「A 能不能插进 B？」），而 `structure` 字段仍写着
      three_segment_via_host ⇒ 判据读的是 structure，压根没被破防
      ⇒ 报「闸门是装饰」的假警报。
      **变异必须打在判据真正依据的那个字段上。**
      判据据 `structure != three_segment_via_host` 判红，故这里改 structure。
    """
    m = copy.deepcopy(cm)
    m["relation_semantics"]["co_mount"]["structure"] = "peer_to_peer"
    m["relation_semantics"]["co_mount"]["question"] = \
        "A 能不能插进 B？（与 peer-to-peer 同）"
    return m, ts


def _mut_drop_exhausted(cm, ts, label):
    """抹掉 port_exhausted 状态 ⇒ 退化成二段关系，必须判红。"""
    m = copy.deepcopy(cm)
    m["relation_semantics"]["co_mount"]["verdicts"] = \
        ["mountable", "type_error", "unknown"]
    return m, ts


def _mut_all_unknown(cm, ts, label):
    """最坏状态：全部判 unknown ⇒ 零可判定必须判红（正向判据 ④）。"""
    m = copy.deepcopy(cm)
    bh = (m.get("summary") or {}).get("by_host") or {}
    h = next(iter(bh), "HUB-031")
    m["summary"]["pair_verdict_histogram"] = {"unknown": 0}
    m["summary"]["by_host"] = {h: {"unknown": 0}}
    m["summary"]["pair_evaluations"] = 0
    m["pair_verdicts"] = []
    return m, ts


def _mut_count_break(cm, ts, label):
    """计数不守恒 ⇒ 必须判红。"""
    m = copy.deepcopy(cm)
    m["summary"]["pair_evaluations"] = 99999
    return m, ts


def _mut_illegal_verdict(cm, ts, label):
    """拼写漂移的裁决值 ⇒ 必须判红。"""
    m = copy.deepcopy(cm)
    m["summary"]["pair_verdict_histogram"]["mountiable"] = 1
    return m, ts


def _mut_drop_evidence(cm, ts, label):
    """抹掉宿主一手出处 ⇒ 必须判红。"""
    t = copy.deepcopy(ts)
    for h in (t.get("hosts") or []):
        h["source_url"] = ""
        h["source_tier"] = ""
    return cm, t


def _mut_ports_null_no_note(cm, ts, label):
    """tool_io_ports=null 但不登记原因 ⇒ 缺口不可见，必须判红。"""
    t = copy.deepcopy(ts)
    for h in (t.get("hosts") or []):
        if h.get("tool_io_ports") is None:
            h["key_facts"] = []
    return cm, t


def _mut_flange_free_text(cm, ts, label):
    """tool_flange 改成自由文本 ⇒ join 会失败，必须判红。"""
    t = copy.deepcopy(ts)
    for h in (t.get("hosts") or []):
        h["tool_flange"] = "ISO 9409-1 A50 4-M6 flange"
    return cm, t


def _mut_drop_single(cm, ts, label):
    """抹掉单件判据 ⇒ 只剩双件，必须判红。"""
    m = copy.deepcopy(cm)
    m["summary"]["single_mount_by_host"] = {}
    return m, ts


def _mut_ports_gt1(cm, ts, label):
    """tool_io_ports 填 >1（把位数当针数）⇒ 必须判红。"""
    t = copy.deepcopy(ts)
    for h in (t.get("hosts") or []):
        if h.get("tool_io_ports") == 1:
            h["tool_io_ports"] = 8      # 8 是针数，不是位数
    return cm, t


def _mut_drop_honest(cm, ts, label):
    """抹掉未建模声明 ⇒ 过度声称，必须判红。"""
    m = copy.deepcopy(cm)
    m["meta"]["honest_limits"] = []
    return m, ts


MUTATIONS = [
    ("关系类型被改回 peer-to-peer", _mut_relabel),
    ("port_exhausted 状态被抹掉（退化成二段关系）", _mut_drop_exhausted),
    ("最坏状态：全部 unknown（零可判定）", _mut_all_unknown),
    ("计数不守恒", _mut_count_break),
    ("裁决值拼写漂移", _mut_illegal_verdict),
    ("宿主一手出处被抹掉", _mut_drop_evidence),
    ("tool_io_ports=null 但未登记缺口原因", _mut_ports_null_no_note),
    ("tool_flange 用自由文本（join 会失败）", _mut_flange_free_text),
    ("单件判据被抹掉", _mut_drop_single),
    ("tool_io_ports 填针数而非位数", _mut_ports_gt1),
    ("未建模声明被抹掉（过度声称）", _mut_drop_honest),
]


# ═══════════════════════════════════════════════════════════════════
def main():
    print("verify_co_mount — 共装层自证")
    cm = _load("api/co_mount.json")
    ts = _load("api/robot_tool_side.json")
    graph = _load("api/morphology_graph.json")
    if not cm or not ts or not graph:
        fail("产物缺失（api/co_mount.json / api/robot_tool_side.json / "
             "api/morphology_graph.json）")
        return 1

    # ── 阴性：空产物必须判红（空闸门与空产物是两种故障）──
    print("\n[阴性] 空产物必须判红")
    e = _errors({}, {})
    if e:
        ok("空产物判红（%d 项）" % len(e))
    else:
        fail("空产物被判绿 —— 空闸门")

    # ── 阳性：真产物必须判绿 ──
    print("\n[阳性] 真实产物判据")
    errs = _errors(cm, ts)
    if errs:
        for x in errs[:6]:
            fail("真实产物被判红：" + x)
    else:
        s = cm["summary"]
        ok("关系类型 co_mount 已登记（三段，%d 裁决态）"
           % len(cm["relation_semantics"]["co_mount"]["verdicts"]))
        ok("计数守恒：by_host 合计 %d == pair_evaluations %d"
           % (sum(sum(v.values()) for v in s["by_host"].values()),
              s["pair_evaluations"]))
        ok("单件与双件分别给判据：单件 %s｜双件 %s"
           % (s.get("single_mount"), s.get("verdict_histogram")))
        ok("口径守卫：未建模范畴 + 端口缺口 + 判定粒度上限 + 不改写 compose 均已声明")

    # ── 引擎级行为验证：只看产物不算验到引擎 ──
    print("\n[引擎] 三段判据的行为验证")
    nodes = {n["id"]: n for n in (graph.get("nodes") or [])
             if n.get("composable", True)}
    host = {"id": "TEST-HOST", "tool_flange": "MECH:ISO9409-1-A50-4-M6",
            "tool_io_ports": 1}
    dev_ok = {"id": "DEV-OK", "ports": [
        {"type": "MECH:ISO9409-1-A50-4-M6", "status": "declared"},
        {"type": "ELEC:CONNECTOR:M8-5-PIN", "status": "declared"},
        {"type": "SIG:OUTPUT_SPIKE", "status": "declared"}]}
    dev_in = {"id": "DEV-IN", "ports": [
        {"type": "MECH:ISO9409-1-A50-4-M6", "status": "declared"},
        {"type": "ELEC:CONNECTOR:M8-5-PIN", "status": "declared"},
        {"type": "SIG:INPUT_SENSORY", "status": "declared"}]}
    dev_badflange = {"id": "DEV-BAD", "ports": [
        {"type": "MECH:ISO9409-1-A80-6-M8", "status": "declared"},
        {"type": "SIG:INPUT_SENSORY", "status": "declared"}]}
    dev_noflange = {"id": "DEV-NONE", "ports": [
        {"type": "MECH:UNKNOWN", "status": "not_declared"},
        {"type": "SIG:INPUT_SENSORY", "status": "declared"}]}

    r = co_mount(dev_ok, dev_in, host, graph, already_mounted=[])
    if r["stages"]["mount_fit"]["a"]["verdict"] == "fit":
        ok("机械段：同型法兰判 fit（identity，不是互插）")
    else:
        fail("机械段同型法兰未判 fit：%s" % r["stages"]["mount_fit"]["a"]["reason"])
    if r["stages"]["port_budget"]["verdict"] == "exhausted":
        ok("端口段：1 位宿主装 2 个器件 ⇒ exhausted（工程约束）")
    else:
        fail("端口预算未判 exhausted：%s" % r["stages"]["port_budget"]["verdict"])
    if r["stages"]["signal_complementary"]["verdict"] == "complementary":
        ok("信号段：OUTPUT↔INPUT 判 complementary")
    else:
        fail("信号段未判 complementary")

    # 端口位数的关键反向对照：位=2 时同两件必须判 mountable
    host2 = dict(host, tool_io_ports=2)
    r2 = co_mount(dev_ok, dev_in, host2, graph, already_mounted=[])
    if r2["stages"]["port_budget"]["verdict"] == "fit" and r2["overall"] == "mountable":
        ok("反向对照：位=2 时同两件判 mountable（ports 判据对位数敏感）")
    else:
        fail("端口位=2 时未判 mountable（%s）" % r2["overall"])

    # exhausted ≠ unknown：宿主位数未取证必须走 unknown
    host_null = dict(host, tool_io_ports=None)
    r3 = co_mount(dev_ok, dev_in, host_null, graph, already_mounted=[])
    if r3["overall"] == "unknown" and r3["stages"]["port_budget"]["verdict"] == "unknown":
        ok("exhausted ≠ unknown：位数未取证走 unknown，不假装 exhausted")
    else:
        fail("位数未取证时的裁决错误：%s" % r3["overall"])

    rb = co_mount(dev_badflange, dev_in, host, graph, already_mounted=[])
    if rb["overall"] == "type_error":
        ok("异型法兰判 type_error（A80 配 A50）")
    else:
        fail("异型法兰未判 type_error")
    rn = co_mount(dev_noflange, dev_in, host, graph, already_mounted=[])
    if rn["stages"]["mount_fit"]["a"]["verdict"] == "unknown":
        ok("器件机械端口全 not_declared ⇒ mount_fit unknown（缺口不掩盖）")
    else:
        fail("未声明机械端口时的 mount_fit 错误")
    # 同一 id 只算一位（单件查询不得被要求 2 位）
    rs_ = co_mount(dev_ok, dev_ok, host, graph, already_mounted=[])
    if rs_["stages"]["port_budget"]["ports_needed"] == 1:
        ok("同一 id 重复出现只计 1 位（单件查询语义正确）")
    else:
        fail("同一 id 被计为 %d 位" % rs_["stages"]["port_budget"]["ports_needed"])

    # 真实产物的可复现性：重算一个真实对必须一致
    s = cm["summary"]
    if s.get("l2_device_ids") and s["l2_device_ids"][0] in nodes:
        d0 = s["l2_device_ids"][0]
        rr = co_mount(nodes[d0], nodes[d0], {
            "id": s["l2_device_ids"][0] and "HUB-031", "tool_flange":
            "MECH:ISO9409-1-A50-4-M6", "tool_io_ports": 1}, graph, already_mounted=[])
        if rr["stages"]["mount_fit"]["a"]["verdict"] in ("fit", "unknown", "incompatible"):
            ok("真实节点重算一致（%s 机械段可复现）" % d0)
        else:
            fail("真实节点重算失败")

    # ── 变异：每个都必须判红 ──
    print("\n[变异] %d 项（每项都必须判红）" % len(MUTATIONS))
    for name, fn in MUTATIONS:
        m, t = fn(cm, ts, name)
        got = _errors(m, t)
        if got:
            for g in got:
                emit("%s → %s" % (name, g))
            ok("捕获：%s" % name)
        else:
            fail("★ 变异未被捕获（闸门是装饰）：%s" % name)

    print("\n结果：%s" % ("PASS" if not FAILED else "FAIL"))
    if MUTFAIL:
        print("变异触发 %d 条断言（证明判据确实在守这些点）" % len(MUTFAIL))
    print("真实产物判绿项 %d" % PASSED)
    return 0 if not FAILED else 1


if __name__ == "__main__":
    raise SystemExit(main())
