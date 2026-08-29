# -*- coding: utf-8 -*-
"""
为 api/entities.json 全量补 mechanical_interface 字段（机械互换维度）。

设计原则（与本库数据质量闸门一致）：
  1. 不臆造尺寸。无公开出处的法兰/孔位一律留 null，用 status 显式表达"未声明"。
  2. 把"静默缺失"变成"可查询的缺口"——agent 查询时能明确得到 not_declared / n_a，
     而不是字段不存在导致的歧义。
  3. 非机械耦合类实体（芯片/协议/LLM/数据集/电气总线）标 n_a，避免污染覆盖率分母。

幂等：可重复运行。
"""
import json
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, 'api', 'entities.json')
REGISTRY_REF = '/api/mechanical_interfaces.json'

# 机械可耦合类目：存在物理安装面，需要机械接口数据
# 【20260809-07】connectors 属机械可耦合：连接器有对接面、防呆/极性、安装方向与
# 板端占位尺寸 —— 正是"接口兼容"最物理的那一层。它必须进机械声明率分母，
# 否则新录的连接器哪怕一条尺寸都没有也不显示为缺口（记 n_a = 宣称"本来就不需要"）。
MECH_RELEVANT = {'actuators', 'flexible_actuators', 'sensors', 'platforms', 'connectors'}
# 非机械耦合类目：软件/半导体/协议/总线/数据集
MECH_NA = {'chips', 'protocols', 'llms', 'robot_ai_models', 'data_acquisition', 'interfaces'}

NA_REASON = '非机械耦合类实体（芯片/协议/模型/数据集/电气总线），无物理安装面'

# 【20260809-03】entity_kind 非 component 的条目（企业主体 / 市场情报报告）
# 根本不是实物，却曾按类目落进 not_declared，等于宣称"这家公司有安装面但没告诉我们"。
# 它们必须计 n_a：既不污染机械覆盖率分母，也不让 agent 误以为是可补齐的缺口。
NON_COMPONENT_NA_REASON = '%s 条目（企业主体/市场情报），不是实物零部件，无物理安装面'

# 【20260809-04】补数据通道曾被本脚本自己堵死。
#
# 原实现对全部 706 条无条件 `e['mechanical_interface'] = build(e)`，而 build() 里
# 唯一能产出 partial 的来源是下面这张**写死在源码里的 2 条白名单**。后果：
#   · declared 永远是 0，partial 永远 ≤ 2，与实际采集到多少数据无关；
#   · 任何人（或 agent）把厂商声明写进 api/entities.json，下一次本脚本一跑就被抹掉；
#   · 而"补 declared 机械数据 / fill_pct 0.54%"恰恰是长期挂在待办首位的头号瓶颈。
# 也就是说：名字叫 add_mechanical_interface 的脚本，是唯一在删除机械接口数据的东西。
#
# 修法：条目自身已带**有出处**的声明时原样保留，本脚本只负责给没有声明的补默认值。
# 白名单降级为种子，不再是唯一入口。
CURATED_STATUSES = ('declared', 'partial')


def _curated(entity):
    """判断条目自带的 mechanical_interface 是否为可保留的有据声明。

    要求两条，缺一不可：
      1. status ∈ declared/partial —— not_declared / n_a 是本脚本自己的产物，不算声明；
      2. source 非空 —— 没出处的"已声明"就是凭空断言，保留它等于给假绿开后门（L1.64 族）。
    另外 declared 必须真带 standard 或 flange：只写 status='declared' 却没有任何
    可比对尺寸，是"标签绿、内容空"，判定引擎拿它做孔位级互换会得出错误结论。
    """
    mi = entity.get('mechanical_interface')
    if not isinstance(mi, dict):
        return None
    if mi.get('status') not in CURATED_STATUSES:
        return None
    if not str(mi.get('source') or '').strip():
        return None
    if mi.get('status') == 'declared' and not (mi.get('standard') or mi.get('flange')):
        return None
    out = dict(mi)
    out['registry_ref'] = REGISTRY_REF
    return out


