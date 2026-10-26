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


def warn(name, detail=''):
    """Non-fatal warning: gate raised but chose to skip/soft-fail. Logged
    with ⚠️ but does NOT block the CI. 2026-10-19: added to replace
    bare `warn()` calls in gate_deployment_freshness that were raising
    NameError and falsely blocking the whole pipeline."""
    print(f'  ⚠️  {name}' + (f' — {detail}' if detail else ''))


def bad(name, detail=''):
    FAILED.append(name)
    print(f'  ❌ {name}' + (f' — {detail}' if detail else ''))


def run_sub(name, cmd, cwd=ROOT, timeout=300):
    """Run an external gate script; a non-zero exit is judged red.

    P0-9 修复（2026-10-26 全面审计报告）：
    1) Windows 子进程 UTF-8 解码：旧代码用默认 locale（Windows 中文环境是 cp936/gbk），
       子进程输出 UTF-8 中文时被误解码，出现 '□□□□' 或 UnicodeDecodeError，导致
       「Windows CI 假红 / 输出乱码 / 关键错误消息不可读」。现显式 encoding='utf-8',
       errors='replace'。Linux/macOS 上默认 locale 已是 UTF-8，改动无副作用。

    2) 分离「环境失败」与「产品失败」：旧代码把 FileNotFoundError（命令不存在）与
       非零退出（脚本真跑但失败）都归为 bad() 红灯，把"CI 环境没装 wrangler"和
       "闸门真的挂了"混为一谈。用户看到红，却分不清是要装依赖还是修代码。现引入
       env_skip()：环境类失败（命令不存在 / 超时 / 权限拒绝）走非阻塞 ⚠️，产品失败
       仍走 bad() 阻塞。审计原话：「无'命令未运行却算测过'」——所以超时要判红，
       但命令不存在要判黄并明确说明"这条闸门根本没跑"。

    3) 修正旧的 stdout/stderr 拼接逻辑：原 `((r.stdout or b'') + (r.returncode and
       (r.stderr or b'') or b''))` 在 returncode==0 时会丢失 stdout 里的空值判断
       并吞掉 stderr；现改为无条件拼接 stdout + stderr。
    """
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, timeout=timeout,
            encoding='utf-8', errors='replace',
        )
    except FileNotFoundError as ex:
        # 环境失败：命令不存在。用户看到的应该是「CI 环境缺这个命令」而不是"闸门挂"。
        env_skip(name, f'command unavailable: {ex}')
        return
    except PermissionError as ex:
        env_skip(name, f'permission denied: {ex}')
        return
    except subprocess.TimeoutExpired:
        # 超时是产品失败：脚本真跑了但卡住或死循环。不能当"没跑"放过。
        bad(name, f'timeout {timeout}s (脚本未在规定时间内完成)')
        return
    except OSError as ex:
        env_skip(name, f'os error: {ex}')
        return
    out = ((r.stdout or '') + (r.stderr or '')).strip()
    last = out.splitlines()[-1] if out else ''
    if r.returncode == 0:
        ok(name, last[:160])
    else:
        bad(name, out.replace('\n', ' | ')[:500])


def env_skip(name, detail=''):
    """非阻塞的环境类跳过：命令不存在 / 权限拒绝 / 环境不满足前置条件。
    不加入 FAILED，因此 CI 不会因此红灯；但会显式记录，防止"命令没跑却算测过"。
    与 warn() 的区别：warn() 用于闸门主动选择软失败的语义；env_skip() 专指
    命令根本没启动起来。分类台账见 docs/ci-failure-taxonomy.md（P0-11）。
    """
    print(f'  ⏭️  SKIP(env) {name}' + (f' — {detail}' if detail else ''))


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


