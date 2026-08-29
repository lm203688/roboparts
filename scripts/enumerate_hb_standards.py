#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行业标准（行标）枚举器 —— 全国标准信息公共服务平台 · 行标备案库
================================================================

**为什么需要这一份（与 enumerate_standards.py 的分工）**

`enumerate_standards.py` 覆盖两个维度：
  - 国标 GB/GB-T  →  std.samr.gov.cn
  - 团标 T/xxx    →  ttbz（已被 robots 禁）/ ndls（已被 WAF 挑战）

**行业标准（JB/T 机械、SJ/T 电子、YD/T 通信 …）此前是一整个未覆盖维度** ——
截至本文件建立时，标准登记表 `seen` 里 26 条全部是 `GB/T ` 或 `T/` 前缀，
行标条目数为 0。不是"扫过没有"，是**根本没有扫过**。

**通道可用性实测（20260811-12）**
  - `https://hbba.sacinfo.org.cn/robots.txt` → 302 到 SSO 登录页；
    但那是因为该路径不存在、未知路径统一跳登录，**不构成 robots 禁止**
    （站点没有 robots.txt = 没有声明限制）。
  - `GET /stdList` → 200，无需登录。
  - `POST /stdQueryList`（form-urlencoded）→ 200 JSON，无需登录。
    参数取自该页自身的 `queryParams()`：
      current / size / key / ministry / industry / pubdate / date / status
  - `GET /stdDetail/<pk>` → 200，可作逐条取证 URL。

**翻页参数的坑（与 GB 枚举器相反，务必看清）**
  GB 那边（std.samr）认 `pageNo`，传 `current` 会被忽略并反复返回第一页
  —— 那次静默失效让扫描面被读成"拉满了"。
  **本平台恰恰相反：它认 `current`**（其前端 `queryParams()` 就是这么发的）。
  两个平台参数名相反，所以本文件**不复用** GB 那套翻页代码，
  并在每次翻页时做首条重复自证（见 `_assert_page_advanced`）。

**空输入不得平凡成立（L1.88）**
  上一次事故：ndls 返回 WAF 挑战页 → 解析出 0 条 → `0 == 0` → 判 complete=True，
  对 436 条宣称"整表过了一遍"。本文件的硬规矩：
    - 非 200 / 非 JSON / records 为空但 total>0  → 一律 RED，exit 2
    - 收齐条数 < total                            → RED，不得写台账
    - 相对**历史最大值**缩水 >10%                  → RED，拒绝写台账
  即"拿不到"与"确实没有"必须是两种结论，绝不合并成 HOLD/complete。

用法
----
  python scripts/enumerate_hb_standards.py --industry 机械 --full
  python scripts/enumerate_hb_standards.py --keywords 机器人,机械臂
  python scripts/enumerate_hb_standards.py --self-test      # 阴阳对照

退出码：0 正常 / 2 通道异常（RED，调用方不得据此更新台账）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = 'https://hbba.sacinfo.org.cn'
QUERY_API = BASE + '/stdQueryList'
DETAIL_URL = BASE + '/stdDetail/'
LIST_PAGE = BASE + '/stdList'

LEDGER = os.path.join(os.path.dirname(__file__), '..', 'ops', 'intel',
                      'hb-standards-ledger.json')

# 作用域判据：**必须同时**命中「机器人域」与「零部件/接口域」。
# 只要一边就收 → 会把 272 条船用/管道法兰标准全拖进来（实测）。
# 这不是保守，是作用域定义：本站判据是"零部件接口能不能对上"，
# 不是"标题里出现过法兰两个字"。
ROBOT_RE = re.compile(r'(机器人|机械臂|机器手|具身|人形|末端执行器|夹持器|AGV)')
IFACE_RE = re.compile(
    r'(机械接口|接口|法兰|连接器|安装尺寸|互换|坐标系|关节|减速器|伺服|'
    r'编码器|总线|通信协议|模组|电连接器|插头|插座)')

