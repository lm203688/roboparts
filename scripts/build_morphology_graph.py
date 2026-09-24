#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_morphology_graph.py —— 形态图生成器（D4 协同设计底座 / D5 组合演算的输入形式）

单一真相源（只读，不改）：
    api/entities.json               实体（节点）
    api/mechanical_interfaces.json  机械端口类型的规范行（登记标号 + 判定语法）
    api/negative_compat.json        机械端口类型之间的权威裁决（81 条，纯几何现算）
    api/electrical_interfaces.json  电气端口类型（连接器/总线变体）
    neurorobotics/signal_interface.schema.json  信号端口类型（output/input/reward 三层）
    scripts/onboarding_block.py     机械声明率的唯一真相源 facts()
产出：
    api/morphology_graph.json       由本脚本生成，禁止手改

为什么需要「端口类型」这一层（本图的核心设计）
----------------------------------------------
直接建「实体 × 实体」的兼容边会得到 593² ≈ 35 万条边，且每一条都要重复判定。
ISO 9409-1 的语义本身就是**类型系统**：*法兰标号就是类型*，两件能装当且仅当
标号一致（或经转接盘）。故本图建成**二部结构**：

    实体 (node) ──has_port──> 端口类型 (port_type) ──type_compat──> 端口类型

于是「判定」只需在 9 个端口类型之间做（复用 negative_compat 的 81 条现算裁决），
实体侧只剩「持有哪个端口、声明到什么程度」。这正是 D5 组合演算要的类型层雏形。

三态诚实建模（本图的纪律核心）
--------------------------------
`not_declared` 的 414 个实体**不被丢弃、也不被假定兼容**，而是挂到 `MECH:UNKNOWN`
这个显式端口类型上。后果是**图结构自己把缺口画出来**：UNKNOWN 成为入度最高的
端口类型节点。下游协同设计优化器必须显式处理 unknown，不可能"没看见"而误判兼容。

fail-closed：unknown 端口类型的任何组合裁决恒为 `unknown`，**永不回退到按标号字面猜测**
（negative_compat.meta.coverage_note 的既有纪律）。

用法：
    python scripts/build_morphology_graph.py            # 生成
    python scripts/build_morphology_graph.py --dry-run  # 只打印摘要，不写文件
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

ENT_PATH = os.path.join(ROOT, 'api', 'entities.json')
MI_PATH = os.path.join(ROOT, 'api', 'mechanical_interfaces.json')
NC_PATH = os.path.join(ROOT, 'api', 'negative_compat.json')
EL_PATH = os.path.join(ROOT, 'api', 'electrical_interfaces.json')
SIG_PATH = os.path.join(ROOT, 'neurorobotics', 'signal_interface.schema.json')
OUT = os.path.join(ROOT, 'api', 'morphology_graph.json')

TZ = timezone(timedelta(hours=8))

# 与 mechanical_interfaces.designations_in_use.join_rule 同口径（同一归一化只许一处语义）
_JOIN = lambda s: re.sub(r'ISO9409-1-A', 'ISO9409-1-', str(s).upper().replace(' ', ''))
_ISO_RE = re.compile(r'^ISO9409-1-(\d+(?:\.\d+)?)-(\d+)-M(\d+)$')
_ISO_BARE_RE = re.compile(r'^ISO9409-1$')

# 信号契约的三个语义层——直接对应 signal_interface.schema.json 的
# mappings.output / mappings.input / mappings.reward，不是自创分类。
SIG_LAYERS = [
    ('SIG:OUTPUT_SPIKE', '控制器输出群体 → 躯体执行器', 'mappings.output'),
    ('SIG:INPUT_SENSORY', '躯体传感器 → 控制器输入群体', 'mappings.input'),
    ('SIG:REWARD', '事件 → 奖励群体', 'mappings.reward'),
]

# 可能成为信号契约端点的品类（这些实体**本该**有信号声明，实测 0 条）。
SIGNAL_ENDPOINT_CATEGORIES = {
    'actuators', 'flexible_actuators', 'grippers', 'sensors',
    'controllers', 'integrated_joints', 'bionic_mechanisms', 'reducers',
}

# **应当**有电气接口的品类。这些实体若未声明 connector，挂 ELEC:UNKNOWN（status=not_declared），
# 与机械轴的 MECH:UNKNOWN 对称——让电气缺口也在图结构里显形，而不是表现为"没有端口"。
# 刻意不含 reducers / structural：纯机械件，不预期有电气接口
# （给它们挂电气端口是无根据的断言，不是诚实留白）。
ELEC_EXPECTED_CATEGORIES = {
    'chips', 'data_acquisition', 'sensors', 'actuators', 'flexible_actuators',
    'controllers', 'power', 'pcb', 'cables', 'connectors', 'integrated_joints',
    'grippers', 'bionic_mechanisms',
}

