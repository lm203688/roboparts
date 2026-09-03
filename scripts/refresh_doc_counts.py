#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""README / llms.txt 数据量行 + llms.txt 干净集行的现算刷新器。

为什么需要这个脚本
------------------
`README.md` 第 9 行与 `llms.txt` 第 6 行都有一段「数据量: N实体（分类明细）」，
`llms.txt` 第 25 行还有「已隔离实体 X 条。干净集为 Y 条（Tier A 可追溯率 Z%）」。
这些数字此前是**手工维护**的，加实体后极易漏改，被 L2「七处实体总数一致」与
L1.82 干净集口径判红（见 regression.py 1242 / 667）。

本脚本把「改了真相源 → 立刻重生这两段文案」收进 regen 管线，做到：
  - 实体总数 = len(entities)
  - 分类明细 = 各 canonical category 的现算计数（顺序/标签沿用文件原有写法，
    仅替换数字，避免破坏各文件的自定义标签措辞）
  - 干净集 / 隔离数 / Tier A 率 = meta.data_quality.clean / quarantined 与
    meta.provenance_coverage.traceable_pct（由 audit_data_quality / govern_source_tier 现算）

幂等：可重复运行，结果一致。应在 normalize_categories / audit_data_quality /
govern_source_tier 之后运行（依赖它们的 meta 输出）。

用法：python scripts/refresh_doc_counts.py
"""
import os
import re
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES_PATH = os.path.join(ROOT, "api", "entities.json")
README_PATH = os.path.join(ROOT, "README.md")
LLMS_PATH = os.path.join(ROOT, "llms.txt")

# 文件原有标签 → canonical category（覆盖 README 与 llms.txt 两份文件的全部标签写法）
LABEL2CANON = {
    "执行器": "actuators",
    "传感器": "sensors",
    "芯片": "chips",
    "协议": "protocols",
    "接口": "interfaces",
    "大模型（含VLA）": "llms",
    "LLM": "llms",
    "大模型": "llms",
    "机器人AI模型": "robot_ai_models",
    "平台": "platforms",
    "数据采集设备": "data_acquisition",
    "柔性执行器": "flexible_actuators",
    "仿生机械": "bionic_mechanisms",
    "夹爪": "grippers",
    "连接器": "connectors",
    "一体化关节模组": "integrated_joints",
    "减速器": "reducers",
    "控制器": "controllers",
    "结构件": "structural",
    "线缆": "cables",
    "电源": "power",
    "PCB": "pcb",
    "pcb": "pcb",
}


def load_counts():
    d = json.load(open(ENTITIES_PATH, encoding="utf-8"))
    ents = d.get("entities", [])
    # 优先用 meta.category_counts（normalize_categories 现算的权威值），
    # 否则退化到直接按 category 字段计数。
    counts = dict(d.get("meta", {}).get("category_counts") or {})
    if not counts:
        from collections import Counter
        counts = dict(Counter(e.get("category") for e in ents))
    return d, ents, counts


def rebuild_line(line, counts, total=None):
    """把一行「数据量[:：] N实体（细分）」里的数字全部替换为现算值，保留标签与顺序。

    total 为标题数字（默认取细分求和；传 len(entities) 可用真相源总数兜底）。
    """
    m = re.search(r"^(.*?数据量\*?\*?[:：]\s*)(\d+)实体（(.*)）(.*)$", line)
    if not m:
        return None
    prefix, _old_total, inner, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
    segs = []
    for seg in inner.split(" · "):
        mm = re.match(r"^\s*(\d+)\s*(.*?)\s*$", seg)
        if not mm:
            segs.append(seg)
            continue
        label = mm.group(2).strip()
        canon = LABEL2CANON.get(label)
        if canon is None:
            # 未知标签：保留原样（不篡改），仅告警
            print(f"  ⚠️ 未识别的细分标签「{label}」，跳过其计数刷新")
            segs.append(seg)
            continue
        segs.append(f"{counts.get(canon, 0)}{label}")
    head = total if total is not None else sum(
        counts.get(LABEL2CANON.get(re.match(r'^\s*\d+\s*(.*?)\s*$', s).group(1).strip()), 0)
        for s in segs if re.match(r'^\s*\d+\s*(.*?)\s*$', s))
    return f"{prefix}{head}实体（{' · '.join(segs)}）{suffix}"


def refresh_data_qty(path, counts, total):
    if not os.path.exists(path):
        return False
    lines = open(path, encoding="utf-8").read().split("\n")
    changed = False
    for i, ln in enumerate(lines):
        if "实体（" in ln and "数据量" in ln:
            new = rebuild_line(ln, counts, total)
            if new and new != ln:
                lines[i] = new
                changed = True
                print(f"  ✅ {os.path.basename(path)} 数据量行已刷新")
    if changed:
        open(path, "w", encoding="utf-8").write("\n".join(lines))
    return changed


def refresh_llms_clean(d):
    """llms.txt 第 25 行附近：已隔离实体 X 条。干净集为 Y 条（Tier A 可追溯率 Z%）。"""
    path = LLMS_PATH
    if not os.path.exists(path):
        return False
    meta = d.get("meta", {})
    dq = meta.get("data_quality", {})
    prov = meta.get("provenance_coverage", {})
    clean = dq.get("clean")
    quar = dq.get("quarantined")
    pct = prov.get("traceable_pct")
    if clean is None or quar is None or pct is None:
        print("  ⚠️ llms.txt 干净集行跳过：meta.data_quality / provenance_coverage 尚未现算")
        return False
    text = open(path, encoding="utf-8").read()
    pat = re.compile(r"已隔离实体 \d+ 条。干净集为 \d+ 条（Tier A 可追溯率 [\d.]+%）")
    new_seg = f"已隔离实体 {quar} 条。干净集为 {clean} 条（Tier A 可追溯率 {pct}%）"
    if not pat.search(text):
        print("  ⚠️ llms.txt 未找到「已隔离实体…干净集为…」段落，跳过")
        return False
    new_text = pat.sub(new_seg, text, count=1)
    if new_text != text:
        open(path, "w", encoding="utf-8").write(new_text)
        print(f"  ✅ llms.txt 干净集行已刷新（隔离 {quar} / 干净 {clean} / TierA {pct}%）")
        return True
    return False


def main():
    d, ents, counts = load_counts()
    total = len(ents)
    print(f"[REFRESH-DOC-COUNTS] 真相源实体总数 {total}；刷新 README/llms.txt 数据量行")
    refresh_data_qty(README_PATH, counts, total)
    refresh_data_qty(LLMS_PATH, counts, total)
    refresh_llms_clean(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
