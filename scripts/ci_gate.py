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


def gate_feedback_loop_aggregate():
    """反馈信号回流聚合（Q-Planning 借鉴·失败数据回流纪律）不得静默退化。

    2026-09-01 把"只采集不消费"的 adapter-feedback / recommend-feedback 改成透明、
    样本门控的社区信号回流：aggregateCommunityFit（同对反向归并、bad 占比≥0.3→needs_review、
    样本不足→insufficient_data、adjust 计入不触发、缺 flange 跳过）与 aggregateRecfb
    （跨 16 分片累加、忽略 _updated 控制键）。本闸门跑 scripts/test_feedback_loop.mjs
    （10 断言），非零退出即判红。回归风险：配对键写错会静默把"需复核"误标为"适配良好"，
    或把小样本噪声当信号 —— 两者都直接违反假绿纪律。
    """
    run_sub('反馈信号回流聚合',
            ['node', os.path.join(ROOT, 'scripts', 'test_feedback_loop.mjs')])


def gate_flywheel_idempotency():
    """飞轮幂等/可恢复治理（OpenClaw signal→candidate→promote→effect 借鉴）。

    2026-09-01 新增：共享阶段状态台账 flywheel_state.py（纯函数 + 阴阳自测）、
    community_listener 信号摄入幂等（ID 去重 + 上限截断 + 原子写，纯自测）、
    promote 效果台账与阶段状态（fingerprintUrls / buildPromoEntry 纯函数自测）。
    三者任一退化即判红 —— 它们保证飞轮重跑不产生副作用、崩溃后可按输入指纹跳过重算。
    """
    run_sub('飞轮状态台账 flywheel_state 自测',
            [sys.executable, os.path.join(ROOT, 'scripts', 'flywheel_state.py'),
             '--self-test'])
    run_sub('信号摄入幂等 community_listener 自测',
            [sys.executable, os.path.join(ROOT, 'scripts', 'community_listener.py'),
             '--self-test'])
    run_sub('推广效果台账 promote 纯函数自测',
            ['node', os.path.join(ROOT, 'scripts', 'test_promote_ledger.mjs')])


def gate_demand_signal_classification():
    """需求信号判别层（三态 fail-closed）+ 对外端点口径。

    事故：api/demand-signal.json 曾对外宣称「已捕获 10 条真实兼容性提问信号」，
    实际这 10 条全是 AI/LLM 软件仓库的 PR（ROCm MXFP4 GEMM、godot engine、
    elastic/kibana、rust ABI），与机器人零件无关。根因是 real_signal 写死为 true、
    正则无领域锚定、relevance 写死「需判别」——fail-open：不可判定 → 直接判真。

    本闸门两段：
    1) 跑判别层三脚本的阴阳自测。必须同时证明「历史噪声确实判 noise」与
       「硬件锚定真信号确实判 confirmed」——只测绿路径的判据会把引擎写死成
       恒假而永远不红。
    2) 校验对外端点的**产物级**口径：不得出现 %% 双百分号（reflow 曾把已带 %
       的串传给 buildVerdict，而 buildVerdict 又自加 %）、不得再宣称
       「真实兼容性提问」、不得挂「反喂 ingestion」这条做不到位的建议。
       这些检查刻意直接读 api/demand-signal.json 而不是读入参——入参契约
       一致的自测永远看不见调用方传错格式。
    """
    run_sub('需求信号判别规则自测（三态 fail-closed + 历史噪声阴性对照）',
            ['node', os.path.join(ROOT, 'scripts', 'lib', 'demand_signal_rules.mjs'),
             '--self-test'])
    run_sub('需求信号扫描自测（demand_scan 报告组装）',
            ['node', os.path.join(ROOT, 'scripts', 'demand_scan.mjs'),
             '--self-test'])
    run_sub('需求信号回流自测（reflow 重判 + 产物级校验）',
            ['node', os.path.join(ROOT, 'scripts', 'reflow_demand_signal.mjs'),
             '--self-test'])

    ds_path = os.path.join(ROOT, 'api', 'demand-signal.json')
    try:
        with open(ds_path, encoding='utf-8') as f:
            ds = json.load(f)
    except OSError as ex:
        bad('需求信号对外口径', 'api/demand-signal.json 不可读: %s' % ex)
        return
    except json.JSONDecodeError as ex:
        bad('需求信号对外口径', 'JSON 解析失败: %s' % ex)
        return

    problems = []
    text = json.dumps(ds, ensure_ascii=False)
    if '%%' in text:
        problems.append('对外 JSON 出现 %% 双百分号（调用方传入已带 % 的串）')
    if '反喂 ingestion' in text:
        problems.append('actionable_fixes 仍挂「反喂 ingestion」——该指令做不到，'
                        'ingest_oss_bom.mjs 写 oss_components.json，与声明率分母'
                        ' entities.json 不相通')
    if '需判别' in text:
        problems.append('sources[].relevance 仍是写死的「需判别」占位')

    # 「真实兼容性提问」只在**对外承诺面**上算问题。reflow_note 里出现它属于
    # 留痕引述（「旧版…表述已作废」），是正确做法，误报会逼人删掉留痕。
    # 故只查 verdict + 顶层计数：断言形态是「已捕获 N 条…（N≥1）」。
    verdict = str(ds.get('verdict') or '')
    if re.search(r'已捕获\s*\d+\s*条真实兼容性提问', verdict):
        problems.append('verdict 仍以断言形态宣称「已捕获 N 条真实兼容性提问」'
                        '（仅 reflow_note 的历史引述例外）')
    if ds.get('real_query_count', 0) >= 1 and not ds.get('classification', {}).get('rule_module'):
        problems.append('real_query_count≥1 但缺 classification.rule_module，'
                        '无法证明这些计数来自判别层而非写死常量')

    cls = ds.get('classification') or {}
    if not cls.get('rule_module'):
        problems.append('缺 classification.rule_module，无法追溯判据来源')
    tri = cls.get('confirmed', 0) + cls.get('unclassified', 0) + cls.get('noise', 0)
    if tri != cls.get('total_hits'):
        problems.append('三态计数之和 %d != total_hits %s' % (tri, cls.get('total_hits')))
    if ds.get('real_query_count') != cls.get('confirmed'):
        problems.append('real_query_count %s != classification.confirmed %s'
                        % (ds.get('real_query_count'), cls.get('confirmed')))

    for i, s in enumerate(ds.get('sources') or []):
        if 'signal_state' not in s:
            problems.append('sources[%d] 缺 signal_state' % i)
            break
        if s.get('real_signal') != (s.get('signal_state') == 'confirmed'):
            problems.append('sources[%d] real_signal 与 signal_state 不一致' % i)
            break
        if s.get('signal_state') not in ('confirmed', 'unclassified', 'noise'):
            problems.append('sources[%d] signal_state 取值非法: %s'
                            % (i, s.get('signal_state')))
            break

    if problems:
        bad('需求信号对外口径', '；'.join(problems))
    else:
        ok('需求信号对外口径',
           '确认 %s / 未判 %s / 噪声 %s，无 %%、无旧假陈述、无失效建议'
           % (cls.get('confirmed'), cls.get('unclassified'), cls.get('noise')))


