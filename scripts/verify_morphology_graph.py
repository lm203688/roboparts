#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_morphology_graph.py —— 形态图闸门（审计 + 阴阳自证）

为什么需要这个闸门
------------------
形态图是本仓新加的「形式对象层」，它的失效模式**不是崩溃而是静默说谎**：

  · 一个永远返回 `unknown` 的引擎，与一个被写坏成"什么都判 unknown"的引擎，
    产物长得**一模一样** —— 只比 api/morphology_graph.json 必然假绿。
  · 反过来，把 `unknown` 误判成 `identity`（"未声明"当"兼容"）会让下游协同设计
    把不存在的组合当成合法解 —— 这是最危险的失真，且**不会报错**。

故本闸门必须三管齐下：
  ① **不变量**（审计）：缺口枢纽入度 == facts() 的 not_declared；类型 id 唯一；
     无悬挂端口；每个轴的类型对完整；**unknown 类型参与的对永不产出身份/转接裁决**。
  ② **阴阳对照**（自证）：构造真实形态的合成输入，证明确实会算（阳性），
     抽掉证据确实会 fail-closed（阴性）。
  ③ **变异对照**：把产物人为改坏，证明判据会红 —— 否则判据自己可能是装饰。

用法
----
    python scripts/verify_morphology_graph.py             # 审计（含与已提交产物比内容）
    python scripts/verify_morphology_graph.py --self-test # 阴阳 + 变异自证
    python scripts/verify_morphology_graph.py --quiet     # 只输出结论行
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from build_morphology_graph import (  # noqa: E402
    build, mech_ports_of, elec_ports_of, build_type_compat,
    build_mechanical_port_types, build_electrical_port_types,
    build_signal_port_types, _load, OUT, SIG_ROLE_BY_CATEGORY,
    MI_PATH, NC_PATH, EL_PATH, SIG_PATH,
)

VERDICTS = {'identity', 'adapter_required', 'incompatible', 'unknown'}
STATUSES = {'declared', 'partial', 'not_declared'}
# 这几个 class 表示「没有可比几何」，它们参与的任何裁决都必须是 unknown
NO_GEOMETRY_CLASSES = {'unknown', 'unparseable_bare', 'proprietary'}


# --------------------------------------------------------------- 不变量（纯函数）

