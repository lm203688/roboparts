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


def refresh_llms_subsets(d, ents):
    """llms.txt 子集口径四段现算回填（20260908-22，P1 数据保鲜）。

    起因（_NEEDS_USER「llms.txt 子集口径大面积过期」）：总数有 L2 七处一致闸门盯，
    子集数谁都不盯 —— assessed 83/768、机械可耦合 372/395 两套分母混用、
    not_declared 389、全库 768、声明率 2.82% 全部停在旧库时代，静默漂移三轮。

    修法与既有纪律一致：数字一律由真相源现算后正则回填（幂等），措辞仅
    在"旧文案两套分母自相矛盾"处收敛为单一口径，禁手改数字。
    """
    path = LLMS_PATH
    if not os.path.exists(path):
        print("  ⚠️ llms.txt 不存在，子集刷新跳过")
        return False
    meta = d.get("meta", {})
    mic = meta.get("mechanical_interface_coverage") or {}
    total = len(ents)
    applicable = mic.get("applicable")
    declared = mic.get("declared")
    partial = mic.get("partial")
    not_decl = mic.get("not_declared")
    na = mic.get("not_applicable")
    if None in (applicable, declared, partial, not_decl, na):
        print("  ⚠️ llms.txt 子集刷新跳过：meta.mechanical_interface_coverage 不完整")
        return False
    # 一致性自检：分母必须自洽，否则说明 meta 与实体库脱钩，停下来而不是写错数
    if declared + partial + not_decl != applicable or applicable + na != total:
        print("  ❌ 机械覆盖分母不自洽（declared+partial+not_declared=%d ≠ applicable=%d 或 applicable+n_a=%d ≠ total=%d），拒绝回填"
              % (declared + partial + not_decl, applicable, applicable + na, total))
        return False
    pct_mech = round((declared + partial) * 100.0 / applicable, 2) if applicable else 0.0
    # assessed 不信任 meta.standard_conformance_coverage（其 total/pct 曾停在 768 时代），
    # 直接从实体现算
    assessed = sum(
        1 for e in ents
        if isinstance(e.get("standard_conformance"), dict)
        and e["standard_conformance"].get("assessed") is True)
    pct_assessed = round(assessed * 100.0 / total, 2) if total else 0.0

    text = open(path, encoding="utf-8").read()
    changed = False

    # ① assessed 可评估行：当前 **83/768（10.81%）** 可评估
    pat = re.compile(r"当前 \*\*\d+/\d+（[\d.]+%）\*\* 可评估")
    new_seg = f"当前 **{assessed}/{total}（{pct_assessed}%）** 可评估"
    if pat.search(text):
        text2 = pat.sub(new_seg, text, count=1)
        if text2 != text:
            changed = True
        text = text2

    # ② 机械可耦合行：旧文案「768 条中 372 条…」把类目和(372)与 applicable(395)
    #    两套分母混进同一句 —— 收敛为单一 applicable 口径，括注改为不举类目的写法
    pat = re.compile(
        r"\*\*覆盖率如实披露\*\*：\d+ 条中 \d+ 条为机械可耦合实体（[^）]*）。"
        r"现状：尺寸级已声明 \d+ 条、partial \d+ 条（声明率 [\d.]+%，含 partial），"
        r"not_declared \d+ 条，n_a \d+ 条(?:（[^）]*）)?。")
    new_seg = (f"**覆盖率如实披露**：{total} 条中 {applicable} 条为机械可耦合实体"
               f"（具备物理安装面的实物零部件）。现状：尺寸级已声明 {declared} 条、"
               f"partial {partial} 条（声明率 {pct_mech}%，含 partial），"
               f"not_declared {not_decl} 条，n_a {na} 条。")
    if pat.search(text):
        text2 = pat.sub(new_seg, text, count=1)
        if text2 != text:
            changed = True
        text = text2

    # ③ 「全库 N 条中」边界行
    pat = re.compile(r"全库 (\d+) 条中，参数口径达到「可跨厂商直接比较」的为")
    m = pat.search(text)
    if m and int(m.group(1)) != total:
        text = pat.sub(f"全库 {total} 条中，参数口径达到「可跨厂商直接比较」的为", text, count=1)
        changed = True

    # ④ 「声明率仅 X%」边界行（与 onboarding_block html_block 同一口径源）
    pat = re.compile(r"声明率仅 [\d.]+%")
    new_seg = f"声明率仅 {pct_mech}%"
    if pat.search(text):
        text2 = pat.sub(new_seg, text, count=1)
        if text2 != text:
            changed = True
        text = text2

    if changed:
        open(path, "w", encoding="utf-8").write(text)
        print(f"  ✅ llms.txt 子集行已刷新（assessed {assessed}/{total}={pct_assessed}%；"
              f"机械 {declared}+{partial}/{applicable}={pct_mech}%，nd {not_decl}/na {na}）")
    else:
        print("  ✅ llms.txt 子集行已与真相源一致（无需改动）")
    return changed


def main():
    d, ents, counts = load_counts()
    total = len(ents)
    print(f"[REFRESH-DOC-COUNTS] 真相源实体总数 {total}；刷新 README/llms.txt 数据量行")
    refresh_data_qty(README_PATH, counts, total)
    refresh_data_qty(LLMS_PATH, counts, total)
    refresh_llms_clean(d)
    refresh_llms_subsets(d, ents)
    return 0


if __name__ == "__main__":
    sys.exit(main())