def gate_adapter_geometry():
    """法兰转接件的「三方几何一致性」——预览 / OpenSCAD 导出 / CLI 三处口径。

    2026-09-21 新增。背景：同一个 ISO 9409-1 法兰参数在三个地方各写了一份
    （adapter-generator.html 的 three.js 预览分支、同文件的 OpenSCAD 导出模板、
    adapters/gen_adapter.py 的 CLI），三处一致**完全靠人的记忆维持**。
    历史上预览分支真把 pinPCD 当半径用过，导致「浏览器里看到的 3D」与
    「下载去打印的 STL」是两套几何，而发现方式是人工读三处代码比对——
    gen_adapter.py 的注释在修复后还挂着过期警告一周，会误导下一个人"修"回去。

    本闸门跑 check_adapter_geometry.py，它同时做两件事：
      ① 审计生产源码（label 自洽 + pinPCD 一律直径口径 + 跨实现 (pcd,holes,thread) 一致）；
      ② 阴阳自证（喂 6 种真实分叉：预览回退半径、**只坏一半**、label 与字段不符、
         跨实现孔数分叉、pins() 半径口径、清空预设表，逐一必须判红）。
    为什么必须带自证：第一版判据只扫全文件的 `pinPCD/2*`，预览有 cos/sin 两处，
    只坏 cos 那处时闸门照常通过 —— 一个"只坏了一半"的几何分叉被放行。
    故本闸门把"只坏一半"也列为阴性对照，防止判据自己退化成装饰。
    """
    run_sub('转接件几何一致性（审计）',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'check_adapter_geometry.py')])
    run_sub('转接件几何一致性（阴阳自证）',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'check_adapter_geometry.py'),
             '--self-test'])


def gate_pure_drift():
    """纯漂移判别器 —— 收口提交的机械前置闸门。

    2026-09-21 新增。背景：部署会重生成一批派生文件（api/*.json 的
    `updated`/`audited_at` 滚日、llms.txt 的「最后更新」、data.js 的 updated、
    注入器重渲染的空白归一化），这类改动惯例收口成一句「仅时间戳滚日，无内容改动」。

    **这句话此前只能靠人肉核验。** scripts/auto_drift_heal.py 的做法是
    `git add -A` + `git commit -m "auto-heal: drift remediation"` —— 它只看
    git status 有没有改动，不看改动**是什么**。于是真内容改动（改了数字、改了
    文案、改了逻辑）会被贴上 drift 标签静默入库，review 者看到
    "drift remediation" 就放过去了。这是本仓「闸门自己分不清两种输入」病史的
    又一例（同族：L1.74 idset 假绿、L1.76 数字识别器漏网）。

    本闸门只跑 check_pure_drift.py 的 --self-test，**不在 CI 跑审计模式**：
    审计（工作树 vs HEAD）在 CI 上恒为「无改动」= 无信号；在工作树上则会把正常
    开发中的源改动报成内容改动 = 假警报。它真正的调用点是收口路径 ——
    auto_drift_heal.py 在 `git add -A` 之前调它，不过关即拒绝自动提交。
    于是 CI 上该守的就只剩「判别器自身会不会退化」：自证 12 项对照（含 5 条内容
    改动阴性对照：JSON 数字/文案/数组长度、文本词语/数字）+ 1 条**真实临时 git
    仓库端到端**用例（覆盖取 diff → 分类 → 汇总判定整条管道：纯漂移必须放行、
    夹带 798→688 必须判红）。
    """
    run_sub('纯漂移判别器阴阳自证',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'check_pure_drift.py'),
             '--self-test'])


