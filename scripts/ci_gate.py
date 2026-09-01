#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 闸门：在 GitHub Actions 上可跑的质量校验子集。

为什么不直接跑 scripts/regression.py
------------------------------------
`regression.py`（1000+ 断言）里有大量**留痕纪律**闸门，依赖私有 ops 仓
（`ops/` 在 .gitignore 中，CI checkout 拿不到）与完整 git 历史，
在 CI 环境必然全红。所以 CI 跑的是「不依赖 ops/、纯仓内可判定」的子集。

诚实边界：本闸门**不等于**完整回归。完整回归仍需本地
`python scripts/regression.py`（含留痕/棘轮/日报纪律）。
CI 的作用是：**任何人（含未来的外部 PR）改数据或代码，都不能绕过数据契约与
分发一致性校验** —— 此前这些校验只在 AI 本地手工执行，PR 路径完全无保护。

用法
----
    python scripts/ci_gate.py           # 全部闸门
    python scripts/ci_gate.py --list    # 只列出闸门
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAILED = []
PASSED = []


def ok(name, detail=''):
    PASSED.append(name)
    print(f'  ✅ {name}' + (f' — {detail}' if detail else ''))


def bad(name, detail=''):
    FAILED.append(name)
    print(f'  ❌ {name}' + (f' — {detail}' if detail else ''))


def run_sub(name, cmd, cwd=ROOT, timeout=300):
    """跑外部闸门脚本，非零退出即判红。"""
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
    except FileNotFoundError as ex:
        bad(name, f'命令不可用: {ex}')
        return
    except subprocess.TimeoutExpired:
        bad(name, f'超时 {timeout}s')
        return
    out = ((r.stdout or b'') + (r.returncode and (r.stderr or b'') or b'')
           ).decode('utf-8', 'replace').strip()
    last = out.splitlines()[-1] if out else ''
    if r.returncode == 0:
        ok(name, last[:160])
    else:
        bad(name, out.replace('\n', ' | ')[:500])


# ---------------------------------------------------------------- 闸门定义

def gate_json_parses():
    """所有对外 JSON 必须可解析（坏 JSON 会让整站接口 500）。"""
    bad_files = []
    n = 0
    for d in ('api', '.well-known'):
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for fn in files:
                if not fn.endswith('.json'):
                    continue
                p = os.path.join(root, fn)
                n += 1
                try:
                    with open(p, encoding='utf-8') as f:
                        json.load(f)
                except Exception as ex:
                    bad_files.append(f'{os.path.relpath(p, ROOT)}: {ex}')
    for extra in ('agent-discovery.json', 'package.json'):
        p = os.path.join(ROOT, extra)
        if os.path.exists(p):
            n += 1
            try:
                with open(p, encoding='utf-8') as f:
                    json.load(f)
            except Exception as ex:
                bad_files.append(f'{extra}: {ex}')
    if bad_files:
        bad('对外 JSON 全部可解析', '; '.join(bad_files[:5]))
    else:
        ok('对外 JSON 全部可解析', f'{n} 个文件')


def gate_entities_meta_consistent():
    """entities.json 的 meta 计数不得与实体数组脱节（派生数字撒谎）。"""
    p = os.path.join(ROOT, 'api', 'entities.json')
    try:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
    except Exception as ex:
        bad('entities.json meta 与实体一致', f'读取失败: {ex}')
        return
    ents = d.get('entities') or []
    meta = d.get('meta') or {}
    problems = []
    for key in ('total_entities', 'total', 'entity_count'):
        if key in meta and meta[key] != len(ents):
            problems.append(f'meta.{key}={meta[key]} vs 实际 {len(ents)}')
    cc = meta.get('category_counts')
    if isinstance(cc, dict):
        from collections import Counter
        real = Counter(e.get('category') for e in ents)
        diff = {k: (v, real.get(k, 0)) for k, v in cc.items() if real.get(k, 0) != v}
        missing = set(real) - set(cc)
        if diff:
            problems.append(f'category_counts 不一致 {list(diff.items())[:4]}')
        if missing:
            problems.append(f'category_counts 缺品类 {sorted(missing)[:5]}')
    if problems:
        bad('entities.json meta 与实体一致', '; '.join(problems))
    else:
        ok('entities.json meta 与实体一致', f'{len(ents)} 实体')


