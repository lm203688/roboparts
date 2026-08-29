# -*- coding: utf-8 -*-
"""生成 RoboParts 站点图标（favicon.svg / favicon.ico / apple-touch-icon.png）。

为什么要有这个脚本：
  2026-08-07 21 点巡检发现 —— 全站 27 个 HTML 里只有 4 个声明了图标，
  且用的是 emoji data-URI（`<link rel=icon href="data:image/svg+xml,...🤖">`）。
  两个后果都是真的、可验证的：
    1. `https://roboparts.cc/favicon.ico` 线上 **404**（浏览器按惯例必发这个请求）；
    2. Google / Bing 的 SERP 图标抓取要求图标是**可抓取的文件 URL**，
       data: URI 不被采用 → 搜索结果里我们一直显示的是默认地球图标。
  对一个主要靠搜索与 GEO 曝光的 B2B 目录站，这是免费且立刻可兑现的可信度修复。

刻意不引第三方库（本机无 PIL），全部用 zlib + struct 手写 PNG / ICO，
避免为一个图标给构建链新增依赖。
"""

import binascii
import os
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BG = (0x0b, 0x10, 0x20)      # --bg  站点底色
ACC = (0x37, 0xe0, 0xa6)     # --acc 站点强调色
SS = 4                       # 超采样倍数（抗锯齿）


def _rounded_rect_a(x, y, n, radius):
    """点 (x,y) 在边长 n、圆角 radius 的圆角方内则返回 1。"""
    rx = min(x, n - 1 - x)
    ry = min(y, n - 1 - y)
    if rx >= radius or ry >= radius:
        return 1
    dx, dy = radius - rx, radius - ry
    return 1 if dx * dx + dy * dy <= radius * radius else 0


def render(n):
    """渲染 n×n RGBA 像素（bytes）。法兰环 + 4 个螺栓孔 + 中心轴孔。"""
    m = n * SS
    cx = cy = (m - 1) / 2.0
    r_out = 0.355 * m
    r_in = 0.205 * m
    r_bolt_ring = 0.280 * m
    r_bolt = 0.048 * m
    r_hub = 0.088 * m
    radius = 0.225 * m

    bolts = []
    for i in range(4):
        import math
        a = math.pi / 4 + i * math.pi / 2
        bolts.append((cx + r_bolt_ring * math.cos(a),
                      cy + r_bolt_ring * math.sin(a)))

    # 先在超采样网格上做二值判定，再降采样成 alpha —— 等效抗锯齿
    acc_hits = [[0] * n for _ in range(n)]
    bg_hits = [[0] * n for _ in range(n)]
    for sy in range(m):
        y = sy
        row_acc = acc_hits[sy // SS]
        row_bg = bg_hits[sy // SS]
        dy = y - cy
        for sx in range(m):
            if not _rounded_rect_a(sx, sy, m, radius):
                continue
            row_bg[sx // SS] += 1
            dx = sx - cx
            d2 = dx * dx + dy * dy
            on = (r_in * r_in <= d2 <= r_out * r_out) or (d2 <= r_hub * r_hub)
            if on:
                for bx, by in bolts:
                    if (sx - bx) ** 2 + (sy - by) ** 2 <= r_bolt * r_bolt:
                        on = False
                        break
            if on:
                row_acc[sx // SS] += 1

    tot = SS * SS
    out = bytearray()
    for y in range(n):
        for x in range(n):
            a_cov = bg_hits[y][x] / tot          # 背景（含圆角）覆盖率
            f_cov = acc_hits[y][x] / tot         # 前景覆盖率
            if a_cov == 0:
                out += bytes((0, 0, 0, 0))
                continue
            t = 0.0 if a_cov == 0 else min(1.0, f_cov / a_cov)
            rgb = tuple(int(round(BG[i] * (1 - t) + ACC[i] * t)) for i in range(3))
            out += bytes((rgb[0], rgb[1], rgb[2], int(round(a_cov * 255))))
    return bytes(out)


def png_bytes(n, rgba):
    """手写最小合规 PNG（RGBA8，filter=0）。"""
    raw = bytearray()
    stride = n * 4
    for y in range(n):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        c = tag + data
        return (struct.pack('>I', len(data)) + c
                + struct.pack('>I', binascii.crc32(c) & 0xffffffff))

    ihdr = struct.pack('>IIBBBBB', n, n, 8, 6, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
            + chunk(b'IEND', b''))


def ico_bytes(pngs):
    """PNG-in-ICO（Vista+ 与全部现代浏览器均支持）。pngs: [(size, data)]"""
    head = struct.pack('<HHH', 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, body = b'', b''
    for size, data in pngs:
        entries += struct.pack('<BBBBHHII',
                               size if size < 256 else 0,
                               size if size < 256 else 0,
                               0, 0, 1, 32, len(data), offset)
        offset += len(data)
        body += data
    return head + entries + body


SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="RoboParts">
  <title>RoboParts</title>
  <rect width="64" height="64" rx="14.4" fill="#0b1020"/>
  <g fill="#37e0a6">
    <path fill-rule="evenodd" d="M32 9.28a22.72 22.72 0 1 0 0 45.44 22.72 22.72 0 0 0 0-45.44Zm0 9.6a13.12 13.12 0 1 1 0 26.24 13.12 13.12 0 0 1 0-26.24Z"/>
    <circle cx="32" cy="32" r="5.63"/>
  </g>
  <g fill="#0b1020">
    <circle cx="44.67" cy="44.67" r="3.07"/><circle cx="19.33" cy="44.67" r="3.07"/>
    <circle cx="19.33" cy="19.33" r="3.07"/><circle cx="44.67" cy="19.33" r="3.07"/>
  </g>
</svg>
'''


def main():
    sizes = [16, 32, 48]
    pngs = [(s, png_bytes(s, render(s))) for s in sizes]
    with open(os.path.join(ROOT, 'favicon.ico'), 'wb') as f:
        f.write(ico_bytes(pngs))
    with open(os.path.join(ROOT, 'apple-touch-icon.png'), 'wb') as f:
        f.write(png_bytes(180, render(180)))
    with open(os.path.join(ROOT, 'favicon.svg'), 'w', encoding='utf-8') as f:
        f.write(SVG)
    for name in ('favicon.ico', 'apple-touch-icon.png', 'favicon.svg'):
        p = os.path.join(ROOT, name)
        print(f'  ✅ {name:24s} {os.path.getsize(p):>7d} B')


if __name__ == '__main__':
    main()