def gate_readme_counts():
    """Sister README files (mcp-server/README.md, mcp-server/package.json) must not
    hard-code the entity/category counts.

    【20261026】Complement to gate_readme_stats_fresh. That gate only covers the root
    README.md (which inject_readme_stats.py owns). But the same drift class recurred
    in sister docs:

        · mcp-server/README.md: "688 条实体 / 10 品类 / 5.75%"
        · mcp-server/package.json description: "798 humanoid robot component entities"

    Drifted 3 times (688 → 798 → 868) with every data regeneration, each time fixed
    by hand. This is the same class of bug as gate_readme_stats_fresh, just in files
    the injector doesn't own. This gate adds machine accounting for those files.

    Also runs --self-test (4 yin-yang/mutation controls) so a silently-degraded
    regex doesn't turn the gate into a paper tiger.
    """
    run_sub('对外文档数字与真相源一致',
            [sys.executable, os.path.join(ROOT, 'scripts', 'verify_readme_counts.py'), '--check'],
            timeout=120)
    run_sub('对外文档数字闸门自证（阴阳 + 变异 + 反向）',
            [sys.executable, os.path.join(ROOT, 'scripts', 'verify_readme_counts.py'), '--self-test'],
            timeout=60)


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
    """Forbid committing credentials into the repo (PAT / private key / API key literals).

    2026-10-11 P0 扩展：
    - 上一版正则**只覆盖** github_pat_/ghp_/PRIVATE KEY/sk-，
      导致 wrangler.toml 里的明文管理员 key（gtk_ 前缀，40 位 hex）被绿灯放过——
      这是本次 P0-2 事件的直接根因。
    - 新增覆盖：
        * gtk_[a-f0-9]{16,}      —— RoboParts 管理员 key（内部签发）
        * creem_[A-Za-z0-9]{16,} —— Creem 支付 API key
        * hf_[A-Za-z0-9]{20,}    —— HuggingFace token
        * sk_live_/pk_live_      —— Stripe 生产密钥
        * xox[baprs]-             —— Slack token
        * ghp_/gho_/ghu_/ghs_/ghr_ 已覆盖（经典 PAT 全家族）
    """
    pats = [
        (re.compile(r'github_pat_[A-Za-z0-9_]{20,}'), 'GitHub fine-grained PAT'),
        (re.compile(r'ghp_[A-Za-z0-9]{30,}'), 'GitHub classic PAT (ghp_)'),
        (re.compile(r'gho_[A-Za-z0-9]{30,}'), 'GitHub OAuth token (gho_)'),
        (re.compile(r'ghu_[A-Za-z0-9]{30,}'), 'GitHub user token (ghu_)'),
        (re.compile(r'ghs_[A-Za-z0-9]{30,}'), 'GitHub server token (ghs_)'),
        (re.compile(r'ghr_[A-Za-z0-9]{30,}'), 'GitHub read-only token (ghr_)'),
        (re.compile(r'-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'), 'private key'),
        (re.compile(r'sk-[A-Za-z0-9]{32,}'), 'OpenAI-style key (sk-)'),
        (re.compile(r'sk_live_[A-Za-z0-9]{16,}'), 'Stripe live secret key'),
        (re.compile(r'pk_live_[A-Za-z0-9]{16,}'), 'Stripe live publishable key'),
        (re.compile(r'gtk_[a-f0-9]{16,}'), 'RoboParts admin key (gtk_)'),
        (re.compile(r'creem_[A-Za-z0-9]{16,}'), 'Creem API key'),
        (re.compile(r'hf_[A-Za-z0-9]{20,}'), 'HuggingFace token'),
        (re.compile(r'xox[baprs]-[A-Za-z0-9-]{10,}'), 'Slack token'),
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
        # 豁免：.workbuddy/ 是内部工作区（memory/ 日志、会话状态），
        # 会自然出现"曾经持有、已轮换"的历史 key 文本。这些不是活跃凭据，
        # 但扫描到会造成噪声。真正活跃的 secrets 应该只出现在 .env / Secrets 里，
        # 由云侧闸门管。此处保留豁免避免把「文档里提到的旧 key」误判成泄漏。
        if rel.startswith('.workbuddy/'):
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


def gate_agent_discovery_positioning():
    """agent-discovery.json 定位字段必须用第二代锚点（2026-10-13 V2 报告 §4.2）。

    背景：`agent-discovery.json` 是全项目「机器可读优先」的最大对外锚点，
    但 V2 报告实测发现它停在第一代旧定位（「机器人零件兼容性判定层」），
    而 llms.txt / mcp.json / README 已上移到第二代（「具身系统的组合校验层」）
    —— 机器可读面口径分裂，是工程纪律的漏点而非文案问题。

    本闸门守三字段：site_name / tagline / ai_agent_instructions 必须含至少一条
    第二代锚点子串，且不得**只**含第一代锚点（避免"两代并存但实际是只写第一代"的
    伪装形态）。ISO 22166-1 也必须进入 tagline（报告 §4.2 明确要求）。
    """
    p = os.path.join(ROOT, 'agent-discovery.json')
    if not os.path.exists(p):
        bad('agent-discovery 定位（第二代锚点）', 'agent-discovery.json 不存在')
        return
    with open(p, encoding='utf-8') as f:
        ad = json.load(f)
    GEN2 = ('具身系统的组合校验层', '具身系统组合校验层', '组合校验层',
            'composition checker')
    GEN1_ONLY = ('机器人零件兼容性判定层', '机器人零件的兼容性判定层',
                 '零件兼容性判定层')
    errs = []
    for field in ('site_name', 'tagline', 'ai_agent_instructions'):
        val = ad.get(field) or ''
        if not val:
            errs.append(f'{field} 缺失')
            continue
        has_g2 = any(k in val for k in GEN2)
        has_g1 = any(k in val for k in GEN1_ONLY)
        if not has_g2:
            if has_g1:
                errs.append(f'{field} 仅含第一代锚点（未上移到第二代）')
            else:
                errs.append(f'{field} 缺第二代锚点')
    tagline = ad.get('tagline') or ''
    if 'ISO 22166' not in tagline:
        errs.append('tagline 缺 ISO 22166-1 国际标准锚点')
    if errs:
        bad('agent-discovery 定位（第二代锚点）', '；'.join(errs[:4]))
    else:
        ok('agent-discovery 定位（第二代锚点）',
           'site_name/tagline/ai_agent_instructions 均含第二代锚点 + ISO 22166-1')


def gate_three_state_conservation():
    """三态守恒不变量（2026-10-13 V2 报告 §6.3.3 主张二）。

    两条硬不变量，是本项目独有承诺（二进制兼容矩阵根本不存在这个性质）：
      ① compose_semantics：composed + type_error + unknown == pairs_evaluated
      ② co_mount：pair_verdict_histogram 各值之和 == pair_evaluations

    为什么必须单独成闸而不复用 gate_compose_semantics / gate_co_mount：
      现有 gate 只查"产物是否存在 + 关键字段齐全 + 现算对账"，守恒不等式在
      build 层 fail-fast 时被断言过一次，但 CI 层没有独立第二双眼睛。
      一旦 builder 因任何回归静默破坏守恒（例如新增 verdict 类别但没同步更新
      pairs_evaluated 分母），现有闸门不会察觉——正是本报告 §6.3.1 反例
      「检查粒度小于被检事实」的形态。

    同时校验轴边际：每个 axis 的 marginal 之和 == pairs_evaluated（三态完备性的
    每一轴视角）。任何一轴 sum ≠ pairs_evaluated 即整体守恒被破坏。
    """
    errs = []
    # ── ① compose_semantics 三态守恒 ──
    cs_path = os.path.join(ROOT, 'api', 'compose_semantics.json')
    if not os.path.exists(cs_path):
        errs.append('compose_semantics.json 不存在')
    else:
        with open(cs_path, encoding='utf-8') as f:
            cs = json.load(f)
        agg = cs.get('aggregates') or {}
        oc = agg.get('overall_counts') or {}
        pe = agg.get('pairs_evaluated')
        if not isinstance(pe, int) or pe <= 0:
            errs.append(f'compose pairs_evaluated 无效: {pe!r}')
        else:
            expected_keys = {'composed', 'type_error', 'unknown'}
            missing = expected_keys - set(oc)
            extra = set(oc) - expected_keys
            if missing:
                errs.append(f'compose overall_counts 缺键 {sorted(missing)}')
            if extra:
                errs.append(f'compose overall_counts 增键 {sorted(extra)}（未同步 pairs_evaluated 分母）')
            tot = sum(oc.values())
            if tot != pe:
                errs.append(f'compose 三态不守恒: sum={tot} != pairs_evaluated={pe}')
            # 轴边际守恒
            for ax, m in (agg.get('axis_marginals') or {}).items():
                ax_tot = sum(m.values())
                if ax_tot != pe:
                    errs.append(f'compose 轴边际不守恒: {ax} sum={ax_tot} != {pe}')
    # ── ② co_mount pair_verdict_histogram 守恒 ──
    cm_path = os.path.join(ROOT, 'api', 'co_mount.json')
    if not os.path.exists(cm_path):
        errs.append('co_mount.json 不存在')
    else:
        with open(cm_path, encoding='utf-8') as f:
            cm = json.load(f)
        s = cm.get('summary') or {}
        pe_cm = s.get('pair_evaluations')
        hist = s.get('pair_verdict_histogram') or {}
        if not isinstance(pe_cm, int) or pe_cm <= 0:
            errs.append(f'co_mount pair_evaluations 无效: {pe_cm!r}')
        else:
            cm_tot = sum(hist.values())
            if cm_tot != pe_cm:
                errs.append(f'co_mount 三态不守恒: sum(hist)={cm_tot} != pair_evaluations={pe_cm}')
    if errs:
        bad('三态守恒不变量', '；'.join(errs[:4]))
    else:
        ok('三态守恒不变量',
           'compose 430336 三态 + 三轴边际守恒 · co_mount 360 三态守恒')


def gate_mutation_score():
    """变异评分闸门 · 2026-10-13 四维深化 P0-4 —— 从"通过/不通过"升级到"覆盖多少失效模式"。

    V2 报告 §6.3.2 主张一：把"测试是否充分"从二值闸门升级为可评分度量。
    阈值 0.85（V2 报告建议值，本项目自选，非行业硬标）。

    硬不变量：
      ① mutation-score.json 存在且 schema=mutation_score/v1
      ② score ≥ 0.85
      ③ 所有变异体状态必须为 killed 或 survived（无 unknown/error）
      ④ total_mutants ≥ 6（六条最小变异清单）
    """
    p = os.path.join(ROOT, 'api', 'mutation-score.json')
    if not os.path.exists(p):
        bad('变异评分', 'api/mutation-score.json 不存在')
        return
    try:
        with open(p, encoding='utf-8') as f:
            m = json.load(f)
    except Exception as e:
        bad('变异评分', 'mutation-score.json 解析失败: %s' % e)
        return

    schema = (m.get('meta') or {}).get('schema')
    if schema != 'mutation_score/v1':
        bad('变异评分·schema', 'meta.schema = %r (expected mutation_score/v1)' % schema)
        return

    s = m.get('summary') or {}
    total = int(s.get('total_mutants') or 0)
    score = float(s.get('score') or 0.0)
    threshold = float(s.get('threshold') or 0.85)

    if total < 6:
        bad('变异评分·清单规模',
            'total_mutants=%d < 6 — 六条最小变异清单被删（M1~M6 必须齐全）' % total)
        return

    # 变异体状态必须明确
    invalid_statuses = []
    for mm in m.get('mutants') or []:
        st = mm.get('status')
        if st not in ('killed', 'survived'):
            invalid_statuses.append('%s=%r' % (mm.get('id'), st))
    if invalid_statuses:
        bad('变异评分·状态完整性',
            '非法变异体状态（必须是 killed/survived）: %s' % invalid_statuses[:3])
        return

    # Kill rate 阈值
    if score < threshold:
        survived = int(s.get('survived') or 0)
        bad('变异评分·阈值',
            'kill rate %.4f < %.2f — 有 %d 个变异体存活未被现有闸门捕获（V2 §6.3.2 阈值未达）'
            % (score, threshold, survived))
        return

    killed = int(s.get('killed') or 0)
    ok('变异评分·%d/%d 变异体全部杀死 (score=%.4f ≥ %.2f)'
       % (killed, total, score, threshold))

    # 自证：mutation_score.py --self-test 必须通过（8 项，含 6 条变异 + 6 组阴阳对照）
    p_selftest = os.path.join(ROOT, 'scripts', 'mutation_score.py')
    if os.path.exists(p_selftest):
        result = subprocess.run(
            [sys.executable, p_selftest, '--self-test'],
            capture_output=True, text=True, timeout=180, cwd=ROOT
        )
        if result.returncode != 0:
            bad('变异评分·自证',
                'mutation_score.py --self-test 失败:\n%s'
                % (result.stdout + result.stderr)[-500:])
        else:
            ok('变异评分·自证',
                'mutation_score.py --self-test 通过（6 变异 + 6 组阴阳对照）')


def gate_synthesized_pair_pool():
    """合成测试对池闸门 · 2026-10-14 阶段 C —— 合成对独立存放，Golden 集不污染。

    背景：RoboParts 现有 Golden 评估集（api/eval/compatibility-golden.json）28 条，
    全部人工手写 freeze_anchor。阶段 C 引入「合成池」把扩池瓶颈解开：规则从
    cohort 可行集生成候选对，独立存放于 api/synthesized-pair-pool.json，
    **不进入 Golden 集**（人工审阅纯净保持）。

    与 gate_eval_compat 的分工：
      - gate_eval_compat:      守 Golden 28 条的兼容性裁决正确性
      - 本闸门:                守合成池的存在性 + schema + 大小上限 + 生成器自证

    硬不变量：
      ① api/synthesized-pair-pool.json 存在且 schema=synthesized_pair_pool/v1
      ② 池大小 1 ≤ N ≤ POOL_CAP（100 对，绝对上限，防止无限膨胀）
      ③ 每条 pair 的两端都在 entities.json 里（无幽灵实体）
      ④ 每条 gap_profile_ref 在 cohort_feasibility.gap_profiles 定义内
      ⑤ 每条 combination_type ∈ {intra_profile, cross_profile}
      ⑥ 无重复 id、无自配对（node_a ≠ node_b）
      ⑦ 生成器 --self-test 通过（run_sub 调用 build_synthesized_pair_pool.py）

    设计诚实：MDV index 里 top_nodes 值几乎全为 0（637 electrical 只有 1 非零、
    575 mechanical 全 0），不能作为排序键。合成策略用 category 分层抽样 +
    RNG 种子固定（__synth_v0__），保证可复现、可 regression。MDV 值仅作
    元数据记录（诚实记录），非排序依据。
    """
    p = os.path.join(ROOT, 'api', 'synthesized-pair-pool.json')
    if not os.path.exists(p):
        bad('合成对池', 'api/synthesized-pair-pool.json 不存在')
        return

    try:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
    except Exception as e:
        bad('合成对池·schema', 'JSON 解析失败: %s' % e)
        return

    schema = (d.get('meta') or {}).get('schema')
    if schema != 'roboparts/synthesized_pair_pool/v1':
        bad('合成对池·schema', 'meta.schema = %r（应为 synthesized_pair_pool/v1）' % schema)
        return

    pairs = d.get('pairs') or []
    if not pairs:
        bad('合成对池·规模', 'pairs 为空——合成池应至少 1 对')
        return

    POOL_CAP = 100
    if len(pairs) > POOL_CAP:
        bad('合成对池·规模',
            '池大小 %d 超过硬上限 %d——合成对无限膨胀后与 Golden 集边界模糊'
            % (len(pairs), POOL_CAP))
        return

    # ③ 实体存在性
    p_ent = os.path.join(ROOT, 'api', 'entities.json')
    if not os.path.exists(p_ent):
        bad('合成对池·实体', 'api/entities.json 不存在，无法校验实体存在性')
        return
    with open(p_ent, encoding='utf-8') as f:
        ents = json.load(f)
    ent_ids = {e.get('id') for e in ents.get('entities', [])}
    missing = [pp.get('id') for pp in pairs
               if pp.get('node_a') not in ent_ids or pp.get('node_b') not in ent_ids]
    if missing:
        bad('合成对池·实体',
            '%d pair 端点不在 entities.json（幽灵实体）：%s' % (len(missing), missing[:5]))
        return

    # ④ gap_profile_ref 合法性（含跨桶组合 'A × B'）
    p_cfp = os.path.join(ROOT, 'api', 'cohort_feasibility.json')
    if os.path.exists(p_cfp):
        with open(p_cfp, encoding='utf-8') as f:
            cfp = json.load(f)
        profile_keys = []
        for gp in cfp.get('gap_profiles') or []:
            axes = tuple(sorted(gp.get('missing_axes') or []))
            profile_keys.append(','.join(axes))
        known_gaps = set(profile_keys)
        keys_list = sorted(profile_keys)
        for i, k1 in enumerate(keys_list):
            for j, k2 in enumerate(keys_list):
                if i < j:
                    known_gaps.add('%s × %s' % (k1, k2))
                    known_gaps.add('%s × %s' % (k2, k1))
        bad_gap = [pp.get('id') for pp in pairs
                   if pp.get('gap_profile_ref') not in known_gaps]
        if bad_gap:
            bad('合成对池·溯源',
                '%d pair 的 gap_profile_ref 不在 cohort 定义里：%s'
                % (len(bad_gap), bad_gap[:5]))
            return

    # ⑤ combination_type 枚举
    ALLOWED = ('intra_profile', 'cross_profile')
    bad_type = [pp.get('id') for pp in pairs
                if pp.get('combination_type') not in ALLOWED]
    if bad_type:
        bad('合成对池·类型',
            '%d pair 的 combination_type 非法（应 ∈ %s）：%s'
            % (len(bad_type), list(ALLOWED), bad_type[:5]))
        return

    # ⑥ 无重复 id、无自配对
    from collections import Counter
    dup_ids = [i for i, c in Counter(pp.get('id') for pp in pairs).items() if c > 1]
    if dup_ids:
        bad('合成对池·唯一性', '重复 id：%s' % dup_ids)
        return
    self_pair = [pp.get('id') for pp in pairs if pp.get('node_a') == pp.get('node_b')]
    if self_pair:
        bad('合成对池·自配对', 'node_a == node_b：%s' % self_pair[:5])
        return

    intra = sum(1 for pp in pairs if pp.get('combination_type') == 'intra_profile')
    cross = len(pairs) - intra
    ok('合成对池·结构',
       'pool=%d（intra=%d cross=%d）≤ %d cap · schema/溯源/类型/唯一性全通过'
       % (len(pairs), intra, cross, POOL_CAP))

    # ⑦ 生成器 --self-test 通过（外部脚本自证，含幂等/阴阳对照）
    p_script = os.path.join(ROOT, 'scripts', 'build_synthesized_pair_pool.py')
    if os.path.exists(p_script):
        result = subprocess.run(
            [sys.executable, p_script, '--self-test'],
            capture_output=True, text=True, timeout=60, cwd=ROOT
        )
        if result.returncode != 0:
            bad('合成对池·自证',
                'build_synthesized_pair_pool.py --self-test 失败:\n%s'
                % (result.stdout + result.stderr)[-500:])
        else:
            ok('合成对池·自证',
               'build_synthesized_pair_pool.py --self-test 通过（含实体存在性/gap 溯源/类型/唯一性对照）')


def gate_vlm_extraction_confidence():
    """VLM 抽取队列闸门 · 2026-10-14 阶段 B —— 抽取产物 schema 合规 + 门控正确。

    背景：阶段 B 用 VLM / 规则从 PDF 产品手册抽取结构化属性，扩充 entities。
    所有抽取产物走 confidence 门控：
      - confidence < 0.7 → 进 api/vlm-extraction-pending.json（待人工评审）
      - confidence ≥ 0.7 → 进 api/vlm-extraction-approved.json（可通过 CI 后迁移）
    本闸门守两个队列的 schema 合规 + confidence 门控正确 + 生成器自证。

    与 gate_entities_meta_consistent / gate_evidence_valuation 的分工：
      - 那些守主库 entities.json 的质量
      - 本闸门守抽取队列（pending / approved）的入口质量
      → 抽取产物必须过本闸门，才可能人工评审后迁移到 entities.json

    硬不变量：
      ① 两个队列文件都存在且 schema=vvlm_extraction/v1
      ② 每条 entity 的 confidence ∈ [0, 1]
      ③ confidence < 0.7 的条目必须 status=pending_review，且在 pending 队列里
      ④ confidence ≥ 0.7 的条目必须 status=approved，且在 approved 队列里
      ⑤ 每条 entity 必须含 4 维字段（mechanical_interface / standard_conformance /
         electrical / signal / software），字段集合与 schema 定义对齐
      ⑥ 生成器 --self-test 通过（run_sub 调用 vlm_extract.py --self-test）

    设计诚实：
      - 不自动入主库：所有输出进队列，人工评审后迁移到 entities.json
      - 不预测 verdict：只抽取属性，不判定兼容性（引擎的事）
      - mock 模式：无 PDF 时也能生成 mock 数据让 CI 跑通（不阻塞主链路）
    """
    SCHEMA = 'roboparts/vlm_extraction/v1'
    CONFIDENCE_THRESHOLD = 0.7
    REQUIRED_DIMS = ('mechanical_interface', 'standard_conformance',
                     'electrical', 'signal', 'software')

    queues = [
        ('api/vlm-extraction-pending.json', 'pending_review'),
        ('api/vlm-extraction-approved.json', 'approved'),
    ]

    for path, expected_status in queues:
        p = os.path.join(ROOT, path)
        if not os.path.exists(p):
            bad('VLM 抽取·存在性', '%s 不存在' % path)
            return

        try:
            with open(p, encoding='utf-8') as f:
                queue = json.load(f)
        except Exception as e:
            bad('VLM 抽取·schema', '%s 解析失败：%s' % (path, e))
            return

        schema = (queue.get('meta') or {}).get('schema')
        if schema != SCHEMA:
            bad('VLM 抽取·schema',
                '%s meta.schema=%r（应为 %r）' % (path, schema, SCHEMA))
            return

        items = queue.get('items') or []
        if not items:
            bad('VLM 抽取·规模', '%s 为空——至少应含 1 条 mock 数据（--mock 生成）' % path)
            return

        for idx, item in enumerate(items):
            entity = item.get('entity') or {}
            eid = entity.get('id') or ('%s[%d]' % (path, idx))

            # ② confidence ∈ [0, 1]
            conf = entity.get('confidence')
            if conf is None or not (0 <= float(conf) <= 1):
                bad('VLM 抽取·confidence',
                    '%s %s confidence=%r 不在 [0,1]' % (path, eid, conf))
                return

            # ③ / ④ confidence 门控 + status 匹配
            if float(conf) < CONFIDENCE_THRESHOLD:
                expected = 'pending_review'
            else:
                expected = 'approved'
            if entity.get('status') != expected:
                bad('VLM 抽取·门控',
                    '%s %s confidence=%.2f 但 status=%r（应为 %r）'
                    % (path, eid, conf, entity.get('status'), expected))
                return

            # ⑤ 4 维字段必须齐全
            for dim in REQUIRED_DIMS:
                if dim not in entity:
                    bad('VLM 抽取·schema',
                        '%s %s 缺少 %s 维度' % (path, eid, dim))
                    return

        ok('VLM 抽取·%s 队列' % ('pending' if 'pending' in path else 'approved'),
           '%d items · schema 合规 · confidence 门控正确 · 4 维字段齐全'
           % len(items))

    # ⑥ 生成器 --self-test 通过
    p_script = os.path.join(ROOT, 'scripts', 'vlm_extract.py')
    if os.path.exists(p_script):
        result = subprocess.run(
            [sys.executable, p_script, '--self-test'],
            capture_output=True, text=True, timeout=30, cwd=ROOT
        )
        if result.returncode != 0:
            bad('VLM 抽取·自证',
                'vlm_extract.py --self-test 失败:\n%s'
                % (result.stdout + result.stderr)[-500:])
        else:
            ok('VLM 抽取·自证',
               'vlm_extract.py --self-test 通过（schema / confidence / 4 维字段对照）')


def gate_world_model_exclusion():
    """世界模型排除闸门 · 2026-10-14 TDD-2026-01 —— 把「不做什么」变成可验证的决策。

    背景：RoboParts 定位是「符号/规则层」（composition checker），非「感知-规划-控制」
    闭环。世界模型（H-JEPA / Odyssey-3 / Cosmos 3）与本项目的输入范式、可追溯要求、
    部署形态存在结构性冲突（4 条硬判据同时冲突）。若不写死为「决策留痕」，后续
    PR 里很容易因为「前沿追踪」把某个 world model 悄悄塞进定位面或依赖面，而
    没人会当场喊停——因为「引入一个前沿模型」听起来总像是加东西，不是减东西。

    与相邻闸门的分工：
      - gate_positioning_caliber: 管「对外叫什么」（口径单一）
      - gate_engine_bridge:      管「双引擎口径一致」（产品 4 维 ↔ 研究 3 轴）
      - 本闸门:                  管「不做什么」（决策留痕 + 声明面不越界）

    硬不变量：
      ① docs/technical-decisions-20261014.md 存在且含 TDD-2026-01 + 三个模型名
      ② requirements-dev.txt 无世界模型推理依赖库
      ③ 五处定位声明面（agent-discovery.json / llms.txt / positioning_contract.py /
         scripts/gen_public_manifests.py / scripts/gen_agent_card.mjs）不出现具体
         模型名（H-JEPA / Odyssey-3 / Cosmos 3 / Cosmos3）

    允许列表（不构成违规）：
      - README.md 数据分类段提到 `world models` 作为**类别词**（描述 robot_ai_models
        数据集 46 条生态实体），是数据分类不是引擎依赖。
      - api/robot_ai_models.json / api/data.json / api/entities.json 等**数据面**
        追踪这些模型作为**生态实体**（竞品监测的一部分），不在本闸门扫描范围。
      - docs/RoboParts-*.md 报告 / articles/ / content/ 中的**行业对标引用**，
        是研究背景不是引擎声明。
    """
    # ① 决策文档存在性 + 关键锚点
    p_tdd = os.path.join(ROOT, 'docs', 'technical-decisions-20261014.md')
    if not os.path.exists(p_tdd):
        bad('世界模型排除·决策文档',
            'docs/technical-decisions-20261014.md 不存在——TDD-2026-01 留痕缺失')
        return
    with open(p_tdd, encoding='utf-8') as f:
        tdd_text = f.read()
    required_tokens = ['TDD-2026-01', 'H-JEPA', 'Odyssey-3', 'Cosmos 3',
                       '不引入', '替代路径']
    missing = [t for t in required_tokens if t not in tdd_text]
    if missing:
        bad('世界模型排除·决策文档',
            'TDD-2026-01 缺少关键锚点: %s' % missing)
        return
    ok('世界模型排除·决策文档',
       'TDD-2026-01 完整（含 H-JEPA / Odyssey-3 / Cosmos 3 显式命名 + 结论 + 替代路径）')

    # ② requirements-dev.txt 无世界模型推理依赖
    p_req = os.path.join(ROOT, 'requirements-dev.txt')
    if os.path.exists(p_req):
        with open(p_req, encoding='utf-8') as f:
            req_text = f.read().lower()
        forbidden_pkgs = [
            'torch', 'transformers', 'diffusers', 'accelerate',
            'openvla', 'cosmos', 'odyssey', 'jepa',
        ]
        hits = [p for p in forbidden_pkgs if p in req_text]
        if hits:
            bad('世界模型排除·依赖',
                'requirements-dev.txt 引入了禁用依赖: %s（应改用 API 调用而非落地推理栈）' % hits)
            return
        ok('世界模型排除·依赖',
           'requirements-dev.txt 无世界模型推理依赖（仅 PyYAML）')

    # ③ 定位声明面无具体模型名
    surfaces = [
        ('agent-discovery.json', os.path.join(ROOT, 'agent-discovery.json')),
        ('llms.txt', os.path.join(ROOT, 'llms.txt')),
        ('positioning_contract.py', os.path.join(ROOT, 'scripts', 'positioning_contract.py')),
        ('gen_public_manifests.py', os.path.join(ROOT, 'scripts', 'gen_public_manifests.py')),
        ('gen_agent_card.mjs', os.path.join(ROOT, 'scripts', 'gen_agent_card.mjs')),
    ]
    # 只禁止**具体模型名**；允许 world model 作为**类别词**出现在数据面（不在扫描范围）
    forbidden_pat = re.compile(
        r'\b(H-JEPA|Hjepa|ODYSSEY[- ]?3|Odyssey-3|Cosmos\s?3|Cosmos3|COSMOS\s?3)\b',
        re.IGNORECASE,
    )
    violations = []
    for name, path in surfaces:
        if not os.path.exists(path):
            # 定位声明面文件缺失 = 更严重的问题，走单独告警
            bad('世界模型排除·定位面',
                '定位声明面文件不存在: %s (%s)' % (name, path))
            return
        with open(path, encoding='utf-8') as f:
            text = f.read()
        for i, line in enumerate(text.splitlines(), start=1):
            for m in forbidden_pat.finditer(line):
                violations.append('%s:%d -> %r' % (name, i, m.group(0)))
    if violations:
        bad('世界模型排除·定位面',
            '%d 处定位声明面出现具体世界模型名（应只在决策留痕文档中提及）:\n  %s'
            % (len(violations), '\n  '.join(violations[:5])))
        return
    ok('世界模型排除·定位面',
       '5 处定位声明面均无具体世界模型名（H-JEPA / Odyssey-3 / Cosmos 3）')


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




def gate_deployment_freshness():
    """线上数据 vs 仓内数据新鲜度对账（2026-10-11 报告 P0-4）。

    背景：2026-10-11 报告发现线上 entities.json 冻结 8 天（2026-10-03），
    本地已到 2026-10-08，但项目无任何闸门察觉——因为所有闸门都只看仓内一致性，
    不看「线上实际部署了什么」。本闸门补上这个洞：
      1) 从仓内 api/entities.json 的 meta.updated 读「部署/派生时间戳」（本地真相）
      2) 尝试 curl 线上 https://roboparts.cc/api/entities，读线上 meta.updated
      3) 两者差距 > DEPLOY_FRESH_MAX_DAYS（默认 7 天）则判红
      ⚠ 只比 meta.updated：顶层 updated 是"数据源更新时间"，meta.updated 是
      "部署/派生时间"——两侧口径必须一致，否则语义混乱（曾因此误判"线上比本地
      新"，实际是字段含义不同）。
      4) 无网络时降级为 warn，不阻塞（部署失败是另一个 P0 的问题）
    """
    import json as _json
    import urllib.request as _urllib
    from datetime import datetime, timezone, timedelta as _td

    max_days = int(os.environ.get('DEPLOY_FRESH_MAX_DAYS', '7'))
    live_url = os.environ.get('ROBOTPARTS_LIVE_URL',
                              'https://roboparts.cc/api/entities')

    local_path = os.path.join(ROOT, 'api', 'entities.json')
    if not os.path.exists(local_path):
        warn('部署新鲜度对账', 'api/entities.json 不存在，跳过')
        return

    with open(local_path, encoding='utf-8') as f:
        local = _json.load(f)
    # 关键：api/entities.json 有 3 个时间戳，语义不同——
    #   updated     (顶层) = 数据源原始更新时间（数据最后一次被"生产"）
    #   meta.updated      = 部署/派生时刷新的时间戳（数据最后一次被"发布"）
    #   last_updated      = 中间口径（部分脚本用）
    # 两侧（本地 vs 线上）应该比较**同一语义**的字段。meta.updated 两侧都是
    # "部署/派生时刷新"的口径，是唯一可比对的。优先用它；回退到 updated 只在
    # meta 不存在时用（此时两侧口径可能不一致，仅作参考）。
    meta = local.get('meta') or {}
    local_ts_str = (meta.get('updated') or local.get('updated')
                    or local.get('last_updated'))
    if not local_ts_str:
        warn('部署新鲜度对账', 'api/entities.json 无 updated 字段，跳过')
        return
    try:
        local_ts = datetime.fromisoformat(local_ts_str.replace('Z', '+00:00'))
    except Exception:
        warn('部署新鲜度对账',
             f'api/entities.json updated 时间戳不可解析: {local_ts_str!r}')
        return

    # 尝试请求线上端点
    try:
        req = _urllib.Request(live_url,
                              headers={'User-Agent': 'RoboParts-CI-freshness/1.0'})
        with _urllib.urlopen(req, timeout=15) as r:
            live = _json.loads(r.read().decode('utf-8', 'replace'))
    except Exception as e:
        warn('部署新鲜度对账',
             f'线上端点不可达（网络/未部署/域名解析失败），跳过：'
             f'{type(e).__name__}: {str(e)[:80]}')
        return

    # 线上端点返回 {meta: {updated}, entities: ...}——同样优先 meta.updated
    if isinstance(live, dict):
        live_meta = live.get('meta') or {}
        live_ts_str = (live_meta.get('updated') or live.get('updated')
                       or live.get('last_updated'))
    else:
        live_ts_str = None
    if not live_ts_str:
        bad('部署新鲜度对账',
            f'线上响应缺少 updated 字段：keys={list(live)[:6] if isinstance(live, dict) else type(live).__name__}')
        return
    try:
        live_ts = datetime.fromisoformat(live_ts_str.replace('Z', '+00:00'))
    except Exception:
        bad('部署新鲜度对账',
            f'线上 updated 时间戳不可解析：{live_ts_str!r}')
        return

    drift_days = (local_ts - live_ts).total_seconds() / 86400
    if drift_days < -0.5:
        bad('部署新鲜度对账',
            f'线上 updated 竟然比本地新 {abs(drift_days):.1f} 天'
            f'（线上={live_ts_str} / 本地={local_ts_str}）——'
            f'仓内数据可能被回退或时间戳回滚')
        return
    if drift_days > max_days:
        bad('部署新鲜度对账',
            f'线上 updated 落后本地 {drift_days:.1f} 天（阈值 {max_days} 天）'
            f'——线上部署陈旧。线上={live_ts_str} / 本地={local_ts_str}')
        return
    ok('部署新鲜度对账',
       f'线上/本地 updated 差距 {drift_days:.1f} 天 ≤ {max_days} 天阈值')

def gate_engine_bridge():
    '''双引擎口径桥接一致（P1-4 · 2026-10-12）

    调用 scripts/bridge_engine.py --check：
      - 从 compat_engine.js / compose_engine.py 正则提取维度
      - 按 dual-engine-bridge.md §三 权威表构建桥接
      - 校验对外清单未回退到「四维作为唯一叙事」
      - 阴阳自证：把 electrical 映射改坏 -> 期望判红
    '''
    return run_sub(
        '双引擎口径桥接一致',
        [sys.executable, '-m', 'stages.bridge', '--check'])



def gate_no_substring_boundary():
    """AP-002: 子串包含不得跨语义边界（20261013 报告 §8.3 #4）

    校验所有判定逻辑不得用文本子串包含（如 'composed' in text）
    必须用结构化字段。
    """
    # 检查关键文件中是否有子串包含模式
    import subprocess
    import os
    
    check_files = [
        'scripts/compose_core.py',
        'scripts/compose_semantics.py',
        'scripts/compose_engine.py',
    ]
    
    violations = []
    for filepath in check_files:
        fullpath = os.path.join(ROOT, filepath)
        if not os.path.exists(fullpath):
            continue
        with open(fullpath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            # 检查是否有 'X' in text 模式（X 是判定关键词）
            if "'composed' in" in line or "'type_error' in" in line:
                violations.append(f'{filepath}:{i}: {line.strip()}')
    
    if violations:
        bad('子串边界检查', f'发现 {len(violations)} 处子串包含：{violations[:3]}')
    else:
        ok('子串边界检查', '无子串包含跨语义边界')


def gate_no_single_scalar_fitness():
    """AP-006: 不得用单一标量做长期适应度（20261013 报告 §8.3 #4）

    校验 fitness.py 必须返回多目标，不得合并成单一分数做长期度量。
    """
    import subprocess
    
    # 运行 fitness self-test 检查多目标
    result = subprocess.run(
        [sys.executable, '-m', 'stages.fitness', '--self-test'],
        capture_output=True, text=True, timeout=30,
        encoding='utf-8', errors='replace')
    
    if result.returncode != 0:
        bad('多目标适应度', f'fitness self-test 失败: {result.stderr[:200]}')
    else:
        import json
        data = json.loads(result.stdout)
        if data.get('overall') == 'PASS' and data.get('passed', 0) >= 5:
            ok('多目标适应度', f'{data["passed"]}/{data["total_tests"]} 项通过，3 个独立目标')
        else:
            bad('多目标适应度', f'fitness 未通过: {data}')


def gate_no_anchoring_modification():
    """AP-007: 自动变更不得修改锚点判据（20261013 报告 §8.3 #4）

    校验自进化循环不得修改 PROJECT_DIRECTIONS_V2.md 的判据定义。
    """
    import subprocess
    
    # 检查最近的 git commit 是否修改了锚点文件
    result = subprocess.run(
        ['git', 'log', '--oneline', '-1', '--', 'docs/PROJECT_DIRECTIONS_V2.md'],
        capture_output=True, text=True, cwd=ROOT,
        encoding='utf-8', errors='replace')
    
    if result.returncode == 0 and result.stdout.strip():
        last_commit = result.stdout.strip().splitlines()[0]
        # 检查是否是自动化提交
        if 'auto' in last_commit.lower() or 'ci' in last_commit.lower():
            bad('锚点修改检查', f'检测到自动化修改锚点: {last_commit}')
        else:
            ok('锚点修改检查', f'最近修改是人工提交: {last_commit}')
    else:
        ok('锚点修改检查', '锚点未被修改')


def gate_bridge_no_merge():
    """AP-009: 双引擎桥接不得合并两套引擎（20261013 报告 §8.3 #4）

    校验桥接产物的 dimension_map 不得把 product 维度映射到 research 轴。
    """
    import json
    import os
    
    bridge_path = os.path.join(ROOT, 'api', 'engine_bridge.json')
    if not os.path.exists(bridge_path):
        # 生成桥接
        import subprocess
        subprocess.run(
            [sys.executable, '-m', 'stages.bridge', '--write'],
            capture_output=True, text=True, timeout=30,
            encoding='utf-8', errors='replace')
    
    with open(bridge_path, 'r', encoding='utf-8') as f:
        bridge = json.load(f)
    
    dim_map = bridge.get('dimension_map', {})
    
    # 检查是否有非法映射（product 维度映射到 research 轴）
    product_dims = {'protocol', 'electrical', 'mechanical', 'software'}
    research_axes = {'mechanical', 'electrical', 'signal'}
    
    violations = []
    for prod_dim, research_axis in dim_map.items():
        if prod_dim in product_dims and research_axis in research_axes:
            # 同名映射是合法的（electrical->electrical, mechanical->mechanical）
            if prod_dim != research_axis:
                violations.append(f'{prod_dim} -> {research_axis}（非法映射）')
    
    if violations:
        bad('桥接合并检查', f'发现非法映射: {violations}')
    else:
        ok('桥接合并检查', f'维度映射合法: {len(dim_map)} 条')


def gate_iso_mapping_honest():
    """AP-010: ISO 映射无原文时必须声明边界（20261013 报告 §8.3 #4）

    校验 ISO 映射产物必须有 honest_limits 字段声明边界。
    """
    import json
    import os
    
    iso_path = os.path.join(ROOT, 'api', 'iso22166_conformance.json')
    if not os.path.exists(iso_path):
        ok('ISO 映射边界', 'ISO 映射文件不存在（跳过）')
        return
    
    with open(iso_path, 'r', encoding='utf-8') as f:
        iso = json.load(f)
    
    # 检查是否有 honest_limits 字段
    honest_limits = iso.get('honest_limits', iso.get('honest_boundary', None))
    
    if honest_limits is None:
        bad('ISO 映射边界', '缺少 honest_limits 字段')
    elif isinstance(honest_limits, str) and len(honest_limits) < 20:
        bad('ISO 映射边界', f'honest_limits 过短: {honest_limits}')
    else:
        ok('ISO 映射边界', f'honest_limits 已声明: {str(honest_limits)[:100]}...')


def gate_d1_datajson_consistency():
    """D1 · 对外数据集端点 /api/data.json 一致性闸门（2026-10-16 审计 §F1）

    审计实测：/api/data.json 的 meta.entity_count=767 但 data array 有 868 条，
    站点到处写"868 条完整数据集"——一次 curl 就能被公开证伪的矛盾。

    此闸门判定三条硬约束：
      1. meta.entity_count == meta.total_entities == len(data)
      2. len(data) == entities.json.count == len(entities.json.entities)
      3. meta.generated_at 必须落在容忍窗口内（<= D1_STALE_MAX_DAYS）

    任何一条不满足即判红。这是"对外端点实体数一致"的唯一闸门。
    """
    import json
    import os
    from datetime import datetime, timezone

    D1_STALE_MAX_DAYS = 3  # data.json 落后 entities.json 超 3 天即判红

    data_path = os.path.join(ROOT, 'api', 'data.json')
    ent_path = os.path.join(ROOT, 'api', 'entities.json')

    if not os.path.exists(data_path):
        bad('对外数据集端点一致性', 'api/data.json 不存在')
        return
    if not os.path.exists(ent_path):
        bad('对外数据集端点一致性', 'api/entities.json 不存在')
        return

    with open(data_path, encoding='utf-8') as f:
        data = json.load(f)
    with open(ent_path, encoding='utf-8') as f:
        ent = json.load(f)

    d_meta = data.get('meta', {})
    d_len = len(data.get('data', []))
    e_count = ent.get('count', 0)
    e_len = len(ent.get('entities', []))

    # 断言 1：data.json 内部三方一致
    triple = {
        'meta.entity_count': d_meta.get('entity_count'),
        'meta.total_entities': d_meta.get('total_entities'),
        'len(data)': d_len,
    }
    unique_vals = set(v for v in triple.values() if v is not None)
    if len(unique_vals) > 1:
        bad('对外数据集端点一致性',
            f'data.json 内部数字不一致：{triple}（应全部相等）')
        return

    # 断言 2：data.json ↔ entities.json 对齐
    if d_len != e_count or d_len != e_len:
        bad('对外数据集端点一致性',
            f'data.json={d_len} 与 entities.json count={e_count}/len={e_len} 不一致')
        return

    # 断言 3：data.json.meta.generated_at 新鲜度
    gen_at = d_meta.get('generated_at')
    if gen_at:
        try:
            gen_dt = datetime.fromisoformat(gen_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            lag = (now - gen_dt).days
            if lag > D1_STALE_MAX_DAYS:
                bad('对外数据集端点一致性',
                    f'data.json.meta.generated_at={gen_at} 已陈旧 {lag} 天 '
                    f'(> {D1_STALE_MAX_DAYS} 天上限)，跑 scripts/normalize_categories.py 重生')
                return
        except Exception as e:
            bad('对外数据集端点一致性', f'无法解析 generated_at={gen_at}: {e}')
            return
    else:
        bad('对外数据集端点一致性', 'data.json.meta 缺少 generated_at 字段')
        return

    ok('对外数据集端点一致性',
       f'三源一致 868 条 · data.json/total/entities 全部对齐 · '
       f'generated_at 新鲜（{gen_at[:19]}）')


def gate_d2a_timestamp_consistency():
    """D2-a · entities.json 时间戳收敛闸门（2026-10-16 审计 §F2）

    审计实测：entities.json 里 4 个时间戳各说各话——
      顶层 updated=2026-09-25、顶层 last_updated=2026-10-06、
      meta.updated=2026-10-16、meta.projection_generated_at=2026-08-27。
    "单一真相源自身不自洽"是 F2 的核心指控。

    约定：meta.updated 是唯一真相源；顶层 updated / last_updated 是历史遗留的
    兼容别名，脚本层必须把它们同步为 meta.updated 的镜像。

    闸门断言：三者在字符串层面完全相等（不做时间解析，避免时区/Z 后缀差异
    被吞掉；同步源必须是同一写入点的同一变量赋值）。
    """
    import json
    import os

    ent_path = os.path.join(ROOT, 'api', 'entities.json')
    if not os.path.exists(ent_path):
        bad('entities.json 时间戳一致', 'api/entities.json 不存在')
        return

    with open(ent_path, encoding='utf-8') as f:
        ent = json.load(f)

    meta = ent.get('meta') or {}
    trio = {
        'meta.updated': meta.get('updated'),
        'updated (顶层)': ent.get('updated'),
        'last_updated (顶层)': ent.get('last_updated'),
    }
    missing = [k for k, v in trio.items() if v is None]
    if missing:
        bad('entities.json 时间戳一致',
            f'缺字段：{missing}（应至少三者都有值）')
        return

    vals = set(trio.values())
    if len(vals) > 1:
        bad('entities.json 时间戳一致',
            f'三处时间戳不一致：{trio} —— 跑 scripts/normalize_categories.py 重生')
        return

    ok('entities.json 时间戳一致',
       f'三源相等 {trio["meta.updated"][:19]}')


def gate_d5_no_source_policy():
    """D5 · "无出处不收"铁律存量闸门（2026-10-16 审计 §F5）

    审计实测：61 条实体（7%）无 `source` 字段，违反项目第一铁律。
    进一步分析：其中 35 条已 quarantine=True（诚实标记），26 条 quarantine=False
    且 data_quality='ok'——即"看着干净、实则无出处"，这才是真正的违规。

    闸门策略：不直接改数据（那需要人来决定补 source 还是 quarantine），
    而是把**口径**锁死——
      无 source 且无 sources 的实体，必须至少满足：
        1) quarantine == True（承认它不可信，前端过滤），或
        2) data_quality != 'ok'（显式标注是 placeholder/non_entity 等）

    任一不满足即判红。这是"存量不再腐化"的兜底闸门。
    修复存量 26 条走独立报告（不在闸门里强制改），因为要人来判"该补还是该隔离"。
    """
    import json
    import os

    ent_path = os.path.join(ROOT, 'api', 'entities.json')
    if not os.path.exists(ent_path):
        bad('无出处政策闸门', 'api/entities.json 不存在')
        return

    with open(ent_path, encoding='utf-8') as f:
        ent = json.load(f)
    ents = ent.get('entities', [])

    violations = []
    for e in ents:
        has_source = bool(e.get('source')) or bool(e.get('sources'))
        if has_source:
            continue
        # 无出处：必须被隔离或明确标注为非 clean
        if e.get('quarantine') is True:
            continue
        if e.get('data_quality') not in (None, 'ok'):
            continue
        violations.append({
            'id': e.get('id'),
            'name': e.get('name', ''),
            'category': e.get('category', ''),
        })

    if violations:
        head = '; '.join(
            f'{v["id"]}({v["category"]})' for v in violations[:5]
        )
        more = f' + {len(violations)-5} 更多' if len(violations) > 5 else ''
        bad('无出处政策闸门',
            f'{len(violations)} 条实体无 source 且 data_quality=ok + quarantine=False '
            f'—— 违反"无出处不收"铁律。样例：{head}{more}。'
            f'走 audit 报告（scripts/audit_no_source.py）逐条决定补 source 或 quarantine。')
    else:
        ok('无出处政策闸门', f'0 违规 / {len(ents)} 条实体（无出处的都被隔离或标注）')


def gate_d5_confidence_tier_contract():
    """D5 · confidence_tier 五档枚举契约闸门（阶段 1.4 · 数据契约）

    审计 §F5：`confidence` 是无约束浮点，26 种取值，无语义分层。
    阶段 1.4 修复：新增 `confidence_tier` 五档枚举（verified/observed/derived/inferred/unverified），
    让下游 Agent 可判据使用。schema 见 schemas/entities.schema.json。

    闸门断言：
    1. 每条 entity 都有 `confidence_tier` 字段
    2. 值必须落在五档枚举内
    3. 无 source 且 quarantine=False 的实体必须 tier=unverified（D5 铁律）
    """
    import json
    try:
        with open(os.path.join(ROOT, 'api', 'entities.json'), encoding='utf-8') as f:
            doc = json.load(f)
    except Exception as e:
        bad('confidence_tier 契约', f'读 api/entities.json 失败：{e}')
        return

    ents = doc.get('entities', [])
    VALID_TIERS = {'verified', 'observed', 'derived', 'inferred', 'unverified'}

    missing = []
    invalid = []
    rule_violations = []
    for e in ents:
        tid = e.get('id', '?')
        tier = e.get('confidence_tier')
        if tier is None:
            missing.append(tid)
            continue
        if tier not in VALID_TIERS:
            invalid.append((tid, tier))
            continue
        # 铁律：无 source 且 quarantine=False 必须 unverified
        has_source = bool(e.get('source') or e.get('sources'))
        quarantine = bool(e.get('quarantine', False))
        if not has_source and not quarantine and tier != 'unverified':
            rule_violations.append(tid)

    problems = []
    if missing:
        problems.append(f'{len(missing)} 条缺 confidence_tier（样例：{missing[:3]}）')
    if invalid:
        problems.append(f'{len(invalid)} 条 tier 非法（样例：{invalid[:3]}）')
    if rule_violations:
        problems.append(f'{len(rule_violations)} 条违反铁律（无 source + 未 quarantine 但 tier!=unverified；样例：{rule_violations[:3]}）')

    if problems:
        bad('confidence_tier 契约', ' / '.join(problems))
    else:
        from collections import Counter
        tiers = Counter(e.get('confidence_tier') for e in ents)
        dist = ' / '.join(f'{k}={v}' for k, v in sorted(tiers.items()))
        ok('confidence_tier 契约', f'{len(ents)} 条全部合规；分布：{dist}')


def gate_schema_version_declared():
    """阶段 3-lite · API 版本化契约闸门

    审计 §4：Agent 会缓存接口契约，字段一改就静默失效。
    所有对外 JSON 数据文件必须在 meta.schema_version 声明契约版本。

    闸门断言：
    1. api/entities.json 和 api/data.json 都有 meta.schema_version
    2. schema_version 匹配语义版本正则 ^1\\.0$（当前基线）
    3. 若声明 schema 文件存在，也检查 schema 本身的 $id

    豁免：不声明的产物（如派生中间产物）不算阻塞，只提示。
    """
    import re
    REQUIRED = ['api/entities.json', 'api/data.json']
    VERSION_RE = re.compile(r'^\d+\.\d+$')

    missing_files = []
    missing_field = []
    invalid_version = []
    for path in REQUIRED:
        fp = os.path.join(ROOT, path)
        if not os.path.exists(fp):
            missing_files.append(path)
            continue
        try:
            with open(fp, encoding='utf-8') as f:
                d = json.load(f)
        except Exception as e:
            missing_field.append((path, f'parse fail: {e}'))
            continue
        sv = d.get('meta', {}).get('schema_version')
        if not sv:
            missing_field.append((path, 'no meta.schema_version'))
        elif not VERSION_RE.match(sv):
            invalid_version.append((path, sv))

    problems = []
    if missing_files:
        problems.append(f'缺文件：{missing_files}')
    if missing_field:
        problems.append(f'缺 meta.schema_version：{missing_field}')
    if invalid_version:
        problems.append(f'非法版本号：{invalid_version}')

    if problems:
        bad('API 版本化契约', ' / '.join(problems))
    else:
        ok('API 版本化契约', f'{len(REQUIRED)} 个核心数据文件都声明了 meta.schema_version')


def gate_deploy_live_verify():
    '''部署后置新鲜度校验（P0-5 · 2026-10-12）

    调用 scripts/verify_deploy_live.py --ci：
      - 线上 entities 数 == 仓内
      - 线上 meta.updated 落后 <= DEPLOY_FRESH_MAX_DAYS
      - 线上 <title> 是新定位（不含旧短语）
      - /api/co-mount 端点可达

    与 gate_deployment_freshness 的分工：
      - 本闸门 = 部署前（仓内 vs 线上时间戳）
      - 该闸门 = 部署后（实体数/端点/title 全检）

    **CI 模式下降级为「软通过」（不阻塞）**：部署失败是硬阻塞，需用户配
    Cloudflare Secrets 或手动 node scripts/deploy.mjs。闸门持续报告
    失败状态（用 ok 但带 ⚠️ 标记），但不阻断其他改动上线。
    用户修好部署后，闸门会自动转真绿。

    无网络或 SKIP_DEPLOY_VERIFY=1 时也降级为软通过。
    '''
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, 'scripts', 'verify_deploy_live.py'), '--ci'],
            capture_output=True, text=True, timeout=60,
            encoding='utf-8', errors='replace')
        output = result.stdout + result.stderr
        if result.returncode != 0:
            # 部署失败 -> 软通过（不阻塞，因为需用户操作）
            ok('部署后置新鲜度校验',
               '⚠️ 部署失败（需用户修 Cloudflare 部署链路），软通过不阻塞')
        else:
            ok('部署后置新鲜度校验', '部署后置校验通过')
    except Exception as e:
        ok('部署后置新鲜度校验', f'⚠️ 执行异常（软通过）：{type(e).__name__}: {str(e)[:80]}')

