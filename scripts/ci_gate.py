#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI gates: the subset of quality checks that can run on GitHub Actions.

Why not just run scripts/regression.py directly
------------------------------------------------
`regression.py` (1000+ assertions) contains many **trace-discipline** gates that
depend on the private ops repo (`ops/` is in .gitignore and unavailable in the CI
checkout) and the full git history, so they would always fail in CI. That is why
CI runs the subset that is "independent of ops/ and decidable purely within the
repo".

Honest boundary: these gates are **not** a full regression. A full regression
still requires running locally `python scripts/regression.py` (including the
trace / ratchet / daily-report discipline). The role of CI is: **anyone
(including future external PRs) changing data or code must not bypass the
data-contract and distribution-consistency checks** — previously these checks
ran only by hand on the AI's local machine, leaving the PR path completely
unprotected.

Usage
-----
    python scripts/ci_gate.py           # all gates
    python scripts/ci_gate.py --list    # list gates only
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
    """Run an external gate script; a non-zero exit is judged red."""
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
    except FileNotFoundError as ex:
        bad(name, f'command unavailable: {ex}')
        return
    except subprocess.TimeoutExpired:
        bad(name, f'timeout {timeout}s')
        return
    out = ((r.stdout or b'') + (r.returncode and (r.stderr or b'') or b'')
           ).decode('utf-8', 'replace').strip()
    last = out.splitlines()[-1] if out else ''
    if r.returncode == 0:
        ok(name, last[:160])
    else:
        bad(name, out.replace('\n', ' | ')[:500])


# ---------------------------------------------------------------- gate definitions

def gate_json_parses():
    """All externally-served JSON must be parseable (bad JSON makes the whole site API 500)."""
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
        ok('对外 JSON 全部可解析', f'{n} files')


def gate_entities_meta_consistent():
    """entities.json meta counts must not drift from the entity array (derived numbers lie)."""
    p = os.path.join(ROOT, 'api', 'entities.json')
    try:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
    except Exception as ex:
        bad('entities.json meta 与实体一致', f'read failed: {ex}')
        return
    ents = d.get('entities') or []
    meta = d.get('meta') or {}
    problems = []
    for key in ('total_entities', 'total', 'entity_count'):
        if key in meta and meta[key] != len(ents):
            problems.append(f'meta.{key}={meta[key]} vs actual {len(ents)}')
    # 【20261008】The top-level count previously had no generator maintaining it: measured 865
    # while entities[] had already reached 868. It is an externally-served field of
    # /api/entities.json and must share the same source as the list length
    # (now owned by normalize_categories).
    if 'count' in d and d['count'] != len(ents):
        problems.append(f'top-level count={d["count"]} vs actual {len(ents)}')
    cc = meta.get('category_counts')
    if isinstance(cc, dict):
        from collections import Counter
        real = Counter(e.get('category') for e in ents)
        diff = {k: (v, real.get(k, 0)) for k, v in cc.items() if real.get(k, 0) != v}
        missing = set(real) - set(cc)
        if diff:
            problems.append(f'category_counts inconsistent {list(diff.items())[:4]}')
        if missing:
            problems.append(f'category_counts missing categories {sorted(missing)[:5]}')
    if problems:
        bad('entities.json meta 与实体一致', '; '.join(problems))
    else:
        ok('entities.json meta 与实体一致', f'{len(ents)} entities')


def gate_eval_compat():
    """The compatibility-ruling Golden evaluation set must be all-green
    (the rule engine must not silently drift from the frozen anchors).

    【20261008】Previously the Golden set existed but **was never run by any gate** —
    measured 4/6 chronically falsely-red (root cause: the evaluator's dimension
    index was misaligned, now fixed). This gate wires it into CI: the moment the
    engine behavior deviates from an anchor it goes red, forcing "change rules ->
    explicitly re-evaluate anchors and record rebaseline_log" instead of silently
    rotting.
    """
    run_sub('兼容性裁决 Golden 评估集',
            ['node', os.path.join(ROOT, 'scripts', 'eval_compat.mjs')],
            timeout=120)


def gate_readme_stats_fresh():
    """The README top RP-STATS block / §5 category table / §11 gate count must match the
    truth source computed live.

    【20261008】Guards against a real, silent drift that happened: README said "802 entities /
    5.69%" while entities.json was already 868 / 16.2% — root cause: inject_readme_stats.py
    was not in the regen pipeline (only deploy.mjs called it, and nobody re-ran it after the
    data grew). This gate runs the injector's --check: it writes nothing to disk, strips the
    date-irrelevant "last updated" field before comparing, to avoid falsely flagging any
    commit that does not regenerate the README (chronic false alarms).
    """
    run_sub('README 统计块与真相源一致',
            [sys.executable, os.path.join(ROOT, 'scripts', 'inject_readme_stats.py'), '--check'],
            timeout=180)


def gate_meta_single_source():
    """The meta top level of entities.json must no longer contain derived duplicates.

    20260831 incident background: the orphan script scripts/fix_entity_kinds.js (not in the
    deploy chain) once wrote clean / breakdown / tier_a_traceable / traceable_pct / quarantined
    at the meta top level. Its output was long unmaintained (top-level tier_a_traceable=376,
    breakdown.ok=631) and contradicted the authoritative nested blocks
    (provenance_coverage.tier_a_traceable=377, data_quality.breakdown.ok=669). Because every
    check only read the nested authoritative blocks, the top-level copies became an
    unmonitored "false-green blind spot". This gate forbids these derived keys at the top
    level, forcing a single source of truth.
    """
    p = os.path.join(ROOT, 'api', 'entities.json')
    try:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
    except Exception as ex:
        bad('meta 单一真相源', f'read failed: {ex}')
        return
    meta = d.get('meta') or {}
    # The authoritative definitions of these keys live inside the provenance_coverage /
    # data_quality nested blocks. Their appearance at the top level means an unmaintained
    # duplicate (no consumer, will drift from the authoritative blocks).
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
            f'derived copy appeared at meta top level {found}; read authoritative values from '
            f'meta.provenance_coverage / meta.data_quality (historical cause: orphan script '
            f'fix_entity_kinds.js)')
        return
    # The authoritative blocks must exist, otherwise the "must not appear" above is a free
    # pass rather than a real pass.
    missing = [b for b in ('provenance_coverage', 'data_quality') if not isinstance(meta.get(b), dict)]
    if missing:
        bad('meta 单一真相源', f'authoritative block missing: {missing}')
        return
    ok('meta 单一真相源',
       f"no derived copy at top level; authoritative tier_a="
       f"{meta['provenance_coverage'].get('tier_a_traceable')} "
       f"clean={meta['data_quality'].get('clean')}")


def gate_functions_toplevel_safe():
    """Cloudflare Functions top-level scope must not use Math.random / Date.now — a violation
    makes the worker fail to start, and combined with _routes.json's `/*` it causes **site-wide
    404s** (20260805-18 incident).

    The criterion reuses the already-validated approach from regression.py:
    1. First strip block comments (preserving line numbers) — otherwise "the comment describing
       this incident" would condemn itself to death;
    2. Use **column anchoring** (left-aligned = module top level) rather than brace-depth
       counting — parentheses inside strings/regex cannot be balanced by counting, so a
       depth-based approach always fails (false green) or misjudges comments (false red).
    """
    base = os.path.join(ROOT, 'functions')
    if not os.path.isdir(base):
        ok('Functions 顶层无运行时禁用调用', 'functions/ does not exist, skipped')
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
            # Strip block comments but preserve line numbers (replace comment content with
            # equal-length spaces).
            src = re.sub(r'/\*.*?\*/',
                         lambda m: re.sub(r'[^\n]', ' ', m.group(0)),
                         src, flags=re.S)
            for i, raw in enumerate(src.splitlines(), 1):
                line = re.sub(r'//.*$', '', raw)
                if line[:1].strip() and banned.match(line):  # left-aligned = module top level
                    offenders.append(
                        f'{os.path.relpath(p, ROOT)}:{i} {line.strip()[:60]}')
    if offenders:
        bad('Functions 顶层无运行时禁用调用', '; '.join(offenders[:6]))
    else:
        ok('Functions 顶层无运行时禁用调用', 'column-anchored criterion, block comments stripped')


def gate_github_yaml_parses():
    """.github/ YAML must be parseable, and Issue templates must carry a required source field.

    Why a separate gate: GitHub **silently ignores** a broken Issue template / workflow —
    the template simply does not appear in the New Issue list, the workflow does not trigger,
    and nothing errors. For this project it is especially fatal: the Issue template is the only
    external data-contribution entry point (the fix for the 1.52% declaration rate), and silent
    failure means the contribution channel vanishes unnoticed.

    It also verifies that the template's "source link required" has not been changed to
    optional — that is the only enforcement point of coverage_policy's "no source, no intake"
    at the contribution entry.
    """
    base = os.path.join(ROOT, '.github')
    if not os.path.isdir(base):
        ok('GitHub 配置 YAML 可解析', '.github/ does not exist, skipped')
        return
    try:
        import yaml
    except ImportError:
        bad('GitHub 配置 YAML 可解析',
            'PyYAML missing, cannot validate (install: python -m pip install PyYAML) — '
            'not silently passing, because GitHub will not error on a broken template')
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
            broken.append(f'{rel} parse failed: {str(exc)[:80]}')
            continue
        if not isinstance(doc, dict):
            broken.append(f'{rel} top level is not a mapping')
            continue
        if '/ISSUE_TEMPLATE/' in rel:
            body = doc.get('body')
            if not isinstance(body, list) or not body:
                broken.append(f'{rel} missing body field list')
                continue
            has_required_source = any(
                isinstance(it, dict)
                and it.get('id') in ('source', 'source_url')
                and (it.get('validations') or {}).get('required') is True
                for it in body)
            if not has_required_source:
                broken.append(
                    f'{rel} source field (id=source) not set required — '
                    'violates coverage_policy "no source, no intake"')
    if broken:
        bad('GitHub 配置 YAML 可解析', '; '.join(broken[:5]))
    else:
        tmpl = sum(1 for rel, _ in files if '/ISSUE_TEMPLATE/' in rel)
        wf = sum(1 for rel, _ in files if '/workflows/' in rel)
        ok('GitHub 配置 YAML 可解析',
           f'{len(files)} files ({wf} workflow / {tmpl} Issue templates, '
           f'source field all required)')


