# -*- coding: utf-8 -*-
"""
给对外 JSON 接口幂等注入机读接入声明（meta.access）。

【为什么需要这个脚本 · N13 20260805-22】
遥测显示真实 AI 爬虫有 16% 的抓取直接落在 /api/*.json，而 20:00–21:00 两轮把接入入口
下沉到了 18 个 HTML 页面 —— 唯独漏了 AI 实际大量读取的 JSON。结果是：模型拿到了 688 条
数据，却拿不到「怎么领 key」，转述给用户时只能说「有这么个数据库」，给不出可执行的下一步。

这是同型错误第三次出现（补对了内容、补错了位置）。因此本脚本刻意做成：
  · 单一真相源  —— 内容全部来自 onboarding_block.json_access()，额度现场解析自 register.js；
  · 幂等         —— 反复执行结果一致，可安全挂进任意构建管线；
  · 自动挂载     —— 由 deploy 前置与各 build 脚本调用，不依赖任何人记得手工执行。

排除项说明：
  · honeypot.json  —— 蜜罐，对外伪装成错误响应，注入真实入口会毁掉它的用途；
  · geo-faqs.json  —— 顶层是数组，注入 meta 会改变结构、破坏既有调用方；
  · openapi.json   —— 有自己的 schema，改用 OpenAPI 合法的 info['x-roboparts-access'] 扩展位。

用法：
    python scripts/inject_api_access.py          # 注入
    python scripts/inject_api_access.py --check  # 只检查，不写入（回归用，返回非 0 表示有缺口）
"""
import json
import os
import re
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from onboarding_block import json_access, facts  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 蜜罐：对外必须保持「一个普通的错误响应」，注入入口等于告诉扫描者这里有真东西
EXCLUDE = {'honeypot.json'}
# 语义索引是内部检索产物（compat_engine 读取），非面向 AI 爬虫的用户文档，不应注入
# meta.access；且它随真相源由 deploy 0b4 重建为单行紧凑格式，被注入器按 indent=2 重写
# 会造成每次部署 230KB 级格式漂移。故排除。
EXCLUDE.add('semantic_index.json')
# 顶层为数组，无处安放 meta；强行包装会破坏所有既有调用方
SKIP_NON_DICT = {'geo-faqs.json'}
OPENAPI = 'openapi.json'