def gate_morphology_graph():
    """形态图闸门（D4 协同设计底座的输入形式）。

    2026-09-23 新增（方向锚点 v2.1 的 Phase A2）。形态图的失效模式不是崩溃而是
    **静默说谎**：一个永远返回 unknown 的引擎与一个被写坏成"什么都判 unknown"的
    引擎产物一模一样；反过来把「未声明」误判成「兼容」，会让下游协同设计把不存在
    的组合当合法解。故本闸门两趟：
      ① 审计：不变量（缺口枢纽入度 == facts().mech_not_declared、类型 id 唯一、
         无悬挂端口、各轴类型对完整、**无几何类型参与的对必须判 unknown**、
         汇总层不得与实体脱节）+ 与已提交产物逐键比对（抓未重建的漂移）；
      ② 自证：21 项阴阳/变异对照 —— 4 阳性（证明真会算几何）、8 阴性（抽掉证据
         必须 fail-closed）、5 变异（把产物人为改坏必须判红）、3 守卫（两个真实
         踩过的 bug：连接器匹配被括号打断、中文厂商名塌成同一空 id）。
    """
    run_sub('形态图不变量（审计 + 漂移）',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_morphology_graph.py'), '--quiet'])
    run_sub('形态图判据阴阳/变异自证',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_morphology_graph.py'), '--self-test'])


def gate_embodiment_provenance():
    """具身跨层溯源闸门（方向锚点 v2.1 的 D6 地基）。

    2026-09-23 新增。产物的核心输出是**四个布尔**（L1–L4 连接条件是否满足），
    布尔最容易假绿。本闸门首版真实踩到一个假绿：L3（body→policy）判据把
    robot_ai_models 条目与自己比，而该文件是 entities.json 里那 46 条实体的
    **派生视图**（条目 id 就是实体 id），于是"引用自己"被当成跨层引用，
    产物报 body→policy=true —— 而真实的物理零件引用数是 0。
    若无此闸门，「链已闭合」会作为事实对外输出。故两趟：
      ① 契约 + 不变量（complete ⇒ 四链全满足；satisfied=false ⇒ 必须给出
         blocked_by；dangling ⇒ 必须指明断点；honest_limits 必须披露完整链数）；
      ② 自证 12 项（含 5 变异 + 3 守卫，守卫③ 是上述自引用 bug 的反证）。
    """
    run_sub('跨层溯源契约与不变量',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_provenance.py'), '--quiet'])
    run_sub('跨层溯源判据阴阳/变异自证',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_provenance.py'), '--self-test'])


def gate_croissant_metadata():
    """Croissant 元数据闸门（方向锚点 v2.1 Phase A1 副产品 —— 引用入口）。

    2026-09-23 新增。副产品不等于免检：对外元数据的失效模式是
    ① 计数与 facts() 脱节（手写副本腐烂）；② license/诚实边界被改掉后
    下游把声明值数据当 benchmark 用。故两趟：
      ① 审计：必备键、license=CC-BY-4.0、distribution 指到的文件真实存在、
         计数逐键对账 facts()、description 必须内嵌现算 total/pct（抓陈旧描述）；
      ② 自证 7 项（1 阳性 + 6 变异：翻计数/改机械四态/换 license/删
         distribution/描述去数字/清空诚实边界，每个变异必须判红）。
    """
    run_sub('Croissant 元数据审计',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_croissant.py'), '--quiet'])
    run_sub('Croissant 判据阴阳/变异自证',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_croissant.py'), '--self-test'])


def gate_compose_semantics():
    """组合语义闸门（方向锚点 v2.1 Phase B1/B2 —— compose 效应系统原型）。

    2026-09-23 新增。失效模式：① 引擎常量与产物 rule_table/verdicts 脱节；
    ② 聚合计数与 graph 现算漂移；③ fail-closed 被悄悄放宽（unknown 轴
    冒出 composed）。故两趟：
      ① 审计：结构 + 与 graph 现算逐键对账 + 判例引擎复验 +
         不变量（无已声明 SIG 通道 ⇒ composed 必为 0）；
      ② 自证 21 项（阳性/阴性/公理/fail-closed/变异/守卫/确定性往返）。
    """
    run_sub('组合语义审计（graph 现算对账 + 判例复验）',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_compose_semantics.py'), '--quiet'])
    run_sub('组合语义阳性/阴性/变异自证',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_compose_semantics.py'), '--self-test'])


def gate_gap_classification():
    """缺口成因分类闸门（D-GAP：机械缺口按成因 (i)/(ii) 拆分）。

    2026-09-24 挂闸。为什么必须挂：锚点 §6.1 明令「在 (i)/(ii) 分类完成之前，
    不得把 5.69% 单独当标准覆盖边界的实证证据」——分类结论若与 facts() 脱节，
    就是拿错误前提做方向判断。

    失效模式：
      ① 分类计数与 facts() 漂移（构建器自带 fail-fast，闸门是第二双眼睛）；
      ② 分类不完备——某实体既不算缺口也不算已解，静默消失；
      ③ 汇总层与 per_category 脱节（分品类数加不总）；
      ④ signal_axis 退回硬编码：该字段曾硬编码 ``0`` + 硬编码 note，
         2026-09-24 信号轴定向赋值后已失效一次。这正是锚点 §5.3 记的双盲区——
         锚点扫描与回归都不覆盖生成器**内部**的字面量。
    """
    run_sub('缺口成因分类生成（fail-fast 与 facts 交叉校验）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_gap_classification.py')])
    p = os.path.join(ROOT, 'api', 'gap_classification.json')
    if not os.path.exists(p):
        bad('缺口成因分类聚合口径', '产物缺失')
        return
    with open(p, encoding='utf-8') as f:
        gc = json.load(f)
    from onboarding_block import facts
    ft = facts()
    try:
        mg = json.load(open(os.path.join(ROOT, 'api', 'morphology_graph.json'),
                            encoding='utf-8'))
    except (OSError, ValueError):
        live_sig = None
    else:
        live_sig = sum(1 for n in (mg.get('nodes') or []) for pp in (n.get('ports') or [])
                       if pp['type'].startswith('SIG')
                       and pp.get('status') in ('declared', 'partial'))
    errs = _gap_doc_errors(gc, ft, live_sig)
    if errs:
        bad('缺口成因分类聚合口径', '；'.join(errs[:4]))
    else:
        b = gc.get('buckets') or {}
        og = b.get('open_gap') or {}
        ok('缺口成因分类聚合口径',
           'solved=%s na=%s open_gap=%s（unpublished %s）信号端口现算 %s'
           % (b.get('solved'), b.get('na'), og.get('open_gap_total'),
              og.get('unpublished_suspect'), live_sig))
    # 阳性对照：本闸门必须真的会红，否则它就是装饰（空闸门与空产物一样是故障）。
    # 三处变异各打一条不同的断言线：计数漂移 / 完备性破洞 / signal_axis 回退硬编码。
    for tag, mutate in (
            ('与 facts 漂移',
             lambda d: d['buckets'].update({'solved': d['buckets']['solved'] + 1})),
            ('分类不完备',
             lambda d: d['totals'].update({'entities_total': d['totals']['entities_total'] - 1})),
            ('signal_axis 退回硬编码',
             lambda d: d['signal_axis'].update({'declared_signal_ports': 0})),
    ):
        mut = json.loads(json.dumps(gc))
        mutate(mut)
        if _gap_doc_errors(mut, ft, live_sig) == []:
            bad('缺口成因分类判据自证', '变异「%s」未判红——本闸门是装饰' % tag)
        else:
            ok('缺口成因分类判据自证·%s ⇒ 红' % tag)


def gate_evidence_valuation():
    """边际声明价值（MDV）闸门——取证投资的判据源。

    2026-10-03 挂闸。本层回答一个此前全项目没回答过的问题：
    **「补哪一条机械/电气/信号声明，能把最多 unknown 配对变成可判定配对？」**

    为什么必须挂（不是又一层统计）：
      MDV 的输出包含「某轴的边际收益**恒为 0**」这种定理级断言。
      它错的方式极隐蔽——引擎里 PAIR_RANK 阈值改错一点、或 type_compat
      少登记几条，MDV 就能整体翻号，而项目所有既有检查都照样绿。
      一旦翻号，后果是**把取证资源系统性投入到死轴上**，
      且没有任何现有指标能发现（声明率反而会"上升"）。

    三重对照（项目 §四纪律：只测绿路径的闸门等于没闸门）：
      ① 构建器 fail-fast 算术守卫（内建于 build_evidence_valuation.build）
      ② verify_evidence_valuation.py 的 5 组自证：算术自洽 / 阴阳合成图
         （正样本 SYN-D MDV>0、负样本 SYN-E 缺两轴⇒MDV=0）/ 6 种变异
         全部判红 / 恒等复现 / 反向误报
      ③ 本函数额外守一条**跨层不变量**：MDV 的零轴裁决必须与
         compose_semantics 的 binding_axis 口径一致。
         两者由不同代码路径算出（MDV 走 _decidable_matrix，
         compose 走 eval_all_pairs），若分叉说明其中一层已失效。
    """
    run_sub('MDV 生成（fail-fast 算术守卫）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_evidence_valuation.py')])
    p = os.path.join(ROOT, 'api', 'evidence_valuation.json')
    if not os.path.exists(p):
        bad('MDV 产物', 'api/evidence_valuation.json 缺失')
        return
    with open(p, encoding='utf-8') as f:
        ev = json.load(f)
    errs = _mdv_errors(ev)
    if errs:
        bad('MDV 聚合口径', '；'.join(errs[:4]))
    else:
        s = ev['summary']
        dead = [a for a in ('mechanical', 'electrical', 'signal')
                if (ev['by_axis'][a]['verdict'] or '').startswith('provably_zero_mdv')]
        ok('MDV 聚合口径',
           '三轴AND=%s binding=%s 零贡献轴=%s electrical 正收益目标=%s'
           % (s['three_axis_conjunction'], s['binding_axis'],
              dead or '无', ev['by_axis']['electrical']['positive_mdv_nodes']))

    # 跨层不变量：MDV 判定的瓶颈轴须与 compose_semantics 口径咬合。
    # MDV 说「某轴 MDV 恒 0」⇒ 该轴无论怎么取证都不改变三轴 AND。
    # 若 compose_semantics 报告三轴 AND > 0，两者就矛盾了。
    cp = os.path.join(ROOT, 'api', 'compose_semantics.json')
    if os.path.exists(cp):
        with open(cp, encoding='utf-8') as f:
            cs = json.load(f)
        overall = (cs.get('aggregates') or {}).get('overall_counts') or {}
        composed = overall.get('composed', 0)
        s = ev['summary']
        if composed > 0 and s['three_axis_conjunction'] == 0:
            bad('MDV 跨层不变量',
                'compose_semantics 报 composed=%d>0，但 MDV 算出的三轴 AND=0'
                '——两层判定分叉，至少一层已失效' % composed)
        else:
            ok('MDV 跨层不变量',
               'compose_semantics composed=%d 与 MDV 三轴AND=%s 口径一致'
               % (composed, s['three_axis_conjunction']))

    # 阳性/阴性/变异自证：跑独立自证脚本（它内部含 6 变异 + 正负样本）
    run_sub('MDV 阴阳/变异自证（正样本+负样本+6 变异+恒等复现+反向误报）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'verify_evidence_valuation.py')],
            timeout=600)


def gate_cohort_feasibility():
    """最小可行同质声明集闸门——**真正的取证判据**。

    2026-10-03 挂闸。这层的存在源于一次**对自己结论的纠正**：
    MDV 层输出「16 个单条高收益节点」，但端到端注入验证发现
    单独补这 16 个，电气可判定对数 1→1 持平，**预测未兑现**。
    根因是 MDV 算的是「n 与 j 同时被填充」的联合上界，
    而严格语义下单条声明的边际收益在全库三轴恒为 0。

    修正后的判据：约束是**最小可行同质集**——K=1 不可能，K=2 即可。

    为什么必须挂闸（本层特有的失效模式）：
      这层产物自身完全自洽（计数守恒、profile 加总一致），
      它的错误**不会表现为数字异常，而会表现为语义标签错误**——
      即「把候选可行集说成保证可行集」。算术守卫抓不住这类错误。
      故本闸门额外守三件事：
        ① K=1 不可能性论证必须在位（method.k1_impossible 被删即红）；
        ② MDV 的 16 个候选目标必须全部落在本层可行集内（跨层不变量）；
        ③ 乐观上界的免责措辞必须在位（honest_limits 含 optimism 说明）。
    """
    run_sub('Cohort 生成（fail-fast 守恒守卫）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_cohort_feasibility.py')])
    p = os.path.join(ROOT, 'api', 'cohort_feasibility.json')
    if not os.path.exists(p):
        bad('Cohort 产物', 'api/cohort_feasibility.json 缺失')
        return
    with open(p, encoding='utf-8') as f:
        cf = json.load(f)
    errs = _cohort_errors(cf)
    if errs:
        bad('Cohort 聚合口径', '；'.join(errs[:4]))
    else:
        s = cf['summary']
        rc = cf.get('mdv_reconciliation') or {}
        ok('Cohort 聚合口径',
           'K=%s 可行对 %s 同质 %s（%s%%）涉及 %s 节点；MDV 对账 %s/%s'
           % (s.get('min_viable_k'), s.get('viable_pairs_k2'),
              s.get('homogeneous_viable_pairs'), s.get('homogeneous_share_pct'),
              s.get('nodes_in_any_viable_cohort'),
              rc.get('landed_in_viable_cohort'), rc.get('mdv_single_declaration_targets')))

    # 跨层不变量：MDV 的候选目标必须全部落在 cohort 可行集内
    mp = os.path.join(ROOT, 'api', 'evidence_valuation.json')
    if os.path.exists(mp):
        with open(mp, encoding='utf-8') as f:
            mdv = json.load(f)
        tops = (mdv.get('by_axis', {}).get('electrical', {}).get('top_targets') or [])
        mdv_ids = {t['id'] for t in tops if t.get('mdv', 0) > 0}
        landed = set((cf.get('mdv_reconciliation') or {}).get('ids') or [])
        missing = sorted(mdv_ids - landed)
        if missing:
            bad('Cohort 跨层不变量',
                'MDV 候选目标 %d 个未全部落在 cohort 可行集：%s —— 两层判定分叉'
                % (len(missing), missing[:5]))
        else:
            ok('Cohort 跨层不变量',
               'MDV %d 个候选目标全部落在 cohort 可行集内' % len(mdv_ids))

    # 乐观上界免责措辞必须在位（本层最大的语义风险就是把上界说成保证）
    hl = ' '.join((cf.get('meta', {}).get('honest_limits') or []))
    if '上界' not in hl or '⊆' not in hl:
        bad('Cohort 语义守卫', 'honest_limits 缺少乐观上界免责（实际可行集 ⊆ 本表）')
    else:
        ok('Cohort 语义守卫', '乐观上界免责措辞在位')

    run_sub('Cohort 阴阳/变异自证（正样本+负样本+K1 不可能性+6 变异）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'verify_cohort_feasibility.py')],
            timeout=600)


def _elec_token(label):
    """连接器 label → 形态图里的端口类型 token（必须与 build_morphology_graph._slug 同源）。

    2026-10-04 教训：闸门原先用「去空格大写子串包含」匹配 label 与 type，
    在 label 含 CJK 时**必然失配**——`_slug` 只保留 [a-z0-9]，
    "OnRobot tool I/O + Ethernet (UR tool connector 兼容)" 里
    那两个汉字被整段丢掉，于是闸门报「未落地」而接线其实是对的。

    这与 2026-10-03 的教训同型：**判据必须复用生产代码的规范化函数**，
    不能在闸门里另写一份近似实现。近似实现必然在某类输入上分叉。
    """
    return 'ELEC:CONNECTOR:' + re.sub(r'[^a-z0-9]+', '-', str(label).lower()).strip('-').upper()


def gate_electrical_wiring():
    """电气取证层 → 形态图 的**接线完整性**闸门。

    2026-10-03 挂闸。这条闸门守的是一个**已经真实发生过**的故障：

    取证层落了 4 个一手核实的连接器（6 条），产物完全自洽、字段齐全、
    闸门全绿——但 `build_morphology_graph.py` **从不读它**。
    实体仍然挂 `ELEC:UNKNOWN`，判定对数**一个都没变**。
    「产物已落盘但判据层没接线」是半接线故障：两边各自都对，接起来没反应。

    第一次接线后又踩了第二层：取证层用**本地 id**（SENS-852）作键，
    而实体侧稳定键是 **rp_id**（RP-SEN-0091）⇒ 依然一条不命中。
    两层故障叠加，症状完全相同：**改完看起来都对，就是不生效。**

    所以本闸门不看「接线代码写了没」（那是形式），只验**行为**：
      ① 取证层每条记录，必须能在形态图里找到持有对应 ELEC 端口的节点；
      ② 形态图必须存在由取证层 token 构造的端口类型；
      ③ 电气轴可判定对数必须 ≥ 1（否则接线等于没接）；
      ④ 取证层的键必须全是 rp_id 形态。
    """
    ep = os.path.join(ROOT, 'api', 'electrical_evidence.json')
    gp = os.path.join(ROOT, 'api', 'morphology_graph.json')
    cp = os.path.join(ROOT, 'api', 'compose_semantics.json')
    for p in (ep, gp, cp):
        if not os.path.exists(p):
            bad('电气接线完整性', '产物缺失：%s' % os.path.basename(p))
            return
    ee = json.load(open(ep, encoding='utf-8'))
    mg = json.load(open(gp, encoding='utf-8'))
    cs = json.load(open(cp, encoding='utf-8'))
    ents = json.load(open(os.path.join(ROOT, 'api', 'entities.json'), encoding='utf-8'))

    # rp_id -> 实体 id 列表（一个 rp_id 理论上只应有一个实体——
    # rp_id 唯一性由 schema_contract 把关；这里仍按列表处理，
    # 宁可对「意外重复」判红，也不静默只认第一条）。
    id_by_rp: dict = {}
    for e in ents.get('entities') or []:
        if e.get('rp_id'):
            id_by_rp.setdefault(e['rp_id'], []).append(e['id'])

    errs = []
    evidence = ee.get('evidence') or {}
    # ④ 键必须是 rp_id 形态（本地 id 会一条不命中）
    for k in evidence:
        if not re.match(r'^RP-[A-Z]+-\d{3,}$', k):
            errs.append('取证层键 %r 不是 rp_id 形态（本地 id 接不上）' % k)

    # ①② 每条记录必须在形态图里落地
    nodes = {n['id']: n for n in (mg.get('nodes') or []) if n.get('composable', True)}
    elec_tokens = {t['id'] for t in (mg.get('port_types') or [])
                  if t.get('axis') == 'electrical' and t.get('class') == 'registered_connector'}
    landed, unlanded = 0, []
    for rp, ev in evidence.items():
        targets = sorted(n for n in (id_by_rp.get(rp) or []) if n in nodes)
        if not targets:
            unlanded.append('%s(实体未入图)' % rp)
            continue
        want = {_elec_token(c.get('label') or c.get('id'))
                for c in ev.get('connectors') or []}
        miss = []
        for nid in targets:
            have = {p['type'] for p in (nodes[nid].get('ports') or [])
                    if p['type'].startswith('ELEC:')}
            if want & have:
                landed += 1
            else:
                miss.append(nid)
        if miss:
            unlanded.append('%s→%s' % (rp, miss))
    if unlanded:
        errs.append('取证层有 %d 个 rp_id 未在形态图全部落地：%s'
                    % (len(unlanded), unlanded[:4]))
    if not (elec_tokens & {'ELEC:UNKNOWN'} == elec_tokens) and not elec_tokens:
        errs.append('形态图无电气 registered_connector 类型')

    # ③ 行为验证：电气轴可判定对数必须 ≥1
    elec_pairs = ((cs.get('aggregates') or {}).get('axis_marginals') or {}) \
        .get('electrical', {}).get('compatible', 0)
    if elec_pairs < 1:
        errs.append('电气轴可判定对数 = %d（接线未生效或无任何可判定电气对）' % elec_pairs)

    if errs:
        bad('电气接线完整性', '；'.join(errs[:4]))
    else:
        ok('电气接线完整性',
           '取证 %d 条全部在形态图落地；电气 registered_connector 类型 %d 个；'
           '电气轴可判定对 %d' % (landed, len(elec_tokens), elec_pairs))

    # 变异检测：把取证层换成空（模拟「忘了接线」）必须判红
    empty = dict(ee)
    empty['evidence'] = {}
    if _wiring_errors(empty, mg, cs, id_by_rp) == []:
        bad('电气接线判据自证', '变异「取证层清空」未判红——本闸门是装饰')
    else:
        ok('电气接线判据自证·取证层清空 ⇒ 红')


def _wiring_errors(ee, mg, cs, id_by_rp):
    """接线完整性判据（纯函数，供闸门与变异自证共用）。"""
    errs = []
    evidence = ee.get('evidence') or {}
    for k in evidence:
        if not re.match(r'^RP-[A-Z]+-\d{3,}$', k):
            errs.append('键非 rp_id 形态：%r' % k)
    if not evidence:
        errs.append('取证层为空')
        return errs
    nodes = {n['id']: n for n in (mg.get('nodes') or []) if n.get('composable', True)}
    for rp, ev in evidence.items():
        targets = sorted(n for n in (id_by_rp.get(rp) or []) if n in nodes)
        if not targets:
            errs.append('%s 未落地（实体不在可组合节点里）' % rp)
            continue
        want = {_elec_token(c.get('label') or c.get('id'))
                for c in ev.get('connectors') or []}
        for nid in targets:
            have = {p['type'] for p in (nodes[nid].get('ports') or [])
                    if p['type'].startswith('ELEC:')}
            if not (want & have):
                errs.append('%s/%s 无电气端口（want %s / have %s）'
                            % (rp, nid, sorted(want), sorted(have)))
    elec_pairs = ((cs.get('aggregates') or {}).get('axis_marginals') or {}) \
        .get('electrical', {}).get('compatible', 0)
    if elec_pairs < 1:
        errs.append('电气轴可判定对数 = %d' % elec_pairs)
    return errs


def _cohort_errors(cf):
    """cohort_feasibility 产物的纯函数判据。"""
    errs = []
    s = cf.get('summary') or {}
    n = s.get('nodes_evaluated')
    if not isinstance(n, int) or n <= 0:
        return ['nodes_evaluated 非法：%r' % (n,)]
    total = n * (n - 1) // 2
    v = s.get('viable_pairs_k2')
    h = s.get('homogeneous_viable_pairs')
    if not isinstance(v, int) or not isinstance(h, int):
        return ['可行对计数非整数：viable=%r homogeneous=%r' % (v, h)]
    if h > v:
        errs.append('同质集 %d > 可行集 %d' % (h, v))
    if v > total:
        errs.append('可行对 %d > C(n,2) %d' % (v, total))
    if s.get('min_viable_k') != 2:
        errs.append('min_viable_k 应为 2，收到 %r' % (s.get('min_viable_k'),))
    if (s.get('k1_status') or '').startswith('possible'):
        errs.append('k1_status 声称 K=1 可行，与 method.k1_impossible 矛盾')
    if 'k1_impossible' not in (cf.get('method') or {}):
        errs.append('K=1 不可能性论证缺失')
    prof = cf.get('gap_profiles') or []
    psum = sum(p.get('viable_pairs', 0) for p in prof)
    if psum != h:
        errs.append('缺口画像加总 %d != 同质可行对 %d' % (psum, h))
    for p in prof:
        if p.get('nodes_involved', 0) > n:
            errs.append('profile %r 节点数 %d 溢出全库 %d'
                        % (p.get('missing_axes'), p['nodes_involved'], n))
    rc = cf.get('mdv_reconciliation')
    if rc and rc.get('mdv_single_declaration_targets'):
        if rc.get('landed_in_viable_cohort') != rc['mdv_single_declaration_targets']:
            errs.append('MDV 跨层对账不一致：%r/%r'
                        % (rc.get('landed_in_viable_cohort'),
                           rc['mdv_single_declaration_targets']))
    return errs


def gate_electrical_evidence():
    """电气接口取证闸门——MDV 定向取证的落地产物。

    2026-10-03 挂闸。本层是「MDV/cohort 算出的取证方向」的实际执行记录，
    它最危险的失效方式是**看起来有出处、实际是推断**：
    电气连接器一旦猜错针序，工程师照着接会烧件——这是人身与设备风险，
    不是数据质量问题。故本闸门把「必须有一手出处」变成硬约束。

    三重对照：
      ① 构建器 _validate() 强制：每条证据必须有 source_url + source_tier + vendor；
      ② M8 家族冲突表自洽：同 family 的变体针数必须真的不同，
         否则「物理不可互插」的结论没有几何依据；
      ③ 变异检测：删 source_url / 改 tier / 抹掉冲突表 / 抹掉诚实缺口声明，
         闸门必须逐一判红。
    """
    run_sub('电气取证生成（fail-fast 一手出处强制）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_electrical_evidence.py')])
    p = os.path.join(ROOT, 'api', 'electrical_evidence.json')
    if not os.path.exists(p):
        bad('电气取证产物', 'api/electrical_evidence.json 缺失')
        return
    with open(p, encoding='utf-8') as f:
        ee = json.load(f)
    errs = _electrical_evidence_errors(ee)
    if errs:
        bad('电气取证出处纪律', '；'.join(errs[:4]))
    else:
        n_conn = sum(len(v.get('connectors') or []) for v in (ee.get('evidence') or {}).values())
        cf = ee.get('coverage') or {}
        ok('电气取证出处纪律',
           '%d 器件 / %d 连接器 全部具一手出处；覆盖 MDV 目标 %s/16；'
           'M8 家族冲突组 %d'
           % (len(ee.get('evidence') or {}), n_conn,
              cf.get('evidenced_now'), len(ee.get('family_conflicts') or [])))

    # 语义守卫：诚实缺口（pinout null）必须显式登记 evidence_gap，
    # 不能悄悄留空——「不知道」必须可被 agent 看见，否则会被当成「没有针序要求」
    gaps = 0
    for nid, ev in (ee.get('evidence') or {}).items():
        for c in ev.get('connectors') or []:
            if c.get('pinout') is None:
                if not c.get('evidence_gap'):
                    bad('电气取证诚实缺口',
                        '%s/%s 的 pinout 为 null 但未登记 evidence_gap —— '
                        '「不知道」必须显式可见，否则会被误读为「无针序要求」'
                        % (nid, c.get('id')))
                else:
                    gaps += 1
    if gaps:
        ok('电气取证诚实缺口', '%d 处 pinout 未知已显式登记 evidence_gap' % gaps)

    # 变异检测（内存级注入，不改磁盘——ci_gate 会先跑 builder 把文件级篡改洗掉）
    for tag, mutate in (
            ('删除一手出处',
             lambda d: d['evidence'].pop('RP-SEN-0091')),
            ('来源 tier 降级为非法值',
             lambda d: d['evidence']['RP-GRI-0002'].update({'source_tier': 'X'})),
            ('抹掉 M8 家族冲突表',
             lambda d: d.update({'family_conflicts': []})),
            # 变异目标必须打在**真的 incompatible 表**上，且抹平**所有**几何维度。
            # 2026-10-04 修正：原变异只把 M8 表的 pins 全设成 6。判据同日扩展为
            # 「比对全部几何维度」后，thread/variant 仍有差异 ⇒ 不再破防 ⇒ 假警报。
            # 教训（SKILL 已记）：**变异体本身也要验证确实打到了破口**。
            ('冲突表 incompatible 结论失去几何依据（thread/pins/variant 抹平）',
             lambda d: [v.update({'pins': 5, 'thread': 'M8', 'variant': 'x'})
                        for v in [t for t in d['family_conflicts']
                                  if t['verdict'].startswith('incompatible')][0]['variants']]),
            ('冲突表 identity 案例被改成有差异（自相矛盾）',
             lambda d: d['family_conflicts'][-1]['variants'][0].update({'thread': 'M8'})),
            ('抹掉诚实缺口登记',
             lambda d: d['evidence']['RP-SEN-0054']['connectors'][0].pop('evidence_gap', None)),
    ):
        mut = json.loads(json.dumps(ee))
        try:
            mutate(mut)
        except (KeyError, IndexError):
            fail_msg = ('变异「%s」无法注入——判据源结构已变，闸门需同步更新' % tag)
            bad('电气取证判据自证', fail_msg)
            continue
        if _electrical_evidence_errors(mut) == [] and not _has_gap_violation(mut):
            bad('电气取证判据自证', '变异「%s」未判红——本闸门是装饰' % tag)
        else:
            ok('电气取证判据自证·%s ⇒ 红' % tag)


