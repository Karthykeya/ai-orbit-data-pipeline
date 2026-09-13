import json
from collections import defaultdict

records = json.load(open('data/mcp_servers.json'))
seen = defaultdict(list)
for r in records:
    key = (r['name'].strip().lower(), r['metadata']['vendor'].strip().lower())
    seen[key].append(r)

for key, recs in seen.items():
    if len(recs) > 1:
        print('DUPLICATE PAIR:', key)
        for r in recs:
            print('  id:', r['id'])
            print('  url:', r['url'])
            print('  source:', r['source'])


