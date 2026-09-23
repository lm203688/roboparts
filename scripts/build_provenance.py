#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_provenance.py —— 具身跨层溯源（D6）生成器

单一真相源（只读）：
    api/entities.json                 body 层（实体 + 溯源等级）
    api/morphology_graph.json         body 层的端口/类型结构
    api/neurorobotics.json            连接组登记 + signal_contracts
    api/robot_ai_models.json          policy 层
    api/mechanical_interfaces.json    / 其它按需
产出：
    api/provenance.json               由本脚本生成，禁止手改

设计要点（为什么不写成「一份描述文档」）
----------------------------------------
本项目的病史是「口径 ≠ 事实」：写一段"我们支持端到端溯源"的散文，没人能证伪。
故本产物把「链」做成**四个机器可判定的连接条件**，每条的条件现算：

    L1 neuron→topology : 是否存在 motif id 引用了已登记的 connectome_ref
    L2 topology→body   : signal_contract.body.actuators[].id 是否落在一个真实实体 id 上
    L3 body→policy     : robot_ai_models 条目是否引用真实实体 id
    L4 policy→behavior : 是否存在运行日志（行为层）

任何一条从 false 变 true，产物自动更新 —— 于是它同时是**活的 gap tracker**，
而不是需要人记得回来改的静态文档。当前四条全 false，产物如实报 `0 条完整链`。

用法：
    python scripts/build_provenance.py
    python scripts/build_provenance.py --dry-run
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

ENT = os.path.join(ROOT, 'api', 'entities.json')
MG = os.path.join(ROOT, 'api', 'morphology_graph.json')
NR = os.path.join(ROOT, 'api', 'neurorobotics.json')
RAM = os.path.join(ROOT, 'api', 'robot_ai_models.json')
OUT = os.path.join(ROOT, 'api', 'provenance.json')
SCHEMA = os.path.join(ROOT, 'schemas', 'embodiment_provenance.schema.json')
TZ = timezone(timedelta(hours=8))

LAYER_ORDER = ['neuron', 'topology', 'body', 'policy', 'behavior']


def _load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def _referenced_ids(obj, id_set, prefix_re=None, skip_keys=('id',)):
    """结构里出现的、命中给定 id 集合的字符串（完全相等，或作为独立 token 出现）。

    `skip_keys` 是**必需**的，不是可选优化：层间引用判定极易被自引用污染。
    真实事故（本脚本首版）：L3（body→policy）判据把 robot_ai_models 条目与自己比
    —— 而 `robot_ai_models.json` 是 entities.json 里那 46 条实体的**派生视图**，
    条目的 `id` 本身就是实体 id，于是"引用自己"被算成了一次跨层引用，
    判据报 satisfied=True 而真实的物理零件引用数是 **0**。
    加 `skip_keys=('id',)` 后判据才回答它真正要问的问题：「策略层有没有指向躯体」。
    """
    hits = set()
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, str):
            if cur in id_set:
                hits.add(cur)
            elif prefix_re and prefix_re.search(cur):
                for tok in re.split(r'[\s,;/|()（）]+', cur):
                    if tok in id_set:
                        hits.add(tok)
        elif isinstance(cur, dict):
            for k, v in cur.items():
                if k in skip_keys:
                    continue
                stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return hits


