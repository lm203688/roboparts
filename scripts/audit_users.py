#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""真实转化基线审计 —— 把"有没有真实用户"变成一个可以被回答的问题。

背景（20260805-20）
-------------------
飞轮连续 6 轮报告"真实转化 0"，但这个结论此前**无法被验证**：
USER_CREDITS 命名空间里有 46 个 gtk_ 键，全部由历史健康检查、部署校验、
支付测试产生（healthcheck@test.com / deploy-verify-* / paytest@example.com
/ *.invalid），与潜在真实用户共用同一前缀、同一结构、同一计数器。

也就是说，即使明天来了第一个真实用户，我们也说不清 47 个键里哪个是他。
这与 18:00「没有流量埋点」、19:00「读不存在的字段做判断」同型：
**指标存在、口径不成立，于是数字再准也没有意义。**

本脚本按可枚举的特征规则把用户键分为三类，输出可信的真实转化基线：
  real     — 不匹配任何测试特征，视为真实用户
  selftest — 飞轮自检（selftest_ 前缀或 selftest:true 字段，20:00 起自动隔离）
  legacy   — 20:00 隔离机制上线前的历史测试残留（按邮箱特征识别）

用法
----
  python scripts/audit_users.py            # 只审计，不改动（默认安全）
  python scripts/audit_users.py --purge    # 删除 legacy/selftest 键并校正计数器

