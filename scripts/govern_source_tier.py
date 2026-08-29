#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboParts 溯源等级治理 —— source_tier 必须由证据推导，不得自封

【为什么有这个脚本 · 2026-08-10 第 70 次运行】
enrich_provenance.py 的文档字符串（2026-08-05 写下）明确定义：

    Tier A 可追溯 traceable —— 有 URL / 具名文档，**可点开复核**

同一份文件里，实现却是：

    def tier_of(e):
        if not e.get('source'): return 'C'
        if e.get('source_tier'): return e['source_tier']
        return 'A'                      # ← 只要 source 字段非空就是 A

再加上主函数里的 `if e.get('source') and not e.get('source_tier'): e['source_tier']='A'`，
结果是「往 source 里塞任何一句话就能拿 A」。而那段改动的注释恰恰写着
「杜绝指标注水」—— 反注水的补丁自己就是注水的。

实测后果（修复前全库 708 条）：
  · tier=A 336 条，其中真有深链、点得开具体页面的只有 48 条（14.3%）
  · 275 条 A 级实体**没有任何 URL**，包括 source 文本写着
    "web aggregation (credibility B)" 却标 A 的自相矛盾条目
  · 对外 meta.provenance_coverage 播报 traceable_pct=47.32%、
    tier_a_traceable=335，note 写明「Tier A 可点开复核」
    —— 真实可点开率 63/708=8.90%，**虚报约 5 倍**，且这是给 MCP/API
    消费方做来源过滤用的对外契约字段。

本脚本把判据收成唯一源 derive_tier()，enrich_provenance.py 反过来引用它，
不再各写一份（同一事实存两处的教训见 L1.69）。

判据只回答一个问题：**读者能不能顺着我们给的线索自己复核到这条数据。**
不回答「这条数据对不对」（那是 confidence / verified 的职责）。

  A 可追溯   有深链 URL（域名 + 路径），点开即落到具体产品/文档页
  B 可归因   仅根域名 URL（点开只到首页，找不到该型号）
             / 具名标准号（公开可查的锚点）
             / 具名厂商目录（来源身份明确，只是没留链接）
  C 无溯源   无 source / 无身份的聚合（web aggregation）/ 有话无锚点

用法：
    python scripts/govern_source_tier.py [--dry-run]