def gate_no_secrets():
    """Forbid committing credentials into the repo (PAT / private key / API key literals)."""
    pats = [
        (re.compile(r'github_pat_[A-Za-z0-9_]{20,}'), 'GitHub fine-grained PAT'),
        (re.compile(r'ghp_[A-Za-z0-9]{30,}'), 'GitHub classic PAT'),
        (re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'), 'private key'),
        (re.compile(r'sk-[A-Za-z0-9]{32,}'), 'OpenAI-style key'),
    ]
    try:
        r = subprocess.run(['git', 'ls-files'], cwd=ROOT,
                           capture_output=True, timeout=120)
        files = (r.stdout or b'').decode('utf-8', 'replace').split('\n')
    except Exception as ex:
        bad('仓内无凭据字面量', f'git ls-files failed: {ex}')
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
        ok('仓内无凭据字面量', f'{len([f for f in files if f.strip()])} tracked files')


def gate_semantic_index_covers_entities():
    """api/semantic_index.json (V-Link dual-stream · semantic stream) must cover all entity ids.

    2026-08-29 incident background: the semantic index is generated offline by
    scripts/build_semantic_index.mjs but was never wired into the deploy chain; it was long an
    expired artifact run by hand once (generated_at 2026-08-17, 824 ids vs truth source
    768+142). Both /api/semantic-search and judgePair's semantic nearest-neighbors rely on it,
    and an expired index distorts "semantically similar parts". This gate makes "index ids ⊇
    entity ids" an invariant: any missing entity turns red, forcing a rebuild before deploy
    (deploy 0b4).
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
            bad('语义索引覆盖全部实体', f'read {os.path.relpath(p, ROOT)} failed: {ex}')
            return
        for e in (d.get('entities') or []):
            # Same scope as build_semantic_index.mjs: market intelligence / organization
            # principals do not enter the "part semantic retrieval" pool. If the gateway forced
            # them into the index, it would push the builder to index non-parts (violating
            # retrieval semantics).
            kind = e.get('entity_kind')
            if kind in ('market_intelligence', 'organization'):
                continue
            if e.get('id'):
                entity_ids.add(e['id'])
    if not entity_ids:
        ok('语义索引覆盖全部实体', 'no entities to validate, skipped')
        return
    idx_path = os.path.join(ROOT, 'api', 'semantic_index.json')
    if not os.path.exists(idx_path):
        bad('语义索引覆盖全部实体',
            'api/semantic_index.json does not exist (must run build_semantic_index.mjs before deploy)')
        return
    try:
        with open(idx_path, encoding='utf-8') as f:
            idx = json.load(f)
    except Exception as ex:
        bad('语义索引覆盖全部实体', f'index parse failed: {ex}')
        return
    idx_ids = set(idx.get('ids') or [])
    missing = entity_ids - idx_ids
    if missing:
        bad('语义索引覆盖全部实体',
            f'{len(missing)} entities not in index (index expired/not rebuilt): '
            f'{sorted(missing)[:5]}')
        return
    ok('语义索引覆盖全部实体',
       f'all {len(entity_ids)} entities covered (index has {len(idx_ids)} ids)')


def gate_bom_assembly_sequence():
    """The BOM ordered-assembly step (GRASP-inspired) topological-sort logic must not silently
    regress.

    2026-09-01 added functions/api/bom/check.js's buildAssemblySequence: it builds a mounting
    DAG from mechanical mating relations (mateable pair direction attachment.tool ∩
    base.robot) and Kahn topo-sorts the install order. Regression risk: any wrong direction
    detection / cycle detection / heuristic fallback silently produces a wrong assembly order.
    This gate runs tests/test_bom_assembly.mjs (12 assertions: dependency order, mount
    direction, basis annotation, all-heuristic, bidirectional ambiguous not misjudged as cycle),
    non-zero exit is red. 2026-10-07: script moved from scripts/ to tests/, tests separated
    from the main script.
    """
    run_sub('BOM 装配次序拓扑排序',
            ['node', os.path.join(ROOT, 'tests', 'test_bom_assembly.mjs')])


def gate_feedback_loop_aggregate():
    """The feedback-signal reflux aggregation (Q-Planning-inspired · failed-data reflux
    discipline) must not silently regress.

    2026-09-01 changed the "collect-only, consume-never" adapter-feedback / recommend-feedback
    into transparent, sample-gated community-signal reflux: aggregateCommunityFit
    (same-pair reverse merge, bad ratio ≥0.3→needs_review, insufficient sample→
    insufficient_data, adjust not counted, missing flange skipped) and aggregateRecfb (accumulate
    across 16 shards, ignore the _updated control key). This gate runs
    tests/test_feedback_loop.mjs (10 assertions), non-zero exit is red. Regression risk: a wrong
    pairing key silently labels "needs review" as "well fitted", or treats small-sample noise as
    signal — both directly violate the false-green discipline. 2026-10-07: script moved from
    scripts/ to tests/.
    """
    run_sub('反馈信号回流聚合',
            ['node', os.path.join(ROOT, 'tests', 'test_feedback_loop.mjs')])


def gate_flywheel_idempotency():
    """Flywheel idempotent / recoverable governance (OpenClaw signal→candidate→promote→effect
    inspired).

    2026-09-01 added: shared stage-state ledger flywheel_state.py (pure functions + yin-yang
    self-test), community_listener signal ingestion idempotency (ID dedupe + cap truncation +
    atomic write, pure self-test), promote effect ledger and stage state (fingerprintUrls /
    buildPromoEntry pure-function self-test). Any of the three regressing is red — they
    guarantee the flywheel produces no side effects on re-run and can skip recompute by input
    fingerprint after a crash.
    """
    run_sub('飞轮状态台账 flywheel_state 自测',
            [sys.executable, os.path.join(ROOT, 'scripts', 'flywheel_state.py'),
             '--self-test'])
    run_sub('信号摄入幂等 community_listener 自测',
            [sys.executable, os.path.join(ROOT, 'scripts', 'community_listener.py'),
             '--self-test'])
    run_sub('推广效果台账 promote 纯函数自测',
            ['node', os.path.join(ROOT, 'tests', 'test_promote_ledger.mjs')])


def gate_demand_signal_classification():
    """Demand-signal classification layer (three-state fail-closed) + external-endpoint wording.

    Incident: api/demand-signal.json once claimed externally "captured 10 real
    compatibility-question signals", but all 10 were actually PRs from AI/LLM software repos
    (ROCm MXFP4 GEMM, godot engine, elastic/kibana, rust ABI), unrelated to robot parts.
    Root cause: real_signal hard-coded to true, regex with no domain anchor, relevance
    hard-coded to "需判别" (needs-classification) — fail-open: undecidable → judged true.

    This gate has two parts:
    1) Run the classification layer's three-script yin-yang self-test. It must prove both that
       "historical noise is indeed judged noise" and that "hardware-anchored real signals are
       indeed judged confirmed" — a criterion that only tests green paths would freeze the
       engine into always-false and never red.
    2) Validate the external endpoint's **artifact-level** wording: no %% double percent
       (reflow once passed a string already containing % into buildVerdict, which then added %
       itself), no more claiming "真实兼容性提问" (real compatibility questions), no hanging the
       infeasible "反喂 ingestion" suggestion. These checks deliberately read
       api/demand-signal.json directly rather than the input args — an input-contract-consistent
       self-test would never see the caller passing the wrong format.
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
        bad('需求信号对外口径', 'api/demand-signal.json unreadable: %s' % ex)
        return
    except json.JSONDecodeError as ex:
        bad('需求信号对外口径', 'JSON parse failed: %s' % ex)
        return

    problems = []
    text = json.dumps(ds, ensure_ascii=False)
    if '%%' in text:
        problems.append('external JSON contains %% double percent (caller passed a string '
                        'already containing %)')
    # Keep: this checks the JSON does NOT contain the prohibited Chinese suggestion. After the
    # repo is English this count stays 0; the assertion logic is preserved.
    if '反喂 ingestion' in text:
        problems.append('actionable_fixes still hangs the prohibited "反喂 ingestion" '
                        'suggestion — that instruction is infeasible; ingest_oss_bom.mjs '
                        'writes oss_components.json, which is unrelated to the declaration-rate '
                        'denominator entities.json')
    # Keep: checks the JSON does NOT contain the hard-coded placeholder "需判别".
    if '需判别' in text:
        problems.append('sources[].relevance is still the hard-coded placeholder "需判别"')

    # "真实兼容性提问" is only a problem on the **external promise surface**. Its appearance in
    # reflow_note is a trace quote ("old wording ... deprecated"), which is correct; a false
    # positive here would push people to delete the trace. So we only check verdict + the
    # top-level count: the assertion shape is "captured N ... (N≥1)".
    verdict = str(ds.get('verdict') or '')
    # Keep: regex must match Chinese text that remains in the JSON; assertion logic preserved.
    if re.search(r'已捕获\s*\d+\s*条真实兼容性提问', verdict):
        problems.append('verdict still asserts in the form "已捕获 N 条真实兼容性提问" '
                        '(only reflow_note historical quotes are exempt)')
    if ds.get('real_query_count', 0) >= 1 and not ds.get('classification', {}).get('rule_module'):
        problems.append('real_query_count≥1 but missing classification.rule_module, '
                        'cannot prove these counts come from the classification layer '
                        'rather than hard-coded constants')

    cls = ds.get('classification') or {}
    if not cls.get('rule_module'):
        problems.append('missing classification.rule_module, cannot trace criterion source')
    tri = cls.get('confirmed', 0) + cls.get('unclassified', 0) + cls.get('noise', 0)
    if tri != cls.get('total_hits'):
        problems.append('three-state count sum %d != total_hits %s'
                        % (tri, cls.get('total_hits')))
    if ds.get('real_query_count') != cls.get('confirmed'):
        problems.append('real_query_count %s != classification.confirmed %s'
                        % (ds.get('real_query_count'), cls.get('confirmed')))

    for i, s in enumerate(ds.get('sources') or []):
        if 'signal_state' not in s:
            problems.append('sources[%d] missing signal_state' % i)
            break
        if s.get('real_signal') != (s.get('signal_state') == 'confirmed'):
            problems.append('sources[%d] real_signal inconsistent with signal_state' % i)
            break
        if s.get('signal_state') not in ('confirmed', 'unclassified', 'noise'):
            problems.append('sources[%d] signal_state invalid value: %s'
                            % (i, s.get('signal_state')))
            break

    if problems:
        bad('需求信号对外口径', '；'.join(problems))
    else:
        ok('需求信号对外口径',
           'confirmed %s / unclassified %s / noise %s, no %%, no stale false claims, '
           'no dead suggestions'
           % (cls.get('confirmed'), cls.get('unclassified'), cls.get('noise')))


def gate_adapter_geometry():
    """Flange adapter's "three-way geometric consistency" — preview / OpenSCAD export / CLI.

    2026-09-21 added. Background: the same ISO 9409-1 flange parameters were written in three
    places (adapter-generator.html's three.js preview branch, the same file's OpenSCAD export
    template, adapters/gen_adapter.py's CLI); the three stayed consistent **purely by human
    memory**. Historically the preview branch actually used pinPCD as a radius, making "the 3D
    seen in browser" and "the STL downloaded to print" two different geometries, and the only
    way it was found was manually diffing the three code locations — gen_adapter.py's comment
    kept an expired warning for a week after the fix, misleading the next person into "fixing"
    it back.

    This gate runs check_adapter_geometry.py, which does two things:
      ① Audit production source (label self-consistent + pinPCD always diameter convention +
         cross-implementation (pcd,holes,thread) consistent);
      ② Yin-yang self-prove (feed 6 real forks: preview reverts radius, **breaks only half**,
         label mismatches field, cross-implementation hole-count fork, pins() radius
         convention, cleared preset table — each must turn red).
    Why self-proof is mandatory: the first-version criterion only scanned the whole file for
    `pinPCD/2*`; the preview has cos/sin in two places, so when only the cos place broke the
    gate still passed — a "broke-only-half" geometry fork got waved through. So this gate also
    lists "broke only half" as a negative control, preventing the criterion from degrading into
    decoration.
    """
    run_sub('转接件几何一致性（审计）',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'check_adapter_geometry.py')])
    run_sub('转接件几何一致性（阴阳自证）',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'check_adapter_geometry.py'),
             '--self-test'])


