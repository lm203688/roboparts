#!/usr/bin/env python3
"""
spec_declare_cli.py — 规格书文本 → 机械接口 partial 声明（批量提案）

与 functions/api/spec_declare.js 同源正则逻辑（确定性，不调用 LLM）。
输出「提案」JSON（status=partial），**不自动写入 entities.json**——
升 declared 需人工补官域 source_url 并逐字核对（遵守 AI 不编纪律）。

用法：
  # 单文件
  python scripts/spec_declare_cli.py specs/onrobot_2fg7.txt
  # 批量 → 写出 proposals/onrobot_2fg7.patch.json
  python scripts/spec_declare_cli.py specs/*.txt --out proposals/
  # 管道
  cat specs/x.txt | python scripts/spec_declare_cli.py -

AI 不编纪律：本脚本永远产出 status="partial"，且 source_url 留空。
"""
import argparse
import json
import re
import sys
from pathlib import Path

ISO_RE = re.compile(r'ISO\s*9409[-\s]*1[-\s](\d{2,3})[-\s](\d{1,2})[-\s]M(\d{1,2})', re.I)
A_RE = re.compile(r'(?:^|[\s,，、;；])(A\d{2,3})[-\s](\d{1,2})[-\s]M(\d{1,2})', re.I)
PCD_RE = re.compile(r'(?:PCD|节圆直径|节圆|pitch\s*circle\s*diameter)[\s:：]*?(\d{2,3})\s*(?:mm)?', re.I)
HOLE_RE = re.compile(r'(\d{1,2}|[一二三四五六七八九十])\s*(?:孔|holes|bolts|mounting\s*holes)', re.I)
THR_RE = re.compile(r'M(\d{1,2})', re.I)
CN_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def parse_spec(text: str):
    cands = []
    for m in ISO_RE.finditer(text):
        pcd, holes, thr = int(m.group(1)), int(m.group(2)), 'M' + m.group(3)
        cands.append(_mk(pcd, holes, thr, 0.95, ['iso_code'], m.group(0).strip()))
    if not cands:
        for m in A_RE.finditer(text):
            pcd = int(m.group(1)[1:])
            cands.append(_mk(pcd, int(m.group(2)), 'M' + m.group(3), 0.9, ['a_notation'], m.group(0).strip()))
    if not cands:
        pm, hm, tm = PCD_RE.search(text), HOLE_RE.search(text), THR_RE.search(text)
        if pm and hm and tm:
            pcd = int(pm.group(1))
            hraw = hm.group(1)
            holes = CN_NUM.get(hraw) if hraw in CN_NUM else int(hraw)
            thr = 'M' + tm.group(1)
            cands.append(_mk(pcd, holes, thr, 0.7, ['scattered_geometry'],
                              f'PCD {pcd} / {holes}孔 / {thr}'))
    seen, uniq = set(), []
    for c in cands:
        k = (c['pcd'], c['holes'], c['thread'])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(c)
    return uniq


def _mk(pcd, holes, thread, conf, rules, raw):
    return {
        'pcd': pcd, 'holes': holes, 'thread': thread,
        'iso_code': f'ISO 9409-1-{pcd}-{holes}-{thread}',
        'confidence': conf, 'rules': rules, 'raw': raw,
    }


def build_proposed(cands):
    if not cands:
        return None
    c = max(cands, key=lambda x: x['confidence'])
    iso = c['iso_code']
    return {
        'mechanical_interface': {
            'status': 'partial',
            'mount_type': 'flange',
            'standard': iso,
            'flange': None,
            'declared_note': f"AI 从规格书文本提取（{'+'.join(c['rules'])} 命中：{c['raw'] or iso}）。待人工以厂商官域 source_url 逐字核对孔位尺寸后，方可升 declared。",
            'source': '规格书文本 AI 正则提取（scripts/spec_declare_cli.py，2026-09-14）',
            'source_url': '',
            'confidence': c['confidence'],
            'registry_ref': '/api/mechanical_interfaces.json',
            'gap': 'source_url 官域出处待补；升 declared 前须核对 PCD/孔数/螺纹与厂商 Drawing 一致',
        }
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+', help='规格书 .txt/.md 路径，或用 - 读 stdin')
    ap.add_argument('--out', help='提案写出目录（默认打印到 stdout）')
    args = ap.parse_args()

    proposals = []
    for f in args.files:
        if f == '-':
            text = sys.stdin.read()
            name = 'stdin'
        else:
            p = Path(f)
            text = p.read_text(encoding='utf-8', errors='replace')
            name = p.stem
        cands = parse_spec(text)
        proposed = build_proposed(cands)
        rec = {'source': name, 'parsed': bool(cands), 'count': len(cands),
               'candidates': cands, 'proposed': proposed,
               'note': '确定性正则提取，不调用 LLM。status=partial，需人工补官域 source_url 后升 declared。'}
        proposals.append(rec)
        if args.out:
            outp = Path(args.out)
            outp.mkdir(parents=True, exist_ok=True)
            (outp / f'{name}.patch.json').write_text(
                json.dumps(rec, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'[{ "OK" if rec["parsed"] else "MISS" }] {name}: {len(cands)} 候选 → {outp / (name + ".patch.json")}', file=sys.stderr)
        else:
            print(json.dumps(rec, ensure_ascii=False, indent=2))

    if args.out:
        print(f'\n共 {len(proposals)} 份，{sum(1 for p in proposals if p["parsed"])} 份命中。提案为 partial，需人工核实后写入 entities.json。', file=sys.stderr)


if __name__ == '__main__':
    main()