def _has_gap_violation(ee):
    """pinout 为 null 但未登记 evidence_gap ⇒ 诚实缺口被吞掉。"""
    for ev in (ee.get('evidence') or {}).values():
        for c in ev.get('connectors') or []:
            if c.get('pinout') is None and not c.get('evidence_gap'):
                return True
    return False


def _electrical_evidence_errors(ee):
    """电气取证的纯函数判据：出处纪律 + 冲突表几何依据。"""
    errs = []
    ev = ee.get('evidence')
    if not ev:
        return ['evidence 为空——fail-closed，无一手出处不得落盘']
    for nid, e in ev.items():
        for field in ('vendor', 'device', 'source_url', 'source', 'source_tier', 'confidence'):
            if not e.get(field):
                errs.append('%s 缺必填字段 %s' % (nid, field))
        if e.get('source_tier') not in ('A', 'B', 'C'):
            errs.append('%s source_tier=%r 非法（只允许 A/B/C）'
                        % (nid, e.get('source_tier')))
        if not e.get('connectors'):
            errs.append('%s 无连接器记录' % nid)
        for c in (e.get('connectors') or []):
            for field in ('id', 'label', 'family', 'carries', 'note'):
                if not c.get(field):
                    errs.append('%s/%s 缺字段 %s' % (nid, c.get('id', '?'), field))
    # coverage.evidenced_now 必须与实际条目数一致——否则删条目不会被发现。
    # 起因：本闸门第一版漏了这条，变异「删除一手出处」（pop 一个器件）
    # 竟然未判红——因为剩 3 条仍满足「每条都有出处」，只是**少了一条**没人发现。
    # 这就是「只测绿路径的闸门等于没闸门」的具体形态：断言够不够强，
    # 不看它抓不抓得住「缺失」而非「错误」。
    cov = ee.get('coverage') or {}
    if cov.get('evidenced_now') != len(ev):
        errs.append('coverage.evidenced_now=%r != 实际条目数 %d（有条目被删或计数漂移）'
                    % (cov.get('evidenced_now'), len(ev)))
    n_conn = sum(len(e.get('connectors') or []) for e in ev.values())
    cov_conn = cov.get('connectors_recorded')
    if cov_conn is not None and cov_conn != n_conn:
        errs.append('coverage.connectors_recorded=%r != 实际连接器数 %d'
                    % (cov_conn, n_conn))
    # 冲突表：每条表**声明的阻断维度必须真的存在差异**。
    # 2026-10-04 扩展：判据原为「针数必须不同」，被两条新表证伪——
    #   · SAME_PIN_COUNT_DIFFERENT_THREAD：针数**相同**，阻断维度是螺纹
    #     （Robotiq 2F-85 = M8 5-pole vs FT 300 = M12 5-pin A-coded，
    #      针数/针序/信号全同，仅螺纹不同 ⇒ 不可插）
    #   · M12：合法 **identity** 案例（FT 300 与 FT 300-S），所有维度都相同
    # 沿用旧判据会把合法的 identity 也判红，迫使判据退化成
    # 「同家族一律 incompatible」——那是方向相反的另一种臆断。
    # **判据必须随已登记的实证一起扩展，否则它会开始拒绝正确的东西。**
    cfs = ee.get('family_conflicts') or []
    if not cfs:
        errs.append('family_conflicts 为空——「M8 是家族不是类型」这一核心发现无机读证据')
    for cf in cfs:
        verdict = cf.get('verdict') or ''
        variants = cf.get('variants') or []
        if len(variants) < 2:
            errs.append('冲突表 %s 变体不足 2 条' % cf.get('family'))
            continue
        diffs = {d for d in ('pins', 'thread', 'family', 'variant')
                 if len({v.get(d) for v in variants}) > 1}
        if verdict.startswith('incompatible'):
            if not diffs:
                errs.append('冲突表 %s 判 incompatible 但所有几何维度都相同，'
                            '结论缺依据——没有差异就没有不可插的理由'
                            % cf.get('family'))
        elif verdict.startswith('identity'):
            if diffs:
                errs.append('冲突表 %s 判 identity 但几何维度 %s 不同 ⇒ 自相矛盾'
                            % (cf.get('family'), sorted(diffs)))
        else:
            errs.append('冲突表 %s 的 verdict %r 未登记'
                        '（只允许 incompatible_* / identity_*）'
                        % (cf.get('family'), verdict))
    return errs


