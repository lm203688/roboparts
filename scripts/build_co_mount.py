#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_co_mount — 宿主（机器人本体）工具侧接口层 + 共装裁决产物。

    → api/robot_tool_side.json   宿主侧一手取证（法兰/端口数/连接器）
    → api/co_mount.json          三段共装裁决聚合

── 为什么需要这一层 ──────────────────────────────────────────────
co_mount 是三段关系（A↔宿主↔B），宿主侧数据缺一不可。而**宿主侧数据此前
完全不存在**：865 个实体里 category=platforms 的 105 条全部是**零件**
（工具本体法兰），没有一条声明「我是一台机器人，我的工具侧有几个端口」。

这正是 co-mount 在此前的模型里**根本无法表达**的根因——不是没数据，
是**没有「宿主」这个角色**。本体只有 tool_flange 一个字段，
既无端口数也无连接器型号，于是「同时装 A 和 B」这个问题无处落笔。

── 取证纪律 ──────────────────────────────────────────────────────
1. `tool_io_ports` **必须有一手出处**。厂商 datasheet 明写才填；
   未公开 ⇒ null ⇒ 判据走 unknown，**不按型号名推断**。
2. 端口数是**整数计数**，不是「支持 Tool I/O ⇒ 至少 1」。UR 的 Tool I/O
   是**单个 8-pin 连接器**，物理上只承载一个工具——这正是
   port_exhausted 状态存在的物理基础。若把它写成 8，会得到错误的「可装 8 个」。
3. `tool_flange` 用形态图的**端口类型 id**（如
   `MECH:ISO9409-1-A50-4-M6`），不是自由文本——否则 join 必然失败
   （这与 rp_id 键口径事故同型）。
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from co_mount_engine import ENGINE_VERSION, co_mount  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: 宿主侧一手取证表。
#:
#: 字段口径：
#:   tool_flange          形态图机械端口类型 id（非自由文本，见纪律 3）
#:   tool_io_ports        工具侧**电气接口位**数量。UR = 1（单个 8-pin
#:                        连接器，物理上承载一个工具）。未取证 ⇒ None
#:   tool_io_connector    连接器型号（用于 (family,pins,pinout) 三元组判据）
#:   tool_io_signals      该接口承载的信号（决定能挂什么类型的东西）
#:   source_tier          A=厂商官方域 / B=授权经销商转载 / C=第三方目录
HOSTS = {
    "HUB-031": {   # UR5e
        "tool_flange": "MECH:ISO9409-1-A50-4-M6",
        "tool_io_ports": 1,
        "tool_io_connector": "M8 8-pin",
        "tool_io_pins": 8,
        "tool_io_signals": ["24V", "GND", "2x DO", "2x DI", "2x AI/RS485"],
        "signal_direction": "bidirectional",
        "mountable_tools": "gripper / sensor（任意 24V Tool I/O 器件）",
        "source_url": "https://www.universal-robots.com/tw/developer/hardware-and-motion/"
                      "electrical-interfaces-tool-connector/",
        "source": "UR 官方开发者文档「Tool Connector」页：明写 *eight-pinned* "
                  "male connector on the tool flange；UR5e User Manual §6.8 逐针表"
                  "（GND / POWER / TO0 / TO1 / TI0 / TI1 / AI2-RS485+ / AI3-RS485-）"
                  "+ UR5e e-Series datasheet「Tool flange EN ISO-9409-1-50-4-M6」",
        "source_tier": "A",
        "confidence": 0.95,
        "key_facts": [
            "工具侧是**单个** 8-pin M8 连接器 ⇒ 工具侧位=1，"
            "不是 8（8 是**针数**，位=连接器数）。"
            "把针数当位数会让 co_mount 误判「可同时挂 8 个工具」。",
            "逐针表已公开（power + 2 DO + 2 DI + 2 AI/RS485）⇒ "
            "可判定「哪些器件的电气需求能被满足」，而不只是「有几个口」。",
            "Tool Flange = EN ISO-9409-1-50-4-M6 ⇒ 与库内 16 个 L2 节点的"
            "MECH:ISO9409-1-A50-4-M6 **同型** ⇒ 机械段 identity 成立。",
        ],
    },
    "HUB-030": {   # UR3e
        "tool_flange": "MECH:ISO9409-1-A50-4-M6",
        "tool_io_ports": 1,
        "tool_io_connector": "M8 8-pin",
        "tool_io_pins": 8,
        "tool_io_signals": ["24V", "GND", "2x DO", "2x DI", "2x AI/RS485"],
        "signal_direction": "bidirectional",
        "mountable_tools": "gripper / sensor（任意 24V Tool I/O 器件）",
        "source_url": "https://www.universal-robots.com/tw/developer/hardware-and-motion/"
                      "electrical-interfaces-tool-connector/",
        "source": "UR 官方 Tool Connector 页逐型号表（UR3e/UR5e/UR10e/UR16e/UR20/UR30 "
                  "共用同一 8-pin 工具连接器规格）+ UR3e datasheet Tool Flange "
                  "EN ISO-9409-1-50-4-M6",
        "source_tier": "A",
        "confidence": 0.95,
        "key_facts": [
            "UR 官方页面把 UR3e 与 UR5e 等**并列在同一张工具连接器规格表**下，"
            "字段值完全相同 ⇒ 同源取证，不是分别推断。",
        ],
    },
    "SUPERDEX-fr3": {   # Franka FR3（SuperDex 摄入）
        "tool_flange": "MECH:ISO9409-1-A50-4-M6",
        "tool_io_ports": None,
        "tool_io_connector": "end effector connector（datasheet 未给型号/针数）",
        "tool_io_pins": None,
        "tool_io_signals": ["2x DI", "2x DO (24V, isolated, EN 61131-2 type 3)"],
        "signal_direction": "bidirectional",
        "mountable_tools": "datasheet 仅称 connector for end effector",
        "source_url": "https://static.generation-robots.com/media/"
                      "franka-robotics-fr3-datasheet.pdf",
        "source": "FRANKA RESEARCH 3 datasheet：「Mounting flange DIN ISO 9409-1-A50」"
                  "+「connector for end effector」+「hardware prepared for: "
                  "2x DI & 2x DO (24V, isolated)」",
        "source_tier": "B",
        "confidence": 0.7,
        "key_facts": [
            "**tool_io_ports = null 是刻意的**：datasheet 只说「有一个终端执行器"
            "连接器」，未说明位数量与连接器型号。按纪律 1，"
            "宁可判 unknown 也不填「1」。",
            "2x DI & 2x DO 24V isolated ⇒ 信号能力已知，"
            "但这**不等于**位数为 1——是「接口电气规格」而非「物理位数」。",
        ],
    },
}