_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')


class ChannelError(RuntimeError):
    """通道层异常 —— 与「确实没有数据」严格区分，调用方必须判红。"""


def _post(params: dict, timeout: int = 30, retries: int = 3) -> dict:
    """带退避重试。

    ⚠️ 重试**只针对传输层抖动**（超时/连接重置）。协议层异常（非 JSON =
    挑战页、HTTP 非 200）一律立刻抛出不重试 —— 对着挑战页重试三次只会
    把"被挡在门外"熬成"看起来偶发"，正是 L1.88 要防的那种自我安慰。
    """
    last = None
    for attempt in range(1, retries + 1):
        try:
            return _post_once(params, timeout)
        except ChannelError as exc:
            msg = str(exc)
            if not msg.startswith('请求失败'):
                raise                      # 协议层异常：不重试
            last = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise ChannelError(f'{last}（已重试 {retries} 次）')


def _post_once(params: dict, timeout: int = 30) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(QUERY_API, data=data, headers={
        'User-Agent': _UA,
        'Referer': LIST_PAGE,
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                raise ChannelError(f'HTTP {r.status}')
            raw = r.read().decode('utf-8', 'ignore')
    except ChannelError:
        raise
    except Exception as exc:                      # noqa: BLE001
        raise ChannelError(f'请求失败: {exc}') from exc

    stripped = raw.lstrip()
    if not stripped.startswith('{'):
        # 典型症状：被挑战页/登录页顶替。绝不能当成"查无此标"。
        raise ChannelError('响应非 JSON（疑似登录页/挑战页），前 80 字: '
                           + stripped[:80].replace('\n', ' '))
    try:
        return json.loads(raw)
    except Exception as exc:                      # noqa: BLE001
        raise ChannelError(f'JSON 解析失败: {exc}') from exc


def _assert_page_advanced(prev_codes, cur_codes, page: int) -> None:
    """翻页真实推进自证。

    平台忽略翻页参数时的表现是"每页都返回同一批" —— 这在计数上完全自洽
    （每页都满、页数也对），只有比对内容才看得出来。GB 枚举器就是栽在这里。
    """
    if not prev_codes or not cur_codes:
        return
    if cur_codes[0] == prev_codes[0]:
        raise ChannelError(
            f'第 {page} 页首条与上一页相同（{cur_codes[0]}）——'
            '翻页参数疑似被忽略，拒绝把重复页当成扫描面')
    if not set(cur_codes) - set(prev_codes):
        raise ChannelError(f'第 {page} 页与上一页完全重叠，翻页无效')


MIN_COVERAGE = 0.99   # 低于此覆盖率＝通道结构性坏了，数据不可用
_CANARY_CACHE: dict = {}


def channel_alive() -> bool:
    """探针：查一个**已知必然非空**的面，证明通道此刻是通的。

    为什么需要它：`total==0` 有两种截然不同的成因 ——「关键词确实没命中」
    与「WAF 挑战页/协议变更导致解析出 0」。v1 因为分不清，一律判红，
    结果是**永远无法证明"确实没有"**，枚举器对空结果毫无判定力。
    有了探针就能分开：探针通 + 本查询 0 条 ⇒ 确实没有（可判 complete）；
    探针不通 ⇒ 拿不到，判红。
    """
    if 'ok' in _CANARY_CACHE:
        return _CANARY_CACHE['ok']
    try:
        d = _post({'current': 1, 'size': 1, 'key': '', 'industry': '机械'})
        ok = isinstance(d.get('records'), list) and int(d.get('total') or 0) > 1000
    except Exception:
        ok = False
    _CANARY_CACHE['ok'] = ok
    return ok


def enumerate_query(key: str = '', industry: str = '', size: int = 100,
                    max_pages: int = 400, sleep: float = 0.25,
                    verbose: bool = True) -> dict:
    """枚举一个检索面，返回 {records,total,collected,complete,coverage,missing}。

    ## v2 修正：把「能不能用这批数据」和「能不能宣称穷举」拆成两件事

    v1 把两者绑死：`collected < total` 直接抛 ChannelError。实测 21023/21025
    （覆盖率 99.99%，平台 total 自身含 2 条重复/下架的口径误差）被整批丢弃 ——
    防假绿防到了「通道永远不可用」，等于把这条维度关掉了。

    v2 判据：
    - `total==0` 且探针通 → 确实没有，complete=True（count 0 亦为结论）
    - `total==0` 且探针不通 → RED（拿不到，L1.88 那次假绿的原形）
    - 覆盖率 < MIN_COVERAGE → RED，结构性坏，数据不可用
    - 覆盖率 ≥ MIN_COVERAGE 但未拉满 → **写数据，但 complete=False**
      调用方凡要宣称「整表穷举」必须自行断言 complete，否则只能说「已覆盖 N/M」
    """
    out: dict = {}
    total = None
    prev_codes: list = []
    page = 1
    stopped_early = ''
    while page <= max_pages:
        params = {'current': page, 'size': size, 'key': key}
        if industry:
            params['industry'] = industry
        d = _post(params)
        if total is None:
            total = int(d.get('total') or 0)
        recs = d.get('records')
        if not isinstance(recs, list):
            raise ChannelError('records 非列表，协议疑似变更')
        if not recs:
            if total and len(out) < total:
                stopped_early = f'第 {page} 页空但 total={total}（已收 {len(out)}）'
            break
        codes = [str(r.get('code') or '') for r in recs]
        _assert_page_advanced(prev_codes, codes, page)
        prev_codes = codes
        for r in recs:
            out[str(r.get('code') or r.get('pk'))] = r
        if verbose and page % 20 == 0:
            print(f'    …第 {page} 页，已收 {len(out)}/{total}', flush=True)
        if len(out) >= (total or 0):
            break
        page += 1
        time.sleep(sleep)

    return finalize(total or 0, out, channel_alive, stopped_early)


def finalize(total: int, out: dict, canary, stopped_early: str = '') -> dict:
    """把最终判据抽成纯函数 —— 否则这段最容易出假绿的逻辑只能靠真发网络请求才测得到，
    等于测不到。`canary` 传可调用对象，自测时注入桩。"""
    collected = len(out)
    if total == 0:
        if not canary():
            raise ChannelError('total=0 且通道探针不通 —— 是"拿不到"，不是"没有"')
        return {'records': {}, 'total': 0, 'collected': 0, 'complete': True,
                'coverage': 1.0, 'missing': 0, 'note': '探针通过，确实无命中'}
    coverage = collected / total
    if coverage < MIN_COVERAGE:
        raise ChannelError(
            f'覆盖率 {coverage:.2%} < {MIN_COVERAGE:.0%}：收 {collected}/{total}'
            + (f'；{stopped_early}' if stopped_early else ''))
    return {'records': out, 'total': total, 'collected': collected,
            'complete': collected == total, 'coverage': coverage,
            'missing': total - collected,
            'note': stopped_early or ''}


def in_scope(name: str) -> bool:
    return bool(ROBOT_RE.search(name) and IFACE_RE.search(name))


def load_ledger() -> dict:
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding='utf-8') as f:
            return json.load(f)
    return {'version': 1, 'scan_index': {}, 'baseline_max': {}, 'runs': []}


def save_ledger(led: dict) -> None:
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, 'w', encoding='utf-8') as f:
        json.dump(led, f, ensure_ascii=False, indent=2, sort_keys=True)