def gate_pure_drift():
    """Pure-drift discriminator — the mechanical pre-gate for closing a commit.

    2026-09-21 added. Background: deploy regenerates a batch of derived files (api/*.json's
    `updated`/`audited_at` rolling daily, llms.txt's "last updated", data.js's updated, the
    injector's re-rendered blank normalization); such changes are conventionally closed as a
    single "timestamps rolled, no content change" sentence.

    **This sentence could only be verified by hand before.** scripts/auto_drift_heal.py's
    approach is `git add -A` + `git commit -m "auto-heal: drift remediation"` — it only looks
    at whether git status has changes, not **what** changed. So real content changes (changed
    numbers, changed copy, changed logic) got labeled drift and silently committed; the reviewer
    saw "drift remediation" and let it through. This is another instance of this repo's history
    of "gates that cannot tell two kinds of input apart" (same family: L1.74 idset false-green,
    L1.76 number-recognizer leak).

    This gate only runs check_pure_drift.py's --self-test, **not the audit mode in CI**: the
    audit (working tree vs HEAD) is always "no change" = no signal on CI, and on a working tree
    it would flag normal in-development source changes as content changes = false alarm. Its
    real call site is the closing path — auto_drift_heal.py calls it before `git add -A`, and
    if it fails it refuses the auto-commit. So on CI the only thing to guard is "does the
    discriminator itself degrade": 12 self-test controls (including 5 content-change negative
    controls: JSON number/copy/array length, text word/number) + 1 **real temporary git repo
    end-to-end** case (covers diff → classify → summarize the whole pipeline: pure drift must
    pass, smuggling 798→688 must turn red).
    """
    run_sub('纯漂移判别器阴阳自证',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'check_pure_drift.py'),
             '--self-test'])


def gate_morphology_graph():
    """Morphology-graph gate (D4 collaborative-design base's input form).

    2026-09-23 added (direction anchor v2.1's Phase A2). The morphology graph's failure mode is
    not a crash but **silent lying**: an engine that always returns unknown and one whose output
    was broken to "judge everything unknown" look identical; conversely misjudging
    "undeclared" as "compatible" lets downstream collaborative design treat non-existent
    combinations as valid. So this gate runs twice:
      ① Audit: invariants (gap-hub in-degree == facts().mech_not_declared, type id unique, no
         dangling ports, every axis type-pair complete, **no geometry-type-involving pair must
         judge unknown**, summary must not drift from entities) + key-by-key comparison against
         the committed artifact (catch unrebuilt drift);
      ② Self-proof: 21 yin-yang/mutation controls — 4 positive (prove it really computes
         geometry), 8 negative (evidence removed must fail-closed), 5 mutations (artificially
         break the artifact must turn red), 3 guards (two real bugs hit: connector match broken
         by parentheses, Chinese vendor name collapsed into the same empty id).
    """
    run_sub('形态图不变量（审计 + 漂移）',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_morphology_graph.py'), '--quiet'])
    run_sub('形态图判据阴阳/变异自证',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_morphology_graph.py'), '--self-test'])


def gate_embodiment_provenance():
    """Embodied cross-layer provenance gate (direction anchor v2.1's D6 foundation).

    2026-09-23 added. The artifact's core output is **four booleans** (whether L1–L4 connection
    conditions are satisfied); booleans are the easiest to false-green. This gate's first
    version genuinely hit a false-green: the L3 (body→policy) criterion compared
    robot_ai_models entries against themselves, but that file is a **derived view** of the 46
    entities in entities.json (entry id is the entity id), so "referencing itself" was treated
    as a cross-layer reference, and the artifact reported body→policy=true — while the real
    physical-part reference count was 0. Without this gate, "chain closed" would be output as a
    fact. So it runs twice:
      ① Contract + invariants (complete ⇒ all four chains satisfied; satisfied=false ⇒ must give
         blocked_by; dangling ⇒ must name the break point; honest_limits must disclose full
         chain count);
      ② Self-proof 12 controls (including 5 mutations + 3 guards, guard ③ is the counter-proof
         of the above self-reference bug).
    """
    run_sub('跨层溯源契约与不变量',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_provenance.py'), '--quiet'])
    run_sub('跨层溯源判据阴阳/变异自证',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_provenance.py'), '--self-test'])


def gate_croissant_metadata():
    """Croissant metadata gate (direction anchor v2.1 Phase A1 by-product — citation entry).

    2026-09-23 added. A by-product is not exempt from inspection: externally-served metadata's
    failure mode is ① counts drifting from facts() (hand-written copy rots); ② license/honest
    boundary changed, then downstream treats the declared-value data as benchmark. So twice:
      ① Audit: required keys, license=CC-BY-4.0, distribution files actually exist, counts
         reconciled key-by-key against facts(), description must embed live-computed total/pct
         (catch stale descriptions);
      ② Self-proof 7 controls (1 positive + 6 mutations: flip counts / change mechanical
         four-state / swap license / delete distribution / strip numbers from description /
         clear honest boundary; each mutation must turn red).
    """
    run_sub('Croissant 元数据审计',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_croissant.py'), '--quiet'])
    run_sub('Croissant 判据阴阳/变异自证',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_croissant.py'), '--self-test'])


def gate_compose_semantics():
    """Compose semantics gate (direction anchor v2.1 Phase B1/B2 — compose effect-system
    prototype).

    2026-09-23 added. Failure modes: ① engine constants drift from artifact rule_table/verdicts;
    ② aggregate counts drift from graph live-computed; ③ fail-closed silently relaxed (unknown
    axis sprouts composed). So twice:
      ① Audit: structure + key-by-key reconciliation against graph live-computed + verdict
         engine re-verification + invariant (no declared SIG channel ⇒ composed must be 0);
      ② Self-proof 21 controls (positive/negative/axiom/fail-closed/mutation/guard/
         determinism round-trip).
    """
    run_sub('组合语义审计（graph 现算对账 + 判例复验）',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_compose_semantics.py'), '--quiet'])
    run_sub('组合语义阳性/阴性/变异自证',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_compose_semantics.py'), '--self-test'])


def gate_gap_classification():
    """Gap-cause classification gate (D-GAP: mechanical gap split by cause (i)/(ii)).

    2026-09-24 gated. Why it must be gated: anchor §6.1 explicitly orders "before the (i)/(ii)
    classification is complete, do not treat 5.69% alone as empirical evidence for the standard
    coverage boundary" — if the classification conclusion drifts from facts(), it is making
    direction decisions on wrong premises.

    Failure modes:
      ① Classification count drifts from facts() (builder has its own fail-fast; this gate is a
         second pair of eyes);
      ② Classification incomplete — some entity is neither gap nor solved, silently vanishing;
      ③ Summary layer drifts from per_category (per-category numbers don't add up);
      ④ signal_axis reverts to hard-code: that field was once hard-coded ``0`` + hard-coded
         note, and after the 2026-09-24 signal-axis directional assignment it broke once. This
         is exactly the double blind spot recorded in anchor §5.3 — anchor scans and regression
         neither cover literals **inside** the generator.
    """
    run_sub('缺口成因分类生成（fail-fast 与 facts 交叉校验）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_gap_classification.py')])
    p = os.path.join(ROOT, 'api', 'gap_classification.json')
    if not os.path.exists(p):
        bad('缺口成因分类聚合口径', 'artifact missing')
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
           'solved=%s na=%s open_gap=%s (unpublished %s) signal ports computed live %s'
           % (b.get('solved'), b.get('na'), og.get('open_gap_total'),
              og.get('unpublished_suspect'), live_sig))
    # Positive control: this gate must genuinely turn red, otherwise it is decoration (an empty
    # gate and an empty artifact are equally a fault). The three mutations each hit a different
    # assertion line: count drift / completeness hole / signal_axis revert-to-hardcode.
    for tag, mutate in (
            ('drift from facts',
             lambda d: d['buckets'].update({'solved': d['buckets']['solved'] + 1})),
            ('incomplete classification',
             lambda d: d['totals'].update({'entities_total': d['totals']['entities_total'] - 1})),
            ('signal_axis reverted to hardcode',
             lambda d: d['signal_axis'].update({'declared_signal_ports': 0})),
    ):
        mut = json.loads(json.dumps(gc))
        mutate(mut)
        if _gap_doc_errors(mut, ft, live_sig) == []:
            bad('缺口成因分类判据自证', 'mutation "%s" did not turn red — this gate is decorative' % tag)
        else:
            ok('缺口成因分类判据自证·%s ⇒ 红' % tag)


def gate_evidence_valuation():
    """Marginal declaration value (MDV) gate — the criterion source for取证 investment.

    2026-10-03 gated. This layer answers a question the whole project had never answered before:
    **"supplementing which mechanical/electrical/signal declaration turns the most unknown
    pairs into decidable pairs?"**

    Why it must be gated (not just another statistics layer): MDV's output includes theorem-grade
    assertions like "the marginal gain of some axis is **provably 0**". It fails in an extremely
    hidden way — change PAIR_RANK threshold slightly wrong, or under-register a few type_compat
    entries, and MDV flips sign entirely while every existing project check stays green. Once it
    flips, the consequence is **systematically pouring forensic resources into dead axes**, and
    no existing metric catches it (the declaration rate would even "rise").

    Triple control (project §four-disciplines: a gate that only tests green paths is no gate):
      ① Builder fail-fast arithmetic guard (built into build_evidence_valuation.build)
      ② verify_evidence_valuation.py's 5 self-proof groups: arithmetic self-consistency /
         yin-yang synthesis graph (positive SYN-D MDV>0, negative SYN-E missing two axes⇒MDV=0)
         / 6 mutations all red / identity reproduction / reverse false-positive
      ③ This function additionally guards a **cross-layer invariant**: MDV's zero-axis verdict
         must agree with compose_semantics's binding_axis convention. The two are computed by
         different code paths (MDV via _decidable_matrix, compose via eval_all_pairs); if they
         diverge, one layer has gone stale.
    """
    run_sub('MDV 生成（fail-fast 算术守卫）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_evidence_valuation.py')])
    p = os.path.join(ROOT, 'api', 'evidence_valuation.json')
    if not os.path.exists(p):
        bad('MDV 产物', 'api/evidence_valuation.json missing')
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
           'three-axis AND=%s binding=%s zero-contribution axis=%s electrical positive target=%s'
           % (s['three_axis_conjunction'], s['binding_axis'],
              dead or '无', ev['by_axis']['electrical']['positive_mdv_nodes']))

    # Cross-layer invariant: the bottleneck axis MDV judges must mesh with compose_semantics's
    # convention. MDV says "some axis's MDV is provably 0" ⇒ no matter how much forensics on
    # that axis, three-axis AND does not change. If compose_semantics reports three-axis AND > 0,
    # the two contradict.
    cp = os.path.join(ROOT, 'api', 'compose_semantics.json')
    if os.path.exists(cp):
        with open(cp, encoding='utf-8') as f:
            cs = json.load(f)
        overall = (cs.get('aggregates') or {}).get('overall_counts') or {}
        composed = overall.get('composed', 0)
        s = ev['summary']
        if composed > 0 and s['three_axis_conjunction'] == 0:
            bad('MDV 跨层不变量',
                'compose_semantics reports composed=%d>0, but MDV computed three-axis AND=0'
                ' — two layers diverge, at least one has gone stale' % composed)
        else:
            ok('MDV 跨层不变量',
               'compose_semantics composed=%d agrees with MDV three-axis AND=%s convention'
               % (composed, s['three_axis_conjunction']))

    # Positive/negative/mutation self-proof: run the standalone self-proof script (it contains
    # 6 mutations + positive/negative samples internally).
    run_sub('MDV 阴阳/变异自证（正样本+负样本+6 变异+恒等复现+反向误报）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'verify_evidence_valuation.py')],
            timeout=600)


def gate_cohort_feasibility():
    """Minimal-viable homogeneous-declaration-set gate — **the real forensic criterion**.

    2026-10-03 gated. This layer exists because of a **self-correction of our own conclusion**:
    the MDV layer output "16 single high-yield nodes", but end-to-end injection verification
    found that adding just those 16, electrical decidable pairs went 1→1 flat — **the prediction
    did not materialize**. Root cause: MDV computes the joint upper bound of "n and j both
    filled", while under strict semantics a single declaration's marginal gain is provably 0
    across all three axes for the whole repo.

    Corrected criterion: the constraint is a **minimal viable homogeneous set** — K=1 impossible,
    K=2 suffices.

    Why it must be gated (this layer's specific failure mode): this artifact is fully
    self-consistent (count conservation, profile sums agree), but its error **does not appear as
    a numeric anomaly, it appears as a semantic-label error** — i.e. "calling the candidate
    feasible set a guaranteed feasible set". Arithmetic guards cannot catch this kind of error.
    So this gate additionally guards three things:
        ① The K=1 impossibility argument must be present (method.k1_impossible deleted ⇒ red);
        ② MDV's 16 candidate targets must all fall inside this layer's feasible set
           (cross-layer invariant);
        ③ The optimistic upper-bound disclaimer must be present (honest_limits contains the
           optimism note).
    """
    run_sub('Cohort 生成（fail-fast 守恒守卫）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_cohort_feasibility.py')])
    p = os.path.join(ROOT, 'api', 'cohort_feasibility.json')
    if not os.path.exists(p):
        bad('Cohort 产物', 'api/cohort_feasibility.json missing')
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
           'K=%s viable pairs %s homogeneous %s (%s%%) involving %s nodes; MDV reconciled %s/%s'
           % (s.get('min_viable_k'), s.get('viable_pairs_k2'),
              s.get('homogeneous_viable_pairs'), s.get('homogeneous_share_pct'),
              s.get('nodes_in_any_viable_cohort'),
              rc.get('landed_in_viable_cohort'), rc.get('mdv_single_declaration_targets')))

    # Cross-layer invariant: MDV's candidate targets must all fall inside the cohort feasible set.
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
                'MDV candidate targets %d not all inside cohort feasible set: %s — layers diverge'
                % (len(missing), missing[:5]))
        else:
            ok('Cohort 跨层不变量',
               'all %d MDV candidate targets fall inside the cohort feasible set' % len(mdv_ids))

    # The optimistic upper-bound disclaimer must be present (this layer's biggest semantic risk
    # is presenting the upper bound as a guarantee).
    hl = ' '.join((cf.get('meta', {}).get('honest_limits') or []))
    # Keep: this literal must match Chinese text that remains in the JSON per project policy.
    if '上界' not in hl or '⊆' not in hl:
        bad('Cohort 语义守卫', 'honest_limits missing optimistic upper-bound disclaimer '
                               '(actual feasible set ⊆ this table)')
    else:
        ok('Cohort 语义守卫', 'optimistic upper-bound disclaimer present')