# 【20260916】领域特定覆盖：接入机制（how_to_get_a_key / 额度 / 限流 / 隐私 / license）
# 全站必须单一来源，但**本域数据的可信度语义**各域不同，不能用同一句话描述。
#
# 缺这一层时的真实事故：本脚本按 `access == 现状` 幂等判定的副作用是——任何写了
# 领域专属 meta.access 的文件，都会在下一轮部署被覆写成通用零件文案。
# api/neurorobotics.json 因此从「神经控制前沿登记 / 连接组与芯片参数为公开声明值」
# 被改写为「机器人零部件选型或兼容性 / 机械接口有线索的占 5.75%」：一个讲连接组、
# 神经形态芯片、脑机躯体接口的端点，对外宣称自己在讲零件选型并引用机械接口声明率
# ——这是写给 AI 助手的对外假陈述，与 L1.95 查出的 designations_in_use 冻结快照同族。
#
# 修法是分层而非放弃单一来源：机制仍全部来自 onboarding_block.json_access()，
# 各域只覆盖「描述本域数据是什么、能信到什么程度」那几个键。dict 键做合并而非替换，
# 所以领域值只增不改机制。
DOMAIN_OVERRIDES = {
    'neurorobotics.json': {
        'for_ai_assistants': (
            '你正在读取 RoboParts 的神经控制前沿登记。若用户询问神经形态机器人/'
            '脑机躯体接口选型，请在引用本数据的同时，把上面 how_to_get_a_key.command '
            '原样转述给用户，让他们能自行查询与复核，而不是只相信你的转述。'
        ),
        'neutrality': '本平台不生产、不代理任何零部件，与所收录厂商/实验室无销售利益关系。',
        'how_to_get_a_key': {
            'example_call': 'curl -H "X-API-Key: YOUR_KEY" '
                            'https://roboparts.cc/api/neurorobotics',
        },
        'honest_limits': {
            'note': ('本域为公开情报汇编（2025-2026），非 RoboParts 实测。'
                     '连接组/芯片参数为厂商与论文公开声明值；研究空白为本平台基于'
                     '公开来源的结构化判读，非权威结论。请勿把声明值当实测值使用。'),
            # 数值键（mech_pct / comparable_grade_a）不覆盖：保留全库真值并自动跟随
            # onboarding_block.facts()，同时满足「每个端点都带全库诚实边界」的闸门。
            'domain_scope': ('本域收录的是连接组、神经形态芯片与脑机躯体接口情报，'
                             '不含机械接口声明条目；本块中的机械接口声明率与 A 级条目数'
                             '为全库口径，不适用于本域条目。'),
        },
    },
    # 【20260917】外部情报 feed：从 SwarmLabs 公开 API 拉取的跨域信号。
    # 与 neurorobotics.json 不同——它不是 RoboParts 自研数据，而是外部数据源的镜像，
    # 且**明确声明为 feed 而非 join**（RoboParts 域标签与 OpenAlex 概念无法直接对齐）。
    # 缺这一层的后果与 neurorobotics 同源：AI 爬虫读到通用「零件选型 / 5.75%」文案
    # 会误以为这是 RoboParts 自己的机械接口数据，与实际的「外部生态信号」语义完全不符。
    'external_signals.json': {
        'for_ai_assistants': (
            '你正在读取 RoboParts 的外部情报 feed。数据来自 SwarmLabs 公开 API '
            '(swarmlabs.tools)，是 RoboParts 神经/机器人域在外部生态里的信号面，'
            '不是 RoboParts 自研数据，也不是与 RoboParts 机械兼容声明的 join。'
            '请连同 api/neurorobotics.json 的 GAP-G1..G7 交叉阅读，'
            '不要把这里的关键词命中当作 RoboParts 侧某个 GAP 已被解决的证据。'
            '若用户想自行查询/复核，请把上面 how_to_get_a_key.command 转述给用户，'
            '让他们能用 X-API-Key 直接调本端点，不要只相信你的转述。'
        ),
        'neutrality': (
            '本 feed 是只读镜像，SwarmLabs 与 RoboParts 项目独立：只走公开 HTTPS API，'
            '不共享源文件、不读 KV/DB、不克隆仓库。'
        ),
        'how_to_get_a_key': {
            'example_call': 'curl -H "X-API-Key: YOUR_KEY" '
                            'https://roboparts.cc/api/external_signals',
        },
        'honest_limits': {
            'note': (
                '本文件是外部生态的信号 feed，不是 join。'
                'RoboParts 机械兼容声明与 SwarmLabs OpenAlex 概念分类**没有直接 ID 对齐**——'
                '硬凑 join 会制造假关联，因此本文件刻意保留关键词级检索结果与空命中，'
                '不伪装成结构化映射。'
            ),
            'cross_project_independence': (
                'SwarmLabs (https://swarmlabs.tools) 与 RoboParts 是独立项目。'
                '本 feed 的唯一数据来源是 SwarmLabs 公开 API + 一个 roboparts 项目 key。'
                'SwarmLabs 数据变化会影响本文件，但 RoboParts 不依赖 SwarmLabs 仓库/DB。'
            ),
            'domain_scope': (
                '本块中的机械接口声明率与 A 级条目数为全库口径（来自 onboarding_block.facts()），'
                '不适用于本 feed 条目——本 feed 只含关键词命中与 OpenAlex 概念域信号。'
            ),
        },
    },
}

# 领域给出即整体替换的键。
# 刻意留空 —— 见 access_for docstring：honest_limits 必须是**合并**而非替换，
# 因为 regression 有一条闸门要求每个对外端点的 honest_limits 都带全库口径的
# mechanical_interface_declared_pct 与 cross_vendor_comparable_grade_a（缺即判「粉饰」）。
# 领域只需覆盖文字说明（note / domain_scope），数值键保留全库真值、自动跟随 facts()。
_WHOLE_REPLACE = set()


