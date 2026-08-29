#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(encoding='utf-8')
import importlib.util, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('govern_source_tier', os.path.join(ROOT, 'scripts', 'govern_source_tier.py'))
gst = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gst)

data = json.load(open(os.path.join(ROOT, 'api', 'entities.json'), 'r', encoding='utf-8'))
bad = []
for e in data['entities']:
    tier, basis = gst.derive_tier(e)
    stored = e.get('source_tier', 'C')
    if stored != tier:
        bad.append((e['id'], stored, tier, basis))
print(f'Mismatched: {len(bad)}')
for eid, stored, computed, basis in bad:
    print(f'  {eid}: stored={stored} computed={computed} basis={basis}')