# 非物理实体：不进形态图（没有端口），但要计数，不许静默消失
NON_PHYSICAL_KINDS = {'software', 'market_intelligence', 'organization', 'specification'}


def _load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')


def _vendor_slug(primary):
    """厂商主名 → 稳定 id 段。

    `_slug` 会抹掉全部非 ASCII，中文厂商名（如「宇立仪器」）由此**塌成空串**，
    不同中文厂商会拿到同一个 id `MECH:PROPRIETARY:` —— 一个静默的类型合并。
    故 ASCII 段为空时改用主名的 sha1 前 8 位（确定性、无碰撞风险）；
    可读的原文留在 token 与 prov 里。
    """
    s = _slug(primary)
    if s:
        return s.upper()
    import hashlib
    return 'V' + hashlib.sha1(primary.encode('utf-8')).hexdigest()[:8].upper()


# 端口类型 id 前缀 → 轴名。刻意与 id 前缀解耦：前缀是机器标识，轴名是对外语义，
# 早期直接把前缀 lower() 当轴名用过，'MECH'→'mech' 与轴名 'mechanical' 不匹配而崩（已修）。
_PREFIX_AXIS = {'MECH': 'mechanical', 'ELEC': 'electrical', 'SIG': 'signal'}


def axis_of(type_id):
    return _PREFIX_AXIS[type_id.split(':')[0]]


_PROPRIETARY_NOTE = (
    '已知非 ISO 9409-1 体系，但**无几何数据**，故与他型的裁决一律 unknown；'
    '不得据"专有"直接推 incompatible（转接盘是否存在需要几何证据，不是命名学结论）。'
)


def _ensure_proprietary(port_types, vendor, basis):
    """按厂商现算专有端口类型（惰性、幂等）。单一构造点，避免两处写法漂移。

    id 只用厂商**主名**（截到第一个括号/斜杠/逗号），全串留在 token 与 prov.note：
    曾直接用全串 slug，产出过 `...VITTORIO-LUMARE-YEAH-ROBOTICS-PUBLIC-INVENTION`
    这种读不出主次的 id（实体 manufacturer 字段本身含 "A (B) / C" 三写法）。
    """
    full = str(vendor)
    primary = re.split(r'[（(/、,，]', full)[0].strip() or full
    tid = 'MECH:PROPRIETARY:' + _vendor_slug(primary)
    if tid not in port_types:
        port_types[tid] = {
            'id': tid, 'axis': 'mechanical', 'class': 'proprietary',
            'token': primary, 'geometry': None, 'consumers': [],
            'prov': _prov('构造类型：厂商自研安装体系（依据：%s）' % basis,
                          None, None, _PROPRIETARY_NOTE),
        }
        if primary != full:
            port_types[tid]['prov']['vendor_full'] = full
    return tid


def _prov(source, tier=None, retrieved=None, note=None):
    """PROV-O 风格的最小溯源块（跨层溯源 schema 的前身，见 schemas/embodiment_provenance.schema.json）。"""
    p = {'source': source}
    if tier:
        p['tier'] = tier
    if retrieved:
        p['retrieved'] = retrieved
    if note:
        p['note'] = note
    return p


# --------------------------------------------------------------- 端口类型层

def build_mechanical_port_types(mi_doc, nc_doc, ents):
    """机械端口类型 = 登记标号 + 裸标号 + 专有接口 + UNKNOWN 四类。"""
    types = {}
    for d in mi_doc.get('flange_designations') or []:
        tid = 'MECH:' + d['id']
        types[tid] = {
            'id': tid,
            'axis': 'mechanical',
            'class': 'registered_standard',
            'token': d['id'],
            'geometry': {
                'pcd_mm': d.get('d1_mm'),
                'bolt_count': d.get('bolt_count'),
                'thread': d.get('thread'),
            },
            'is_canonical_iso': bool(d.get('is_canonical_iso')),
            'consumers': [],
            'prov': _prov(
                d.get('source') or 'api/mechanical_interfaces.json#flange_designations',
                d.get('source_tier'), None, d.get('note')),
        }
    # UNKNOWN 端口类型：不是"缺失"，是**显式类型**。缺口在这里可视化。
    types['MECH:UNKNOWN'] = {
        'id': 'MECH:UNKNOWN',
        'axis': 'mechanical',
        'class': 'unknown',
        'token': None,
        'geometry': None,
        'consumers': [],
        'prov': _prov('构造类型：机械接口未声明到可判定粒度',
                      None, None,
                      '本类型的存在本身即是结论——它承载「公开可判定粒度上的标准登记缺口」。'
                      '任何涉及本类型的组合裁决恒为 unknown（fail-closed）。'),
    }
    types['MECH:ISO9409-1-BARE'] = {
        'id': 'MECH:ISO9409-1-BARE',
        'axis': 'mechanical',
        'class': 'unparseable_bare',
        'token': 'ISO 9409-1',
        'geometry': None,
        'consumers': [],
        'prov': _prov('构造类型：厂商只声明到标准号，未给 d1/孔数/螺纹',
                      None, None,
                      '裸标号不可判定几何，禁止按标号字面猜 PCD。'),
    }

    # 专有接口类型不在此预建：它由 `mech_ports_of` 按实体证据**惰性**创建，
    # 避免预建出一批「零消费者」的孤儿类型（那会让端口类型数与实体对不上）。
    return types