def check_doc(doc, expect_not_declared=None):
    """对一份形态图文档做不变量检查，返回问题列表（空 = 通过）。

    刻意是**纯函数**：既能审真实产物，也能在自证里审人为改坏的产物。
    """
    P = []
    types = doc.get('port_types') or []
    nodes = doc.get('nodes') or []
    compat = doc.get('type_compat') or []

    # 1) 类型 id 唯一
    ids = [t['id'] for t in types]
    if len(ids) != len(set(ids)):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        P.append('端口类型 id 重复: %s' % dup[:5])
    tmap = {t['id']: t for t in types}

    # 2) 无悬挂端口引用
    dangling = sorted({p['type'] for n in nodes for p in n.get('ports') or []
                       if p['type'] not in tmap})
    if dangling:
        P.append('%d 个端口指向未声明的类型: %s' % (len(dangling), dangling[:5]))

    # 3) 端口 status 合法
    bad_st = sorted({p['status'] for n in nodes for p in n.get('ports') or []
                     if p['status'] not in STATUSES})
    if bad_st:
        P.append('端口 status 非法: %s' % bad_st)

    # 4) 裁决取值合法
    bad_v = sorted({c['verdict'] for c in compat if c['verdict'] not in VERDICTS})
    if bad_v:
        P.append('裁决取值非法: %s' % bad_v)

    # 5) 类型对完整性：每个轴内所有无序对（含自配对）都要有裁决
    for ax in ('mechanical', 'electrical', 'signal'):
        ax_ids = sorted(i for i in tmap if tmap[i]['axis'] == ax)
        want = len(ax_ids) * (len(ax_ids) + 1) // 2
        got = {(c['a'], c['b']) for c in compat if c.get('axis') == ax}
        if len(got) != want:
            P.append('%s 轴类型对不完整: 期望 %d 实得 %d' % (ax, want, len(got)))

    # 6) **fail-closed 核心**：无几何类型参与的对，裁决必须是 unknown
    for c in compat:
        ta, tb = tmap.get(c['a']), tmap.get(c['b'])
        if not ta or not tb:
            continue
        if (ta['class'] in NO_GEOMETRY_CLASSES or tb['class'] in NO_GEOMETRY_CLASSES):
            if c['verdict'] != 'unknown':
                P.append('无几何类型对判成了 %s（应为 unknown，fail-closed 被破坏）: %s × %s'
                         % (c['verdict'], c['a'], c['b']))
                break

    # 7) declared 状态的机械端口必须指向有几何的类型
    for n in nodes:
        for p in n.get('ports') or []:
            if p['status'] != 'declared':
                continue
            t = tmap.get(p['type'])
            if not t or t['axis'] != 'mechanical' or t['class'] != 'registered_standard':
                continue
            if not (t.get('geometry') or {}).get('pcd_mm'):
                P.append('declared 机械端口指向无几何类型: %s -> %s' % (n['id'], p['type']))
                break

    # 8) 缺口枢纽入度必须等于真相源的 not_declared（防"缺口被静默美化"）
    if expect_not_declared is not None:
        hub = tmap.get('MECH:UNKNOWN', {}).get('consumer_count')
        if hub != expect_not_declared:
            P.append('MECH:UNKNOWN 入度 %s != facts().mech_not_declared %s'
                     % (hub, expect_not_declared))

    # 9) summary 的自报数必须与实体相符（防汇总层撒谎）
    s = doc.get('summary') or {}
    if s.get('nodes_total') != len(nodes):
        P.append('summary.nodes_total %s != 实得 %d' % (s.get('nodes_total'), len(nodes)))
    real_ports = sum(len(n.get('ports') or []) for n in nodes)
    if s.get('ports_total') != real_ports:
        P.append('summary.ports_total %s != 实得 %d' % (s.get('ports_total'), real_ports))
    if s.get('type_compat_pairs') != len(compat):
        P.append('summary.type_compat_pairs %s != 实得 %d'
                 % (s.get('type_compat_pairs'), len(compat)))
    if s.get('port_types_total') != len(types):
        P.append('summary.port_types_total %s != 实得 %d'
                 % (s.get('port_types_total'), len(types)))

    # 10) 信号端口必须是**单一角色**且与品类映射一致。旧实现给每个终端实体
    #     无差别赋全部 3 个角色（output/input/reward），一只执行器同时充当
    #     传感器输入端——语义错误，也让信号轴永远凑不出任何互补配对。
    for n in nodes:
        sig = [p for p in n.get('ports') or [] if p['type'].startswith('SIG')]
        if len(sig) > 1:
            P.append('节点 %s 有 %d 个信号端口（定向赋值后应至多 1 个）'
                     % (n['id'], len(sig)))
            break
        if sig:
            exp = SIG_ROLE_BY_CATEGORY.get(n.get('category'))
            if exp and sig[0]['type'] != exp:
                P.append('节点 %s（品类 %s）信号角色 %s != 映射 %s'
                         % (n['id'], n.get('category'), sig[0]['type'], exp))
                break
            if sig[0].get('status') != 'declared':
                P.append('节点 %s 信号端口 status=%r（品类映射应判 declared）'
                         % (n['id'], sig[0].get('status')))
                break

    # 11) 信号轴裁决规则固定：互补对 identity、同类端 unknown。
    #     旧实现把全部信号对硬编码 unknown，信号轴等于零信号。
    cindex = {(c['a'], c['b']): c for c in compat}

    def _sigv(a, b):
        e = cindex.get((a, b)) or cindex.get((b, a))
        return e['verdict'] if e else None

    if _sigv('SIG:OUTPUT_SPIKE', 'SIG:INPUT_SENSORY') != 'identity':
        P.append('信号互补对 OUTPUT~INPUT 未判 identity（得 %r）'
                 % _sigv('SIG:OUTPUT_SPIKE', 'SIG:INPUT_SENSORY'))
    for same in ('SIG:OUTPUT_SPIKE', 'SIG:INPUT_SENSORY', 'SIG:REWARD'):
        v = _sigv(same, same)
        if v != 'unknown':
            P.append('信号同类端 %s 自配对未判 unknown（得 %r）' % (same, v))
    return P


