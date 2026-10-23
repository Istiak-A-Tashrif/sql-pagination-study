#!/usr/bin/env python3
"""Audit and summarize the extension collection. Only a fully accepted collection is analyzed."""
from pathlib import Path
import json,collections,statistics,hashlib
import numpy as np
X=Path(__file__).resolve().parent;RAW=X/'results/raw';OUT=X/'results/derived';OUT.mkdir(parents=True,exist_ok=True)
read=lambda n:[json.loads(l) for l in (RAW/n).read_text().splitlines() if l.strip()]
accepted=[x for x in read('collections.jsonl') if x['status']=='accepted'];assert len(accepted)==1,'need exactly one accepted collection'
col=accepted[0]['collection'];manifest=json.loads((X/'manifest.json').read_text())
assert hashlib.sha256((X/'manifest.json').read_bytes()).hexdigest()==accepted[0]['manifest_sha256'],'manifest changed after collection'
requests=[x for x in read('requests.jsonl') if x['collection']==col];api={x['id']:x for x in read('api.jsonl') if 'error' not in x}
trials=[x for x in read('trials.jsonl') if x['collection']==col]
assert len(trials)==manifest['counts']['trials']==1260
meas=[x for x in requests if x['phase']=='measurement'];assert len(meas)==manifest['counts']['measured_requests']
assert all(x['id'] in api for x in requests),'request without API provenance'
assert not [x for x in read('api.jsonl') if 'error' in x],'API errors present'
# Equivalence: every design/method/cursor mode must return identical rows for the same schema and window.
digests=collections.defaultdict(set)
for x in requests:digests[(x['schema'],x['offset'],x['limit'])].add(x['rowDigest'])
assert all(len(v)==1 for v in digests.values()),'row digest mismatch within a window'
# s100000 and noidx100000 hold identical data, so their windows must also agree.
for off in {k[1] for k in digests}:
 assert digests[('s100000',off,25)]==digests[('noidx100000',off,25)] if ('noidx100000',off,25) in digests and ('s100000',off,25) in digests else True
rng=np.random.default_rng(20261022)
def ci(v):
 v=np.array(v,float);return [float(v.mean()),*map(float,np.percentile(v[rng.integers(0,len(v),(10000,len(v)))].mean(axis=1),[2.5,97.5]))]
key=lambda c:(c['exp'],c['schema'],c['api'],c['variant'],c['method'],c['cursor'],c['fraction'],c['limit'])
by=collections.defaultdict(lambda:collections.defaultdict(list))
for t in trials:by[key(t)][t['run']]=[]
for x in meas:
 a=api[x['id']];by[key(x)][x['run']].append((a['serviceMs'],a['dbMs'],a['cursorMs'] or 0.0,x['clientMs']))
summary=[]
for k,runs in by.items():
 assert len(runs)==20 and all(len(v)==3 for v in runs.values()),k
 m=[[statistics.mean(q[i] for q in v) for i in range(4)] for v in runs.values()]
 summary.append(dict(zip(['exp','schema','api','variant','method','cursor','fraction','limit'],k),n=20,service=ci([r[0] for r in m]),db=ci([r[1] for r in m]),cursor_ms=ci([r[2] for r in m]),client=ci([r[3] for r in m])))
assert len(summary)==63
(OUT/'summary.json').write_text(json.dumps(summary,indent=2))
cell=lambda **kw:next(s for s in summary if all(s[a]==b for a,b in kw.items()))
fmt=lambda a:f'{a[0]:.2f} [{a[1]:.2f}, {a[2]:.2f}]'
labels={'global':'Global aggregates','page_grouped':'Page-first grouped','page_lateral':'Page-first lateral'}
# Plans: scan counters and the settings actually in force.
def nodes(r):
 yield r
 for x in r.get('Plans',[]):yield from nodes(x)
plans=[];
for f in RAW.glob('plans-*-'+col+'.txt'):
 for l in f.read_text().splitlines():
  if l.startswith('{'):plans.append(json.loads(l))
pl={}
for p in plans:
 if p['type']!='plan':continue
 root=p['plan'][0]['Plan'];ns=list(nodes(root))
 scan={t:sum(q.get('Actual Rows',0)*q.get('Actual Loops',1) for q in ns if q.get('Relation Name')==t and 'Scan' in q['Node Type']) for t in ['products','order_items','reviews']}
 types={q['Node Type'] for q in ns}
 pl[key(p)]=dict(scan=scan,exec_ms=p['plan'][0]['Execution Time'],hits=root.get('Shared Hit Blocks',0),gather=bool(types&{'Gather','Gather Merge'}),workers=max([q.get('Workers Launched',0) for q in ns]+[0]),jit='JIT' in p['plan'][0],seq_scans=sorted({q['Relation Name'] for q in ns if q['Node Type']=='Seq Scan' and q.get('Relation Name') in ('order_items','reviews')}),settings=p['settings'])
(OUT/'plans.json').write_text(json.dumps([{'key':list(k),**v} for k,v in pl.items()],indent=2))
cp=[json.loads(l) for f in RAW.glob('plans-*-'+col+'.txt') for l in f.read_text().splitlines() if l.startswith('{"type":"cursor_plan"')]
# E1
t1='| Design | OFFSET | Keyset, known cursor | Keyset, discovered cursor | Discovery alone |\n|---|---:|---:|---:|---:|\n'
for v in labels:
 for f in [.95]:
  o=cell(exp='E1_cursor',variant=v,method='offset',fraction=f);k=cell(exp='E1_cursor',variant=v,method='keyset',cursor='known',fraction=f);l=cell(exp='E1_cursor',variant=v,method='keyset',cursor='lookup',fraction=f)
  t1+=f'| {labels[v]} | {fmt(o["service"])} | {fmt(k["service"])} | {fmt(l["service"])} | {l["cursor_ms"][0]:.2f} |\n'
