#!/usr/bin/env python3
import json, re, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = json.load(open(os.path.join(ROOT, 'api', 'entities.json'), 'r', encoding='utf-8'))
paths_3d = set()
for e in data['entities']:
    text = json.dumps(e)
    for m in re.finditer(r'/3d/[^\s"\\]+', text):
        paths_3d.add(m.group(0))
print('3D paths found:')
for p in sorted(paths_3d):
    print('  ', p)
