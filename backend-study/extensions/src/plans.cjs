// EXPLAIN (ANALYZE, BUFFERS) for every extension cell, under this process's session settings (PGOPTIONS).
const {Pool}=require('pg');const {sql,cursorSql}=require('./queries.cjs');
const pool=new Pool({host:'db',user:'unibackend',password:'local-study-only',database:'unibackend',max:1});
const cells=JSON.parse(require('fs').readFileSync('/results/ext-cells.json','utf8'));const api=process.argv[2];
(async()=>{try{
 const settings=(await pool.query("SELECT name,setting FROM pg_settings WHERE name IN ('jit','max_parallel_workers_per_gather')")).rows;
 for(const c of cells.filter(x=>x.api===api&&!(x.method==='keyset'&&x.cursor==='lookup'))){
  const query=sql(c.variant,c.method,c.schema);
  const plan=(await pool.query('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+query,[c.limit,c.offset])).rows[0]['QUERY PLAN'];
  console.log(JSON.stringify({type:'plan',at:new Date().toISOString(),api,settings,...c,plan}));
 }
 for(const schema of ['s100000']){for(const offset of [Math.floor(100000*.5)-1,Math.floor(100000*.95)-1]){
  const plan=(await pool.query('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+cursorSql(schema),[offset])).rows[0]['QUERY PLAN'];
  console.log(JSON.stringify({type:'cursor_plan',api,schema,offset,plan}));
 }}
}finally{await pool.end()}})().catch(e=>{console.error(e);process.exitCode=1});
