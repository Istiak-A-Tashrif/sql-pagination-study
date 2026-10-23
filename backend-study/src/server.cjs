const express=require('express'),{Pool}=require('pg'),{createClient}=require('redis'),fs=require('fs'),crypto=require('crypto');
const {sql,variants,methods,scales}=require('./queries.cjs');
const pool=new Pool({host:'db',user:'unibackend',password:'local-study-only',database:'unibackend',max:1});
const redis=createClient({url:'redis://redis:6379'});redis.on('error',e=>console.error(e));
const app=express();app.use(express.json());
const log=x=>fs.appendFileSync('/results/api.jsonl',JSON.stringify({at:new Date().toISOString(),...x})+'\n');
app.get('/health',(_,res)=>res.json({ok:true}));
app.post('/query',async(req,res)=>{
 const t=performance.now(),id=crypto.randomUUID();const c=req.body;
 try{
 const {scale,variant,method,limit,offset,run,cache}=c;
 if(!Number.isInteger(limit)||limit<1||limit>100||!Number.isInteger(offset)||offset<0||offset+limit>scale||!/^[-a-zA-Z0-9]+$/.test(run)||!['off','on'].includes(cache))throw Error('invalid request');
 const query=sql(variant,method,scale),key=`backend:${run}:${scale}:${variant}:${method}:${limit}:${offset}`;
 let rows=null,dbMs=null,lookupMs=null,parseMs=null,writeMs=null,serializeMs=null,outcome=cache==='on'?'miss':'off';
 if(cache==='on'){const x=performance.now();const value=await redis.get(key);lookupMs=performance.now()-x;if(value){const x=performance.now();rows=JSON.parse(value);parseMs=performance.now()-x;outcome='hit';}}
 if(rows===null){const x=performance.now();rows=(await pool.query(query,[limit,offset])).rows;dbMs=performance.now()-x;
 if(cache==='on'){const x=performance.now();const value=JSON.stringify(rows);serializeMs=performance.now()-x;const y=performance.now();await redis.setEx(key,3600,value);writeMs=performance.now()-y;}}
 const x=performance.now();const body=JSON.stringify({id,data:rows});const responseSerializeMs=performance.now()-x;
 const event={...c,id,key,outcome,dbMs,lookupMs,parseMs,serializeMs,writeMs,responseSerializeMs,serviceMs:performance.now()-t,bytes:Buffer.byteLength(body),rowCount:rows.length,rowDigest:crypto.createHash('sha256').update(JSON.stringify(rows)).digest('hex')};
 log(event);res.set('Cache-Control','no-store').type('json').send(body);
 }catch(e){log({...c,id,error:e.message});res.status(500).json({error:e.message})}
});
(async()=>{await redis.connect();app.listen(5001,'0.0.0.0')})();
