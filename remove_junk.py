import json

path = 'data/raw/registry_pull.json'
records = json.load(open(path))

JUNK_VENDORS = {'samuelar2', 'badroobot'}

before = len(records)
cleaned = [r for r in records if r.get('vendor', '').strip().lower() not in JUNK_VENDORS]
after = len(cleaned)

json.dump(cleaned, open(path, 'w'), indent=2)
print(f'Removed {before - after} junk record(s). {before} -> {after} records remain.')
