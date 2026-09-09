#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""渠道漏斗报表 · RoboParts 外溢流量度量。

为什么需要它
------------
站上早就有两套归因，但都读不出「某个渠道到底带来了多少人」：

* `functions/api/register.js` 算出 source/detail 后，只写进**单条用户记录**，
  未按渠道聚合 ⇒ 「古月居来了几个人」要遍历全部用户键才答得出（事实上答不出）；
* `functions/_middleware.js` 只记 `ref:<host>`（浏览器 referer），而渠道标记
  原先只认 HTTP 头 `x-roboparts-via` —— 浏览器点链接不会带自定义头，
  于是**社区发帖 → 点击 → 注册**这条外溢流量主路径整条不可见。

20260909-25 补上两侧后，本脚本把「点击」与「注册」配成漏斗：
只有注册数，无法区分「没人来」和「来了留不住」。

两侧数据都在同一个 namespace（USER_CREDITS）：
  * 点击：`metrics:<day>:s<shard>`（JSON 对象）里的 `via:<channel>` 键
  * 注册：`stat:via:<source>:<detail>` 单键（永久，无 TTL）

用法
----
    python scripts/channel_report.py              # 近 7 天渠道漏斗
    python scripts/channel_report.py --days 30
    python scripts/channel_report.py --link guyuehome   # 生成带标记的投放链接
    python scripts/channel_report.py --selftest   # 纯函数阴阳对照（不触网）