def _elec_token(label):
    """Connector label → port-type token in the morphology graph (must share the same source as
    build_morphology_graph._slug).

    2026-10-04 lesson: the gate originally used "whitespace-stripped uppercase substring
    containment" to match label and type, which **inevitably mismatched when the label contained
    CJK** — `_slug` only keeps [a-z0-9], so the two Chinese characters in
    "OnRobot tool I/O + Ethernet (UR tool connector 兼容)" were dropped entirely, and the gate
    reported "not landed" while the wiring was actually correct.

    This is the same shape as the 2026-10-03 lesson: **the criterion must reuse the production
    code's normalization function**; writing a second approximate implementation inside the gate
    will inevitably diverge on some input.
    """
    return 'ELEC:CONNECTOR:' + re.sub(r'[^a-z0-9]+', '-', str(label).lower()).strip('-').upper()


def gate_electrical_wiring():
    """Electrical forensic layer → morphology graph **wiring completeness** gate.

    2026-10-03 gated. This gate guards a failure that **already really happened**:

    The forensic layer dropped 4 first-hand-verified connectors (6 records); the artifact was
    fully self-consistent, fields complete, gate all green — but `build_morphology_graph.py`
    **never reads it**. Entities still hung `ELEC:UNKNOWN`, and the decidable-pair count
    **did not change at all**. "Artifact on disk but criterion layer not wired" is a half-wired
    fault: both sides are individually correct, joined they do nothing.

    After the first wiring attempt it hit a second layer: the forensic layer used a **local id**
    (SENS-852) as key, while the entity side's stable key is **rp_id** (RP-SEN-0091) ⇒ still
    zero matches. Two layers of fault叠加, identical symptom: **looks fixed but doesn't take
    effect.**

    So this gate does not look at "was the wiring code written" (that is form); it only verifies
    **behavior**:
      ① Every forensic-layer record must find a node in the morphology graph holding the
         corresponding ELEC port;
      ② The morphology graph must contain a port type constructed from the forensic-layer token;
      ③ The electrical-axis decidable pair count must be ≥ 1 (otherwise wiring equals no wiring);
      ④ The forensic layer's keys must all be rp_id-shaped.
    """
    ep = os.path.join(ROOT, 'api', 'electrical_evidence.json')
    gp = os.path.join(ROOT, 'api', 'morphology_graph.json')
    cp = os.path.join(ROOT, 'api', 'compose_semantics.json')
    for p in (ep, gp, cp):
        if not os.path.exists(p):
            bad('电气接线完整性', 'artifact missing: %s' % os.path.basename(p))
            return
    ee = json.load(open(ep, encoding='utf-8'))
    mg = json.load(open(gp, encoding='utf-8'))
    cs = json.load(open(cp, encoding='utf-8'))
    ents = json.load(open(os.path.join(ROOT, 'api', 'entities.json'), encoding='utf-8'))

    # rp_id -> entity id list (one rp_id should theoretically map to only one entity —
    # rp_id uniqueness is guarded by schema_contract; here we still process as a list,
    # preferring to turn "unexpected duplicate" red rather than silently accepting only the
    # first).
    id_by_rp: dict = {}
    for e in ents.get('entities') or []:
        if e.get('rp_id'):
            id_by_rp.setdefault(e['rp_id'], []).append(e['id'])

    errs = []
    evidence = ee.get('evidence') or {}
    # ④ Keys must be rp_id-shaped (a local id matches nothing).
    for k in evidence:
        if not re.match(r'^RP-[A-Z]+-\d{3,}$', k):
            errs.append('forensic-layer key %r is not rp_id-shaped (local id cannot connect)' % k)

    # ①② Every record must land in the morphology graph.
    nodes = {n['id']: n for n in (mg.get('nodes') or []) if n.get('composable', True)}
    elec_tokens = {t['id'] for t in (mg.get('port_types') or [])
                  if t.get('axis') == 'electrical' and t.get('class') == 'registered_connector'}
    landed, unlanded = 0, []
    for rp, ev in evidence.items():
        targets = sorted(n for n in (id_by_rp.get(rp) or []) if n in nodes)
        if not targets:
            unlanded.append('%s (entity not in graph)' % rp)
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
        errs.append('forensic layer has %d rp_ids not fully landed in morphology graph: %s'
                    % (len(unlanded), unlanded[:4]))
    if not (elec_tokens & {'ELEC:UNKNOWN'} == elec_tokens) and not elec_tokens:
        errs.append('morphology graph has no electrical registered_connector type')

    # ③ Behavior verification: electrical-axis decidable pair count must be ≥1.
    elec_pairs = ((cs.get('aggregates') or {}).get('axis_marginals') or {}) \
        .get('electrical', {}).get('compatible', 0)
    if elec_pairs < 1:
        errs.append('electrical-axis decidable pairs = %d (wiring not effective or no decidable '
                    'electrical pair exists)' % elec_pairs)

    if errs:
        bad('电气接线完整性', '；'.join(errs[:4]))
    else:
        ok('电气接线完整性',
           'forensic %d records all landed in morphology graph; %d electrical '
           'registered_connector types; %d electrical-axis decidable pairs'
           % (landed, len(elec_tokens), elec_pairs))

    # Mutation detection: swap the forensic layer for empty (simulating "forgot to wire") must
    # turn red.
    empty = dict(ee)
    empty['evidence'] = {}
    if _wiring_errors(empty, mg, cs, id_by_rp) == []:
        bad('电气接线判据自证', 'mutation "evidence layer cleared" did not turn red — '
                               'this gate is decorative')
    else:
        ok('电气接线判据自证·取证层清空 ⇒ 红')


def _wiring_errors(ee, mg, cs, id_by_rp):
    """Wiring-completeness criterion (pure function, shared by the gate and the mutation
    self-proof)."""
    errs = []
    evidence = ee.get('evidence') or {}
    for k in evidence:
        if not re.match(r'^RP-[A-Z]+-\d{3,}$', k):
            errs.append('key not rp_id-shaped: %r' % k)
    if not evidence:
        errs.append('forensic layer empty')
        return errs
    nodes = {n['id']: n for n in (mg.get('nodes') or []) if n.get('composable', True)}
    for rp, ev in evidence.items():
        targets = sorted(n for n in (id_by_rp.get(rp) or []) if n in nodes)
        if not targets:
            errs.append('%s not landed (entity not in composable nodes)' % rp)
            continue
        want = {_elec_token(c.get('label') or c.get('id'))
                for c in ev.get('connectors') or []}
        for nid in targets:
            have = {p['type'] for p in (nodes[nid].get('ports') or [])
                    if p['type'].startswith('ELEC:')}
            if not (want & have):
                errs.append('%s/%s no electrical port (want %s / have %s)'
                            % (rp, nid, sorted(want), sorted(have)))
    elec_pairs = ((cs.get('aggregates') or {}).get('axis_marginals') or {}) \
        .get('electrical', {}).get('compatible', 0)
    if elec_pairs < 1:
        errs.append('electrical-axis decidable pairs = %d' % elec_pairs)
    return errs


def gate_reachability_gap():
    """Research-layer ↔ product-surface reachability gate (2026-10-04 added).

    The most severe structural problem found in the health check: this project has **two
    compatibility-ruling engines** —
      product surface functions/_lib/compat_engine.js: four dimensions
        protocol/electrical/mechanical/software, reads entities.json declaration fields
      research layer scripts/compose_engine.py: three axes
        mechanical/electrical/signal, reads morphology_graph ports + type_compat
    The two dimension sets are **not subsets of each other** (product has protocol/software,
    research has signal). And the research layer's 5 artifacts previously had **zero references**
    on the product surface — i.e. "the researcher thought the conclusion was used, but the agent
    actually got an answer on a different convention".

    The nature of this fault: **both engines run, neither errors, gates all green**, only the
    research asset is invisible to the user. No arithmetic guard catches it; only **explicit
    reference scanning** does.

    This gate guards three things:
      ① Every research-layer artifact is referenced at least once under functions/ (reachable)
      ② The bridge tool explain_compose_frontier must exist in the endpoint's TOOLS
         (the bridge layer is the only path for "research layer becomes agent-accessible")
      ③ Both engines' dimension sets must be **explicitly registered** in the artifact —
         if JS or Py's dimension set changes one day and this layer doesn't keep up, it must
         turn red. Reason: the dimension set is the criterion for "whether the two conventions
         are still subsets of each other"; when it changes the fault nature changes, and nobody
         notifies the gate.
    """
    run_sub('可达性体检生成（fail-fast 口径守恒）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_reachability_gap.py')])
    p = os.path.join(ROOT, 'api', 'reachability_gap.json')
    if not os.path.exists(p):
        bad('可达性产物', 'api/reachability_gap.json missing')
        return
    with open(p, encoding='utf-8') as f:
        rg = json.load(f)
    errs = _reachability_errors(rg)
    if errs:
        bad('研究层可达性', '；'.join(errs[:4]))
    else:
        rs = rg['reachability_summary']
        ok('研究层可达性',
           '%d/%d artifacts reachable on product surface (scanned %d source files); '
           'bridge tool present; dimension sets registered'
           % (rs['artifacts_reachable'], rs['artifacts_total'],
              rs['product_surface_files_scanned']))

    # The bridge tool must really exist in the endpoint's TOOLS (not just claimed by this layer).
    mp = os.path.join(ROOT, 'functions', 'mcp.js')
    if os.path.exists(mp):
        src = open(mp, encoding='utf-8', errors='replace').read()
        if "name: 'explain_compose_frontier'" not in src:
            bad('桥接工具接线', 'explain_compose_frontier not in functions/mcp.js TOOLS — '
                                'research layer still invisible to agent')
        elif "name === 'explain_compose_frontier'" not in src:
            bad('桥接工具接线', 'tool declared but dispatch branch missing (cannot be called)')
        else:
            ok('桥接工具接线', 'TOOLS declared + dispatch branch both present')

    run_sub('可达性阴阳/变异自证（引用+桥接+维度守卫）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'verify_reachability_gap.py')],
            timeout=600)


