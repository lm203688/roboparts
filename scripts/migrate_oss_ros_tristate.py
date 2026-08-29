#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【20260806-15】一次性迁移：清除 OSS 数据层里由「抽取器种类」硬编码出来的 ros_support 断言。

背景
----
`scripts/ingest_oss.mjs` 的三个抽取器此前按抽取器种类给 ros_support 写死布尔值：

  urdf   (125 条) -> ros_support = true    「从 URDF 抓的，那就是 ROS 生态的」
  bom_md ( 63 条) -> ros_support = false   「从机械 BOM 表抓的，那就是不支持」
  readme (  1 条) -> ros_support = /ros/i.test(name)  「名字里有 ros 就算支持」

这三条规则没有一条来自厂商声明：
 - URDF 只证明该关节位点出现在某个 ROS/URDF 模型里，是**出处**，不是**能力声明**；
 - bom_md 里多为侧板/大腿内侧/电池底盖等纯结构件，无电气接口，
   「支不支持 ROS」对它们根本不成立——写 false 是范畴错误，比「不知道」更糟；
 - /ros/i 会命中 gy(ros)cope、mic(roS)D、(Ros)enberger 等无关词。

后果被放大的两点：
 1. ros_support 是 /api/oss 的 PREMIUM_FIELDS 之一，即**付费字段**；
 2. OSS 325 条里未声明数为 0，导致上两轮修好的兼容性引擎 unknown 分支
    在这条数据链上**完全不可达**（数据层已把 unknown 全部消灭）。

迁移规则（与修好后的 ingest_oss.mjs 完全一致，保证下次 ingest 后结果幂等）
----------------------------------------------------------------------
  extractor == 'urdf'   -> 删除 ros_support；补 ros_ecosystem_origin=true；compatibility=['URDF']
  extractor == 'bom_md' -> 删除 ros_support
  extractor == 'readme' -> 删除 ros_support
  种子数据（无 extractor）-> 原样保留（种子表里每条都显式声明过，是真实依据）

幂等：重复执行不会产生额外变化。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'api', 'oss_components.json')

with open(PATH, encoding='utf-8') as f:
    doc = json.load(f)

rows = doc['data']
stats = {'urdf': 0, 'bom_md': 0, 'readme': 0, 'untouched': 0}

for e in rows:
    ext = e.get('extractor')
    if ext == 'urdf':
        if 'ros_support' in e:
            del e['ros_support']
            stats['urdf'] += 1
        e['ros_ecosystem_origin'] = True
        # 出处是 URDF 文件本身；'ROS2' 是未经证实的能力外推，去掉
        e['compatibility'] = ['URDF']
    elif ext in ('bom_md', 'readme'):
        if 'ros_support' in e:
            del e['ros_support']
            stats[ext] += 1
    else:
        stats['untouched'] += 1

undeclared = sum(1 for e in rows if 'ros_support' not in e)
declared_t = sum(1 for e in rows if e.get('ros_support') is True)
declared_f = sum(1 for e in rows if e.get('ros_support') is False)

with open(PATH, 'w', encoding='utf-8') as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)
    f.write('\n')

print('迁移完成：', PATH)
print('  清除伪造断言  urdf={urdf}  bom_md={bom_md}  readme={readme}'.format(**stats))
print('  种子未改动    {untouched}'.format(**stats))
print('  迁移后 ros_support 分布: true={} false={} 未声明={} / 总计 {}'.format(
    declared_t, declared_f, undeclared, len(rows)))
if undeclared == 0:
    print('  !! 未声明数仍为 0，迁移未生效', file=sys.stderr)
    sys.exit(1)
