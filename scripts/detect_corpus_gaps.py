#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboParts 语料缺口探测器（T5 数据实体扩展 · 输入通道 ② 的自给替代）

【为什么需要这个脚本】
T5 扩展任务设计了三路输入：
  ① ops/monthly/direction-YYYYMM.json   —— 月度品类目标（唯一长期有效的一路）
  ② ops/feedback/search-misses-*.md     —— 搜索无结果关键词
  ③ ops/rapid/                          —— P0 情报待录项
实际运行中 ②③ 长期为空目录 —— 站点尚未部署搜索埋点回流，情报任务也没往 rapid/ 落盘。
于是 T5 每轮只剩 ① 一路输入，而 ① 的五大优先品类被前几轮批次灌满后，
再跑就只会产出同义重复实体 —— 这正是 T5「零产出静默死亡」的深层诱因：
不是脚本崩了，是输入枯竭后无人察觉。

【本脚本的解法】
在等到真实搜索埋点之前，用**库内语料自身**推导缺口信号：
对一组「人形机器人供应链应当覆盖的关键词」做全库匹配，命中数低于阈值的
即视为结构性空白（selection/BOM 场景下用户一搜即空的品类）。
这是**派生信号，不是真实用户搜索日志**，输出文件里会显式标注，不得混淆。

用法：
  python scripts/detect_corpus_gaps.py                 # 打印报告
  python scripts/detect_corpus_gaps.py --write         # 同时写入 ops/feedback/search-misses-YYYYMMDD.md