def strip_ts(doc):
    d = copy.deepcopy(doc)
    m = d.get('meta') or {}
    m.pop('generated_at', None)
    # meta.access 是 inject_api_access.py 的受管区（构建器不产出、注入器负责）。
    # 不剥离会让注入后的合法比对假红 —— 与 verify_provenance 同口径。
    m.pop('access', None)
    return d


# --------------------------------------------------------------- 自证

def _synthetic_types():
    mi = _load(MI_PATH)
    nc = _load(NC_PATH)
    el = _load(EL_PATH)
    sg = _load(SIG_PATH)
    ents = []
    pt = {}
    pt.update(build_mechanical_port_types(mi, nc, ents))
    pt.update(build_electrical_port_types(el))
    pt.update(build_signal_port_types(sg))
    return pt, nc


def self_test():
    ok, fail = [], []

    def chk(name, cond, detail=''):
        (ok if cond else fail).append(name)
        print('  %s %s%s' % ('✅' if cond else '❌', name,
                             ('  — ' + detail) if detail and not cond else ''))

    pt, nc = _synthetic_types()

    def verdict(*ids):
        """按需现算某组类型间的裁决。

        不能在开头算一次就复用：合成实体会**惰性创建专有类型**，先算会把它们漏掉，
        查不到就抛 KeyError（首次运行时真实踩到）。现算保证与生成器同口径。
        """
        m = {frozenset((c['a'], c['b'])): c['verdict']
             for c in build_type_compat(pt, nc)}
        return m[frozenset(ids)]

    # ── 阳性对照：证明引擎真的会算 ──
    e_iso = {'id': 'T-A50', 'mechanical_interface': {'status': 'declared',
             'standard': 'ISO 9409-1-50-4-M6'}}
    ports, _ = mech_ports_of(e_iso, pt)
    chk('阳性① declared ISO 标号 → 解析出登记类型',
        len(ports) == 1 and ports[0]['type'] == 'MECH:ISO9409-1-A50-4-M6',
        repr(ports))

    chk('阳性② 同标号 → identity', verdict('MECH:ISO9409-1-A50-4-M6') == 'identity')
    chk('阳性③ PCD 不同 → adapter_required（真的在算几何）',
        verdict('MECH:ISO9409-1-A50-4-M6', 'MECH:ISO9409-1-A40-4-M6') == 'adapter_required')

    # 多值标号 → 多端口（Array.isArray 口径）
    e_multi = {'id': 'T-MULTI', 'mechanical_interface': {'status': 'declared',
               'standard': ['ISO 9409-1-50-4-M6', 'ISO 9409-1-40-4-M6']}}
    p2, _ = mech_ports_of(e_multi, pt)
    chk('阳性④ 多值标号 → 多个端口（不吞掉第二个）', len(p2) == 2, repr(p2))

    # ── 阴性对照：抽掉证据必须 fail-closed ──
    e_nd = {'id': 'T-ND', 'mechanical_interface': {'status': 'not_declared'}}
    p3, _ = mech_ports_of(e_nd, pt)
    chk('阴性① not_declared → 挂到 MECH:UNKNOWN（不是丢弃、不是假定兼容）',
        len(p3) == 1 and p3[0]['type'] == 'MECH:UNKNOWN', repr(p3))
    chk('阴性② unknown × 已登记标号 → unknown（**不得**回退成 identity/adapter_required）',
        verdict('MECH:UNKNOWN', 'MECH:ISO9409-1-A50-4-M6') == 'unknown')
    chk('阴性③ unknown 自配对 → 仍 unknown（不是空泛的 identity）',
        verdict('MECH:UNKNOWN') == 'unknown')

    # 裸标号不得被猜出 PCD
    e_bare = {'id': 'T-BARE', 'mechanical_interface': {'status': 'partial',
              'standard': 'ISO 9409-1'}}
    p4, _ = mech_ports_of(e_bare, pt)
    chk('阴性④ 裸标号 → ISO9409-1-BARE（不猜几何）',
        len(p4) == 1 and p4[0]['type'] == 'MECH:ISO9409-1-BARE', repr(p4))
    chk('阴性⑤ 裸标号 与 A50 → unknown（不按标号字面猜）',
        verdict('MECH:ISO9409-1-BARE', 'MECH:ISO9409-1-A50-4-M6') == 'unknown')

    # 专有接口不得据命名推 incompatible
    e_prop = {'id': 'T-PROP', 'manufacturer': 'Acme', 'mechanical_interface':
              {'status': 'partial', 'declared_note': '专有安装体系，非标准法兰'}}
    p5, _ = mech_ports_of(e_prop, pt)
    chk('阴性⑥ 有散文证据的 partial → 专有类型（证据驱动归类）',
        len(p5) == 1 and p5[0]['type'].startswith('MECH:PROPRIETARY:'), repr(p5))
    chk('阴性⑦ 专有 × ISO → unknown（不据"专有"推 incompatible）',
        verdict(p5[0]['type'], 'MECH:ISO9409-1-A50-4-M6') == 'unknown')

    # partial 但连散文都没有 → UNKNOWN（不是硬塞专有）
    e_pn = {'id': 'T-PN', 'manufacturer': 'Acme', 'mechanical_interface':
            {'status': 'partial'}}
    p6, _ = mech_ports_of(e_pn, pt)
    chk('阴性⑧ partial 无任何证据 → UNKNOWN（诚实留白，不硬塞专有）',
        len(p6) == 1 and p6[0]['type'] == 'MECH:UNKNOWN', repr(p6))

    # ── 变异对照：把产物改坏，判据必须红 ──
    good = build(with_timestamp=False)
    from onboarding_block import facts
    F = facts()
    chk('基线：真实产物通过全部不变量',
        check_doc(good, F['mech_not_declared']) == [],
        repr(check_doc(good, F['mech_not_declared'])[:3]))

    m1 = copy.deepcopy(good)
    for c in m1['type_compat']:
        if c['a'] == 'MECH:UNKNOWN':
            c['verdict'] = 'identity'
            break
    chk('变异① unknown 对改成 identity → 判红（fail-closed 判据有效）',
        any('fail-closed' in p for p in check_doc(m1)))

    m2 = copy.deepcopy(good)
    for t in m2['port_types']:
        if t['id'] == 'MECH:UNKNOWN':
            t['consumer_count'] = 0
            break
    chk('变异② 把缺口枢纽入度抹成 0 → 判红（缺口美化会被抓）',
        any('MECH:UNKNOWN 入度' in p for p in check_doc(m2, F['mech_not_declared'])))

    m3 = copy.deepcopy(good)
    m3['summary']['ports_total'] = 0
    chk('变异③ 汇总层谎报端口数 → 判红',
        any('ports_total' in p for p in check_doc(m3)))

    m4 = copy.deepcopy(good)
    m4['nodes'][0]['ports'] = [{'type': 'MECH:NOT-A-REAL-TYPE', 'status': 'declared'}]
    chk('变异④ 悬挂端口引用 → 判红',
        any('未声明的类型' in p for p in check_doc(m4)))

    m5 = copy.deepcopy(good)
    m5['type_compat'] = [c for c in m5['type_compat'] if c.get('axis') != 'signal']
    chk('变异⑤ 抽掉整条信号轴的裁决 → 判红（类型对完整性）',
        any('signal 轴类型对不完整' in p for p in check_doc(m5)))

    # ── 回归守卫：两个真实踩过的 bug ──
    e_jst = {'id': 'T-JST', 'connector': 'JST EHR-03（TTL 3-pin；PCB header B3B-EH-A）'}
    pe, _ = elec_ports_of(e_jst, pt)
    chk('守卫① 连接器匹配抹标点（JST EHR-03 的括号不得致匹配失败）',
        pe and pe[0]['type'] == 'ELEC:CONNECTOR:JST-EHR-03', repr(pe))

    e_cn = {'id': 'T-CN', 'manufacturer': '宇立仪器', 'mechanical_interface':
            {'status': 'partial', 'declared_note': '厂商标注'}}
    e_cn2 = {'id': 'T-CN2', 'manufacturer': '欧姆龙', 'mechanical_interface':
             {'status': 'partial', 'declared_note': '厂商标注'}}
    pt2 = copy.deepcopy(pt)
    a, _ = mech_ports_of(e_cn, pt2)
    b, _ = mech_ports_of(e_cn2, pt2)
    chk('守卫② 两个中文厂商名不得塌成同一个空 id',
        a[0]['type'] != b[0]['type'] and a[0]['type'] != 'MECH:PROPRIETARY:',
        '%s vs %s' % (a[0]['type'], b[0]['type']))

    e_multi_conn = {'id': 'T-MC', 'connector': 'XT30PW-M（电源/CAN）+ A1257WR-S-3P（UART）'}
    pm, _ = elec_ports_of(e_multi_conn, pt)
    chk('守卫③ 双连接器实体 → 两个端口（不静默丢第二个）', len(pm) == 2, repr(pm))

    print()
    print('  自证结果：通过 %d / 失败 %d' % (len(ok), len(fail)))
    if fail:
        print('  失败项：')
        for f in fail:
            print('    - ' + f)
    return 1 if fail else 0


