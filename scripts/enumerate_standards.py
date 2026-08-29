#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按发布机构/发布平台**枚举全表**，而不是按关键词搜新闻，来发现与本站命题相关的标准。

为什么要有这个脚本（2026-08-10 立）
------------------------------------
T/BTIAIRI 0001-2025《人形机器人电驱动一体化关节接口要求》2025-12-25 就已实施，
与本站命题（零部件机械+电气+通信接口）贴合度最高，却连续多轮没被我方碰到——
唯一原因是**它没上过热搜**。关键词召回的天花板是「曾被报道过」，
而我们需要的是「曾被发布过」。所以召回手段必须从"搜新闻"改成"枚举发布平台全表"。

召回边界（诚实声明，别把它当全覆盖）
------------------------------------
- ✅ 国家标准（GB / GB/T）：std.samr.gov.cn 提供可脚本化的 JSON 检索接口，
     且该站无 robots.txt（404），未声明禁止。本脚本枚举该表。
- ⛔ 团体标准（T/xxx）· 旧路：全国团体标准信息平台 www.ttbz.org.cn 的 `/ms/` 接口
     在其 robots.txt 中**被显式 Disallow**（实测 `Disallow: /ms/`），本脚本**不抓**该接口。
- ✅ 团体标准（T/xxx）· 新路（20260810-16 接入）：国家数字标准馆 www.ndls.org.cn
     的 `POST /api/standard/list` 同时收录团标，其 robots.txt 只禁 Bytespider/YisouSpider，
     对本 UA 放行。**按 ICS 分类整表枚举**（a826=25.040.30 工业机器人、机械手 等），
     而不是按关键词 —— 关键词的天花板是"曾被报道过"，ICS 整表才是"曾被发布过"。

发现渠道 ≠ 取证渠道（这条必须守住）
------------------------------------
ndls 详情页是 hash 型 URL（/standard/detail/<32位hash>），长期稳定性未验证。
故 ndls 只作**发现**渠道：命中条目写 `discovery_url`，`evidence` 一律留空
并标 `evidence_status='discovery_only'`。取证仍须回落 openstd / ttbz 详情页。
把两者混为一谈，就会重演 8/10 上午那批「拼出来的、看起来已取证的 404 深链」。

触发器纪律（沿用 20260809 教训）
------------------------------------
入库候选的判据是**作用域命中零部件接口**，不是"标题里有人形机器人"。
按后者选出来的标准，多数管的是整机安全/术语/伦理，一条也管不到接口。
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
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES = os.path.join(ROOT, 'api', 'entities.json')
LEDGER = os.path.join(ROOT, 'ops', 'intel', 'standards-enum-ledger.json')

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')

# 拉全表用的主题词。它们只负责"把表拉下来"，**不负责判定是否入库**。
TOPIC_QUERIES = [
    '机器人', '机械臂', '伺服', '减速器', '末端执行器', '连接器', '编码器',
]

# 触发器是**两因子**，缺一不可（首版只做了 B 因子，结果把 LNG 加注连接器、
# 射频同轴连接器、坠落防护连接器全判成候选——"连接器"三个字在全国标准里
# 属于最泛的词之一。词面命中 ≠ 作用域命中，这正是 20260809 立下的纪律）。
#   A 因子·领域：标的必须是机器人/机械臂或其零部件本体
#   B 因子·层面：管的必须是接口/连接/安装配合，而不是整机安全、术语、性能
DOMAIN_PATTERNS = [
    '机器人', '机械臂', '操作机', '末端执行器', '执行器', '关节',
    '伺服', '减速器', '编码器', '驱动器', '舵机', '夹持器', '手爪',
]
DOMAIN_RE = re.compile('|'.join(map(re.escape, DOMAIN_PATTERNS)))

SCOPE_PATTERNS = [
    '接口', '连接器', '法兰', '安装尺寸', '互换', '快换', '接插件',
    '机械接口', '电气接口', '通信协议', '总线', '连接尺寸', '配合尺寸',
    '安装面', '联轴', '插头', '插座', '端子', '协议',
]
SCOPE_RE = re.compile('|'.join(map(re.escape, SCOPE_PATTERNS)))


def in_scope(name: str) -> bool:
    """两因子与逻辑。只有同时命中领域与接口层面才算候选。"""
    return bool(DOMAIN_RE.search(name) and SCOPE_RE.search(name))


GB_API = 'https://std.samr.gov.cn/gb/search/gbQueryPage'
GB_DETAIL = 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno='
OPENSTD_LIST = 'https://openstd.samr.gov.cn/bzgk/gb/std_list'

# ⚠️ 曾经的坑（首版就踩了，20260810 当轮发现并修）：
# 检索接口返回的 `id` **不是** openstd 的 hcno，把它拼成
# `https://std.samr.gov.cn/gb/search/gbDetailed?id=<id>` 会得到一个
# 「无法找到该页面」的死链。死链当证据比没有证据更糟——它看起来已取证，
# 没人会再点开核。故 hcno 必须**另行解析**，解析不到就如实标记未取证。