def build(with_timestamp=True):
    ents_doc = _load(ENT)
    ents = ents_doc['entities']
    ent_ids = {e['id'] for e in ents}
    # 躯体层 = 物理零件（component）。刻意排除 specification/software/organization/
    # market_intelligence —— 策略层指向一份规范文档不算"链上躯体"。
    body_ids = {e['id'] for e in ents if (e.get('entity_kind') or 'component') == 'component'}
    nr = _load(NR)
    ram = _load(RAM)
    mg = _load(MG) if os.path.exists(MG) else {}

    prov_cov = (ents_doc.get('meta') or {}).get('provenance_coverage') or {}
    connectomes = nr.get('connectomes') or []
    conn_ids = {c.get('id') for c in connectomes if c.get('id')}
    contracts = nr.get('signal_contracts') or []
    models = ram.get('data') or []

    # ── 层清单（全部现算） ──
    layers = [
        {
            'id': 'neuron',
            'title_zh': '神经元 / 连接组',
            'owner': 'external(flybrain-connectome)',
            'available': 'external_not_ingested',
            'count': len(connectomes),
            'ref': '/api/neurorobotics.json#connectomes',
            'prov': {
                'source': 'neurorobotics registry 登记的外部连接组（MaleCNS v1.0 / FlyWire 等）',
                'tier': 'B',
                'prov_o_class': 'entity',
                'activity': '电子显微镜重建 + 自动分割 + 人工校对',
                'agent': 'Google/Janelia 等（见各条目 source）',
                'note': '本仓只登记与引用，**不复制连接组数据**（项目独立原则，见 neurorobotics/README.md）。',
            },
        },
        {
            'id': 'topology',
            'title_zh': '拓扑 / 神经回路',
            'owner': 'external(flybrain-connectome)',
            'available': 'declared_empty',
            'count': 0,
            'ref': None,
            'prov': {
                'source': '暂无：本仓未 ingest 任何 motif/回路拓扑',
                'tier': None,
                'prov_o_class': 'entity',
                'activity': None,
                'agent': None,
                'note': 'flybrain 侧有 connectome 派生 motif，但本仓未纳入；此项为显式空层。',
            },
        },
        {
            'id': 'body',
            'title_zh': '躯体 / 零件与接口',
            'owner': 'roboparts',
            'available': 'partial',
            'count': len(ents),
            'ref': '/api/morphology_graph.json',
            'prov': {
                'source': 'api/entities.json（逐条带 source/source_tier/last_verified）',
                'tier': 'A',
                'prov_o_class': 'entity',
                'activity': '厂商目录 / 规格书 / 标准文本采集与归一化',
                'agent': 'roboparts.cc',
                'note': '本仓自持层。Tier A 可点开复核 %s/%d（%s%%）；A/B/C 分级判据唯一源 '
                        'scripts/govern_source_tier.py。'
                        % (prov_cov.get('tier_a_traceable'), len(ents),
                           prov_cov.get('traceable_pct')),
            },
        },
        {
            'id': 'policy',
            'title_zh': '策略 / 学习模型',
            'owner': 'roboparts',
            'available': 'partial',
            'count': len(models),
            'ref': '/api/robot_ai_models.json',
            'prov': {
                'source': 'api/robot_ai_models.json',
                'tier': 'B',
                'prov_o_class': 'entity',
                'activity': '公开模型/平台信息采集',
                'agent': 'roboparts.cc',
                'note': '有模型条目，但**均未与躯体实体建立引用**（L3 连接条件不满足）。',
            },
        },
        {
            'id': 'behavior',
            'title_zh': '行为 / 运行日志',
            'owner': 'roboparts',
            'available': 'declared_empty',
            'count': 0,
            'ref': None,
            'prov': {
                'source': '暂无：本仓无任何具身运行日志',
                'tier': None,
                'prov_o_class': 'entity',
                'activity': None,
                'agent': None,
                'note': '行为层是链的终点。空即是空，不臆造。',
            },
        },
    ]

    # ── L1 neuron→topology：是否有 motif id 引用已登记 connectome ──
    motif_files = []
    for d in ('neurorobotics', 'api'):
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for fn in sorted(os.listdir(base)):
            if fn.endswith('.json') and 'motif' in fn.lower():
                motif_files.append(os.path.join(base, fn))
    l1_hits = set()
    for p in motif_files:
        try:
            l1_hits |= _referenced_ids(_load(p), conn_ids)
        except Exception:
            pass
    l1_ok = bool(l1_hits)

    # ── L2 topology→body：signal_contract 的执行器是否落在真实**物理零件**上 ──
    l2_hits = set()
    for c in contracts:
        l2_hits |= _referenced_ids(c.get('body') or {}, body_ids, re.compile(r'^[A-Z]+-'),
                                   skip_keys=('id',))
    l2_ok = bool(l2_hits)
    l2_blocked = None
    if not l2_ok and contracts:
        kinds = sorted({(c.get('body') or {}).get('kind') for c in contracts})
        acts = sorted({a.get('id') for c in contracts
                       for a in ((c.get('body') or {}).get('actuators') or [])
                       if a.get('id')})
        l2_blocked = ('%d 条 signal_contract 的 body.kind=%s，执行器 id=%s 均为虚拟/抽象名，'
                      '不指向 entities.json 中任何真实实体'
                      % (len(contracts), kinds, acts[:5]))

    # ── L3 body→policy：模型条目是否引用真实**物理零件** id ──
    # skip_keys=('id',) 见 _referenced_ids 的注释：不加会因"条目 id 恰是实体 id"
    # 而把自引用误判成跨层引用（首版实测假阳性）。
    l3_hits = set()
    for m in models:
        l3_hits |= _referenced_ids(m, body_ids, re.compile(r'^[A-Z]{2,6}-'), skip_keys=('id',))
    l3_ok = bool(l3_hits)

    # ── L4 policy→behavior：是否存在运行日志 ──
    behavior_files = []
    for pat in ('behavior', 'run_log', 'rollout'):
        for d in ('api', 'neurorobotics'):
            base = os.path.join(ROOT, d)
            if os.path.isdir(base):
                for fn in os.listdir(base):
                    if pat in fn.lower():
                        behavior_files.append(os.path.join(d, fn))
    l4_ok = bool(behavior_files)

    links = [
        {'from': 'neuron', 'to': 'topology',
         'requires': ['topology.motif_id 引用已登记 connectome_ref（∈ neurorobotics.connectomes[].id）'],
         'satisfied': l1_ok,
         'blocked_by': None if l1_ok else
         ('本仓无任何 motif 数据文件（扫描 neurorobotics/ 与 api/ 的 *motif*）：'
          '本仓刻意不复制 flybrain 侧拓扑'),
         'note': '若本仓选择 ingest motif，此项自动转 true（它是现算的）。'},
        {'from': 'topology', 'to': 'body',
         'requires': ['signal_contract.body.actuators[].id ∈ entities.json[].id'],
         'satisfied': l2_ok,
         'blocked_by': l2_blocked or '无 signal_contract 可判',
         'note': '这是 GAP-G2 的机器可读判据：契约必须落到真实零件，否则只是示例。'},
        {'from': 'body', 'to': 'policy',
         'requires': ['robot_ai_models 条目引用 entities.json[].id'],
         'satisfied': l3_ok,
         'blocked_by': None if l3_ok else
         '%d 个模型条目中无一引用真实实体 id（只有 category 级 applications）' % len(models),
         'note': '模型要能"开哪副身体"才谈得上链。'},
        {'from': 'policy', 'to': 'behavior',
         'requires': ['存在行为/运行日志数据'],
         'satisfied': l4_ok,
         'blocked_by': None if l4_ok else '本仓无任何运行日志文件',
         'note': None},
    ]

    # ── 真实链（从真实 signal_contract 派生，不臆造） ──
    chains = []
    for c in contracts:
        body = c.get('body') or {}
        ctrl = c.get('controller') or {}
        # 该契约走到哪一层？虚拟/仿真躯体到不了本仓 body 层
        reaches_body = bool(_referenced_ids(body, body_ids, re.compile(r'^[A-Z]+-'),
                                            skip_keys=('id',)))
        dangling = None if reaches_body else 'body'
        chains.append({
            'id': 'PROVC-' + str(c.get('id', 'UNKNOWN')).replace('SIGC-', ''),
            'title': '%s 的跨层链' % c.get('title', c.get('id')),
            'status': 'complete' if reaches_body else 'dangling',
            'layers': [
                {'id': 'neuron', 'owner': 'external(flybrain-connectome)',
                 'available': 'external_not_ingested',
                 'count': 1 if ctrl.get('connectome_ref') in conn_ids else 0,
                 'ref': '/api/neurorobotics.json#connectomes',
                 'prov': {'source': ctrl.get('connectome_ref') or '未指向已登记连接组',
                          'tier': 'B', 'prov_o_class': 'entity', 'activity': None,
                          'agent': None, 'note': '引用自 signal_contract.controller.connectome_ref'}},
                {'id': 'topology', 'owner': 'external(flybrain-connectome)',
                 'available': 'declared_empty', 'count': 0, 'ref': None,
                 'prov': {'source': '无 motif 数据', 'tier': None, 'prov_o_class': 'entity',
                          'activity': None, 'agent': None, 'note': '本仓未 ingest'}},
                {'id': 'body', 'owner': 'roboparts',
                 'available': 'partial' if reaches_body else 'declared_empty',
                 'count': len(l2_hits), 'ref': '/api/morphology_graph.json' if reaches_body else None,
                 'prov': {'source': 'signal_contract.body（kind=%s）' % body.get('kind'),
                          'tier': 'B', 'prov_o_class': 'entity', 'activity': None, 'agent': None,
                          'note': ('执行器已落到真实实体' if reaches_body else
                                   '执行器为虚拟/抽象名（%s），未落到任何真实实体'
                                   % sorted({a.get('id') for a in (body.get('actuators') or [])
                                             if a.get('id')})[:4])}},
                {'id': 'policy', 'owner': 'roboparts', 'available': 'declared_empty',
                 'count': 0, 'ref': None,
                 'prov': {'source': '本链未涉及策略层', 'tier': None, 'prov_o_class': 'entity',
                          'activity': None, 'agent': None, 'note': None}},
                {'id': 'behavior', 'owner': 'roboparts', 'available': 'declared_empty',
                 'count': 0, 'ref': None,
                 'prov': {'source': '本链未涉及行为层', 'tier': None, 'prov_o_class': 'entity',
                          'activity': None, 'agent': None, 'note': None}},
            ],
            'links': [dict(l) for l in links],
            'dangling_at': dangling,
        })

    complete = sum(1 for c in chains if c['status'] == 'complete')

    out = {
        'meta': {
            'schema': 'embodiment_provenance/v1',
            'title': 'RoboParts 具身跨层溯源清单（Embodied Provenance）',
            'contract': 'schemas/embodiment_provenance.schema.json',
            'anchor': 'docs/PROJECT_DIRECTIONS_V2.md §1（方向锚点 v2.1 · D6）',
            'generated_by': 'scripts/build_provenance.py',
            'generated_at': (datetime.now(TZ).strftime('%Y-%m-%dT%H:%M:%S+08:00')
                             if with_timestamp else None),
            'prov_o_alignment': {
                'entity': '每一层的产物（连接组 / motif / 实体 / 模型 / 日志）',
                'activity': '产生该层的活动（EM 重建 / 采集 / 训练 / 运行）',
                'agent': '负责主体（实验室 / 厂商 / roboparts.cc）',
                'note': '本仓的 prov 块（source/tier/retrieved/activity/agent）是 PROV-O 的扁平化子集，'
                        '与 api/morphology_graph.json 的 prov 块同形，可跨文件拼接。',
            },
            'layer_order': LAYER_ORDER,
            'chain_status_enum': {
                'complete': '五层齐备且四条连接条件全满足',
                'partial': '部分层有数据但链不闭合',
                'dangling': '链在 dangling_at 指定的层断掉',
                'spec-example': '对公开演示的结构化重述，非实测闭环',
            },
            'honest_limits': [
                '**当前完整链数 = %d**。四条连接条件（L1–L4）全部不满足，'
                '故本仓目前**没有任何一条**「神经元→行为」的端到端可追溯链。' % complete,
                '唯一存在的 signal_contract 是 spec-example（虚拟游戏躯体），'
                '它**不触及本仓的躯体层** —— 这正是 GAP-G2 的机器可读证据。',
                'neuron 层与 topology 层归外部项目（flybrain-connectome）持有，'
                '本仓只登记引用、**不复制数据**（项目独立原则）。',
                '四条连接条件均为**现算**：任何一条数据到位，本产物会自动转 true。'
                '因此它不是静态描述，是活的 gap tracker。',
                '本产物不声称任何未满足的条件"即将满足"；未满足即如实报 false。',
            ],
        },
        'layer_inventory': {l['id']: {'title_zh': l['title_zh'], 'owner': l['owner'],
                                      'available': l['available'], 'count': l['count'],
                                      'ref': l['ref']} for l in layers},
        'links': links,
        'chains': chains,
        'chain_summary': {
            'total': len(chains),
            'complete': complete,
            'dangling': sum(1 for c in chains if c['status'] == 'dangling'),
            'links_satisfied': sum(1 for l in links if l['satisfied']),
            'links_total': len(links),
            'first_dangling_at': next((c['dangling_at'] for c in chains
                                       if c['status'] != 'complete'), None),
        },
    }
    return out


def main():
    dry = '--dry-run' in sys.argv
    out = build()
    if dry:
        print(json.dumps({'layer_inventory': out['layer_inventory'],
                          'chain_summary': out['chain_summary']},
                         ensure_ascii=False, indent=2))
        print('  (dry-run，未写文件)')
        return
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write('\n')
    s = out['chain_summary']
    print('  ✅ 已生成 api/provenance.json')
    print('     层：%s' % ' · '.join('%s=%s(%d)' % (k, v['available'], v['count'])
                                    for k, v in out['layer_inventory'].items()))
    print('     链 %d 条（完整 %d / 断裂 %d）· 连接条件满足 %d/%d · 首个断点 %s'
          % (s['total'], s['complete'], s['dangling'], s['links_satisfied'],
             s['links_total'], s['first_dangling_at']))


if __name__ == '__main__':
    main()
