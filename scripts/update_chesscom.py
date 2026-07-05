import yaml
import copy

with open('sources/chesscom.yml', 'r') as f:
    spec = yaml.safe_load(f)

for table in spec['tables']:
    for col in table['columns']:
        name = col['name']
        if '__' in name:
            path_parts = name.split('__')
            col['expr'] = {
                'kind': 'path',
                'path': path_parts
            }

with open('sources/chesscom.yml', 'w') as f:
    yaml.dump(spec, f, default_flow_style=False, sort_keys=False)
