# -*- coding: utf-8 -*-
"""提交清单守卫（staged guard）。

起因（2026-08-08 16:18 那轮的真实事故）：
    `git add -A scripts/` 把本轮**从未编辑过**的 `scripts/promote.mjs` 一起暂存并提交了，
    而起手 `git status` 明明是 0 改动 —— 也就是说运行途中有东西改了它，来源至今未明。
    审阅后内容正确故保留，但「我不知道自己提交了什么」本身就是事故：
    下一次那 14 行如果是错的、或是别的进程写坏的，同样会被无声带上车。

守卫的思路（不是"更小心一点"，而是把核对变成机器动作）：
    1. 提交前必须**显式声明本轮打算改哪些文件**（--intent），没声明的暂存文件一律判红；
    2. 声明不许用能把事故文件顺手罩进去的**过宽通配**——尤其 `scripts/`、`functions/`
       这类可执行代码目录，必须精确到文件名（`scripts/*` 会直接把 promote.mjs 罩住，
       等于给自己开后门，所以显式禁掉）；
    3. 暂存文件的 mtime 若早于**本轮起手时刻**，说明"不是本轮改的却要提交"，判红。

关键设计（吃过亏才写下的）：
    - `evaluate()` 是**纯函数**：staged 清单、mtime、起手时刻全部由调用方注入。
      对照用例的基准必须钉死在用例内部，绝不向环境取值 —— 否则测试会被"被测流程
      自己会改的状态"污染（L1.58/L1.59 已各栽过一次）。
    - 守卫判红只是"停下来看一眼"，不是"禁止提交"：确认无误后把文件补进 --intent
      即可放行。惩罚的是**不核对**，不是惩罚改动本身。

用法:
    python scripts/staged_guard.py --begin                 # 起手：记录本轮起点
    python scripts/staged_guard.py --intent a.py --intent 'ops/results/*.md'
    python scripts/staged_guard.py --selftest              # 阴阳对照自测
"""
import argparse
import fnmatch
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'ops', 'results', '_run_start.json')
CST = timezone(timedelta(hours=8))

# 可执行代码目录：这些目录下的东西一旦被无声带上车，后果是线上行为改变，
# 不是多一个 md 文件。所以此处禁止任何通配，必须精确到文件名。
CODE_DIRS = ('scripts/', 'functions/', 'mcp-server/', 'adapters/')
WILDCARD_CHARS = '*?['


def _first_wildcard(pattern):
    idx = [pattern.find(c) for c in WILDCARD_CHARS]
    idx = [i for i in idx if i >= 0]
    return min(idx) if idx else -1


def classify_intent(pattern):
    """把一条 --intent 归类：exact / glob / overbroad / overbroad_code。"""
    p = (pattern or '').strip().replace('\\', '/')
    if not p:
        return 'overbroad', '空模式'
    if p in ('*', '**', '.', './', '*/*', '**/*'):
        return 'overbroad', '匹配全仓，等于没声明'
    w = _first_wildcard(p)
    if w < 0:
        return 'exact', ''
    prefix = p[:w]
    if '/' not in prefix:
        # 形如 *.py / promote* —— 会跨目录扫全仓
        return 'overbroad', '通配符前没有目录限定（%s），会跨目录命中' % (prefix or '空',)
    for d in CODE_DIRS:
        if prefix.startswith(d) or d.rstrip('/') == prefix.rstrip('/'):
            return 'overbroad_code', '代码目录 %s 下禁止通配，必须精确到文件名' % d
    return 'glob', ''


def _matches(path, pattern):
    p = path.replace('\\', '/')
    pat = pattern.strip().replace('\\', '/')
    if _first_wildcard(pat) < 0:
        return p == pat
    return fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(p, pat.rstrip('/') + '/*')


def evaluate(staged, intents, mtimes=None, run_start=None):
    """纯函数：给定暂存清单与声明，判定是否放行。

    staged    : list[str]  暂存文件路径（仓库相对）
    intents   : list[str]  本轮声明打算改的文件/模式
    mtimes    : dict[str, float] | None  路径 -> mtime(epoch秒)；缺省不做 stale 判定
    run_start : float | None  本轮起手时刻 epoch 秒
    """
    staged = [s.replace('\\', '/') for s in (staged or [])]
    intents = [i for i in (intents or []) if str(i).strip()]
    res = {
        'ok': False, 'staged': staged,
        'undeclared': [], 'stale': [], 'overbroad': [], 'unused': [], 'covered': [],
    }
    if staged and not intents:
        res['overbroad'].append(('<未提供 --intent>', '暂存了 %d 个文件却没有声明任何意图' % len(staged)))
        return res

    for pat in intents:
        kind, why = classify_intent(pat)
        if kind in ('overbroad', 'overbroad_code'):
            res['overbroad'].append((pat, why))

    for f in staged:
        if any(_matches(f, pat) for pat in intents):
            res['covered'].append(f)
        else:
            res['undeclared'].append(f)

    for pat in intents:
        if not any(_matches(f, pat) for f in staged):
            res['unused'].append(pat)

    if mtimes and run_start:
        for f in staged:
            mt = mtimes.get(f)
            if mt is not None and mt < run_start - 1:
                res['stale'].append((f, mt))

    res['ok'] = not (res['undeclared'] or res['stale'] or res['overbroad'])
    return res