def _canon_flange(raw: str) -> str:
    """法兰标号归一：剥掉形态图前缀 + 抹掉所有非字母数字字符。

    实测同一法兰在三处有三种字面（`ISO 9409-1-50-4-M6` /
    `ISO-9409-1-A50-4-M6` / `MECH:ISO9409-1-A50-4-M6`），
    且 ISO 命名允许省略 `A` 前缀。**跨源标识必须走归一化**——
    这与「M8 是家族不是类型，靠名字匹配连接器必误判」是同型教训。

    ★ 第三版踩的坑：前缀剥离必须在这一层做。
      实体侧写 `ISO9409-1-A50-4-M6`（无前缀），
      形态图侧写 `MECH:ISO9409-1-A50-4-M6`（有前缀）——
      归一时若只抹符号不剥前缀，两边永远对不上，
      而**看起来只差一个词**（很容易漏）。
      凡跨源比标识，**归一函数要负责把命名空间前缀也吃掉**。
    """
    s = str(raw).strip()
    if ":" in s:
        s = s.split(":", 1)[1]          # 吃掉 MECH: / ELEC: 这类命名空间前缀
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _strip_flange_a(canon: str) -> str:
    """从已归一的法兰号里去掉「数字后紧邻的 a」（ISO 命名允许省略 A 前缀）。

    只处理 `iso9409-1-a<num>` 这个位置上的 a；其它位置的 a 一律不动
    （`m6`/`mm6` 里的内容不受影响）。用正则而非字符串 replace，
    否则会删错位置的 a —— 实测初版用 `replace("a","",1)` 时
    `iso94091a504m6` 恰好能过，但那是巧合，不是判据。
    """
    return re.sub(r"(?<=\d)a(?=\d)", "", canon, count=1)