# 有厂商公开声明、但未给出尺寸的条目（partial）——种子，非唯一入口
PARTIAL = {
    'SENS-ft-sri-c025xx': {
        'mount_type': 'direct_mount',
        'declared': '单侧安装，无需转接法兰（厂商声明）',
        'source': '宇立仪器官网产品页 (srisensor.com.cn)',
        'confidence': 0.7,
    },
    'SENS-ft-sri-c075xx': {
        'mount_type': 'direct_mount',
        'declared': '无需转接法兰，可直接安装于协作机器人（厂商声明）',
        'source': '宇立仪器官网产品页 (srisensor.com.cn)',
        'confidence': 0.7,
    },
}


def build(entity):
    cat = entity.get('category')
    eid = entity.get('id')

    kind = entity.get('entity_kind')
    if kind and kind != 'component':
        return {
            'status': 'n_a',
            'reason': NON_COMPONENT_NA_REASON % kind,
            'registry_ref': REGISTRY_REF,
        }

    # 已有有据声明 → 原样保留。放在类目默认值之前：类目映射只是启发式默认，
    # 而"某条目确实有厂商公开的机械接口出处"是针对该条目的具体事实，事实优先。
    kept = _curated(entity)
    if kept is not None:
        return kept

    if cat in MECH_NA:
        return {
            'status': 'n_a',
            'reason': NA_REASON,
            'registry_ref': REGISTRY_REF,
        }

    if eid in PARTIAL:
        p = PARTIAL[eid]
        return {
            'status': 'partial',
            'mount_type': p['mount_type'],
            'standard': None,
            'flange': None,
            'declared_note': p['declared'],
            'source': p['source'],
            'confidence': p['confidence'],
            'registry_ref': REGISTRY_REF,
            'gap': '缺法兰节圆/孔数/螺纹规格，无法做孔位级互换判定',
        }

    if cat in MECH_RELEVANT:
        return {
            'status': 'not_declared',
            'mount_type': 'unknown',
            'standard': None,
            'flange': None,
            'confidence': 0.0,
            'registry_ref': REGISTRY_REF,
            'gap': '厂商未公开或尚未采集机械安装接口规格',
        }

    # 兜底：未知类目按未声明处理，不静默丢失
    return {
        'status': 'not_declared',
        'mount_type': 'unknown',
        'standard': None,
        'flange': None,
        'confidence': 0.0,
        'registry_ref': REGISTRY_REF,
        'gap': f'未归类类目 {cat}',
    }


def main():
    with io.open(ENT, encoding='utf-8') as f:
        doc = json.load(f)

    ents = doc['entities']
    stats = {'n_a': 0, 'not_declared': 0, 'partial': 0, 'declared': 0}

    for e in ents:
        mi = build(e)
        e['mechanical_interface'] = mi
        stats[mi['status']] = stats.get(mi['status'], 0) + 1

    denom = stats['not_declared'] + stats['partial'] + stats['declared']
    filled = stats['declared'] + stats['partial']

    doc['meta']['mechanical_interface_coverage'] = {
        'schema_version': '1.0.0',
        'registry': REGISTRY_REF,
        'applicable': denom,
        'not_applicable': stats['n_a'],
        'declared': stats['declared'],
        'partial': stats['partial'],
        'not_declared': stats['not_declared'],
        'fill_pct': round(filled * 100.0 / denom, 2) if denom else 0.0,
        'note': '机械互换维度基线。fill_pct 为已获得厂商声明的比例；'
                'not_declared 为显式缺口（可被 agent 查询），非字段缺失。',
    }

    with io.open(ENT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')   # 与仓库内既有落盘格式一致，避免每跑一次都产生一行"无换行符"假差异

    print('mechanical_interface 写入完成')
    print('  适用实体 (applicable):      ', denom)
    print('  不适用   (n_a):             ', stats['n_a'])
    print('  已声明   (declared):        ', stats['declared'])
    print('  部分声明 (partial):         ', stats['partial'])
    print('  未声明   (not_declared):    ', stats['not_declared'])
    print('  填充率   (fill_pct):        ', doc['meta']['mechanical_interface_coverage']['fill_pct'], '%')
    print('  合计:', denom + stats['n_a'], '/', len(ents))


if __name__ == '__main__':
    main()
