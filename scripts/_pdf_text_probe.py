# -*- coding: utf-8 -*-
"""一次性取证辅助：把 PDF 的 FlateDecode 流解压后抽出文本字面量，用于逐字核对厂商手册原文。

不入产品链路，仅供人工采编时自证「我读到的原文确实来自这份 PDF」。
用法：python scripts/_pdf_text_probe.py <pdf> <关键词> [关键词...]
"""
import hashlib
import re
import sys
import zlib


def extract(path):
    raw = open(path, 'rb').read()
    sha = hashlib.sha256(raw).hexdigest()
    chunks = []
    for m in re.finditer(rb'stream\r?\n', raw):
        s = m.end()
        e = raw.find(b'endstream', s)
        if e < 0:
            continue
        try:
            chunks.append(zlib.decompress(raw[s:e]))
        except Exception:
            continue
    blob = b'\n'.join(chunks)
    lits = re.findall(rb'\(([^()\\]{1,300})\)', blob)
    text = b' '.join(lits).decode('latin-1')
    # 部分 PDF 用 UTF-16BE 写文本字面量，latin-1 解出来会夹 NUL；一并抹掉
    text = text.replace('\x00', '')
    text = re.sub(r'\s+', ' ', text)
    return sha, len(raw), len(blob), text


def compact(s):
    """去掉所有空白，用于绕开 PDF 逐字排版导致的字间空格。"""
    return re.sub(r'\s+', '', s)


def main():
    if len(sys.argv) < 3:
        raise SystemExit('用法: python scripts/_pdf_text_probe.py <pdf> <关键词>...')
    sha, size, inflated, text = extract(sys.argv[1])
    print('sha256=%s size=%d inflated=%d textlen=%d' % (sha, size, inflated, len(text)))
    ctext = compact(text)
    for kw in sys.argv[2:]:
        ckw = compact(kw)
        hits = [m.start() for m in re.finditer(re.escape(ckw), ctext)][:3]
        print('KW %r -> %s' % (kw, hits))
        for i in hits:
            print('   >> ' + ctext[max(0, i - 260):i + 380])


if __name__ == '__main__':
    main()