def build_electrical_port_types(el_doc):
    types = {}
    for c in el_doc.get('connectors') or []:
        label = c.get('label') or c.get('name') or c.get('id')
        if not label:
            continue
        tid = 'ELEC:CONNECTOR:' + _slug(label).upper()
        types[tid] = {
            'id': tid,
            'axis': 'electrical',
            'class': 'registered_connector',
            'token': label,
            'pins': c.get('pins'),
            'pitch_mm': c.get('pitch_mm'),
            'consumers': [],
            'prov': _prov('api/electrical_interfaces.json#connectors',
                          c.get('source_tier'), None,
                          c.get('warning') or c.get('source_discrepancy') or c.get('role')),
        }
    types['ELEC:UNKNOWN'] = {
        'id': 'ELEC:UNKNOWN',
        'axis': 'electrical',
        'class': 'unknown',
        'token': None,
        'pins': None,
        'consumers': [],
        'prov': _prov('构造类型：电气接口未声明', None, None,
                      '电气轴覆盖率极低（见 electrical_interfaces.coverage），本类型为显式缺口。'),
    }
    return types


def build_signal_port_types(sig_schema):
    """信号端口类型 = schema 的三个映射层。schema 已定义，实测 0 条完整声明。"""
    props = sig_schema.get('properties', {}).get('mappings', {}).get('properties', {})
    types = {}
    for tid, label, key in SIG_LAYERS:
        types[tid] = {
            'id': tid,
            'axis': 'signal',
            'class': 'declared_by_schema',
            'token': key,
            'schema_defined': key in props,
            'consumers': [],
            'prov': _prov('neurorobotics/signal_interface.schema.json#properties.mappings.'
                          + key, 'B', None,
                          'schema 已定义该层；当前库内 0 条完整信号契约，故端点全为 not_declared。'),
        }
    return types


# --------------------------------------------------------------- 实体 → 端口

def mech_ports_of(e, port_types):
    """返回 (ports, evidence)。ports = [{'type':tid,'status':...}]"""
    mi = e.get('mechanical_interface')
    if not isinstance(mi, dict):
        return [], None
    st = mi.get('status')
    if st == 'n_a':
        return [], None
    if st == 'not_declared':
        return [{'type': 'MECH:UNKNOWN', 'status': 'not_declared'}], mi
    # declared / partial：找 token。
    # **只在 `standard` 上取端口**，`flange`/`tool_side`/`tool_side_flange` 只在
    # `standard` 完全没有可解析内容时兜底 —— 它们是同一接口的补充细节，不是第二个接口。
    # 反例（真实踩过）：BIONIC-HAND-002 的 standard="ISO 9409-1"（裸标号）、
    # flange="50mm"；把两者都当 token 会凭空造出一个 PROPRIETARY 端口，
    # 与 mechanical_interfaces.designations_in_use 的口径（该实体只计 1 个裸标号）打架。
    toks = []
    std = mi.get('standard')
    if isinstance(std, list):
        toks = [x for x in std if x]
    elif std:
        toks = [std]
    if not toks:
        for k in ('flange', 'tool_side', 'tool_side_flange'):
            v = mi.get(k)
            if isinstance(v, list):
                toks += [x for x in v if x]
            elif v:
                toks.append(v)
    out = []
    for t in toks:
        n = _JOIN(t)
        m = _ISO_RE.match(n)
        if m:
            tid = 'MECH:ISO9409-1-A%s-%s-M%s' % (m.group(1), m.group(2), m.group(3))
            if tid not in port_types:
                # 语义化：标号可解析但未登记 → 单列，不许静默归到 UNKNOWN
                tid = 'MECH:UNREGISTERED:' + n
                port_types[tid] = {
                    'id': tid, 'axis': 'mechanical', 'class': 'unregistered_standard',
                    'token': t, 'geometry': {
                        'pcd_mm': float(m.group(1)), 'bolt_count': int(m.group(2)),
                        'thread': 'M' + m.group(3)},
                    'consumers': [], 'prov': _prov(
                        '由实体 mechanical_interface 现算（未命中 flange_designations 规范行）',
                        None, None,
                        '在用但未登记。按 L1.77 纪律不替标准发明规范行；缺口显式列出。'),
                }
        elif _ISO_BARE_RE.match(n) or n.startswith('ISO9409-1'):
            tid = 'MECH:ISO9409-1-BARE'
        else:
            v = str(e.get('manufacturer') or e.get('developer') or 'unknown').strip() or 'unknown'
            tid = _ensure_proprietary(port_types, v, '非 ISO 标号的 standard/flange 取值')
        out.append({'type': tid, 'status': st})
    if not out:
        # declared/partial 但一个 token 都没取到。归类按**证据**而非状态字面：
        #   · 有 declared_note（厂商散文描述了安装体系）→ 专有类型，证据指向厂商自研
        #   · 连散文都没有 → UNKNOWN（partial 但无所指，诚实留白）
        # 曾把 9 个专有实体一律归 UNKNOWN，使 UNKNOWN 入度虚高到 423（真值 414）——
        # 「缺口结构自己会说话」的前提是分类正确，否则它说的是错话。
        if mi.get('declared_note'):
            v = str(e.get('manufacturer') or e.get('developer') or 'unknown').strip() or 'unknown'
            tid = _ensure_proprietary(port_types, v, 'declared_note 描述了厂商自研安装体系')
            out.append({'type': tid, 'status': st})
        else:
            out.append({'type': 'MECH:UNKNOWN', 'status': st})
    return out, mi


