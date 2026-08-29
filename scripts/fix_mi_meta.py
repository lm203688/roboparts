import json

with open('api/entities.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

ents = data['entities']
mi_ents = [e for e in ents if e.get('mechanical_interface')]

stat = {}
for e in mi_ents:
    s = e['mechanical_interface'].get('status', 'missing')
    stat[s] = stat.get(s, 0) + 1

applicable = stat.get('declared', 0) + stat.get('partial', 0) + stat.get('not_declared', 0)
declared = stat.get('declared', 0)
fill_pct = round(declared / applicable * 100, 2) if applicable > 0 else 0

new_cov = {
    "schema_version": "1.0.0",
    "registry": "/api/mechanical_interfaces.json",
    "applicable": applicable,
    "not_applicable": stat.get('n_a', 0),
    "declared": declared,
    "partial": stat.get('partial', 0),
    "not_declared": stat.get('not_declared', 0),
    "fill_pct": fill_pct,
    "note": "机械互换维度基线。fill_pct 为已获得厂商声明的比例；not_declared 为显式缺口（可被 agent 查询），非字段缺失。"
}

data['meta']['mechanical_interface_coverage'] = new_cov

with open('api/entities.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Updated meta.mechanical_interface_coverage:')
print(json.dumps(new_cov, indent=2, ensure_ascii=False))
