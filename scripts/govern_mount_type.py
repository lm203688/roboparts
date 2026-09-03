#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Schema 治理：mechanical_interface.mount_type 枚举统一（单一真相源 + 归一化 + 闸门）。

发现经过（20260831 项目完整性评估实测）：
  全库 798 实体的 mount_type 出现 **12 种写法**，而 registry 的权威分类
  `mounting_taxonomy`(TAXO-MOTOR-MOUNT) 只定义 5 个合法 key。三类问题：

  A. 同义异写（真违规，高危）
     ACT-028 / SENS-31 / BRG-crb-iko-crbf 写 'flange_mount'，权威 key 是 'flange'。
     这 3 条恰是全库唯一的 2 条 declared + 1 条法兰类 partial —— 最核心的声明数据
     全部落在权威枚举之外。按 mount_type 分组做孔位比对时会整组漏掉。
     （已核：build_negative_compat.py 按 standard 比对、不读 mount_type，
       故当前裁决结果未被污染；但任何未来按 mount_type 分组的消费方都会踩坑。）

  B. 语义冗余
     ACE-VIDIHAND-001 / ZEST-FRAMEWORK-001 写字符串 'N/A'，而 status 已是 n_a，
     且全库另有 355 条同语义用 null 表达 —— 同一语义两种载体。

  C. 权威分类作用域不足（不是数据错，是契约缺）
     TAXO-MOTOR-MOUNT 的 description 明写「关节电机安装方式分类」，
     但全库含连接器/轴承/仿生皮肤等非电机实体，其真实安装方式
     (wire_to_board / press_fit / surface_mount / adhesive / integrated)
     在权威分类里无位置。

  D. 维度混淆
     XFA-017 写 'research_prototype' —— 这是**成熟度**不是安装方式。
     其 gap 字段已载明「研究原型阶段，无标准化接口」，信息不丢，故 mount_type
     归一为 unknown（安装方式确实未知）。

根因：无单一枚举源、无闸门。各写入脚本各写各的 ——
  add_bionic_entities.py -> 'flange'
  backfill_platform_flanges.py / backfill_platforms_hub.py -> 'flange_mount'
  add_reference_entities.py -> 'N/A'
写完即入库，无任何校验拦截。

附带修掉的对外失真：
  build_flange_page.py 对外宣称「RoboParts 数据库中 mechanical_interface.mount_type
  字段即取以下枚举值」并只渲染 TAXO 的 5 个值 —— 与实际 12 种写法不符。
  本脚本把扩展枚举写进 registry，供该页渲染真实全库口径。

设计原则（严禁编造）：
  1. 标准派生组（standard_derived）逐字沿用 TAXO-MOTOR-MOUNT 的 key/label/definition，
     不改一字、不新增；出处即该 taxonomy 的 source（cssn.net.cn 标准文本 4.1.6）。
  2. 扩展组（roboparts_extension）显式标注 `authority: "roboparts_internal"`，
     不冒充标准术语；每项写明为何标准分类装不下它。
  3. 归一化只做**同义合并**与**冗余消除**，不新增语义、不猜测未知实体的安装方式。
  4. 归一化前后逐条打印，可审计。

