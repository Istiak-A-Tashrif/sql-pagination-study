import fs from 'node:fs';import crypto from 'node:crypto';import {performance} from 'node:perf_hooks';
const base=new URL('../',import.meta.url),manifest=JSON.parse(fs.readFileSync(new URL('manifest.json',base))),collection=process.argv[2];
if(!collection||!/^[-a-zA-Z0-9]+$/.test(collection))throw Error('collection identifier required');
const raw=new URL('results/raw/',base),append=(f,x)=>fs.appendFileSync(new URL(f,raw),JSON.stringify({at:new Date().toISOString(),collection,...x})+'\n');
async function query(c,run,phase,step,cache){
 const body={...c,run,collection,phase,step,cache},start=performance.now();
 const response=await fetch('http://127.0.0.1:24001/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const value=await response.json(),clientMs=performance.now()-start;
 if(!response.ok)throw Error(JSON.stringify(value));
 const ids=value.data.map(x=>x.id);if(ids.length!==c.limit||ids.some((x,i)=>x!==c.offset+i+1))throw Error('unexpected product page');
 const digest=crypto.createHash('sha256').update(JSON.stringify(value.data)).digest('hex');
 append('requests.jsonl',{...c,run,phase,step,id:value.id,clientMs,rowDigest:digest,rowCount:ids.length,cache});
}
// Health only; no application timing is accepted before independent SQL verification.
for(let i=0;i<120;i++){try{if((await fetch('http://127.0.0.1:24001/health')).ok)break;}catch{}if(i===119)throw Error('API not ready');await new Promise(r=>setTimeout(r,500));}
for(const [i,c] of manifest.cells.entries())for(let j=0;j<manifest.warmups_per_cell;j++)await query(c,`${collection}-warm-${i}`,'warmup',j,'off');
append('events.jsonl',{event:'warmup-complete',cells:manifest.cells.length});
for(const c of manifest.trials){
 const run=`${collection}-${c.trial}`,start=new Date().toISOString();
 if(c.state==='hit')await query(c,run,'fill',-1,'on');
 for(let j=0;j<manifest.samples_per_trial;j++)await query(c,c.state==='miss'?`${run}-q${j}`:run,'measurement',j,c.state==='off'?'off':'on');
 append('trials.jsonl',{...c,run,start,end:new Date().toISOString()});
 if(c.index%100===0)console.log(JSON.stringify({collection,completed:c.index+1,total:manifest.trials.length}));
}
append('events.jsonl',{event:'measurement-complete',trials:manifest.trials.length});
