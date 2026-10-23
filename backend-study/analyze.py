#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,collections,csv,statistics,re
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
B=Path(__file__).resolve().parent;RAW=B/'results/raw';OUT=B/'results/derived';FIG=B/'manuscript/figures'
OUT.mkdir(exist_ok=True);FIG.mkdir(exist_ok=True)
read=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
collections_log=read(RAW/'collections.jsonl');accepted=[x['collection'] for x in collections_log if x['status']=='accepted']
if not accepted:raise RuntimeError('No fully accepted guarded collection')
collection=accepted[-1];manifest=json.loads((B/'manifest.json').read_text());env=json.loads((RAW/f'environment-{collection}.json').read_text())
assert hashlib.sha256((B/'manifest.json').read_bytes()).hexdigest()==env['source_sha256']['manifest.json']
for p in ['src/server.cjs','src/prepare.cjs','src/queries.cjs','src/plans.cjs','src/runner.mjs',*['sql/'+x.name for x in (B/'sql').glob('*.sql')]]:
 assert hashlib.sha256((B/p).read_bytes()).hexdigest()==env['source_sha256'][p],('measured source changed',p)
guards=[x for x in read(RAW/'batches.jsonl') if x['collection']==collection]
for stage in ['build','startup','correctness','plans','measurement']:
 g=[x for x in guards if x['stage']==stage];assert len(g)==2 and [x['event'] for x in g]==['start','end'] and all(x['guard_clear'] for x in g) and g[-1]['exit']==0
correct=[json.loads(x) for x in (RAW/f'correctness-{collection}.txt').read_text().splitlines() if x.startswith('{')]
checks=[x for x in correct if x['type']=='correctness'];assert len(checks)==18 and all(x['status']=='PASS' for x in checks)
counts=[x for x in correct if x['type']=='counts'];assert len(counts)==3
plans=[json.loads(x) for x in (RAW/f'plans-{collection}.txt').read_text().splitlines() if x.startswith('{')];assert len(plans)==90
requests=[x for x in read(RAW/'requests.jsonl') if x['collection']==collection]
api=[x for x in read(RAW/'api.jsonl') if x['collection']==collection]
trials=[x for x in read(RAW/'trials.jsonl') if x['collection']==collection]
assert len(trials)==len(manifest['trials'])==2160
assert len(requests)==len(api)==6780
assert len({x['id'] for x in api})==len(api)
a={x['id']:x for x in api};by_trial=collections.defaultdict(list);audits=[]
for x in requests:
 y=a[x['id']];assert 'error' not in y and x['rowDigest']==y['rowDigest'] and x['rowCount']==y['rowCount']==x['limit']
 assert all(y[k]==x[k] for k in ['scale','variant','method','limit','offset','phase','step','run'])
 expected='off' if x['cache']=='off' else ('hit' if x['state']=='hit' and x['phase']=='measurement' else 'miss')
 assert y['outcome']==expected,(x['id'],expected,y['outcome'])
 assert (y['dbMs'] is None)==(expected=='hit')
 if x['phase']=='measurement':by_trial[x['trial']].append((x,y))
 audits.append({'id':x['id'],'run':x['run'],'phase':x['phase'],'outcome':y['outcome'],'database_executed':y['dbMs'] is not None,'status':'PASS'})
records=[]
metrics=['clientMs','serviceMs','dbMs','lookupMs','parseMs','serializeMs','writeMs','responseSerializeMs','bytes']
for t in trials:
 pairs=by_trial[t['trial']];assert len(pairs)==3 and {x['step'] for x,y in pairs}=={0,1,2}
 assert all(y['variant']==t['variant'] and y['scale']==t['scale'] and y['method']==t['method'] for x,y in pairs)
 record={k:t[k] for k in ['family','scale','variant','method','fraction','limit','offset','rep','state','trial','run']}
 for m in metrics:record[m]=float(np.mean([x[m] if m=='clientMs' else (y[m] or 0) for x,y in pairs]))
 record['db_per_request']=sum(y['dbMs'] is not None for x,y in pairs)/3
 records.append(record)
keys=['family','scale','variant','method','fraction','limit','state'];groups=collections.defaultdict(list)
for x in records:groups[tuple(x[k] for k in keys)].append(x)
rng=np.random.default_rng(20261021)
def estimate(values,indices=None):
 v=np.asarray(values,dtype=float);assert len(v)==20
 indices=rng.integers(0,len(v),(10000,len(v))) if indices is None else indices;means=v[indices].mean(axis=1);lo,hi=np.quantile(means,[.025,.975]);return [float(v.mean()),float(lo),float(hi)]
