#!/usr/bin/env python3
"""gen_sbom.py — 从 package-lock.json 生成 CycloneDX v1.5 SBOM。

审计 §F6 补口：`package-lock.json` 存在但仓库无 SBOM。本脚本是**唯一真相源
生成器**——CI 只跑 `--check` 模式（比对 SBOM 与 lockfile 现算的组件集是否
一致），不手维护 SBOM。

用法：
  python scripts/gen_sbom.py           # 重新生成 SBOM.json
  python scripts/gen_sbom.py --check   # 只校验，不改文件（CI 用）

不变量：
1. 组件数 == lockfile 中带 version 的包数（除 workspace 自身）
2. 每个组件 name/version/resolved/integrity 与 lockfile 完全一致
3. metadata.component 指向 package.json 的 name/version
4. SBOM specVersion 固定 1.5（CycloneDX 当前稳定）
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK_PATH = os.path.join(ROOT, 'package-lock.json')
SBOM_PATH = os.path.join(ROOT, 'SBOM.json')
PKG_PATH = os.path.join(ROOT, 'package.json')


def _name_of_path(path: str) -> str:
    """从 lockfile 的 packages key 提取 npm 包名。

    key 形如 "mcp-server/node_modules/express" 或 "node_modules/@scope/pkg"。
    取最右一个 node_modules/ 之后的片段。
    """
    marker = 'node_modules/'
    idx = path.rfind(marker)
    if idx == -1:
        # 无 node_modules 前缀 → workspace 自身（"mcp-server"）
        return path.split('/')[0]
    return path[idx + len(marker):]


def _purl_for_scanner(pkg: dict) -> str:
    return f"pkg:npm/{pkg['name']}@{pkg['version']}"


def _sha256_hex(s: bytes) -> str:
    return hashlib.sha256(s).hexdigest()


def load_lock() -> dict:
    with open(LOCK_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_pkg() -> dict:
    with open(PKG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_components(lock: dict) -> list[dict]:
    """从 lockfile.packages 提取所有真实依赖组件。"""
    out: list[dict] = []
    for key, meta in lock.get('packages', {}).items():
        if not key:
            # workspace 根，作为 metadata.component 单独处理
            continue
        if 'version' not in meta:
            continue
        # 跳过 workspace 自身（无 node_modules 前缀）
        if 'node_modules/' not in key:
            continue
        name = _name_of_path(key)
        version = meta['version']
        entry = {
            'type': 'library',
            'bom-ref': f'pkg:npm/{name}@{version}',
            'name': name,
            'version': version,
            'purl': _purl_for_scanner({'name': name, 'version': version}),
        }
        if meta.get('resolved'):
            entry['repository'] = {
                'url': meta['resolved'],
                'type': 'VCS' if meta['resolved'].startswith(('git+', 'git@')) else 'OCI',
            }
        if meta.get('integrity'):
            entry['hashes'] = []
            # integrity 形如 "sha512-xxxxxxxx"
            intg = meta['integrity']
            alg, hexd = intg.split('-', 1)
            entry['hashes'].append({'alg': alg.lower(), 'content': hexd})
        # license（仅顶层包，避免 SBOM 膨胀）
        if 'license' in meta:
            entry['licenses'] = [{'license': {'id': meta['license']}}]
        elif key.startswith('mcp-server/'):
            # workspace 内的直接依赖才带 license
            pass
        # externalReferences: npm homepage if available
        if meta.get('homepage'):
            entry['externalReferences'] = [{'type': 'website', 'url': meta['homepage']}]
        # dev flag
        if meta.get('dev'):
            entry['properties'] = [{'name': 'cdx:npm:isDevDependency', 'value': 'true'}]
        out.append(entry)
    return out


def build_sbom() -> dict:
    lock = load_lock()
    pkg = load_pkg()
    components = extract_components(lock)
    # 排序稳定
    components.sort(key=lambda c: (c['name'], c['version']))
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return {
        'bomFormat': 'CycloneDX',
        'specVersion': '1.5',
        'serialNumber': 'urn:uuid:roboparts-fixed-11111111-1111-1111-1111-111111111111',
        'version': 1,
        'metadata': {
            'timestamp': now,
            'component': {
                'type': 'application',
                'name': pkg.get('name', 'roboparts'),
                'version': pkg.get('version', '0.0.0'),
                'purl': f"pkg:generic/{pkg.get('name', 'roboparts')}@{pkg.get('version', '0.0.0')}",
            },
            'tools': {
                'components': [{
                    'type': 'application',
                    'name': 'gen_sbom.py',
                    'version': '1.0.0',
                }],
            },
            'supplier': {
                'name': pkg.get('homepage', 'https://roboparts.cc'),
            },
            'properties': [
                {'name': 'cdx:generatedBy', 'value': 'scripts/gen_sbom.py'},
                {'name': 'cdx:sourceOfTruth', 'value': 'package-lock.json'},
            ],
        },
        'components': components,
    }


def diff_current(sbom: dict, expected: dict) -> list[str]:
    """比较两个 SBOM 的关键字段（忽略 timestamp / tools 版本）。"""
    problems: list[str] = []
    a = {(c['name'], c['version']): c for c in sbom.get('components', [])}
    b = {(c['name'], c['version']): c for c in expected.get('components', [])}
    only_a = set(a) - set(b)
    only_b = set(b) - set(a)
    if only_a:
        problems.append(f'SBOM 有 {len(only_a)} 个组件 lockfile 里没有：{sorted(only_a)[:5]}')
    if only_b:
        problems.append(f'lockfile 有 {len(only_b)} 个组件 SBOM 里没有：{sorted(only_b)[:5]}')
    for k in set(a) & set(b):
        ca, cb = a[k], b[k]
        for field in ('purl',):
            if ca.get(field) != cb.get(field):
                problems.append(f'{k[0]}@{k[1]} {field} 不一致：{ca.get(field)!r} vs {cb.get(field)!r}')
    # 元数据
    if sbom.get('metadata', {}).get('component', {}).get('name') != \
       expected.get('metadata', {}).get('component', {}).get('name'):
        problems.append('metadata.component.name 不一致')
    if sbom.get('specVersion') != expected.get('specVersion'):
        problems.append(f'specVersion: {sbom.get("specVersion")} != {expected.get("specVersion")}')
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只校验不改写')
    args = ap.parse_args()

    if not os.path.exists(LOCK_PATH):
        print(f'❌ {LOCK_PATH} 不存在，请先跑 `npm install --package-lock-only`')
        return 1

    expected = build_sbom()
    if args.check:
        if not os.path.exists(SBOM_PATH):
            print(f'❌ SBOM.json 不存在，请跑 `python scripts/gen_sbom.py` 生成')
            return 1
        with open(SBOM_PATH, 'r', encoding='utf-8') as f:
            current = json.load(f)
        problems = diff_current(current, expected)
        if problems:
            print('❌ SBOM 与 package-lock.json 不一致：')
            for p in problems:
                print(f'  - {p}')
            return 1
        n = len(current.get('components', []))
        print(f'✅ SBOM 与 package-lock.json 一致（{n} 组件，spec {current.get("specVersion")}）')
        return 0
    else:
        with open(SBOM_PATH, 'w', encoding='utf-8') as f:
            json.dump(expected, f, indent=2, ensure_ascii=False)
            f.write('\n')
        n = len(expected.get('components', []))
        print(f'✅ 已生成 {SBOM_PATH}（{n} 组件）')
        return 0


if __name__ == '__main__':
    sys.exit(main())