设计原则：默认只读。任何删除都必须显式加 --purge，且只删被规则明确判定为
非真实用户的键——真实用户键永不参与删除候选。
"""
import json
import re
import subprocess
import sys

NS = 'f01526d743c24e1a91b2586a865f4864'  # USER_CREDITS

# 测试账号特征。新增自动化测试时若用了新邮箱模式，必须同步加进来，
# 否则该批测试会被误判为真实用户，把转化基线重新污染。
TEST_PATTERNS = [
    r'@test\.com$', r'@example\.com$', r'\.invalid$', r'@test\.',
    r'healthcheck', r'deploy-verify', r'daily-health', r'paytest',
    r'flywheel', r'e2e', r'selftest', r'probe', r'smoke',
]
_TEST_RE = re.compile('|'.join(TEST_PATTERNS), re.I)


def kv(*args, timeout=180):
    """调用 wrangler kv，返回 stdout 文本（失败返回空串）。"""
    cmd = ['npx', 'wrangler', 'kv', *args,
           f'--namespace-id={NS}', '--remote']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, shell=(sys.platform == 'win32'))
        return r.stdout or ''
    except Exception as e:
        print(f'  [warn] wrangler 调用失败: {e}')
        return ''


def _test_email_hashes():
    """生成已知自动化测试邮箱的 SHA-256 反查表。

    register.js 早期存 email 明文、后期改为只存 email_hash。若仅凭"有没有
    明文邮箱"分类，所有 hash-only 记录都会被算成真实用户 —— 首次运行本脚本
    正是这样报出了"23 个真实用户"，而真相是它们绝大多数仍是健康检查产生的。
    **把测试当成真人，比承认 0 更危险**：它会让后续所有增长决策建立在
    不存在的用户之上。因此用确定性哈希反查代替特征猜测。
    """
    cands = {'healthcheck@test.com', 'paytest@example.com', 'test@test.com',
             'health@roboparts.cc', 'healthcheck@roboparts.cc',
             'admin@roboparts.cc', 'flywheel-e2e-20260805@roboparts.cc'}
    prefixes = ('healthcheck', 'daily-health', 'deploy-verify', 'deploy-verify-v2',
                'verify', 'smoke', 'probe', 'flywheel-e2e')
    for mm, dmax in (('07', 32), ('08', 32)):
        for dd in range(1, dmax):
            for pre in prefixes:
                stamp = f'2026{mm}{dd:02d}'
                cands.add(f'{pre}-{stamp}@example.com')
                cands.add(f'{pre}+{stamp}@roboparts.cc')
                cands.add(f'{pre}-{stamp}@test.com')
                cands.add(f'{pre}-{stamp}@roboparts.cc')
    import hashlib
    return {hashlib.sha256(e.lower().strip().encode()).hexdigest(): e for e in cands}


_HASH2EMAIL = _test_email_hashes()


def classify(key, raw):
    """归类为 real / selftest / legacy / unverified。

    判据优先级：显式隔离标记 > 前缀 > 邮箱明文特征 > 邮箱哈希反查 > 存疑。

    关键设计：无法证实的记录归为 **unverified 而非 real**。
    "无法证明是测试" ≠ "是真实用户"。把存疑项计入真实转化，等于用一个
    好看的数字掩盖测量能力的不足 —— 与 KD-01 自曝缺陷同一条原则：
    宁可承认基线为 0，也不虚报。unverified 永不参与删除。
    """
    if key.startswith('selftest_'):
        return 'selftest', 'key 前缀隔离'
    try:
        d = json.loads(raw)
    except Exception:
        return 'unverified', '记录无法解析'
    if d.get('selftest') is True:
        return 'selftest', 'selftest 字段'
    email = str(d.get('email') or '')
    if email and _TEST_RE.search(email):
        return 'legacy', f'测试邮箱明文 {email[:40]}'
    eh = d.get('email_hash')
    if eh and eh in _HASH2EMAIL:
        return 'legacy', f'哈希反查命中 {_HASH2EMAIL[eh][:40]}'
    # 20:00 后注册的真实用户会带 source 字段，可确证
    if d.get('source'):
        return 'real', f'来源 {d.get("source")}/{d.get("source_detail", "")}'
    return 'unverified', f'无来源标记、哈希未命中（创建于 {d.get("created", "?")[:10]}）'


def main():
    purge = '--purge' in sys.argv
    print('=' * 56)
    print('RoboParts 真实转化基线审计' + ('（PURGE 模式）' if purge else '（只读）'))
    print('=' * 56)

    out = kv('key', 'list')
    try:
        keys = [k['name'] for k in json.loads(out)]
    except Exception:
        print('❌ 无法读取 KV 键列表（wrangler 未登录或网络异常）')
        return 1

    users = [k for k in keys if k.startswith('gtk_') or k.startswith('selftest_')]
    print(f'\n用户键总数: {len(users)}（gtk_ {sum(1 for k in users if k.startswith("gtk_"))}'
          f' / selftest_ {sum(1 for k in users if k.startswith("selftest_"))}）')

    buckets = {'real': [], 'selftest': [], 'legacy': [], 'unverified': []}
    for k in users:
        cat, why = classify(k, kv('key', 'get', k))
        buckets[cat].append((k, why))

    for cat, label in (('real', '已确证真实用户'), ('unverified', '存疑·不计入转化'),
                       ('selftest', '飞轮自检'), ('legacy', '历史测试残留')):
        items = buckets[cat]
        print(f'\n[{label}] {len(items)} 个')
        for k, why in items[:6]:
            print(f'    {k[:20]}… — {why}')
        if len(items) > 6:
            print(f'    …等 {len(items)} 个')

    # ---- 来源归因分布（20:00 起写入，回答"第一个用户从哪来"）----
    print('\n[来源归因] 真实注册按渠道分布')
    found = False
    for src in ('agent', 'channel', 'referral', 'web', 'unknown'):
        v = kv('key', 'get', f'stat:src:{src}').strip()
        if v and v.isdigit() and int(v) > 0:
            print(f'    {src}: {v}')
            found = True
    if not found:
        print('    尚无真实注册（AI 通道刚于 20:00 开放，等待首个信号）')
    first = kv('key', 'get', 'stat:first_signup').strip()
    if first and first.startswith('{'):
        print(f'    首个真实注册现场: {first[:200]}')

    n_real = len(buckets['real'])
    print('\n' + '=' * 56)
    n_unv = len(buckets['unverified'])
    print(f'✅ 可信真实转化基线：已确证真实用户 {n_real} 人')
    print(f'   （剔除 {len(buckets["legacy"])} 历史测试 + {len(buckets["selftest"])} 自检；'
          f'另有 {n_unv} 个存疑键未计入——无法证明是测试不等于是真人）')
    print('=' * 56)

    if not purge:
        n_del = len(buckets['legacy']) + len(buckets['selftest'])
        if n_del:
            print(f'\n提示：加 --purge 可清理 {n_del} 个非真实用户键并校正计数器。')
        return 0

    # ---- PURGE：只删被明确判定为非真实的键 ----
    doomed = [k for k, _ in buckets['legacy']] + [k for k, _ in buckets['selftest']]
    print(f'\n开始清理 {len(doomed)} 个非真实用户键…')
    for i, k in enumerate(doomed, 1):
        kv('key', 'delete', k)
        if i % 10 == 0 or i == len(doomed):
            print(f'    {i}/{len(doomed)}')
    # 计数器校正为真实值，让 stat:users:total 从此可信
    subprocess.run(['npx', 'wrangler', 'kv', 'key', 'put', 'stat:users:total',
                    str(n_real), f'--namespace-id={NS}', '--remote'],
                   capture_output=True, text=True, shell=(sys.platform == 'win32'))
    print(f'✅ 清理完成，stat:users:total 校正为 {n_real}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
