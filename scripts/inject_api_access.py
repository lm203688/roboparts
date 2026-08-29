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
# 顶层为数组，无处安放 meta；强行包装会破坏所有既有调用方
SKIP_NON_DICT = {'geo-faqs.json'}
OPENAPI = 'openapi.json'


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
    access = json_access()
    injected, already, skipped, missing = [], [], [], []

    for path in sorted(glob.glob(os.path.join(ROOT, 'api', '*.json'))):
        name = os.path.basename(path)
        if name in EXCLUDE:
            skipped.append((name, '蜜罐，故意不注入'))
            continue

        doc = _load(path)

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
            if not _sync_openapi(probe, access):
                already.append(name)
                continue
            if check_only:
                missing.append(name)
                continue
            _sync_openapi(doc, access)
            _dump(path, doc)
            injected.append(name)
            continue

        if doc.get('meta', {}).get('access') == access:
            already.append(name)
            continue
        if check_only:
            missing.append(name)
            continue

        _dump(path, _meta_first(doc, access))
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
        print('✅ 对外 JSON 接入声明齐备（%d 个已注入 / %d 个按设计跳过）'
              % (len(already), len(skipped)))
        return 0

    print('✅ 注入完成：新写入 %d 个 / 已最新 %d 个' % (len(injected), len(already)))
    for n in injected:
        print('   +', n)
    for n, why in skipped:
        print('   ·', n, '——', why)
    return 0


if __name__ == '__main__':
    sys.exit(main())