def gate_meta_single_source():
    """entities.json 的 meta 顶层不得再出现派生副本。

    20260831 事故背景：孤儿脚本 scripts/fix_entity_kinds.js（不在部署链路内）曾把
    clean / breakdown / tier_a_traceable / traceable_pct / quarantined 写在 meta 顶层。
    其输出长期失修（顶层 tier_a_traceable=376、breakdown.ok=631）且与权威嵌套块
    （provenance_coverage.tier_a_traceable=377、data_quality.breakdown.ok=669）矛盾。
    因所有校验只读嵌套权威块，顶层副本成了无人看管的「假绿盲区」。
    本闸门把这些派生键在顶层列为禁写，强制单一真相源。
    """
    p = os.path.join(ROOT, 'api', 'entities.json')
    try:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
    except Exception as ex:
        bad('meta 单一真相源', f'读取失败: {ex}')
        return
    meta = d.get('meta') or {}
    # 这些键的权威定义在 provenance_coverage / data_quality 嵌套块内，
    # 顶层出现即为失修副本（无消费方、会与权威块漂移）。
    forbidden = (
        'clean', 'quarantined', 'breakdown', 'quarantine_pct', 'audited_at',
        'tier_a_traceable', 'tier_b_attributable', 'tier_c_none',
        'traceable_pct', 'source_pct', 'confidence_pct', 'last_verified_pct',
        'verified_true', 'verified_false', 'clean_set',
        'tier_definition', 'tier_rule',
    )
    found = [k for k in forbidden if k in meta]
    if found:
        bad('meta 单一真相源',
            f'meta 顶层出现派生副本 {found}；权威值请改读 meta.provenance_coverage / '
            f'meta.data_quality（历史成因：孤儿脚本 fix_entity_kinds.js）')
        return
    # 权威块必须存在，否则上面的「不出现」是空过而非真过
    missing = [b for b in ('provenance_coverage', 'data_quality') if not isinstance(meta.get(b), dict)]
    if missing:
        bad('meta 单一真相源', f'权威块缺失: {missing}')
        return
    ok('meta 单一真相源',
       f"顶层无派生副本；权威 tier_a={meta['provenance_coverage'].get('tier_a_traceable')} "
       f"clean={meta['data_quality'].get('clean')}")


def gate_functions_toplevel_safe():
    """Cloudflare Functions 顶层作用域禁用 Math.random / Date.now —— 违规会让
    worker 启动即失败，配合 _routes.json 的 `/*` 造成**全站 404**（20260805-18 事故）。

    判据沿用 regression.py 已验证的做法：
    1. 先剥离块注释（保持行号）—— 否则「描述该事故的注释」会把自己判死；
    2. 用**列锚定**（顶格 = 模块顶层）而非括号深度计数 —— 字符串/正则里的
       括号无法用计数法配平，深度法会恒不成立（假绿）或误判注释（假红）。
    """
    base = os.path.join(ROOT, 'functions')
    if not os.path.isdir(base):
        ok('Functions 顶层无运行时禁用调用', 'functions/ 不存在，跳过')
        return
    banned = re.compile(
        r'^(?:const|let|var|export\s+(?:const|let|var))\s+[\w${}\[\],\s]+='
        r'[^\n]*?(?:Math\.random\(|Date\.now\(|crypto\.getRandomValues\('
        r'|crypto\.randomUUID\()')
    offenders = []
    for root, _, files in os.walk(base):
        for fn in files:
            if not fn.endswith('.js'):
                continue
            p = os.path.join(root, fn)
            with open(p, encoding='utf-8', errors='ignore') as f:
                src = f.read()
            # 剥离块注释但保留行号（把注释内容替换为等长空格）
            src = re.sub(r'/\*.*?\*/',
                         lambda m: re.sub(r'[^\n]', ' ', m.group(0)),
                         src, flags=re.S)
            for i, raw in enumerate(src.splitlines(), 1):
                line = re.sub(r'//.*$', '', raw)
                if line[:1].strip() and banned.match(line):  # 顶格 = 模块顶层
                    offenders.append(
                        f'{os.path.relpath(p, ROOT)}:{i} {line.strip()[:60]}')
    if offenders:
        bad('Functions 顶层无运行时禁用调用', '; '.join(offenders[:6]))
    else:
        ok('Functions 顶层无运行时禁用调用', '列锚定判据，已剥离块注释')