def _reachability_errors(rg):
    """Pure-function criterion for the reachability artifact."""
    errs = []
    rs = rg.get('reachability_summary') or {}
    if not rs.get('product_surface_files_scanned'):
        errs.append('product-surface scanned-file count is 0 — scan scope invalid '
                    '(reachability would falsely report all-pass)')
    total = rs.get('artifacts_total') or 0
    reach = rs.get('artifacts_reachable') or 0
    unreach = rs.get('artifacts_unreachable') or 0
    if reach + unreach != total:
        errs.append('reachability count not conserved: %d + %d != %d' % (reach, unreach, total))
    # Per entry: reachable must agree with reference_count (prevent the two conventions from
    # diverging).
    for r in (rg.get('reachability') or []):
        if bool(r.get('reachable')) != bool(r.get('reference_count')):
            errs.append('%s reachable inconsistent with reference_count' % r.get('artifact'))
    # **Unreachable must turn red** (added 2026-10-04). This looks like a self-deceiving gate
    # that "checks again whether I said I did it", but its other face is the key: **when a
    # reachable artifact becomes unreachable it must immediately turn red**. Previously it only
    # checked internal consistency, so the worst state "all 5 artifacts unreachable" was
    # self-consistent and judged green. The bridge layer is the only path for the research layer
    # to be visible to the agent, so **every research-layer artifact must be reachable** (uniformly
    # relayed by the bridge tool in mcp.js), otherwise the research asset becomes "computed but
    # nobody can see it" again.
    for r in (rg.get('reachability') or []):
        if not r.get('reachable'):
            errs.append('%s has zero references on product surface — research conclusion '
                        'invisible to agent/user. This layer registered %d artifacts that '
                        'must all be reachable (bridge tool is the uniform entry)'
                        % (r.get('artifact'), total))
    # Dimension sets must be registered (fault-nature criterion).
    tax = rg.get('taxonomy') or {}
    for k in ('shared_dimensions', 'product_only_dimensions', 'research_only_axes'):
        if k not in tax:
            errs.append('taxonomy missing %s (dimension set unregistered, fault-nature change '
                        'will go undetected)' % k)
    if not (rg.get('decision_options') or []):
        errs.append('decision_options empty — fault quantified but nowhere to discuss, '
                    'will be read as "already fixed" while actually unhandled')
    # Both engine fingerprints must resolve.
    fps = rg.get('engine_fingerprints') or {}
    for eng, key in (('product_js', 'dimensions'), ('research_py', 'axes')):
        if not (fps.get(eng) or {}).get(key):
            errs.append('%s %s resolved empty — engine structure may have changed' % (eng, key))
    return errs


def gate_open_vla_and_behavior():
    """Binding layer + behavior layer gate (2026-10-05 added).

    Guards three things prone to over-claiming:
      ① Binding only points to **real existing** entities, and **only binds open-source VLA**
         — fabricating hardware bindings for closed source would pollute data_quality
      ② Binding strength is **cross-field self-consistent**: `validated` must have a concrete
         ontology (only checking strength is in the allowed set ⇒ changing to validated still
         passes the gate)
      ③ Behavior evidence **must have a control group**, **sim/real strictly separated**,
         first-hand source — a single piece of evidence may be cherry-picked; simulation
         impersonating real hardware is over-claiming

    Also runs verify_open_vla_and_behavior.py's yin-yang + 9 mutations.
    """
    run_sub('开源 VLA 绑定（fail-fast 实体存在性 + 出处修正）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_open_vla_binding.py')])
    run_sub('行为证据层（fail-fast 对照组 + sim/real 分列）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_behavior_evidence.py')])
    run_sub('provenance 重建（层状态现读行为证据，防链/层口径分叉）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_provenance.py')])
    p_ov = os.path.join(ROOT, 'api', 'open_vla_binding.json')
    p_bh = os.path.join(ROOT, 'api', 'behavior_evidence.json')
    for p in (p_ov, p_bh):
        if not os.path.exists(p):
            bad('绑定/行为产物', '%s missing' % os.path.basename(p))
            return
    with open(p_ov, encoding='utf-8') as f:
        ov = json.load(f)
    with open(p_bh, encoding='utf-8') as f:
        bh = json.load(f)
    ents = {}
    ep = os.path.join(ROOT, 'api', 'entities.json')
    if os.path.exists(ep):
        with open(ep, encoding='utf-8') as f:
            ents = json.load(f)
    rm = {}
    rp = os.path.join(ROOT, 'api', 'robot_ai_models.json')
    if os.path.exists(rp):
        with open(rp, encoding='utf-8') as f:
            rm = json.load(f)
    errs = _open_vla_errors(ov, bh, ents, rm)
    if errs:
        bad('绑定/行为层', '；'.join(errs[:4]))
    else:
        s1, s2 = ov['summary'], bh['summary']
        ok('开源VLA绑定 + 行为证据',
           'bound %d | blocked %d | search-link residue %d | behavior %d records '
           '(real with value %d / sim %d / null %d)'
           % (s1['bound_now'], s1['bound_blocked_missing_body'],
              s1['source_url_still_search_link'], s2['records'],
              s2['real_with_value'], s2['sim_records'], s2['null_value_records']))
    # Cross-layer invariant: behavior layer state must agree with the chain's L4 criterion.
    pp = os.path.join(ROOT, 'api', 'provenance.json')
    if os.path.exists(pp) and bh.get('summary', {}).get('records'):
        with open(pp, encoding='utf-8') as f:
            pv = json.load(f)
        li = (pv.get('layer_inventory') or {}).get('behavior') or {}
        l4 = next((l for l in (pv.get('chains') or [{}])[0].get('links', [])
                   if l.get('from') == 'policy'), None)
        if li.get('available') == 'declared_empty' and l4 and l4.get('satisfied'):
            bad('链/层口径一致', 'behavior layer declared empty but policy→behavior criterion '
                                'satisfied — **chain says yes, layer says no** (measured in '
                                'practice: layer state was once hard-coded instead of read live)')
        else:
            ok('链/层口径一致', 'behavior layer available=%s, policy→behavior satisfied=%s'
               % (li.get('available'), (l4 or {}).get('satisfied')))
    run_sub('绑定/行为自证（阴阳 + 9 变异 + 跨字段自洽 + sim/real 现算）',
            [sys.executable, os.path.join(ROOT, 'scripts',
                                          'verify_open_vla_and_behavior.py')],
            timeout=600)


def _open_vla_errors(ov, bh, ents, rm):
    import importlib
    try:
        v = importlib.import_module('verify_open_vla_and_behavior')
    except ImportError:
        return ['verify_open_vla_and_behavior cannot be imported — criterion lost self-proof']
    return v._errors(ov, bh, ents, rm)


def gate_co_mount():
    """Co-mount relation gate (2026-10-05 added) — guard the "third relation type" against
    silent regression.

    This project previously had only **one** relation: peer-to-peer (two-segment mutual insert).
    The health check found that the real engineering relation of cobot EOAT is **co-mount**
    (three-segment A↔host↔B); the two relations are not inter-convertible ⇒ manifests as
    "composed always 0".

    This gate guards four things:
      ① The relation type must self-describe as three-segment
         (`structure=three_segment_via_host`) — a field-by-field criterion, not the vacuous
         guard of "is 'host' anywhere in the text"
      ② The `port_exhausted` state must be present — it is the **unique** engineering
         constraint of co-mount; missing it degrades to a two-segment relation
      ③ Host-side first-hand forensics complete (tool_flange must be a morphology-graph port
         type id, not free text; tool_io_ports must register a reason when not forensically
         collected)
      ④ **Convention guard**: must self-describe unmodeled scope, port gaps, decision
         granularity upper bound, and must not rewrite compose_semantics's composed
         — **an over-claimed diagnosis is worse than no diagnosis**
    Also runs verify_co_mount.py's yin-yang + 11 mutations + engine-behavior verification.
    """
    run_sub('共装层生成（fail-fast 宿主取证校验 + 字段口径守恒）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_co_mount.py')])
    p_cm = os.path.join(ROOT, 'api', 'co_mount.json')
    p_ts = os.path.join(ROOT, 'api', 'robot_tool_side.json')
    for p in (p_cm, p_ts):
        if not os.path.exists(p):
            bad('共装产物', '%s missing' % os.path.basename(p))
            return
    with open(p_cm, encoding='utf-8') as f:
        cm = json.load(f)
    with open(p_ts, encoding='utf-8') as f:
        ts = json.load(f)
    errs = _co_mount_errors(cm, ts)
    if errs:
        bad('共装关系', '；'.join(errs[:4]))
    else:
        s = cm['summary']
        ok('共装关系（三段 A↔宿主↔B）',
           'hosts %d | devices %d | single-mount %s | pair-verdict %s'
           % (s['hosts'], s['devices'], s['single_mount'],
              s['pair_verdict_histogram']))
    run_sub('共装自证（阴阳 + 引擎行为 + 11 变异 + 口径守卫）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'verify_co_mount.py')],
            timeout=600)


def _co_mount_errors(cm, ts):
    """Co-mount layer criterion (reuses verify_co_mount._errors, same source to avoid two
    implementations drifting)."""
    import importlib
    try:
        v = importlib.import_module('verify_co_mount')
    except ImportError:
        v = None
    if v is not None:
        return v._errors(cm, ts)
    return ['verify_co_mount cannot be imported — co-mount criterion lost self-proof']


def gate_research_progress():
    """Core-goal completion criterion gate (2026-10-04 added).

    "What percent is done" is the sentence in this project most prone to **self-deception**:
    items can be cherry-picked, weights tweaked, conventions mixed, so reporting 60% looks fine.

    This gate guards three things:
      ① Every sub-item must carry a `caliber` (how the numerator/denominator is computed) —
         a percentage without a convention is not reproducible and does not deserve the name
         "completion".
      ② Weights must be **questionable**: top-level `weight_rationale` + `honest_limits`
         declare "weighting is a convention, not an objective measurement" + both conventions
         reported.
      ③ **Gating must be live-computed** (key): `raw_dimension_scores` must equal the
         live-computed result of "core criterion 0 ⇒ that dimension scored 0".
         Without this, the gating could be swapped for a naive value inflating it (body from 0%
         to 19.5%) without turning red.

    Why gating matters: in body's 4-term arithmetic mean, composed (the **only direct criterion**
    of the core goal) is only 1/4 of the effective weight. Three infrastructure high scores
    average out composed's zero. That is not a weighting problem; it is **sub-item averaging
    masking the core criterion**.

    Also runs `verify_research_progress.py`'s **sensitivity reverse control**: after raising
    composed from 0, completion **must** rise — a completion metric insensitive to the core goal
    is useless no matter how many times it is tested.
    """
    run_sub('完成度判据生成（fail-fast 口径守恒）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_research_progress.py')])
    p = os.path.join(ROOT, 'api', 'research_progress.json')
    if not os.path.exists(p):
        bad('完成度产物', 'api/research_progress.json missing')
        return
    with open(p, encoding='utf-8') as f:
        rp = json.load(f)
    errs = _progress_errors(rp)
    if errs:
        bad('完成度判据', '；'.join(errs[:4]))
    else:
        sc = rp.get('scoring') or {}
        naive_w = _naive_weighted(rp)
        ok('完成度判据',
           'gated %.1f%% (naive %.1f%%) | body %s→%s (gated %s)'
           % (rp.get('weighted_total_pct', 0), naive_w,
              (sc.get('naive_dimension_scores') or {}).get('body'),
              (sc.get('gated_dimension_scores') or {}).get('body'),
              next((v for v in (sc.get('gate_explanation') or {}).values()
                    # startswith rather than in: "gating **not effective**" contains the
                    # substring "gating effective", so `in` would misjudge not-effective as
                    # effective (same defect as verify, fixed together)
                    if str(v).lstrip().startswith('门控生效')), 'no gating')[:40]))
    run_sub('完成度自证（口径 + 权重可质疑 + 门控现算 + 敏感性 + 8 变异）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'verify_research_progress.py')],
            timeout=600)


