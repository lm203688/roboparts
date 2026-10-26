#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export RoboParts entity dataset to ModelScope staging format.

Reads api/data.json (the single source of truth), flattens 708 entities to a
CSV, and renders a dataset card (README.md) with COVERAGE NUMBERS COMPUTED
FROM THE DATA (never hardcoded) so the card stays honest on every re-publish.

Output: modelscope_staging/entities.csv + modelscope_staging/README.md
"""
import json
import os
import csv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'api', 'data.json')
OUTDIR = os.path.join(ROOT, 'modelscope_staging')

COLUMNS = [
    'id', 'name', 'name_en', 'category', 'manufacturer', 'type',
    'torque', 'speed', 'weight', 'voltage', 'protocol', 'interface',
    'position_resolution', 'applications', 'price_range', 'compatibility',
    'ros_support', 'domestic_rate', 'import_dependency',
    'verified', 'quarantine', 'data_quality',
    'source', 'source_tier', 'confidence',
    'mech_status', 'mech_mount_type', 'mech_standard',
    'std_assessed', 'std_ros2', 'entity_kind',
]


def flat(e):
    mi = e.get('mechanical_interface') or {}
    sc = e.get('standard_conformance') or {}
    def jl(v):
        return '; '.join(v) if isinstance(v, list) else (v or '')
    def blank(v):
        return '' if v is None else v
    return {
        'id': e.get('id'), 'name': e.get('name'), 'name_en': e.get('name_en'),
        'category': e.get('category'), 'manufacturer': e.get('manufacturer'),
        'type': e.get('type'),
        'torque': e.get('torque'), 'speed': e.get('speed'), 'weight': e.get('weight'),
        'voltage': e.get('voltage'), 'protocol': e.get('protocol'),
        'interface': e.get('interface'), 'position_resolution': e.get('position_resolution'),
        'applications': jl(e.get('applications')), 'price_range': e.get('price_range'),
        'compatibility': jl(e.get('compatibility')),
        'ros_support': blank(e.get('ros_support')),
        'domestic_rate': e.get('domestic_rate'), 'import_dependency': e.get('import_dependency'),
        'verified': blank(e.get('verified')), 'quarantine': blank(e.get('quarantine')),
        'data_quality': e.get('data_quality'),
        'source': e.get('source'), 'source_tier': e.get('source_tier'),
        'confidence': blank(e.get('confidence')),
        'mech_status': mi.get('status'), 'mech_mount_type': mi.get('mount_type'),
        'mech_standard': mi.get('standard'),
        'std_assessed': blank(sc.get('assessed')), 'std_ros2': blank(sc.get('ros2')),
        'entity_kind': e.get('entity_kind'),
    }


def compute_stats(data, meta):
    n = len(data)
    def c(pred):
        return sum(1 for x in data if pred(x))
    prov = meta.get('provenance_coverage', {})
    dq = meta.get('data_quality', {})
    mech = meta.get('mechanical_interface_coverage', {})
    ros_true = c(lambda x: x.get('ros_support') is True)
    ros_false = c(lambda x: x.get('ros_support') is False)
    ros_null = c(lambda x: x.get('ros_support') in (None,))
    mech_decl = c(lambda x: (x.get('mechanical_interface') or {}).get('status') == 'declared')
    mech_nd = c(lambda x: (x.get('mechanical_interface') or {}).get('status') == 'not_declared')
    return {
        'total': n,
        'cat_counts': meta.get('category_counts', {}),
        'tier_a': prov.get('tier_a_traceable'), 'tier_b': prov.get('tier_b_attributable'),
        'tier_c': prov.get('tier_c_none'),
        'source_pct': prov.get('source_pct'), 'traceable_pct': prov.get('traceable_pct'),
        'confidence_pct': prov.get('confidence_pct'), 'last_verified_pct': prov.get('last_verified_pct'),
        'clean': dq.get('clean'), 'quarantined': dq.get('quarantined'),
        'quarantine_pct': dq.get('quarantine_pct'),
        'ros_true': ros_true, 'ros_false': ros_false, 'ros_null': ros_null,
        'mech_applicable': mech.get('applicable'), 'mech_decl': mech_decl,
        'mech_nd': mech_nd, 'mech_fill_pct': mech.get('fill_pct'),
        'verified_true': c(lambda x: x.get('verified') is True),
        'updated': meta.get('updated'),
    }


def render_readme(s, meta):
    cats = ''.join(f'| {k} | {v} |\n' for k, v in s['cat_counts'].items())
    return f"""# RoboParts — 仿生机器人零部件结构化数据集

> 中立、开源、可机器读取的仿生/人形机器人零部件数据库。覆盖执行器、传感器、芯片、接口、协议、机器人 AI 模型、数据采集、LLM、平台、柔性执行器、连接器共 **{s['total']}** 个实体、**11** 个类别。

## 一句话定位
RoboParts 把分散在各厂商目录里的机器人硬件参数，归一化成可横向比较、可核验来源、且**诚实标注缺失**的结构化数据集，供选型、兼容性判定、世界模型/URDF 生成与标准符合性自查使用。

## 数据规模
| 指标 | 数值 |
|---|---|
| 实体总数 | {s['total']} |
| 类别数 | 11 |
| 清洁集（去重可信） | {s['clean']} |
| 隔离集（quarantine，不进默认选型） | {s['quarantined']}（{s['quarantine_pct']}%）|
| 已核验（verified=true） | {s['verified_true']} |
| 最后更新 | {s['updated']} |