# E2
t2='| Design | Pagination | Cloned base | Skewed fan-out |\n|---|---|---:|---:|\n'
for v in labels:
 for m in ['offset','keyset']:
  c=cell(exp='E1_cursor',variant=v,method=m,cursor='none' if m=='offset' else 'known',fraction=.95);s=cell(exp='E2_skew',variant=v,method=m,fraction=.95)
  p=pl[key(s)]['scan'] if key(s) in pl else {'order_items':0,'reviews':0}
  t2+=f'| {labels[v]} | {m.upper()} | {fmt(c["service"])} | {fmt(s["service"])} |\n'
# E3
t3='| Design | Pagination | Primary settings | Default settings |\n|---|---|---:|---:|\n'
for v in labels:
 for m in ['offset','keyset']:
  c=cell(exp='E1_cursor',variant=v,method=m,cursor='none' if m=='offset' else 'known',fraction=.95);d=cell(exp='E3_default_jit_parallel',variant=v,method=m)
  q=pl.get(key(d),{});t3+=f'| {labels[v]} | {m.upper()} | {fmt(c["service"])} | {fmt(d["service"])} |\n'
# E4
t4='| Design | Pagination | Depth | Indexed | Indexes removed |\n|---|---|---:|---:|---:|\n'
for v in labels:
 for m in ['offset','keyset']:
  for f in [0,.95]:
   c=cell(exp='E1_cursor',variant=v,method=m,cursor='none' if m=='offset' else 'known',fraction=f);n=cell(exp='E4_no_index',variant=v,method=m,fraction=f)
   t4+=f'| {labels[v]} | {m.upper()} | {int(f*100)}% | {fmt(c["service"])} | {fmt(n["service"])} |\n'
prep=[json.loads(l) for l in (RAW/('correctness-'+col+'.txt')).read_text().splitlines() if l.startswith('{')]
fan=next(x for x in prep if x['type']=='fanout')
g95=cell(exp='E1_cursor',variant='global',method='offset',fraction=.95)['service'][0]
kn=cell(exp='E1_cursor',variant='page_lateral',method='keyset',cursor='known',fraction=.95);lk=cell(exp='E1_cursor',variant='page_lateral',method='keyset',cursor='lookup',fraction=.95)
sk_g=cell(exp='E2_skew',variant='global',method='offset',fraction=.95)['service'][0];sk_l=cell(exp='E2_skew',variant='page_lateral',method='keyset',fraction=.95)['service'][0]
nl=cell(exp='E4_no_index',variant='page_lateral',method='offset',fraction=.95)['service'][0];ng=cell(exp='E4_no_index',variant='page_grouped',method='offset',fraction=.95)['service'][0]
scal=dict(ext_g95=f'{g95:.1f}',ext_known=f'{kn["service"][0]:.2f}',ext_lookup=f'{lk["service"][0]:.2f}',ext_lookup_cursor=f'{lk["cursor_ms"][0]:.2f}',ext_ratio_known=f'{g95/kn["service"][0]:.0f}',ext_ratio_lookup=f'{g95/lk["service"][0]:.0f}',ext_skew_global=f'{sk_g:.0f}',ext_skew_lateral=f'{sk_l:.2f}',ext_ratio_skew=f'{sk_g/sk_l:.0f}',
 ext_noidx_lateral=f'{nl:.0f}',ext_noidx_grouped=f'{ng:.0f}',ext_fan_max_items=f'{fan["skew"]["max_items"]:,}',ext_fan_base_items=str(fan['cloned_base']['max_items']),ext_fan_median_items=str(fan['skew']['median_items']),ext_fan_p99_items=str(fan['skew']['p99_items']),ext_fan_max_reviews=f'{fan["skew"]["max_reviews"]:,}',ext_fan_base_reviews=str(fan['cloned_base']['max_reviews']),ext_fan_median_reviews=str(fan['skew']['median_reviews']),ext_fan_p99_reviews=str(fan['skew']['p99_reviews']),ext_fan_no_items=f'{fan["skew"]["products_without_items"]:,}',ext_fan_no_reviews=f'{fan["skew"]["products_without_reviews"]:,}',ext_n_trials=f'{len(trials):,}',ext_n_requests=f'{len(meas):,}',ext_n_cells=str(len(summary)))
vals=dict(**scal,ext_collection=col,ext_table_cursor=t1,ext_table_skew=t2,ext_table_default=t3,ext_table_noindex=t4,ext_trials=len(trials),ext_requests=len(meas),ext_fanout=fan,
 ext_dropped=[x for x in prep if x['type']=='dropped_indexes'][0]['dropped'],ext_cursor_plan_ms=[c['plan'][0]['Execution Time'] for c in cp])
(OUT/'ext-values.json').write_text(json.dumps(vals,indent=2))
(OUT/'raw-sha256.json').write_text(json.dumps({str(p.relative_to(X)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.glob('*')) if p.is_file()},indent=2))
print('PASS',col,len(trials),'trials',len(meas),'requests'); print(t1);print(t2);print(t3);print(t4);print(json.dumps(fan))