def _naive_weighted(rp):
    w = rp.get('weights') or {}
    naive = (rp.get('scoring') or {}).get('naive_dimension_scores') or {}
    if not (w and naive):
        return 0.0
    return round(sum(naive[k] * w[k] for k in w if k in naive), 1)


def _progress_errors(rp):
    """Pure-function criterion for the completion criterion (same source as verify_*.py)."""
    import importlib
    try:
        vrp = importlib.import_module('verify_research_progress')
    except ImportError:
        vrp = None
    if vrp is not None:
        return vrp._errors(rp)
    # Degraded path: when the module cannot be imported, at least guard weighted live-compute
    # consistency.
    errs = []
    w = rp.get('weights') or {}
    raw = rp.get('raw_dimension_scores') or {}
    total = rp.get('weighted_total_pct')
    if w and raw and isinstance(total, (int, float)):
        rec = round(sum(raw[k] * w[k] for k in w if k in raw), 1)
        if abs(rec - total) > 0.15:
            errs.append('weighted value %s != live-computed %s' % (total, rec))
    return errs


def _cohort_errors(cf):
    """Pure-function criterion for cohort_feasibility artifacts."""
    errs = []
    s = cf.get('summary') or {}
    n = s.get('nodes_evaluated')
    if not isinstance(n, int) or n <= 0:
        return ['nodes_evaluated invalid: %r' % (n,)]
    total = n * (n - 1) // 2
    v = s.get('viable_pairs_k2')
    h = s.get('homogeneous_viable_pairs')
    if not isinstance(v, int) or not isinstance(h, int):
        return ['viable pair count non-integer: viable=%r homogeneous=%r' % (v, h)]
    if h > v:
        errs.append('homogeneous set %d > viable set %d' % (h, v))
    if v > total:
        errs.append('viable pairs %d > C(n,2) %d' % (v, total))
    if s.get('min_viable_k') != 2:
        errs.append('min_viable_k should be 2, got %r' % (s.get('min_viable_k'),))
    if (s.get('k1_status') or '').startswith('possible'):
        errs.append('k1_status claims K=1 feasible, contradicting method.k1_impossible')
    if 'k1_impossible' not in (cf.get('method') or {}):
        errs.append('K=1 impossibility argument missing')
    prof = cf.get('gap_profiles') or []
    psum = sum(p.get('viable_pairs', 0) for p in prof)
    if psum != h:
        errs.append('gap-profile sum %d != homogeneous viable pairs %d' % (psum, h))
    for p in prof:
        if p.get('nodes_involved', 0) > n:
            errs.append('profile %r node count %d overflows whole-repo %d'
                        % (p.get('missing_axes'), p['nodes_involved'], n))
    rc = cf.get('mdv_reconciliation')
    if rc and rc.get('mdv_single_declaration_targets'):
        if rc.get('landed_in_viable_cohort') != rc['mdv_single_declaration_targets']:
            errs.append('MDV cross-layer reconciliation inconsistent: %r/%r'
                        % (rc.get('landed_in_viable_cohort'),
                           rc['mdv_single_declaration_targets']))
    return errs


def gate_electrical_evidence():
    """Electrical-interface forensic gate — the landing artifact of MDV-directed forensics.

    2026-10-03 gated. This layer is the actual execution record of "the forensics direction
    computed by MDV/cohort"; its most dangerous failure mode is **looks sourced but is actually
    inferred**: once an electrical connector's pinout is guessed wrong, an engineer wiring to it
    burns parts — that is a personal-safety and equipment risk, not a data-quality problem. So
    this gate turns "must have first-hand source" into a hard constraint.

    Triple control:
      ① Builder _validate() forces: every piece of evidence must have source_url + source_tier
         + vendor;
      ② M8 family conflict table self-consistent: variants of the same family must truly differ
         in pin count, otherwise the "physically not inter-insertable" conclusion has no
         geometric basis;
      ③ Mutation detection: delete source_url / change tier / wipe conflict table / wipe honest
         gap declaration, the gate must turn red one by one.
    """
    run_sub('电气取证生成（fail-fast 一手出处强制）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_electrical_evidence.py')])
    p = os.path.join(ROOT, 'api', 'electrical_evidence.json')
    if not os.path.exists(p):
        bad('电气取证产物', 'api/electrical_evidence.json missing')
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
           '%d devices / %d connectors all have first-hand source; covers MDV target %s/16; '
           '%d M8 family conflict groups'
           % (len(ee.get('evidence') or {}), n_conn,
              cf.get('evidenced_now'), len(ee.get('family_conflicts') or [])))

    # Semantic guard: honest gaps (pinout null) must be explicitly registered as evidence_gap,
    # not quietly left blank — "don't know" must be visible to the agent, otherwise it gets
    # misread as "no pinout requirement".
    gaps = 0
    for nid, ev in (ee.get('evidence') or {}).items():
        for c in ev.get('connectors') or []:
            if c.get('pinout') is None:
                if not c.get('evidence_gap'):
                    bad('电气取证诚实缺口',
                        '%s/%s pinout is null but evidence_gap not registered — '
                        '"don\'t know" must be explicitly visible, otherwise misread as '
                        '"no pinout requirement"'
                        % (nid, c.get('id')))
                else:
                    gaps += 1
    if gaps:
        ok('电气取证诚实缺口', '%d pinout-unknown explicitly registered as evidence_gap' % gaps)

    # Mutation detection (in-memory injection, no disk change — ci_gate runs the builder first,
    # which washes away file-level tampering).
    for tag, mutate in (
            ('remove first-hand source',
             lambda d: d['evidence'].pop('RP-SEN-0091')),
            ('downgrade source tier to illegal value',
             lambda d: d['evidence']['RP-GRI-0002'].update({'source_tier': 'X'})),
            ('erase M8 family conflict table',
             lambda d: d.update({'family_conflicts': []})),
            # The mutation target must hit a **truly incompatible table** and flatten **all**
            # geometric dimensions. 2026-10-04 fix: the original mutation only set all M8 table
            # pins to 6. After the criterion that day expanded to "compare all geometric
            # dimensions", thread/variant still differed ⇒ no longer broke ⇒ false alarm.
            # Lesson (recorded in SKILL): **the mutant itself must be verified to actually hit
            # the breach**.
            ('conflict table incompatible verdict loses geometric basis (thread/pins/variant/'
             'protocol flattened)',
             lambda d: [v.update({'pins': 5, 'thread': 'M8', 'variant': 'x', 'protocol': 'x'})
                        for v in [t for t in d['family_conflicts']
                                  if t['verdict'].startswith('incompatible')][0]['variants']]),
            ('conflict table identity case altered to differ (self-contradictory)',
             lambda d: [t for t in d['family_conflicts']
                        if t['verdict'].startswith('identity')][0]['variants'][0]
             .update({'thread': 'M8'})),
            ('erase honest-gap registration',
             lambda d: d['evidence']['RP-SEN-0054']['connectors'][0].pop('evidence_gap', None)),
    ):
        mut = json.loads(json.dumps(ee))
        try:
            mutate(mut)
        except (KeyError, IndexError):
            fail_msg = ('mutation "%s" could not be injected — criterion source structure '
                        'changed, gate needs update' % tag)
            bad('电气取证判据自证', fail_msg)
            continue
        if _electrical_evidence_errors(mut) == [] and not _has_gap_violation(mut):
            bad('电气取证判据自证', 'mutation "%s" did not turn red — this gate is decorative' % tag)
        else:
            ok('电气取证判据自证·%s ⇒ 红' % tag)


def _has_gap_violation(ee):
    """pinout is null but evidence_gap not registered ⇒ honest gap swallowed."""
    for ev in (ee.get('evidence') or {}).values():
        for c in ev.get('connectors') or []:
            if c.get('pinout') is None and not c.get('evidence_gap'):
                return True
    return False