幂等：可重复运行，第二次起 changed=0。
"""
import json
import os
import re
import sys
import collections
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES_PATH = os.path.join(ROOT, 'api', 'entities.json')

# 可能承载 URL 的全部字段 —— 漏掉任何一个都会把有证据的实体误降级
URL_FIELDS = ('source', 'source_url', 'datasheet_url', 'url', 'homepage')
URL_RE = re.compile(r'https?://[^\s，,）)\]"\'<>]+')
# 裸域名（无 scheme）：库里大量来源写成 "agilityrobotics.com (URL 引用)"。
# 判据只问「读者能不能顺着复核」—— 补个 https:// 就能打开，与带 scheme 的等价。
# 限定 TLD 白名单，避免把 "audit_data_quality.py" 之类文件名误当域名。
BARE_DOMAIN_RE = re.compile(
    r'(?<![/\w.@-])((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+'
    r'(?:com|cn|org|net|io|ai|tech|co|de|jp|kr|eu|us|uk|fr|it|se|ch|nl|info|store|dev|xyz)'
    r'(?:\.[a-z]{2})?)((?:/[^\s，,）)\]"\'<>]*)?)',
    re.I,
)

# 具名标准号：公开可查的锚点，比「某厂商说的」强，但库里没存条文出处，仍算 B
NAMED_STANDARD = re.compile(
    r'\b(IEC|ISO|IEEE|CiA|SAE|EN|GB[/T]*|RFC|ANSI|JIS|USB|MIPI|OPC)\s*[-·]?\s*\d',
    re.I,
)
JUNK_STANDARDS = {
    'Proprietary', 'Industry Standard', 'Exhibition Standard',
    'Regional Policy Standard', '未指定', '未明确',
}

# 来源身份明确但无链接：读者虽点不开，但**知道去哪里找**（专利库、官方目录、规格书…）
# 分界线不是「有没有提到公司名」，而是「有没有指向一份可定位的具体材料」：
#   "Tesla 2026 patent filings" → 能去专利库按主体+年份检索到  → B
#   "Unitree Robotics 2025-2026" → 该厂两年内说过的一切都算？无法定位 → C
NAMED_ATTRIB = ('厂商目录声明值', '具名标准', '官方目录', '规格书', 'datasheet', 'specsheet',
                'patent', '专利', '白皮书', 'whitepaper', 'press release', '新闻稿',
                '年报', 'annual report', '招股', '说明书', '用户手册', 'manual',
                'catalog', 'catalogue', '产品目录', '官方文档', 'documentation')

# 无身份的聚合 / 明确自述不可信 —— 连「谁说的」都答不上来
NO_ANCHOR = ('web aggregation', 'web_aggregation', '网络聚合', 'aggregation',
             'web search', 'web_search', '网络检索', '公开资料整理', '推测', '估算')

# 自造来源：不是外部证据，是我方自己写的条目名。绝不能因为「source 非空」而得分。
SELF_AUTHORED = ('roboparts',)

VALID_TIERS = ('A', 'B', 'C')


def _extract(text):
    """从一段文本里抽出全部 URL，带 scheme 的和裸域名的都要"""
    if not isinstance(text, str) or not text:
        return []
    found = URL_RE.findall(text)
    # 抠掉已带 scheme 的部分，剩下的再找裸域名，避免同一个 URL 被数两次
    rest = URL_RE.sub(' ', text)
    for host, path in BARE_DOMAIN_RE.findall(rest):
        found.append('https://' + host + path)
    return found


def collect_urls(e):
    """收集实体上所有字段里出现的 URL（含 sources[] 数组、裸域名）"""
    out = []
    for f in URL_FIELDS:
        out.extend(_extract(e.get(f)))
    for s in (e.get('sources') or []):
        if isinstance(s, dict):
            for f in ('url', 'link', 'source_url'):
                out.extend(_extract(s.get(f)))
    return out


def _is_deep(u):
    """深链 = 有路径段，点开能落到具体页面；纯域名/首页不算"""
    try:
        p = urlparse(u)
    except ValueError:
        return False
    if not p.netloc:
        return False
    path = (p.path or '').strip('/')
    # 只有 query 也算能定位（如 ?id=xxx 的详情页）
    return bool(path) or bool(p.query)


def derive_tier(e):
    """唯一判据：只看证据形态，不看已有的 source_tier 字段。

    返回 (tier, basis)。basis 是可读的判定依据，写回实体便于审计。
    """
    urls = collect_urls(e)
    deep = [u for u in urls if _is_deep(u)]
    if deep:
        p = urlparse(deep[0])
        anchor = (p.netloc + p.path)[:60]
        return 'A', f'deep_link:{anchor}'
    if urls:
        # 根 URL 默认封顶 B（首页证明得了这家厂商存在，证明不了这个型号的任何参数）。
        # 唯一例外沿用 L1.70 的 source_scope：站点主体**就是该实体本身**时
        # （项目主页 / 标准组织自身），首页即其一手发布地，仍可 A。
        # 判据不在本文件另写一份 —— source_scope 是「根 URL 够不够 A」的子判据唯一源。
        #
        # 【20260810-21 实测缺陷】source_scope 判 'entity' 的依据是「实体名去掉域名
        # 主体后无残留标识」。名字**为空**时残留自然也为空 —— 于是无名条目一律
        # 白送 Tier A。判据不能因为「什么都没有」而放行，必须要求主体同一是被
        # 证明出来的，不是因缺失而默认成立。
        name = str(e.get('name') or '').strip()
        if name:
            try:
                import source_scope as _ss
                if _ss.scope_of({'name': name, 'source_url': urls[0]}) == 'entity':
                    return 'A', 'entity_homepage'
            except Exception:
                pass
        return 'B', 'root_url_only'

    src = str(e.get('source') or '').strip()
    if not src:
        return 'C', 'no_source'

    low = src.lower()
    std = str(e.get('standard') or '').strip()
    # 自造来源优先判死：否则 "RoboParts … Series/Catalog" 会蹭上 named_attrib
    if any(k in low for k in SELF_AUTHORED):
        return 'C', 'self_authored'
    if (NAMED_STANDARD.search(src) or
            (std and std not in JUNK_STANDARDS and NAMED_STANDARD.search(std))):
        return 'B', 'named_standard'
    if any(k.lower() in low for k in NAMED_ATTRIB):
        return 'B', 'named_vendor_catalog'
    if any(k.lower() in low for k in NO_ANCHOR):
        return 'C', 'aggregation_no_anchor'
    return 'C', 'unattributable_text'


def audit(entities):
    """只读审计：返回 (需变更列表, 分布Counter, basis分布Counter)"""
    changes, dist, basis_dist = [], collections.Counter(), collections.Counter()
    for e in entities:
        t, b = derive_tier(e)
        dist[t] += 1
        basis_dist[b] += 1
        if e.get('source_tier') != t:
            changes.append((e.get('id'), e.get('source_tier'), t, b))
    return changes, dist, basis_dist


def main():
    dry = '--dry-run' in sys.argv
    doc = json.load(open(ENTITIES_PATH, encoding='utf-8'))
    entities = doc['entities']

    before = collections.Counter(e.get('source_tier') for e in entities)
    changes, dist, basis_dist = audit(entities)

    if not dry:
        for e in entities:
            t, b = derive_tier(e)
            if e.get('source_tier') != t and 'source_tier_prev' not in e:
                # 首次纠正时留存原值，供审计「自封 A」的历史规模
                e['source_tier_prev'] = e.get('source_tier')
            e['source_tier'] = t
            e['source_tier_basis'] = b
        with open(ENTITIES_PATH, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write('\n')

    print('=== source_tier 证据化治理 ===', '(dry-run)' if dry else '')
    print(f'  修复前： A={before.get("A",0)} B={before.get("B",0)} C={before.get("C",0)}')
    print(f'  推导后： A={dist["A"]} B={dist["B"]} C={dist["C"]}')
    print(f'  需变更： {len(changes)} 条')
    print('  判定依据分布：')
    for b, n in basis_dist.most_common():
        print(f'    {n:>4}  {b}')
    if changes:
        print('  样例（前 8 条）：')
        for cid, old, new, b in changes[:8]:
            print(f'    {cid}: {old} -> {new}  ({b})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
