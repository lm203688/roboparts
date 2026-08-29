# -*- coding: utf-8 -*-
"""
规则 4：清洁集内的「同物异 ID」重复检测（20260808-02 新增）

发现经过
--------
巡检时按 (name, manufacturer) 归一化聚类全库 688 条，命中 8 组同名同厂商。
其中 4 组的「另一半」已被规则 1/3 隔离（placeholder_id / non_entity），
清洁集里各自唯一，无害；但**另外 4 组两条都是 quarantine=false / data_quality=ok**：

    CHIP-66  / CHIP-81   Jetson Orin NX      （仅 type 措辞不同）
    CHIP-68  / CHIP-91   Qualcomm RB5        （仅 type 措辞不同）
    CHIP-80  / CHIP-95   Qualcomm QRB5165    （仅 type 措辞不同）
    RPLAT-009 / RPLAT-010 Tesla Optimus Gen 3（同一产品两版描述）

即：对外宣称的「593 条可信条目」里，有 4 对是同一个东西登记了两遍。

为什么必须治
------------
functions/mcp.js 的 search_components / recommend_for_application 只过滤
quarantine，**不做去重**。Agent 调 recommend 会拿到两条「不同 id、同一颗芯片」
的候选，误判为两个可选方案 —— 这是选型引擎的功能性硬伤，
也再一次坐实「公布的数量 ≠ 实际不重复条目数」。

治法
----
沿用既有治理约定：**不删除**。把非规范条目标
    quarantine=true / data_quality='duplicate' / duplicate_of=<规范 id>
保留全部字段与可追溯性，只是不再进选型结果。
"""
import collections
import re

# 规范条目人工裁定。判断依据随条写死在此处，避免每次运行结果漂移，也便于复核。
CANONICAL_OVERRIDES = {
    # Jetson Orin NX 官方形态是核心模组（System on Module）；SoC 指的是模组内部的
    # Orin 芯片本身。CHIP-81 的 type 更贴事实，以它为准。
    ('jetson orin nx', 'nvidia'): 'CHIP-81',
    # Qualcomm RB5 是面向机器人的开发套件，CHIP-68 的 "Robotics Development Kit"
    # 比笼统的 "Development Kit" 更具体。
    ('qualcomm rb5', 'qualcomm'): 'CHIP-68',
    # QRB5165 本体是处理器（SoC）；"Robotics Platform" 说的其实是 RB5 套件，
    # 留着会与上一条语义打架。
    ('qualcomm qrb5165', 'qualcomm'): 'CHIP-80',
    # 两条同为 Optimus Gen 3。RPLAT-010 带重量/身高/自由度/电池等可核对规格，
    # RPLAT-009 只有营销口径与第三方排名，信息量低。
    ('tesla optimus gen 3', 'tesla'): 'RPLAT-010',
}

_WS = re.compile(r'\s+')


def dedupe_key(e):
    """归一化聚类键。

    只按 (名称, 厂商) 双字段严格匹配 —— 仅凭名称合并会把不同厂商的同名件错并
    （例如多家都叫 "Development Kit"）。宁可漏判，不可错并。
    """
    name = _WS.sub(' ', str(e.get('name', '')).strip()).lower()
    vendor = _WS.sub(' ', str(e.get('manufacturer') or e.get('developer') or '').strip()).lower()
    if not name:
        return None
    return (name, vendor)


def pick_canonical(group):
    """从同物组里选规范条目。确定性顺序：人工裁定 > 字段数多 > id 字典序小。"""
    ids = {e['id'] for e in group}
    override = CANONICAL_OVERRIDES.get(dedupe_key(group[0]))
    if override and override in ids:
        return override
    return sorted(group, key=lambda e: (-len(e), e['id']))[0]['id']


def mark_duplicates(entities, tags):
    """在规则 1~3 判定为 ok 的条目中做去重标记。

    只在清洁集内部去重：另一半已被隔离的组，清洁集里本就唯一，无需处理。
    幂等 —— 每次运行先由调用方重算 tags，非重复条目的 duplicate_of 会被清掉。

    返回 [(dup_id, canonical_id, key)]
    """
    groups = collections.defaultdict(list)
    for e in entities:
        if tags.get(e['id']) != 'ok':
            continue
        k = dedupe_key(e)
        if k:
            groups[k].append(e)

    marked = []
    for k, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        canonical = pick_canonical(group)
        for e in sorted(group, key=lambda x: x['id']):
            if e['id'] != canonical:
                tags[e['id']] = 'duplicate'
                e['duplicate_of'] = canonical
                marked.append((e['id'], canonical, k))
    return marked


def find_clean_duplicates(entities):
    """只读检测：返回清洁集（quarantine != True）中未标 duplicate_of 的同物组。

    供回归闸门使用 —— 闸门不改数据，只判断"是否还有没治的重复"。
    """
    groups = collections.defaultdict(list)
    for e in entities:
        if e.get('quarantine') is True:
            continue
        k = dedupe_key(e)
        if k:
            groups[k].append(e)
    return {k: [e['id'] for e in v] for k, v in groups.items() if len(v) > 1}