# --------------------------------------------------------------- 审计

def audit(quiet=False):
    problems = []
    if not os.path.exists(OUT):
        print('❌ api/morphology_graph.json 不存在（先跑 scripts/build_morphology_graph.py）')
        return 1
    committed = _load(OUT)
    fresh = build(with_timestamp=False)

    from onboarding_block import facts
    F = facts()

    problems += check_doc(committed, F['mech_not_declared'])

    # 与新鲜构建比内容（忽略生成的时刻戳）
    if strip_ts(committed) != strip_ts(fresh):
        # 定位第一处差异，避免只报"不一致"让人无从下手
        c, f = strip_ts(committed), strip_ts(fresh)
        where = []
        for k in ('port_types', 'nodes', 'edges', 'type_compat', 'summary', 'meta'):
            if c.get(k) != f.get(k):
                where.append(k)
        problems.append('已提交产物与现算不一致（漂移）: %s' % where)

    if problems:
        print('❌ 形态图闸门未通过（%d 项）' % len(problems))
        for p in problems:
            print('   - ' + p)
        return 1
    s = committed['summary']
    if not quiet:
        print('  ✅ 形态图不变量全部通过')
        print('     节点 %d · 端口 %d · 端口类型 %d（在用 %d）· 类型对 %d'
              % (s['nodes_total'], s['ports_total'], s['port_types_total'],
                 sum(1 for t in committed['port_types'] if t['in_use']),
                 s['type_compat_pairs']))
        print('     缺口枢纽 %s' % s['gap_hubs'])
        print('     与现算产物逐键一致（忽略 generated_at）')
    print('✅ 形态图通过')
    return 0


def main():
    if '--self-test' in sys.argv:
        return self_test()
    return audit(quiet='--quiet' in sys.argv)


if __name__ == '__main__':
    sys.exit(main())