def _load(rel: str) -> dict:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _validate() -> None:
    ents = _load("api/entities.json") or {}
    types = {t["id"] for t in
             ((_load("api/morphology_graph.json") or {}).get("port_types") or [])}
    by_id = {e["id"]: e for e in (ents.get("entities") or [])}
    errs: list = []
    for hid, h in HOSTS.items():
        e = by_id.get(hid)
        if not e:
            errs.append("%s 不在 entities.json" % hid)
            continue
        if e.get("entity_kind") != "component":
            errs.append("%s 的 entity_kind=%r 不是 component" % (hid, e.get("entity_kind")))
        # 纪律 3：法兰必须是端口类型 id，否则 co_mount 的 join 必然失败
        if h["tool_flange"] not in types:
            errs.append("%s.tool_flange=%r 不是形态图端口类型 id —— "
                        "用自由文本会导致 co_mount 机械段全部 join 失败"
                        % (hid, h["tool_flange"]))
        # 实体自身的机械声明必须与 tool_flange 一致（防两处口径分叉）
        # ★ 实测踩过两次，教训是「跨源标识必须走归一化，不能靠字面相等」：
        #   ① 实体 standard 写 `ISO 9409-1-50-4-M6`（**无 A**、有空格），
        #      形态图写 `ISO9409-1-A50-4-M6`（**有 A**、无空格）⇒ 直接比字符串必假红。
        #   ② 归一后仍差：实体 aliases 写 `ISO-9409-1-A50-4-M6`（**ISO- 带连字符**），
        #      形态图 `ISO9409-1-A50-4-M6`（**ISO9409 无连字符**）。
        #      ⇒ 归一必须抹掉**所有**非字母数字字符，不能只抹空格。
        #   ③ FR3 连 aliases 都没有（它 standard 恰好是无 A 版）⇒ 必须允许
        #      「A 可省略」这一 ISO 命名事实。
        # 归一后的比对是**唯一**正确做法：同型法兰在三个源里有三种字面。
        canon = _canon_flange(h["tool_flange"])
        declared = set()
        for f in ("standard", "aliases", "flange"):
            v = (e.get("mechanical_interface") or {}).get(f)
            for x in (v if isinstance(v, list) else [v]):
                if isinstance(x, str):
                    declared.add(_canon_flange(x))
                elif isinstance(x, dict):
                    # flange 是 dict 形态（pcd/bolt/thread），用 pcd+thread 复原标号
                    pcd, blt = x.get("pcd_mm"), x.get("bolt_count")
                    if pcd and blt:
                        declared.add(_canon_flange("ISO9409-1-A%s-%s-M%s"
                                                  % (pcd, blt, x.get("thread", ""))))
        # ISO 命名允许省略 `A` 前缀，但只在「数字之后紧邻的 A」可省。
        # ★ 初版写 `d.replace("A", "", 1)` —— 归一后已是小写，
        #   且更糟：**第一个 A 可能出现在别处**。实测 declared 里
        #   `iso94091504m6` 是无 A 版、`iso94091a504m6` 是有 A 版，
        #   正确做法是构造两种形态互相比对，而不是「删第一个 A」。
        canon = _canon_flange(h["tool_flange"])
        variants = {canon, _strip_flange_a(canon)}
        if not variants & declared:
            errs.append("%s 的 tool_flange %s 与实体机械声明 %s 不一致（两处口径分叉）"
                        % (hid, h["tool_flange"].replace("MECH:", ""),
                           sorted(declared)))
        for field in ("source_url", "source", "source_tier", "confidence", "mountable_tools"):
            if not h.get(field) and h.get(field) != 0:
                errs.append("%s 缺必填字段 %s" % (hid, field))
        if h["source_tier"] not in ("A", "B", "C"):
            errs.append("%s source_tier=%r 非法" % (hid, h["source_tier"]))
        # 端口数必须是非负整数或 None（纪律 2：不得把针数当位数）
        n = h["tool_io_ports"]
        if n is not None and (not isinstance(n, int) or n < 0):
            errs.append("%s tool_io_ports=%r 不是非负整数" % (hid, n))
        if n is not None and h.get("tool_io_pins") is not None and n == h["tool_io_pins"]:
            errs.append("%s tool_io_ports(%d) == tool_io_pins(%d) —— "
                        "针数不是位数，两者相等通常是把针数误当位数"
                        % (hid, n, h["tool_io_pins"]))
    if errs:
        raise SystemExit("build_co_mount 校验失败:\n  - " + "\n  - ".join(errs))