"""
import json
import subprocess
import sys
from collections import defaultdict
from datetime import date, timedelta

NS = 'f01526d743c24e1a91b2586a865f4864'  # USER_CREDITS
SITE = 'https://roboparts.cc'


# ---------------------------------------------------------------- KV 访问

def kv_list(prefix):
    """列出指定前缀的键名；失败返回 []。"""
    try:
        r = subprocess.run(
            ['npx', 'wrangler', 'kv', 'key', 'list',
             f'--prefix={prefix}', f'--namespace-id={NS}', '--remote'],
            capture_output=True, text=True, timeout=120, shell=True,
        )
        if r.returncode != 0:
            return []
        data = json.loads(r.stdout.strip() or '[]')
        return [d.get('name', '') for d in data if d.get('name')]
    except Exception:
        return []


def kv_get_raw(key):
    try:
        r = subprocess.run(
            ['npx', 'wrangler', 'kv', 'key', 'get', key,
             f'--namespace-id={NS}', '--remote'],
            capture_output=True, text=True, timeout=90, shell=True,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return r.stdout.strip()
    except Exception:
        return None


# ---------------------------------------------------------------- 纯函数

def merge_clicks(daily_blobs):
    """[{day: blob dict}] → {渠道: 点击数}。blob 里只挑 via: 前缀。"""
    out = defaultdict(int)
    for blob in daily_blobs:
        if not isinstance(blob, dict):
            continue
        for k, v in blob.items():
            if k.startswith('via:') and isinstance(v, (int, float)):
                out[k[len('via:'):]] += int(v)
    return dict(out)


def merge_signups(stat_keys):
    """{'stat:via:<src>:<detail>': n} → {渠道: 注册数}（只取 channel 来源）。

    referral/agent/web 不是「投放渠道」，不参与渠道漏斗，
    但会单独列出，避免把自然流量误算成渠道成果。
    """
    channel, other = defaultdict(int), defaultdict(int)
    for k, v in stat_keys.items():
        if not k.startswith('stat:via:'):
            continue
        rest = k[len('stat:via:'):]
        src, _, detail = rest.partition(':')
        if src == 'channel' and detail:
            channel[detail] += int(v)
        else:
            other[f'{src}:{detail}'] += int(v)
    return dict(channel), dict(other)


def funnel(clicks, signups):
    """(点击, 注册) → 排序后的渠道行列表。含只点不注册 / 只注册不点两类异常。"""
    rows = []
    for ch in set(clicks) | set(signups):
        c, s = clicks.get(ch, 0), signups.get(ch, 0)
        rate = (s / c * 100) if c else None
        rows.append({'channel': ch, 'clicks': c, 'signups': s, 'rate': rate})
    rows.sort(key=lambda r: (-r['signups'], -r['clicks'], r['channel']))
    return rows


def safe_channel(name):
    """渠道名白名单清洗，与 worker 侧规则一致（进 KV 键，必须可控）。"""
    keep = [c for c in (name or '').lower() if c.isalnum() or c in '._-']
    return ''.join(keep)[:40]


def build_links(channel):
    """生成带 ?via= 的投放链接。落地页选问得多、能立刻动手的那几个。"""
    ch = safe_channel(channel)
    if not ch:
        return []
    targets = [
        ('', '首页（通用投放）'),
        ('/llms.txt', 'Agent/开发者接入说明'),
        ('/bom-checker.html', 'BOM 兼容检查（最能体现价值）'),
        ('/adapter-generator.html', '转接盘生成器'),
    ]
    return [(f'{SITE}/{p.lstrip("/")}?via={ch}' if p else f'{SITE}/?via={ch}', d)
            for p, d in targets]


# ---------------------------------------------------------------- 报表

def report(days=7):
    today = date.today()
    blobs = []
    for i in range(days):
        day = (today - timedelta(days=i)).isoformat()
        for key in kv_list(f'metrics:{day}:'):
            raw = kv_get_raw(key)
            if not raw:
                continue
            try:
                blobs.append(json.loads(raw))
            except Exception:
                continue

    clicks = merge_clicks(blobs)

    stat_keys = {}
    for key in kv_list('stat:via:'):
        raw = kv_get_raw(key)
        if raw and raw.strip().isdigit():
            stat_keys[key] = int(raw.strip())
    signups, other_src = merge_signups(stat_keys)

    print(f'=== RoboParts 渠道漏斗 · 近 {days} 天（{today.isoformat()}）===')
    print('※ 点击与注册均为**下界**：遥测读数是分片读-改-写，两个 isolate '
          '同时写同分片会互相覆盖（见 read_metrics.py 头部说明）。')
    print('※ 只能用来证明「至少有多少」，不能用来证明「只有这么多」。\n')

    rows = funnel(clicks, signups)
    if not rows:
        print('（无渠道数据：尚无带 ?via= 的点击，也无线索级注册）')
        print('  下一步：用 --link <渠道名> 生成投放链接，发出去后本表才有数。')
    else:
        print(f"{'渠道':<24}{'点击':>8}{'注册':>8}{'转化':>10}")
        print('-' * 52)
        for r in rows:
            rate = '—' if r['rate'] is None else f"{r['rate']:.1f}%"
            flag = ''
            if r['clicks'] and not r['signups']:
                flag = '  ← 有点击零注册：落地页或钩子问题'
            elif r['signups'] and not r['clicks']:
                flag = '  ← 有注册零点击：标记未落到点击侧'
            print(f"{r['channel']:<24}{r['clicks']:>8}{r['signups']:>8}{rate:>10}{flag}")
        print()

    if other_src:
        print('[非渠道注册] 自然流量/直接访问，不计入渠道 ROI：')
        for k, v in sorted(other_src.items(), key=lambda x: -x[1]):
            print(f'  {k:<40}{v:>6}')
        print()

    total_c = sum(clicks.values())
    total_s = sum(signups.values())
    print(f'合计：渠道点击 {total_c} · 渠道注册 {total_s}'
          + (f' · 整体转化 {total_s / total_c * 100:.1f}%' if total_c else ''))
    return 0


def selftest():
    bad = 0

    def check(cond, name):
        nonlocal bad
        print(('  ✅ ' if cond else '  ❌ ') + name)
        if not cond:
            bad += 1

    # 阳：正常漏斗
    c = merge_clicks([{'via:guyuehome': 10, 'ref:x.com': 5, 'path:index': 3}])
    check(c == {'guyuehome': 10}, '点击合并只取 via: 前缀（ref:/path: 不混入）')
    check(merge_clicks([{'via:a': 2}, {'via:a': 3, 'via:b': 1}]) == {'a': 5, 'b': 1},
          '跨分片/跨天累加')
    s, o = merge_signups({'stat:via:channel:guyuehome': 2,
                          'stat:via:referral:github.com': 4,
                          'stat:via:agent:curl': 1})
    check(s == {'guyuehome': 2}, '注册只把 channel 来源算作渠道')
    check(o == {'referral:github.com': 4, 'agent:curl': 1},
          'referral/agent 归入非渠道，避免把自然流量算成投放成果')

    f = funnel({'a': 10, 'b': 0}, {'a': 1})
    check(f[0]['channel'] == 'a' and f[0]['rate'] == 10.0, '转化率按点击数计算')
    check(any(r['channel'] == 'b' for r in f), '零点击零注册的渠道也出现在表里')

    # 阴：空输入 / 脏输入
    check(merge_clicks([]) == {}, '空输入不报错')
    check(merge_clicks([None, 'x', 42]) == {}, '脏 blob 被跳过')
    check(merge_signups({}) == ({}, {}), '无 stat 键时两个字典都为空')
    check(funnel({}, {}) == [], '空漏斗返回空列表')

    # 渠道名清洗（防键空间污染，必须与 worker 侧同规则）
    check(safe_channel('Guyue Home!!') == 'guyuehome', '清洗去除非法字符并转小写')
    check('/' not in safe_channel('../../etc') and '\\' not in safe_channel('..\\..\\etc'),
          '路径分隔符被剔除（渠道名进 KV 键，不得含分隔符）')
    check(safe_channel('') == '', '空渠道名返回空（调用方据此拒绝生成链接）')
    check(len(safe_channel('x' * 100)) == 40, '长度截断到 40')

    links = build_links('guyuehome')
    check(len(links) == 4 and all('?via=guyuehome' in u for u, _ in links),
          '生成 4 条带标记的落地页链接')
    check(build_links('!!') == [], '非法渠道名不生成链接')

    # 鉴别力：两个渠道顺序不同，排序结果必须不同（否则报表无鉴别力）
    a = funnel({'a': 1}, {'a': 5})
    b = funnel({'a': 1}, {'a': 0})
    check(a[0]['signups'] != b[0]['signups'], '注册数差异能体现在报表上')

    print('  ✅ 阴阳对照通过' if bad == 0 else f'  ❌ 阴阳对照失败 {bad} 项')
    return bad == 0


def main():
    if '--selftest' in sys.argv:
        return 0 if selftest() else 1
    if '--link' in sys.argv:
        i = sys.argv.index('--link')
        ch = sys.argv[i + 1] if len(sys.argv) > i + 1 else ''
        links = build_links(ch)
        if not links:
            print(f'渠道名非法或为空：{ch!r}（只允许字母数字 . _ -，最长 40）')
            return 1
        print(f'=== 投放链接 · 渠道 {safe_channel(ch)} ===')
        for u, d in links:
            print(f'  {d}\n    {u}')
        print('\n※ 页面已带 canonical，?via= 不会产生重复内容 SEO 风险。')
        print('※ 发出后用 python scripts/channel_report.py 看该渠道的点击与注册。')
        return 0
    days = 7
    if '--days' in sys.argv:
        try:
            days = int(sys.argv[sys.argv.index('--days') + 1])
        except (ValueError, IndexError):
            pass
    return report(days)


if __name__ == '__main__':
    sys.exit(main())