def elec_ports_of(e, port_types):
    """电气端口：仅认 connector 字段（voltage/protocol 单独不足以定位物理端口类型）。

    匹配用**归一化后的去标点**比较：连接器表用 `label`（"JST EHR-03"），实体用
    "JST EHR-03（TTL 3-pin；PCB header B3B-EH-A）"。先前拿表里的 `id`
    （"jst_ehr_03"）去比，标点差异使**全部 32 个实体**匹配失败、集体落到
    ELEC:UNKNOWN —— 一个「电气轴 0 覆盖」的假象，而真值是 5 个连接器类型在用。
    故先抹非字母数字再双向包含；且**匹配全部命中**而非首个 ——
    一个实体可以同时持有两个连接器（ACT-016 就是 "XT30PW-M + A1257WR-S-3P"），
    只取首个会把第二个连接器静默丢掉。
    """
    conn = e.get('connector')
    if not conn:
        # 该品类**预期**有电气接口却未声明 → 显式 ELEC:UNKNOWN（不是"没有端口"）。
        # 只对预期品类这么做：对纯机械件挂电气端口是无根据的断言。
        if e.get('category') in ELEC_EXPECTED_CATEGORIES:
            return [{'type': 'ELEC:UNKNOWN', 'status': 'not_declared'}], None
        return [], None
    cn = re.sub(r'[^A-Z0-9]', '', str(conn).upper())
    hits = []
    for tid in sorted(port_types):
        t = port_types[tid]
        if t['class'] != 'registered_connector':
            continue
        tok = re.sub(r'[^A-Z0-9]', '', str(t['token']).upper())
        if tok and (tok in cn or cn in tok):
            hits.append(tid)
    if not hits:
        hits = ['ELEC:UNKNOWN']
    return [{'type': tid, 'status': 'declared'} for tid in hits], {'connector': conn}


# 品类 → 单一信号端角色。语义直接来自 signal_interface.schema.json 的
# properties.mappings：output[].body_actuator = 「躯体执行器」、
# input[].body_sensor = 「躯体传感器」、reward[].event = 「事件 → 奖励群体」。
# 旧实现的错误是**给每个终端实体无差别赋全部 3 个角色**——一只执行器不可能同时
# 是「躯体传感器输入端」，这让信号轴永远凑不出任何互补配对（signal compatible 恒 0）。
# 现在按 schema 角色定向赋**唯一**角色：
SIG_ROLE_BY_CATEGORY = {
    'actuators':           'SIG:OUTPUT_SPIKE',   # body_actuator 端
    'flexible_actuators':  'SIG:OUTPUT_SPIKE',
    'grippers':            'SIG:OUTPUT_SPIKE',
    'reducers':            'SIG:OUTPUT_SPIKE',
    'bionic_mechanisms':   'SIG:OUTPUT_SPIKE',
    'integrated_joints':   'SIG:OUTPUT_SPIKE',
    'sensors':             'SIG:INPUT_SENSORY',  # body_sensor 端
    # 'controllers' 故意不赋：它是 output/input 群体的**宿主**（脑侧），
    # 不是体侧被连接端。给体侧图强行造一个端口，是为迎合叙事而捏造数据。
}