def gate_github_yaml_parses():
    """.github/ 下的 YAML 必须可解析，且 Issue 模板必须带必填出处字段。

    为什么单列一条闸门：GitHub 对写坏的 Issue 模板 / workflow 是**静默失效** ——
    模板不出现在 New Issue 列表里，workflow 不触发，都不报错。
    对本项目尤其致命：Issue 模板是唯一的外部数据贡献入口（声明率 1.52% 的解法），
    静默失效等于贡献通道消失而无人知晓。

    另校验模板里「出处链接必填」没被人改成选填 —— 那是 coverage_policy
    「无出处不收」在贡献入口的唯一执行点。
    """
    base = os.path.join(ROOT, '.github')
    if not os.path.isdir(base):
        ok('GitHub 配置 YAML 可解析', '.github/ 不存在，跳过')
        return
    try:
        import yaml
    except ImportError:
        bad('GitHub 配置 YAML 可解析',
            '缺 PyYAML，无法校验（装：python -m pip install PyYAML）—— '
            '不静默放行，因为写坏的模板 GitHub 不会报错')
        return

    files, broken = [], []
    for root, _, names in os.walk(base):
        for fn in names:
            if fn.endswith(('.yml', '.yaml')):
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, ROOT).replace('\\', '/')
                files.append((rel, p))
    for rel, p in files:
        try:
            doc = yaml.safe_load(open(p, encoding='utf-8'))
        except Exception as exc:  # noqa: BLE001
            broken.append(f'{rel} 解析失败：{str(exc)[:80]}')
            continue
        if not isinstance(doc, dict):
            broken.append(f'{rel} 顶层不是映射')
            continue
        if '/ISSUE_TEMPLATE/' in rel:
            body = doc.get('body')
            if not isinstance(body, list) or not body:
                broken.append(f'{rel} 缺 body 字段列表')
                continue
            has_required_source = any(
                isinstance(it, dict)
                and it.get('id') in ('source', 'source_url')
                and (it.get('validations') or {}).get('required') is True
                for it in body)
            if not has_required_source:
                broken.append(
                    f'{rel} 出处字段(id=source)未设为必填 —— '
                    '违反 coverage_policy「无出处不收」')
    if broken:
        bad('GitHub 配置 YAML 可解析', '; '.join(broken[:5]))
    else:
        tmpl = sum(1 for rel, _ in files if '/ISSUE_TEMPLATE/' in rel)
        wf = sum(1 for rel, _ in files if '/workflows/' in rel)
        ok('GitHub 配置 YAML 可解析',
           f'{len(files)} 个文件（{wf} workflow / {tmpl} Issue 模板，'
           f'出处字段均为必填）')


def gate_no_secrets():
    """禁止把凭据提交进仓（PAT / 私钥 / API key 字面量）。"""
    pats = [
        (re.compile(r'github_pat_[A-Za-z0-9_]{20,}'), 'GitHub 细粒度 PAT'),
        (re.compile(r'ghp_[A-Za-z0-9]{30,}'), 'GitHub 经典 PAT'),
        (re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'), '私钥'),
        (re.compile(r'sk-[A-Za-z0-9]{32,}'), 'OpenAI 风格密钥'),
    ]
    try:
        r = subprocess.run(['git', 'ls-files'], cwd=ROOT,
                           capture_output=True, timeout=120)
        files = (r.stdout or b'').decode('utf-8', 'replace').split('\n')
    except Exception as ex:
        bad('仓内无凭据字面量', f'git ls-files 失败: {ex}')
        return
    hits = []
    for rel in files:
        rel = rel.strip()
        if not rel:
            continue
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            continue
        try:
            if os.path.getsize(p) > 3_000_000:
                continue
            with open(p, encoding='utf-8', errors='ignore') as f:
                txt = f.read()
        except Exception:
            continue
        for pat, label in pats:
            if pat.search(txt):
                hits.append(f'{rel} ({label})')
                break
    if hits:
        bad('仓内无凭据字面量', '; '.join(hits[:6]))
    else:
        ok('仓内无凭据字面量', f'{len([f for f in files if f.strip()])} 个跟踪文件')


def gate_semantic_index_covers_entities():
    """api/semantic_index.json（V-Link 双流·语义流）必须覆盖全部实体 id。

    2026-08-29 事故背景：语义索引由 scripts/build_semantic_index.mjs 离线生成，却从未挂进
    部署链，长期是手工跑一次的过期派生物（generated_at 2026-08-17，824 ids vs 真相源 768+142）。
    /api/semantic-search 与 judgePair 的语义近邻全靠它，过期索引会让"语义相近零件"失真。
    本闸门把"索引 ids ⊇ 实体 ids"定为不变量：任一实体缺失即判红，迫使部署前重建（deploy 0b4）。
    """
    ent_paths = [os.path.join(ROOT, 'api', 'entities.json'),
                 os.path.join(ROOT, 'api', 'entities.contrib.json')]
    entity_ids = set()
    for p in ent_paths:
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding='utf-8') as f:
                d = json.load(f)
        except Exception as ex:
            bad('语义索引覆盖全部实体', f'读取 {os.path.relpath(p, ROOT)} 失败: {ex}')
            return
        for e in (d.get('entities') or []):
            # 与 build_semantic_index.mjs 同口径：市场情报 / 企业主体不进"零件语义检索"池，
            # 网关若强行要求它们入索引，会逼 builder 索引非零件（违背检索语义）。
            kind = e.get('entity_kind')
            if kind in ('market_intelligence', 'organization'):
                continue
            if e.get('id'):
                entity_ids.add(e['id'])
    if not entity_ids:
        ok('语义索引覆盖全部实体', '无实体可校验，跳过')
        return
    idx_path = os.path.join(ROOT, 'api', 'semantic_index.json')
    if not os.path.exists(idx_path):
        bad('语义索引覆盖全部实体',
            'api/semantic_index.json 不存在（部署前必须运行 build_semantic_index.mjs）')
        return
    try:
        with open(idx_path, encoding='utf-8') as f:
            idx = json.load(f)
    except Exception as ex:
        bad('语义索引覆盖全部实体', f'索引解析失败: {ex}')
        return
    idx_ids = set(idx.get('ids') or [])
    missing = entity_ids - idx_ids
    if missing:
        bad('语义索引覆盖全部实体',
            f'{len(missing)} 个实体未进索引（索引过期/未重建）：{sorted(missing)[:5]}')
        return
    ok('语义索引覆盖全部实体', f'{len(entity_ids)} 实体全部覆盖（索引 {len(idx_ids)} ids）')


