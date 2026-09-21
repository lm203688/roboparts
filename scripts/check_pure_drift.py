#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯漂移判别器 —— 部署后收口提交的机械前置闸门。

## 为什么需要它

部署会重生成一批派生文件（api/*.json 的 `updated`/`audited_at` 滚日、llms.txt 的
「最后更新」、data.js 的 updated、注入器重渲染的空白归一化）。这类改动收口时通常
打成一句「漂移收口：仅时间戳滚日，无内容改动」。

**但这句话此前只能靠人肉核验。** `scripts/auto_drift_heal.py` 的做法是
`git add -A` + `git commit -m "auto-heal: drift remediation"` —— 它只看
`git status` 是否有改动，不看改动**是什么**。于是：
  真内容改动（改了数字、改了文案、改了逻辑）会被贴上「drift」标签静默入库，
  而 review 者看到 "drift remediation" 就放过去了。
这与本仓其它「闸门自己假绿」的病史同源：检测器无法区分两种性质不同的输入。

## 判别口径（三层，逐文件取最强判据）

| 文件类型 | 判据 |
|---|---|
| `.json` | 解析后**结构比较**：两侧把白名单时间戳键替换为占位符，其余字段必须完全相等 |
| 其余文本 | ① 去掉全部空白后相等 ⇒ `whitespace`；② 再把 ISO 日期/时刻 token 抹掉后相等 ⇒ `timestamp` |

白名单里的 `entities_sha256` / `source_digest` 属**派生自字节**的哈希：时间戳一动
它们必然跟着动，故一并忽略 —— 这不放松强度，因为其**上游内容**（entities 数组本身）
已在结构比较里逐字段对齐。

## 已知盲区（诚实登记，勿当成绿灯）

- 文本层抹日期 token 属于**弱判据**：若真内容改动恰好只涉及日期文本（例如把
  「2026-08 判断」改成「2026-09 判断」），会被误判为 timestamp。JSON 层无此问题，
  因为结构比较不抹值。凡结论为 `timestamp` 的文本文件，本器都会在输出里标注
  `(文本弱判据)`，提示人再看一眼。
- 二进制文件一律判 `content`（不猜测语义）。

用法:
    python scripts/check_pure_drift.py                # 工作树 vs HEAD，有内容改动则 exit 1
    python scripts/check_pure_drift.py --base <ref>   # 指定基准
    python scripts/check_pure_drift.py --root <dir>   # 审计别的检出目录
    python scripts/check_pure_drift.py --quiet        # 只输出一行结论
    python scripts/check_pure_drift.py --self-test    # 阴阳对照自证（含临时仓库端到端）

## 为什么 CI 只跑 --self-test

审计模式（工作树 vs HEAD）在 CI 上恒为「无改动」——**没有信号**；在工作树上则
必然把正常开发中的源改动报成内容改动——**假警报**。两种场合它都不该被当成 CI 闸门。
它真正的调用点是收口路径：`scripts/auto_drift_heal.py` 在 `git add -A` 之前调
本器，不过关即拒绝自动提交。CI 上该守的是**本器自身会不会退化**，故 CI 只跑
`--self-test`，而自证里带一条真实临时 git 仓库的端到端用例，覆盖「取 diff →
逐文件分类 → 汇总判定」整条管道，而不只是 classify() 这个纯函数。
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 允许随部署滚动的键名（时间戳 / 派生自字节的摘要）
TS_KEYS = {
    'updated', 'audited_at', 'last_updated', 'generated_at', 'built_at',
    'deployed_at', 'refreshed_at', 'snapshot_at', 'as_of', 'reflowed_at',
    'upstream_time', 'entities_sha256', 'source_digest', 'generated',
}

# 文本层日期 token：ISO 日期 / 日期时刻 / 仅月份
_ISO_DATE = re.compile(r'\b20\d\d-\d\d(-\d\d)?(T\d\d:\d\d(:\d\d)?(\.\d+)?'
                       r'(Z|[+-]\d\d:?\d\d)?)?\b')
_LABELED_TS = re.compile(r'(最后更新|更新于|更新时间|生成于|审计于)[:：]\s*\S+')


def _git(*args, root=None):
    r = subprocess.run(['git'] + list(args), cwd=root or ROOT, capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    return r.stdout


def scrub_json(obj):
    """递归把白名单键替换为占位符。"""
    if isinstance(obj, dict):
        return {k: ('<TS>' if k in TS_KEYS else scrub_json(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_json(x) for x in obj]
    return obj


def scrub_text(s):
    s = _LABELED_TS.sub(lambda m: m.group(1) + '：<TS>', s)
    return _ISO_DATE.sub('<TS>', s)


def strip_ws(s):
    return re.sub(r'\s+', '', s)


def classify(path, old_text, new_text):
    """返回 (类别, 说明)。类别 ∈ {unchanged, whitespace, timestamp, content}。"""
    if old_text == new_text:
        return 'unchanged', ''
    if path.endswith('.json'):
        try:
            a, b = scrub_json(json.loads(old_text)), scrub_json(json.loads(new_text))
        except Exception as e:  # noqa: BLE001
            return 'content', 'JSON 解析失败: %s' % e
        if a == b:
            return 'timestamp', '仅白名单时间戳/派生摘要键变动'
        return 'content', _first_json_diff(a, b)
    # 二进制探测（NUL 字节）
    if '\x00' in old_text or '\x00' in new_text:
        return 'content', '二进制文件，不猜测语义'
    if strip_ws(old_text) == strip_ws(new_text):
        return 'whitespace', '仅空白差异'
    if scrub_text(old_text) == scrub_text(new_text):
        return 'timestamp', '仅日期 token 变动 (文本弱判据)'
    return 'content', _first_text_diff(old_text, new_text)


def _first_json_diff(x, y, path=''):
    if type(x) is not type(y):
        return '%s: 类型 %s -> %s' % (path or '$', type(x).__name__, type(y).__name__)
    if isinstance(x, dict):
        for k in sorted(set(x) | set(y)):
            if k not in x:
                return '%s.%s 新增' % (path, k)
            if k not in y:
                return '%s.%s 删除' % (path, k)
            d = _first_json_diff(x[k], y[k], '%s.%s' % (path, k))
            if d:
                return d
    elif isinstance(x, list):
        if len(x) != len(y):
            return '%s: 长度 %d -> %d' % (path, len(x), len(y))
        for i, (p, q) in enumerate(zip(x, y)):
            d = _first_json_diff(p, q, '%s[%d]' % (path, i))
            if d:
                return d
    elif x != y:
        return '%s: %r -> %r' % (path, str(x)[:60], str(y)[:60])
    return ''


def _first_text_diff(a, b):
    la, lb = scrub_text(a).splitlines(), scrub_text(b).splitlines()
    for i in range(max(len(la), len(lb))):
        x = la[i] if i < len(la) else '<缺行>'
        y = lb[i] if i < len(lb) else '<缺行>'
        if strip_ws(x) != strip_ws(y):
            return 'L%d: %r -> %r' % (i + 1, x.strip()[:70], y.strip()[:70])
    return '行数或空白不同'


def changed_files(base):
    out = _git('diff', '--name-status', base)
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) >= 2 and parts[0] in ('M', 'T'):
            rows.append((parts[0], parts[-1]))
    return rows


def read_worktree(path):
    p = os.path.join(ROOT, path.replace('/', os.sep))
    try:
        with open(p, encoding='utf-8') as f:
            return f.read()
    except Exception:  # noqa: BLE001
        with open(p, 'rb') as f:
            return f.read().decode('utf-8', errors='replace')


def main():
    global ROOT
    if '--self-test' in sys.argv:
        return self_test()

    quiet = '--quiet' in sys.argv
    base = 'HEAD'
    if '--base' in sys.argv:
        base = sys.argv[sys.argv.index('--base') + 1]
    # --root 用于对别的检出目录审计（也是自证里端到端用例的入口）。
    # 刻意做成显式 CLI 参数而不是环境变量：本仓 L1.94 要求 scripts/ 读的每个 env 键
    # 都登记进 scripts/env_contract.json，为一处测试钩子引入全局 env 旋钮不划算。
    if '--root' in sys.argv:
        ROOT = os.path.abspath(sys.argv[sys.argv.index('--root') + 1])

    rows = changed_files(base)
    if not rows:
        print('PURE-DRIFT: PASS（工作树相对 %s 无改动）' % base)
        return 0

    buckets = {'whitespace': [], 'timestamp': [], 'content': []}
    for _st, path in rows:
        old = _git('show', '%s:%s' % (base, path))
        if old == '' and path not in _git('ls-tree', '--name-only', base, '--', path):
            buckets['content'].append((path, '新增文件（非漂移）'))
            continue
        kind, why = classify(path, old, read_worktree(path))
        if kind in buckets:
            buckets[kind].append((path, why))

    n = sum(len(v) for v in buckets.values())
    if quiet:
        print('PURE-DRIFT: %s（%d 文件: whitespace=%d timestamp=%d content=%d）'
              % ('FAIL' if buckets['content'] else 'PASS', n,
                 len(buckets['whitespace']), len(buckets['timestamp']),
                 len(buckets['content'])))
        return 1 if buckets['content'] else 0

    print('=== 纯漂移判别（基准 %s，%d 个改动文件）===' % (base, n))
    for name, label in (('whitespace', '空白归一化'), ('timestamp', '时间戳滚动'),
                        ('content', '❗内容改动')):
        if buckets[name]:
            print('  %s: %d' % (label, len(buckets[name])))
            for path, why in buckets[name][:40]:
                print('     %-56s %s' % (path, why[:90]))
    if buckets['content']:
        print()
        print('  ❌ 存在 %d 个内容改动文件 —— 不得以「漂移收口」名义提交。'
              % len(buckets['content']))
        print('     请按内容改动单独提交（并在 commit message 里说明改了什么）。')
        return 1
    print()
    print('  ✅ 全部为空白/时间戳漂移，可安全收口为 drift commit')
    return 0


def self_test():
    """阴阳对照：证明本器能区分「纯漂移」与「内容改动」。"""
    fails = []
    n = 0
    cases = [
        # (标签, 期望类别, 旧, 新, 文件名)
        ('JSON 仅 updated 滚日', 'timestamp',
         '{"a":1,"meta":{"updated":"2026-09-20","n":798}}',
         '{"a":1,"meta":{"updated":"2026-09-21","n":798}}', 'api/x.json'),
        ('JSON 派生摘要变动', 'timestamp',
         '{"meta":{"source_digest":"aaaaaaaa","updated":"2026-09-20"}}',
         '{"meta":{"source_digest":"bbbbbbbb","updated":"2026-09-21"}}', 'api/x.json'),
        ('JSON 数字真改动(阴性)', 'content',
         '{"meta":{"updated":"2026-09-20","n":798}}',
         '{"meta":{"updated":"2026-09-20","n":688}}', 'api/x.json'),
        ('JSON 文案真改动(阴性)', 'content',
         '{"name":"机器人零件兼容性判定层"}',
         '{"name":"仿生机器人生态平台"}', 'api/x.json'),
        ('JSON 数组长度变化(阴性)', 'content',
         '{"items":[1,2,3]}', '{"items":[1,2]}', 'api/x.json'),
        ('文本仅空白', 'whitespace',
         '<h1>标题</h1>\n\n  \n<p>正文</p>',
         '<h1>标题</h1>\n<p>正文</p>', 'a.html'),
        ('文本仅日期 token', 'timestamp',
         '# T\n> 最后更新：2026-09-20T04:16:00Z\n', '# T\n> 最后更新：2026-09-21T04:16:00Z\n', 'llms.txt'),
        ('文本仅 updated 字段', 'timestamp',
         '  "updated": "2026-09-20T06:00:37.953091Z",\n',
         '  "updated": "2026-09-21T02:38:49.352913Z",\n', 'data.js'),
        ('文本词语真改动(阴性)', 'content',
         'RoboParts 机器人零件兼容性判定层', 'RoboParts 仿生机器人生态平台', 'x.txt'),
        ('文本数字真改动(阴性)', 'content',
         '收录 133 个开源组件', '收录 325 个开源组件', 'x.txt'),
        ('无改动', 'unchanged', 'same', 'same', 'x.txt'),
    ]
    for label, want, old, new, fn in cases:
        n += 1
        got, why = classify(fn, old, new)
        if got != want:
            fails.append('  %-24s 期望 %s，实得 %s（%s）' % (label, want, got, why))
    # 自证本身也要能失败：把分类器换成一个恒返回 timestamp 的桩，必须报错
    n += 1
    stub = lambda *_a: ('timestamp', '')  # noqa: E731
    if not any(stub(f, o, nw)[0] != w for _l, w, o, nw, f in cases):
        fails.append('  自证无效：恒真桩未被检出')

    # ---- 端到端：真实临时 git 仓库，覆盖「取 diff → 分类 → 汇总判定」整条管道 ----
    # 只测 classify() 不够：changed_files() 的 base 解析、--base 传参、
    # read_worktree 的编码路径都可能坏，而坏了的表现是「报 0 个改动」——
    # 一个看起来最健康的数字（与 L1.76 数字识别器报 0 条同类）。
    n += 1
    e2e_fail = _e2e_temp_repo()
    if e2e_fail:
        fails.append(e2e_fail)

    if fails:
        print('纯漂移判别器自证: FAIL')
        for x in fails:
            print(x)
        return 1
    print('纯漂移判别器自证: PASS（%d 项，含 5 条内容改动阴性对照 + 1 条临时仓库端到端）'
          % n)
    return 0


def _e2e_temp_repo():
    """在临时目录建一个真 git 仓库，跑完整审计路径，返回失败说明（成功返回 ''）。"""
    import shutil
    import tempfile

    d = tempfile.mkdtemp(prefix='pure-drift-e2e-')
    try:
        def g(*a):
            return subprocess.run(['git'] + list(a), cwd=d, capture_output=True,
                                  text=True, encoding='utf-8', errors='replace')

        g('init', '-q')
        g('config', 'user.email', 'e2e@local')
        g('config', 'user.name', 'e2e')
        os.makedirs(os.path.join(d, 'api'), exist_ok=True)
        with open(os.path.join(d, 'api', 'x.json'), 'w', encoding='utf-8') as f:
            f.write('{"meta":{"updated":"2026-09-20","n":798}}')
        with open(os.path.join(d, 'page.html'), 'w', encoding='utf-8') as f:
            f.write('<h1>T</h1>\n\n<p>798</p>')
        g('add', '-A')
        g('commit', '-qm', 'base')

        # 阶段 ①：纯漂移（时间戳 + 空白）→ 必须 PASS
        with open(os.path.join(d, 'api', 'x.json'), 'w', encoding='utf-8') as f:
            f.write('{"meta":{"updated":"2026-09-21","n":798}}')
        with open(os.path.join(d, 'page.html'), 'w', encoding='utf-8') as f:
            f.write('<h1>T</h1>\n<p>798</p>')
        r = subprocess.run([sys.executable, os.path.abspath(__file__), '--root', d],
                           cwd=d, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        if r.returncode != 0:
            return ('  端到端 ①失败：纯漂移被误判为红灯（rc=%s）\n%s'
                    % (r.returncode, (r.stdout or '')[-400:]))

        # 阶段 ②：夹带真内容改动（798 -> 688）→ 必须红
        with open(os.path.join(d, 'api', 'x.json'), 'w', encoding='utf-8') as f:
            f.write('{"meta":{"updated":"2026-09-21","n":688}}')
        r = subprocess.run([sys.executable, os.path.abspath(__file__), '--root', d],
                           cwd=d, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        if r.returncode == 0:
            return ('  端到端 ②失败：夹带的真内容改动（798→688）未被判红\n%s'
                    % (r.stdout or '')[-400:])
        return ''
    except Exception as e:  # noqa: BLE001
        return '  端到端 异常: %s' % e
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