def _mdv_errors(ev):
    """MDV 产物的纯函数判据（供闸门复用；不手写期望值，全部与产物自洽性对账）。"""
    errs = []
    s = ev.get('summary') or {}
    n = s.get('nodes_evaluated')
    if not isinstance(n, int) or n <= 0:
        return ['nodes_evaluated 非法：%r' % (n,)]
    total = n * (n - 1) // 2
    if s.get('total_pairs') != total:
        errs.append('total_pairs %r != C(n,2) %d' % (s.get('total_pairs'), total))
    per = s.get('per_axis_decidable_pairs') or {}
    for axis, cnt in per.items():
        if not isinstance(cnt, int) or cnt < 0 or cnt > total:
            errs.append('%s 可判定对 %r 越界 [0,%d]' % (axis, cnt, total))
    conj = s.get('two_axis_conjunction') or {}
    for combo, cnt in conj.items():
        a, b = combo.split('+')
        if a in per and b in per and cnt > min(per[a], per[b]):
            errs.append('%s=%r 超过单轴上界' % (combo, cnt))
    if conj and s.get('three_axis_conjunction', 0) > min(conj.values()):
        errs.append('三轴 AND %r 超过二轴 AND' % s.get('three_axis_conjunction'))
    # MDV 计数守恒 + 索引完备
    by = ev.get('by_axis') or {}
    expect_idx = 0
    for axis, b in by.items():
        if b['positive_mdv_nodes'] + b['zero_mdv_nodes'] != b['undeclared_nodes']:
            errs.append('%s MDV 计数不守恒：%d+%d != %d'
                        % (axis, b['positive_mdv_nodes'], b['zero_mdv_nodes'],
                           b['undeclared_nodes']))
        expect_idx += b['undeclared_nodes']
        zero_claim = (b['verdict'] or '').startswith('provably_zero_mdv')
        actually = b['positive_mdv_nodes'] == 0 and b['undeclared_nodes'] > 0
        if zero_claim != actually:
            errs.append('%s 零轴裁决 %r 与实测（正收益 %d/未声明 %d）矛盾'
                        % (axis, b['verdict'], b['positive_mdv_nodes'],
                           b['undeclared_nodes']))
    if len(ev.get('entity_mdv_index') or {}) != expect_idx:
        errs.append('entity_mdv_index 条数 %d != 未声明总数 %d'
                    % (len(ev.get('entity_mdv_index') or {}), expect_idx))
    return errs