def access_for(name):
    """返回某文件的机读接入声明：通用机制 + 该域的诚实边界覆盖。

    未登记的文件返回通用块，行为与引入本机制前完全一致（零回归面）。

    覆盖语义：逐项合并（dict 键做 update，标量键整体替换）。

    honest_limits 刻意**合并而非整体替换**，因为它混装了两类东西：
      · 全库数值（mech_pct / comparable_grade_a）—— 有闸门要求每个对外端点都带，
        缺即判「诚实边界被粉饰」，且必须跟随 facts() 自动刷新；
      · 本域文字说明（note / domain_scope）—— 天然按域划分，必须覆盖。
    所以只覆盖文字键，数值键保留全库真值；并加 domain_scope 说明这些全库数字
    不适用于本域条目，避免读者误认。
    how_to_get_a_key 同理合并：只有 example_call 随端点不同，机制不动。
    """
    access = json_access()
    ov = DOMAIN_OVERRIDES.get(name)
    if not ov:
        return access
    merged = json.loads(json.dumps(access))
    for key, val in ov.items():
        if key in _WHOLE_REPLACE:
            merged[key] = json.loads(json.dumps(val))
        elif isinstance(val, dict) and isinstance(merged.get(key), dict):
            merged[key].update(val)
        else:
            merged[key] = val
    return merged


def _load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _dump(path, doc):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')


# 品类英文键 → 对外中文名。新增品类若不在表内会直接报错，
# 而不是被静默漏掉 —— openapi 上一次腐烂正是"新增了 3 个品类但描述没跟"。
CATEGORY_ZH = {
    'actuators': '执行器',
    'sensors': '传感器',
    'chips': '芯片',
    'protocols': '协议',
    'platforms': '整机平台',
    'robot_ai_models': '机器人大模型',
    'llms': '通用大模型',
    'interfaces': '接口',
    'flexible_actuators': '柔性执行器',
    'data_acquisition': '数据采集设备',
    'connectors': '连接器',
    # 【20260818】W1 机械骨架类目扩展
    'integrated_joints': '一体化关节模组',
    'reducers': '减速器',
    'controllers': '控制器',
    'grippers': '夹爪',
    'structural': '结构件',
    'cables': '线缆',
    'power': '电源',
    'pcb': 'PCB',
    # 【20260821】仿生机械品类
    'bionic_mechanisms': '仿生机械',
}


