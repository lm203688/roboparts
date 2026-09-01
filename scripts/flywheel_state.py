#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""飞轮幂等/可恢复治理 · 阶段状态台账（signal→candidate→promote→effect）

借鉴 team.openclaw.ai 的任务闭环思想：每轮飞轮是一串"信号→候选→推广→效果"阶段，
治理目标是两件事：
  1) 幂等（idempotent）：同一输入重跑不产生副作用/重复应用；
  2) 可恢复（recoverable）：某阶段崩溃后，下一轮能靠"输入指纹是否变化"决定
     跳过未变阶段（继续），而非从头全跑或重复应用。

本模块是这条链路的**共享纯函数引擎**，不依赖网络、不依赖 git 历史：
  - fingerprint(obj)              稳定指纹（canonical JSON 的 sha256 前 16 位）
  - record_stage(states,...)     纯函数：写入某阶段状态，不修改入参
  - compute_should_run(prev,...) 纯函数：上一轮 OK 且输入指纹未变 → skip
  - load_states / save_states    损坏可恢复（load 返回 {}）+ 原子写（temp+rename）
  - CLI: record / should-run / fingerprint-file / --self-test

约定（与 run_lock / staged_guard / hash_history 同源纪律）：
  - 所有判定函数都是纯函数，基准钉死在 selftest 内部，绝不向环境取值；
  - 写文件一律 temp+rename，崩溃不会留下半截文件；
  - 状态文件路径默认 ops/results/_flywheel_state.json（运营态，不入主库对外 JSON）。

用法
----
  python scripts/flywheel_state.py record signal --file api/demand-signal.json --ok 1
  python scripts/flywheel_state.py should-run candidate <fp>      # 打印 run / skip
  python scripts/flywheel_state.py fingerprint-file api/entities.contrib.json
  python scripts/flywheel_state.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'ops', 'results', '_flywheel_state.json')
CST = timezone(timedelta(hours=8))


# ---------------------------------------------------------------- 纯函数

def fingerprint(obj) -> str:
    """稳定指纹：canonical JSON（排序键、紧凑分隔）→ sha256 前 16 位。"""
    canonical = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                           separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]


def fingerprint_file(path: str) -> str:
    """文件内容的稳定指纹（用于"输出指纹"）。

    读不到文件时返回全 0 —— 调用方据此应判为"需 run"而非崩溃。
    """
    try:
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return '0' * 16


def record_stage(states: dict, name: str, input_fp: str,
                 output_fp: str, ok: bool) -> dict:
    """纯函数：写入某阶段状态，返回**新** dict，不改动入参。"""
    new = dict(states or {})
    new[name] = {
        'input_fp': input_fp,
        'output_fp': output_fp,
        'ok': bool(ok),
        'at': datetime.now(CST).isoformat(timespec='seconds'),
    }
    return new


def compute_should_run(prev: dict | None, name: str, input_fp: str) -> bool:
    """纯函数：该阶段本轮是否应运行。

    返回 True=run，False=skip（可恢复/幂等的核心判定）：
      - 无历史        → run（首跑）
      - 历史不 OK      → run（上一轮失败，必须重跑）
      - 输入指纹变化   → run（输入变了，产物需重算）
      - 历史 OK 且同输入 → skip（幂等：没变就不重做）
    """
    prev = prev or {}
    st = prev.get(name)
    if st is None:
        return True
    if not st.get('ok'):
        return True
    if st.get('input_fp') != input_fp:
        return True
    return False


# ---------------------------------------------------------------- 持久化

def load_states(path: str = STATE) -> dict:
    """损坏/缺失可恢复：返回 {}，绝不抛异常。"""
    try:
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get('stages'), dict):
            return d['stages']
        # 老格式容错：顶层直接是 stages
        if isinstance(d, dict):
            return d
        return {}
    except Exception:
        return {}