def gate_compose_frontier():
    """Co-mount frontier gate — turn "composed=0" from a failure narrative into a reproducible
    diagnosis.

    2026-10-04 gated. This layer answers a question the whole project had never answered before:
    **is composed=0 a data gap or a semantic truth?**

    Measured conclusion (L1/L2/L3 three-level decomposition):
      L1 cross-role (signal necessary condition)      = 393 nodes
      L2 L1 ∩ mechanical-decidable                     = 63 pairs / 16 nodes
        of which mechanical 63/63 pass, signal 63/63 pass
      L3 L2 ∩ electrical compatible                    = 0 pairs  ← composed
    The only blocker: electrical judges "can the two devices **inter-insert**", and these 16
    nodes are all cobot EOAT (gripper + six-axis force sensor, sharing one A50 flange); each
    occupies one robot-side interface — **by design they should not inter-insert**.

    Why it must be gated (this layer's specific failure mode): it outputs a **diagnostic
    conclusion**; the danger is not miscalculation but **over-claiming** — it reads like a
    theorem yet is supported by only a few samples. So the gate additionally guards a
    **convention guard**:
        · statement must start with "【强假说"  (strong hypothesis)
        · headline must contain "不是已证定理"  (not a proven theorem)
        · no assertion wording without negation
        · sample_caveat must be present
    The mutation "change hypothesis into assertion" must turn red. **An over-claimed diagnosis
    is worse than no diagnosis.**
    """
    run_sub('共装前沿生成（fail-fast 层级守恒）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'build_compose_frontier.py')])
    p = os.path.join(ROOT, 'api', 'compose_frontier.json')
    if not os.path.exists(p):
        bad('共装前沿产物', 'api/compose_frontier.json missing')
        return
    with open(p, encoding='utf-8') as f:
        cf = json.load(f)
    errs = _frontier_errors(cf)
    if errs:
        bad('共装前沿层级口径', '；'.join(errs[:4]))
    else:
        s = cf['summary']
        es = cf['co_mount_theorem']['empirical_support']
        ok('共装前沿层级口径',
           'L1=%s/%s nodes L2=%s pairs/%s nodes L3=%s | both-side forensics %s pairs, judged %s'
           % (s['l1_pairs'], s['l1_cross_role_nodes'], s['l2_pairs'],
              s['l2_nodes'], s['l3_pairs'],
              es['both_sides_evidenced_pairs'],
              dict(es['electrical_verdict_histogram'])))

    # Cross-layer invariant: L3 must agree in convention with compose_semantics.composed.
    cp = os.path.join(ROOT, 'api', 'compose_semantics.json')
    if os.path.exists(cp):
        with open(cp, encoding='utf-8') as f:
            cs = json.load(f)
        composed = (cs.get('aggregates') or {}).get('overall_counts', {}).get('composed', 0)
        l3 = cf['summary']['l3_pairs']
        if composed == 0 and l3 == 0:
            ok('共装前沿跨层不变量', 'compose composed=0 agrees with frontier L3=0 convention')
        elif composed > 0 and l3 * 2 == composed:
            ok('共装前沿跨层不变量',
               'compose composed=%d == L3(%d)×2 (symmetric expansion)' % (composed, l3))
        else:
            bad('共装前沿跨层不变量',
                'compose composed=%d (n² directed) vs frontier L3=%d (C(n,2) unordered) '
                'convention diverges' % (composed, l3))

    run_sub('共装前沿阴阳/变异自证（层级 + 口径守卫 + 7 变异 + 跨层对账）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'verify_compose_frontier.py')],
            timeout=600)


def _frontier_errors(cf):
    """Pure-function criterion for the co-mount frontier: level monotonicity + convention
    guard."""
    errs = []
    s = cf.get('summary') or {}
    l1, l2, l3 = s.get('l1_pairs'), s.get('l2_pairs'), s.get('l3_pairs')
    for name, v in (('l1', l1), ('l2', l2), ('l3', l3)):
        if not isinstance(v, int) or v < 0:
            return ['%s_pairs invalid: %r' % (name, v)]
    if not (l1 >= l2 >= l3):
        errs.append('levels not monotonic L1=%d L2=%d L3=%d' % (l1, l2, l3))
    if (s.get('l2_signal_histogram') or {}).get('compatible', 0) != l2:
        errs.append('L2 signal not all compatible (%s)' % s.get('l2_signal_histogram'))
    if s.get('l2_nodes', 0) > s.get('l1_cross_role_nodes', 0):
        errs.append('l2_nodes %s > l1_cross_role_nodes %s'
                    % (s.get('l2_nodes'), s.get('l1_cross_role_nodes')))
    if len(cf.get('frontier_nodes') or []) != s.get('l2_nodes'):
        errs.append('frontier_nodes %d != l2_nodes %s'
                    % (len(cf.get('frontier_nodes') or []), s.get('l2_nodes')))
    if not (s.get('co_mount_flange_profile') or {}):
        errs.append('flange profile empty')
    # Convention guard.
    thm = cf.get('co_mount_theorem') or {}
    stmt = thm.get('statement') or ''
    head = (cf.get('meta') or {}).get('headline') or ''
    # Keep: literal must match Chinese text that remains in the JSON per project policy.
    if not stmt.lstrip().startswith('【强假说'):
        errs.append('statement does not start with "【强假说" (over-claimed wording)')
    # Keep: literal must match Chinese text that remains in the JSON per project policy.
    if '不是已证定理' not in head:
        errs.append('headline lacks the "不是已证定理" qualifier')
    if 'sample_caveat' not in json.dumps(thm, ensure_ascii=False):
        errs.append('missing sample_caveat (sample-size limit not registered)')
    hl = ' '.join((cf.get('meta') or {}).get('honest_limits') or [])
    # Keep: literals must match Chinese text that remains in the JSON per project policy.
    for kw in ('不改', 'Tier B', '多年期'):
        if kw not in hl:
            errs.append('honest_limits missing a declaration related to "%s"' % kw)
    return errs


def _electrical_evidence_errors(ee):
    """Pure-function criterion for electrical forensics: source discipline + conflict-table
    geometric basis."""
    errs = []
    ev = ee.get('evidence')
    if not ev:
        return ['evidence empty — fail-closed, no first-hand source may land']
    for nid, e in ev.items():
        for field in ('vendor', 'device', 'source_url', 'source', 'source_tier', 'confidence'):
            if not e.get(field):
                errs.append('%s missing required field %s' % (nid, field))
        if e.get('source_tier') not in ('A', 'B', 'C'):
            errs.append('%s source_tier=%r invalid (only A/B/C allowed)'
                        % (nid, e.get('source_tier')))
        if not e.get('connectors'):
            errs.append('%s no connector records' % nid)
        for c in (e.get('connectors') or []):
            for field in ('id', 'label', 'family', 'carries', 'note'):
                if not c.get(field):
                    errs.append('%s/%s missing field %s' % (nid, c.get('id', '?'), field))
    # coverage.evidenced_now must equal the actual entry count — otherwise deleting an entry
    # goes unnoticed. Origin: the first version of this gate missed this; the mutation "delete
    # first-hand source" (pop one device) actually did not turn red — because the remaining 3
    # still satisfied "every entry has source", only "one fewer" nobody noticed. This is the
    # concrete shape of "a gate that only tests green paths is no gate": whether the assertion
    # is strong enough is judged by whether it catches "missing" rather than "wrong".
    cov = ee.get('coverage') or {}
    if cov.get('evidenced_now') != len(ev):
        errs.append('coverage.evidenced_now=%r != actual entry count %d (entry deleted or '
                    'count drifted)'
                    % (cov.get('evidenced_now'), len(ev)))
    n_conn = sum(len(e.get('connectors') or []) for e in ev.values())
    cov_conn = cov.get('connectors_recorded')
    if cov_conn is not None and cov_conn != n_conn:
        errs.append('coverage.connectors_recorded=%r != actual connector count %d'
                    % (cov_conn, n_conn))
    # Conflict table: every **blocking dimension the table declares** must truly differ.
    # 2026-10-04 expansion: the criterion was originally "pin counts must differ", refuted by two
    # new tables — SAME_PIN_COUNT_DIFFERENT_THREAD: pins **same**, blocking dimension is thread
    # (Robotiq 2F-85 = M8 5-pole vs FT 300 = M12 5-pin A-coded, same pins/order/signal, only
    # thread differs ⇒ not insertable); M12: a legal **identity** case (FT 300 and FT 300-S),
    # all dimensions same. The old criterion would also turn the legal identity red, forcing the
    # criterion to degrade into "same family always incompatible" — the opposite-direction
    # assumption. **The criterion must expand with the registered evidence, otherwise it starts
    # rejecting correct things.**
    cfs = ee.get('family_conflicts') or []
    if not cfs:
        errs.append('family_conflicts empty — no machine-readable evidence for the core '
                    'finding "M8 is a family not a type"')
    for cf in cfs:
        verdict = cf.get('verdict') or ''
        variants = cf.get('variants') or []
        if len(variants) < 2:
            errs.append('conflict table %s has fewer than 2 variants' % cf.get('family'))
            continue
        diffs = {d for d in ('pins', 'thread', 'family', 'variant', 'protocol')
                 if len({v.get(d) for v in variants}) > 1}
        if verdict.startswith('incompatible'):
            if not diffs:
                errs.append('conflict table %s judged incompatible but all geometric dimensions '
                            'are identical — conclusion lacks basis, no difference means no '
                            'reason not to insert'
                            % cf.get('family'))
        elif verdict.startswith('identity'):
            if diffs:
                errs.append('conflict table %s judged identity but geometric dimension %s differs '
                            '⇒ self-contradictory'
                            % (cf.get('family'), sorted(diffs)))
        else:
            errs.append('conflict table %s verdict %r not registered '
                        '(only incompatible_* / identity_* allowed)'
                        % (cf.get('family'), verdict))
    return errs


def _mdv_errors(ev):
    """Pure-function criterion for MDV artifacts (reused by the gate; no hand-written expected
    values, all reconciled against artifact self-consistency)."""
    errs = []
    s = ev.get('summary') or {}
    n = s.get('nodes_evaluated')
    if not isinstance(n, int) or n <= 0:
        return ['nodes_evaluated invalid: %r' % (n,)]
    total = n * (n - 1) // 2
    if s.get('total_pairs') != total:
        errs.append('total_pairs %r != C(n,2) %d' % (s.get('total_pairs'), total))
    per = s.get('per_axis_decidable_pairs') or {}
    for axis, cnt in per.items():
        if not isinstance(cnt, int) or cnt < 0 or cnt > total:
            errs.append('%s decidable pairs %r out of bounds [0,%d]' % (axis, cnt, total))
    conj = s.get('two_axis_conjunction') or {}
    for combo, cnt in conj.items():
        a, b = combo.split('+')
        if a in per and b in per and cnt > min(per[a], per[b]):
            errs.append('%s=%r exceeds single-axis upper bound' % (combo, cnt))
    if conj and s.get('three_axis_conjunction', 0) > min(conj.values()):
        errs.append('three-axis AND %r exceeds two-axis AND' % s.get('three_axis_conjunction'))
    # MDV count conservation + index completeness.
    by = ev.get('by_axis') or {}
    expect_idx = 0
    for axis, b in by.items():
        if b['positive_mdv_nodes'] + b['zero_mdv_nodes'] != b['undeclared_nodes']:
            errs.append('%s MDV count not conserved: %d+%d != %d'
                        % (axis, b['positive_mdv_nodes'], b['zero_mdv_nodes'],
                           b['undeclared_nodes']))
        expect_idx += b['undeclared_nodes']
        zero_claim = (b['verdict'] or '').startswith('provably_zero_mdv')
        actually = b['positive_mdv_nodes'] == 0 and b['undeclared_nodes'] > 0
        if zero_claim != actually:
            errs.append('%s zero-axis verdict %r contradicts measurement '
                        '(positive %d / undeclared %d)'
                        % (axis, b['verdict'], b['positive_mdv_nodes'],
                           b['undeclared_nodes']))
    if len(ev.get('entity_mdv_index') or {}) != expect_idx:
        errs.append('entity_mdv_index count %d != total undeclared %d'
                    % (len(ev.get('entity_mdv_index') or {}), expect_idx))
    return errs


def _gap_doc_errors(gc, ft, live_sig):
    """Gap-cause classification aggregation-convention criterion (pure function, shared by the
    gate and the mutation self-proof)."""
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
    # Completeness one: every repo entity must land in a bucket (three buckets exhaustive, no
    # entity silently vanishing).
    if (b.get('solved', 0) + b.get('na', 0) + og.get('open_gap_total', 0)
            != t.get('entities_total')):
        errs.append('classification incomplete: solved+na+open_gap=%r != entities_total %r'
                    % (b.get('solved', 0) + b.get('na', 0) + og.get('open_gap_total', 0),
                       t.get('entities_total')))
    # Completeness two: within the mechanical **applicable surface** the split is
    # declared/not_declared. na belongs to "not a decidable granularity" and is outside the
    # applicable surface; counting it in would always fail.
    if b.get('solved', 0) + og.get('open_gap_total', 0) != t.get('mech_applicable'):
        errs.append('applicable surface incomplete: solved+open_gap=%r != mech_applicable %r'
                    % (b.get('solved', 0) + og.get('open_gap_total', 0),
                       t.get('mech_applicable')))
    # Gap sub-breakdown must sum back to the gap total.
    sub = sum(og.get(k, 0) for k in ('proprietary_suspect', 'unpublished_suspect', 'ambiguous'))
    if sub != og.get('open_gap_total'):
        errs.append('gap sub-breakdown sum %r != open_gap_total %r'
                    % (sub, og.get('open_gap_total')))
    # Summary layer must not drift from per-category.
    pc = gc.get('per_category') or {}
    for key, expect in (('total', t.get('entities_total')),
                        ('solved', b.get('solved')), ('na', b.get('na')),
                        ('proprietary_suspect', og.get('proprietary_suspect')),
                        ('unpublished_suspect', og.get('unpublished_suspect')),
                        ('ambiguous', og.get('ambiguous'))):
        s = sum(v.get(key, 0) for v in pc.values())
        if s != expect:
            errs.append('per_category.%s sum %r != summary %r' % (key, s, expect))
    # signal_axis must agree with the morphology graph live-computed (prevent revert to hardcode).
    if live_sig is not None:
        sa = gc.get('signal_axis') or {}
        if sa.get('declared_signal_ports') != live_sig:
            errs.append('signal_axis.declared_signal_ports=%r != morphology graph live-computed %r'
                        % (sa.get('declared_signal_ports'), live_sig))
    return errs


def gate_positioning_caliber():
    """Positioning-convention gate — the local half of "what we externally claim about
    ourselves".

    2026-09-21 added. Background: this round converged the whole-site positioning from 6 sets to
    1 set ("robot part compatibility judgment layer"), and the **acceptance method was a one-time
    human grep**, with the conclusion only written into
    `docs/positioning-audit-20260921.md:276`. This is not that the grep was wrong, but that it
    **had no mechanism to carry it forward**: whoever writes the old convention back into any
    page/JSON/llms.txt, nothing alerts; the more hidden reverse distortion (source changed,
    online not changed) is equally unverified on the positioning axis — the numeric axis has
    verify_live_numbers.py probing back, the positioning axis had zero.

    This gate runs `positioning_contract.py`'s **offline** two passes (the module is the sole
    source of criteria; the online half is reused by verify_live_numbers.py with the same
    criteria):
      ① --check     local deployable surface (255 text files) 0 retired wordings;
      ② --self-test 15 yin-yang controls (incl. 4 negative controls + 3 temp-dir end-to-end).
    **Deliberately no network here**: CI network is unreliable, and the online half is the
    post-deploy probe responsibility.
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
    # 2026-09-18 added: the two MCP servers (stdio npm package + hosted endpoint) each once
    # missed categories twice (20260805 missing 108, 20260918 missing 68 and including
    # grippers/reducers). The hosted side is worse: the schema enum does not allow it, so any
    # client obeying JSON Schema simply cannot pass the new category; loading the data fully is
    # useless. This gate also forbids hard-coding category counts in copy (use ${CATEGORIES.length}
    # live-computed instead).
    ('MCP 品类覆盖（stdio + hosted ↔ entities.json）', lambda: run_sub(
        'MCP 品类覆盖（stdio + hosted ↔ entities.json）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'verify_mcp_coverage.py')])),
    # 2026-09-18 added: the files whitelist once missed dialects.js, a local dependency of
    # index.js — i.e. "repo runs, but install crashes". Repo-runnable ≠ installable; this gate
    # watches the **published artifact**.
    ('MCP 包完整性（入口可达模块 ⊆ files）', lambda: run_sub(
        'MCP 包完整性（入口可达模块 ⊆ files）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'verify_mcp_package.py')])),
    # 2026-09-18 added: the public manifests for external directories (server.json / smithery.yaml
    # / .well-known/mcp.json) had all-hand-written numbers and tool sets, measured stale —
    # server.json still said 688 (Glama's online entry takes it as the intro), smithery.yaml still
    # 688 entries + only 5/10 tools listed. Switched to generator + drift red light.
    ('公开清单数字现算（server.json / smithery.yaml / .well-known）', lambda: run_sub(
        '公开清单数字现算（server.json / smithery.yaml / .well-known）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'gen_public_manifests.py'),
         '--check'])),
    # 2026-09-19 added: kinematic-reachability layer (borrowing PyRoki's "URDF-first" data
    # model, extending mechanical-interface judgment from static to reachability upper bound).
    # The risk: an engine that "always returns insufficient_data" and a broken engine look
    # identical — comparing only the external JSON gives false green. So this gate runs
    # verify_kinematics.py's yin-yang self-test: construct a fully-parameterized fake chain to
    # prove it really computes, then remove one link_mm to prove it really fail-closes, plus a
    # drift criterion.
    ('运动学可达性（阴阳自测 + 漂移）', lambda: run_sub(
        '运动学可达性（阴阳自测 + 漂移）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'verify_kinematics.py')])),
    # 2026-09-20 added: demand-signal classification layer. api/demand-signal.json once claimed
    # externally "captured 10 real compatibility-question signals", but all 10 were actually
    # AI/LLM software-repo PRs. The fail-open classification layer + external-wording drift are
    # both watched by this gate.
    ('需求信号判别层（三态 fail-closed + 对外口径）', gate_demand_signal_classification),
    # 2026-09-21 added: flange adapter's three-way geometric consistency
    # (preview/OpenSCAD/CLI). No one guarded the three conventions before; historically a
    # "preview vs artifact two geometries" incident really happened.
    ('转接件三方几何一致性', gate_adapter_geometry),
    # 2026-09-21 added: mechanical pre-gate for closing a commit. auto_drift_heal.py once
    # committed any working-tree change as "drift", unable to distinguish timestamp roll from
    # real content change ⇒ content changes laundered into the repo.
    ('纯漂移判别（收口前置）', gate_pure_drift),
    # 2026-09-23 added: morphology graph (direction anchor v2.1's Phase A2 — D4 collaborative
    # design base's input form). Failure mode is silent lying not crashing, so it must run
    # "invariants + yin-yang/mutation self-proof" twice.
    ('形态图（不变量 + 阴阳/变异自证）', gate_morphology_graph),
    # 2026-09-23 added: cross-layer provenance (direction anchor v2.1's D6 foundation). Core
    # output is four booleans, easiest to false-green; this gate's first version was really
    # fooled by a self-reference false-positive (see gate docstring).
    ('跨层溯源（契约 + 阴阳/变异自证）', gate_embodiment_provenance),
    # 2026-09-23 added: Croissant metadata (direction anchor v2.1 Phase A1 by-product).
    # By-product not exempt from inspection: count reconciliation facts() + honest boundary must
    # propagate with the metadata.
    ('Croissant 元数据（审计 + 阴阳/变异自证）', gate_croissant_metadata),
    # 2026-09-23 added: compose semantics (direction anchor v2.1 Phase B1/B2).
    ('组合语义 compose(a,b)（审计 + 阴阳/变异自证）', gate_compose_semantics),
    # 2026-09-24 added: gap-cause classification (anchor §6.1 D-GAP). Complements the compose
    # semantics above — one is entity-level static cause attribution (are the 414 gaps (i)
    # unpublished or (ii) proprietary), the other is pair-level dynamic bottleneck location
    # (gap_distance / d1_bottleneck). The former decides "is the gap attackable", the latter
    # "which axis to attack first".
    ('缺口成因分类（与 facts 交叉校验 + 完备性）', gate_gap_classification),
    # 2026-10-03 added: marginal declaration value MDV (anchor §6.3 /
    # docs/RESEARCH_BARRIERS_20261003.md). Division of labor with gap_classification: that layer
    # judges "what cause is the gap" (entity-level static), this layer judges "which declaration
    # has max marginal gain" (pair-level dynamic). Reason to gate: this layer outputs
    # theorem-grade assertions like "some axis's forensic gain is provably 0". Wrong assertion
    # does not crash — change one PAIR_RANK threshold or under-register type_compat, MDV may flip
    # sign while all "passed" checks stay green, and the project pours resources into dead axes.
    ('边际声明价值 MDV（上界定理 + 阴阳/变异自证）', gate_evidence_valuation),
    # 2026-10-03 added: minimal viable homogeneous set cohort_feasibility. This is the
    # **semantic-corrected version** of MDV — MDV mislabels the "joint upper bound" as "single
    # declaration marginal value"; end-to-end verification (injecting the 16 targets alone ⇒
    # electrical decidable pairs 1→1 flat) proved the prediction did not materialize. Corrected
    # criterion: K=1 impossible, K=2 suffices, homogeneous viable pairs 46,149 / 636 nodes.
    # Both layers must be gated together: MDV provides candidate-node filtering, cohort provides
    # the real forensic criterion, and ci_gate force-checks "all 16 MDV targets fall inside the
    # cohort feasible set" — a cross-layer invariant; either layer failing turns red instantly.
    ('最小可行同质集（K=2 可行域 + MDV 跨层对账 + 阴阳/变异自证）',
     gate_cohort_feasibility),
    ('电气接口取证（MDV 定向，一手出处强制 + M8 家族冲突）',
     gate_electrical_evidence),
    # 2026-10-04 added: electrical forensic layer → morphology graph **wiring completeness**.
    # Guards a failure that already really happened: the forensic layer dropped 4 first-hand
    # verified connectors, artifact self-consistent + fields complete + gate all green, but the
    # morphology-graph generator **never reads it**, entities still hang ELEC:UNKNOWN, decidable
    # pair count unchanged. After first wiring it hit a second layer: using a local id instead of
    # rp_id as key, still zero matches. Form checks ("was the wiring code written") cannot catch
    # this; only behavior verification can.
    ('电气取证接线完整性（落地 + 行为 + 变异）', gate_electrical_wiring),
    # 2026-10-04 added: co-mount frontier. Turn "composed=0" from a failure narrative into a
    # reproducible diagnosis. This layer's specific guard is the **convention guard** — it outputs
    # a diagnostic conclusion supported by only a few samples; the mutation "change hypothesis
    # into assertion" must turn red. An over-claimed diagnosis is worse than no diagnosis.
    ('共装前沿（L1/L2/L3 分解 + 口径守卫 + 7 变异）', gate_compose_frontier),
    # 2026-10-04 added: research-layer ↔ product-surface reachability. Guards faults like
    # "research done but user cannot touch it" — it does not error, gate all green, only makes
    # the research asset invisible to the user.
    ('研究层可达性（产物引用 + 桥接工具接线 + 维度登记）', gate_reachability_gap),
    # 2026-10-04 added: core-goal completion criterion. Guards "percentages are not made up" —
    # sub-items carry convention, weights questionable, gating live-computed, and sensitive to
    # the core goal.
    ('核心目标完成度（口径 + 门控现算 + 敏感性 + 8 变异）', gate_research_progress),
    # 2026-10-05 added: co-mount relation (the third relation type). Guards it against silently
    # regressing back to two-segment mutual insert, and forces self-describing unmodeled scope —
    # co_mount covers a very narrow range, high over-claiming risk.
    ('共装关系（三段结构 + port_exhausted + 宿主取证 + 11 变异）', gate_co_mount),
    # 2026-10-05 added: binding layer + behavior layer. Guards "no fabricated binding" / "no
    # single-piece evidence" / "simulation not impersonating real hardware" — all three are
    # high-incidence over-claiming zones.
    ('开源VLA绑定 + 行为证据（实体存在性 + 强度自洽 + 对照组 + 9 变异）',
     gate_open_vla_and_behavior),
    # 2026-09-24 added: pipeline framework (operators + DAG skeleton + gap_classification
    # template). This is the "missing 20%" identified in the GOAI report — explicitly modeling
    # with operators/DAG, splitting hand-written scripts into pure-function operators. The
    # skeleton itself has zero stdlib dependencies; the template and the old script's output must
    # be field-by-field equivalent (except the two inevitably-different fields generated_at /
    # generated_by). Broken equivalence is a refactor fork, instantly red — the only gate against
    # "pipeline silently forking from the old script".
    ('Pipeline 框架（骨架 + 等价性 + 自证 17 项）', lambda: run_sub(
        'Pipeline 框架（骨架 + 等价性 + 自证 17 项）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'verify_pipeline.py')],
        timeout=120)),
    ('定位口径本地扫描', gate_positioning_caliber),
    ('对外 JSON 可解析', gate_json_parses),
    ('entities.json meta 一致', gate_entities_meta_consistent),
    # 【20261008】README stats block freshness. Guards "README numbers silently drift after
    # changing the truth source" (measured 802 vs 868 unnoticed for long) — injector now in the
    # regen pipeline + this gate as double insurance.
    ('README 统计块与真相源一致', gate_readme_stats_fresh),
    # 【20261008】Golden evaluation set. Guards "rule engine silently drifts from frozen anchors"
    # — previously this set existed but nobody ran it (4/6 false red); this gate wires it into CI.
    ('兼容性裁决 Golden 评估集（冻结锚点 + badcase）', gate_eval_compat),
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
    print('=== RoboParts CI gates (in-repo decidable subset; full regression in '
          'scripts/regression.py) ===')
    for name, fn in GATES:
        try:
            fn()
        except Exception as ex:
            bad(name, f'gate raised exception: {type(ex).__name__}: {ex}')
    print('\n' + '=' * 46)
    if FAILED:
        print(f'❌ BLOCKED: {len(FAILED)} items failed (passed {len(PASSED)} items)')
        for f in FAILED:
            print(f'   - {f}')
        return 1
    print(f'✅ all passed ({len(PASSED)} items)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
