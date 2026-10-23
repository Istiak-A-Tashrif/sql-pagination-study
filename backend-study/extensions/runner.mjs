import fs from 'node:fs';import crypto from 'node:crypto';import {performance} from 'node:perf_hooks';
const base=new URL('./',import.meta.url),manifest=JSON.parse(fs.readFileSync(new URL('manifest.json',base))),collection=process.argv[2];
if(!collection||!/^[-a-zA-Z0-9]+$/.test(collection))throw Error('collection identifier required');
const raw=new URL('results/raw/',base),append=(f,x)=>fs.appendFileSync(new URL(f,raw),JSON.stringify({at:new Date().toISOString(),collection,...x})+'\n');
const port={tuned:24002,default:24003};
async function query(c,run,phase,step){
 const body={schema:c.schema,variant:c.variant,method:c.method,cursor:c.cursor,limit:c.limit,offset:c.offset,exp:c.exp,run,collection,phase,step},start=performance.now();
 const response=await fetch(`http://127.0.0.1:${port[c.api]}/query`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const value=await response.json(),clientMs=performance.now()-start;
 if(!response.ok)throw Error(JSON.stringify(value));
 const ids=value.data.map(x=>x.id);if(ids.length!==c.limit||ids.some((x,i)=>x!==c.offset+i+1))throw Error('unexpected product page');
 append('requests.jsonl',{...c,run,phase,step,id:value.id,clientMs,rowDigest:crypto.createHash('sha256').update(JSON.stringify(value.data)).digest('hex'),rowCount:ids.length});
}
for(const p of Object.values(port))for(let i=0;i<120;i++){try{if((await fetch(`http://127.0.0.1:${p}/health`)).ok)break;}catch{}if(i===119)throw Error('API not ready');await new Promise(r=>setTimeout(r,500));}
for(const [i,c] of manifest.cells.entries())for(let j=0;j<manifest.warmups_per_cell;j++)await query(c,`${collection}-warm-${i}`,'warmup',j);
append('events.jsonl',{event:'warmup-complete',cells:manifest.cells.length});
for(const c of manifest.trials){
 const run=`${collection}-${c.trial}`,start=new Date().toISOString();
 for(let j=0;j<manifest.samples_per_trial;j++)await query(c,run,'measurement',j);
 append('trials.jsonl',{...c,run,start,end:new Date().toISOString()});
 if(c.index%100===0)console.log(JSON.stringify({collection,completed:c.index+1,total:manifest.trials.length}));
}
append('events.jsonl',{event:'measurement-complete',trials:manifest.trials.length});