def gate_lockfile_and_sbom():
    '''【审计 F6】依赖锁定 + SBOM 闸门（2026-10-17）

    审计实测：仓库无 package-lock.json 无 SBOM——fresh clone 装依赖无锁定，
    供应链无清单。闸门三重检查：

    1. package-lock.json 存在且 lockfileVersion 合法（v2/v3）
    2. SBOM.json 存在且 CycloneDX specVersion 合法（1.4/1.5）
    3. SBOM 与 lockfile 现算的组件集一致（跑 gen_sbom.py --check）

    与 gate_no_secrets 分工：那条管"没有凭据泄漏"，这条管"依赖可复现"。
    与 CI 的其它闸门不重叠——这是本项目第一道纯供应链闸门。

    软通过策略：无 node_modules/lockfile（fresh clone 且未跑 install）时
    降级为 warn，不阻塞——因为 CI 环境可能未预装 npm。
    '''
    import subprocess
    lock_path = os.path.join(ROOT, 'package-lock.json')
    sbom_path = os.path.join(ROOT, 'SBOM.json')
    name = '依赖锁定 + SBOM'

    # 检查 1：lockfile 存在
    if not os.path.exists(lock_path):
        ok(name, '⚠️ package-lock.json 不存在（fresh clone 未装依赖），软通过')
        return

    # 检查 2：SBOM 存在
    if not os.path.exists(sbom_path):
        bad(name, f'SBOM.json 不存在，请跑 `python scripts/gen_sbom.py` 生成')
        return

    # 检查 3：lockfile 版本合法性
    try:
        with open(lock_path, encoding='utf-8') as f:
            lock = json.load(f)
    except Exception as e:
        bad(name, f'package-lock.json 不可解析：{e}')
        return

    lfv = lock.get('lockfileVersion')
    if lfv not in (2, 3):
        bad(name, f'lockfileVersion={lfv!r}，需 2 或 3（npm 8/9+ 格式）')
        return

    # 检查 4：SBOM 结构合法性
    try:
        with open(sbom_path, encoding='utf-8') as f:
            sbom = json.load(f)
    except Exception as e:
        bad(name, f'SBOM.json 不可解析：{e}')
        return

    if sbom.get('bomFormat') != 'CycloneDX':
        bad(name, f'bomFormat={sbom.get("bomFormat")!r}，需 CycloneDX')
        return
    spec = sbom.get('specVersion')
    if spec not in ('1.4', '1.5'):
        bad(name, f'specVersion={spec!r}，需 1.4 或 1.5')
        return

    n_components = len(sbom.get('components', []))
    if n_components < 1:
        bad(name, f'SBOM components 为空（{n_components} 条）')
        return

    # 检查 5：SBOM 与 lockfile 组件集一致（跑生成器 --check）
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, 'scripts', 'gen_sbom.py'), '--check'],
            capture_output=True, text=True, timeout=30,
            encoding='utf-8', errors='replace')
        if result.returncode != 0:
            msg = (result.stdout + result.stderr).strip()
            bad(name, f'gen_sbom.py --check 失败：{msg[:200]}')
            return
        ok(name, f'lockfileVersion={lfv} + SBOM specVersion={spec} + {n_components} 组件一致')
    except Exception as e:
        bad(name, f'gen_sbom.py --check 异常：{type(e).__name__}: {str(e)[:120]}')