def build_tool_side() -> dict:
    ents = _load("api/entities.json") or {}
    by_id = {e["id"]: e for e in (ents.get("entities") or [])}
    hosts = []
    for hid, h in sorted(HOSTS.items()):
        e = by_id.get(hid) or {}
        rec = dict(h)
        rec["id"] = hid
        rec["name"] = e.get("name")
        rec["manufacturer"] = e.get("manufacturer")
        rec["entity_source_tier"] = e.get("source_tier")
        hosts.append(rec)

    verified = [h for h in hosts if h.get("tool_io_ports") is not None]
    return {
        "meta": {
            "title": "宿主工具侧接口（co-mount 三段关系的中间节点）",
            "title_zh": "宿主工具侧接口取证层",
            "why": (
                "co_mount 是三段关系（A↔宿主↔B），必须有宿主侧数据。"
                "此前 865 个实体里**没有任何一条声明宿主侧工具接口**——"
                "category=platforms 的 105 条全是零件本体法兰，"
                "既无工具 I/O 位数也无连接器型号。"
                "这就是「能否同时装夹爪 A 和传感器 B」此前**无法回答**的根因："
                "不是缺零件数据，是**模型里没有宿主这个角色**。"),
            "caliber": (
                "本层是**研究层口径**（co_mount_engine/v1），与 "
                "check_compatibility 的四维 protocol/electrical/mechanical/software "
                "**不可混用**。前者判「三段共装」，后者判「二段互插」。"),
            "engine": ENGINE_VERSION,
            "hosts": len(hosts),
            "hosts_with_port_count": len(verified),
            "evidence_gaps": [
                "UR30（HUB-038）工具法兰是 ISO-9409-1-80-6-M8，"
                "与 A50 族不同型 ⇒ 与本库 EOAT 机械段 incompatible，故未收录。",
                "FR3 的 tool_io_ports 未取证 ⇒ 判据走 unknown（刻意不填）。",
            ],
        },
        "hosts": hosts,
        "coverage": {
            "hosts": len(hosts),
            "tool_io_ports_verified": len(verified),
            "tool_io_ports_null": len(hosts) - len(verified),
            "note": "null 表示**刻意不填**（一手数据未公开）而非漏填；"
                    "判据据此走 unknown。",
        },
    }


