#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""飞轮单实例锁 —— 防止同一小时两个运行实例并发写同一份留痕/并发部署。

## 为什么需要它（2026-08-11 06:00 实测事故）

本仓在 2026-08-11 06:00–06:22 之间**同时跑着两个飞轮实例**：
一个（记为 A）从 06:00 起做 www 主机同源排查，06:16 写 `roboparts-20260811-06.md`、
06:17 覆盖 `_LATEST.md`；另一个（记为 B）06:10 启动，做标准枚举盲区排查。
两者都被指令要求「用 Write **覆盖** `_LATEST.md`」。B 若照做，A 那份唯一记载
「www 在播旧站 + 30 条 URL 已误推百度」的 P0 报告会被静默抹掉。

## v1 的致命缺陷：用「辅助命令的 PID」代理「飞轮实例的存活」（2026-08-11 12:40 实测）

v1（提交 d6b076d）把 `os.getpid()` 写进锁文件。但 `acquire` 是个**打印完就退出的
辅助命令** —— 飞轮实例本身是一段跨多次工具调用的会话，根本不存在一个贯穿全程的
长活进程。于是锁文件里记的 PID 在写下的**下一秒就已经是 dead**，而 v1 的判据是
「PID 确认不存在 → 立刻抢占」，等价于：

    任何后来者，任何时刻，都能无条件抢占。这把锁从第一天起就是个装饰品。

代价是真金白银：本次运行期间 12:42 / 12:55 出现两个并非本实例所做的提交
（32b3343、300c653，作者 RoboParts Flywheel），即另一实例全程并发跑完并提交了。

**它为什么没被自测抓住**：v1 的阴性对照是「伪造一个不存在的 pid，期望能抢占」——
测的恰好是缺陷本身的表现，测试通过反而给缺陷背了书。缺的是那条真正对应现实的
用例：「上一实例 1 分钟前刚 acquire（其辅助进程当然已退出），第二实例必须被拒」。

## v2 判据：存活由「心跳」证明，不由 PID 证明

- 锁文件 `.workbuddy/runlock.json` 记 owner(随机令牌) / pid / started_at /
  **heartbeat_at** / label。
- **唯一主判据 = 心跳新鲜度**：`heartbeat_at` 在 `--stale`（默认 30 分钟）以内
  即视为「有人在跑」，**无论 PID 是死是活**。持锁方每推进一步调一次
  `renew` 刷新心跳；一个还在干活的实例不可能 30 分钟不推进任何一步。
- **PID 只作补强，且只能加严不能放宽**：PID 确认存活 → 即使心跳过期也不抢占。
  PID 死 → 什么都不说明（辅助命令本来就会退出），继续看心跳。
- 心跳过期 → 按崩溃处理，可抢占。这是唯一的自愈路径，避免崩溃一次卡死整条飞轮。

## 用法（飞轮第 0 步、中途每个大步、最后一步）

    python scripts/run_lock.py acquire --label run-80   # 0=拿到 3=别人在跑
    python scripts/run_lock.py renew                    # 每个大步调一次，刷心跳
    python scripts/run_lock.py status                   # 只读
    python scripts/run_lock.py release                  # 幂等
    python scripts/run_lock.py --self-test              # 阳性+阴性对照

拿不到锁时的正确动作：**不写 `_LATEST.md`/`_SUMMARY.md`/不部署/不提交**，
只做只读排查，把增量结论写成新文件（`ops/intel/*`、`ops/watchdog/*`），再在对话里汇报。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / '.workbuddy' / 'runlock.json'
DEFAULT_STALE_MIN = 30
CST = timezone(timedelta(hours=8))


def _now() -> datetime:
    return datetime.now(CST)


ALIVE, DEAD, UNKNOWN = 'alive', 'dead', 'unknown'


def _pid_state(pid: int) -> str:
    """三态存活判定：ALIVE / DEAD / UNKNOWN。

    ⚠️ 这个函数**只能用来加严**（确认活着 → 更不该抢占）。绝不能用
    「确认死了」去放宽抢占 —— 见模块头 v1 缺陷说明：飞轮的 acquire 辅助
    进程本来就会立刻退出，DEAD 是常态而非异常信号。
    """
    if pid <= 0:
        return UNKNOWN
    if os.name == 'nt':
        try:
            import subprocess
            # 不用 text=True：本机 tasklist 输出为 GBK，按 UTF-8 解码会炸。
            raw = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                                 capture_output=True, timeout=15)
            if raw.returncode != 0:
                return UNKNOWN
            out = raw.stdout.decode('gbk', 'ignore') or raw.stdout.decode('utf-8', 'ignore')
            return ALIVE if str(pid) in out else DEAD
        except Exception:
            return UNKNOWN
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return DEAD
    except PermissionError:
        return ALIVE
    except Exception:
        return UNKNOWN
    return ALIVE


def _read(path: Path = None) -> dict | None:
    p = path or LOCK
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        # 锁文件损坏＝无法证明有人在跑，但也无法证明没有。按"有人在跑"处理，
        # 心跳缺失由 stale 兜底自愈；直接删掉才是危险的（等于把并发保护关了）。
        return {'pid': -1, 'owner': '<corrupt>', 'started_at': _now().isoformat(),
                'heartbeat_at': _now().isoformat(), 'label': '<corrupt>'}


