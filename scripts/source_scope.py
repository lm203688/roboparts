"""source_url 作用域判定 —— Tier 分级的单一真相源。

【20260809-09 · L1.70】为什么要有这个模块
--------------------------------------------------
`api/entities.json` 的 `meta.provenance_coverage.tier_definition` 是本仓自己写下的定义：

    A = 可点开复核的一手来源（官方规格书/标准文本/**带链接厂商文档**）
    B = 弱归因（厂商目录声明值、**官网首页，无原始链接**）
    C = 无溯源

也就是说「官网首页」按本仓定义就该是 B。这条规则**不是新提出的**：
`scripts/quality-baseline.json` 的 `_traceable_history` 2026-08-05 第 3 轮已明确写下

    「判级引入 scope 硬封顶：URL 若仅为厂商首页（如把 Maxon EC Flat 60 挂到
      maxongroup.com），无论响应多正常一律封顶 Tier B —— 该规则当场挤掉 8 条注水 Tier A」

但它当时只落在 `scripts/verify_vendor_sources.py` 里，且 scope 来自一张**手维护的
REGISTRY（entity_id -> scope）**，只覆盖登记过的 57 条。没登记的条目一律绕过。
于是同一种注水复发：今天全库仍有 88 条 `Tier A + 站点根 URL`，其中
`MOT-maxon-re25` 挂 `https://www.maxongroup.com` —— 与当年被点名的反例是同一个域名、
同一种错法。**规则修过一次却没变成闸门，等于没修。**

判据必须从 URL 形状与实体名**推导**，不能靠人去登记，否则覆盖面不会自己生长
（同 L1.69 教训：一张手维护的名词表决定"看不看"，新增的就永远看不到）。

判定规则
--------------------------------------------------
deep   : URL 带路径/查询串 —— 指向具体页面，可作 Tier A
entity : URL 是站点根，但该站点主体**就是这个实体本身**（项目主页/标准组织自身），
         首页即其一手发布地，可作 Tier A。判据：实体名去掉域名主体后无残留标识。
vendor : URL 是站点根，但实体名在域名主体之外**还有型号/系列标识**（残留 token）——
         首页证明得了这家厂商存在，证明不了这个型号的任何一个参数。封顶 Tier B。

反例守护（必须保持成立，见 regression L1.70 自测）：
  · maxon RE 25 + maxongroup.com   -> vendor（残留 're','25'）  当年点名的注水形态
  · Octo        + octo-models.github.io -> entity（无残留）     项目自己的主页
"""
import re
from urllib.parse import urlparse

# 域名里不承载"主体身份"的通用词：留着会把任何名字都误配成同一主体
GENERIC_DOMAIN_TOKENS = {
    'www', 'com', 'cn', 'org', 'net', 'io', 'tech', 'ai', 'co', 'jp', 'tw',
    'de', 'dev', 'github', 'gov', 'edu', 'inc', 'group', 'robotics', 'robot',
    'sig', 'tel', 'berlin', 'stanford', 'cs',
}


def _domain_tokens(netloc):
    return [t for t in re.split(r'[.\-]', (netloc or '').lower())
            if t and t not in GENERIC_DOMAIN_TOKENS]


def _name_tokens(name):
    """取实体名里的**拉丁标识 token**（型号/系列）。

    中文描述性词（如「六维力传感器」）不作型号标识，否则每条中文名都会被判残留。
    真正决定"首页够不够"的是有没有型号号段。
    """
    name = re.sub(r'[（(].*?[)）]', ' ', name or '')
    toks = re.split(r'[\s\-_/·,，、+]+', name.lower())
    out = []
    for t in toks:
        t = t.strip()
        if not t:
            continue
        if re.fullmatch(r'[\u4e00-\u9fff]+', t):   # 纯中文：描述词，不算型号
            continue
        out.append(t)
    return out


def scope_of(entity):
    """返回 'deep' | 'entity' | 'vendor' | None（无 source_url）。"""
    url = (entity.get('source_url') or '').strip()
    if not url:
        return None
    p = urlparse(url)
    if (p.path or '').strip('/') or p.query:
        return 'deep'
    dts = _domain_tokens(p.netloc)
    nts = _name_tokens(entity.get('name', ''))
    residual = [t for t in nts if not any(t in dt or dt in t for dt in dts)]
    return 'vendor' if residual else 'entity'


def tier_cap(entity):
    """该条目按出处形状允许的最高 tier。"""
    return 'B' if scope_of(entity) == 'vendor' else 'A'


def violations(entities):
    """全库扫描：标了 Tier A 但出处形状只够 B 的条目。"""
    out = []
    for e in entities:
        if e.get('source_tier') == 'A' and tier_cap(e) == 'B':
            out.append(e)
    return out
