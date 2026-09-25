#!/usr/bin/env python3
"""
sync_hub_to_entities.py — 把 platforms.json 的 50 台 HUB- 工业臂同步到 entities.json

目的：让 `check_compatibility` MCP 工具能真的回答「UR5e + Robotiq 2F-85 能装吗」。
     之前这些机器人只在 platforms.json 里，check_compatibility 走 entities.json，
     所以只能返回 UNKNOWN。

幂等：按 id 前缀 HUB- 去重，重复运行不重复添加。
回滚：先备份 entities.json.bak.<timestamp>，出错可回退。
"""
import json, sys, datetime, shutil

SRC = "api/platforms.json"
DST = "api/entities.json"
TS = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
BACKUP = f"api/entities.json.bak.{TS}"

def main():
    apply = "--apply" in sys.argv
    # 1) 读源
    with open(SRC, encoding="utf-8") as f:
        p = json.load(f)
    hub = [x for x in p["data"] if str(x.get("id","")).startswith("HUB-")]
    if not hub:
        print("[WARN] platforms.json 里没有 HUB- 条目，无操作")
        return

    # 2) 读目标
    with open(DST, encoding="utf-8") as f:
        e = json.load(f)
    ents = e["entities"]
    before = len(ents)

    # 3) 幂等去重（按 name 归一化）
    import re
    def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())
    existing = {norm(x.get("name","")) for x in ents}

    # 4) 备份
    if apply:
        shutil.copy(DST, BACKUP)
        print(f"[BACKUP] {DST} -> {BACKUP}")

    # 5) 转换 + 追加
    added = []
    for h in hub:
        nm = h.get("name","")
        if norm(nm) in existing:
            continue
        # 构造 entities.json 格式（参考 ACT-028 Robotiq 2F-85 的 schema）
        mi = h.get("mechanical_interface") or {}
        entry = {
            "id": h["id"],
            "name": nm,
            "name_en": h.get("name_en") or nm,
            "category": "platforms",
            "manufacturer": h.get("manufacturer",""),
            "type": "industrial_robot_arm",
            "description": h.get("description",""),
            "verified": True,
            "data_quality": "ok",
            "quarantine": False,
            "source": h.get("source",""),
            "source_url": h.get("source_url",""),
            "source_tier": h.get("source_tier","B"),
            "confidence": h.get("confidence", 0.85),
            "confidence_basis": h.get("confidence_basis",""),
            "last_verified": h.get("last_verified",""),
            "mechanical_interface": {
                "status": mi.get("status","not_declared"),
                "mount_type": mi.get("mount_type","flange_mount"),
                "standard": mi.get("standard",[]),
                "aliases": mi.get("aliases",[]),
                "flange": mi.get("flange"),
                "source": mi.get("source",""),
                "source_url": mi.get("source_url",""),
                "source_tier": mi.get("source_tier","B"),
                "confidence": h.get("confidence", 0.85),
            },
            "entity_kind": "platform",
        }
        added.append(entry)
        existing.add(norm(nm))

    # 6) 打印
    print(f"[DRY-RUN] would add {len(added)} entries")
    for a in added[:5]:
        mi = a["mechanical_interface"]
        print(f"  + {a['id']} {a['name']} -> {mi['status']} {mi['standard']}")
    if len(added) > 5:
        print(f"  ... and {len(added)-5} more")

    if not apply:
        print("[DRY-RUN] 用 --apply 实写")
        return

    # 7) 写入
    ents.extend(added)
    e["entities"] = ents
    e["count"] = len(ents)
    e["updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(e, f, ensure_ascii=False, indent=2)
    print(f"[APPLIED] entities.json: {before} -> {len(ents)} (+{len(added)})")
    print(f"[BACKUP] 回滚: cp {BACKUP} {DST}")

if __name__ == "__main__":
    main()