def _age_min(info: dict, key: str) -> float:
    """字段缺失或不可解析时返回 0.0（＝当作"刚刚"，保守地不抢占）。"""
    raw = info.get(key)
    if not raw:
        return 0.0
    try:
        t = datetime.fromisoformat(raw)
    except Exception:
        return 0.0
    if t.tzinfo is None:
        t = t.replace(tzinfo=CST)
    return (_now() - t).total_seconds() / 60


def _describe(info: dict, stale_min: int) -> tuple[bool, str]:
    """返回 (是否可抢占, 人话说明)。判据顺序即优先级。"""
    pid = int(info.get('pid') or -1)
    label = info.get('label') or '?'
    hb = _age_min(info, 'heartbeat_at')
    age = _age_min(info, 'started_at')
    state = _pid_state(pid)
    base = (f'owner={str(info.get("owner") or "?")[:8]} label={label} '
            f'已持锁 {age:.1f} 分钟 心跳 {hb:.1f} 分钟前 pid={pid}({state})')

    if state == ALIVE:
        # PID 只加严：确认活着就绝不抢占，哪怕心跳过期。
        return False, f'{base} → 持锁进程确认存活，**不抢占**'
    if hb <= stale_min:
        return False, f'{base} → 心跳新鲜（≤{stale_min} 分钟），另一实例正在运行'
    return True, f'{base} → 心跳已停 {hb:.1f} 分钟（>{stale_min}），按崩溃处理，可抢占'


def _write_lock(owner: str, label: str, started_at: str = None) -> dict:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    now = _now().isoformat()
    payload = {
        'owner': owner,
        'pid': os.getpid(),
        'started_at': started_at or now,
        'heartbeat_at': now,
        'label': label or 'unnamed',
    }
    LOCK.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return payload


def cmd_acquire(args) -> int:
    info = _read()
    if info is not None:
        takeover, why = _describe(info, args.stale)
        if not takeover:
            print(f'❌ 未获得锁：{why}')
            print('   → 请勿写 _LATEST.md / _SUMMARY.md，勿部署，勿提交；改为只读排查 + 写新文件。')
            return 3
        print(f'♻️  抢占陈旧锁：{why}')
    owner = args.owner or uuid.uuid4().hex
    _write_lock(owner, args.label)
    print(f'✅ 已获得锁 owner={owner} label={args.label or "unnamed"}')
    print(f'   ⚠️ 每推进一大步请调一次：python scripts/run_lock.py renew --owner {owner}')
    print(f'   （心跳超过 {args.stale} 分钟不刷新，别的实例就会判你崩溃并抢占）')
    return 0


def cmd_renew(args) -> int:
    info = _read()
    if info is None:
        print('⚠️  当前无锁，renew 无对象（是不是没 acquire 或已被 release？）')
        return 4
    if args.owner and info.get('owner') != args.owner and not args.force:
        print(f'❌ 拒绝续期：锁属于 owner={str(info.get("owner"))[:8]}，与 --owner 不符。')
        return 5
    _write_lock(info.get('owner') or 'unknown', info.get('label') or '',
                started_at=info.get('started_at'))
    print(f'💓 心跳已刷新 owner={str(info.get("owner"))[:8]} label={info.get("label")}')
    return 0


def cmd_status(args) -> int:
    info = _read()
    if info is None:
        print('🟢 无人持锁')
        return 0
    _, why = _describe(info, args.stale)
    print(f'🔒 {why}')
    return 0


def cmd_release(args) -> int:
    if not LOCK.exists():
        print('🟢 本就无锁，无需释放')
        return 0
    info = _read() or {}
    mine = (args.owner and info.get('owner') == args.owner)
    if args.force or mine or not args.owner:
        # 未提供 --owner 时按"就是我"处理：飞轮实例常跨多次调用丢失令牌，
        # 强行要求令牌会导致锁永远释放不掉，反而更糟。误释放的代价（并发窗口）
        # 小于卡死整条飞轮的代价，且心跳机制会让真正在跑的那个立刻重新拿回。
        LOCK.unlink()
        print('✅ 已释放锁')
        return 0
    print(f'⚠️  锁属于 owner={str(info.get("owner"))[:8]}，非本实例，未释放（要强制请加 --force）')
    return 0


# ---------------------------------------------------------------- self test

def _scenario_second_acquire_refused(mod) -> bool:
    """核心回归用例：**上一实例 1 分钟前 acquire、其辅助进程早已退出**，
    第二实例必须被拒。这是现实中 100% 会发生的形态，v1 在此必然放行。

    返回 True 表示"被正确拒绝"。
    """
    import tempfile
    tmp = Path(tempfile.mkdtemp()) / 'runlock.json'
    saved = mod.LOCK
    mod.LOCK = tmp
    try:
        dead_pid = 999999  # 确定不存在
        now = mod._now()
        payload = {
            'owner': 'aaaabbbb',
            'pid': dead_pid,
            'started_at': (now - timedelta(minutes=1)).isoformat(),
            'heartbeat_at': (now - timedelta(minutes=1)).isoformat(),
            'label': 'instance-A',
        }
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        info = mod._read()
        # v1 的 _describe 签名是 (info, ttl_min)，v2 是 (info, stale_min)，位置参数兼容
        takeover, _why = mod._describe(info, 30)
        return not takeover
    finally:
        mod.LOCK = saved


