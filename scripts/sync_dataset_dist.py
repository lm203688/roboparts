#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对外数据集分发目录生成器（roboparts-dataset-github/）。

为什么需要这个脚本
------------------
`.github/workflows/sync-to-huggingface.yml` 与 `sync-to-modelscope.yml`
发布的是 `roboparts-dataset-github/`，但该目录历史上**没有任何生成器**，
纯手工维护 ⇒ 必然漂移。20260831-10 实测漂移量：

    真相源 api/entities.json          798 实体 / 20 品类
    data/roboparts_full.json          544 实体 / 10 品类（updated 2026-08-04）
    README.md（对外数据集卡片）        自称 688 实体 / 10 品类 / 声明率 0.57%

三个互相矛盾的数字全部对外发布（HuggingFace / ModelScope / GitHub），
直接违反项目「全站数字唯一真相源」纪律 —— 因为闸门从未覆盖这个目录。

本脚本把该目录纳入生成链：所有数字**现算**，禁止手写。

用法
----
    python scripts/sync_dataset_dist.py            # 重新生成
    python scripts/sync_dataset_dist.py --check    # 只校验，漂移则 exit 1（供闸门/CI 用）

设计约束
--------
1. 唯一真相源 = `api/entities.json`，实体对象原样透传（不裁剪字段，
   下游 HF/ModelScope 消费方看到的 schema 与官网 API 完全一致）。
2. README 整篇由本脚本模板渲染，散文照抄、**数字一律现算**。
3. 品类的「核心字段」列也现算（取该品类最常见的非通用字段），
   避免手写字段名随数据演进而失真。
4. 声明率对外唯一口径 = (declared + partial) / applicable，
   applicable = 总数 − n_a（与 `_NEEDS_USER.md` / 官网口径一致）。
