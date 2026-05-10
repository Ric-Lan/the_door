import json
from collections import Counter
with open('structure_v100.json', encoding='utf-8') as f:
    data = json.load(f)

prefixes = Counter()
for n in data['nodes']:
    path = n.get('file', '').replace('\\', '/').replace('//', '/')
    parts = path.split('/')
    for i, p in enumerate(parts):
        if p == 'the_door' and i + 2 < len(parts):
            prefixes[parts[i+1] + '/' + parts[i+2]] += 1
            break

print('Node distribution by module (top 20):')
for k, v in sorted(prefixes.items(), key=lambda x: -x[1])[:20]:
    print(f'  {k}: {v}')

# Also show unique node types
types = Counter(n['type'] for n in data['nodes'])
print('\nNode types:')
for k, v in sorted(types.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')

# Show some entry point nodes
entry_nodes = [t for t in data['topology'] if t.get('is_entry_point')]
print(f'\nEntry point nodes: {len(entry_nodes)}')
for t in sorted(entry_nodes, key=lambda x: -x.get('out_degree', 0))[:15]:
    node = next((n for n in data['nodes'] if n['node_id'] == t['node_id']), {})
    print(f"  {t['node_id']} (out={t['out_degree']}, in={t['in_degree']})")
