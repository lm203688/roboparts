import json

with open('api/entities.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

fixed = 0
for e in data['entities']:
    mi = e.get('mechanical_interface', {})
    if mi.get('status') == 'not_applicable':
        mi['status'] = 'n_a'
        fixed += 1
        print('Fixed:', e['id'])

with open('api/entities.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Total fixed:', fixed)