def _gap_doc_errors(gc, ft, live_sig):
    """缺口成因分类聚合口径判据（纯函数，供闸门与变异自证共用）。"""
    errs = []
    t = gc.get('totals') or {}
    b = gc.get('buckets') or {}
    og = b.get('open_gap') or {}
    if b.get('solved') != ft.get('mech_declared'):
        errs.append('solved=%r != facts().mech_declared=%r'
                    % (b.get('solved'), ft.get('mech_declared')))
    if og.get('open_gap_total') != ft.get('mech_not_declared'):
        errs.append('open_gap_total=%r != facts().mech_not_declared=%r'
                    % (og.get('open_gap_total'), ft.get('mech_not_declared')))
    if t.get('entities_total') != ft.get('total_entities'):
        errs.append('entities_total=%r != facts().total_entities=%r'
                    % (t.get('entities_total'), ft.get('total_entities')))
    # 完备性一：全库每条必须落桶（三桶穷尽，不得有实体静默消失）
    if (b.get('solved', 0) + b.get('na', 0) + og.get('open_gap_total', 0)
            != t.get('entities_total')):
        errs.append('分类不完备：solved+na+open_gap=%r != entities_total %r'
                    % (b.get('solved', 0) + b.get('na', 0) + og.get('open_gap_total', 0),
                       t.get('entities_total')))
    # 完备性二：机械**适用面**内部是 declared/not_declared 二分。
    # na 属「非可判定粒度」不在适用面内，把它算进来会恒等失败。
    if b.get('solved', 0) + og.get('open_gap_total', 0) != t.get('mech_applicable'):
        errs.append('适用面不完备：solved+open_gap=%r != mech_applicable %r'
                    % (b.get('solved', 0) + og.get('open_gap_total', 0),
                       t.get('mech_applicable')))
    # 缺口细分必须加总回缺口总数
    sub = sum(og.get(k, 0) for k in ('proprietary_suspect', 'unpublished_suspect', 'ambiguous'))
    if sub != og.get('open_gap_total'):
        errs.append('缺口细分合计 %r != open_gap_total %r' % (sub, og.get('open_gap_total')))
    # 汇总层不得与分品类脱节
    pc = gc.get('per_category') or {}
    for key, expect in (('total', t.get('entities_total')),
                        ('solved', b.get('solved')), ('na', b.get('na')),
                        ('proprietary_suspect', og.get('proprietary_suspect')),
                        ('unpublished_suspect', og.get('unpublished_suspect')),
                        ('ambiguous', og.get('ambiguous'))):
        s = sum(v.get(key, 0) for v in pc.values())
        if s != expect:
            errs.append('per_category.%s 合计 %r != 汇总 %r' % (key, s, expect))
    # signal_axis 必须与形态图现算一致（防退回硬编码）
    if live_sig is not None:
        sa = gc.get('signal_axis') or {}
        if sa.get('declared_signal_ports') != live_sig:
            errs.append('signal_axis.declared_signal_ports=%r != 形态图现算 %r'
                        % (sa.get('declared_signal_ports'), live_sig))
    return errs