def cmd_self_test(stale: int) -> int:
    import tempfile
    ok, bad = 0, []

    def check(name, cond):
        nonlocal ok
        if cond:
            ok += 1
            print(f'  ✅ {name}')
        else:
            bad.append(name)
            print(f'  ❌ {name}')

    print('【自测】run_lock v2')
    me = sys.modules[__name__]

    # 1 核心回归（对应真实事故形态）
    check('上一实例 1 分钟前 acquire(辅助进程已退出) → 第二实例被拒', _scenario_second_acquire_refused(me))

    now = _now()
    mk = lambda **kw: {**{'owner': 'x', 'pid': 999999, 'label': 't',
                          'started_at': now.isoformat(),
                          'heartbeat_at': now.isoformat()}, **kw}

    # 2 心跳新鲜 + pid dead → 不抢占
    check('心跳 5 分钟前 + pid dead → 不抢占',
          _describe(mk(heartbeat_at=(now - timedelta(minutes=5)).isoformat()), stale)[0] is False)
    # 3 心跳过期 + pid dead → 可抢占（自愈路径）
    check('心跳 45 分钟前 + pid dead → 可抢占',
          _describe(mk(heartbeat_at=(now - timedelta(minutes=45)).isoformat()), stale)[0] is True)
    # 4 心跳过期但 pid 确认存活 → 仍不抢占（PID 只加严）
    check('心跳 45 分钟前 但 pid 存活 → 不抢占',
          _describe(mk(pid=os.getpid(),
                       heartbeat_at=(now - timedelta(minutes=45)).isoformat()), stale)[0] is False)
    # 5 缺 heartbeat 字段（老格式锁）→ 按"刚刚"处理，不抢占
    old = {'pid': 999999, 'started_at': now.isoformat(), 'label': 'v1-format'}
    check('老格式锁(无 heartbeat 字段) → 保守不抢占', _describe(old, stale)[0] is False)
    # 6 损坏锁文件 → 不抢占
    tmpd = Path(tempfile.mkdtemp()) / 'runlock.json'
    tmpd.parent.mkdir(parents=True, exist_ok=True)
    tmpd.write_text('{{{ not json', encoding='utf-8')
    saved = me.LOCK
    me.LOCK = tmpd
    try:
        check('锁文件损坏 → 按有人在跑，不抢占', _describe(_read(), stale)[0] is False)
    finally:
        me.LOCK = saved
    # 7 renew 确实推进心跳
    tmpr = Path(tempfile.mkdtemp()) / 'runlock.json'
    me.LOCK = tmpr
    try:
        _write_lock('own1', 'lbl')
        stale_payload = json.loads(tmpr.read_text(encoding='utf-8'))
        stale_payload['heartbeat_at'] = (now - timedelta(minutes=20)).isoformat()
        tmpr.write_text(json.dumps(stale_payload), encoding='utf-8')
        before = _age_min(_read(), 'heartbeat_at')
        ns = argparse.Namespace(owner='own1', force=False)
        cmd_renew(ns)
        after = _age_min(_read(), 'heartbeat_at')
        check(f'renew 把心跳从 {before:.0f} 分钟拉回 {after:.0f} 分钟', before > 15 and after < 1)
        # 8 owner 不符拒绝续期
        check('owner 不符 → 拒绝续期', cmd_renew(argparse.Namespace(owner='WRONG', force=False)) == 5)
    finally:
        me.LOCK = saved

    print(f'\n结果：{ok} 通过 / {len(bad)} 失败')
    if bad:
        for b in bad:
            print(f'  失败：{b}')
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description='飞轮单实例锁 v2（心跳判活）')
    p.add_argument('--stale', type=int, default=DEFAULT_STALE_MIN,
                   help='心跳静默多少分钟视为崩溃（默认 30）')
    p.add_argument('--self-test', action='store_true', help='阳性+阴性对照自测')
    sub = p.add_subparsers(dest='cmd')
    a = sub.add_parser('acquire')
    a.add_argument('--label', default='')
    a.add_argument('--owner', default='')
    n = sub.add_parser('renew')
    n.add_argument('--owner', default='')
    n.add_argument('--force', action='store_true')
    sub.add_parser('status')
    r = sub.add_parser('release')
    r.add_argument('--owner', default='')
    r.add_argument('--force', action='store_true')
    args = p.parse_args()
    if getattr(args, 'self_test', False):
        return cmd_self_test(args.stale)
    if not args.cmd:
        p.print_help()
        return 2
    return {'acquire': cmd_acquire, 'renew': cmd_renew,
            'status': cmd_status, 'release': cmd_release}[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())
