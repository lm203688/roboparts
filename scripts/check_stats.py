import json

# Load entities
with open('api/entities.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
ents = data['entities']

# Count by category
cats = {}
for e in ents:
    c = e.get('category', 'unknown')
    cats[c] = cats.get(c, 0) + 1

# Print updated stats
print('Updated stats for data.js:')
for k, v in sorted(cats.items(), key=lambda x: -x[1]):
    print(f'    "{k}": {v},')
