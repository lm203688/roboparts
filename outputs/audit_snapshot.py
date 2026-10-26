from pathlib import Path
from collections import Counter
import json, re

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', 'node_modules', '.wrangler', '.deploy-staging', '.trae-html-share-packages'}
files = [p for p in ROOT.rglob('*') if p.is_file() and not any(x in SKIP for x in p.parts)]
root_html = sorted(ROOT.glob('*.html'))
api_json = sorted((ROOT / 'api').glob('*.json'))
functions = sorted((ROOT / 'functions').rglob('*.js'))
scripts = sorted((ROOT / 'scripts').glob('*'))
docs = sorted((ROOT / 'docs').rglob('*.md'))
entities_doc = json.loads((ROOT / 'api' / 'entities.json').read_text(encoding='utf-8'))
entities = entities_doc.get('entities', entities_doc if isinstance(entities_doc, list) else [])
cat = Counter(e.get('category', '<missing>') for e in entities)
quarantine = sum(bool(e.get('quarantine')) for e in entities)
source_tiers = Counter(e.get('source_tier', '<missing>') for e in entities)
confidence = Counter(e.get('confidence_tier', '<missing>') for e in entities)
mech = Counter((e.get('mechanical_interface') or {}).get('status', '<missing>') for e in entities)
asset_exts = {'.urdf', '.mjcf', '.step', '.stp', '.stl', '.scad', '.glb', '.usd', '.usdz'}
assets = [str(p.relative_to(ROOT)) for p in files if p.suffix.lower() in asset_exts]
html_stats = []
for p in root_html:
    t = p.read_text(encoding='utf-8')
    html_stats.append({
        'file': p.name,
        'bytes': p.stat().st_size,
        'lang': (re.search(r'<html[^>]+lang=["\']([^"\']+)', t, re.I) or [None, '<missing>'])[1],
        'shell_js': t.count('<script src="/_shell.js"'),
        'project_js': t.count('<script src="/rp-project.js"'),
        'analytics': '/api/analytics/events' in t,
        'legacy_nav': '<nav' in t.lower(),
        'inline_script_bytes': sum(len(x.encode('utf-8')) for x in re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', t, re.I | re.S)),
        'external_cdn': sorted(set(re.findall(r'https://(?:cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com)[^"\'\s<]+', t))),
        'sri': 'integrity=' in t,
    })
result = {
    'snapshot_date': '2026-10-26',
    'file_count_excluding_heavy_dirs': len(files),
    'root_html_pages': len(root_html),
    'api_json_files': len(api_json),
    'function_js_files': len(functions),
    'script_files_top_level': len(scripts),
    'docs_markdown_files': len(docs),
    'entities': len(entities),
    'categories': dict(cat.most_common()),
    'quarantined_entities': quarantine,
    'source_tiers': dict(source_tiers),
    'confidence_tiers': dict(confidence),
    'mechanical_interface_status': dict(mech),
    'assets': assets,
    'html': html_stats,
    'html_summary': {
        'shell_all_pages': all(x['shell_js'] >= 1 for x in html_stats),
        'project_all_pages': all(x['project_js'] >= 1 for x in html_stats),
        'pages_with_analytics': sum(x['analytics'] for x in html_stats),
        'pages_zh_cn': sum(x['lang'] == 'zh-CN' for x in html_stats),
        'pages_with_legacy_nav': sum(x['legacy_nav'] for x in html_stats),
        'pages_with_cdn': sum(bool(x['external_cdn']) for x in html_stats),
        'pages_with_sri': sum(x['sri'] for x in html_stats),
        'largest_pages': sorted([{'file': x['file'], 'bytes': x['bytes'], 'inline_script_bytes': x['inline_script_bytes']} for x in html_stats], key=lambda x: x['bytes'], reverse=True)[:8],
        'duplicate_shell_tags': [x['file'] for x in html_stats if x['shell_js'] != 1],
        'duplicate_project_tags': [x['file'] for x in html_stats if x['project_js'] != 1],
    },
    'size_bytes': {
        'index_html': (ROOT / 'index.html').stat().st_size,
        'entities_json': (ROOT / 'api' / 'entities.json').stat().st_size,
        'data_js': (ROOT / 'data.js').stat().st_size,
        'shell_js_css': (ROOT / '_shell.js').stat().st_size + (ROOT / '_shell.css').stat().st_size,
    }
}
(ROOT / 'outputs' / 'audit_snapshot.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in {'html','categories','source_tiers','confidence_tiers','mechanical_interface_status'}}, ensure_ascii=False, indent=2))
print('categories=', dict(cat.most_common()))
print('mechanical=', dict(mech))