summary=[]
for key,items in sorted(groups.items()):
 assert len(items)==20 and {x['rep'] for x in items}==set(range(20))
 row=dict(zip(keys,key));row['n']=len(items)
 indices=rng.integers(0,len(items),(10000,len(items)))
 for m in metrics+['db_per_request']:row[m]=estimate([x[m] for x in items],indices)
 summary.append(row)
assert len(summary)==108
# Plan buffers are inclusive at the root: never sum the same buffers across a tree.
plan_summary=[]
def nodes(root):
 yield root
 for x in root.get('Plans',[]):yield from nodes(x)
for x in plans:
 p=x['plan'][0];root=p['Plan'];ns=list(nodes(root));r={k:x[k] for k in ['scale','variant','method','fraction','limit','offset']}
 r.update(planning_ms=p['Planning Time'],execution_ms=p['Execution Time'],shared_hits=root.get('Shared Hit Blocks',0),shared_reads=root.get('Shared Read Blocks',0),temp_reads=root.get('Temp Read Blocks',0),temp_writes=root.get('Temp Written Blocks',0))
 r['scan_rows']={t:sum(q.get('Actual Rows',0)*q.get('Actual Loops',0) for q in ns if q.get('Relation Name')==t and 'Scan' in q['Node Type']) for t in ['products','order_items','reviews']}
 r['nodes']=[{'type':q['Node Type'],'relation':q.get('Relation Name'),'index':q.get('Index Name'),'rows':q.get('Actual Rows'),'loops':q.get('Actual Loops'),'rows_removed':q.get('Rows Removed by Filter',0)} for q in ns]
 plan_summary.append(r)
bykey={tuple(x[k] for k in keys):x for x in summary}
def cell(family,scale,variant,method,fraction=.95,limit=25,state='off'):
 return bykey[(family,scale,variant,method,fraction,limit,state)]
def paired(aa,bb,metric='serviceMs',ratio=False):
 def select(spec):return {x['rep']:x[metric] for x in records if all(x[k]==v for k,v in spec.items())}
 a1,b1=select(aa),select(bb);assert len(a1)==len(b1)==20
 return estimate([a1[k]/b1[k] if ratio else a1[k]-b1[k] for k in sorted(a1)])
contrasts=[]
for method in ['offset','keyset']:
 for v in ['page_grouped','page_lateral']:
  base=dict(family='primary',scale=100000,method=method,fraction=.95,limit=25,state='off')
  contrasts.append({'variant':v,'method':method,'service_difference_ms':paired(dict(base,variant=v),dict(base,variant='global')),'paired_speed_ratio_global_over_variant':paired(dict(base,variant='global'),dict(base,variant=v),ratio=True)})
# Drift is diagnostic only: no outlier deletion or post-hoc exclusion.
drift=[]
for key,items in sorted(groups.items()):
 items=sorted(items,key=lambda x:int(x['trial'][1:]));mid=len(items)//2
 drift.append({**dict(zip(keys,key)),'early_service_mean':statistics.mean(x['serviceMs'] for x in items[:mid]),'late_service_mean':statistics.mean(x['serviceMs'] for x in items[mid:])})
for name,value in [('summary.json',summary),('trial-means.json',records),('audit.json',audits),('plans-summary.json',plan_summary),('contrasts.json',contrasts),('drift.json',drift)]:
 (OUT/name).write_text(json.dumps(value,indent=2)+'\n')