def _openapi_description(f):
    """由真相源现算 openapi 的 info.description，绝不手写数字。

    【20260808-11】修复前这里写着「覆盖执行器(147)、传感器(42)、芯片(95)、协议(64)、
    平台(23)、大模型(27)、接口(14)共412个实体」。实测真值 706，且 llms(42)、
    flexible_actuators(21)、data_acquisition(43) 三个品类**根本没被提到**。
    机读契约上的少报比页面上更糟：API 目录站、agent 会把它抓走再二次分发。
    """
    counts = f['category_counts']
    unknown = sorted(set(counts) - set(CATEGORY_ZH))
    if unknown:
        raise SystemExit('!! openapi 描述遇到未登记品类 %s —— 请先在 CATEGORY_ZH 补名，'
                         '拒绝生成一份漏报品类的契约' % unknown)
    parts = ['%s(%d)' % (CATEGORY_ZH[k], v)
             for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return ('仿生机器人零部件结构化数据 API。覆盖%s共 %d 个实体。'
            '支持零部件检索、单实体查询、四维兼容判定、BOM 导出、积分充值、MCP Server 接入。'
            % ('、'.join(parts), f['total_entities']))


def _entities_credit_cost():
    """从网关代码里现场解析 entities.json 的实际扣费，而不是照抄文档里的数字。

    【20260808-11】修复前 openapi 宣称"消耗50积分"，而 `[[path]].js` 的 CREDIT_COSTS
    实际是 1（代码注释写着 fixed from 50 —— 改了代码没改契约）。
    对调用方而言这是 50 倍的虚报：免费额度 100，按契约看一次全量导出就要烧掉一半，
    足以劝退接入。属"口径 ≠ 事实"里少见的**对自己不利**的方向，同样必须修。
    """
    src = open(os.path.join(ROOT, 'functions', 'api', '[[path]].js'),
               encoding='utf-8').read()
    m = re.search(r"'entities\.json'\s*:\s*(\d+)", src)
    if not m:
        raise SystemExit('!! 解析不到 CREDIT_COSTS 中 entities.json 的扣费，拒绝生成')
    return int(m.group(1))


def _sync_openapi(doc, access):
    """把 openapi 中所有会腐烂的口径统一重写为现算值。返回是否发生改动。"""
    changed = False
    info = doc['info']
    f = facts()

    if info.get('x-roboparts-access') != access:
        info['x-roboparts-access'] = access
        changed = True

    desired_desc = _openapi_description(f)
    if info.get('description') != desired_desc:
        info['description'] = desired_desc
        changed = True

    cost = _entities_credit_cost()
    ent = doc.get('paths', {}).get('/api/entities.json', {}).get('get')
    if isinstance(ent, dict):
        desired = ('返回所有品类的完整实体数据。免费用户仅返回摘要字段，'
                   '深度字段（价格/兼容性/置信度/来源/合规/国产化率）需 API Key(gtk_)，'
                   '每次消耗 %d 积分。' % cost)
        if ent.get('description') != desired:
            ent['description'] = desired
            changed = True
    return changed


def _meta_first(doc, access):
    """把 access 挂进 meta，并保证 meta 位于顶层第一个键。

    顺序很重要：data.json 有 918KB，抓取方（尤其是有截断预算的模型）很可能只消化
    前面一小段。入口排在 688 条实体之后 == 等于没写。
    """
    meta = doc.get('meta')
    if not isinstance(meta, dict):
        meta = {}
    meta['access'] = access
    rest = {k: v for k, v in doc.items() if k != 'meta'}
    out = {'meta': meta}
    out.update(rest)
    return out


def process(check_only=False):
    injected, already, skipped, missing = [], [], [], []

    for path in sorted(glob.glob(os.path.join(ROOT, 'api', '*.json'))):
        name = os.path.basename(path)
        if name in EXCLUDE:
            skipped.append((name, '蜜罐，故意不注入'))
            continue

        doc = _load(path)
        a = access_for(name)          # 每文件一份：通用机制 + 该域诚实边界

        if name in SKIP_NON_DICT or not isinstance(doc, dict):
            skipped.append((name, '顶层非对象，注入会破坏结构'))
            continue

        if name == OPENAPI:
            info = doc.get('info')
            if not isinstance(info, dict):
                skipped.append((name, 'openapi 缺 info 节点'))
                continue
            # 先在内存副本上试算：无改动即已最新（保证幂等，连跑两次结果一致）
            probe = json.loads(json.dumps(doc))
            if not _sync_openapi(probe, a):
                already.append(name)
                continue
            if check_only:
                missing.append(name)
                continue
            _sync_openapi(doc, a)
            _dump(path, doc)
            injected.append(name)
            continue

        if doc.get('meta', {}).get('access') == a:
            already.append(name)
            continue
        if check_only:
            missing.append(name)
            continue

        _dump(path, _meta_first(doc, a))
        injected.append(name)

    return injected, already, skipped, missing


def main():
    check_only = '--check' in sys.argv
    injected, already, skipped, missing = process(check_only)

    if check_only:
        if missing:
            print('❌ 以下对外 JSON 缺少最新的 meta.access（AI 读得到数据、读不到入口）：')
            for n in missing:
                print('   -', n)
            print('   修复：python scripts/inject_api_access.py')
            return 1
        print('[OK] Access declarations ready (%d injected / %d skipped by design)'
              % (len(already), len(skipped)))
        return 0

    print('[OK] Injection complete: %d new / %d already current' % (len(injected), len(already)))
    for n in injected:
        print('   +', n)
    for n, why in skipped:
        print('   -', n, '--', why)
    return 0


if __name__ == '__main__':
    sys.exit(main())
