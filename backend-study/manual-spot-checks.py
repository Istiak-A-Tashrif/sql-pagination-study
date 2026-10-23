#!/usr/bin/env python3
"""Five quantities independently selected from raw records; no analysis import."""
from pathlib import Path
import json,statistics
B=Path(__file__).resolve().parent;raw=B/'results/raw'
load=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
c=[x['collection'] for x in load(raw/'collections.jsonl') if x['status']=='accepted'][-1]
a=[x for x in load(raw/'api.jsonl') if x['collection']==c]
checks=[json.loads(x) for x in (raw/f'correctness-{c}.txt').read_text().splitlines() if x.startswith('{')]
print('1. Largest independently counted product total:',next(x['counts']['products'] for x in checks if x['type']=='counts' and x['scale']==100000))
for i,v,m in [(2,'global','offset'),(3,'page_lateral','keyset')]:
 rows=[x for x in a if x.get('phase')=='measurement' and x.get('family')=='primary' and x['scale']==100000 and x['fraction']==.95 and x['variant']==v and x['method']==m]
 assert len(rows)==60;print(i,v,m,'service sum',sum(x['serviceMs'] for x in rows),'requests',len(rows),'mean',statistics.mean(x['serviceMs'] for x in rows))
p=[json.loads(x) for x in (raw/f'plans-{c}.txt').read_text().splitlines() if x.startswith('{')]
def walk(x):
 yield x
 for q in x.get('Plans',[]):yield from walk(q)
print('4. Product scan output in lateral deep-page plans:')
for m in ['offset','keyset']:
 root=next(x['plan'][0]['Plan'] for x in p if x['scale']==100000 and x['fraction']==.95 and x['limit']==25 and x['variant']=='page_lateral' and x['method']==m)
 print(m,[(x['Actual Rows'],x['Actual Loops']) for x in walk(root) if x.get('Relation Name')=='products'])
hits=[x for x in a if x.get('phase')=='measurement' and x['outcome']=='hit'];assert len(hits)==360
print('5. Measured cache hits:',len(hits),'database queries:',sum(x['dbMs'] is not None for x in hits))