幂等：可重复运行。--check 模式只读不写，供 regression / CI 闸门调用。
"""
import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES_PATH = os.path.join(ROOT, 'api', 'entities.json')
REGISTRY_PATH = os.path.join(ROOT, 'api', 'mechanical_interfaces.json')

REGISTRY_NODE = 'mount_type_enum'

# ---- 归一化映射（只做同义合并 / 冗余消除）---------------------------------
# value: (归一目标, 判据说明)  目标为 None 表示写 JSON null
ALIASES = {
    'flange_mount': ('flange', "同义异写；权威分类 TAXO-MOTOR-MOUNT 的 key 为 'flange'"),
    'N/A': (None, "status 已表达 n_a，且全库 355 条同语义用 null；消除双载体"),
    'research_prototype': ('unknown', "成熟度维度误入安装方式字段；成熟度信息已在 gap 中保留"),
}

# ---- 扩展枚举（RoboParts 内部建模口径，非标准术语）------------------------
EXTENSION_VALUES = [
    {
        'key': 'wire_to_board',
        'label': '线对板',
        'definition': '连接器类实体：线束一侧压接、另一侧焊装于 PCB，无法兰面。',
        'why_not_in_standard': 'TAXO-MOTOR-MOUNT 作用域为关节电机，未涵盖连接器。',
        'seen_on': ['CONN-molex-minimix'],
    },
    {
        'key': 'press_fit',
        'label': '压装',
        'definition': '靠过盈配合压入配合孔固定，无螺纹紧固件。',
        'why_not_in_standard': '轴承/衬套类装配方式，电机分类未涵盖。',
        'seen_on': ['BIONIC-JOINT-003'],
    },
    {
        'key': 'surface_mount',
        'label': '表面贴装',
        'definition': '贴装于基体表面（含回流焊或结构胶固定的贴装件）。',
        'why_not_in_standard': '元件级贴装方式，电机分类未涵盖。',
        'seen_on': ['BIONIC-ACTUATOR-002'],
    },
    {
        'key': 'adhesive',
        'label': '粘接',
        'definition': '靠胶粘剂与基体贴合固定，无机械紧固点（柔性皮肤/贴片式传感器常见）。',
        'why_not_in_standard': '柔性件固定方式，电机分类未涵盖。',
        'seen_on': ['BIONIC-SENSOR-001', 'BIONIC-SKIN-001'],
    },
    {
        'key': 'integrated',
        'label': '一体成型',
        'definition': '与本体一体制造、不存在可分离安装界面，故无可比对的互换标识。',
        'why_not_in_standard': '与 embedded（嵌入关节壳体、仍可拆）区别在于不可分离；电机分类未涵盖。',
        'seen_on': ['BIONIC-SENSOR-002'],
    },
]


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def dump(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def build_spec(taxo):
    """据 registry 的权威 taxonomy 现算枚举规格（标准组逐字沿用，不硬编码副本）。"""
    std_values = [
        {
            'key': v['key'],
            'label': v['label'],
            'definition': v['definition'],
        }
        for v in taxo['values']
    ]
    return {
        'id': 'ENUM-MOUNT-TYPE',
        'description': (
            'mechanical_interface.mount_type 的**全库**合法取值。分两组：'
            'standard_derived 逐字派生自 mounting_taxonomy(TAXO-MOTOR-MOUNT)，'
            '作用域为关节电机；roboparts_extension 为本平台内部建模扩展，'
            '用于标准分类装不下的非电机实体（连接器 / 轴承 / 柔性件等）。'
        ),
        'authority_note': (
            'standard_derived 组有标准出处；roboparts_extension 组**不是**任何标准的术语，'
            '是本平台为如实记录非电机实体安装方式而设的内部键名，'
            '不得被引用方当作标准编码转述。'
        ),
        'standard_derived': {
            'authority': 'standard',
            'derived_from': taxo['id'],
            'scope': taxo['description'],
            'source': taxo.get('source'),
            'source_tier': taxo.get('source_tier'),
            'values': std_values,
        },
        'roboparts_extension': {
            'authority': 'roboparts_internal',
            'scope': '非关节电机实体（连接器、轴承、仿生柔性件等）的安装方式',
            'source': 'RoboParts 内部建模口径（20260831 mount_type 枚举治理）',
            'source_tier': 'C',
            'values': EXTENSION_VALUES,
        },
        'null_policy': (
            'mount_type 为 null 表示「未采集/不适用」。'
            '实体是否适用机械接口由 mechanical_interface.status 表达（n_a=不适用），'
            'mount_type 不重复承载该语义 —— 故禁止写字符串 "N/A"。'
        ),
        'normalization_history': [
            {
                'at': '2026-08-31',
                'action': 'flange_mount -> flange',
                'reason': '同义异写归一至权威 key',
                'affected': ['ACT-028', 'SENS-31', 'BRG-crb-iko-crbf'],
            },
            {
                'at': '2026-08-31',
                'action': '"N/A" -> null',
                'reason': 'status 已表达 n_a，消除双载体',
                'affected': ['ACE-VIDIHAND-001', 'ZEST-FRAMEWORK-001'],
            },
            {
                'at': '2026-08-31',
                'action': 'research_prototype -> unknown',
                'reason': '成熟度维度误入安装方式字段；成熟度信息保留在 gap',
                'affected': ['XFA-017'],
            },
        ],
        'enforced_by': 'scripts/schema_contract.py（越界即判红）',
    }


def legal_keys(spec):
    keys = {v['key'] for v in spec['standard_derived']['values']}
    keys |= {v['key'] for v in spec['roboparts_extension']['values']}
    return keys


def scan(entities, keys):
    """返回 (违规列表, 分布计数)。"""
    violations = []
    dist = {}
    for e in entities:
        mi = e.get('mechanical_interface')
        if not isinstance(mi, dict):
            continue
        v = mi.get('mount_type')
        dist[v] = dist.get(v, 0) + 1
        if v is None:
            continue
        if v not in keys:
            hint = ''
            if v in ALIASES:
                tgt = ALIASES[v][0]
                hint = ' → 应归一为 %s' % ('null' if tgt is None else repr(tgt))
            violations.append('%s: mount_type 越界 %r%s' % (e.get('id', '?'), v, hint))
    return violations, dist


def main():
    ap = argparse.ArgumentParser(description='mount_type 枚举治理')
    ap.add_argument('--check', action='store_true',
                    help='只读校验：枚举节点在位 + 实体取值合法，越界 exit 1')
    args = ap.parse_args()

    reg = load(REGISTRY_PATH)
    ents_doc = load(ENTITIES_PATH)
    entities = ents_doc['entities']

    taxo = reg.get('mounting_taxonomy')
    if not taxo:
        print('❌ registry 缺 mounting_taxonomy，无法派生枚举')
        return 1

    spec = build_spec(taxo)
    keys = legal_keys(spec)

    if args.check:
        problems = []
        node = reg.get(REGISTRY_NODE)
        if not node:
            problems.append('registry 缺 %s 节点（未跑 govern_mount_type.py）' % REGISTRY_NODE)
        else:
            # 权威组必须与 taxonomy 逐字一致（防 taxonomy 改了枚举节点没跟）
            want = spec['standard_derived']['values']
            got = node.get('standard_derived', {}).get('values')
            if got != want:
                problems.append(
                    'registry.%s.standard_derived 与 mounting_taxonomy 漂移'
                    '（taxonomy 改动后需重跑 govern_mount_type.py）' % REGISTRY_NODE)
        v, dist = scan(entities, keys)
        problems.extend(v)
        if problems:
            print('❌ mount_type 闸门不通过（%d 项）：' % len(problems))
            for p in problems[:20]:
                print('   -', p)
            if len(problems) > 20:
                print('   ... 共 %d 项' % len(problems))
            print('   修复：python scripts/govern_mount_type.py')
            return 1
        print('✅ mount_type 闸门通过｜合法枚举 %d 个｜实体取值分布 %s'
              % (len(keys), {k: n for k, n in sorted(
                  dist.items(), key=lambda x: -x[1]) if k is not None}))
        return 0

    # ---- 写入模式 ----------------------------------------------------------
    print('=== mount_type 枚举治理 ===')
    before, _ = scan(entities, keys)
    print('归一前越界 %d 条' % len(before))

    changed = 0
    for e in entities:
        mi = e.get('mechanical_interface')
        if not isinstance(mi, dict):
            continue
        v = mi.get('mount_type')
        if v in ALIASES:
            tgt, why = ALIASES[v]
            mi['mount_type'] = tgt
            print('  %-24s %r → %s   （%s）'
                  % (e.get('id', '?'), v, 'null' if tgt is None else repr(tgt), why))
            changed += 1

    reg[REGISTRY_NODE] = spec
    reg['meta']['version'] = '1.2.0'
    reg['meta']['generated_at'] = datetime.datetime.now().astimezone().isoformat(
        timespec='seconds')

    dump(REGISTRY_PATH, reg)
    dump(ENTITIES_PATH, ents_doc)

    after, dist = scan(entities, keys)
    print('\n实体归一 %d 条｜registry 写入 %s（合法枚举 %d 个）'
          % (changed, REGISTRY_NODE, len(keys)))
    print('归一后越界 %d 条' % len(after))
    for a in after:
        print('  !', a)
    print('取值分布：%s' % {k: n for k, n in sorted(dist.items(), key=lambda x: -x[1])})
    print('\n后续：python scripts/normalize_categories.py（重生成派生文件）')
    return 1 if after else 0


if __name__ == '__main__':
    sys.exit(main())