"""
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'api', 'entities.json')
DIST = os.path.join(ROOT, 'roboparts-dataset-github')
DIST_DATA = os.path.join(DIST, 'data', 'roboparts_full.json')
DIST_README = os.path.join(DIST, 'README.md')

CST = timezone(timedelta(hours=8))

# 品类中文标签（仅展示用；键必须来自真相源实际出现的 category）
CATEGORY_ZH = {
    'actuators': '执行器 (Actuators)',
    'chips': '芯片 (Chips)',
    'sensors': '传感器 (Sensors)',
    'protocols': '通信协议 (Protocols)',
    'robot_ai_models': '机器人AI模型 (Robot AI Models)',
    'data_acquisition': '数据采集设备 (Data Acquisition)',
    'interfaces': '接口 (Interfaces)',
    'llms': '大模型 (LLMs)',
    'platforms': '平台 (Platforms)',
    'flexible_actuators': '柔性执行器 (Flexible Actuators)',
    'grippers': '夹爪 / 末端执行器 (Grippers)',
    'reducers': '减速器 (Reducers)',
    'bionic_mechanisms': '仿生机构 (Bionic Mechanisms)',
    'controllers': '控制器 (Controllers)',
    'structural': '结构件 (Structural)',
    'connectors': '连接器 (Connectors)',
    'cables': '线缆 (Cables)',
    'power': '电源 (Power)',
    'pcb': '电路板 (PCB)',
    'integrated_joints': '一体化关节 (Integrated Joints)',
}

# 计算「核心字段」列时忽略的治理/通用字段
GENERIC_FIELDS = {
    'id', 'rp_id', 'name', 'name_en', 'category', 'subcategory',
    'verified', 'data_quality', 'quarantine', 'quarantine_reason',
    'source', 'sources', 'source_url', 'source_tier', 'source_tier_prev',
    'source_tier_basis', 'source_scope', 'confidence', 'confidence_basis',
    'mechanical_interface', 'standard_conformance', 'entity_kind',
    'entity_kind_basis', 'kind_basis', 'tier_upgrade_reason', 'tier_cap_reason',
    'needs_provenance', 'last_verified', 'last_updated', 'derived_properties',
    'verification_note', 'description', 'description_en', 'duplicate_of',
    'gap_fill_batch', 'application_en', 'type_en', 'manufacturer_en',
    'lost_layer_recovery', 'scope', 'relevance', 'layer',
}

# 字段名 → 中文显示（缺失则回退英文键名）
FIELD_ZH = {
    'torque': '扭矩', 'speed': '速度', 'weight': '重量', 'voltage': '电压',
    'protocol': '协议', 'interface': '接口', 'price_range': '价格区间',
    'price': '价格', 'applications': '应用', 'application': '应用',
    'compatibility': '兼容性', 'ros_support': 'ROS 支持', 'manufacturer': '厂商',
    'type': '类型', 'cpu': 'CPU', 'gpu': 'GPU', 'npu': 'NPU', 'tdp': '功耗',
    'ai_perf': 'AI 算力', 'memory': '内存', 'range': '量程', 'precision': '精度',
    'latency': '延迟', 'determinism': '确定性', 'topology': '拓扑',
    'max_nodes': '最大节点', 'cable': '线缆', 'connector': '连接器',
    'position_resolution': '位置分辨率', 'domestic_rate': '国产化程度',
    'import_dependency': '进口依赖', 'open_source': '开源', 'license': '许可',
    'developer': '开发方', 'parameters': '参数量', 'year': '年份',
    'release_date': '发布日期', 'features': '特性', 'key_features': '关键特性',
    'form_factor': '形态', 'pros': '优点', 'cons': '缺点', 'status': '状态',
    'specs': '规格', 'interfaces': '接口', 'oss': '开源项目',
    'data_modalities': '数据模态', 'vla_support': 'VLA 支持',
    'robot_integration': '机器人集成', 'embodied_ai': '具身智能',
    'supply_chain': '供应链', 'power': '功率', 'input': '输入', 'output': '输出',
    'reduction_ratio': '减速比', 'output_torque': '输出扭矩', 'backlash': '背隙',
    'input_speed': '输入转速', 'max_load': '最大负载', 'grip_width': '开口宽度',
    'load_capacity': '负载能力', 'dof': '自由度', 'flange': '法兰',
    'material': '材料', 'stroke': '行程', 'company': '公司', 'vendor': '厂商',
    'organization': '机构', 'standard': '标准', 'standard_compliance': '标准合规',
    'robotics_use': '机器人用途', 'api_available': 'API 可用',
    'toolchain': '工具链', 'bionic_features': '仿生特性',
}


def _load_src():
    with open(SRC, encoding='utf-8') as f:
        return json.load(f)


def compute_facts(src):
    """所有对外数字的唯一现算入口。"""
    ents = src.get('entities') or []
    n = len(ents)
    cats = Counter(e.get('category') for e in ents)

    mi = Counter((e.get('mechanical_interface') or {}).get('status') for e in ents)
    n_a = mi.get('n_a', 0)
    declared = mi.get('declared', 0)
    partial = mi.get('partial', 0)
    not_declared = mi.get('not_declared', 0)
    applicable = n - n_a
    declared_rate = (declared + partial) / applicable * 100 if applicable else 0.0

    def filled(key):
        return sum(1 for e in ents if e.get(key) not in (None, '', [], {}))

    tiers = Counter(e.get('source_tier') for e in ents)
    std_assessed = sum(
        1 for e in ents if (e.get('standard_conformance') or {}).get('assessed'))

    # 每个品类的「核心字段」= 该品类中出现率 >= 40% 的非通用字段，取前 6
    core_fields = {}
    for cat in cats:
        sub = [e for e in ents if e.get('category') == cat]
        fc = Counter()
        for e in sub:
            for k, v in e.items():
                if k in GENERIC_FIELDS:
                    continue
                if v in (None, '', [], {}):
                    continue
                fc[k] += 1
        keep = [k for k, c in fc.most_common() if c / len(sub) >= 0.4][:6]
        if not keep:
            keep = [k for k, _ in fc.most_common(3)]
        core_fields[cat] = keep

    return {
        'total': n,
        'category_count': len(cats),
        'categories': dict(cats),
        'core_fields': core_fields,
        'mi': {
            'declared': declared, 'partial': partial,
            'not_declared': not_declared, 'n_a': n_a,
            'applicable': applicable, 'rate': declared_rate,
        },
        'coverage': {
            'name': filled('name'),
            'manufacturer': filled('manufacturer'),
            'source_url': filled('source_url'),
            'price_range': filled('price_range'),
            'std_assessed': std_assessed,
        },
        'tiers': dict(tiers),
    }


def build_data(src, facts, now):
    """生成分发用 JSON：实体原样透传，meta 数字现算。"""
    # 保留既有 meta 的描述性字段（若分发文件存在），数字一律覆盖
    static = {
        'name': 'RoboParts Dataset',
        'name_zh': '机器人零部件结构化数据集',
        'domain': 'roboparts.cc',
        'homepage': 'https://roboparts.cc',
        'github': 'https://github.com/lm203688/roboparts',
        'license': 'CC-BY-4.0',
    }
    if os.path.exists(DIST_DATA):
        try:
            with open(DIST_DATA, encoding='utf-8') as f:
                prev = (json.load(f) or {}).get('meta') or {}
            # 注：name / name_zh 是**定位口径**，属受管字段，一律由本文件现算，
            # 不从旧分发文件继承 —— 否则改了这里的定位后，旧值会被"保留"住，
            # 形成「生成器已改、产物没变」的静默漂移（20260921 实测踩到）。
            for k in ('description', 'domain', 'homepage', 'github'):
                if prev.get(k):
                    static[k] = prev[k]
        except Exception:
            pass

    cat_list = ', '.join(sorted(facts['categories']))
    static['description'] = (
        'Structured dataset of bionic / humanoid robot components. '
        f"{facts['total']} entities across {facts['category_count']} categories "
        f'({cat_list}). Generated from the single source of truth '
        '(api/entities.json) by scripts/sync_dataset_dist.py — all counts computed, '
        'never hand-written.'
    )

    meta = dict(static)
    meta.update({
        'total_entities': facts['total'],
        'category_count': facts['category_count'],
        'category_counts': dict(
            sorted(facts['categories'].items(), key=lambda x: -x[1])),
        'mechanical_interface_declared_rate_pct': round(facts['mi']['rate'], 2),
        'mechanical_interface_counts': {
            'declared': facts['mi']['declared'],
            'partial': facts['mi']['partial'],
            'not_declared': facts['mi']['not_declared'],
            'not_applicable': facts['mi']['n_a'],
            'applicable_denominator': facts['mi']['applicable'],
        },
        'source_tier_counts': dict(sorted(facts['tiers'].items())),
        'updated': now.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'generated_by': 'scripts/sync_dataset_dist.py',
        'truth_source': 'api/entities.json',
    })
    return {'meta': meta, 'entities': src.get('entities') or []}


def build_readme(facts, now):
    f = facts
    mi = f['mi']
    cov = f['coverage']
    n = f['total']

    def pct(x):
        return f'{x / n * 100:.1f}%'

    rows = []
    for cat, cnt in sorted(f['categories'].items(), key=lambda x: -x[1]):
        label = CATEGORY_ZH.get(cat, cat)
        fields = '、'.join(FIELD_ZH.get(k, k) for k in f['core_fields'].get(cat, []))
        rows.append(f'| {label} | {cnt} | {fields or "—"} |')
    table = '\n'.join(rows)

    zh_names = '、'.join(
        CATEGORY_ZH.get(c, c).split(' (')[0]
        for c, _ in sorted(f['categories'].items(), key=lambda x: -x[1]))

    tier_lines = []
    for t in ('A', 'B', 'C'):
        c = f['tiers'].get(t, 0)
        tier_lines.append(f'{t} {c} 条（{pct(c)}）')
    tier_summary = ' · '.join(tier_lines)

    return f"""# RoboParts Dataset — 机器人零部件结构化数据集（兼容判定就绪）

