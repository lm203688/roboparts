#!/usr/bin/env python3
"""derive_replacement_classes.py — 可替换等价类推导（只读审计）

从 api/morphology_graph.json 的 type_compat 现算，输出三层结论：

  1. 端口型层「无适配直换类」：identity 边的连通分量闭包。
     同类的两个端口型直接互替，无需适配器。

  2. 端口型层「单适配可达类」：identity ∪ adapter_required 的连通分量。
     同类可通过至多一个适配器（或直接）互替；这层才是「替换池」。

  3. 实体层投影：把实体经 mechanical_interface / nodes.ports 投影到端口型，
     再归入其适配等价类，得到「给定零件 → 可互替实体集合」。

  4. unknown 三态化审计：对 verdict==unknown 的配对，施加严格判定规则
     （机械看两端几何、电气看两端 pins/family/variant/pinout），
     可判才判；其余如实报告为「数据缺口不可判」，并给出缺口成因分布，
     便于补齐 pinout/geometry 后重跑。**绝不臆断**。

【纪律】
- 只读：绝不写 api/*.json；无 --apply，无任何写回动作。
- 幂等：同输入产出字节一致（排序固定）。
- 不发明：无规格证据即判「数据缺口」，不替厂商或标准发明条目（L1.77）。
- 与 refresh_designations_in_use.py 同一归一化口径（去空格、大写、删 '-A-'）。
- 与 grammar.designation_forms.normalize_rule 交叉一致。

【用法】
    python scripts/derive_replacement_classes.py                 # 审计报告到 stdout
    python scripts/derive_replacement_classes.py --out ops/      # 同时把 JSON 报告写进目录
    python scripts/derive_replacement_classes.py --tri-state     # 只跑 unknown 三态化审计

【输出】
    默认仅 stdout 人类可读报告；--out DIR 额外写 DIR/derive_replacement_classes.json。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(ROOT, "api", "morphology_graph.json")
ENTITIES = os.path.join(ROOT, "api", "entities.json")

# 归一化：去空格、大写、删尺寸段前的 'A' 前缀（与 refresh_designations_in_use.py 同口径）
TOK_RE = re.compile(r"^ISO9409-1-(\d+(?:\.\d+)?)-(\d+)-M(\d+)$")
BARE_RE = re.compile(r"^ISO9409-1$")


def normalize(s: Any) -> str:
    return re.sub(r"ISO9409-1-A", "ISO9409-1-", str(s).upper().replace(" ", ""))


def read_json(path: str) -> Any:
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def token_to_port_type(token: Any, reverse_index: Dict[str, str]) -> Optional[str]:
    """实体标号/法兰字典 -> 端口型 id。reverse_index: 去 MECH: 与 '-A-' 的端口型 token 索引。

    - 结构化法兰字典 {pcd_mm, bolt_count, thread, mount_type} -> MECH:ISO9409-1-A{pcd}-{bolt}-{thread}
    - 字符串标号 'ISO 9409-1-50-4-M6' -> 反查
    - 裸 PCD 字符串 '50mm'（缺 bolt/thread）-> None（规格不全，如实记为不可解析）
    """
    if isinstance(token, dict):
        pcd = token.get("pcd_mm")
        bolt = token.get("bolt_count")
        thread = token.get("thread")
        if pcd is not None and bolt is not None and thread:
            return "MECH:ISO9409-1-A{}-{}-{}".format(pcd, bolt, thread)
        return None
    if not isinstance(token, str):
        return None
    norm = normalize(token)
    # 裸标号：只有标准号、无尺寸
    if BARE_RE.match(norm):
        return reverse_index.get("ISO9409-1-BARE")
    if TOK_RE.match(norm):
        return reverse_index.get(norm)
    # 非 ISO 形式：直接反查（如机械法兰的其它命名）
    return reverse_index.get(norm)


def build_reverse_index(port_types: List[Dict[str, Any]]) -> Dict[str, str]:
    idx: Dict[str, str] = {}
    for p in port_types:
        pid = p.get("id") or ""
        if p.get("axis") == "mechanical" and pid.startswith("MECH:"):
            key = pid[len("MECH:"):]
            # 端口型是 MECH:ISO9409-1-A50-4-M6 -> key 去 '-A-' 得 ISO9409-1-50-4-M6
            idx.setdefault(normalize(key), pid)
            idx.setdefault(normalize(pid), pid)  # 带 MECH: 前缀也兜底
        else:
            idx.setdefault(normalize(pid), pid)
    return idx


def connected_components(nodes: Set[str], edges: List[Tuple[str, str]]) -> List[Set[str]]:
    """无向连通分量。nodes 之外的端点自动并入（防御悬空边）。"""
    adj: Dict[str, Set[str]] = defaultdict(set)
    for a, b in edges:
        if a == b:
            continue
        adj[a].add(b)
        adj[b].add(a)
    seen: Set[str] = set()
    comps: List[Set[str]] = []
    for start in sorted(nodes):
        if start in seen:
            continue
        stack = [start]
        comp: Set[str] = set()
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp.add(x)
            for y in adj.get(x, ()):  # type: ignore[arg-type]
                if y not in seen:
                    stack.append(y)
        comps.append(comp)
    return comps


def geometry_of(p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    g = p.get("geometry")
    return g if isinstance(g, dict) else None


def mech_geom_signature(p: Dict[str, Any]) -> Optional[str]:
    g = geometry_of(p)
    if not g:
        return None
    parts = []
    for k in ("pcd_mm", "outer_diameter_mm", "holes", "thread", "bolt_count", "mount_type"):
        if g.get(k) is not None:
            parts.append(f"{k}={g[k]}")
    return "|".join(parts) if parts else None


def tri_state_unknown(e: Dict[str, Any],
                      pa: Dict[str, Any],
                      pb: Dict[str, Any]) -> Tuple[str, Optional[str], str]:
    """返回 (可判?, verdict?, 缺口成因)。

    严格规则：
      - 机械：两端几何齐备才判；几何签名相等->identity，不等->incompatible（法兰无适配器）。
      - 电气：两端 pins+family 齐备才判；同 family 同 pins 同 variant 同 pinout -> identity；
              同 family 不同 pins -> adapter_required（如 M8 3->4 针适配器）；不同 family -> incompatible。
              其余（缺 pinout / variant 分歧 / 缺 spec）-> 数据缺口。
      - signal/reward：非点对点接口，不参与组合判定。
    """
    axis = e.get("axis", "")
    if axis == "mechanical":
        sa, sb = mech_geom_signature(pa), mech_geom_signature(pb)
        if sa is not None and sb is not None:
            return ("decidable", "identity" if sa == sb else "incompatible", "")
        if sa is None or sb is None:
            return ("undecidable", None, "mechanical_geom_gap(至少一侧无几何，专有/裸标号)")
        return ("undecidable", None, "mechanical_geom_gap")
    if axis == "electrical":
        pa_pins, pb_pins = pa.get("pins"), pb.get("pins")
        pa_fam, pb_fam = pa.get("family"), pb.get("family")
        if pa_pins and pb_pins and pa_fam and pb_fam:
            if pa_fam != pb_fam:
                return ("decidable", "incompatible", "")
            if pa_pins != pb_pins:
                return ("decidable", "adapter_required", "")
            # 同 family 同 pins：需 variant + pinout 才能定 identity
            if (pa.get("variant") == pb.get("variant")
                    and pa.get("pinout") and pb.get("pinout")
                    and pa.get("pinout") == pb.get("pinout")):
                return ("decidable", "identity", "")
            return ("undecidable", None, "electrical_variant_pinout_gap(同 family 同 pins 但 variant/pinout 未定)")
        return ("undecidable", None, "electrical_spec_gap(缺 pins 或 family)")
    return ("undecidable", None, "non_point_to_point(reward/信号映射，非点对点接口)")


def entity_port_types(entity: Dict[str, Any], reverse_index: Dict[str, str]) -> List[str]:
    """实体 -> 端口型集合。优先 nodes.ports，回退 mechanical_interface 标号解析。"""
    found: List[str] = []
    mi = entity.get("mechanical_interface") or {}
    for key in ("standard", "flange", "tool_side", "tool_side_flange"):
        v = mi.get(key)
        if not v:
            continue
        vals = v if isinstance(v, list) else [v]
        for tok in vals:
            pt = token_to_port_type(tok, reverse_index)
            if pt:
                found.append(pt)
    return sorted(set(found))


def flange_port_types(entity: Dict[str, Any], reverse_index: Dict[str, str]) -> List[str]:
    """实体法兰专用投影：只用 flange / tool_side_flange 字段。

    对应 handoff 的 HUB 池主张：带结构化法兰的实体 -> 机械法兰端口型。
    """
    found: List[str] = []
    mi = entity.get("mechanical_interface") or {}
    for key in ("flange", "tool_side_flange"):
        v = mi.get(key)
        if not v:
            continue
        vals = v if isinstance(v, list) else [v]
        for tok in vals:
            pt = token_to_port_type(tok, reverse_index)
            if pt:
                found.append(pt)
    return sorted(set(found))


def main() -> int:
    ap = argparse.ArgumentParser(description="推导可替换等价类（只读审计）")
    ap.add_argument("--out", metavar="DIR", default=None,
                    help="额外把 JSON 报告写入该目录（不写 api/*.json）")
    ap.add_argument("--tri-state", action="store_true",
                    help="只运行 unknown 三态化审计")
    args = ap.parse_args()

    graph = read_json(GRAPH)
    ents_doc = read_json(ENTITIES)
    ents = ents_doc.get("entities") or []

    port_types = graph.get("port_types") or []
    type_compat = graph.get("type_compat") or []
    nodes = graph.get("nodes") or []

    pt_by_id = {p["id"]: p for p in port_types}
    reverse_index = build_reverse_index(port_types)

    # ---- 1. 四态分布 ----
    verdicts = Counter(e.get("verdict") for e in type_compat)

    # ---- 2. 端口型层等价类 ----
    port_ids = set(pt_by_id.keys())
    identity_edges: List[Tuple[str, str]] = []
    adapter_edges: List[Tuple[str, str]] = []
    for e in type_compat:
        v = e.get("verdict")
        a, b = e.get("a"), e.get("b")
        if not a or not b:
            continue
        if v == "identity":
            identity_edges.append((a, b))
            adapter_edges.append((a, b))
        elif v == "adapter_required":
            adapter_edges.append((a, b))

    id_classes = connected_components(port_ids, identity_edges)
    ad_classes = connected_components(port_ids, adapter_edges)

    # 多型适配类（>1 端口型）才是有意义的替换池
    multi_ad = [c for c in ad_classes if len(c) > 1]

    # ---- 3. 实体投影 ----
    # 实体端口型：优先 nodes.ports[].type（形态图节点自带），回退 mechanical_interface 解析
    node_ports: Dict[str, List[str]] = {}
    for n in nodes:
        nid = n.get("id") or n.get("entity_id")
        if not nid:
            continue
        ports = n.get("ports") or []
        ptypes = [p.get("type") for p in ports if isinstance(p, dict) and p.get("type")]
        node_ports[nid] = ptypes

    # 实体 -> 适配类标签
    entity_class: Dict[str, str] = {}
    for ent in ents:
        eid = ent.get("id")
        if not eid:
            continue
        pts = node_ports.get(eid) or entity_port_types(ent, reverse_index)
        for pt in pts:
            if pt in pt_by_id:
                # 找 pt 所属的适配等价类（含单元素类）
                for i, comp in enumerate(ad_classes):
                    if pt in comp:
                        entity_class[eid] = f"adapter_class_{i}"
                        break
                break  # 一个实体取首个可解析端口型即可（机械法兰单值场景）

    # ---- 3b. 法兰专用投影（handoff 的 HUB 池主张）----
    # 只用机械法兰字段，看带法兰的实体是否落入同一个适配等价类
    flange_class: Dict[str, str] = {}
    flange_unparse = []
    for ent in ents:
        eid = ent.get("id")
        if not eid:
            continue
        pts = flange_port_types(ent, reverse_index)
        if pts:
            pt = pts[0]
            if pt in pt_by_id:
                for i, comp in enumerate(ad_classes):
                    if pt in comp:
                        flange_class[eid] = f"adapter_class_{i}"
                        break
        elif any((ent.get("mechanical_interface") or {}).get(k)
                 for k in ("flange", "tool_side_flange")):
            # 有法兰字段但解析不出（裸 PCD 缺 bolt/thread 等）
            flange_unparse.append(eid)

    # ---- 4. unknown 三态化审计 ----
    unk = [e for e in type_compat if e.get("verdict") == "unknown"]
    dec = []
    undec = []
    for e in unk:
        pa = pt_by_id.get(e.get("a"))
        pb = pt_by_id.get(e.get("b"))
        if pa is None or pb is None:
            undec.append((e, "端点缺失"))
            continue
        kind, verdict, gap = tri_state_unknown(e, pa, pb)
        if kind == "decidable":
            dec.append((e, verdict))
        else:
            undec.append((e, gap))
    gap_counter = Counter(gap for _, gap in undec)

    report = {
        "inputs": {
            "morphology_graph": "api/morphology_graph.json",
            "entities": "api/entities.json",
            "entities_count": len(ents),
            "port_type_count": len(port_types),
            "type_compat_count": len(type_compat),
        },
        "verdict_distribution": dict(verdicts),
        "identity_class_count": len(id_classes),
        "identity_classes_multi": [sorted(c) for c in id_classes if len(c) > 1],
        "adapter_class_count": len(ad_classes),
        "adapter_classes_multi": [sorted(c) for c in multi_ad],
        "entity_projection": {
            "entities_typed": len(entity_class),
            "pool_by_class": {
                cls: sorted([eid for eid, c in entity_class.items() if c == cls])
                for cls in sorted(set(entity_class.values()))
            },
        },
        "flange_projection": {
            "entities_with_flange_typed": len(flange_class),
            "entities_flange_unparseable": flange_unparse,
            "pool_by_class": {
                cls: sorted([eid for eid, c in flange_class.items() if c == cls])
                for cls in sorted(set(flange_class.values()))
            },
            "n_pools": len(set(flange_class.values())),
        },
        "unknown_tristate_audit": {
            "unknown_total": len(unk),
            "decidable": [{"a": e["a"], "b": e["b"], "verdict": v} for e, v in dec],
            "decidable_count": len(dec),
            "undecidable_count": len(undec),
            "gap_reason_counts": dict(gap_counter),
        },
    }

    if args.tri_state:
        print(f"[tri-state] unknown={len(unk)} 可判={len(dec)} 不可判={len(undec)}")
        for reason, n in gap_counter.most_common():
            print(f"  {n:>4}  {reason}")
        print("  结论：数据缺口非可解歧义。补齐 pinout/geometry 后重跑本脚本即可判定。")
    else:
        print(f"[type_compat] 四态分布: {dict(verdicts)}")
        print(f"[classes] 无适配直换类={len(id_classes)}（多型={sum(1 for c in id_classes if len(c)>1)}） "
              f"单适配可达类={len(ad_classes)}（多型={len(multi_ad)}）")
        for c in multi_ad:
            print(f"  [adapter class] {len(c)} 型: {' | '.join(sorted(c))}")
        print(f"[entities] 可解析端口型实体={len(entity_class)}/{len(ents)}")
        for cls in sorted(set(entity_class.values())):
            members = sorted(eid for eid, c in entity_class.items() if c == cls)
            print(f"  [pool {cls}] {len(members)} 实体: {', '.join(members[:8])}{' ...' if len(members)>8 else ''}")
        print(f"[tri-state] unknown={len(unk)} 可判={len(dec)} 不可判={len(undec)}")
        for reason, n in gap_counter.most_common():
            print(f"  {n:>4}  {reason}")

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        dest = os.path.join(args.out, "derive_replacement_classes.json")
        with io.open(dest, "w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"written -> {os.path.relpath(dest, ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
