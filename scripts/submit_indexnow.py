# -*- coding: utf-8 -*-
"""
submit_indexnow.py —— 向 IndexNow 提交 URL，让搜索引擎立即抓取新增/更新页面。

【20260805-17 修复背景】
  仓库里早就有 indexnow-key.txt，但 IndexNow 协议要求密钥校验文件必须命名为
  `{key}.txt`（即 roboparts2026indexnow.txt）并放在站点根目录。实测线上
  /roboparts2026indexnow.txt 返回 404、/indexnow-key.txt 返回 200 ——
  文件名不符合协议，任何提交都会因密钥校验失败被静默拒绝。
  与 _routes.json 白名单、agent-discovery 计数同型：**配置写了，但从未生效。**

用法：
  python scripts/submit_indexnow.py            # 提交 sitemap 中的全部 URL
  python scripts/submit_indexnow.py --new      # 仅提交本轮新增内容页
"""
import io
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = 'roboparts.cc'
KEY = 'roboparts2026indexnow'
KEY_LOCATION = 'https://%s/%s.txt' % (HOST, KEY)
# IndexNow 是共享协议：提交给任一端点会同步到其余参与方（Bing / Yandex / Seznam / Naver 等）
ENDPOINTS = ['https://api.indexnow.org/indexnow', 'https://www.bing.com/indexnow']


def sitemap_urls():
    xml = io.open(os.path.join(ROOT, 'sitemap.xml'), encoding='utf-8').read()
    return re.findall(r'<loc>([^<]+)</loc>', xml)


def new_content_urls():
    """本轮新上线的内容页：文章 + 索引 + 长尾落地页。"""
    urls = ['https://%s/articles/' % HOST, 'https://%s/iso-9409-flange' % HOST,
            'https://%s/llms.txt' % HOST, 'https://%s/sitemap.xml' % HOST]
    for f in sorted(os.listdir(os.path.join(ROOT, 'articles'))):
        if f.endswith('.html') and f != 'index.html':
            urls.append('https://%s/articles/%s' % (HOST, f[:-5]))
    return urls


def verify_key():
    # 必须带常规 UA：Cloudflare 对 Python-urllib 默认 UA 返回 403，
    # 曾导致本函数误判「密钥文件未部署」而中止提交（实际 curl 取到 200）。
    req = urllib.request.Request(KEY_LOCATION, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; RoboParts-IndexNow/1.0)'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode('utf-8', 'ignore').strip()
        ok = (r.status == 200 and body == KEY)
        print('密钥校验文件 %s → HTTP %d，内容%s' % (KEY_LOCATION, r.status, '匹配' if body == KEY else '不匹配: %r' % body[:40]))
        return ok
    except Exception as e:
        print('密钥校验文件不可访问：%s' % e)
        return False


def submit(urls):
    payload = json.dumps({
        'host': HOST, 'key': KEY, 'keyLocation': KEY_LOCATION, 'urlList': urls,
    }, ensure_ascii=False).encode('utf-8')
    results = []
    for ep in ENDPOINTS:
        req = urllib.request.Request(
            ep, data=payload,
            headers={'Content-Type': 'application/json; charset=utf-8',
                     'User-Agent': 'RoboParts-IndexNow/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                results.append((ep, r.status, r.read().decode('utf-8', 'ignore')[:120]))
        except Exception as e:
            code = getattr(e, 'code', None)
            body = ''
            try:
                body = e.read().decode('utf-8', 'ignore')[:160]
            except Exception:
                pass
            results.append((ep, code or 'ERR', body or str(e)[:120]))
    return results


def main():
    only_new = '--new' in sys.argv
    urls = new_content_urls() if only_new else sitemap_urls()
    # IndexNow 单次上限 10000，且不接受非本站 host
    urls = [u for u in dict.fromkeys(urls) if u.startswith('https://%s/' % HOST)][:10000]
    print('准备提交 %d 个 URL（%s）' % (len(urls), '仅新增内容页' if only_new else '全站 sitemap'))

    if not verify_key():
        print('❌ 密钥校验未通过，提交必然被拒。请确认 %s.txt 已部署到站点根目录。' % KEY)
        return 1

    for ep, status, body in submit(urls):
        # 200/202 = 已接受；400 = 请求格式错；403 = 密钥无效；422 = URL 不属于该 host；429 = 频率超限
        flag = '✅' if status in (200, 202) else '⚠️'
        print('%s %s → %s %s' % (flag, ep, status, body.strip()))
    print('\n提交完成。IndexNow 为异步协议，返回 200/202 仅代表已受理，'
          '实际抓取由各搜索引擎自行调度（通常数分钟至数天）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
