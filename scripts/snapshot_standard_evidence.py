#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""标准取证快照器 —— 把「详情页原文」冻结成可离线机械比对的快照。

为什么需要它（20260811-04 立）：
  团标召回缺口是靠 ndls.org.cn（国家数字标准馆）枚举全表闭合的，但这带来一个新风险——
  **发现渠道与取证渠道同源**。枚举器解析出的日期/状态若解析错了，没有第二双眼睛。
  过去白名单（ttbz/std.samr/openstd/cssn/iso）的立意是「排除新闻站/公众号/聚合站/软文」，
  ndls 由**中国标准化研究院**主办（站脚版权声明 + service@cnis.ac.cn），与已在白名单的
  cssn.net.cn 同一主办单位，属一手题录库，按立意应当纳入。
  但「是权威源」不等于「解析对了」。所以纳入白名单的同时必须配上这一层：
  **登记表里的每个日期/状态断言，都要挂得住一份详情页原文快照，逐字机械比对。**
  枚举器若把「公布日期」当成「发布日期」，快照一比就现形。

用法：
  python scripts/snapshot_standard_evidence.py --url <ndls detail url> [...]
  python scripts/snapshot_standard_evidence.py --verify          # 只离线校验，不发请求
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_PATH = os.path.join(ROOT, 'ops', 'intel', 'standards-evidence-snapshots.json')
CST = timezone(timedelta(hours=8))

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')

# 允许做取证快照的主机（与 regression._STD_EVIDENCE_HOSTS 立意一致：一手题录/发布机构，
# 刻意不含新闻站/聚合站/厂商软文站）
SNAPSHOT_HOSTS = {'www.ndls.org.cn', 'ndls.org.cn'}


def _text_lines(html):
    t = re.sub(r'<script.*?</script>', '', html, flags=re.S)
    t = re.sub(r'<style.*?</style>', '', t, flags=re.S)
    t = re.sub(r'<[^>]+>', '\n', t)
    t = t.replace('&nbsp;', ' ').replace('&amp;', '&')
    return [x.strip() for x in t.split('\n') if x.strip()]


def _after(lines, label, maxgap=3):
    """取 label 之后最近的一个非标签值（详情页是「字段名/换行/值」的结构）。"""
    for i, x in enumerate(lines):
        if x.rstrip('：:') == label.rstrip('：:') or x == label:
            for j in range(i + 1, min(i + 1 + maxgap, len(lines))):
                v = lines[j].strip()
                if v and not v.endswith('：') and not v.endswith(':'):
                    return v
    return ''


def extract(html):
    """从 ndls 详情页原文抽取受控字段。抽不到一律留空，绝不猜。"""
    lines = _text_lines(html)
    out = {}

    # 标准号：<title> 形如 "T/CAMETA 40004-2021-协作机器人末端接口技术条件-国家标准馆..."
    m = re.search(r'<title>(.*?)</title>', html, flags=re.S)
    title = (m.group(1) if m else '').strip()
    tm = re.match(r'\s*([A-Z]+/[A-Z]+\s+[0-9.\-]+)\s*-\s*(.+?)\s*-\s*国家标准馆', title)
    if tm:
        out['std_no'] = tm.group(1).strip()
        out['name'] = tm.group(2).strip()

    # 状态：标准号那一行的紧邻上一行（详情页把「现行/废止」标在编号上方）
    if out.get('std_no'):
        for i, x in enumerate(lines):
            if x == out['std_no'] and i > 0 and lines[i - 1] in ('现行', '废止', '即将实施', '被代替'):
                out['status'] = lines[i - 1]
                break

    out['issued_at'] = _after(lines, '发布日期：')
    out['effective_at'] = _after(lines, '实施日期：')
    out['administered_by'] = _after(lines, '归口单位：')
    out['ics'] = _after(lines, 'ICS分类：')

    # 范围摘录：详情页把「本标准规定了…」直接排在实施日期之后
    scope = [x for x in lines if x.startswith('本标准规定了') or x.startswith('本文件规定了')]
    if scope:
        out['scope_excerpt'] = scope[0][:300]
    return out


def load_snaps():
    if os.path.exists(SNAP_PATH):
        with open(SNAP_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {'version': 1, 'note': '标准登记表的日期/状态断言必须挂得住这里的详情页原文快照', 'snapshots': {}}


def canonical_digest(rec):
    """对受控字段做稳定摘要，任何一个字段被事后改动都会变。"""
    keys = ('std_no', 'name', 'status', 'issued_at', 'effective_at', 'administered_by')
    payload = '|'.join(str(rec.get(k, '')) for k in keys)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]


def fetch(url):
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or '').lower()
    if host not in SNAPSHOT_HOSTS:
        raise SystemExit('拒绝：%s 不在取证快照主机白名单内' % host)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode('utf-8', 'replace')


def verify(snaps):
    """离线自校验：每条快照的 digest 必须与受控字段一致（防手改快照）。"""
    bad = []
    for k, rec in snaps.get('snapshots', {}).items():
        if canonical_digest(rec) != rec.get('digest'):
            bad.append(k)
        for must in ('std_no', 'name', 'status', 'issued_at', 'source_url', 'fetched_at'):
            if not rec.get(must):
                bad.append('%s(缺%s)' % (k, must))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', action='append', default=[])
    ap.add_argument('--verify', action='store_true')
    a = ap.parse_args()

    snaps = load_snaps()

    if a.verify and not a.url:
        bad = verify(snaps)
        if bad:
            print('❌ 快照自校验失败：%s' % bad)
            return 1
        print('✅ 快照自校验通过（%d 条）' % len(snaps.get('snapshots', {})))
        return 0

    for i, url in enumerate(a.url):
        if i:
            time.sleep(3)  # 礼貌闸
        html = fetch(url)
        rec = extract(html)
        if not rec.get('std_no'):
            print('⚠ 抽取失败（页面结构可能已变），跳过：%s' % url)
            continue
        rec['source_url'] = url
        rec['source_tier'] = '题录库（国家数字标准馆 ndls.org.cn，中国标准化研究院主办）'
        rec['fetched_at'] = datetime.now(CST).isoformat(timespec='seconds')
        rec['digest'] = canonical_digest(rec)
        snaps['snapshots'][rec['std_no']] = rec
        print('✅ %s %s | %s | 发布 %s 实施 %s | %s'
              % (rec['std_no'], rec.get('name'), rec.get('status'),
                 rec.get('issued_at'), rec.get('effective_at'), rec.get('administered_by')))

    bad = verify(snaps)
    if bad:
        print('❌ 写入前自校验失败：%s' % bad)
        return 1
    os.makedirs(os.path.dirname(SNAP_PATH), exist_ok=True)
    with open(SNAP_PATH, 'w', encoding='utf-8') as f:
        json.dump(snaps, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('已写入 %s（共 %d 条快照）' % (SNAP_PATH, len(snaps['snapshots'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
