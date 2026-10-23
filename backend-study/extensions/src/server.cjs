const express=require('express'),{Pool}=require('pg'),fs=require('fs'),crypto=require('crypto');
const {sql,cursorSql,variants,methods,schemas}=require('./queries.cjs');
const pool=new Pool({host:'db',user:'unibackend',password:'local-study-only',database:'unibackend',max:1});
const app=express();app.use(express.json());
const log=x=>fs.appendFileSync('/results/api.jsonl',JSON.stringify({at:new Date().toISOString(),...x})+'\n');
app.get('/health',(_,res)=>res.json({ok:true}));
app.get('/settings',async(_,res)=>res.json((await pool.query("SELECT name,setting FROM pg_settings WHERE name IN ('jit','max_parallel_workers_per_gather')")).rows));
app.post('/query',async(req,res)=>{
 const t=performance.now(),id=crypto.randomUUID();const c=req.body;
 try{
  const {schema,variant,method,cursor,limit,offset,run}=c;
  if(!schemas.includes(schema)||!variants.includes(variant)||!methods.includes(method)||!['none','known','lookup'].includes(cursor))throw Error('invalid request');
  if(!Number.isInteger(limit)||limit<1||limit>100||!Number.isInteger(offset)||offset<0||offset+limit>100000||!/^[-a-zA-Z0-9]+$/.test(run))throw Error('invalid request');
  const query=sql(variant,method,schema);let cursorMs=null,after=offset;
  if(method==='keyset'&&cursor==='lookup'&&offset>0){
   const x=performance.now();const r=await pool.query(cursorSql(schema),[offset-1]);cursorMs=performance.now()-x;
   if(r.rows.length!==1||r.rows[0].id!==offset)throw Error('cursor lookup mismatch');after=r.rows[0].id;
  }
  const x=performance.now();const rows=(await pool.query(query,[limit,after])).rows;const dbMs=performance.now()-x;
  const y=performance.now();const body=JSON.stringify({id,data:rows});const responseSerializeMs=performance.now()-y;
  const event={...c,id,dbMs,cursorMs,responseSerializeMs,serviceMs:performance.now()-t,bytes:Buffer.byteLength(body),rowCount:rows.length,rowDigest:crypto.createHash('sha256').update(JSON.stringify(rows)).digest('hex')};
  log(event);res.set('Cache-Control','no-store').type('json').send(body);
 }catch(e){log({...c,id,error:e.message});res.status(500).json({error:e.message})}
});
(async()=>{app.listen(5001,'0.0.0.0')})();
