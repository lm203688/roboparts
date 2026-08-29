#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill_platform_flanges.py — 路线 X·扩面
把 mechanical_interfaces.json 的 flange_designations.known_hosts（已核实的机器人臂平台）
回填为 platforms.json 一级实体，挂上对应 ISO 9409-1 机械接口。
只用知识库内已核实数据（OEM 证据 URL 优先），不编造。幂等：同名跳过。
"""
import json, re, datetime, sys

MI = "api/mechanical_interfaces.json"
PF = "api/platforms.json"

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def save(p, o):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=2)

def main():
    apply = "--apply" in sys.argv
    mi = load(MI)
    pf = load(PF)
    data = pf.get("data", [])
    existing = { (x.get("name") or "").strip().lower() for x in data }

    def manu(name):
        if name.startswith("ABB"): return "ABB"
        if name.startswith("Universal Robots"): return "Universal Robots"
        return "未知"

    added = []
    for d in mi.get("flange_designations", []):
        desig = d["id"]  # e.g. ISO9409-1-A50-4-M6
        rest = desig.split("ISO9409-1-", 1)[1] if "ISO9409-1-" in desig else desig
        std = "ISO 9409-1-" + rest
        # std like "ISO 9409-1-A50-4-M6"
        hosts = d.get("known_hosts", [])
        ev = { (e.get("host") or "").strip().lower(): e for e in (d.get("known_hosts_evidence") or []) }
        for h in hosts:
            if h.strip().lower() in existing:
                continue
            e = ev.get(h.strip().lower(), {})
            src_url = e.get("source_url") or d.get("source_url")
            tier = e.get("source_tier") or d.get("source_tier") or "B"
            basis = e.get("source_tier_basis") or d.get("source_tier_basis") or "known_host_compilation"
            entry = {
                "id": "RARM-%03d" % (len(data) + len(added) + 1),
                "name": h,
                "name_en": h,
                "type": "robot arm platform (tool flange declared)",
                "description": "%s 机械臂平台，工具法兰符合 %s（PCD %smm / %s孔 / %s）。" % (
                    h, std, d.get("d1_mm"), d.get("bolt_count"), d.get("thread")),
                "manufacturer": manu(h),
                "category": "platforms",
                "verified": bool(src_url),
                "data_quality": "ok",
                "quarantine": False,
                "source": (e.get("source") or d.get("source") or "flange registry known_hosts"),
                "source_url": src_url,
                "source_tier": tier,
                "confidence": float(d.get("confidence", 0.8)),
                "confidence_basis": basis,
                "last_verified": datetime.date.today().isoformat(),
                "standard_conformance": {
                    "assessed": False, "bus_class": "unknown", "ros2": None,
                    "interop_stack_20262893": "unknown", "caee060_relevant": True,
                    "interop_posture": "unknown", "iso22166_relevant": True,
                },
                "mechanical_interface": {
                    "status": "declared",
                    "mount_type": "flange_mount",
                    "standard": [std],
                    "flange": {
                        "pcd_mm": d.get("d1_mm"),
                        "bolt_count": d.get("bolt_count"),
                        "thread": d.get("thread"),
                        "dowel_holes": d.get("dowel_holes"),
                        "mount_type": "flange_mount",
                    },
                    "source": e.get("quote") or d.get("source"),
                    "source_url": src_url,
                    "source_tier": tier,
                },
                "entity_kind": "component",
            }
            added.append(entry)

    print("would add:", len(added))
    for a in added:
        print("  +", a["name"], "->", a["mechanical_interface"]["standard"][0], "(tier %s)" % a["source_tier"])
    if not apply:
        print("DRY-RUN")
        return
    data.extend(added)
    pf["data"] = data
    pf["count"] = len(data)
    pf["updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    save(PF, pf)
    print("APPLIED. platforms now:", len(data))

if __name__ == "__main__":
    main()