[![RoboParts](https://img.shields.io/badge/RoboParts-机器人零件兼容性判定层-06b6d4)](https://roboparts.cc)
[![Entities](https://img.shields.io/badge/Entities-{n}-10b981)](./data/)
[![License](https://img.shields.io/badge/License-CC--BY--4.0-blue)](./LICENSE)
[![ModelScope](https://img.shields.io/badge/ModelScope-数据集-ff6a00)](https://www.modelscope.cn/datasets/lm203688/roboparts-data)
[![PyPI](https://img.shields.io/badge/PyPI-roboparts-3775a9)](https://pypi.org/project/roboparts/)

> 覆盖 **{f['category_count']} 大品类**（{zh_names}）的结构化零部件数据集，
> 面向具身智能 / 人形 / 仿生机器人研发，可被 AI Agent 直接检索与引用。
> 当前 **{n} 条实体**。

<!-- 本文件由 scripts/sync_dataset_dist.py 从 api/entities.json 生成，所有数字现算。
     请勿手工编辑数字：手改会被 regression / CI 的分发漂移闸门判红。 -->

## 30 秒接入（无需注册表单 / 无需信用卡 / 无需审批）

**直接读数据（不需要任何 key）**
```bash
curl https://roboparts.cc/api/entities.json             # {n} 条实体全量
curl https://roboparts.cc/api/parameter_semantics.json  # 参数口径规范
```

**需要调用兼容性校验时，一行拿 key**
```bash
curl -X POST https://roboparts.cc/api/register \\
  -H "Content-Type: application/json" \\
  -d '{{"email":"you@example.com"}}'
# 即时返回 api_key + 100 次免费额度（30 次/小时），邮箱仅存 SHA-256 摘要
```

```bash
curl -X POST https://roboparts.cc/api/validate \\
  -H "Authorization: Bearer gtk_你的key" \\
  -H "Content-Type: application/json" \\
  -d '{{"components":["ACT-001","SEN-001"]}}'
```

**给 AI Agent 的说明**：机读接入描述见 [`agent-discovery.json`](https://roboparts.cc/agent-discovery.json) 与 [`llms.txt`](https://roboparts.cc/llms.txt)，可直接解析后代用户执行。

## 我们不隐瞒的四件事

在你决定是否使用这份数据前，这些事实值得先知道（数字均由生成器现算，不是宣传口径）：

1. **{n} 条实体中，参数口径达到"可跨厂商直接比较"的是 0 条。** 行业普遍不声明测试条件——扭矩不给温升与持续时间、背隙不给加载条件。我们把这个缺陷公开登记（含我方自身数据的同类问题），而不是用漂亮数字掩盖。判据见 [参数口径规范](https://roboparts.cc/robot-joint-parameter-spec)。
2. **机械互换维度（"能不能拧上去"）声明率仅 {mi['rate']:.2f}%。** 适用分母 {mi['applicable']} 条（总数 {n} 减去 {mi['n_a']} 条本身无机械接口的实体）中，仅 {mi['declared']} 条完整声明 + {mi['partial']} 条部分声明；其余 {mi['not_declared']} 条如实标注 `not_declared`，我们不做猜测填充。
3. **溯源分布是公开的**：{tier_summary}。Tier C 为无溯源历史导入，`confidence` 上限 0.30。有原始链接（`source_url`）的实体 {cov['source_url']} 条（{pct(cov['source_url'])}）——**意味着约 {pct(n - cov['source_url'])} 的实体目前无法一键回溯到原始文档**。
4. **兼容性结论是基于已声明数据的线索，不是认证，不替代样机实测。**

**为什么这仍然值得用**：RoboParts 不生产、不销售、不代理任何零部件。关节厂商自建的选型器无法回避一个结构性问题——选型结果天然偏向自家可造方案。中立是我们唯一无法被复制的东西，而中立的代价就是必须连自己的短板一起公开。

## 数据概览（{n} 实体 · {f['category_count']} 品类 · {now.strftime('%Y-%m-%d')} 更新）

| 品类 | 数量 | 高频字段（现算） |
|---|---|---|
{table}

**总计：{n} 个实体，覆盖 {f['category_count']} 大品类**

> 「高频字段」= 该品类中填充率 ≥ 40% 的业务字段，由生成器统计得出。
> 长尾品类（数量个位数）字段稀疏属实，未做填充美化。

## 数据质量（覆盖率现算，非宣传值）

| 字段 | 覆盖 | 覆盖率 | 说明 |
|---|---|---|---|
| 名称 | {cov['name']}/{n} | {pct(cov['name'])} | 官方型号或通用名称 |
| 厂商 | {cov['manufacturer']}/{n} | {pct(cov['manufacturer'])} | 采集自官网 / 目录 |
| 原始链接 | {cov['source_url']}/{n} | {pct(cov['source_url'])} | 可一键回溯到来源文档 |
| 价格区间 | {cov['price_range']}/{n} | {pct(cov['price_range'])} | 参考公开报价 |
| 标准符合性已评估 | {cov['std_assessed']}/{n} | {pct(cov['std_assessed'])} | ISO / GB / IEC / ROS2 维度 |

溯源分级（Provenance Tier）：

- `A` 一手可复核（官方规格书 / 标准文本 / 带链接厂商文档）—— 建议默认采信
- `B` 弱归因（厂商目录声明值）—— 可参考，需二次核验
- `C` 无溯源（历史导入待补）—— `confidence` 上限 0.30，带 `needs_provenance: true`

## 为什么是 RoboParts（不只是另一个选型器）

- 🔗 **跨品牌兼容性矩阵**：电气 / 机械 / 协议 / 软件四维兼容检测——选完型，来 RoboParts 验证「它能不能拼在一起」。
- 🤖 **AI 可检索（GEO 友好）**：`llms.txt` + `robots.txt` 显式欢迎 GPTBot / ClaudeBot / PerplexityBot 等抓取，数据可被大模型与 Agent 直接引用（CC-BY 4.0，注明出处即可）。
- 📦 **开源可下载**：数据集已发布至 [ModelScope（公开）](https://www.modelscope.cn/datasets/lm203688/roboparts-data)。
- 🧬 **仿生品类**：SEA 串联弹性驱动器、柔性驱动器、仿生脊柱、灵巧手、人工肌肉。
- ✅ **溯源透明**：每条实体标注 `source_tier`（A/B/C）+ `confidence`，公开 Tier C 与隔离数据的存在，可核验性优先于数量宣称。

## Topics

`robotics` `robot-parts` `humanoid-robot` `embodied-ai` `actuator` `sensor` `ros2` `bionic` `dataset` `open-data` `flexible-actuator` `robot-ai` `vla` `compatibility`

## 快速开始

### 方式一：Python SDK

```bash
pip install roboparts
```

```python
from roboparts import RoboPartsClient

client = RoboPartsClient()
data = client.get_all()

# 查找所有仿生执行器
bionic = client.filter(category="actuators", bionic=True)
print(f"找到 {{len(bionic)}} 个仿生执行器")

# 膝关节推荐（额定扭矩 > 80 Nm）
knee = client.filter(category="actuators", min_torque=80)
```

### 方式二：直接下载 JSON

```bash
curl -o roboparts-data.json https://roboparts.cc/api/data.json
```

### 方式三：在线选型引擎

访问 [roboparts.cc](https://roboparts.cc) 使用可视化选型 + 兼容性校验。

## 数据结构

分发文件 [`data/roboparts_full.json`](./data/roboparts_full.json) 的实体对象与官网
`/api/entities.json` **完全一致**（不裁剪字段），顶层结构：

```json
{{
  "meta": {{
    "total_entities": {n},
    "category_count": {f['category_count']},
    "category_counts": {{ "...": 0 }},
    "mechanical_interface_declared_rate_pct": {mi['rate']:.2f},
    "truth_source": "api/entities.json",
    "generated_by": "scripts/sync_dataset_dist.py"
  }},
  "entities": [ /* {n} 条 */ ]
}}
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

## 贡献

数据缺口是公开的（尤其机械接口声明率 {mi['rate']:.2f}%），欢迎补数据：

1. **补机械接口声明**（最缺、门槛最低）——
   用 [机械接口声明 Issue 模板](https://github.com/lm203688/roboparts/issues/new?template=mechanical-interface.yml)
   贴出处链接即可，**不必会写 JSON**，我们代录
2. **报数据错误** ——
   用 [数据纠错 Issue 模板](https://github.com/lm203688/roboparts/issues/new?template=data-correction.yml)
3. **提 PR 直接改** `api/entities.json`，本地跑 `python scripts/ci_gate.py` 自检后提交

贡献要求与最小可核验格式详见主仓
[`CONTRIBUTING.md`](https://github.com/lm203688/roboparts/blob/main/CONTRIBUTING.md)。
无出处的数据一律不收 —— 我们宁愿留着 `not_declared`，也不猜。

## 许可

[CC BY 4.0](./LICENSE) — 自由使用，需注明出处。

## 相关链接

- 官网 / 选型引擎：[https://roboparts.cc](https://roboparts.cc)
- 数据集（ModelScope，公开）：[https://www.modelscope.cn/datasets/lm203688/roboparts-data](https://www.modelscope.cn/datasets/lm203688/roboparts-data)
- Python SDK：[`python-sdk/`](./python-sdk)
- API 文档：[https://roboparts.cc/api-pricing](https://roboparts.cc/api-pricing)
- 数据主权中心：[https://roboparts.cc/data-hub](https://roboparts.cc/data-hub)
"""


def _norm_json(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + '\n'


# ---------------------------------------------------------------------------
# Python SDK（DIST/python-sdk/）内的对外数字
# ---------------------------------------------------------------------------
# 20260921 发现：python-sdk/ 是 DIST 下的**手维护**静态目录（不由本脚本产出），
# 它的数字从未纳入生成链 ⇒ 已实测失修成「已发布包对外撒谎」：
#
#     README.md   自称 688 实体 / 10 品类：执行器(199)、传感器(90)…
#                 真值   798 实体 / 20 品类：执行器(220)、传感器(95)…
#     README.md   套餐 Starter ¥9=500 积分 / Pro ¥29=2000 / Lifetime ¥199=9999
#                 真相源 functions/api/payment/create.js 是 100 / 500 / 999999
#
# 危害级别高于站点：这是 PyPI 上别人会 `pip install` 的产物，且 DIST 在
# .gitignore 里、SDK 又不在任何闸门扫描面内——数字错了没有任何机器会响。
#
# 处理：把 SDK 里承载数字的句子纳入本脚本重写面；任一条正则**失配即判红**，
# 防止 SDK 改版后这里静默失效（那会变成「闸门绿，但它已经没在看东西」）。
SDK_DIR = os.path.join(DIST, 'python-sdk')
PAYMENT_CFG = os.path.join(ROOT, 'functions', 'api', 'payment', 'create.js')


def plan_truth():
    """套餐（价格 / 积分）唯一真相源 = 真正扣费的那个文件。

    为什么不新造一个 plans.json：扣费逻辑已经在 create.js 里，再造一份就是
    「同一口径的第二份来源」，正是本项目反复踩的漂移起点。解析不足 3 档即抛。
    """
    src = open(PAYMENT_CFG, encoding='utf-8').read()
    out = {}
    for m in re.finditer(
            r"(\w+)\s*:\s*\{\s*price\s*:\s*(\d+)\s*,\s*credits\s*:\s*(\d+)\s*,", src):
        out[m.group(1)] = (int(m.group(2)), int(m.group(3)))
    if len(out) < 3:
        raise SystemExit('!! 从 functions/api/payment/create.js 解析到 %d 档套餐（<3），'
                         'SDK 套餐数字拒绝生成' % len(out))
    return out


def _cat_zh(cat):
    return CATEGORY_ZH.get(cat, cat).split(' (')[0]


def sdk_patches(facts, plans):
    """返回 {SDK 相对路径: [(正则, 替换), ...]}。每个正则都必须命中，否则判红。"""
    f = facts
    cats = f['categories']
    total = f['total']

    def n(cat):
        return cats.get(cat, 0)

    def plan_text(key):
        price, credits = plans[key]
        return '¥%d' % price, ('无限' if credits >= 999999 else '%d' % credits)

    cat_detail = '、'.join('%s(%d)' % (_cat_zh(c), cats[c])
                          for c, _ in sorted(cats.items(), key=lambda kv: -kv[1]))

    rp = {}

    # --- README.md（对外数据集卡片，HuggingFace / ModelScope 也展示它）---
    # 注：所有「去品牌词」类锚点必须写成 (旧|新) 二选一 —— 否则第一次跑完旧词没了，
    # 第二次跑就"锚点失配"判红（一次性替换不是幂等，会把闸门变成永远红）。
    rules = [
        (r'(?:仿生机器人零部件结构化数据|机器人零部件结构化数据)', '机器人零部件结构化数据'),
        (r'覆盖 \*\*\d+ 个实体\*\*[^\n]*',
         '覆盖 **%d 个实体** / **%d 个品类**：%s' % (total, f['category_count'], cat_detail)),
    ]
    for ep, cat in (('get_actuators', 'actuators'), ('get_sensors', 'sensors'),
                    ('get_chips', 'chips'), ('get_protocols', 'protocols')):
        rules.append((r'(\|\s*`%s\(limit\)`\s*\|\s*`GET /api/%s\.json`\s*\|\s*)\d+' % (ep, cat),
                      r'\g<1>%d' % n(cat)))
    rules.append((r'(\|\s*`get_entities\(\)`\s*\|\s*`GET /api/entities\.json`\s*\|\s*)\d+',
                  r'\g<1>%d' % total))
    for key in ('starter', 'pro', 'lifetime'):
        price, cred = plan_text(key)
        rules.append((r'(\|\s*`%s`\s*\|\s*)¥\d+(\s*\|\s*)(?:\d+|无限)' % key,
                      r'\g<1>%s\g<2>%s' % (price, cred)))
    rp['README.md'] = rules

    # --- roboparts/client.py（docstring 里的实体数与积分）---
    rules = []
    for cat, label in (('actuators', '执行器'), ('sensors', '传感器'),
                       ('chips', '芯片'), ('protocols', '通信协议')):
        rules.append((r'(获取%s列表（)\d+( 个实体，免费）)' % label, r'\g<1>%d\g<2>' % n(cat)))
    for key in ('starter', 'pro', 'lifetime'):
        price, cred = plan_text(key)
        rules.append((r'(- ``"%s"``: )¥\d+( / )(?:\d+|无限)( 积分)' % key,
                      r'\g<1>%s\g<2>%s\g<3>' % (price, cred)))
    rp['roboparts/client.py'] = rules

    # --- roboparts/__init__.py（包首屏 docstring）---
    rules = [
        (r'(?:仿生机器人零部件结构化数据|机器人零部件结构化数据)', '机器人零部件结构化数据'),
        (r'覆盖执行器\(\d+\)、传感器\(\d+\)、\s*芯片\(\d+\)、协议\(\d+\) 共 \d+ 个实体。',
         '覆盖执行器(%d)、传感器(%d)、\n芯片(%d)、协议(%d) 共 %d 个实体。'
         % (n('actuators'), n('sensors'), n('chips'), n('protocols'), total)),
    ]
    rp['roboparts/__init__.py'] = rules

    # --- roboparts/models.py（dataclass docstring）---
    rp['roboparts/models.py'] = [
        (r'(等 )\d+( 个执行器实体)', r'\g<1>%d\g<2>' % n('actuators')),
        (r'(等 )\d+( 个传感器实体)', r'\g<1>%d\g<2>' % n('sensors')),
    ]

    # --- 打包元数据（PyPI 上展示的 description）---
    rp['pyproject.toml'] = [
        (r'(?:仿生机器人零部件结构化数据|机器人零部件结构化数据)', '机器人零部件结构化数据')]
    # setup.py 的措辞少一个「结构化」（历史不一致），单独给锚点
    rp['setup.py'] = [
        (r'(?:仿生机器人零部件数据|机器人零部件数据)', '机器人零部件数据')]
    return rp


def sdk_sync(facts, write):
    """按真相源重写 SDK 内的对外数字。返回 (漂移文件列表, 失配列表)。

    write=True 时写盘；False 时只报告。**失配（正则没命中）永远算问题**——
    它意味着 SDK 结构变了、本脚本已经看不见那些数字了。
    """
    plans = plan_truth()
    patches = sdk_patches(facts, plans)
    drifted, unmatched = [], []
    for rel, rules in patches.items():
        p = os.path.join(SDK_DIR, rel.replace('/', os.sep))
        if not os.path.exists(p):
            unmatched.append('python-sdk/%s 不存在' % rel)
            continue
        cur = open(p, encoding='utf-8').read()
        new = cur
        for pat, rep in rules:
            if not re.search(pat, new):
                unmatched.append('python-sdk/%s 数字锚点失配 /%s/' % (rel, pat[:46]))
                continue
            new = re.sub(pat, rep, new)
        if new != cur:
            drifted.append('python-sdk/%s' % rel)
            if write:
                with open(p, 'w', encoding='utf-8', newline='') as fh:
                    fh.write(new)
    return drifted, unmatched


def main():
    check = '--check' in sys.argv
    if not os.path.exists(SRC):
        print(f'❌ 真相源缺失: {SRC}')
        return 2
    src = _load_src()
    facts = compute_facts(src)
    now = datetime.now(CST)

    new_data = build_data(src, facts, now)
    new_readme = build_readme(facts, now)

    problems = []

    # --- 数据文件比对（忽略 meta.updated 这类时间戳，只比实质内容）---
    def strip_ts(d):
        d = json.loads(json.dumps(d))
        (d.get('meta') or {}).pop('updated', None)
        return d

    old_data = None
    if os.path.exists(DIST_DATA):
        try:
            with open(DIST_DATA, encoding='utf-8') as f:
                old_data = json.load(f)
        except Exception as ex:
            problems.append(f'data/roboparts_full.json 解析失败: {ex}')
    if old_data is None:
        problems.append('data/roboparts_full.json 缺失')
    else:
        on = len(old_data.get('entities') or [])
        if on != facts['total']:
            problems.append(
                f"实体数漂移: 分发 {on} vs 真相源 {facts['total']}")
        oc = (old_data.get('meta') or {}).get('category_counts') or {}
        if oc != new_data['meta']['category_counts']:
            problems.append(
                f"meta.category_counts 漂移: 分发 {len(oc)} 品类 vs 真相源 "
                f"{facts['category_count']} 品类")
        if strip_ts(old_data) != strip_ts(new_data):
            problems.append('data/roboparts_full.json 内容与真相源现算结果不一致')

    # --- README 比对（逐字节；时间戳行单独宽容）---
    old_readme = None
    if os.path.exists(DIST_README):
        with open(DIST_README, encoding='utf-8') as f:
            old_readme = f.read()
    if old_readme is None:
        problems.append('README.md 缺失')
    else:
        def blur_date(s):
            import re
            return re.sub(r'\d{4}-\d{2}-\d{2} 更新', 'DATE 更新', s)
        if blur_date(old_readme.lstrip('\ufeff')) != blur_date(new_readme):
            # 给出可诊断的具体数字差异
            import re
            for label, pat, truth in (
                ('Entities badge', r'Entities-(\d+)-', facts['total']),
                ('总计实体', r'\*\*总计：(\d+) 个实体', facts['total']),
                ('品类数', r'覆盖 (\d+) 大品类\*\*', facts['category_count']),
            ):
                m = re.search(pat, old_readme)
                if m and int(m.group(1)) != truth:
                    problems.append(
                        f'README {label} 漂移: {m.group(1)} vs 真相源 {truth}')
            m = re.search(r'声明率仅 ([\d.]+)%', old_readme)
            if m and abs(float(m.group(1)) - facts['mi']['rate']) > 0.005:
                problems.append(
                    f"README 声明率漂移: {m.group(1)}% vs 真相源 "
                    f"{facts['mi']['rate']:.2f}%")
            problems.append('README.md 内容与真相源现算结果不一致')

    # --- Python SDK 内的对外数字（PyPI 已发布，见文件头注释）---
    sdk_drift, sdk_unmatched = sdk_sync(facts, write=not check)
    problems.extend(sdk_unmatched)
    if check:
        problems.extend('%s 对外数字与真相源不一致' % x for x in sdk_drift)

    if check:
        if problems:
            print('❌ 分发目录漂移（roboparts-dataset-github/ 会把错误数字发布到 '
                  'HuggingFace / ModelScope / PyPI）:')
            for p in problems:
                print(f'   - {p}')
            print('   修复: python scripts/sync_dataset_dist.py')
            return 1
        print(f"✅ 分发目录与真相源一致（{facts['total']} 实体 / "
              f"{facts['category_count']} 品类 / 声明率 {facts['mi']['rate']:.2f}%）")
        return 0

    os.makedirs(os.path.dirname(DIST_DATA), exist_ok=True)
    with open(DIST_DATA, 'w', encoding='utf-8', newline='\n') as f:
        f.write(_norm_json(new_data))
    with open(DIST_README, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_readme)

    print(f"✅ 已生成分发目录: {facts['total']} 实体 / "
          f"{facts['category_count']} 品类 / 声明率 {facts['mi']['rate']:.2f}%")
    if sdk_drift:
        print('   （SDK 对外数字已同步）')
        for x in sdk_drift:
            print(f'   - {x}')
    if problems:
        print('   （修正了以下漂移）')
        for p in problems:
            print(f'   - {p}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