def gate_bom_assembly_sequence():
    """BOM 有序装配步骤（GRASP 借鉴）的拓扑排序逻辑不得静默退化。

    2026-09-01 新增 functions/api/bom/check.js 的 buildAssemblySequence：由机械对接关系
    （mateable 对方向 attachment.tool ∩ base.robot）构建挂载 DAG，Kahn 拓扑排序得安装次序。
    回归风险：方向判定/循环检测/启发式 fallback 任一写错，会在无告警下产出错误装配次序。
    本闸门跑 scripts/test_bom_assembly.mjs（12 断言：依赖顺序、挂载方向、basis 标注、
    全启发式、双向 ambiguous 不误判 cycle），非零退出即判红。
    """
    run_sub('BOM 装配次序拓扑排序',
            ['node', os.path.join(ROOT, 'scripts', 'test_bom_assembly.mjs')])


GATES = [
    ('语义索引覆盖全部实体', gate_semantic_index_covers_entities),
    ('实体 schema 契约', lambda: run_sub(
        '实体 schema 契约',
        [sys.executable, os.path.join(ROOT, 'scripts', 'schema_contract.py')])),
    ('mount_type 枚举契约', lambda: run_sub(
        'mount_type 枚举契约',
        [sys.executable, os.path.join(ROOT, 'scripts', 'govern_mount_type.py'),
         '--check'])),
    ('standard_conformance 覆盖率一致', lambda: run_sub(
        'standard_conformance 覆盖率一致',
        [sys.executable, os.path.join(ROOT, 'scripts', 'govern_standard_conformance.py'),
         '--check'])),
    ('对外数据集分发一致性', lambda: run_sub(
        '对外数据集分发一致性',
        [sys.executable, os.path.join(ROOT, 'scripts', 'sync_dataset_dist.py'),
         '--check'])),
    ('agent-discovery 技能清单一致性', lambda: run_sub(
        'agent-discovery 技能清单一致性',
        ['node', os.path.join(ROOT, 'scripts', 'gen_skills_manifest.mjs'),
         '--check'])),
    ('对外 JSON 可解析', gate_json_parses),
    ('entities.json meta 一致', gate_entities_meta_consistent),
    ('meta 单一真相源', gate_meta_single_source),
    ('Functions 顶层安全', gate_functions_toplevel_safe),
    ('GitHub 配置 YAML 可解析', gate_github_yaml_parses),
    ('无凭据泄漏', gate_no_secrets),
    ('BOM 装配次序拓扑排序', gate_bom_assembly_sequence),
]


def main():
    if '--list' in sys.argv:
        for name, _ in GATES:
            print(name)
        return 0
    print('=== RoboParts CI 闸门（仓内可判定子集；完整回归见 scripts/regression.py）===')
    for name, fn in GATES:
        try:
            fn()
        except Exception as ex:
            bad(name, f'闸门自身异常: {type(ex).__name__}: {ex}')
    print('\n' + '=' * 46)
    if FAILED:
        print(f'❌ 阻断：{len(FAILED)} 项未通过（通过 {len(PASSED)} 项）')
        for f in FAILED:
            print(f'   - {f}')
        return 1
    print(f'✅ 全部通过（{len(PASSED)} 项）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
