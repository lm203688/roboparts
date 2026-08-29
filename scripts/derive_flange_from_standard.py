#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
derive_flange_from_standard.py
路线 X·派生层：把已声明 ISO 9409-1 标准的零件，自动补上法兰几何（pcd/bolt/thread/dowel）。
不编造：仅当 mechanical_interface.standard 含 ISO 9409-1 代码、且 flange 为 null 时才派生。
复用 api/mechanical_interfaces.json 的 flange_designations 知识库（含 OEM 证据）。
"""
import json, re, sys

E_PATH = "api/entities.json"
MI_PATH = "api/mechanical_interfaces.json"
CODE_RE = re.compile(r"9409-1-(\d+(?:\.\d+)?)-(\d+)-M(\d+)", re.I)

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def main():
    apply = "--apply" in sys.argv
    ents = load(E_PATH)
    mi = load(MI_PATH)
    fd = mi.get("flange_designations", [])
    # 知识库： (d1, bolts, thread) -> designation
    kb = {}
    for d in fd:
        key = (d.get("d1_mm"), d.get("bolt_count"), d.get("thread"))
        kb[key] = d

    lifted = 0
    report = []
    for e in ents.get("entities", []):
        mie = e.get("mechanical_interface")
        if not isinstance(mie, dict):
            continue
        if mie.get("status") not in ("declared", "partial"):
            continue
        codes = list(mie.get("standard") or [])
        codes += [str(c) for c in (e.get("standard_conformance") or [])]
        target = None
        for c in codes:
            m = CODE_RE.search(str(c))
            if m:
                key = (float(m.group(1)), int(m.group(2)), "M" + m.group(3))
                if key in kb:
                    target = kb[key]
                    break
        if not target:
            continue
        if mie.get("flange"):
            continue  # 已有几何，不覆盖
        lifted += 1
        report.append((e.get("id"), e.get("name"), target["id"]))
        if apply:
            mie["flange"] = {
                "pcd_mm": target["d1_mm"],
                "bolt_count": target["bolt_count"],
                "thread": target["thread"],
                "dowel_holes": target.get("dowel_holes"),
                "mount_type": "flange_mount",
                "derived_from": target["id"],
                "source_tier": target.get("source_tier"),
            }
    if apply:
        with open(E_PATH, "w", encoding="utf-8") as f:
            json.dump(ents, f, ensure_ascii=False, indent=1)
        print("APPLIED")
    else:
        print("DRY-RUN")
    print(f"lifted={lifted}")
    for r in report:
        print(" -", r[0], "|", r[1], "->", r[2])

if __name__ == "__main__":
    main()