SIG_PORT_BASIS = ('signal_interface.schema.json#properties.mappings '
                  '角色语义 + 品类映射')
# 诚实边界：这是**品类级推断**（Tier B），不是厂商 datasheet 实测。
# 具体零件的信号引脚/协议需 datasheet 确认；因此声明的是「角色」，
# 不是「该零件确有一个可插的信号接头」。
SIG_PORT_CAVEAT = ('品类级推断（Tier B），非厂商 datasheet 实测；'
                   '声明的是信号**角色**，不代表该零件存在已标定的信号接头')


def sig_ports_of(e):
    role = SIG_ROLE_BY_CATEGORY.get(e.get('category'))
    if not role:
        return []
    return [{'type': role, 'status': 'declared',
             'role_basis': SIG_PORT_BASIS,
             'caveat': SIG_PORT_CAVEAT,
             'prov_override': {'source': SIG_PORT_BASIS, 'tier': 'B',
                               'note': SIG_PORT_CAVEAT}}]


# --------------------------------------------------------------- 类型间裁决

def build_type_compat(port_types, nc_doc):
    """类型间裁决。

    机械：直接复用 negative_compat 的 81 条现算裁决（同族真理源，不另立一份规则）。
    电气：由 pin 数推导 —— 同连接器 identity；pin 数不同 incompatible；其余 unknown。
    信号：schema 已定义但 0 条完整声明 ⇒ 一律 unknown（fail-closed，不臆断）。
    跨界（不同 axis）：incompatible（物理上不是同一种接口，不可互换）。
    """
    pairs = []
    mech_ids = sorted(t for t in port_types if port_types[t]['axis'] == 'mechanical')
    nc_index = {}
    for r in nc_doc.get('rulings') or []:
        a, b = r['pair']
        nc_index[frozenset((a, b))] = r

    def _mech_pair(a, b):
        ta, tb = port_types[a], port_types[b]
        # 任一侧是 unknown/bare/proprietary ⇒ fail-closed
        if ta['class'] in ('unknown', 'unparseable_bare', 'proprietary') or \
           tb['class'] in ('unknown', 'unparseable_bare', 'proprietary'):
            cls = 'GAP' if 'unknown' in (ta['class'], tb['class']) else 'NO_GEOMETRY'
            return ('unknown',
                    '至少一侧属 %s，无可比几何' % (
                        'not_declared（未声明）' if cls == 'GAP' else '专有/裸标号'),
                    [])
        r = nc_index.get(frozenset((ta['id'], tb['id'])))
        if r:
            return (r['verdict'], r.get('reason'), r.get('blocking_dims') or [])
        # 未登记但几何可解析 → 现算同口径（PCD / 孔数任一不同即 adapter_required）
        ga, gb = ta['geometry'] or {}, tb['geometry'] or {}
        if ga and gb:
            if ga.get('pcd_mm') != gb.get('pcd_mm') or ga.get('bolt_count') != gb.get('bolt_count'):
                return ('adapter_required',
                        '节圆直径或孔数不同，必须经转接盘',
                        [k for k in ('pcd_mm', 'bolt_count')
                         if ga.get(k) != gb.get(k)])
            return ('identity', '几何等同（同 PCD 同孔数），螺栓孔位可互换', [])
        return ('unknown', '无裁决记录且几何不全', [])

    for i, a in enumerate(mech_ids):
        for b in mech_ids[i:]:
            ta, tb = port_types[a], port_types[b]
            if a == b:
                if ta['class'] == 'unknown':
                    verdict, reason, blk = 'unknown', 'unknown 与自身仍不可断言（未声明即不可判定）', []
                elif ta['class'] in ('proprietary', 'unparseable_bare'):
                    verdict, reason, blk = 'unknown', '%s 无几何数据，同型亦不可断言' % ta['class'], []
                else:
                    verdict, reason, blk = 'identity', '同一标号，自配对，必然可装', []
            else:
                verdict, reason, blk = _mech_pair(a, b)
            pairs.append({'a': a, 'b': b, 'axis': 'mechanical', 'verdict': verdict,
                          'reason': reason, 'blocking_dims': blk,
                          'prov': _prov('api/negative_compat.json + 标号几何现算', 'B', None, None)})

    # 电气（仅在同 axis 内）
    el_ids = sorted(t for t in port_types if port_types[t]['axis'] == 'electrical')
    for i, a in enumerate(el_ids):
        for b in el_ids[i:]:
            ta, tb = port_types[a], port_types[b]
            if a == b:
                v, rs = ('identity', '同一连接器') if ta['class'] != 'unknown' \
                    else ('unknown', '未知连接器不可断言')
            elif ta['class'] == 'unknown' or tb['class'] == 'unknown':
                v, rs = 'unknown', '至少一侧未声明'
            elif ta.get('pins') and tb.get('pins') and ta['pins'] != tb['pins']:
                v, rs = 'incompatible', '针数不同（%s vs %s），物理上不可直接对接' % (ta['pins'], tb['pins'])
            else:
                v, rs = 'unknown', '连接器不同型但无针数/间距证据，不臆断'
            pairs.append({'a': a, 'b': b, 'axis': 'electrical', 'verdict': v,
                          'reason': rs, 'blocking_dims': ['pins'] if v == 'incompatible' else [],
                          'prov': _prov('api/electrical_interfaces.json 连接器/针数现算',
                                        'B', None, None)})

    # 信号（三型两两）。
    # 旧实现把全部信号对硬编码成 unknown，理由是「0 条完整契约」——但那否定的是
    # **协议级**契约（波特率、时序、编码），不是**角色级**组合语义。schema 的
    # mappings 已经把角色关系说清楚了：output[].body_actuator 与 input[].body_sensor
    # 是一对互补端（执行器输出 ↔ 传感器输入）。角色级配对有契约依据，可以断言；
    # 协议级细节仍 fail-closed，写在 reason 里不注水。
    # reward 是「事件 → 奖励群体」的映射，不是点对点物理接口，不参与组合判定。
    def _sig_pair(a, b):
        if 'REWARD' in a or 'REWARD' in b:
            return ('unknown',
                    'reward 是「事件→奖励群体」映射，非点对点接口，不参与组合判定')
        if a == b:
            # 同类端不判 incompatible：那暗示「物理上冲突」，但真相是
            # 「不构成两元素互补对」——两个执行器之间不是禁止连接，而是
            # 需要一个控制器中介（更高层次的组合结构，超出二元 compose 的域）。
            # 判 unknown 并把原因写清，比硬判 incompatible 更诚实。
            return ('unknown',
                    '同一角色端不构成互补对（output~output / input~input）；'
                    '需控制器中介，超出二元组合的判定域')
        if {a, b} == {'SIG:OUTPUT_SPIKE', 'SIG:INPUT_SENSORY'}:
            return ('identity',
                    '执行器输出端 ↔ 传感器输入端，schema mappings 定义的标准互补连接'
                    '（角色级；协议级细节另需 datasheet 确认）')
        return ('unknown', 'schema 未定义该角色组合的连接语义')

    sg_ids = sorted(t for t in port_types if port_types[t]['axis'] == 'signal')
    for i, a in enumerate(sg_ids):
        for b in sg_ids[i:]:
            v, rs = _sig_pair(a, b)
            pairs.append({'a': a, 'b': b, 'axis': 'signal', 'verdict': v,
                          'reason': rs,
                          'blocking_dims': ['role_polarity'] if v == 'incompatible' else [],
                          'prov': _prov('neurorobotics/signal_interface.schema.json'
                                        '#properties.mappings 角色语义', 'B', None,
                                        None if v == 'unknown' else
                                        '角色级配对；协议级（时序/编码）未标定，'
                                        '需 datasheet 确认')})
    return pairs