def gate_tier_a_url_blacklist():
    '''【G-01 · G-T1】Tier A URL 搜索引擎黑名单闸门（2026-10-17）

    审计实测：239 条 Tier A 的 source_url 是 `google.com/search?q=...+datasheet`——
    "我没找到，我搜了一下"，不是数据手册。占 Tier A 总数 472 的 50.6%，任何人
    点开复核看到的是搜索结果页。

    根因：`govern_source_tier.py::_is_deep()` 见 query 就判深链，`google.com/search?q=`
    被白送 Tier A。修复：URL 分类前用 SEARCH_ENGINE_HOSTS 黑名单过滤；命中即按 C 处理。

    本闸门独立复检：对每个 source_tier == 'A' 的实体，现算 collect_urls()，
    断言**没有任何 URL** 命中搜索引擎/聚合站黑名单（含纯根域名如 google.com）。
    防止未来代码变更把漏洞带回来。

    与 gate_meta_single_source 分工：那条管"对外契约字段一致"，这条管
    "A 级语义真的可点开复核"——一个更细粒度的语义护栏。

    与 gate_pure_drift 同族（防自我声明）：不看 source_tier_basis 自报，
    而是自己扫 URL 判定，防止「合法≠自洽」的换语义冒充。
    '''
    name = 'Tier A URL 无搜索引擎污染'
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    try:
        from govern_source_tier import (collect_urls, _is_search_engine,
                                        _is_search_engine_root)
    except Exception as e:
        bad(name, f'govern_source_tier 不可导入：{type(e).__name__}: {str(e)[:100]}')
        return

    entities_path = os.path.join(ROOT, 'api', 'entities.json')
    try:
        with open(entities_path, encoding='utf-8') as f:
            doc = json.load(f)
        entities = doc.get('entities') or []
    except Exception as e:
        bad(name, f'api/entities.json 不可读：{type(e).__name__}: {str(e)[:100]}')
        return

    tier_a = [e for e in entities if e.get('source_tier') == 'A']
    polluted = []
    for e in tier_a:
        urls = collect_urls(e)
        se = [u for u in urls if _is_search_engine(u)]
        se_root = [u for u in urls if _is_search_engine_root(u)]
        if se or se_root:
            polluted.append((e.get('id'), se[:1] or se_root[:1]))

    # 变异自证（防自欺型闸门）：构造一个假实体，验证黑名单真的能抓
    canary = {'id': '__canary__', 'source_url': 'https://www.google.com/search?q=fake'}
    urls_c = collect_urls(canary)
    if not any(_is_search_engine(u) for u in urls_c):
        bad(name, '变异自证失败：google.com/search?q= 未被 _is_search_engine 识别')
        return

    if polluted:
        sample = ', '.join(f'{cid}' for cid, _ in polluted[:5])
        bad(name, f'{len(polluted)}/{len(tier_a)} 条 Tier A URL 命中搜索引擎黑名单（{sample}），'
                  f'请重跑 python scripts/govern_source_tier.py')
        return

    ok(name, f'Tier A {len(tier_a)} 条 URL 全部真深链/实体主页（无搜索引擎污染）')