# ---------------- CLI 侧：与 git / 文件系统打交道 ----------------

def git(*args):
    return subprocess.run(['git'] + list(args), cwd=ROOT, capture_output=True,
                          text=True, encoding='utf-8', errors='replace')


def cmd_begin():
    head = git('rev-parse', 'HEAD').stdout.strip()
    dirty = [l for l in git('status', '--porcelain').stdout.splitlines() if l.strip()]
    now = datetime.now(CST)
    state = {
        'started_at': now.isoformat(timespec='seconds'),
        'started_epoch': now.timestamp(),
        'head': head,
        'worktree_clean': not dirty,
        'dirty_at_start': dirty[:50],
    }
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, 'w', encoding='utf-8') as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    print('起点已记录: %s  HEAD=%s  工作区%s' %
          (state['started_at'], head[:8], '干净' if state['worktree_clean'] else '有 %d 处改动' % len(dirty)))

    # 起手就脏 = 上一轮把活漏在工作区没提交 —— 这不是"记一笔"，是要停下来看的事。
    #
    # 2026-08-09 的真实事故：上一轮改了 39 个文件（含 functions/、api/entities.json），
    # 暂存了、部署也没做、更没提交，然后收工。本轮起手 `git status` 39 处改动，
    # 而 cmd_begin 只是打印一句"工作区有 39 处改动"并 return 0 —— 照常放行。
    # 后果：那 39 个文件里的生产代码**只存在于工作区**，不在任何提交、也不在远端；
    # 任何一次 `git checkout .` / `reset --hard` 都会把它悄悄抹掉，
    # 而从干净克隆重新部署会把**旧代码**推回生产（静默回滚）。
    #
    # 飞轮每小时从一个"已落定"的状态起手，所以起手脏在语义上只有一个解释：
    # 上一轮没收尾。判红不阻止你继续（确认后照常干活），只是不许它无声滑过去。
    if dirty:
        staged = [l for l in dirty if l[0] not in ' ?']
        print('\n⚠️  起手工作区不干净：%d 处改动，其中 %d 处已暂存未提交。' % (len(dirty), len(staged)))
        print('    飞轮每轮都从已落定状态起手 —— 起手就脏＝上一轮活没收尾。')
        print('    若这些是上一轮的成果：先核对再提交，别让生产代码只活在工作区。')
        for l in dirty[:10]:
            print('      %s' % l)
        if len(dirty) > 10:
            print('      …… 另有 %d 处' % (len(dirty) - 10))
        return 3
    return 0


def load_run_start():
    try:
        with open(STATE, encoding='utf-8') as fh:
            return json.load(fh).get('started_epoch')
    except Exception:
        return None


def cmd_check(intents, start_override=None, strict_stale=True):
    out = git('diff', '--cached', '--name-only')
    staged = [l.strip() for l in out.stdout.splitlines() if l.strip()]
    if not staged:
        print('暂存区为空，无需核对。')
        return 0
    mtimes = {}
    for f in staged:
        fp = os.path.join(ROOT, f)
        if os.path.exists(fp):
            mtimes[f] = os.path.getmtime(fp)
    run_start = start_override if start_override else (load_run_start() if strict_stale else None)
    res = evaluate(staged, intents, mtimes, run_start)

    print('=== 提交清单守卫 ===')
    print('暂存 %d 个文件；声明 %d 条 intent；起点 %s' %
          (len(staged), len(intents),
           datetime.fromtimestamp(run_start, CST).strftime('%H:%M:%S') if run_start else '未记录(跳过 stale 判定)'))
    for f in res['covered']:
        print('  ✅ %s' % f)
    for pat, why in res['overbroad']:
        print('  ❌ intent 过宽: %s —— %s' % (pat, why))
    for f in res['undeclared']:
        print('  ❌ 未声明却被暂存: %s  ←先查清它为什么变了，再决定是否提交' % f)
    for f, mt in res['stale']:
        print('  ❌ 非本轮修改却被暂存: %s (mtime %s)' %
              (f, datetime.fromtimestamp(mt, CST).strftime('%m-%d %H:%M:%S')))
    for pat in res['unused']:
        print('  ·  声明了但无对应暂存改动: %s' % pat)
    print('结论: %s' % ('放行' if res['ok'] else '判红——停下来核对，确认无误后把文件补进 --intent'))
    return 0 if res['ok'] else 1


# ---------------- 阴阳对照自测（基准全部钉死在用例内部） ----------------