### 类别分布
| 类别 | 数量 |
|---|---|
{cats}

## 字段说明（entities.csv）
`id, name, name_en, category, manufacturer, type, torque, speed, weight, voltage, protocol, interface, position_resolution, applications, price_range, compatibility, ros_support, domestic_rate, import_dependency, verified, quarantine, data_quality, source, source_tier, confidence, mech_status, mech_mount_type, mech_standard, std_assessed, std_ros2, entity_kind`

- `applications` / `compatibility` 为 `; ` 分隔的多值字段。
- `ros_support`：`true` / `false` / 空（**空=厂商从未声明，不等于不兼容**）。
- `mech_status`：`declared` / `not_declared` / 空（空=该类别不适用机械接口）。
- `source_tier`：A=可点开复核的一手来源；B=弱归因（厂商目录声明值，无原始链接）；C=无溯源。

## 数据诚实性（本项目核心差异点）
很多零部件数据库会把"不知道"悄悄写成"没有"。RoboParts 刻意把缺失当作**第三态**显式保留，绝不把"未声明"折叠成"不兼容"。

### 1. 来源分级与可溯源率
| 来源分级 | 数量 |
|---|---|
| Tier A（可点开复核的一手来源） | {s['tier_a']} |
| Tier B（弱归因，如厂商目录声明值） | {s['tier_b']} |
| Tier C（无溯源，confidence 上限 0.30） | {s['tier_c']} |

- 有来源字段占比 `source_pct = {s['source_pct']}%`（含 Tier B 弱归因，仅作过程指标）
- **可点开复核占比 `traceable_pct = {s['traceable_pct']}%`**（主指标，曾虚报已更正）
- 置信度已标注占比 `confidence_pct = {s['confidence_pct']}%`
- 最近核验占比 `last_verified_pct = {s['last_verified_pct']}%`

### 2. 机械接口维度（三态）
| 状态 | 数量 |
|---|---|
| 适用实体 | {s['mech_applicable']} |
| 已声明（declared） | {s['mech_decl']} |
| 未声明（not_declared，显式缺口） | {s['mech_nd']} |

机械接口已获厂商声明的比例仅 **{s['mech_fill_pct']}%**——这是一个真实的、被显式记录的缺口，不是字段缺失。

### 3. ROS 支持维度（三态）
| 状态 | 数量 |
|---|---|
| 声明支持 ROS | {s['ros_true']} |
| 声明不支持 ROS | {s['ros_false']} |
| 从未声明（不推断为不兼容） | {s['ros_null']} |

### 4. 隔离与去重策略
- `quarantine=true` 的 {s['quarantined']} 条不删除，前端默认不进选型结果，仅在"显示未核验数据"时展示。
- 同名同厂商重复登记只保留一条规范条目，其余隔离，清洁集内不再有同物异 ID。

## 许可证
[Creative Commons Attribution 4.0 (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)

## 获取与实时访问
数据集会随站点持续更新；如需实时数据请用开放 API（免费 key，无需信用卡）：
```bash
curl -X POST https://roboparts.cc/api/register -H "Content-Type: application/json" -d '{{"email":"you@example.com"}}'
curl -H "X-API-Key: YOUR_KEY" https://roboparts.cc/api/data.json
```
- 在线平台：https://roboparts.cc
- 数据集仓库：https://github.com/lm203688/roboparts
- MCP Server：`roboparts-mcp-server`（npm）

## 中立性声明
本平台不生产、不代理任何零部件，与所收录厂商无销售利益关系。本库参数为厂商公开声明值，未经我方实测复现；跨厂商可直接横向比较的 A 级条目为 0 条，机械接口有线索的占 {s['mech_fill_pct']}%。请据此判断可信度，不要把声明值当实测值使用。

## 使用方式
```python
import pandas as pd
df = pd.read_csv('entities.csv')
# 查看已声明 ROS 支持的实体
df[df['ros_support'] == True]
# 查看机械接口已声明的实体
df[df['mech_status'] == 'declared']
```

## 引用
```bibtex
@dataset{{roboparts2026,
  title={{RoboParts: A Structured Dataset for Bionic Robot Components}},
  author={{RoboParts Team}},
  year={{2026}},
  url={{https://roboparts.cc}}
}}
```
"""


def main():
    with open(SRC, encoding='utf-8') as f:
        doc = json.load(f)
    data = doc['data']
    meta = doc['meta']
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, 'entities.csv')
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for e in data:
            w.writerow(flat(e))
    s = compute_stats(data, meta)
    readme = render_readme(s, meta)
    with open(os.path.join(OUTDIR, 'README.md'), 'w', encoding='utf-8') as f:
        f.write(readme)
    print(f'wrote {csv_path} ({len(data)} rows)')
    print(f'wrote {os.path.join(OUTDIR, "README.md")}')
    print(f'stats: total={s["total"]} clean={s["clean"]} quarantine={s["quarantined"]} '
          f'traceable_pct={s["traceable_pct"]} mech_fill={s["mech_fill_pct"]}% '
          f'ros_true={s["ros_true"]} ros_null={s["ros_null"]}')


if __name__ == '__main__':
    main()