def guard_shrink(led: dict, face: str, count: int) -> None:
    """相对历史**最大值**（不是最近值）缩水 >10% 判红。

    取最大值而非最近值：若某轮通道半坏收了一半并被写进台账，
    用"最近值"当基线会让下一轮把腰斩当成新常态，缺陷就此固化。
    """
    base = int((led.get('baseline_max') or {}).get(face) or 0)
    if base and count < base * 0.9:
        raise ChannelError(
            f'{face}: 本次 {count} 较历史最大 {base} 缩水 '
            f'{(1 - count / base) * 100:.0f}% > 10%，疑似召回退化，拒绝写台账')


def self_test() -> int:
    """阴阳对照 —— 每条断言都必须能被反向证伪，否则等于没测。"""
    ok = True

    def yes(cond, msg):
        nonlocal ok
        print(('  ✅ ' if cond else '  ❌ ') + msg)
        ok = ok and bool(cond)

    print('[HB 枚举器自测]')

    # 阳性：作用域判据认得真样本
    yes(in_scope('包装用机器人与视觉系统TCP通信接口协议'), '阳性: 机器人∩接口 被收')
    yes(in_scope('多关节机器人用伺服电动机技术规范'), '阳性: 机器人∩伺服 被收')
    # 阴性：单边命中一律不收（这是 272 条船用法兰的防线）
    yes(not in_scope('船用法兰吸入止回阀'), '阴性: 只有接口词（船用法兰）不收')
    yes(not in_scope('工业机器人安全实施规范'), '阴性: 只有机器人词（安全规范）不收')
    yes(not in_scope('法兰铸铁直角安全阀'), '阴性: 管路法兰不收')

    # 阴性：翻页未推进必须判红（GB 那次静默失效的防线）
    try:
        _assert_page_advanced(['A-1', 'B-2'], ['A-1', 'B-2'], 2)
        yes(False, '阴性: 重复页应判红')
    except ChannelError as e:
        yes('翻页参数疑似被忽略' in str(e), f'阴性: 重复页被判红（{str(e)[:34]}…）')

    # 阴性：部分重叠但首条不同 —— 应放行（避免假红）
    try:
        _assert_page_advanced(['A-1', 'B-2'], ['B-2', 'C-3'], 2)
        yes(True, '阴性(不该红): 首条已推进则放行，不误判')
    except ChannelError:
        yes(False, '阴性(不该红): 误判了正常翻页')

    # 阴性：空表不得 complete
    led = {'baseline_max': {'机械': 21025}}
    try:
        guard_shrink(led, '机械', 100)
        yes(False, '阴性: 腰斩应判红')
    except ChannelError as e:
        yes('缩水' in str(e), f'阴性: 缩水被判红（{str(e)[:30]}…）')
    try:
        guard_shrink(led, '机械', 20000)
        yes(True, '阴性(不该红): 轻微波动放行')
    except ChannelError:
        yes(False, '阴性(不该红): 正常波动被误判')

    # --- 覆盖率判据（v2 新增）：探针桩注入，不发网络 ---
    live, dead = (lambda: True), (lambda: False)
    fake = lambda n: {str(i): {} for i in range(n)}

    # 阴性：探针不通 + 空表 → 必须红（L1.88 假绿原形）
    try:
        finalize(0, {}, dead)
        yes(False, '阴性: 探针不通的空表应判红')
    except ChannelError as e:
        yes('拿不到' in str(e), f'阴性: 空表+探针不通判红（{str(e)[:26]}…）')
    # 阳性：探针通 + 空表 → 判"确实没有"（v1 在此永远判红，等于无判定力）
    r0 = finalize(0, {}, live)
    yes(r0['complete'] is True and r0['collected'] == 0, '阳性: 探针通的空表＝确实没有')
    # 阴性：覆盖率腰斩 → 红
    try:
        finalize(21025, fake(10000), live)
        yes(False, '阴性: 覆盖率 48% 应判红')
    except ChannelError as e:
        yes('覆盖率' in str(e), f'阴性: 覆盖率不足判红（{str(e)[:26]}…）')
    # 阳性：99.99% 尾差 → 收数据但 complete=False（v1 在此整批丢弃）
    r1 = finalize(21025, fake(21023), live)
    yes(r1['complete'] is False and r1['collected'] == 21023 and r1['missing'] == 2,
        '阳性: 尾差 2 条 → 数据可用但 complete=False（不得宣称穷举）')
    # 阳性：拉满 → complete=True
    yes(finalize(500, fake(500), live)['complete'] is True, '阳性: 拉满 → complete=True')

    print('  →', '自测通过' if ok else '自测失败')
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--industry', default='')
    ap.add_argument('--keywords', default='')
    ap.add_argument('--full', action='store_true', help='整表枚举该行业')
    ap.add_argument('--size', type=int, default=100)
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--no-write', action='store_true')
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    led = load_ledger()
    faces = {}

    try:
        if a.full and a.industry:
            print(f'[整表枚举] industry={a.industry}')
            r = enumerate_query(industry=a.industry, size=a.size)
            guard_shrink(led, a.industry, r['collected'])
            faces[a.industry] = r
        for kw in [k.strip() for k in a.keywords.split(',') if k.strip()]:
            print(f'[关键词枚举] key={kw}')
            r = enumerate_query(key=kw, size=a.size)
            guard_shrink(led, 'kw:' + kw, r['collected'])
            faces['kw:' + kw] = r
    except ChannelError as exc:
        print(f'\n🔴 通道异常（RED）：{exc}')
        print('   → 未写台账。"拿不到"不等于"没有"，本轮不得据此下结论。')
        return 2

    if not faces:
        print('未指定 --industry --full 或 --keywords，无事可做')
        return 0

    merged = {}
    for name, r in faces.items():
        merged.update(r['records'])
        print(f'  {name}: total={r["total"]} 收齐={r["collected"]} '
              f'覆盖率={r.get("coverage", 0):.4%} complete={r["complete"]}'
              + (f'  ⚠️{r["note"]}' if r.get('note') else ''))
    exhaustive = all(r['complete'] for r in faces.values())
    if not exhaustive:
        miss = sum(r.get('missing', 0) for r in faces.values())
        print(f'  ⚠️ 本次**未拉满**（缺 {miss} 条）：可以说"已覆盖 N/M"，'
              f'**不得**宣称"整表穷举/已排除全部"。')

    scoped = {c: r for c, r in merged.items() if in_scope(str(r.get('chName') or ''))}
    print(f'\n去重合计 {len(merged)} 条，作用域内（机器人∩接口） {len(scoped)} 条：')
    for c, r in sorted(scoped.items()):
        print(f'  {c:22s} [{r.get("status")}] {r.get("industry")}  '
              f'{str(r.get("chName"))[:52]}')
        print(f'      evidence: {DETAIL_URL}{r.get("pk")}')

    if not a.no_write:
        led.setdefault('scan_index', {})
        led.setdefault('baseline_max', {})
        for name, r in faces.items():
            led['scan_index'][name] = r['collected']
            led['baseline_max'][name] = max(
                int(led['baseline_max'].get(name) or 0), r['collected'])
        led.setdefault('runs', []).append({
            'at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'faces': {k: v['collected'] for k, v in faces.items()},
            'coverage': {k: round(v.get('coverage', 0), 6) for k, v in faces.items()},
            'complete': {k: bool(v['complete']) for k, v in faces.items()},
            'claims_exhaustive': exhaustive,
            'in_scope': sorted(scoped),
        })
        led['in_scope_latest'] = {
            c: {'name': r.get('chName'), 'status': r.get('status'),
                'industry': r.get('industry'),
                'evidence': DETAIL_URL + str(r.get('pk')),
                'evidence_tier': '题录库（全国标准信息公共服务平台 · 行标备案库）'}
            for c, r in sorted(scoped.items())}
        save_ledger(led)
        print(f'\n台账已更新: {os.path.relpath(LEDGER)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
