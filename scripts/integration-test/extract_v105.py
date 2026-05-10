import sys, json
sys.path.insert(0, 'the_door/src')
from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.topology.topology_analyzer import TopologyAnalyzer

codebase_path = r'C:\Users\Ric\Desktop\test-targets\the-door-v105'
extractor = ASTExtractor()
result = extractor.extract(codebase_path)

analyzer = TopologyAnalyzer()
topology = analyzer.analyze(result.nodes, result.edges)

output = {
    'files': [{'path': f.path, 'language': f.language} for f in result.files],
    'nodes': [
        {'node_id': n.node_id, 'type': n.type, 'name': n.name,
         'file': n.file, 'language': n.language,
         'decorators': n.decorators, 'parameters': n.parameters,
         'return_type': n.return_type, 'docstring': n.docstring,
         'comments': n.comments}
        for n in result.nodes
    ],
    'edges': [{'from': e.from_node, 'to': e.to_node, 'type': e.type} for e in result.edges],
    'topology': [
        {'node_id': t.node_id, 'in_degree': t.in_degree, 'out_degree': t.out_degree,
         'topology_rank': t.topology_rank, 'is_entry_point': t.is_entry_point,
         'batch_assignment': t.batch_assignment}
        for t in topology.entries
    ],
    'analyzed_files': [f.path for f in result.files],
}
with open('structure_v105.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)
print(f'files: {len(result.files)}, nodes: {len(result.nodes)}, edges: {len(result.edges)}')
print('Saved structure_v105.json')
