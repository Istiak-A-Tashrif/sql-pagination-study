const {Pool}=require('pg');const {sql,variants,methods,scales}=require('./queries.cjs');
const pool=new Pool({host:'db',user:'unibackend',password:'local-study-only',database:'unibackend',max:1});
(async()=>{try{for(const scale of scales)for(const variant of variants)for(const method of methods)for(const fraction of [0,.5,.95])for(const limit of (scale===100000?[10,25,100]:[25])){
 const offset=Math.floor(scale*fraction),query=sql(variant,method,scale);
 const plan=(await pool.query('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+query,[limit,offset])).rows[0]['QUERY PLAN'];
 console.log(JSON.stringify({type:'plan',at:new Date().toISOString(),scale,variant,method,fraction,limit,offset,sql:query,plan}));
}}finally{await pool.end()}})().catch(e=>{console.error(e);process.exitCode=1});
