#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史重写感知的哈希解析器（全仓唯一识别器）。

── 这个模块为什么存在 ──

2026-08-10 17:30，用户执行 `git filter-repo` 清除 13 份运营文档在公开仓历史中的
痕迹（这是 `_NEEDS_USER.md` 里挂了多日、只能由本人操作的事项）。副作用是**全仓
87 个提交哈希被整体重写**：此前每一轮运行如实记录在 `ops/results/*.md` 里的提交
哈希，在新对象库中一律「查无此物」。

于是 regression 里三道靠 git 取证的闸门同时判红：
  1. L1.x「报告声称的提交哈希在仓库中真实存在」→ 3 个幽灵哈希；
  2. L1.40「补写报告引用至少一个真实存在的 commit 哈希」→ 4 份无据重建；
  3. L1.59「可从 git 取到修复前原版做阴性对照」→ `git show 822296c:...` 失败。

**这三条红都是假红**：报告没造假，是历史被合法重写了。而假红比漏报更致命
（本仓 8/9 立的纪律）——恒红会逼下一轮去放宽判据，亲手造出闸门本要防的假绿。
最省事的放宽写法是「查不到就跳过」，那等于把这三道闸门一起废掉。

── 正确的修法 ──

filter-repo 会留下 `.git/filter-repo/commit-map`（old40 → new40）。把它固化成
**受版本控制的台账**（`.git/` 不入库，随时可能被清掉；台账必须活得比它久），
解析顺序改为：

    对象库里有       → 真实存在（原样）
    对象库里没有，但在台账 old 列 → 曾真实存在，只是被改名（返回新哈希）
    两边都没有       → 幽灵（伪造）—— 判据强度不变

伪造的哈希在对象库和映射表里都查不到，检出能力**一点没降**；反而新增了
「把重写前哈希解析回当前哈希」的能力，让阴性对照这类需要真跑旧代码的闸门
在历史重写后继续可用。
"""

import json
import os
import subprocess

LEDGER_REL = os.path.join('ops', 'history_rewrite_ledger.json')


def ledger_path(root):
    return os.path.join(root, LEDGER_REL)


def load_ledger(root):
    p = ledger_path(root)
    if not os.path.isfile(p):
        return {'version': 1, 'events': []}
    try:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        if not isinstance(d, dict) or not isinstance(d.get('events'), list):
            return {'version': 1, 'events': []}
        return d
    except Exception:
        return {'version': 1, 'events': []}


def _read_commit_map(root):
    """读取 filter-repo 的 old→new 映射；不存在返回 {}。

    注意 filter-repo 会把「被删掉的提交」映射到全 0 哈希，这类不算改名，
    原样保留即可（解析时全 0 视为不可解析，仍走幽灵判定）。
    """
    p = os.path.join(root, '.git', 'filter-repo', 'commit-map')
    if not os.path.isfile(p):
        return {}
    out = {}
    with open(p, encoding='utf-8', errors='replace') as f:
        for line in f:
            parts = line.split()
            if len(parts) != 2 or parts[0] == 'old':
                continue
            if len(parts[0]) != 40 or len(parts[1]) != 40:
                continue
            out[parts[0]] = parts[1]
    return out


def _read_ref_map(root):
    p = os.path.join(root, '.git', 'filter-repo', 'ref-map')
    if not os.path.isfile(p):
        return []
    rows = []
    with open(p, encoding='utf-8', errors='replace') as f:
        for line in f:
            parts = line.split()
            if len(parts) == 3 and parts[0] != 'old':
                rows.append({'old': parts[0], 'new': parts[1], 'ref': parts[2]})
    return rows


def sync_from_filter_repo(root):
    """把 `.git/filter-repo/` 的映射固化进台账；**幂等**。

    幂等判据用 (old_head,new_head,n) 三元组，不用文件 mtime —— mtime 会被
    任何一次无关的 filter-repo 空跑刷新，用它做判据会每轮追加一条重复事件。

    返回 (是否新增, 台账内映射总条数)。
    """
    cmap = _read_commit_map(root)
    refs = _read_ref_map(root)
    if not cmap or not refs:
        led = load_ledger(root)
        return (False, sum(len(e.get('map') or {}) for e in led['events']))

    main = next((r for r in refs if r['ref'].endswith('/main')), refs[0])
    key = (main['old'], main['new'], len(cmap))
    led = load_ledger(root)
    for ev in led['events']:
        if (ev.get('old_head'), ev.get('new_head'),
                len(ev.get('map') or {})) == key:
            return (False, sum(len(e.get('map') or {}) for e in led['events']))

    st = os.stat(os.path.join(root, '.git', 'filter-repo', 'commit-map'))
    import datetime as _dt
    led['events'].append({
        'rewritten_at': _dt.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%dT%H:%M'),
        'tool': 'git filter-repo',
        'reason': '清除 13 份运营文档在公开仓历史中的痕迹（用户本人执行）',
        'ref': main['ref'],
        'old_head': main['old'],
        'new_head': main['new'],
        'map': cmap,
    })
    with open(ledger_path(root), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(led, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')
    return (True, sum(len(e.get('map') or {}) for e in led['events']))


_ZERO = '0' * 40


def _mapping(root):
    led = load_ledger(root)
    m = {}
    for ev in led['events']:
        for o, n in (ev.get('map') or {}).items():
            if n and n != _ZERO:
                m[o] = n
    return m


def object_type(root, sha, repos=None):
    """该哈希在当前对象库里的真实类型；查无返回 None。"""
    for repo in (repos or [root]):
        if not os.path.isdir(os.path.join(repo, '.git')):
            continue
        try:
            r = subprocess.run(['git', 'cat-file', '-t', sha], cwd=repo,
                               capture_output=True, text=True, timeout=15)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return None


def resolve(root, sha, repos=None):
    """解析一个（可能是缩写的）哈希。

    返回 (status, current_sha, obj_type)：
      ('current',   原哈希, 类型)  —— 当前对象库里就有
      ('rewritten', 新哈希, 类型)  —— 重写前的真实哈希，已映射到当前哈希
      ('unknown',   None,   None)  —— 两边都查不到 = 幽灵
    """
    sha = (sha or '').strip().lower()
    if not sha:
        return ('unknown', None, None)
    t = object_type(root, sha, repos)
    if t:
        return ('current', sha, t)
    m = _mapping(root)
    new = m.get(sha)
    if new is None and 7 <= len(sha) < 40:
        hits = {v for k, v in m.items() if k.startswith(sha)}
        # 缩写撞到多个不同目标 = 不可判定，宁可当幽灵也不猜
        new = hits.pop() if len(hits) == 1 else None
    if not new:
        return ('unknown', None, None)
    return ('rewritten', new, object_type(root, new, repos))


def to_current(root, sha, repos=None):
    """解析成当前对象库里可用的哈希；不可解析返回 None。"""
    st, cur, _ = resolve(root, sha, repos)
    return cur if st in ('current', 'rewritten') else None