def selftest(check=None):
    """返回 [(通过?, 说明), ...]；check 可传入 regression 的 check 以便统一计数。"""
    results = []

    def ck(cond, msg):
        results.append((bool(cond), msg))
        if check:
            check(bool(cond), msg)

    T0 = 1000000.0          # 本轮起手（虚构，钉死）
    LATER = T0 + 600        # 本轮内修改
    EARLIER = T0 - 7200     # 两小时前就改了

    # 阳性 1：复现真实事故 —— 未声明的 promote.mjs 混进暂存
    r = evaluate(['scripts/staged_guard.py', 'scripts/promote.mjs'],
                 ['scripts/staged_guard.py'],
                 {'scripts/staged_guard.py': LATER, 'scripts/promote.mjs': LATER}, T0)
    ck((not r['ok']) and r['undeclared'] == ['scripts/promote.mjs'],
       '阳性: 未声明的 scripts/promote.mjs 混进暂存被精确判红（复现 8/8 16:18 事故）')

    # 阳性 2：用 scripts/* 把事故文件罩进去 —— 代码目录禁通配，仍须判红
    r = evaluate(['scripts/staged_guard.py', 'scripts/promote.mjs'], ['scripts/*'],
                 {'scripts/staged_guard.py': LATER, 'scripts/promote.mjs': LATER}, T0)
    ck((not r['ok']) and any(p == 'scripts/*' for p, _ in r['overbroad']),
       '阳性: 代码目录通配 scripts/* 被拒（否则一条 glob 就能绕开整个守卫）')

    # 阳性 3：全局通配
    for bad in ('*', '**', '*.py', 'promote*'):
        r = evaluate(['scripts/promote.mjs'], [bad], None, None)
        ck((not r['ok']) and r['overbroad'], '阳性: 过宽 intent %r 被拒' % bad)

    # 阳性 4：非本轮修改却被暂存
    r = evaluate(['scripts/promote.mjs'], ['scripts/promote.mjs'],
                 {'scripts/promote.mjs': EARLIER}, T0)
    ck((not r['ok']) and r['stale'] and r['stale'][0][0] == 'scripts/promote.mjs',
       '阳性: mtime 早于本轮起点的文件被判 stale（"我没改它，谁改的？"）')

    # 阳性 5：有暂存却完全没声明
    r = evaluate(['a.md'], [], None, None)
    ck(not r['ok'], '阳性: 暂存非空但 intent 为空 → 判红（不许免声明提交）')

    # 阴性 1：逐个精确声明 → 放行
    r = evaluate(['scripts/staged_guard.py', 'ops/results/_LATEST.md'],
                 ['scripts/staged_guard.py', 'ops/results/_LATEST.md'],
                 {'scripts/staged_guard.py': LATER, 'ops/results/_LATEST.md': LATER}, T0)
    ck(r['ok'] and not r['undeclared'], '阴性: 逐个精确声明的正常提交放行（守卫不阻塞日常）')

    # 阴性 2：运营目录 glob 允许（ops/ 全是本飞轮自己的产物，逐个列没有信息量）
    r = evaluate(['ops/results/_LATEST.md', 'ops/results/_SUMMARY.md'],
                 ['ops/results/*.md'],
                 {'ops/results/_LATEST.md': LATER, 'ops/results/_SUMMARY.md': LATER}, T0)
    ck(r['ok'], '阴性: ops/results/*.md 这类运营目录 glob 被允许（严格要用在刀刃上）')

    # 阴性 3：声明了但没改动 → 只提示，不判红
    r = evaluate(['a.md'], ['a.md', 'ops/results/*.md'], {'a.md': LATER}, T0)
    ck(r['ok'] and r['unused'] == ['ops/results/*.md'],
       '阴性: 声明了却无对应改动只提示不判红（否则会逼人事后裁剪声明）')

    # 阴性 4：无起点时刻时不做 stale 判定（缺状态≠指控）
    r = evaluate(['scripts/promote.mjs'], ['scripts/promote.mjs'],
                 {'scripts/promote.mjs': EARLIER}, None)
    ck(r['ok'] and not r['stale'], '阴性: 未记录起点时不臆断 stale（无证据不定罪）')

    # 隔离性：evaluate 不读 git、不读磁盘 —— 注入不存在的路径照样得同样结论
    r1 = evaluate(['no/such/file-zzz.md'], ['no/such/file-zzz.md'], None, None)
    r2 = evaluate(['no/such/file-zzz.md'], ['other.md'], None, None)
    ck(r1['ok'] and not r2['ok'],
       '隔离性: evaluate 是纯函数，结论只由注入参数决定（不向环境取值）')

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--begin', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--intent', action='append', default=[])
    ap.add_argument('--start-epoch', type=float, default=None)
    a = ap.parse_args()
    if a.begin:
        return cmd_begin()
    if a.selftest:
        rs = selftest()
        for ok, msg in rs:
            print('%s %s' % ('✅' if ok else '❌', msg))
        bad = [m for ok, m in rs if not ok]
        print('自测 %d/%d 通过' % (len(rs) - len(bad), len(rs)))
        return 1 if bad else 0
    return cmd_check(a.intent, a.start_epoch)


if __name__ == '__main__':
    sys.exit(main())
