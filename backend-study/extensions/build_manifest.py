#!/usr/bin/env python3
"""Frozen manifest for the extension experiments (seed 20261022). Cells are fixed here, then trial order is shuffled once."""
import json,random,itertools
SEED=20261022;REPS=20;SAMPLES=3;WARMUPS=2;N=100000
variants=['global','page_grouped','page_lateral'];fractions=[0,.5,.95]
cells=[]
def cell(exp,schema,api,variant,method,cursor,fraction,limit=25):
 cells.append(dict(exp=exp,schema=schema,api=api,variant=variant,method=method,cursor=cursor,fraction=fraction,limit=limit,offset=int(N*fraction)))
# E1 cursor acquisition: OFFSET, keyset with a known cursor, keyset after a discovery query, adjacent in the same session.
for v,f in itertools.product(variants,fractions):
 cell('E1_cursor','s100000','tuned',v,'offset','none',f)
 cell('E1_cursor','s100000','tuned',v,'keyset','known',f)
 cell('E1_cursor','s100000','tuned',v,'keyset','lookup',f)
# E2 independently generated heavy-tailed fan-out dataset.
for v,m,f in itertools.product(variants,['offset','keyset'],fractions):cell('E2_skew','skew100000','tuned',v,m,'known' if m=='keyset' else 'none',f)
# E3 default JIT and parallel-query settings, deepest page.
for v,m in itertools.product(variants,['offset','keyset']):cell('E3_default_jit_parallel','s100000','default',v,m,'known' if m=='keyset' else 'none',.95)
# E4 child product_id indexes removed, first and deepest page.
for v,m,f in itertools.product(variants,['offset','keyset'],[0,.95]):cell('E4_no_index','noidx100000','tuned',v,m,'known' if m=='keyset' else 'none',f)
rng=random.Random(SEED)
trials=[dict(c,cell=i,rep=r) for i,c in enumerate(cells) for r in range(REPS)]
rng.shuffle(trials)
for i,t in enumerate(trials):t['index']=i;t['trial']=f"x{i:04d}"
json.dump(dict(seed=SEED,repetitions=REPS,samples_per_trial=SAMPLES,warmups_per_cell=WARMUPS,cells=cells,trials=trials,counts=dict(cells=len(cells),trials=len(trials),measured_requests=len(trials)*SAMPLES)),open('manifest.json','w'),indent=1)
json.dump(cells,open('results-cells.json','w'))
print(len(cells),'cells',len(trials),'trials',len(trials)*SAMPLES,'measured requests')