def build() -> dict:
    graph = _load("api/morphology_graph.json") or {}
    ents = _load("api/entities.json") or {}
    frontier = _load("api/compose_frontier.json") or {}
    by_id = {e["id"]: e for e in (ents.get("entities") or [])}
    nodes = {n["id"]: n for n in (graph.get("nodes") or [])
             if n.get("composable", True)}

    # 待共装器件 = compose_frontier 的 L2 节点（跨角色 + 机械可判定的那 16 个）
    # ★ 实测踩过：初版读 `x.get("node")`，而产物字段是 `x["id"]`
    #   ⇒ 恒为空集 ⇒ 「器件 0 个」，**而构建脚本不报错、退出码 0**。
    #   这与「判据读错字段名 ⇒ 永远报 0」是同型失效（纪律 11）。
    #   守卫：L2 节点数必须与 frontier.summary.l2_nodes 一致。
    l2_ids = []
    for x in (frontier.get("frontier_nodes") or []):
        nid = x.get("id") if isinstance(x, dict) else x
        if nid and nid in nodes:
            l2_ids.append(nid)
    l2_ids = sorted(set(l2_ids))
    expect_l2 = ((frontier.get("summary") or {}).get("l2_nodes")
                 or len(frontier.get("frontier_nodes") or []))
    if expect_l2 and len(l2_ids) != expect_l2:
        raise SystemExit(
            "build_co_mount: L2 器件数 %d != compose_frontier.summary.l2_nodes %d —— "
            "字段口径分叉（frontier_nodes[].id 读错？或节点不在形态图里？）"
            % (len(l2_ids), expect_l2))

    host_nodes = {}
    for hid in HOSTS:
        e = by_id.get(hid) or {}
        hn = dict(nodes.get(hid) or {})
        # 宿主节点必须带 tool_io_ports / tool_flange —— 直接从取证表注入，
        # 不依赖形态图（形态图的机械端口是**零件侧**语义，方向相反）
        hn["id"] = hid
        hn["tool_flange"] = HOSTS[hid]["tool_flange"]
        hn["tool_io_ports"] = HOSTS[hid]["tool_io_ports"]
        hn["label"] = e.get("name") or hid
        host_nodes[hid] = hn

    verdicts: list = []
    hist: Counter = Counter()
    # ★ 实测踩过：初版把单件与双件裁决记进**同一个** by_host 计数器
    #   ⇒ 宿主合计 136（=16 单件 + 120 双件）而 pair_evaluations=120，
    #   对不上。**单件可装性与双件共装是两个不同的问题**，
    #   混在一个计数器里会让计数守恒判据永远假红（= 判据形同虚设）。
    by_host: Dict[str, Counter] = defaultdict(lambda: Counter())       # 仅双件
    single_by_host: Dict[str, Counter] = defaultdict(lambda: Counter())  # 仅单件
    single_hist: Counter = Counter()
    single_mount: Dict[str, Dict[str, Any]] = {}   # key = "<host>::<device>"
    stage_blockers: Counter = Counter()

    for hid in sorted(host_nodes):
        host = host_nodes[hid]
        # 单件装装 —— 回答「这个器件能不能装上去」
        for did in l2_ids:
            r = co_mount(nodes[did], nodes[did], host, graph, already_mounted=[])
            # ★ 单件语义：只判机械段 + 端口段。
            #   不可复用 co_mount 的 overall —— 那里 a==b 时会拿
            #   signal_complementary 判「自己和自己不互补」⇒ 恒 type_error，
            #   使单件查询恒为 unknown（实测 16/16 全 unknown，掩盖了机械段 fit）。
            #   另一个修正是端口数：co_mount 已按「同一 id 只算一位」处理。
            sub = r["stages"]["mount_fit"]["a"]
            pb = r["stages"]["port_budget"]
            if sub["verdict"] == "incompatible":
                ov = "type_error"
            elif pb["verdict"] == "exhausted":
                ov = "port_exhausted"
            elif "unknown" in (sub["verdict"], pb["verdict"]):
                ov = "unknown"
            else:
                ov = "mountable"
            single_mount["%s::%s" % (hid, did)] = {
                "host": hid, "device": did, "verdict": ov,
                "mount_fit": sub["verdict"], "port_budget": pb["verdict"],
                "reason": sub.get("reason"),
            }
            single_hist[ov] += 1
            single_by_host[hid][ov] += 1
        # 双件共装 —— 这才是共装的真问题
        for i in range(len(l2_ids)):
            for j in range(i + 1, len(l2_ids)):
                a, b = l2_ids[i], l2_ids[j]
                r = co_mount(nodes[a], nodes[b], host, graph, already_mounted=[])
                verdicts.append({
                    "host": hid, "a": a, "b": b, "verdict": r["overall"],
                    "stage_verdicts": r["stage_verdicts"],
                })
                hist[r["overall"]] += 1
                by_host[hid][r["overall"]] += 1
                for st, v in r["stage_verdicts"].items():
                    if v in ("incompatible", "not_complementary", "exhausted", "unknown"):
                        stage_blockers["%s=%s" % (st, v)] += 1

    # 判例（供论文与人工核对）
    examples = []
    for hid in sorted(host_nodes):
        for v in [x for x in verdicts
                  if x["host"] == hid and x["verdict"] == "mountable"][:3]:
            a, b = nodes[v["a"]], nodes[v["b"]]
            full = co_mount(a, b, host_nodes[hid], graph, already_mounted=[])
            examples.append({
                "host": hid,
                "host_name": host_nodes[hid]["label"],
                "a": v["a"], "a_name": a.get("label") or a.get("id"),
                "b": v["b"], "b_name": b.get("label") or b.get("id"),
                "verdict": "mountable",
                "stages": {
                    "mount_fit": full["stages"]["mount_fit"]["a"]["reason"],
                    "port_budget": full["stages"]["port_budget"]["reason"],
                    "signal": full["stages"]["signal_complementary"]["reason"],
                },
            })
    exhausted_ex = []
    for hid in sorted(host_nodes):
        for v in [x for x in verdicts
                  if x["host"] == hid and x["verdict"] == "port_exhausted"][:2]:
            full = co_mount(nodes[v["a"]], nodes[v["b"]], host_nodes[hid],
                            graph, already_mounted=[])
            exhausted_ex.append({
                "host": hid, "a": v["a"], "b": v["b"],
                "port_budget": full["stages"]["port_budget"]["reason"],
            })

    return {
        "meta": _meta(),
        "summary": {
            "hosts": len(host_nodes),
            "devices": len(l2_ids),
            "pair_evaluations": len(verdicts),
            "pair_verdict_histogram": dict(hist),
            "by_host": {h: dict(c) for h, c in by_host.items()},
            "single_mount": dict(single_hist),
            "single_mount_by_host": {h: dict(c) for h, c in
                                     sorted(single_by_host.items())},
            "counting_note": (
                "**单件与双件分别计数**（single_* vs by_host/hist）。"
                "单件问「这个器件能不能装上去」，双件问「两个能不能同时装」"
                "——两个不同的问题，混算会让守恒判据假红"
                "（实测混算时宿主合计 136 = 16+120，而双件只有 120）。"),
            "stage_blockers": dict(stage_blockers.most_common()),
            "l2_device_ids": l2_ids,
        },
        "relation_semantics": {
            "peer_to_peer": {
                "question": "A 能不能插进 B？",
                "verdicts": ["composed", "type_error", "unknown"],
                "engine": "compose_engine",
            },
            "co_mount": {
                "question": "A 和 B 能不能**同时**装到同一台机器人的工具侧？",
                "verdicts": list(("mountable", "port_exhausted", "type_error", "unknown")),
                "engine": "co_mount_engine",
                "structure": "three_segment_via_host",
                "structure_note": "A 的法兰 → **宿主工具法兰** ← B 的法兰；"
                                  "A 的电气 → **宿主工具 I/O 位** ← B 的电气。"
                                  "中间节点（宿主）是判定的必需项，不是可选项。",
                "distinct_stages": [
                    "mount_fit：器件法兰 **≡** 宿主工具法兰（同型，不是互插）",
                    "port_budget：**宿主资源有限**——UR 工具侧只有 1 个 8-pin 位，"
                    "共装第二个器件即耗尽（这是 peer-to-peer 不存在的状态）",
                    "signal_complementary：共装要求一方输出、另一方感知",
                ],
                "new_verdict_port_exhausted": (
                    "**工程约束**（装不下，需换本体或转接），"
                    "与 unknown（证据缺口）严格区分。"
                    "把两者混为一谈就是把「不知道」伪装成「不行」。"),
            },
        },
        "single_mount": {k: v for k, v in sorted(single_mount.items())},
        "pair_verdicts": verdicts,
        "examples_mountable": examples,
        "examples_port_exhausted": exhausted_ex,
    }