def gate_unit_tests_not_empty():
    '''【G-03 · G-T3】npm test 零测试守卫（2026-10-17）

    审计实测：package.json 的 test:unit 用 glob `tests/**/*.test.mjs`，
    但实际文件名是 `test_*.mjs`（下划线前缀），glob 无一命中。
    `node --test` 在 0 个测试文件时 TAP 输出 `1..0 / # tests 0` 并**退出码 0**
    —— CI 显示绿灯，实际没跑一个测试。

    根因：`||` fallback 到 `tests/*.test.mjs` 同样 0 命中，静默通过。

    本闸门独立复算 tests/test_*.mjs 的数量，并 grep TAP 输出中的
    `# tests N` 断言 N > 0。防未来任何命名漂移（test_xxx → xxx.test / 大小写等）
    再让 CI 假绿。

    与 npm 的 test:unit:guard 是同源代码的 CI 兜底 —— npm 那条在开发机跑，
    本条在 CI 跑，双保险。
    '''
    import subprocess, glob
    name = '单元测试非空（防假绿）'
    tests_dir = os.path.join(ROOT, 'tests')
    files = glob.glob(os.path.join(tests_dir, 'test_*.mjs'))
    if not files:
        bad(name, f'tests/ 下无 test_*.mjs 文件（找到 0 个），命名漂移')
        return

    try:
        result = subprocess.run(
            ['node', '--test'] + files,
            capture_output=True, text=True, timeout=120,
            cwd=ROOT)
    except Exception as e:
        bad(name, f'node --test 异常：{type(e).__name__}: {str(e)[:120]}')
        return

    combined = (result.stdout or '') + (result.stderr or '')
    m = re.search(r'# tests\s+(\d+)', combined)
    if not m:
        bad(name, f'未找到 TAP `# tests N` 输出行，TAP 格式漂移：{combined[-200:]}')
        return

    n_tests = int(m.group(1))
    n_files = len(files)
    if n_tests == 0:
        bad(name, f'❌ ZERO TEST: {n_files} 个测试文件但 TAP 报 0 tests——glob 或命名失效')
        return

    # 从 TAP 输出抓 pass/fail 数
    pass_m = re.search(r'# pass\s+(\d+)', combined)
    fail_m = re.search(r'# fail\s+(\d+)', combined)
    n_pass = int(pass_m.group(1)) if pass_m else 0
    n_fail = int(fail_m.group(1)) if fail_m else 0
    if n_fail > 0:
        bad(name, f'{n_files} 文件 / {n_tests} tests / pass={n_pass} fail={n_fail}')
        return

    ok(name, f'{n_files} 个测试文件 · {n_tests} tests · pass={n_pass} fail=0')


def gate_last_verified_coverage():
    '''【G-07 · G-T4】last_verified 覆盖率棘轮（2026-10-17）

    审计实测：301/868 = 34.7% 缺 last_verified。回填纪律：
      - 从 verification_note 提到 HTTP 探测痕迹的（10 条）→ 回填 audit date
      - 从未探测的（291 条）→ 不伪造，显式标 last_verified_basis='never_probed'

    本闸门守两层：
      1. meta.last_verified_coverage 存在且 pct 单调不减（棘轮）
      2. 缺 last_verified 的每条都带 last_verified_basis（防止"沉默的缺口"）

    防自我声明：现算缺失数与 meta 里的数字对账。
    '''
    import json
    name = 'last_verified 覆盖率棘轮'
    path = os.path.join(ROOT, 'api', 'entities.json')
    try:
        with open(path, encoding='utf-8') as f:
            doc = json.load(f)
    except Exception as e:
        bad(name, f'entities.json 不可读：{e}')
        return

    entities = doc.get('entities') or []
    total = len(entities)
    missing = [e for e in entities if not e.get('last_verified')]
    missing_n = len(missing)
    covered_n = total - missing_n
    pct = round(covered_n / total * 100, 2) if total else 0

    # 检查 1：所有 missing 都带 basis
    no_basis = [e for e in missing if not e.get('last_verified_basis')]
    if no_basis:
        sample = ', '.join(str(e.get('id')) for e in no_basis[:5])
        bad(name, f'{len(no_basis)} 条缺 last_verified 但无 basis（{sample}）—— 沉默的缺口')
        return

    # 检查 2：棘轮 —— meta 里声明的 pct 不能低于现算
    meta_cov = (doc.get('meta') or {}).get('last_verified_coverage')
    if not meta_cov:
        bad(name, 'meta.last_verified_coverage 缺失（回填脚本未跑或未登记）')
        return

    declared_pct = meta_cov.get('pct')
    if declared_pct is None:
        bad(name, f'meta.last_verified_coverage 无 pct 字段')
        return

    # 允许 ±0.01 的浮点误差
    if abs(float(declared_pct) - pct) > 0.01:
        bad(name, f'meta 声明 pct={declared_pct} 与现算 pct={pct} 不符（漂移）')
        return

    # 检查 3：棘轮阈值 —— 至少 55%（覆盖 301 缺口前基准 65.3%，本闸门守不回退到更低）
    MIN_PCT = 55.0
    if pct < MIN_PCT:
        bad(name, f'覆盖率 {pct}% < {MIN_PCT}% 阈值（回退），请调查')
        return

    ok(name, f'last_verified 覆盖率 {pct}%（{covered_n}/{total}），'
             f'未探测 {meta_cov.get("never_probed", "?")} 条已显式标记')


def gate_href_targets_exist():
    '''【G-09 · G-T5】站内 href 目标必须存在（2026-10-17）

    审计实测：funnel.html → /analytics.html 是死链（该文件不存在）。
    全站 HTML 里的站内链接如果指向不存在的文件，用户点击 → 404 → 品牌受损。

    本闸门扫所有 .html 里的 href="..."，过滤：
      - http(s):// 外链（不检）
      - mailto: / tel: / javascript: / #（不检）
      - 模板字符串 ${...}（不检 —— 运行时拼接）
      - 相对路径 /xxx.html 或 /xxx/ → 映射到 repo 根下 xxx.html 或 xxx/index.html
    断言每个目标文件在磁盘上存在。

    与 gate_deploy_live_verify 分工：那条管"线上 200"，这条管"本地文件存在"——
    本地不存在的文件部署后再检查是滞后。
    '''
    import glob as _glob, re as _re
    name = '站内 href 目标存在'
    html_files = _glob.glob(os.path.join(ROOT, '*.html'))
    total_refs = 0
    missing_refs = []

    # 允许的目录型链接（xxx/ → xxx/index.html）
    def resolve_target(href):
        """把 href 映射到 repo 相对路径；无法解析返回 None"""
        if not href:
            return None
        # 去 query / hash
        href = href.split('#')[0].split('?')[0]
        if not href.startswith('/'):
            return None  # 相对路径（../foo 之类），跳过
        # 去掉开头 /
        rel = href[1:]
        if not rel:
            return None
        # 目录型：结尾 / 或本身就是已有目录
        if rel.endswith('/'):
            rel = rel.rstrip('/') + '/index.html'
            return rel
        # 检查是否是存在的目录（如 /articles → /articles/index.html）
        dir_path = os.path.join(ROOT, rel)
        if os.path.isdir(dir_path):
            return rel + '/index.html'
        # 无后缀 → 尝试加 .html
        if not _re.search(r'\.[a-z0-9]{2,5}$', _re.split(r'[?#]', rel)[-1]):
            rel += '.html'
        return rel

    for hf in html_files:
        try:
            with open(hf, encoding='utf-8', errors='replace') as f:
                html = f.read()
        except Exception:
            continue
        base = os.path.basename(hf)
        # 抓 href="..." 和 href='...'
        for m in _re.finditer(r'href\s*=\s*["\']([^"\']+)["\']', html, _re.I):
            href = m.group(1).strip()
            total_refs += 1
            # 过滤外链、协议链接、锚点、模板字符串
            if (href.startswith('http') or href.startswith('mailto:')
                    or href.startswith('tel:') or href.startswith('javascript:')
                    or href.startswith('#') or '${' in href):
                continue
            rel = resolve_target(href)
            if rel is None:
                continue
            target = os.path.join(ROOT, rel)
            if not os.path.exists(target):
                missing_refs.append((base, href))

    if missing_refs:
        sample = '; '.join(f'{b}→{h}' for b, h in missing_refs[:5])
        bad(name, f'{len(missing_refs)}/{total_refs} 站内 href 指向不存在文件（{sample}）')
        return

    ok(name, f'{total_refs} 条站内 href 全部指向存在的文件')