with (OUT/'trial-means.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
plt.rcParams.update({'font.family':'Times New Roman','font.size':10,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
colors={'global':'#333333','page_grouped':'#0072B2','page_lateral':'#D55E00'};labels={'global':'Global aggregates','page_grouped':'Page-first grouped','page_lateral':'Page-first lateral'}
def save(fig,name):
 fig.savefig(FIG/(name+'.pdf'),bbox_inches='tight');fig.savefig(FIG/(name+'.png'),dpi=300,bbox_inches='tight');plt.close(fig)
# Schematic of the three SQL strategies; figure name 'strategies' is Figure 1 in the manuscript.
from matplotlib.patches import FancyBboxPatch
fig,ax=plt.subplots(figsize=(7.1,3.1));ax.set_xlim(0,100);ax.set_ylim(0,100);ax.axis('off')
rows=[('Global\npre-aggregation',colors['global'],[('GROUP BY product\nover all order_items\nand all reviews',0),('Join to products',1),('ORDER BY id\nOFFSET / keyset\nLIMIT 25',2)]),
('Page-first\ngrouped',colors['page_grouped'],[('Select 25 products\n(OFFSET / keyset)',0),('GROUP BY product over\nchild rows joined\nto those 25',1),('Join to page',2)]),
('Page-first\nlateral',colors['page_lateral'],[('Select 25 products\n(OFFSET / keyset)',0),('Per product: indexed\nCOUNT / AVG\nsubqueries',1),('Join to page',2)])]
for r,(title,col,boxes) in enumerate(rows):
 y=70-r*32;ax.text(1,y+9,title,fontsize=9,fontweight='bold',color=col,va='center')
 for text,i in boxes:
  x=25+i*25;ax.add_patch(FancyBboxPatch((x,y),21,18,boxstyle='round,pad=0.4',fc='white',ec=col,lw=1.4));ax.text(x+10.5,y+9,text,ha='center',va='center',fontsize=7.5)
  if i<2:ax.annotate('',xy=(x+25,y+9),xytext=(x+22,y+9),arrowprops=dict(arrowstyle='->',color=col))
ax.text(99,98,'Same columns, same rows, same ORDER BY id',fontsize=8,ha='right',style='italic')
save(fig,'strategies')
fig,axes=plt.subplots(1,2,figsize=(7.1,3.0),sharey=True)
for ax,method in zip(axes,['offset','keyset']):
 for v in colors:
  rows=[cell('primary',n,v,method) for n in [5000,25000,100000]];a=np.array([x['serviceMs'] for x in rows]);ax.errorbar([5,25,100],a[:,0],yerr=[a[:,0]-a[:,1],a[:,2]-a[:,0]],marker={'global':'o','page_grouped':'s','page_lateral':'^'}[v],color=colors[v],label=labels[v],capsize=3)
 ax.set_xscale('log');ax.set_yscale('log');ax.set_xticks([5,25,100],['5k','25k','100k']);ax.set_title(method.upper());ax.set_xlabel('Products');ax.grid(alpha=.2)
axes[0].set_ylabel('API service time (ms, log scale)');axes[1].legend(fontsize=10);fig.tight_layout();save(fig,'scale')
fig,axes=plt.subplots(1,2,figsize=(7.1,3.0),sharey=True)
for ax,method in zip(axes,['offset','keyset']):
 for v in colors:
  a=np.array([cell('primary',100000,v,method,f)['serviceMs'] for f in [0,.5,.95]]);ax.errorbar([0,50,95],a[:,0],yerr=[a[:,0]-a[:,1],a[:,2]-a[:,0]],marker={'global':'o','page_grouped':'s','page_lateral':'^'}[v],color=colors[v],capsize=3,label=labels[v])
 ax.set_yscale('log');ax.set_xticks([0,50,95]);ax.set_xlabel('Skipped product positions (%)');ax.set_title(method.upper());ax.grid(alpha=.2)
axes[0].set_ylabel('API service time (ms, log scale)');axes[1].legend(fontsize=10);fig.tight_layout();save(fig,'depth')
# Render all manuscript quantities from the verified collection, never historical timings.
fmt=lambda a:f'{a[0]:.2f} [{a[1]:.2f}, {a[2]:.2f}]'
table='| Design | Pagination | API service, ms [95% CI] | Database call, ms [95% CI] |\n|---|---|---:|---:|\n'
for v in colors:
 for method in ['offset','keyset']:
  x=cell('primary',100000,v,method);table+=f'| {labels[v]} | {method.upper()} | {fmt(x["serviceMs"])} | {fmt(x["dbMs"])} |\n'
pt='| Design | Pagination | Approx. order-item scan output | Approx. review scan output | Root shared hits |\n|---|---|---:|---:|---:|\n'
for x in plan_summary:
 if x['scale']==100000 and x['limit']==25 and x['fraction']==.95:pt+=f'| {labels[x["variant"]]} | {x["method"].upper()} | {int(x["scan_rows"]["order_items"])} | {int(x["scan_rows"]["reviews"])} | {x["shared_hits"]} |\n'
ct='| Design | Cache outcome | Service, ms [95% CI] | DB queries/request |\n|---|---|---:|---:|\n'
for v in colors:
 for state in ['off','miss','hit']:
  x=cell('cache_sensitivity',100000,v,'offset',state=state);ct+=f'| {labels[v]} | {state} | {fmt(x["serviceMs"])} | {x["db_per_request"][0]:.0f} |\n'
sizes='| Design | Pagination | 10 rows | 25 rows | 100 rows |\n|---|---|---:|---:|---:|\n'
for v in colors:
 for m in ['offset','keyset']:
  vals=[cell('primary' if n==25 else 'page_size',100000,v,m,limit=n)['serviceMs'][0] for n in [10,25,100]];sizes+=f'| {labels[v]} | {m.upper()} | '+ ' | '.join(f'{z:.2f}' for z in vals)+' |\n'
dp='| Design | Pagination | Skipped | Product scan output | Order-item scan output | Review scan output | Root shared hits |\n|---|---|---:|---:|---:|---:|---:|\n'
for x in plan_summary:
 if x['scale']==100000 and x['limit']==25 and x['variant'] in ('global','page_lateral'):dp+=f'| {labels[x["variant"]]} | {x["method"].upper()} | {int(x["fraction"]*100)}% | {int(x["scan_rows"]["products"])} | {int(x["scan_rows"]["order_items"])} | {int(x["scan_rows"]["reviews"])} | {x["shared_hits"]} |\n'
ratio_headline=cell('primary',100000,'global','offset')['serviceMs'][0]/cell('primary',100000,'page_lateral','keyset')['serviceMs'][0]
ratio_offset=cell('primary',100000,'global','offset')['serviceMs'][0]/cell('primary',100000,'page_lateral','offset')['serviceMs'][0]
ratio_client=cell('primary',100000,'global','offset')['clientMs'][0]/cell('primary',100000,'page_lateral','keyset')['clientMs'][0]
client_global=cell('primary',100000,'global','offset')['clientMs'][0];client_lateral_keyset=cell('primary',100000,'page_lateral','keyset')['clientMs'][0]
db_lateral_keyset=cell('primary',100000,'page_lateral','keyset')['dbMs'][0];svc_lateral_keyset=cell('primary',100000,'page_lateral','keyset')['serviceMs'][0]
dataset_sentences=[]
for x in sorted(counts,key=lambda q:q['scale']):
 c=x['counts'];label={5000:'base',25000:'medium',100000:'largest'}[x['scale']]
 dataset_sentences.append('The '+label+' dataset contains '+', '.join(f'{c[t]:,} {label}' for t,label in [('products','products'),('users','users'),('orders','orders'),('order_items','order items'),('reviews','reviews'),('inventory','inventory rows')])+'.')
dataset_sentence=' '.join(dataset_sentences)+' Each dataset has ten categories, fifty tags and an unused empty product-tag relation. Counts are rederived after loading.'
sub={'dataset_sentence':dataset_sentence,'collection':collection,'n_trials':len(trials),'n_requests':sum(x['phase']=='measurement' for x in requests),'n_api':len(api),'n_correct':len(checks),'table_latency':table,'table_plans':pt,'table_depth_plans':dp,'ratio_headline':f'{ratio_headline:.0f}','ratio_offset':f'{ratio_offset:.0f}','global_offset_mean':f"{cell('primary',100000,'global','offset')['serviceMs'][0]:.1f}",'ratio_client':f'{ratio_client:.0f}','client_global':f'{client_global:.1f}','client_lateral_keyset':f'{client_lateral_keyset:.2f}','overhead_lateral_keyset':f'{svc_lateral_keyset-db_lateral_keyset:.2f}','db_lateral_keyset':f'{db_lateral_keyset:.2f}','table_cache':ct,'table_sizes':sizes,'global_offset':fmt(cell('primary',100000,'global','offset')['serviceMs']),'grouped_offset':fmt(cell('primary',100000,'page_grouped','offset')['serviceMs']),'lateral_offset':fmt(cell('primary',100000,'page_lateral','offset')['serviceMs']),'global_keyset':fmt(cell('primary',100000,'global','keyset')['serviceMs']),'lateral_keyset':fmt(cell('primary',100000,'page_lateral','keyset')['serviceMs']),'n_checks':sum(x['products']+x['page_checks'] for x in checks),'counts':counts,'hardware':env['cpu'],'macos':env['macos'],'memory_gib':env['memory_bytes']/2**30,'logical_cpus':env['logical_cpus'],'measurement_start':next(x['at'] for x in guards if x['stage']=='measurement' and x['event']=='start'),'measurement_end':next(x['at'] for x in guards if x['stage']=='measurement' and x['event']=='end')}
extv=B/'extensions/results/derived/ext-values.json'
if extv.exists():
 for k,v in json.loads(extv.read_text()).items():
  if isinstance(v,(str,int,float)):sub[k]=v
(OUT/'manuscript-values.json').write_text(json.dumps(sub,indent=2)+'\n')
if (B/'manuscript/paper.template.md').exists():
 source=(B/'manuscript/paper.template.md').read_text()
 for k,v in sub.items():
  if isinstance(v,(str,int,float)):source=source.replace('{{'+k+'}}',str(v))
 assert '{{' not in source
 (B/'manuscript/paper.md').write_text(source)
sha={str(p.relative_to(B)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.glob('*')) if p.is_file()};(OUT/'raw-sha256.json').write_text(json.dumps(sha,indent=2)+'\n')
print(f'PASS: collection {collection}; {len(trials)} trials; {len(audits)} request audits; {len(summary)} cells; {len(plans)} query plans.')
print(json.dumps({k:sub[k] for k in ['global_offset','grouped_offset','lateral_offset','global_keyset','lateral_keyset']},indent=2))
