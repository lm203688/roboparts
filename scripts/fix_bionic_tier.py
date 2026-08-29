#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(ROOT, 'api', 'entities.json')

with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

changed = 0
for e in data['entities']:
    if e.get('category') == 'bionic_mechanisms' and e.get('source_tier') == 'B':
        e['source_tier'] = 'A'
        e['source_tier_basis'] = 'entity_homepage: roboparts.cc hosts bionic design files'
        changed += 1
        print('  Updated %s to tier A' % e['id'])

print('Total changed: %d' % changed)

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