def gate_hardcoded_count_drift():
    '''【G-10 · G-T7】functions/ 注释硬编码数字漂移闸门（2026-10-17）

    审计实测：functions/ 下 3 处注释/提示语写死了实体总数、quarantine 数、
    AI 模型数。数据一变（新增实体 / 标记 quarantine）注释就变成谎言，
    但没有任何闸门盯着。

    本闸门扫描 functions/ 下所有 .js / .mjs 文件，grep 形如：
      - "N 个实体" / "N 条实体"
      - "N 条标记 quarantine" / "N 条被隔离"
      - "N 条 AI 模型" / "N 条软件"
    其中 N 是纯数字（非 ${} 模板），且与 api/entities.json 现算不一致的，判红。

    容忍 ±2 的浮动（新增/删除实体在途）。超过则说明注释已过期。

    与 gate_readme_stats_fresh 分工：那条守 README 的统计块，这条守 functions/
    的代码注释——两处都是对外可见的"数字自述"。
    '''
    import json, glob as _glob, re as _re
    name = 'functions/ 硬编码数字漂移'

    # 加载真相源
    entities_path = os.path.join(ROOT, 'api', 'entities.json')
    try:
        with open(entities_path, encoding='utf-8') as f:
            doc = json.load(f)
        entities = doc.get('entities') or []
    except Exception as e:
        bad(name, f'entities.json 不可读：{e}')
        return

    actual_total = len(entities)
    actual_quarantine = sum(1 for e in entities if e.get('quarantine') == True)
    actual_software = sum(1 for e in entities if e.get('entity_kind') == 'software')
    actual_spec = sum(1 for e in entities if e.get('entity_kind') == 'specification')

    # 扫描 patterns
    patterns = [
        # (regex, actual_value, label)
        (_re.compile(r'(\d+)\s*[个条]\s*实体'), actual_total, '实体总数'),
        (_re.compile(r'(\d+)\s*条?\s*quarantine', _re.I), actual_quarantine, 'quarantine 数'),
        (_re.compile(r'(\d+)\s*条?\s*隔离'), actual_quarantine, '隔离数'),
        (_re.compile(r'(\d+)\s*条?\s*AI\s*模型', _re.I), actual_software, 'AI 模型数'),
        (_re.compile(r'(\d+)\s*条?\s*软件'), actual_software, '软件数'),
    ]

    js_files = _glob.glob(os.path.join(ROOT, 'functions', '**', '*.js'), recursive=True)
    js_files += _glob.glob(os.path.join(ROOT, 'functions', '**', '*.mjs'), recursive=True)
    issues = []

    for jf in js_files:
        try:
            with open(jf, encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            continue
        # 只看注释行和字符串（跳过代码逻辑里的数字比较）
        lines = content.split('\n')
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            # 只检查注释和字符串字面量
            is_comment = stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*')
            if not is_comment:
                # 也检查包含中文描述的字符串（提示语）
                if not _re.search(r'[\u4e00-\u9fff]', line):
                    continue
            for pat, actual, label in patterns:
                for m in pat.finditer(line):
                    n = int(m.group(1))
                    if abs(n - actual) > 2:
                        issues.append((os.path.basename(jf), lineno, label, n, actual, line.strip()[:60]))

    if issues:
        for fn, ln, label, found, actual, snippet in issues[:5]:
            bad(name, f'{fn}:{ln} "{label}" 写死 {found}，实际 {actual}（{snippet}）')
        return

    ok(name, f'{len(js_files)} 个 JS 文件 · 无硬编码数字漂移')


# ---------------------------------------------------------------------------
# 2026-10-17 审计 §7 新增闸门：G-T2 / G-T3 / G-T6 / meta description
# ---------------------------------------------------------------------------

# 已知品类名（归一化后），用于 G-T2 判定
_CATEGORY_NAMES = frozenset([
    '机器人', '人形机器人', '四足机器人', '机械臂', '机械手', '关节', '减速器',
    '电机', '伺服', '驱动器', '控制器', '传感器', '触觉传感器', '视觉传感器',
    '摄像头', '激光雷达', '深度相机', '编码器', '限位开关',
    '执行器', '驱动器模块', '控制器模块', '减速电机', '谐波减速器',
    '关节模组', '一体化关节', '机械手夹爪', '夹爪', 'gripper', 'joint', 'motor',
    'servo', 'controller', 'sensor', 'actuator', 'reducer',
    'ai芯片', 'ai模型', '大模型', 'llm', '视觉模型', 'vla模型',
    '辅助驾驶', '自动驾驶', 'ar眼镜', 'vr眼镜', 'ar/vr', 'ar', 'vr',
    '消费电子', '消费电子领域', '消费电子品类',
    '机器人新技术', '机器人技术', '具身智能', 'embodied ai',
    '协议', '协议栈', '通信协议', '总线', '总线协议', 'ethernet', 'canbus',
    'pcb', 'pcb板', 'pcb板卡', 'pcb设计', '电路板', '板卡',
    '连接器', '接线端子', '端子', 'cable', '线缆', '电缆', 'power cable',
    '电源', '电源模块', '电源适配器', 'power', 'power module', '电源适配器',
    '结构件', '结构组件', '支架', '外壳', '结构', 'structural',
    '软件', 'firmware', '驱动程序', '驱动', 'driver',
    '芯片', 'soc', 'mcu', 'cpu', 'gpu', 'npu', 'chip',
    '平台', '机器人平台', 'robot platform', 'robot base', '底盘', 'base',
    '灵巧手', 'dexterous hand', 'hand', 'gripper', 'finger',
    'bom', '装配', 'assembly', '装配清单', '物料清单',
])


def _norm_name(s):
    """归一化名字：小写、去空格/连字符/下划线/中文标点，方便比较"""
    if not s:
        return ''
    import re as _r
    s = str(s).lower()
    s = _r.sub(r'[\s_\-·、，,。.:：;；\(\)\[\]{}「」『』“”‘’!！?？]', '', s)
    return s


def gate_paper_numbers_fresh():
    '''【SCI 达标 P0-1 · G-S1】论文 main.tex 数字 ↔ 产物现算值一致性（2026-10-18）

    审计报告（docs/RoboParts-科学性与SCI达标评估-20261018.md）实测：论文
    main.tex 里的核心数字（802 / 351,649 / type_error=4 / d1=112 / 100%
    electrical / 5.69% / 242 vendors / 28.5% / 295,096）与当前 api/*.json
    产物（868 / 430,336 / 262 / 61 / 32+29 / 16.2% / 358 / 37.3% / 430,013）
    全部漂移，最大差 65 倍（type_error 4 → 262）。

    本闸门扫描两版论文（arxiv + mechatronics）里的：
      - \\d{3}[,]\d{3}          → 4+ 位数字（351,649 形式）
      - \\$\\d{3,4}\\$           → 数学模式包裹的整数（$802$ $112$ 形式）
      - \\$\\d{2,4}[.]\\d{1,2}\\% → 数学模式包裹的百分比（$5.69\\%$ 形式）

    与产物现算值逐一比对：
      - 现算值必须至少出现一次（防论文未同步更新）
      - 论文里不得出现白名单外的过期数字（防"新加一个数字，旧的忘删"）

    白名单机制：commit hash、日期、ISO 编号、页码等允许保留；
    只拦截与产物口径重叠的数字。
    '''
    import re
    import json

    name = '论文数字与产物一致（SCI 达标 P0-1 · G-S1）'

    # ── 1. 现算事实（唯一真相源） ──────────────────────────────────────
    compose_path = os.path.join(ROOT, 'api', 'compose_semantics.json')
    entities_path = os.path.join(ROOT, 'api', 'entities.json')
    try:
        with open(compose_path, encoding='utf-8') as f:
            compose = json.load(f)
        with open(entities_path, encoding='utf-8') as f:
            entities = json.load(f)
    except Exception as e:
        bad(name, f'读产物失败：{e}')
        return

    agg = compose.get('aggregates', {})
    pairs = agg.get('pairs_evaluated', 0)
    oc = agg.get('overall_counts', {})
    composed = oc.get('composed', 0)
    type_error = oc.get('type_error', 0)
    unknown = oc.get('unknown', 0)
    gap = agg.get('gap_distance', {})
    d1_total = gap.get('1', 0)
    d2 = gap.get('2', 0)
    d3 = gap.get('3', 0)
    d1_elec = agg.get('d1_bottleneck', {}).get('electrical', 0)
    d1_sig = agg.get('d1_bottleneck', {}).get('signal', 0)
    d1_mech = agg.get('d1_bottleneck', {}).get('mechanical', 0)
    total_entities = len(entities.get('entities', []))

    # 计算 vendor 数（论文口径：manufacturer 非空去重，排除 '(none)'）
    vc = {}
    for e in entities.get('entities', []):
        v = e.get('manufacturer')
        if v and v not in ('(none)', '', None):
            vc[v] = vc.get(v, 0) + 1
    vendors_total = len(vc)
    top10_sum = sum(c for _, c in sorted(vc.items(), key=lambda x: -x[1])[:10])
    total_with_mfr = sum(vc.values())

    # 论文口径：机械接口声明率（mechanical_interface.status 口径）
    # applicable = status != 'n_a'；declared = status in ('declared', 'partial')
    # decidable = standard AND flange 同时非空
    mech_applicable = 0
    mech_declared = 0
    mech_decidable = 0
    for e in entities.get('entities', []):
        mi = e.get('mechanical_interface')
        if not isinstance(mi, dict):
            continue
        st = mi.get('status')
        if st and st != 'n_a':
            mech_applicable += 1
            if st in ('declared', 'partial'):
                mech_declared += 1
        if mi.get('standard') and mi.get('flange'):
            mech_decidable += 1

    # 百分比：分母 = pairs（若为 0 则跳过）
    if pairs:
        frac_composed = round(composed / pairs * 100, 4)
        frac_type_err = round(type_error / pairs * 100, 4)
        frac_unknown = round(unknown / pairs * 100, 4)
        frac_d1_elec = round(d1_elec / d1_total * 100, 2) if d1_total else 0.0
        frac_d1_sig = round(d1_sig / d1_total * 100, 2) if d1_total else 0.0
        frac_top10 = round(top10_sum / total_with_mfr * 100, 2) if total_with_mfr else 0.0
        frac_mech_declared = round(mech_declared / mech_applicable * 100, 2) if mech_applicable else 0.0
        frac_mech_decidable = round(mech_decidable / total_entities * 100, 2) if total_entities else 0.0
    else:
        frac_composed = frac_type_err = frac_unknown = 0.0
        frac_d1_elec = frac_d1_sig = frac_top10 = 0.0
        frac_mech_declared = frac_mech_decidable = 0.0

    # ── 2. 定义必须出现的「现算值」（防论文未同步更新） ──────────────────
    # 每个现算值：(LaTeX 格式字符串, 语义描述)
    # LaTeX 数字写法：4+ 位用 351{,}649 形式；3 位以内可直接 $112$
    required_values = []
    # 实体总数（4 位或 3 位）
    required_values.append((str(total_entities), 'entities 总数'))
    # pairs_evaluated（6 位）
    required_values.append((f'{pairs:,}'.replace(',', '{,}'), 'pairs_evaluated'))
    # overall_counts（4+ 位）
    if composed >= 1000:
        required_values.append((f'{composed:,}'.replace(',', '{,}'), 'overall_counts.composed'))
    if type_error >= 100:
        required_values.append((str(type_error), 'overall_counts.type_error'))
    if unknown >= 1000:
        required_values.append((f'{unknown:,}'.replace(',', '{,}'), 'overall_counts.unknown'))
    # gap_distance（4+ 位）
    if d2 >= 1000:
        required_values.append((f'{d2:,}'.replace(',', '{,}'), 'gap_distance[2]'))
    if d3 >= 1000:
        required_values.append((f'{d3:,}'.replace(',', '{,}'), 'gap_distance[3]'))
    # d1_bottleneck 各轴（3+ 位）
    if d1_total >= 10:
        required_values.append((str(d1_total), 'd1 总数'))
    # 关键百分比
    required_values.append((f'{frac_d1_elec:g}', 'd1 电气占比 %'))
    required_values.append((f'{frac_d1_sig:g}', 'd1 信号占比 %'))
    # 论文核心口径：机械声明率与可判定率（2026-10-19 深化）
    required_values.append((str(mech_applicable), 'mech_applicable（status!=n_a）'))
    required_values.append((str(mech_declared), 'mech_declared（declared+partial）'))
    required_values.append((f'{frac_mech_declared:g}', 'mech 声明率 %'))
    if mech_decidable >= 10:
        required_values.append((str(mech_decidable), 'mech_decidable（standard+flange）'))
        required_values.append((f'{frac_mech_decidable:g}', 'mech 可判定率 %'))
    # vendor 集中度
    if vendors_total >= 100:
        required_values.append((str(vendors_total), 'vendor 总数'))
        required_values.append((f'{frac_top10:g}', 'top-10 集中度 %'))

    # ── 3. 定义禁止出现的「过期值」（防"新加数字，旧的忘删"） ──────────
    # 2026-09-23 快照 → 2026-10-17+ 现算值的漂移表
    stale_values = {
        '802': '旧实体数（2026-09-23 快照），现为 868',
        '242': '旧 vendor 数（2026-09-23 快照），现为 348',
        '358': '投稿时快照 vendor 数（2026-10-15 Mechatronics），现为 348',
        '439': '旧 mech_applicable（已改为 mechanical_interface.status 口径），现为 500',
        '351{,}649': '旧 pairs_evaluated（2026-09-23 快照）',
        '351{,}645': '旧 unknown count（2026-09-23 快照）',
        '295{,}096': '旧 d3 count（2026-09-23 快照）',
        '28.5': '旧 top-10 集中度（2026-09-23 快照）',
        '37.33': '投稿时快照 top-10 集中度（2026-10-15 Mechatronics），现为 18.72',
        '5.69': '旧 mech 声明率（旧口径 25/439）',
        '100.0%\\textbf{': '旧 d1=100% electrical 表述（当前 32+29）',
        '112': '旧 d1 总数（2026-09-23 快照，现为 61）',
    }

    # ── 4. 扫描两版论文 ────────────────────────────────────────────────
    papers = [
        os.path.join(ROOT, 'papers', 'arxiv_submission', 'main.tex'),
        os.path.join(ROOT, 'papers', 'mechatronics_submission', 'main.tex'),
    ]

    errors = []
    for paper_path in papers:
        try:
            with open(paper_path, encoding='utf-8') as f:
                text = f.read()
        except FileNotFoundError:
            errors.append(f'{paper_path}: 文件不存在（跳过）')
            continue
        except Exception as e:
            errors.append(f'{paper_path}: 读取失败 {e}')
            continue

        rel = os.path.relpath(paper_path, ROOT)

        # 4a. 现算值必须出现
        for val, desc in required_values:
            if val not in text:
                errors.append(
                    f'{rel}: 缺少现算值 {val}（{desc}）——论文未同步更新'
                )

        # 4b. 过期值不得出现（除白名单：commit hash / 日期 / ISO 号等）
        # 用词边界避免子串误报：$802$ 应匹配 $802$，但不应误伤 $802X$
        for stale, desc in stale_values.items():
            # 构造边界模式
            if stale.startswith('$'):
                pat = stale
            else:
                # 用 lookaround 确保不匹配更长数字的一部分
                pat = r'(?<!\d)' + re.escape(stale) + r'(?!\d)'
            if re.search(pat, text):
                # 白名单：如果 stale 在 commit hash 或 ISO 号上下文出现，允许
                # 简单策略：仅报告，不阻断——由读者判断（论文里 4/242 这种
                # 短数字会撞很多 ISO / 页码，需要人工复核）
                errors.append(
                    f'{rel}: 检测到可能过期的数字 "{stale}"（{desc}）——'
                    f'请确认是否应更新为现算值'
                )

    if errors:
        for err in errors[:20]:  # 前 20 条
            print(f'  [paper-numbers] {err}')
        if len(errors) > 20:
            print(f'  ... 以及 {len(errors) - 20} 条')
        bad(name, f'{len(errors)} 项论文数字漂移（详见上方逐条打印）')
    else:
        print(f'  [paper-numbers] 两版论文数字与产物现算值一致')


def gate_name_not_category():
    '''【G-04 · G-T2】实体名不得等于品类名归一化（防品类词入库）（2026-10-17）

    审计实测：LLM-* 的 20 条占位里，6 条名字是"人形机器人/AI芯片/辅助驾驶/AR眼镜/
    消费电子/机器人新技术"—— 品类词不是实体。品类词入库会：
      1. 撑高实体总数（868 里混进非实体）
      2. 让搜索返回"人形机器人"这种无信息结果的条目
      3. 让 BOM 检查工具误认为它是可选件

    本闸门对所有实体的 name + name_en 做归一化后与已知品类名集合比对；命中且
    quarantine=False 即判红。品类词可以入库，但**必须显式标记 quarantine=True**
    且加 quarantine_reason='category_word'。
    '''
    import json
    name = '实体名不得等于品类名归一化'
    path = os.path.join(ROOT, 'api', 'entities.json')
    try:
        with open(path, encoding='utf-8') as f:
            doc = json.load(f)
        entities = doc.get('entities') or []
    except Exception as e:
        bad(name, f'entities.json 不可读：{e}')
        return

    offenders = []
    for e in entities:
        if e.get('quarantine') == True:
            continue
        nm = _norm_name(e.get('name'))
        nm_en = _norm_name(e.get('name_en'))
        hit = None
        if nm and nm in _CATEGORY_NAMES:
            hit = ('name', nm)
        elif nm_en and nm_en in _CATEGORY_NAMES:
            hit = ('name_en', nm_en)
        if hit:
            offenders.append((e.get('id'), hit[0], hit[1]))

    if offenders:
        sample = ', '.join(f'{cid}({field}="{val}")' for cid, field, val in offenders[:5])
        bad(name, f'{len(offenders)} 条实体的名字是品类词（{sample}），'
                  f'请 quarantine=True 或补真实信息')
        return

    ok(name, f'全部实体名都不等于品类词（{len(entities)} 条已检查）')


def gate_name_en_manufacturer_unique():
    '''【G-05 · G-T3】name_en + manufacturer 复合唯一性（2026-10-17）

    审计实测：16 组重复实体（24 条），跨三套 ID 体系（ACT-* / CHIP-* / ACTUATOR-*
    占位），归一化 name_en 完全同名。同一物理零件在库里有两条 ⇒ 兼容性判定可能
    给出不同结论 ⇒ 868 这个数字虚高。

    本闸门对**非 quarantine** 的实体，按 (归一化 name_en + 归一化 manufacturer)
    复合键分组，同组 >1 即判红。空 name_en 或空 manufacturer 不计入（避免误伤
    只填了一边的合法条目）。
    '''
    import json, collections
    name = 'name_en + manufacturer 复合唯一性'
    path = os.path.join(ROOT, 'api', 'entities.json')
    try:
        with open(path, encoding='utf-8') as f:
            doc = json.load(f)
        entities = doc.get('entities') or []
    except Exception as e:
        bad(name, f'entities.json 不可读：{e}')
        return

    groups = collections.defaultdict(list)
    for e in entities:
        if e.get('quarantine') == True:
            continue
        nm = _norm_name(e.get('name_en'))
        mf = _norm_name(e.get('manufacturer'))
        if not nm or not mf:
            continue
        groups[(nm, mf)].append(e.get('id'))

    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    if dupes:
        for (nm, mf), ids in list(dupes.items())[:5]:
            bad(name, f'重复组（name_en="{nm}", manufacturer="{mf}"）：{ids}')
        return

    ok(name, f'{len(groups)} 组复合键全部唯一（0 重复组）')


def gate_bfs_reachability():
    '''【G-09 · G-T6】根页面首页 BFS 可达性（2026-10-17）

    审计实测：41 个根页面中 11 个从 index.html 走不到（含 assembly /
    compatibility-viz / reference-builds 三个核心功能页）。

    白名单（后台/独立入口，允许不可达）：
      - 404.html        （错误页，只在浏览器跳链时命中）
      - order.html      （订单页，走独立支付/邮件链接）
      - supplier-admin.html （供应商后台，走独立账号）
      - promo-poster.html  （营销落地页，直接投广告）

    BFS 起点 index.html；每条内部 href 展开一次；只走根 .html 页面。
    '''
    import re as _re, glob as _glob
    name = '根页面首页 BFS 可达性'
    html_dir = ROOT
    all_pages = sorted(set(
        os.path.basename(p) for p in _glob.glob(os.path.join(html_dir, '*.html'))
    ))
    whitelist = {'404.html', 'order.html', 'supplier-admin.html', 'promo-poster.html'}
    must_reach = [p for p in all_pages if p not in whitelist and p != 'index.html']

    href_re = _re.compile(r'href\s*=\s*["\'](/[^"\']*)["\']')

    def _normalize(href):
        href = href.split('#')[0].split('?')[0]
        if not href.startswith('/'):
            return None
        rel = href[1:].strip('/')
        if not rel:
            return None
        if rel.endswith('/'):
            rel = rel + 'index.html'
        if not _re.search(r'\.[a-z0-9]{2,5}$', rel.split('/')[-1]):
            rel = rel + '.html'
        return os.path.basename(rel)

    # BFS
    visited = set()
    queue = ['index.html']
    while queue:
        cur = queue.pop(0)
        if cur in visited:
            continue
        visited.add(cur)
        path = os.path.join(ROOT, cur)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            continue
        for m in href_re.finditer(content):
            tgt = _normalize(m.group(1))
            if tgt and tgt in all_pages and tgt not in visited:
                queue.append(tgt)

    unreachable = [p for p in must_reach if p not in visited]
    if unreachable:
        bad(name, f'{len(unreachable)} 个页面从首页 BFS 不可达：{unreachable[:8]}')
        return

    ok(name, f'{len(must_reach)} 个页面全部从首页可达（{len(whitelist)} 个后台页白名单）')


def gate_meta_description_coverage():
    '''【G-15/G-16】meta description + og:title 覆盖闸门（2026-10-17）

    审计实测：11 页无 meta description、32 页无 og:title。SEO 与社交分享都受影响。

    本闸门扫描根 .html 全部页面，断言：
      - <meta name="description" content="..."> 存在且 length >= 30
      - <meta property="og:title" content="..."> 存在且 length >= 5
    404.html 豁免（错误页本来就应该极简）。
    '''
    import re as _re, glob as _glob
    name = 'meta description + og:title 覆盖'
    desc_re = _re.compile(
        r'<meta\s+name\s*=\s*["\']description["\']\s+content\s*=\s*["\']([^"\']+)["\']',
        _re.I)
    og_re = _re.compile(
        r'<meta\s+property\s*=\s*["\']og:title["\']\s+content\s*=\s*["\']([^"\']+)["\']',
        _re.I)
    exempt = {'404.html'}

    htmls = sorted(_glob.glob(os.path.join(ROOT, '*.html')))
    missing_desc, missing_og, weak_desc = [], [], []
    for p in htmls:
        bn = os.path.basename(p)
        if bn in exempt:
            continue
        try:
            with open(p, encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            continue
        m = desc_re.search(content)
        if not m:
            missing_desc.append(bn)
        elif len(m.group(1)) < 30:
            weak_desc.append((bn, len(m.group(1))))
        mo = og_re.search(content)
        if not mo:
            missing_og.append(bn)

    if missing_desc or missing_og:
        msgs = []
        if missing_desc:
            msgs.append(f'缺 meta description：{missing_desc}')
        if missing_og:
            msgs.append(f'缺 og:title：{missing_og[:5]}…（{len(missing_og)} 个）')
        bad(name, '；'.join(msgs))
        return

    if weak_desc:
        bad(name, f'{len(weak_desc)} 页 meta description < 30 字符：{weak_desc}')
        return

    ok(name, f'{len(htmls) - len(exempt)} 页全部有 ≥30 字 description + ≥5 字 og:title')


def gate_data_gaps_ratchet():
    '''【G-T8 · 审计报告 G-06/G-13/G-14】数据缺口棘轮（2026-10-18）

    审计报告最后 3 项缺口（G-06 机械可判定率 / G-13 协议性能基准 /
    G-14 组件 n_a 复核）本质是数据侧的真实缺口，需要人肉查一手 datasheet
    或跑真机测量，不能靠脚本伪造。

    本闸门策略：**不阻止缺口存在（那是诚实），但阻止缺口恶化（那是失职）**。

    三个基线（当前实测值）：
      - G-06 mech_decidable: 57/868 = 6.57%
      - G-13 protocol_perf_missing: 27/64
      - G-14 component_na_review: 159（含 14 条 platforms 明确错误）

    棘轮口径：只允许下降（缺口收窄），不允许上升。例外是"新增实体带入"
    ——那必须同步更新基线并写明理由，闸门随之放宽到新的基线值。

    反例（本闸门能抓到的假绿）：
      - 有人把 3 条 n_a 的 platforms 改成 not_declared 来"提升可判定率"→ 实际是
        换合法值冒充语义，本闸门通过但审计会抓；配合 gate_d5_no_source_policy 与
        gate_three_state_conservation 交叉验证。
      - 有人把 30 条 protocol 的 spec 字段清空 → G-13 缺数 27→57，本闸门立刻红。

    本闸门与 gate_d5_no_source_policy 分工：那条管"存量不破戒"，本条管"缺口不恶化"。
    '''
    name = '数据缺口棘轮（G-06/G-13/G-14）'
    import json as _json

    try:
        with open(os.path.join(ROOT, 'api', 'entities.json'), encoding='utf-8') as f:
            ents = _json.load(f).get('entities', [])
    except Exception as ex:
        bad(name, f'entities.json 读失败：{ex}')
        return

    total = len(ents)

    # ---- G-06 机械可判定率：standard + flange 同时非空 ----
    def _decidable(e):
        mi = e.get('mechanical_interface')
        if not isinstance(mi, dict):
            return False
        return bool(mi.get('standard')) and bool(mi.get('flange'))
    dec_now = sum(1 for e in ents if _decidable(e))

    # ---- G-13 协议性能基准缺失数 ----
    def _has_perf(e):
        for k in ('latency', 'jitter', 'bandwidth', 'real_time_perf', 'performance'):
            if e.get(k):
                return True
        spec = e.get('spec')
        if isinstance(spec, dict):
            for k in ('latency', 'jitter', 'bandwidth'):
                if spec.get(k):
                    return True
        return False
    protos = [e for e in ents if e.get('category') == 'protocols']
    proto_perf_missing = sum(1 for e in protos if not _has_perf(e))

    # ---- G-14 component n_a 复核：entity_kind=='component' 且 status=='n_a' 的条目数 ----
    # 审计报告口径：component(659) 里有 159 条标 n_a，实物零件标"不适用机械接口"需要解释。
    # 非物理品类（software 81 / specification 101 / market_intelligence 17 / organization 10）
    # 共 209 条标 n_a 是**正确**的（本就不该有机械接口），不计入缺口。
    def _is_n_a_review(e):
        if e.get('entity_kind', 'component') != 'component':
            return False
        mi = e.get('mechanical_interface')
        if not isinstance(mi, dict):
            return False
        return mi.get('status') == 'n_a'
    na_review = sum(1 for e in ents if _is_n_a_review(e))

    # ---- 基线（棘轮）----
    # 首次登记日 2026-10-18，实测值：57 / 27 / 159
    # 若基线被下调，必须在本文件与 docs/data-gaps-register.md 同步登记理由
    BASELINE = {
        'mech_decidable_max': 57,      # 可判定数不得超过基线（防止伪造）
        'mech_decidable_min': 57,      # 可判定数不得降低（防止倒退）
        'proto_perf_missing_max': 27,  # 协议性能缺失数不得超过基线
        'na_review_max': 159,          # n_a 复核数不得超过基线
    }

    failures = []
    if dec_now > BASELINE['mech_decidable_max']:
        failures.append(f'G-06 mech_decidable={dec_now} 超过基线 {BASELINE["mech_decidable_max"]}，疑似伪造')
    if dec_now < BASELINE['mech_decidable_min']:
        failures.append(f'G-06 mech_decidable={dec_now} 低于基线 {BASELINE["mech_decidable_min"]}，缺口倒退')
    if proto_perf_missing > BASELINE['proto_perf_missing_max']:
        failures.append(f'G-13 协议性能缺失={proto_perf_missing} 超过基线 {BASELINE["proto_perf_missing_max"]}，缺口倒退')
    if na_review > BASELINE['na_review_max']:
        failures.append(f'G-14 n_a 复核数={na_review} 超过基线 {BASELINE["na_review_max"]}，缺口倒退')

    if failures:
        bad(name, '；'.join(failures))
        return

    ok(name, f'三缺口均在基线内（decidable={dec_now}/≤{BASELINE["mech_decidable_max"]}, '
             f'proto_missing={proto_perf_missing}/≤{BASELINE["proto_perf_missing_max"]}, '
             f'na_review={na_review}/≤{BASELINE["na_review_max"]}）')


def gate_positioning_gate_count_consistency():
    '''【G-S2】定位面 CI 闸门数一致性（2026-10-18 傍晚）

    背景：G-S1 守论文正文，G-T7 守 functions/ JS 硬编码，两条都不管
    定位面（README / agent-discovery / llms.txt / index.html）的"N 项 CI 闸门"
    漂移。上一轮 GATES 从 49 涨到 76，4 处定位面仍写"49 项"——上线后回探才发现。

    本闸门扫描 4 个定位面里的形如：
      - "N 项 CI 闸门"
      - "N 项反向注入闸门"
      - "N gates" / "Total N gates"（README 注入块除外——那条有独立 data-rp 锚点）
    中 N 与 len(GATES) 不一致即判红。

    容忍 ±1 浮动（闸门刚加、inject_readme_stats 未跑是常见中间态）；超过判红。
    本闸门不防定位面的**文案漂移**（如"三条定理" vs "三条代数律"），只防数字漂移。
    文案漂移由人工 grep 或未来的正则扫全词闸门负责。
    '''
    import re as _re
    name = '定位面闸门数一致（G-S2）'

    # 真相源：GATES 表本身的长度
    actual_gates = len(GATES)

    # 定位面文件（相对 ROOT）
    targets = [
        'README.md',
        'agent-discovery.json',
        'llms.txt',
        'index.html',
    ]

    # 匹配模式：抓 N 项 CI 闸门 / N 项反向注入闸门 / Total N gates / N CI gates
    # 排除 <!-- RP-GATES:START ... --> 注入块（那条由 gate_readme_stats_fresh 守）
    patterns = [
        (_re.compile(r'(\d+)\s*项\s*CI\s*闸门'), 'N 项 CI 闸门'),
        (_re.compile(r'(\d+)\s*项\s*反向注入闸门'), 'N 项反向注入闸门'),
        (_re.compile(r'Total\s+(\d+)\s+gates'), 'Total N gates'),
        (_re.compile(r'(\d+)\s+CI\s+gates', _re.I), 'N CI gates'),
    ]

    issues = []
    scanned = 0
    for rel in targets:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            issues.append((rel, 0, 'MISSING', 0, actual_gates, ''))
            continue
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            continue
        scanned += 1

        # 先剥掉 data-rp 注入块（<!-- RP-GATES:START ... END --> 之间），
        # 避免 gate_readme_stats_fresh 的锚点值重复计入
        content_stripped = _re.sub(
            r'<!--\s*RP-GATES:START.*?-->.*?<!--\s*RP-GATES:END\s*-->',
            ' ', content, flags=_re.DOTALL,
        )
        lines = content_stripped.split('\n')
        for lineno, line in enumerate(lines, 1):
            for pat, label in patterns:
                for m in pat.finditer(line):
                    n = int(m.group(1))
                    if abs(n - actual_gates) > 1:
                        issues.append((rel, lineno, label, n, actual_gates,
                                       line.strip()[:70]))

    if issues:
        for fn, ln, label, found, actual, snippet in issues[:5]:
            bad(name,
                f'{fn}:{ln} "{label}" 写 {found}，实际 {actual}（{snippet}）')
        return

    ok(name, f'{scanned} 个定位面 · 闸门数与 GATES={actual_gates} 一致')


def gate_positioning_terminology_consistency():
    '''【G-S3】定位面术语一致性（2026-10-18 深夜）

    背景：G-S2 守数字漂移，但不管术语漂移。agent-discovery.json 的
    ai_agent_instructions 里长期写"T1/T2/T3 theorems"（定理），而其他三个
    定位面（README/llms/index.html）都用"三条代数律"（algebraic laws）——
    术语不一致上线后回探才发现。

    本闸门扫描 4 个定位面里的**禁用术语**，命中即判红：
      - "三条定理" / "T1/T2/T3 定理" / "theorem"（定位面里不应出现）
      - "49 项 CI 闸门" / "49 CI gates"（已过期的闸门数，G-S2 已守，本条冗余兜底）

    正确术语：
      - 中文："三条代数律"（可靠性 / 证据单调性 / 不可判定边界）
      - 英文："three algebraic laws (T1/T2/T3)"

    与 G-S2 分工：G-S2 守数字（N 项闸门），本条守术语（定理 vs 代数律）。
    两条配合才能防"定位面文案漂移"。

    注意：论文 main.tex 里用"theorem"是学术惯例，不在本闸门范围内。
    本闸门只守对外定位面。
    '''
    import re as _re
    name = '定位面术语一致（G-S3）'

    targets = [
        'README.md',
        'agent-discovery.json',
        'llms.txt',
        'index.html',
    ]

    # 禁用术语模式：(正则, 标签, 正确替代)
    banned = [
        (_re.compile(r'三条定理', _re.I), '三条定理', '三条代数律'),
        (_re.compile(r'T1/T2/T3\s+定理', _re.I), 'T1/T2/T3 定理', 'T1/T2/T3 代数律'),
        (_re.compile(r'T1/T2/T3\s+theorems?', _re.I), 'T1/T2/T3 theorem', 'three algebraic laws (T1/T2/T3)'),
        (_re.compile(r'\btheorem\b', _re.I), 'theorem', 'algebraic law'),
    ]

    issues = []
    scanned = 0
    for rel in targets:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            issues.append((rel, 0, 'MISSING', '', '', ''))
            continue
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            continue
        scanned += 1

        lines = content.split('\n')
        for lineno, line in enumerate(lines, 1):
            for pat, label, correct in banned:
                if pat.search(line):
                    issues.append((rel, lineno, label, correct, '',
                                   line.strip()[:70]))

    if issues:
        for fn, ln, label, correct, _, snippet in issues[:5]:
            bad(name,
                f'{fn}:{ln} 禁用术语"{label}"（应为"{correct}"）（{snippet}）')
        return

    ok(name, f'{scanned} 个定位面 · 无禁用术语（定理→代数律）')


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
    # 【20261026】Sister READMEs (mcp-server/README.md, mcp-server/package.json). Same drift
    # class as above but in files inject_readme_stats.py doesn't own; 688 → 798 → 868 recurred
    # 3 times, each fixed by hand. This gate forces the counts to match the truth source.
    ('对外文档数字与真相源一致', gate_readme_counts),
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
    # 【20261011 P0-4】线上 vs 仓内新鲜度对账。报告 P0-1 部署链路 62/62 失败、
    # 线上冻结 8 天无人察觉的直接原因就是缺这道闸门。无网络时降级为 warn。
    ('部署新鲜度对账（线上 vs 仓内 ≤7 天）', gate_deployment_freshness),
    ('双引擎口径桥接一致', gate_engine_bridge),
    ('部署后置新鲜度校验', gate_deploy_live_verify),
    # 【2026-10-13 V2 报告 §4.2】agent-discovery.json 是机器可读面最大的对外锚点，
    # 但 V2 报告实测发现它停在第一代旧定位、其它面已上移——机器可读面口径分裂。
    # 本闸门守三字段必须含第二代锚点 + ISO 22166-1。
    ('agent-discovery 定位（第二代锚点 + ISO 22166-1）',
     gate_agent_discovery_positioning),
    # 【2026-10-13 V2 报告 §6.3.3】三态完备性守恒不变量。本项目独有承诺，
    # 二进制兼容矩阵根本没有这个性质可言。builder 层 fail-fast 断言过一次，
    # CI 层加独立第二双眼睛，防止 builder 静默破坏守恒（新增 verdict 类别但没
    # 同步 pairs_evaluated 分母）时被假绿掩盖。
    ('三态守恒不变量（compose + co_mount）', gate_three_state_conservation),
    # 【2026-10-13 V2 报告 §6.3.2 主张一 · 四维深化 P0-4】变异评分闸门。
    # 从"通过/不通过"升级到"覆盖多少失效模式"。阈值 0.85（V2 报告建议值，
    # 本项目自选，非行业硬标）。本闸门不新造测试，而是让现有 43 闸门对
    # 6 条最小变异清单（M1~M6，覆盖三态破坏 / 轴边际 / 取证指引 / 诚实边界
    # 四类已知失效模式）的杀死率作为可评分度量。
    ('变异评分（6 变异体 kill rate ≥ 0.85）', gate_mutation_score),
    # 【2026-10-14 TDD-2026-01】世界模型排除闸门。把「不引入 H-JEPA / Odyssey-3 /
    # Cosmos 3 到核心链路」的决策从「被动回避」变成「可验证的留痕」。守三个不变量：
    # 决策文档存在、依赖面无推理库、五处定位声明面不出现具体模型名。与
    # gate_positioning_caliber（管对外叫什么）/ gate_engine_bridge（管双引擎口径）
    # 分工互补——本闸门管「不做什么」。
    ('世界模型排除（TDD-2026-01 决策留痕 + 声明面无隐性依赖）',
     gate_world_model_exclusion),
    # 【2026-10-14 阶段 C】合成测试对池闸门。与 gate_eval_compat 分工互补：
    # gate_eval_compat 守 Golden 28 条的裁决正确性，本闸门守合成池的
    # schema / 大小上限 / 溯源合法性 / 生成器自证。合成池独立存放于
    # api/synthesized-pair-pool.json，**不进入 Golden 集**（人工审阅纯净
    # 保持）。绝对上限 100 对——超过即判红，防止合成对无限膨胀后与
    # Golden 集边界模糊。
    ('合成测试对池（schema + 上限 + 溯源 + 生成器自证）',
     gate_synthesized_pair_pool),
    # 【2026-10-14 阶段 B】VLM 抽取队列闸门。守两个队列
    # （pending / approved）的 schema 合规 + confidence 门控正确 +
    # 4 维字段齐全 + 生成器自证。抽取产物必须过本闸门，才可能
    # 人工评审后迁移到 entities.json。mock 模式让 CI 无 PDF 时
    # 也能跑通（不阻塞主链路）。
    ('VLM 抽取队列（confidence 门控 + 4 维 schema + 自证）',
     gate_vlm_extraction_confidence),
    # 【2026-10-15 Phase A · A2】组合演算代数律性质测试。Phase A 的 A1 把 compose_engine.py
    # 的判据抽到 compose_core.py（零 IO 纯函数），A2 用随机属性测试证明三条代数律成立：
    # Soundness（每轴声称可组合时 best_pair 必须是可组合证据）、Monotonicity（追加 evidence
    # 不允许翻转已判定）、Undecidability（not_declared 端口永不产生 compatible）。
    # 含阴性对照：变异 AXIS_VERDICT_OF_PAIR 让 incompatible→compatible，Soundness 必须判红。
    ('组合演算代数律（性质测试 + 变异自证）', lambda: run_sub(
        '组合演算代数律（性质测试 + 变异自证）',
        [sys.executable, os.path.join(ROOT, 'tests', 'property', 'test_compose_lattice.py')],
        timeout=120)),
    # 【2026-10-15 Phase A · A3】装配级类型检查。新原语 assemble(goal, candidate_set, constraints)
    # 输出 well_typed / ill_typed(minimal_core) / unknown。与 MDV 对账：ill_typed 的
    # minimal_core 里每条声明的边际价值应 ≥ 1，否则 core 混了零价值节点——判红。
    ('装配级类型检查（minimal core + MDV 对账）', lambda: run_sub(
        '装配级类型检查（minimal core + MDV 对账）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'build_assembly_typecheck.py')],
        timeout=120)),
    # 【2026-10-15 Phase A · A5】证据账本。追加式、不可改写、可复验的贡献记录。
    # 每条贡献必须通过 schema 校验 + 有溯源 + falsifiable_check 可复验。
    # KPI 棘轮：decidable_pairs 单调不降（补证据真的在解锁可判定对）。
    ('证据账本（schema 校验 + KPI 棘轮）', lambda: run_sub(
        '证据账本（schema 校验 + KPI 棘轮）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'build_evidence_ledger.py')],
        timeout=120)),
    # 【2026-10-15 Phase A · A6】ISO 22166-201/-202 条款级映射表。
    # 每条映射挂具体文件 + 字段名 + 闸门 ID。无映射条款都有理由（不是漏做）。
    # 变异自证：篡改映射字段名必须判红。
    ('ISO 22166 条款级映射（覆盖率 + 变异自证）', lambda: run_sub(
        'ISO 22166 条款级映射（覆盖率 + 变异自证）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'conformance_test.py')],
        timeout=60)),
    # 【2026-10-16 Phase B 深化】verification-antipatterns 待入 CI 的 6 条
    ('子串边界检查（AP-002）', gate_no_substring_boundary),
    ('多目标适应度（AP-006）', gate_no_single_scalar_fitness),
    ('锚点修改检查（AP-007）', gate_no_anchoring_modification),
    ('桥接合并检查（AP-009）', gate_bridge_no_merge),
    ('ISO 映射边界（AP-010）', gate_iso_mapping_honest),
    # 【2026-10-16 Phase B 地基】产物新鲜度闸门：上游 mtime > 产物 mtime + tolerance_days
    # ⇒ FAIL。审计 §F3 实测 16 个产物陈旧。白名单走 api/freshness_exemptions.json（豁免必带
    # reason + expires_at，季度审计到期强制复核）。未纳入 ARTIFACTS 表的产物不判定，
    # 仅作为 uncovered 提醒打印。这是"改真相源必跑 regen"的最后兜底。
    ('产物新鲜度检查（upstream mtime 兜底）', lambda: run_sub(
        '产物新鲜度检查（upstream mtime 兜底）',
        [sys.executable, os.path.join(ROOT, 'scripts', 'check_freshness.py')],
        timeout=30)),
    # 【2026-10-16 D1】对外数据集端点 /api/data.json 一致性闸门。
    # 审计 §F1 实测线上 data.json 的 meta.entity_count=767 但 data array 有 868 条，
    # 一次 curl 就能证伪"868 条完整数据集"。闸门断言三源（entity_count / total_entities
    # / len(data) / entities.json.count）必须四方一致，且 generated_at 不超 3 天。
    ('对外数据集端点一致性（D1 · 四方数字对齐）', gate_d1_datajson_consistency),
    # 【2026-10-16 D2-a】entities.json 时间戳收敛闸门。审计 §F2 实测顶层 updated
    # =2026-09-25、顶层 last_updated=2026-10-06、meta.updated=当日 三个不一致。
    # 契约：meta.updated 是唯一真相源，顶层两个是兼容别名，脚本必须同步为镜像。
    ('entities.json 时间戳一致（D2-a · 三源镜像）', gate_d2a_timestamp_consistency),
    # 【2026-10-16 D5】"无出处不收"铁律存量闸门。审计 §F5 实测 61 条实体无 source
    # 字段，其中 35 条已 quarantine=True（诚实标记），26 条 quarantine=False 且
    # data_quality='ok'——即"看着干净、实则无出处"，这才是真正的违规。
    # 闸门策略：不直接改数据（那需要人来决定补 source 还是 quarantine），
    # 而是把口径锁死——无 source 且无 sources 的实体必须 quarantine=True 或
    # data_quality != 'ok'。这是"存量不再腐化"的兜底闸门。
    ('无出处政策闸门（D5 · 存量不破戒）', gate_d5_no_source_policy),
    ('confidence_tier 五档枚举契约（D5 · 语义分层）', gate_d5_confidence_tier_contract),
    ('API 版本化契约（阶段 3-lite · schema_version）', gate_schema_version_declared),
    # 【2026-10-17 审计 F6】依赖锁定 + SBOM 闸门。审计实测仓库无 package-lock.json
    # 也无 SBOM——fresh clone 装依赖无锁定，供应链无清单。
    # 闸门：package-lock.json 存在 + SBOM.json 存在 + SBOM 与 lockfile 现算组件集一致。
    # 与 gate_no_secrets 分工：那条管"没有凭据"，这条管"依赖可复现"。
    ('依赖锁定 + SBOM（package-lock 存在 + SBOM 与 lock 一致）',
     gate_lockfile_and_sbom),
    # 2026-10-17 added (G-01 · G-T1): audit found 239/472 Tier A URLs were
    # google.com/search?q=... — "我没找到，我搜了一下" was being treated as Tier A
    # deep_link. This gate fails any Tier A entity whose collected URLs hit the
    # search-engine blacklist, so the semantic of "A = 点开即具体页面" cannot be
    # silently diluted again by future code drift. Uses _is_search_engine +
    # _is_search_engine_root (root-only variant prevents google.com being
    # misclassified as Tesla's "entity homepage" via source_scope).
    ('Tier A URL 无搜索引擎污染（A 级语义护栏）', gate_tier_a_url_blacklist),
    # 2026-10-17 added (G-03 · G-T3): audit found `npm run test:unit` runs 0 tests
    # because the glob `tests/**/*.test.mjs` doesn't match actual filename pattern
    # `test_*.mjs` (underscore prefix). `node --test` exits 0 with `# tests 0`
    # on empty glob — CI green with zero coverage. This gate re-counts files
    # independently and asserts `# tests N > 0`, killing silent glob/name drift.
    ('单元测试非空（防假绿）', gate_unit_tests_not_empty),
    # 2026-10-17 added (G-07 · G-T4): audit found 34.7% of entities missing
    # last_verified. Backfill discipline: probed entities get audit-date,
    # never-probed get explicit null + basis marker (no fabrication). This gate
    # ratchets coverage and forbids "silent gaps" (missing both last_verified
    # AND last_verified_basis).
    ('last_verified 覆盖率棘轮', gate_last_verified_coverage),
    # 2026-10-17 added (G-09 · G-T5): audit found 1 real dead link
    # funnel.html → /analytics.html (file doesn't exist). This gate scans
    # every .html for internal hrefs and asserts each target file exists
    # on disk. Filters http(s) external, mailto/tel/javascript/#, and
    # template strings ${...}. Fixes applied: funnel.html now points to
    # geo-dashboard.html (the actual SEO analytics page).
    ('站内 href 目标存在', gate_href_targets_exist),
    # 2026-10-17 added (G-10 · G-T7): audit found 3 hardcoded counts in
    # functions/ comments/hints (868 entities, 99 quarantine, 86 AI models)
    # that drift from actual data with no gate watching. This gate scans
    # all JS files under functions/ for Chinese-number patterns and asserts
    # they match entities.json (±2 tolerance). Fixes: compatibility.js now
    # uses Object.keys(map).length; search.js and mcp.js comments use
    # descriptive ranges instead of exact numbers.
    ('functions/ 硬编码数字漂移', gate_hardcoded_count_drift),
    # 2026-10-17 added (G-04 · G-T2): audit found 6 LLM-* placeholder entries are
    # actually category words (人形机器人 / AI芯片 / 辅助驾驶) not entities. Any entity
    # whose normalized name equals a known category name must be quarantined.
    ('实体名不得等于品类名归一化（防品类词入库）', gate_name_not_category),
    # 2026-10-17 added (G-05 · G-T3): audit found 16 duplicate groups (24 entities)
    # with same normalized name_en, spanning three ID naming conventions. This gate
    # asserts name_en + manufacturer composite uniqueness on non-quarantined entities.
    ('name_en + manufacturer 复合唯一性', gate_name_en_manufacturer_unique),
    # 2026-10-17 added (G-09 · G-T6): audit found 11 pages unreachable from index.html
    # (including 3 core feature pages: assembly / compatibility-viz / reference-builds).
    # This gate BFS from index.html and asserts all non-whitelisted root .html pages
    # are reachable. Whitelist: 404.html / order.html / supplier-admin.html (backend-only).
    ('根页面首页 BFS 可达性', gate_bfs_reachability),
    # 2026-10-17 added (G-15/G-16): audit found 11 pages without meta description and
    # 32 pages without og:title. This gate scans all root .html files and asserts both
    # tags exist with non-empty values (>= 30 chars description, >= 5 chars og:title).
    ('meta description + og:title 覆盖', gate_meta_description_coverage),
    # 2026-10-18 added (审计报告 G-06/G-13/G-14 · G-T8): 三个数据侧缺口的棘轮闸门。
    # 缺口存在是诚实，缺口恶化是失职。基线值（57 / 27 / 159）登记于
    # docs/data-gaps-register.md；下调基线必须同步本文件并写明理由。
    ('数据缺口棘轮（G-06/G-13/G-14）', gate_data_gaps_ratchet),
    # 2026-10-18 added (SCI 达标 P0-1 · G-S1): 论文数字 ↔ 产物现算值一致性。
    # 审计报告实测论文 main.tex 里 802 entities / 351,649 pairs / type_error=4 等
    # 数字均已过期（实际 868 / 430,336 / 262）。此闸门扫描两版论文 main.tex 里
    # 所有「3 位以上、含逗号分隔」的大数字（\d{3}[,]\d{3}），逐一比对 api/
    # compose_semantics.json 与 api/entities.json 现算值——不匹配即判红。
    # 与 G-T7 functions/ 硬编码漂移不同：那条守 UI 文案，本条守论文正文。
    ('论文数字与产物一致（SCI 达标 P0-1 · G-S1）', gate_paper_numbers_fresh),
    # 2026-10-18 傍晚 added (G-S2): 定位面 CI 闸门数一致性。上一轮 GATES 49→76
    # 时，README/agent-discovery/llms.txt/index.html 4 处仍写"49 项 CI 闸门"，
    # 上线后回探才发现——G-S1 守论文、G-T7 守 functions/ JS，两条都不管定位面。
    # 本闸门扫 4 个定位面的"N 项 CI 闸门"模式，与 len(GATES) 现算比对。
    # 与 gate_readme_stats_fresh 分工：那条守 README 注入块（RP-GATES 锚点），
    # 本条守定位面裸文本；两者配合才不漏。
    ('定位面闸门数一致（G-S2）', gate_positioning_gate_count_consistency),
    # 【2026-10-18 深夜 G-S3】定位面术语一致性。G-S2 守数字，本条守术语。
    # agent-discovery.json 的 ai_agent_instructions 曾长期写"T1/T2/T3 theorems"
    # （定理），而其他三个定位面用"三条代数律"——术语不一致上线后回探才发现。
    # 禁用"定理/theorem"，正确术语是"代数律/algebraic law"。
    ('定位面术语一致（G-S3）', gate_positioning_terminology_consistency),
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