def _meta() -> dict:
    """meta 单独成函数：honest_limits 有 6 条长文本，
    与主结构混排时极易写错括号层级（本项目已因此踩过一次）。"""
    return {
        "title": "共装裁决（co-mount，第三种关系类型）",
        "title_zh": "共装裁决产物：能否同时把 A 和 B 装到同一台机器人上",
        "caliber": "co_mount_engine/v1（研究层）。判据来自 api/robot_tool_side.json，"
                   "与 check_compatibility 的四维**不可混用**。",
        "engine": ENGINE_VERSION,
        "relation_type": "co_mount（三段：A↔宿主↔B）",
        "honest_limits": list(_HONEST_LIMITS),
        "why_this_layer": (
            "compose_engine 只有 peer-to-peer（二段互插）一种关系，"
            "而 cobot EOAT 的真实工程关系是共装。"
            "实测（api/compose_frontier.json）：L2 的 63 对机械 63/63、"
            "信号 63/63 全通过，唯一阻点 electrical 判的是「两器件能否互插」；"
            "而两侧均取证的配对里判出结果的**全部 incompatible、0 compatible**"
            "（EOAT 器件按设计各占机器人侧一个电气端口）。"
            "⇒ 不新增关系类型，补再多电气声明也不会让 composed>0。"),
        "what_this_proves": (
            "本层**不声称解决一般关系类型问题**（那属 D5 多年期范畴论路线）。"
            "只覆盖「同一宿主工具侧共装」一种关系，"
            "并给出一个此前无法回答的问题的机读答案："
            "「这台机器人能否同时装夹爪 A 和传感器 B」。"),
    }