幂等：同日重复运行覆盖同一文件，无副作用。
"""
import argparse
import datetime
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES = os.path.join(ROOT, 'api', 'entities.json')
OUT_DIR = os.path.join(ROOT, 'ops', 'feedback')

# 关键词表：(展示名, [匹配词], 期望最低条数, 归属类目)
# 期望值按「选型场景下用户至少需要几个可比选项」拍定，不是精确科学值。
PROBES = [
    ('谐波减速器',        ['谐波', 'harmonic'],                       8,  'actuators'),
    ('行星滚柱丝杠',      ['滚柱丝杠', 'roller screw'],               8,  'actuators'),
    ('无框力矩电机',      ['无框', 'frameless'],                      8,  'actuators'),
    ('一体化关节模组',    ['关节模组', 'joint module'],               8,  'actuators'),
    ('六维力/力矩传感器', ['六维力', '力矩传感', '扭矩传感', 'force_torque'], 8, 'sensors'),
    ('灵巧手',            ['灵巧手', 'dexterous', 'gripper', '夹爪'], 8,  'actuators'),
    ('腱绳传动',          ['腱绳', 'tendon'],                         3,  'actuators'),
    ('空心杯电机',        ['空心杯', 'coreless'],                     4,  'actuators'),
    ('行星减速器',        ['行星减速'],                               4,  'actuators'),
    ('交叉滚子轴承',      ['交叉滚子', 'crossed roller'],             3,  'actuators'),
    ('关节编码器',        ['编码器', 'encoder'],                      10, 'sensors'),
    ('电子皮肤',          ['电子皮肤', 'e-skin', 'electronic skin'],  4,  'sensors'),
    ('触觉传感器',        ['触觉', 'tactile'],                        10, 'sensors'),
    ('电池/BMS',          ['电池', 'battery', 'bms'],                 5,  'chips'),
    ('减速器润滑/密封',   ['润滑', '密封', 'lubricat', 'seal'],       3,  'actuators'),
    ('谐波柔轮材料',      ['柔轮', 'flexspline'],                     2,  'actuators'),
    ('直线执行器',        ['直线执行', 'linear actuator'],            5,  'actuators'),
    ('串联弹性驱动',      ['串联弹性', 'sea', 'series elastic'],      3,  'actuators'),
]


def blob(e):
    parts = [e.get('name'), e.get('name_en'), e.get('type'), e.get('description')]
    return ' '.join(str(p) for p in parts if p).lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='写入 ops/feedback/search-misses-YYYYMMDD.md')
    args = ap.parse_args()

    ents = json.load(open(ENTITIES, encoding='utf-8'))['entities']
    # 隔离条目不计入覆盖 —— 前端默认不展示，等于用户搜不到
    live = [e for e in ents if not e.get('quarantine')]
    texts = [(e, blob(e)) for e in live]

    rows = []
    for label, kws, expect, cat in PROBES:
        hits = [e for e, b in texts if any(k.lower() in b for k in kws)]
        rows.append({
            'label': label, 'kw': kws, 'expect': expect, 'category': cat,
            'hit': len(hits), 'gap': max(0, expect - len(hits)),
        })
    rows.sort(key=lambda r: (-r['gap'], r['hit']))
    gaps = [r for r in rows if r['gap'] > 0]

    print(f'=== 语料缺口探测 === 干净集 {len(live)} 条（已排除 {len(ents)-len(live)} 条隔离）')
    print(f'{"品类":<20}{"命中":>6}{"期望":>6}{"缺口":>6}  类目')
    for r in rows:
        flag = '  ⚠️' if r['gap'] > 0 else ''
        print(f'{r["label"]:<20}{r["hit"]:>6}{r["expect"]:>6}{r["gap"]:>6}  {r["category"]}{flag}')
    print(f'\n结构性缺口 {len(gaps)} 项，合计待补 {sum(r["gap"] for r in gaps)} 条')

    if not args.write:
        return 0

    today = datetime.date.today().strftime('%Y%m%d')
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'search-misses-{today}.md')
    lines = [
        f'# 搜索缺口信号 · {datetime.date.today().isoformat()}',
        '',
        '> ⚠️ **信号性质声明**：本文件由 `scripts/detect_corpus_gaps.py` 从**库内语料自身**派生，',
        '> **不是真实用户搜索日志**。站点搜索埋点回流尚未建设，此文件是 T5 输入通道 ② 的',
        '> 临时自给替代，用于避免「输入枯竭 → 零产出静默死亡」。',
        '> 真实埋点上线后应直接覆盖本文件，并删除本声明。',
        '',
        f'- 探测基数：干净集 {len(live)} 条（全库 {len(ents)}，排除隔离 {len(ents)-len(live)}）',
        f'- 结构性缺口：**{len(gaps)} 项**，合计待补 **{sum(r["gap"] for r in gaps)} 条**',
        '',
        '## 缺口清单（按缺口大小降序）',
        '',
        '| 品类 | 当前命中 | 期望下限 | 缺口 | 建议归属类目 |',
        '|---|---:|---:|---:|---|',
    ]
    for r in gaps:
        lines.append(f'| {r["label"]} | {r["hit"]} | {r["expect"]} | **{r["gap"]}** | `{r["category"]}` |')
    lines += ['', '## 已达标品类', '', '| 品类 | 命中 | 期望下限 |', '|---|---:|---:|']
    for r in rows:
        if r['gap'] == 0:
            lines.append(f'| {r["label"]} | {r["hit"]} | {r["expect"]} |')
    lines += [
        '',
        '## 下轮 T5 取用方式',
        '',
        '1. 优先补缺口最大的品类；同一品类已有 ≥ 期望值时**不得重复灌注**（会造同义实体）。',
        '2. 补录前先确认锚点可达：本机对多数厂商官网（如 leaderdrive.cn / hiwin.tw）不通，',
        '   而 github.com / arxiv.org 可达 —— 优先选可实证升 Tier A 的锚点，否则会被棘轮闸门拦下。',
        '3. 入库一律先标 `source_tier=B`，升 A 交由 `scripts/verify_vendor_sources.py` 实证。',
        '',
    ]
    open(path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print(f'📄 已写入 {os.path.relpath(path, ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