def gate_positioning_caliber():
    """定位口径闸门 —— 「我们对外自称什么」的本地半场。

    2026-09-21 新增。背景：本轮把全站定位从 6 套收敛为 1 套
    （「机器人零件兼容性判定层」），**验收方式是一次人工 grep**，结论只写进
    `docs/positioning-audit-20260921.md:276`。这不是那次 grep 做错了，而是
    它**没有机制承接**：谁再往任一页面/JSON/llms.txt 写回旧口径，不会有任何
    东西报警；更隐蔽的反向失真（源改了、线上没改）在定位轴上同样无人核验 ——
    数字轴有 verify_live_numbers.py 回探，定位轴一格都没有。

    本闸门跑 `positioning_contract.py` 的**离线**两趟（该模块是判据唯一来源，
    线上半场由 verify_live_numbers.py 复用同一份判据）：
      ① --check     本地可部署面（255 个文本文件）0 处退役表述；
      ② --self-test 15 项阴阳对照（含 4 条阴性对照 + 3 项临时目录端到端）。
    **刻意不在此处联网**：CI 上网络不可依赖，线上半场属部署后回探的职责。
    """
    run_sub('定位口径（本地扫描）',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'positioning_contract.py')])
    run_sub('定位口径判据阴阳自证',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'positioning_contract.py'),
             '--self-test'])


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
    # 2026-09-18 新增：两个 MCP 服务端（stdio npm 包 + hosted 端点）各自的
    # 品类声明曾两度漏品类（20260805 少 108 条、20260918 少 68 条且含
    # grippers/reducers）。hosted 那侧危害更大：schema enum 不放行，
    # 凡遵守 JSON Schema 的客户端根本传不进新品类，数据加载全了也没用。
    # 此闸门还禁止文案里写死品类数（改用 ${CATEGORIES.length} 现算）。
    ('MCP 品类覆盖（stdio + hosted ↔ entities.json）', lambda: run_sub(
        'MCP 品类覆盖（stdio + hosted ↔ entities.json）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'verify_mcp_coverage.py')])),
    # 2026-09-18 新增：files 白名单曾漏掉 index.js 的本地依赖 dialects.js，
    # 即「仓库能跑、装包就崩」。仓库里跑得通≠装得上，此闸门盯的是**发布物**。
    ('MCP 包完整性（入口可达模块 ⊆ files）', lambda: run_sub(
        'MCP 包完整性（入口可达模块 ⊆ files）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'verify_mcp_package.py')])),
    # 2026-09-18 新增：面向外部目录的公开清单（server.json / smithery.yaml /
    # .well-known/mcp.json）里的数字与工具集此前全是手写，已实测失修 ——
    # server.json 仍写 688（Glama 线上条目正是取它当简介），
    # smithery.yaml 仍是 688 条 + 只列 5/10 个工具。改为生成器 + 漂移红灯。
    ('公开清单数字现算（server.json / smithery.yaml / .well-known）', lambda: run_sub(
        '公开清单数字现算（server.json / smithery.yaml / .well-known）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'gen_public_manifests.py'),
         '--check'])),
    # 2026-09-19 新增：运动学可达性层（借鉴 PyRoki「URDF 优先」数据模型，
    # 把机械接口判定从静态延伸到达性上界）。风险在于：一个「永远返回
    # insufficient_data」的引擎与一个写坏的引擎，输出长得一模一样 —— 只比对外
    # JSON 会假绿。故本闸门跑 verify_kinematics.py 的阴阳自测：构造参数齐全的
    # 假链证明它真会算，再抽掉一个 link_mm 证明它真会 fail-closed，外加漂移判据。
    ('运动学可达性（阴阳自测 + 漂移）', lambda: run_sub(
        '运动学可达性（阴阳自测 + 漂移）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'verify_kinematics.py')])),
    # 2026-09-20 新增：需求信号判别层。api/demand-signal.json 曾对外宣称
    # 「已捕获 10 条真实兼容性提问信号」，实际 10 条全是 AI/LLM 软件仓库 PR。
    # fail-open 的判别层 + 对外口径漂移，一起由这个闸门盯住。
    ('需求信号判别层（三态 fail-closed + 对外口径）', gate_demand_signal_classification),
    # 2026-09-21 新增：法兰转接件的三方几何一致性（预览/OpenSCAD/CLI）。
    # 三处口径一致此前无人守，历史上真出过"预览与产物两套几何"的事故。
    ('转接件三方几何一致性', gate_adapter_geometry),
    # 2026-09-21 新增：收口提交的机械前置闸门。auto_drift_heal.py 曾把任何工作树
    # 改动都当"漂移"提交，无法区分时间戳滚动与真内容改动 ⇒ 内容改动被洗白入库。
    ('纯漂移判别（收口前置）', gate_pure_drift),
    # 2026-09-23 新增：形态图（方向锚点 v2.1 的 Phase A2 —— D4 协同设计底座的输入形式）。
    # 失效模式是静默说谎而非崩溃，故必须"不变量 + 阴阳/变异自证"双趟。
    ('形态图（不变量 + 阴阳/变异自证）', gate_morphology_graph),
    # 2026-09-23 新增：跨层溯源（方向锚点 v2.1 的 D6 地基）。核心输出是四个布尔，
    # 最容易假绿；本闸门首版真被一个自引用假阳性骗过（见 gate 文档字符串）。
    ('跨层溯源（契约 + 阴阳/变异自证）', gate_embodiment_provenance),
    # 2026-09-23 新增：Croissant 元数据（方向锚点 v2.1 Phase A1 副产品）。
    # 副产品不免检：计数对账 facts() + 诚实边界必须随元数据传播。
    ('Croissant 元数据（审计 + 阴阳/变异自证）', gate_croissant_metadata),
    # 2026-09-23 新增：组合语义（方向锚点 v2.1 Phase B1/B2）。
    ('组合语义 compose(a,b)（审计 + 阴阳/变异自证）', gate_compose_semantics),
    # 2026-09-24 新增：缺口成因分类（锚点 §6.1 D-GAP）。与上面的组合语义互补——
    # 一个是实体级静态成因归因（414 条缺口属 (i) 未公开还是 (ii) 专有），
    # 一个是配对级动态瓶颈定位（gap_distance / d1_bottleneck）。
    # 前者决定「缺口可不可攻」，后者决定「先攻哪一轴」。
    ('缺口成因分类（与 facts 交叉校验 + 完备性）', gate_gap_classification),
    # 2026-10-03 新增：边际声明价值 MDV（锚点 §6.3 / docs/RESEARCH_BARRIERS_20261003.md）。
    # 与 gap_classification 的分工：那一层判「缺口是什么成因」（实体级静态），
    # 这一层判「补哪条声明边际收益最大」（配对级动态）。
    # 必须挂闸的理由：本层输出「某轴取证收益恒为 0」这种**定理级断言**。
    # 断言错了不会崩——引擎改错一个 PAIR_RANK 阈值或 type_compat 少登记几条，
    # MDV 就可能翻号，而所有「跑通了」的检查照样绿，而项目会把资源投到死轴上。
    ('边际声明价值 MDV（上界定理 + 阴阳/变异自证）', gate_evidence_valuation),
    # 2026-10-03 新增：最小可行同质集 cohort_feasibility。
    # 这是 MDV 的**语义修正版**——MDV 把「联合上界」误标成「单条边际值」，
    # 端到端验证（单独注入 16 个目标 ⇒ 电气可判定对 1→1 持平）证明预测未兑现。
    # 修正后的判据是：K=1 不可能，K=2 即可，同质可行对 46,149 对 / 636 节点。
    # 两层必须同时挂：MDV 提供候选节点筛选，cohort 提供真正的取证判据，
    # 且 ci_gate 强制校验「MDV 的 16 个目标全部落在 cohort 可行集内」——
    # 这是跨层不变量，任一层失效都会立刻红灯。
    ('最小可行同质集（K=2 可行域 + MDV 跨层对账 + 阴阳/变异自证）',
     gate_cohort_feasibility),
    ('电气接口取证（MDV 定向，一手出处强制 + M8 家族冲突）',
     gate_electrical_evidence),
    # 2026-10-04 新增：电气取证层 → 形态图的**接线完整性**。
    # 守的是一个已真实发生过的故障：取证层落了 4 个一手核实的连接器，
    # 产物自洽 + 字段齐全 + 闸门全绿，但形态图生成器**从不读它**，
    # 实体仍挂 ELEC:UNKNOWN，判定对数一个都没变。
    # 第一次接线后又踩第二层：用本地 id 而非 rp_id 作键，依然一条不命中。
    # 形式检查（"接线代码写了没"）抓不住这类故障，只有行为验证能。
    ('电气取证接线完整性（落地 + 行为 + 变异）', gate_electrical_wiring),
    # 2026-09-24 新增：pipeline 框架（算子+DAG 骨架 + gap_classification 样板）。
    # 这是 GOAI 报告里识别的"缺 20%"——用算子/DAG 显式建模，把手写脚本拆成
    # 纯函数算子。骨架本身零依赖 stdlib，样板与旧脚本产出必须逐字段等价
    # （除 generated_at / generated_by 两个必然不同的字段）。等价性断了就是
    # 重构分叉，立刻红灯——这是防"pipeline 与旧脚本悄悄分叉"的唯一闸门。
    ('Pipeline 框架（骨架 + 等价性 + 自证 17 项）', lambda: run_sub(
        'Pipeline 框架（骨架 + 等价性 + 自证 17 项）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'verify_pipeline.py')],
        timeout=120)),
    ('定位口径本地扫描', gate_positioning_caliber),
    ('对外 JSON 可解析', gate_json_parses),
    ('entities.json meta 一致', gate_entities_meta_consistent),
    ('meta 单一真相源', gate_meta_single_source),
    ('Functions 顶层安全', gate_functions_toplevel_safe),
    ('GitHub 配置 YAML 可解析', gate_github_yaml_parses),
    ('无凭据泄漏', gate_no_secrets),
    ('BOM 装配次序拓扑排序', gate_bom_assembly_sequence),
    ('反馈信号回流聚合', gate_feedback_loop_aggregate),
    ('飞轮幂等/可恢复', gate_flywheel_idempotency),
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