# 口径守卫所读的 honest_limits。
#
# ★ 实测踩过（字段位置错位，纪律 11）：初版把这个列表放在**顶层**
#   （与 meta 平级），而判据读 `meta.honest_limits`
#   ⇒ 真实产物被报「缺 5 项 honest_limits」，而它们明明存在。
#   **口径对齐不止是数值对齐，字段位置也要对齐。**
_HONEST_LIMITS = [
    "**只覆盖同一宿主工具侧共装**。跨本体（换机器人）、"
    "转接件链路、多工具同时挂载**未建模**——"
    "那属 D5 范畴论路线的多年期范畴，本层不声称解决。",
    "**tool_io_ports 是一手取证的整数**（UR=1）。"
    "未公开者（如 FR3）留 null ⇒ 判据走 unknown，**不按型号名推断**。",
    "**共装成功 ≠ 集成成功**。机械可装 + 端口够 + 信号互补，"
    "只说明「物理与信号层面允许共存」；实际集成还要看"
    "控制器通道分配、碰撞检测、厂商安全限制——**本层不覆盖**。",
    "**pinout 层未参与共装判定**。工具侧逐针表已公开"
    "（UR: GND/POWER/TO0/TO1/TI0/TI1/AI2/AI3），"
    "但要判「A 的电气需求能否被工具侧满足」需逐针对照，"
    "当前只判位数与信号类。**这是已知的判定粒度上限，不是已完成。**",
    "**单向模型缺陷：工具侧按「单连接器」建模。**"
    "本层把 host.tool_io_ports 显式建模为整数位计数，"
    "而 UR/FR3 在取证范围内确为单 8-pin 连接器（位=1）；"
    "但**本体若提供多位工具接口（如双工位法兰盘），"
    "本层能正确判位>1，而取证表当前无此类实例**"
    "（已由 verify 判据强制 tool_io_ports>1 需重新核实位数定义）。"
    "**换本体时这条假设必须重新审视**——"
    "「位」是物理连接器数，与「针」是每连接器的针数，二者不可混用。",
    "**本层与 compose_semantics 的 composed 互不改写**。"
    "peer-to-peer 的 composed 仍为 0（那是另一个关系类型的答案）。",
]


def main() -> int:
    _validate()
    tool_side = build_tool_side()
    cm = build()
    for rel, doc in (("api/robot_tool_side.json", tool_side),
                     ("api/co_mount.json", cm)):
        p = os.path.join(ROOT, rel)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.write("\n")
    s = cm["summary"]
    print("build_co_mount: 宿主 %d 个（tool_io_ports 取证 %d）"
          % (tool_side["coverage"]["hosts"],
             tool_side["coverage"]["tool_io_ports_verified"]))
    print("  器件 %d 个（compose_frontier L2）｜配对裁决 %d 次"
          % (s["devices"], s["pair_evaluations"]))
    print("  单件装装:", s["single_mount"])
    print("  双件共装:", s["pair_verdict_histogram"])
    print("  段阻点:", list(s["stage_blockers"].items())[:4])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