# --------------------------------------------------------------- 主流程

def build(paths=None, with_timestamp=True):
    """返回形态图文档。

    抽成函数是为了让闸门（verify_morphology_graph.py）**复用同一份实现**：
    若闸门自己另写一遍构建逻辑，它测的就是两份代码是否一致，而不是产物是否对
    ——本仓已有「定义与实现分家」的病史（见 enrich_provenance.py 的 Tier 注释）。
    """
    paths = paths or {}
    from onboarding_block import facts
    F = facts()

    ents_doc = _load(paths.get('entities', ENT_PATH))
    ents = ents_doc['entities']
    mi_doc = _load(paths.get('mechanical', MI_PATH))
    nc_doc = _load(paths.get('negative', NC_PATH))
    el_doc = _load(paths.get('electrical', EL_PATH))
    sig_schema = _load(paths.get('signal', SIG_PATH))

    port_types = {}
    port_types.update(build_mechanical_port_types(mi_doc, nc_doc, ents))
    port_types.update(build_electrical_port_types(el_doc))
    port_types.update(build_signal_port_types(sig_schema))

    nodes, edges = [], []
    port_status = {'mechanical': {}, 'electrical': {}, 'signal': {}}
    excluded = {}
    for e in sorted(ents, key=lambda x: x['id']):
        kind = e.get('entity_kind') or 'component'
        if kind in NON_PHYSICAL_KINDS:
            excluded[kind] = excluded.get(kind, 0) + 1
            continue
        ports = []
        mp, mi_ev = mech_ports_of(e, port_types)
        ep, el_ev = elec_ports_of(e, port_types)
        sp = sig_ports_of(e)
        ports += mp + ep + sp
        for p in ports:
            ax = axis_of(p['type'])
            port_status[ax][p['status']] = port_status[ax].get(p['status'], 0) + 1
            if p['type'] in port_types:
                port_types[p['type']]['consumers'].append(e['id'])
            edges.append({
                'from': e['id'], 'to': p['type'],
                'type': 'has_%s_port' % ax,
                'status': p['status'],
                # 信号端口的出处是 schema 契约 + 品类映射，不是实体自身的
                # source_tier——用实体的出处会给「声明了信号角色」挂错证据。
                'prov': p.get('prov_override') or
                        _prov('api/entities.json#%s' % e['id'], e.get('source_tier'),
                              e.get('last_verified')),
            })
        prov = _prov(e.get('source') or 'api/entities.json',
                     e.get('source_tier'), e.get('last_verified'))
        node = {
            'id': e['id'],
            'label': e.get('name') or e.get('name_en') or e['id'],
            'kind': kind,
            # entity_kind 原样随行：回归闸门要求派生文件里的实体引用与真相源逐键
            # 一致（entity_kind 漂移检查）；缺戳会被判 593 处漂移。
            'entity_kind': kind,
            'category': e.get('category'),
            'manufacturer': e.get('manufacturer') or e.get('developer'),
            # 零端口的节点在本图中无法参与任何组合。不是删除它（删了就看不见），
            # 而是显式标出 + 给原因，让"这个实体为什么组不进去"可被追问。
            'composable': bool(ports),
            'ports': ports,
            'prov': prov,
        }
        if not ports:
            node['non_composable_reason'] = (
                '无任何端口：既无机械接口记录（或无适用声明的品类外），'
                '也不属预期有电气接口的品类——本图无法据此断言其可组合性')
        # 诚实保留厂商散文证据，但**不把它洗成裁决**：放在 hint 里，标明非机读
        if isinstance(mi_ev, dict) and mi_ev.get('declared_note'):
            node['port_note'] = {
                'text': mi_ev['declared_note'],
                'authoritative': False,
                'note': '厂商声明原文（散文），仅供人读；不是机读裁决，勿据此推判决。',
            }
        nodes.append(node)

    type_compat = build_type_compat(port_types, nc_doc)
    for pt in port_types.values():
        pt['consumer_count'] = len(pt['consumers'])
        # 类型层与使用层是**两个事实**：registry 定义了类型，实体用了其中一部分。
        # 未使用的类型不是脏数据，是"登记了但库里还没有实体引用"，必须显式标出，
        # 否则消费方会把「零消费者的类型」当成活跃类型去用。
        pt['in_use'] = pt['consumer_count'] > 0

    unknown_fan = len(port_types['MECH:UNKNOWN']['consumers'])
    gap_hubs = {t['id']: t['consumer_count'] for t in sorted(port_types.values(),
                                                           key=lambda x: x['id'])
                if t['class'] == 'unknown'}

    verdict_hist = {}
    for p in type_compat:
        k = p['axis'] + '/' + p['verdict']
        verdict_hist[k] = verdict_hist.get(k, 0) + 1

    out = {
        'meta': {
            'schema': 'morphology_graph/v1',
            'title': 'RoboParts 形态图（Morphology Graph）',
            'description':
                '把零件目录变成「可组合的形式对象」：实体为节点、接口为带类型的端口、'
                '端口类型之间带可判定裁决。二部结构（实体→端口类型→端口类型）而非'
                '实体×实体的全对边，因为 ISO 9409-1 的语义本身就是类型系统：'
                '法兰标号即类型，两件能装当且仅当标号一致或经转接盘。',
            'anchor': 'docs/PROJECT_DIRECTIONS_V2.md §1（方向锚点 v2.2）',
            'generated_by': 'scripts/build_morphology_graph.py',
            'generated_at': (datetime.now(TZ).strftime('%Y-%m-%dT%H:%M:%S+08:00')
                             if with_timestamp else None),
            'truth_sources': [
                'api/entities.json', 'api/mechanical_interfaces.json',
                'api/negative_compat.json', 'api/electrical_interfaces.json',
                'neurorobotics/signal_interface.schema.json',
            ],
            'port_axes': {
                'mechanical': '能不能拧上去（ISO 9409-1 法兰标号）',
                'electrical': '能不能接上电（连接器/针数/供电轨）',
                'signal': '接上后能不能正确收发脉冲（输出/感觉/奖励三层）',
            },
            'port_status_enum': {
                'declared': '有可比对线索且厂商声明到可判定粒度',
                'partial': '有线索但不足以判定（如专有安装体系、裸标号）',
                'not_declared': '未声明——**不是"不适用"，是"不知道"**',
            },
            'verdict_enum': {
                'identity': '同型，可直接对接',
                'adapter_required': '需转接件（几何可对齐但需中介）',
                'incompatible': '不可对接（物理上无法咬合）',
                'unknown': '数据不足，不做判定（fail-closed，不臆断）',
            },
            'honest_limits': [
                '端口类型层的机械裁决有权威证据（negative_compat 81 条纯几何现算）；'
                '电气层仅由连接器同一性与针数推导，未复核实机；信号层 0 条实测，全部 unknown。',
                'MECH:UNKNOWN 承载 %d 个实体；电气/信号轴的缺口枢纽见 summary.gap_hubs ——'
                '本图**入度最高的节点是缺口本身**，这正是「公开可判定粒度上的登记缺口」，'
                '图结构把它画了出来，下游无法"没看见"。' % unknown_fan,
                '本图不声称任何 unknown 边是兼容的；下游消费者必须显式处理 unknown。',
                '厂商散文声明（port_note）以 authoritative=false 保留，不得作为裁决依据。',
                '端口类型的 `in_use=false` 表示「已登记但库内暂无实体引用」，'
                '不是脏数据；消费方须自行决定是否用于未来组合。',
                '「5.69%」是公开可判定粒度上的标准登记率，低值由**未区分**的两种成因构成'
                '（厂商未公开规格 / 零件本就自研接口）。不得单独当作 ISO 9409-1 覆盖边界的'
                '实证证据——见 docs/PROJECT_DIRECTIONS_V2.md §6.1。',
            ],
        },
        'summary': {
            'nodes_total': len(nodes),
            'nodes_composable': sum(1 for n in nodes if n['composable']),
            'nodes_non_composable': sum(1 for n in nodes if not n['composable']),
            'nodes_excluded_non_physical': excluded,
            'ports_total': sum(len(n['ports']) for n in nodes),
            'port_status_by_axis': port_status,
            'port_types_total': len(port_types),
            'port_types_by_axis': {
                ax: sum(1 for t in port_types.values() if t['axis'] == ax)
                for ax in ('mechanical', 'electrical', 'signal')
            },
            'edges_entity_to_port': len(edges),
            'type_compat_pairs': len(type_compat),
            'type_compat_histogram': verdict_hist,
            'unknown_hub_fanin': unknown_fan,
            'gap_hubs': gap_hubs,
            'mechanical_accounting': {
                'applicable': F['mech_applicable'],
                'declared': F['mech_full_declared'],
                'partial': F['mech_partial'],
                'not_declared': F['mech_not_declared'],
                'n_a': F['mech_n_a'],
                'registered_rate_pct': F['mech_pct'],
                'truth_source': 'scripts/onboarding_block.py::facts()',
            },
        },
        'port_types': sorted(port_types.values(), key=lambda t: t['id']),
        'nodes': nodes,
        'edges': edges,
        'type_compat': type_compat,
    }
    return out