def save_states(states: dict, path: str = STATE) -> None:
    """原子写：temp 同目录 + os.replace，崩溃不留半截文件。"""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    payload = {
        'version': 1,
        'updated_at': datetime.now(CST).isoformat(timespec='seconds'),
        'stages': states,
    }
    fd, tmp = tempfile.mkstemp(dir=d, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


# ---------------------------------------------------------------- CLI

def cmd_record(args) -> int:
    fp = args.fp
    if args.file:
        fp = fingerprint_file(args.file)
    if not fp:
        fp = '0' * 16
    states = load_states(args.state)
    states = record_stage(states, args.stage, fp, fp, args.ok)
    save_states(states, args.state)
    print(f'✅ 阶段状态已记录 {args.stage} input_fp={fp} ok={args.ok} '
          f'（共 {len(states)} 个阶段在台账）')
    return 0


def cmd_should_run(args) -> int:
    states = load_states(args.state)
    run = compute_should_run(states, args.stage, args.fp)
    print('run' if run else 'skip')
    return 0


def cmd_fingerprint_file(args) -> int:
    print(fingerprint_file(args.path))
    return 0


# ---------------------------------------------------------------- 自测

def selftest() -> int:
    ok, bad = 0, []

    def ck(cond, msg):
        nonlocal ok
        if cond:
            ok += 1
            print(f'  ✅ {msg}')
        else:
            bad.append(msg)
            print(f'  ❌ {msg}')

    # 1 fingerprint 确定性 + 字典键顺序无关（canonical，sort_keys）
    a = fingerprint({'b': 1, 'a': 2})
    b = fingerprint({'a': 2, 'b': 1})
    ck(a == b and len(a) == 16, 'fingerprint 确定性且字典键顺序无关')

    # 2 record_stage 纯函数：不修改入参
    prev = {'signal': {'input_fp': 'x', 'ok': True}}
    prev_copy = json.loads(json.dumps(prev))
    nxt = record_stage(prev, 'candidate', 'fp1', 'fp1', True)
    ck(prev == prev_copy, 'record_stage 不修改入参（纯函数）')
    ck(nxt.get('candidate', {}).get('ok') is True, 'record_stage 写入新阶段的 ok')
    ck('signal' in nxt and 'candidate' in nxt, 'record_stage 保留旧阶段')

    # 3 compute_should_run：首跑→run
    ck(compute_should_run({}, 'signal', 'fp') is True, '无历史 → run')
    # 4 历史 OK 且同输入 → skip（幂等核心）
    ck(compute_should_run({'signal': {'input_fp': 'fp', 'ok': True}},
                          'signal', 'fp') is False, '历史 OK 且同输入 → skip')
    # 5 历史 OK 但输入变化 → run
    ck(compute_should_run({'signal': {'input_fp': 'fp', 'ok': True}},
                          'signal', 'fp2') is True, '历史 OK 但输入变化 → run')
    # 6 历史不 OK → run（可恢复：失败必须重跑）
    ck(compute_should_run({'signal': {'input_fp': 'fp', 'ok': False}},
                          'signal', 'fp') is True, '历史失败 → run')

    # 7 load 损坏/缺失返回 {}（可恢复）
    import tempfile
    tmpd = tempfile.mkdtemp()
    corrupt = os.path.join(tmpd, 'bad.json')
    with open(corrupt, 'w', encoding='utf-8') as f:
        f.write('{{{ not json')
    saved = STATE
    globals()['STATE'] = corrupt
    try:
        ck(load_states(corrupt) == {}, '损坏台账 load → 返回 {}（不崩）')
    finally:
        globals()['STATE'] = saved

    # 8 save/load 往返 + 原子性（temp+rename 已隐含；这里验证内容一致）
    tmp2 = os.path.join(tmpd, 'ok.json')
    s0 = record_stage({}, 'promote', 'p1', 'p1', True)
    save_states(s0, tmp2)
    s1 = load_states(tmp2)
    ck(s1.get('promote', {}).get('ok') is True, 'save→load 往返一致')

    # 9 should-run CLI 等价（通过纯函数已覆盖；这里验证 record 后 should-run=skip）
    tmp3 = os.path.join(tmpd, 'state.json')
    st = record_stage({}, 'candidate', 'abc', 'abc', True)
    save_states(st, tmp3)
    ck(compute_should_run(load_states(tmp3), 'candidate', 'abc') is False,
       'record 后再查同输入 → skip（闭环自洽）')

    print(f'\n结果：{ok} 通过 / {len(bad)} 失败')
    if bad:
        for m in bad:
            print(f'  失败：{m}')
        return 1
    return 0


def main() -> int:
    if '--self-test' in sys.argv:
        return selftest()
    p = argparse.ArgumentParser(description='飞轮阶段状态台账（幂等/可恢复）')
    sub = p.add_subparsers(dest='cmd')
    r = sub.add_parser('record')
    r.add_argument('stage')
    r.add_argument('fp', nargs='?', default='')
    r.add_argument('--file', default='')
    r.add_argument('--ok', type=int, default=1)
    r.add_argument('--state', default=STATE)
    s = sub.add_parser('should-run')
    s.add_argument('stage')
    s.add_argument('fp')
    s.add_argument('--state', default=STATE)
    f = sub.add_parser('fingerprint-file')
    f.add_argument('path')
    args = p.parse_args()
    if getattr(args, 'cmd', None) is None:
        p.print_help()
        return 2
    return {'record': cmd_record, 'should-run': cmd_should_run,
            'fingerprint-file': cmd_fingerprint_file}[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())