def resolve_openstd(code: str, sleep: float = 0.6) -> str | None:
    """按标准号在 openstd 全文公开系统反查真实详情链接（hcno）。

    解析不到就返回 None —— 宁可留空，也不吐一个打不开的 URL 冒充证据。
    """
    try:
        url = (f'{OPENSTD_LIST}?p.p1=0&p.p90=circulation_date&p.p91=desc'
               f'&p.p2={urllib.parse.quote(code)}')
        html = fetch(url, timeout=30).decode('utf-8', 'ignore')
    except Exception:
        return None
    finally:
        time.sleep(sleep)
    # 行内形如： <a ... onclick="showInfo('6337492B943BFA7D793FF14B579499EA');">GB/T 29825-2013</a>
    for hcno, shown in re.findall(
            r"showInfo\('([0-9A-Fa-f]{20,})'\);?\"[^>]*>\s*([^<]+?)\s*<", html):
        if norm_code(shown) == norm_code(code):
            return GB_DETAIL + hcno
    return None


def _clean(s: str) -> str:
    """去掉检索接口塞进标题的 <sacinfo> 高亮标签。"""
    return re.sub(r'</?sacinfo>', '', s or '').strip()


def fetch(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://std.samr.gov.cn/',
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ⚠️ 第三个「参数名写错不会报错，只会安静退化」的坑（20260810-19 实测揪出）：
# 本枚举器**从第一版起**就用 `current=<页码>` 翻页 —— 而 std.samr 认的是 `pageNo`。
# `current` 被静默忽略，于是每一页返回的都是**同一批前 50 条**。
# 它伪装得极好，因为三个信号互相打掩护：
#   · 日志打印「[机器人] 拉到 200 条」，看起来翻了 4 页；实际是 50 条重复 4 遍。
#   · 停止条件 `page*page_size >= total` 用的是接口自报的 total=183 —— 4 页 200
#     条恰好越过 183 就 break，**"拉满了"的假象反而成了停下来的理由**。
#   · 已拉条数(200) > 接口自报总数(183) 这个明摆着的矛盾，没有任何一处代码在看。
# 后果：上一轮宣称「164 条国标整表枚举」，真相是「7 个检索词各取前 50 条去重」。
# 现行国标 GB/T 43200-2023《机器人一体化关节性能及试验方法》就漏在第 50 条之后，
# 直到外部情报提到它、`--why` 回答"不在扫描面内"才暴露。
#
# 教训不在"参数名记错"，而在**同一个坑源码里已经写着**：第 179 行为 ndls 记下
# 「传 icsLevel3 会被忽略、静默退化成没过滤」，并配了回填校验；GB 侧却裸奔。
# 已知的坑只在一侧设防，等于没设防。故这里补三道与 ndls 同构的自证闸。
def enumerate_gb(query: str, page_size: int = 50, max_pages: int = 12,
                 sleep: float = 0.8) -> list[dict]:
    """枚举国家标准检索表（全量翻页 + 三道自证：不重复页 / 不触上限 / 条数对得上）。"""
    out: list[dict] = []
    q = urllib.parse.quote(query)
    seen_codes: set[str] = set()
    total = 0
    prev_first = None
    page = 0
    for page in range(1, max_pages + 1):
        url = f'{GB_API}?searchText={q}&pageSize={page_size}&pageNo={page}'
        try:
            body = fetch(url)
        except Exception as e:  # 网络抖动不该让整轮枚举失败
            print(f'   ! {query} 第{page}页失败: {type(e).__name__} {e}')
            break
        try:
            data = json.loads(body.decode('utf-8'))
        except Exception:
            print(f'   ! {query} 第{page}页返回非 JSON（可能被拦截），停止')
            break
        rows = data.get('rows') or []
        if not rows:
            break
        total = data.get('total') or total

        # 自证①：翻页参数一旦被忽略，页页同首条 —— 这正是 current 的失效形态
        first = _clean(rows[0].get('C_STD_CODE'))
        if prev_first is not None and first == prev_first:
            raise RuntimeError(
                f'[{query}] 第{page}页与上页首条相同({first}) —— 翻页参数被忽略，'
                f'拿到的是同一批数据，绝不能当成全表')
        prev_first = first

        for r in rows:
            code = _clean(r.get('C_STD_CODE'))
            if code in seen_codes:
                continue
            seen_codes.add(code)
            out.append({
                'code': code,
                'name': _clean(r.get('C_C_NAME')),
                'nature': r.get('STD_NATURE'),
                'state': r.get('STATE'),
                'issue_date': r.get('ISSUE_DATE'),
                'act_date': r.get('ACT_DATE'),
                'id': r.get('id'),
                'via_query': query,
            })
        if len(rows) < page_size:
            break
        time.sleep(sleep)

    # 自证②：触到翻页深度上限 = 后面还有、只是没去拿（截断的表不是全表）
    if page >= max_pages and total > page * page_size:
        raise RuntimeError(
            f'[{query}] 翻页触及深度上限 {max_pages} 页而 total={total} —— 存在截断')
    # 自证③：拿到的唯一条数必须与接口自报总数对得上（多了少了都说明理解错了接口）
    if total and len(out) != total:
        print(f'   ! [{query}] 唯一 {len(out)} 条 ≠ 接口自报 total={total}'
              f'（差 {len(out) - total:+d}，接口可能含重复号或跨版本条目）')
    return out


# ── 团体标准枚举（国家数字标准馆 ndls.org.cn） ──────────────────────────────
NDLS_API = 'https://www.ndls.org.cn/api/standard/list'
NDLS_DETAIL = 'https://www.ndls.org.cn/standard/detail/'

# 按 ICS 分类整表枚举。选类而非选词，是为了让召回边界可陈述、可复核：
# "ICS 25.040.30 下的全部团标我都过了一遍"，而不是"我搜了几个词"。
NDLS_ICS_CLASSES = [
    ('25.040.30', '工业机器人、机械手'),
    ('25.040.01', '工业自动化系统 综合'),
]

# ⚠️ 静默失效的坑（本轮实测）：同一个接口，传 `icsLevel3=25.040.30` 会被**忽略**，
# 返回 count=10000 的全库结果且行内 ICS 是 13.060.50 —— 参数名写错不会报错，
# 只会安静地退化成"没过滤"。若不校验，枚举器会把全库当成本类全表，
# 得出"这一类里没有接口标准"的错误结论。故每页都要回填校验 ICS。
NDLS_UNFILTERED_SENTINEL = 10000

# ⚠️ 第二个坑（同轮实测）：翻页在**第 6 页硬截断**（data=null），
# 即单次查询最多只能取到 250 条。ICS 25.040.30 团标共 436 条 →
# 直接翻页只能拿到 250 条，剩下 186 条**永远看不见，且不会报错**。
# 「截断的表不是全表」——这与关键词召回的天花板是同一种病，只是换了个位置。
# 解法：用接口自带的 publicyear 聚合桶把全类切成年片（最大片 95 条 < 250），
# 逐片穷举后用 sum(桶) == 全类总数 自证没漏。
NDLS_DEPTH_CAP = 250

# 本轮各 ICS 分类的覆盖率账本。**覆盖率必须落盘**：
# 「拉到 250 条」看起来很勤奋，但它到底是全类 250 条还是全类 436 条里的 250 条，
# 差别是"已穷举"与"漏了 43%"。不记账，下游就只能猜。
ENUM_COVERAGE: list[dict] = []


# 服务端用同一个 code 5320 同时表示两件事：**瞬时限流** 与 **翻页越界**。
# 实测：25.040.01/2024 首 3 次 5320、随后成功（限流）；第 6 页连试 4 次全 5320（越界）。
# 既然本枚举器把每个年片都切到 ≤250 条（即 ≤5 页），就**永远不会合法地请求第 6 页**，
# 于是判据可以收敛成一句不含糊的话：退避重试仍 5320 = 真失败，抛错，不许静默少收。
NDLS_THROTTLE_CODE = 5320
NDLS_BACKOFF = (5, 15, 45, 120, 240)

# ⚠️ 第三个坑，也是最凶的一个（20260811-07 实测）：ndls 前置了加速乐(Jiasule) JS 反爬
# （响应带 `__jsluid_s` Cookie），`/api/standard/list` 不再返回结果集，
# 而是 `code:0, data:{"visitToken":"ndls-platform:VISIT-TOKEN:<uuid>"}`，每次都换一个新 token。
#
# 为什么这一条必须单独立闸：原有三道自证（过滤未静默失效 / 未触深度上限 / sum(年桶)==总数）
# **全部是在"返回的数据内部"做一致性检查**。当返回里压根没有结果集时，它们不是判红，
# 而是各自"平凡地成立"—— total=0 → 年桶为空 → 收 0 条 → `0 == 0` → complete=True。
# 于是「穷举自证」退化成一句同义反复，对外却宣称"这一类我整表过了一遍，一条都没有"。
# 这比抓取失败危险得多：失败会重试会告警，**假绿会被下游当成结论**。
# 实测该退化路径：ICS 25.040.30（历史 436 条）返回 `complete: True, collected: 0/0`。
#
# 立场：本枚举器**不绕过反爬**（不解 JS 挑战、不伪造 token）。抓取权限是别人给的，
# 对方明确设卡就是收回了权限，正确反应是判红+冷却+换合规渠道，不是想办法钻过去。
NDLS_CHALLENGE_KEY = 'visitToken'

# 缩水闸：与 `ingest_oss.mjs` 的">10% 缩水拒写"同源。历史上有数百条的分类突然"全类 0 条"，
# 合理解释是我们被挡在门外，而不是国家把这类标准全撤了。
NDLS_MAX_SHRINK = 0.10


def _ndls_assert_resultset(data, ctx: str, need_count: bool = False) -> None:
    """响应必须是**结果集本身**，而不是挑战页/其它形态。

    这道闸补的是一个结构性盲区：所有既有自证都假设"我们拿到的是一张表"，
    却从没有人验证过这个前提。前提不成立时，它们会一致地判绿。
    """
    if not isinstance(data, dict):
        raise RuntimeError(f'{ctx}: data 非对象（{type(data).__name__}），协议疑似变更')
    if NDLS_CHALLENGE_KEY in data and 'results' not in data:
        raise RuntimeError(
            f'{ctx}: 返回 {NDLS_CHALLENGE_KEY} 挑战而非结果集 —— '
            f'加速乐 JS 反爬已前置；本枚举器不绕过反爬，改判失败并冷却')
    if 'results' not in data:
        raise RuntimeError(
            f'{ctx}: 返回缺少 results 字段（实得 {sorted(data)[:6]}），协议疑似变更')
    if need_count and data.get('count') is None:
        raise RuntimeError(
            f'{ctx}: 返回缺少 count 字段（实得 {sorted(data)[:6]}），无法自证穷举，中止')


def _ndls_post(body: dict, timeout: int = 30) -> dict:
    last = None
    for i, wait in enumerate((0,) + NDLS_BACKOFF):
        if wait:
            time.sleep(wait)
        req = urllib.request.Request(
            NDLS_API, data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
            headers={
                'User-Agent': UA,
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://www.ndls.org.cn/standard/index',
            })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                res = json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last = f'{type(e).__name__} {e}'
            continue
        if res.get('code') == NDLS_THROTTLE_CODE:
            last = f'code={NDLS_THROTTLE_CODE}(限流/越界) 第{i + 1}次'
            continue
        return res
    raise RuntimeError(f'ndls 请求失败（已退避重试 {len(NDLS_BACKOFF)} 次）: {last} body={body}')


T_CODE_RE = re.compile(r'T/[A-Z]{2,12}\s*[A-Z]{0,4}\s*\d+(?:\.\d+)?\s*[—\-]\s*\d{4}')


def _extract_t_code(a100: str) -> str:
    """从 ndls 的 a100 里取出标准号。

    a100 有两种形态：规范的 `T/CIET 1214-2025`，以及把名称也塞进去的
    `T/CIE 轮式机器人移动平台 设计通则-2015`（早期条目）。后者取不出编号，
    就原样返回并由调用方标记 —— 不编一个看起来像编号的东西。
    """
    m = T_CODE_RE.search(a100 or '')
    return m.group(0).strip() if m else (a100 or '').strip()


def _ndls_row(r: dict, ics: str, via: str) -> dict:
    a100 = _clean(r.get('a100'))
    return {
        'code': _extract_t_code(a100),
        'code_parsed': bool(T_CODE_RE.search(a100 or '')),
        'name': _clean(r.get('a298')) or a100,
        'nature': r.get('a104name') or '团体标准',
        'state': (r.get('a000') or '').strip(),
        'issue_date': r.get('a101'),
        'act_date': r.get('a205'),
        'id': r.get('yf001'),
        'ics': r.get('a826'),
        'via_query': via,
        # 发现渠道，不是证据。evidence 由调用方置空。
        'discovery_url': NDLS_DETAIL + str(r.get('yf001') or ''),
    }


def _ndls_page(ics: str, year: int | None, page: int, size: int,
               need_count: bool = False) -> dict:
    body = {'page': page, 'size': size, 'a104': 'CN-TUANTI', 'a826': ics}
    if year is not None:
        body['publicyear'] = str(year)
    data = (_ndls_post(body) or {}).get('data')
    if data is None:
        # 第 6 页起服务端直接回 data=null，这是深度截断的信号，不是"没有更多"
        raise RuntimeError(f'ICS {ics} year={year} 第{page}页返回 data=null（深度截断）')
    # 先确认"这是一张表"，再谈表里的一致性（见 _ndls_assert_resultset）
    _ndls_assert_resultset(data, f'ICS {ics} year={year} 第{page}页', need_count=need_count)
    rows = data.get('results') or []
    bad = [r.get('a826') for r in rows if (r.get('a826') or '') != ics]
    if bad:
        raise RuntimeError(
            f'ICS {ics} 回填校验失败，出现异类 ICS {sorted(set(bad))[:3]}（过滤静默失效）')
    if year is not None:
        badyr = [r.get('publicyear') for r in rows if r.get('publicyear') != year]
        if badyr:
            raise RuntimeError(
                f'ICS {ics} year={year} 回填校验失败，出现异年 {sorted(set(badyr))[:3]}')
    return data


def enumerate_ndls(ics: str, page_size: int = 50, max_pages: int = 12,
                   sleep: float = 3.0, baseline: int | None = None) -> list[dict]:
    """枚举国家数字标准馆里某个 ICS 分类下的**全部团体标准**（真·全表）。

    三道自证，任一不过就抛错中止 —— 宁可这一类没枚举成，
    也不能拿"截断的表 / 没过滤的全库"冒充本类全表：
      1. 过滤未静默失效：每页回填校验 ICS（与请求不符即中止）；
      2. 分片不触深度上限：单个年片 > 250 条即中止（要求再分片），不硬翻；
      3. 穷举自证：sum(年桶) == 全类总数，且实际去重收到的条数 == 全类总数。
      4. 返回的确实是一张表（_ndls_assert_resultset），且这张表非空、未相对历史缩水
         —— 前三道都在"表内部"自证，第 4 道自证"表这个前提本身"。
    """
    probe = _ndls_page(ics, None, 1, 1, need_count=True)
    total = probe.get('count') or 0
    if total >= NDLS_UNFILTERED_SENTINEL:
        raise RuntimeError(f'ICS {ics} 返回 count={total}（哨兵值），过滤疑似静默失效，中止')
    # 空表不许自证穷举：`0 == 0` 恒真会把"被挡在门外"渲染成"这一类确实没有标准"
    if total <= 0:
        raise RuntimeError(
            f'ICS {ics} 全类 count={total} —— 空表不构成穷举证明'
            f'（疑似被拦截/协议变更），中止而非宣称"本类无标准"')
    if baseline and total < baseline * (1 - NDLS_MAX_SHRINK):
        raise RuntimeError(
            f'ICS {ics} 全类 count={total} 较上次成功枚举的 {baseline} 缩水 '
            f'{(1 - total / baseline) * 100:.0f}% > {NDLS_MAX_SHRINK * 100:.0f}%，'
            f'疑似召回退化，拒绝据此更新台账')
    agg = ((probe.get('aggregations') or {}).get('publicyear') or {})
    buckets = [(b['key'], b['doc_count']) for b in (agg.get('buckets') or [])]
    bucket_sum = sum(n for _, n in buckets)
    # 年桶合计可能小于全类总数（实测 25.040.01 少 2 条 —— 那些条目没有发布年份，
    # 落不进任何年片）。这不是致命错，但**绝不能当作已穷举**：先按年片跑完，
    # 再做一次无过滤扫尾捡漏，最后如实记覆盖率。差多少就说差多少。
    out: list[dict] = []
    seen_ids: set[str] = set()
    for year, n in sorted(buckets, reverse=True):
        if n > NDLS_DEPTH_CAP:
            raise RuntimeError(
                f'ICS {ics} 年片 {year} 有 {n} 条 > 深度上限 {NDLS_DEPTH_CAP}，需再分片，中止')
        got = 0
        for page in range(1, max_pages + 1):
            data = _ndls_page(ics, year, page, page_size)
            rows = data.get('results') or []
            if not rows:
                break
            for r in rows:
                rid = str(r.get('yf001') or '')
                if rid and rid in seen_ids:
                    continue
                seen_ids.add(rid)
                out.append(_ndls_row(r, ics, f'ICS {ics}/{year}'))
            got += len(rows)
            if got >= n:
                break
            time.sleep(sleep)
        time.sleep(sleep)

    # 残差扫尾：年片覆盖不到的（无发布年份），用无过滤翻页在深度上限内捡一遍
    if len(seen_ids) < total:
        for page in range(1, (NDLS_DEPTH_CAP // page_size) + 1):
            data = _ndls_page(ics, None, page, page_size)
            rows = data.get('results') or []
            if not rows:
                break
            for r in rows:
                rid = str(r.get('yf001') or '')
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    out.append(_ndls_row(r, ics, f'ICS {ics}/残差扫尾'))
            time.sleep(sleep)

    complete = len(seen_ids) == total
    ENUM_COVERAGE.append({
        'ics': ics, 'total': total, 'collected': len(seen_ids),
        'year_slices': len(buckets), 'bucket_sum': bucket_sum,
        'complete': complete,
    })
    mark = '穷举自证' if complete else '⚠ 未穷举（如实记账，不冒充全表）'
    print(f'    {mark}: {len(buckets)} 个年片，实收 {len(seen_ids)}/{total} 条')
    return out


def known_codes() -> set[str]:
    """已在登记表 / 观察名单里的标准编号（含题录库口径的空格差异归一）。"""
    with open(ENTITIES, encoding='utf-8') as f:
        meta = json.load(f)['meta']
    spec = meta.get('standard_conformance_spec') or {}
    codes: set[str] = set()
    for s in spec.get('standards', []):
        if s.get('id'):
            codes.add(norm_code(s['id']))
    for w in spec.get('registry_watchlist', []) or []:
        if isinstance(w, dict) and w.get('id'):
            codes.add(norm_code(w['id']))
        elif isinstance(w, str):
            m = re.search(r'[A-Z/]+\s*[\d.]+[—\-]\d{4}', w)
            if m:
                codes.add(norm_code(m.group(0)))
    return codes


def norm_code(c: str) -> str:
    return re.sub(r'\s+', ' ', (c or '').replace('—', '-')).strip().upper()


def load_ledger() -> dict:
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding='utf-8') as f:
            return json.load(f)
    return {'version': 1, 'seen': {}, 'runs': []}


def save_ledger(led: dict) -> None:
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, 'w', encoding='utf-8') as f:
        json.dump(led, f, ensure_ascii=False, indent=2)
        f.write('\n')


def _collect_gb(max_pages: int) -> dict[str, dict]:
    seen_rows: dict[str, dict] = {}
    for q in TOPIC_QUERIES:
        rows = enumerate_gb(q, max_pages=max_pages)
        print(f'  [{q}] 拉到 {len(rows)} 条')
        for r in rows:
            key = norm_code(r['code'])
            if key and key not in seen_rows:
                seen_rows[key] = r
    return seen_rows


def ndls_baselines(led: dict | None) -> dict[str, int]:
    """从台账里取每个 ICS 分类**上次成功枚举到的全类总数**，作为缩水闸的基线。

    取"历史最大值"而非"最近一次"：缩水闸要防的就是召回退化，
    拿一个已经退化过的值当基线，等于把退化后的水位认成正常水位。
    """
    out: dict[str, int] = {}
    for r in ((led or {}).get('runs') or []):
        for c in (r.get('coverage') or []):
            ics, tot = c.get('ics'), c.get('total') or 0
            if ics and tot > out.get(ics, 0):
                out[ics] = tot
    return out


def _collect_ndls(max_pages: int, led: dict | None = None) -> dict[str, dict]:
    seen_rows: dict[str, dict] = {}
    base = ndls_baselines(led)
    for ics, label in NDLS_ICS_CLASSES:
        rows = enumerate_ndls(ics, max_pages=max_pages, baseline=base.get(ics))
        print(f'  [ICS {ics} {label}] 拉到 {len(rows)} 条团标'
              f'（基线 {base.get(ics, "无")}）')
        for r in rows:
            key = norm_code(r['code'])
            if key and key not in seen_rows:
                seen_rows[key] = r
    return seen_rows


def _judge(seen_rows: dict[str, dict], source_key: str,
           kn: set[str], already: set[str]) -> tuple[list, list, list]:
    """两因子判定 + 取证。GB 走 openstd 反查；团标只记发现渠道，不伪造证据。"""
    hits, new_hits, obsolete = [], [], []
    for key, r in sorted(seen_rows.items()):
        if not in_scope(r['name']):
            continue
        if source_key == 'gb':
            r['evidence'] = resolve_openstd(r['code']) or ''
            r['evidence_status'] = 'resolved' if r['evidence'] else 'unresolved'
        else:
            # 发现渠道 ≠ 取证渠道：ndls 的 hash URL 只进 discovery_url
            r['evidence'] = ''
            r['evidence_status'] = 'discovery_only'
        r['source_key'] = source_key
        hits.append(r)
        if key in kn or key in already:
            continue
        if (r.get('state') or '').strip() in ('废止', '作废', '被代替'):
            obsolete.append(r)
        else:
            new_hits.append(r)
    return hits, new_hits, obsolete


def _scan_index(seen_rows: dict) -> dict:
    """把**整个扫描面**（不只命中项）压成可机读索引。

    20260810-19 补，起因是一次真实的"查不出来"：外部情报提到现行国标
    GB/T 43200-2023《机器人一体化关节性能及试验方法》，回台账一搜 —— 没有。
    台账里只有 7 条命中项和一个数字 `scanned: 164`，于是**无法回答**最要紧的
    那个问题：这条标准是「扫到了、按两因子淘汰」还是「压根没进扫描面」。
    两者的处置天差地别（前者说明判定正确，后者说明召回有洞），却长得一模一样。

    上一轮的结论是「按发布机构枚举全表才叫穷举」；但**枚举了不留痕 == 没法自证枚举过**。
    只记命中项的台账，把"我筛掉了"和"我没看见"混成同一种沉默。
    故这里把扫描面连同两个因子的命中情况一并落账，`--why <标准号>` 可直接质询。
    """
    idx = {}
    for key, r in seen_rows.items():
        name = r.get('name') or ''
        idx[key] = {
            'name': name[:80],
            'd': bool(DOMAIN_RE.search(name)),   # 领域因子（机器人零部件）
            's': bool(SCOPE_RE.search(name)),    # 层面因子（接口）
        }
    return idx


def explain(code: str, led: dict) -> str:
    """质询台账：某条标准在不在扫描面内、为何没进登记表。"""
    key = re.sub(r'\s+', '', code).upper()
    for sk, idx in (led.get('scan_index') or {}).items():
        for k, v in idx.items():
            if re.sub(r'\s+', '', k).upper() == key:
                if v['d'] and v['s']:
                    verdict = '两因子均命中 → 应为候选（不在登记表则查已登记/已废止扣除）'
                elif v['d']:
                    verdict = '领域命中、**层面未命中** → 按两因子正确淘汰（非接口类标准）'
                elif v['s']:
                    verdict = '层面命中、**领域未命中** → 按两因子正确淘汰（非机器人零部件）'
                else:
                    verdict = '两因子均未命中 → 淘汰'
                return ('在扫描面内（来源 %s）\n  标题: %s\n  领域因子: %s / 层面因子: %s\n  结论: %s'
                        % (sk, v['name'], v['d'], v['s'], verdict))
    scanned = sum(len(i) for i in (led.get('scan_index') or {}).values())
    return ('**不在**已落账的扫描面内（当前扫描面共 %d 条）——\n'
            '  这是召回缺口，不是判定结果：说明检索词/ICS 分类没覆盖到它。' % scanned)


SOURCE_LABEL = {
    'gb': 'std.samr.gov.cn/gb (GB/GB-T only)',
    'tuanbiao': 'ndls.org.cn /api/standard/list (团体标准, ICS 整表)',
}

# ── 声明式来源表（20260810-20 立） ─────────────────────────────────────────
# 为什么要有它：此前"枚举是否还在跑"只看台账 runs[-1]。gb 便宜且几乎必成功，
# 于是每跑一次 gb 就把台账刷新成"新鲜"，**团标源可以一次都没成功过而全程绿灯**。
# 而我方召回缺口恰恰全部集中在团标域（与本站命题最贴合的
# T/BTIAIRI 0001-2025 正是团标）——闸门看不见的地方，正是问题所在的地方。
# 所以：**每一个声明过的来源各自计时**，谁哑了谁判红，别人跑得勤不能替它遮丑。
ENUM_SOURCES = {
    'gb': {'declared_at': '2026-08-10T12:00:00+08:00'},
    'tuanbiao': {'declared_at': '2026-08-10T16:00:00+08:00'},
}
SOURCE_MAX_AGE_DAYS = 14.0          # 单个来源允许的最长静默（含"从未成功"的宽限）
FAIL_COOLDOWN_HOURS = 12.0          # 被 IP 限流后必须的沉默期
DEFAULT_MIN_INTERVAL_HOURS = 20.0   # 成功后的礼貌间隔（标准发布是天级事件）


def _parse_dt(s):
    try:
        return datetime.fromisoformat(str(s))
    except Exception:
        return None


def source_states(led: dict, now: datetime | None = None,
                  min_interval_hours: float = DEFAULT_MIN_INTERVAL_HOURS) -> dict:
    """每个**声明来源**各自一份状态（唯一源；regression 的 L1.79 直接引用本函数）。

    字段语义：
      last_success  该来源最近一次**真的拉到表**（scanned>0）的时间，从未成功为 None
      silent_days   自 last_success（从未成功则自 declared_at）起的静默天数
      overdue       静默超过 SOURCE_MAX_AGE_DAYS → 判红。**never 也会 overdue**，
                    这正是修的那个洞：从未成功不能因为"没有记录"而免于计时。
      cooling       正处在失败冷却里（被限流后的强制沉默）
      due           现在就该跑（既不在礼貌间隔内、也不在失败冷却内）
    """
    now = now or datetime.now(timezone(timedelta(hours=8)))
    runs = (led or {}).get('runs') or []
    attempts = (led or {}).get('attempts') or {}
    # 台账可显式声明「来源自 X 时刻起声明」（led['declared'][sk]），
    # 覆盖 ENUM_SOURCES 里的默认声明时间 —— 新来源入台账即可从当天起算宽限，
    # 测试也能构造「从未成功但宽限期内」的真实形态（见 L1.79 阴性）。
    declared_overrides = (led or {}).get('declared') or {}
    out = {}
    for sk, spec in ENUM_SOURCES.items():
        last_ok = None
        for r in runs:
            # 早期记录没有 source_key，那时只有 gb 一个来源
            if (r.get('source_key') or 'gb') != sk:
                continue
            if not r.get('scanned'):
                continue  # 空跑不算成功：时间新 ≠ 真的拉到表
            dt = _parse_dt(r.get('at'))
            if dt and (last_ok is None or dt > last_ok):
                last_ok = dt
        declared_at = declared_overrides.get(sk) or spec.get('declared_at')
        ref = last_ok or _parse_dt(declared_at) or now
        silent_days = (now - ref).total_seconds() / 86400.0

        fail = attempts.get(sk) or {}
        fail_dt = _parse_dt(fail.get('at')) if fail.get('status') == 'failed' else None
        cooling = bool(fail_dt and (now - fail_dt).total_seconds() < FAIL_COOLDOWN_HOURS * 3600)

        polite = bool(last_ok and (now - last_ok).total_seconds() < min_interval_hours * 3600)

        out[sk] = {
            'label': SOURCE_LABEL.get(sk, sk),
            'last_success': last_ok.isoformat() if last_ok else None,
            'never': last_ok is None,
            'silent_days': round(silent_days, 2),
            'overdue': silent_days > SOURCE_MAX_AGE_DAYS,
            'cooling': cooling,
            'cool_until': ((fail_dt + timedelta(hours=FAIL_COOLDOWN_HOURS)).isoformat()
                           if cooling else None),
            'fail_reason': fail.get('reason') if cooling else None,
            'due': (not polite) and (not cooling),
            'grace_days_left': (round(SOURCE_MAX_AGE_DAYS - silent_days, 2)
                                if not last_ok else None),
        }
    return out


def ledger_verdict(led: dict, now: datetime | None = None) -> tuple[bool, str, dict]:
    """把「枚举召回是否仍然真的在跑」判成一句话 —— 但**逐来源**判，不再只看 runs[-1]。"""
    if not (led or {}).get('runs'):
        return False, '台账无任何运行记录', {}
    st = source_states(led, now)
    bad = ['%s 静默 %.1f 天%s' % (sk, s['silent_days'], '（从未成功）' if s['never'] else '')
           for sk, s in st.items() if s['overdue']]
    if bad:
        return False, '超过 %.0f 天未被真正枚举: %s' % (SOURCE_MAX_AGE_DAYS, '; '.join(bad)), st
    return True, '; '.join(
        '%s %s' % (sk, ('从未成功，宽限剩 %.1f 天' % s['grace_days_left']) if s['never']
                   else '距上次成功 %.1f 天' % s['silent_days'])
        for sk, s in st.items()), st


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true',
                    help='不写台账，只打印（用于自检幂等）')
    ap.add_argument('--max-pages', type=int, default=8)
    ap.add_argument('--source', choices=['gb', 'ndls', 'all'], default='all',
                    help='gb=国家标准；ndls=团体标准（国家数字标准馆）；all=两者')
    ap.add_argument('--min-interval-hours', type=float, default=DEFAULT_MIN_INTERVAL_HOURS,
                    help='同一来源两次枚举的最小间隔（礼貌闸，飞轮每小时跑也不会每小时抓）')
    ap.add_argument('--why', metavar='CODE',
                    help='质询台账：某标准号在不在扫描面内、为何没进登记表（只读，不发请求）')
    ap.add_argument('--due', action='store_true',
                    help='只读：逐来源打印"现在该不该跑"，不发任何请求。'
                         '退出码 0=有来源到期该跑 / 1=全部在冷却或礼貌间隔内')
    args = ap.parse_args()

    if args.why:
        print(explain(args.why, load_ledger()))
        return 0

    if args.due:
        st = source_states(load_ledger(), min_interval_hours=args.min_interval_hours)
        any_due = False
        for sk, s in st.items():
            if s['due']:
                any_due = True
                tag = 'DUE   '
                extra = '（从未成功）' if s['never'] else ''
            elif s['cooling']:
                tag = 'COOL  '
                extra = '→ %s 后可重试；上次失败: %s' % (s['cool_until'], s['fail_reason'])
            else:
                tag = 'POLITE'
                extra = '距上次成功 %.1fh 内' % (s['silent_days'] * 24)
            print('%s %-9s 静默 %.2f 天%s %s'
                  % (tag, sk, s['silent_days'],
                     '（超期！）' if s['overdue'] else '', extra))
        return 0 if any_due else 1

    print('=' * 60)
    print('标准枚举器 · 按发布平台拉全表（非关键词搜新闻）')
    print('召回边界: GB/GB-T 走 std.samr 检索表；团标走 ndls ICS 整表；')
    print('          ttbz 的 /ms/ 被 robots 禁止，全程不抓')
    print('=' * 60)

    kn = known_codes()
    led = load_ledger()
    already = set(led.get('seen', {}).keys())
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()

    def _last_run_at(sk: str):
        for r in reversed(led.get('runs') or []):
            if (r.get('source_key') or 'gb') == sk:
                try:
                    return datetime.fromisoformat(r['at'])
                except Exception:
                    return None
        return None

    plans = []
    if args.source in ('gb', 'all'):
        plans.append(('gb', _collect_gb))
    if args.source in ('ndls', 'all'):
        plans.append(('tuanbiao', _collect_ndls))

    # 礼貌闸：ndls 有 IP 级限流（实测密集请求后连基线查询都被 5320 拒掉，需分钟级冷却）。
    # 标准发布是天级事件，没有任何理由每小时枚举一次；飞轮每小时跑，这里每天至多一次。
    # 抓取权限是别人给的，用超了就没有了。
    # 失败冷却：一旦某来源因 5320 等被限流而中止，必须更长沉默才能恢复，
    # 否则每小时重试会反复触发 IP 惩罚、永远拿不到数据——所以失败也要记一笔并冷却。
    now_dt = datetime.now(timezone(timedelta(hours=8)))
    kept = []
    for sk, fn in plans:
        # 成功枚举的冷却（天级事件，每天至多一次）
        last = _last_run_at(sk)
        if last is not None and (now_dt - last).total_seconds() < args.min_interval_hours * 3600:
            age_h = (now_dt - last).total_seconds() / 3600
            print(f'  ⏭  跳过 {sk}：距上次枚举仅 {age_h:.1f}h < {args.min_interval_hours}h（礼貌闸）')
            continue
        # 失败枚举的冷却（IP 级限流需更长沉默才能恢复，否则会反复触发惩罚）
        last_fail = (led.get('attempts') or {}).get(sk)
        if last_fail and last_fail.get('status') == 'failed':
            try:
                fail_dt = datetime.fromisoformat(last_fail['at'])
            except Exception:
                fail_dt = None
            if fail_dt is not None and (now_dt - fail_dt).total_seconds() < FAIL_COOLDOWN_HOURS * 3600:
                age_h = (now_dt - fail_dt).total_seconds() / 3600
                print(f'  ⏭  跳过 {sk}：上次枚举失败于 {last_fail.get("at")}（{age_h:.1f}h 前），'
                      f'失败冷却 {FAIL_COOLDOWN_HOURS}h 仍不足，避免反复触发 IP 限流')
                continue
        kept.append((sk, fn))
    plans = kept

    total_new = 0
    for source_key, collect in plans:
        print(f'\n── 来源 {source_key}: {SOURCE_LABEL[source_key]} ──')
        try:
            rows = (collect(args.max_pages) if source_key == 'gb'
                    else collect(max(args.max_pages, 12), led))
        except RuntimeError as e:
            # 静默失效必须炸出来，不能悄悄记一笔"扫描 0 条"当没事
            print(f'   !! 该来源枚举中止: {e}')
            # 记失败冷却标记：避免每小时重试用完 IP 配额、反复触发惩罚
            led.setdefault('attempts', {})[source_key] = {
                'at': now, 'status': 'failed', 'reason': str(e)}
            continue
        # 成功抓取即清除失败冷却标记
        (led.get('attempts') or {}).pop(source_key, None)
        print(f'  去重后 {len(rows)} 条进入作用域判定')
        hits, new_hits, obsolete = _judge(rows, source_key, kn, already)
        print(f'  两因子命中（领域=机器人零部件 且 层面=接口）: {len(hits)} 条')
        print(f'  登记表与台账均未收录的新候选: {len(new_hits)} 条'
              f'（另 {len(obsolete)} 条已废止，仅留痕）')
        for r in new_hits:
            print(f"    NEW {r['code']}  {r['state']}  发布{r['issue_date']}  实施{r['act_date']}")
            print(f"        {r['name']}")
            if source_key == 'gb':
                print(f"        {r['evidence'] or '（openstd 未解析到详情链接，本条未取证）'}")
            else:
                print(f"        发现渠道(非证据): {r.get('discovery_url')}")
        total_new += len(new_hits)

        if not args.dry_run:
            for r in hits:
                entry = {
                    'name': r['name'], 'state': r['state'],
                    'issue_date': r['issue_date'], 'act_date': r['act_date'],
                    'evidence': r['evidence'],
                    'evidence_status': r.get('evidence_status', 'unresolved'),
                    'source_key': source_key,
                    'first_seen': now,
                }
                if r.get('discovery_url'):
                    entry['discovery_url'] = r['discovery_url']
                led['seen'].setdefault(norm_code(r['code']), entry)
            # 扫描面整体落账：让"筛掉了"与"没看见"从此可区分（见 _scan_index）
            # 但**空扫描面不得覆盖已有留痕**：一次被拦截的空跑会把 799 条扫描面抹成 0，
            # 而扫描面正是回答"这条标准是被筛掉还是没看见"的唯一依据 —— 抹掉它，
            # `--why` 就会把"我们曾经扫到过"错答成"从来不在扫描面内"（召回缺口的假象）。
            new_idx = _scan_index(rows)
            prev_idx = (led.get('scan_index') or {}).get(source_key) or {}
            if new_idx or not prev_idx:
                led.setdefault('scan_index', {})[source_key] = new_idx
            else:
                print(f'  ⚠ 本轮扫描面为空，保留上次的 {len(prev_idx)} 条'
                      f'（空扫描不得抹掉历史留痕）')
            run = {
                'at': now, 'scanned': len(rows),
                'scope_hits': len(hits), 'new': len(new_hits),
                'source_key': source_key,
                'source': SOURCE_LABEL[source_key],
            }
            if source_key == 'tuanbiao' and ENUM_COVERAGE:
                run['coverage'] = list(ENUM_COVERAGE)
                run['fully_enumerated'] = all(c['complete'] for c in ENUM_COVERAGE)
            led['runs'] = (led.get('runs') or [])[-19:] + [run]

    if not args.dry_run:
        save_ledger(led)
        print(f'\n台账已更新: {os.path.relpath(LEDGER, ROOT)}（新候选合计 {total_new} 条）')

    return 0


if __name__ == '__main__':
    sys.exit(main())