def main():
    dry = '--dry-run' in sys.argv
    out = build()

    if dry:
        print(json.dumps(out['summary'], ensure_ascii=False, indent=2))
        print('  (dry-run，未写文件)')
        return

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write('\n')

    s = out['summary']
    # 不要硬断言哪个 UNKNOWN 枢纽最大 —— 电气轴缺口（540）已超过机械轴（414），
    # 写死"机械最高"会立刻变成一句假陈述。现算。
    hubs = sorted(((t['consumer_count'], t['id']) for t in out['port_types']
                   if t['class'] == 'unknown'), reverse=True)
    print('  ✅ 已生成 api/morphology_graph.json')
    print('     节点 %d（可组合 %d / 不可组合 %d；另排除非物理 %d）'
          % (s['nodes_total'], s['nodes_composable'], s['nodes_non_composable'],
             sum(s['nodes_excluded_non_physical'].values())))
    print('     端口 %d · 端口类型 %d（在用 %d）· 实体→端口边 %d · 类型对 %d'
          % (s['ports_total'], s['port_types_total'],
             sum(1 for t in out['port_types'] if t['in_use']),
             s['edges_entity_to_port'], s['type_compat_pairs']))
    print('     缺口枢纽（入度）: %s'
          % ' · '.join('%s=%d' % (i, c) for c, i in hubs))
    print('     裁决分布 %s' % s['type_compat_histogram'])


if __name__ == '__main__':
    main()
