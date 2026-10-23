// Builds the three extension schemas and verifies every variant against a scalar oracle.
const {Pool}=require('pg'),crypto=require('crypto');
const {sql,variants,methods}=require('./queries.cjs');
const pool=new Pool({host:'db',user:'unibackend',password:'local-study-only',database:'unibackend',max:1});
const emit=x=>console.log(JSON.stringify({at:new Date().toISOString(),...x}));
const tables=['users','categories','products','orders','order_items','reviews','inventory','tags','product_tags'];
const digest=rows=>crypto.createHash('sha256').update(JSON.stringify(rows)).digest('hex');
const oracleSql=s=>`SELECT p.id,p.name,c.name category,(SELECT count(DISTINCT order_id) FROM ${s}.order_items x WHERE x.product_id=p.id) total_orders,COALESCE((SELECT avg(rating) FROM ${s}.reviews x WHERE x.product_id=p.id),0) avg_rating,COALESCE((SELECT stock FROM ${s}.inventory x WHERE x.product_id=p.id),0) stock FROM ${s}.products p LEFT JOIN ${s}.categories c ON c.id=p.category_id ORDER BY p.id`;
async function counts(s){const c={};for(const t of tables)c[t]=Number((await pool.query(`SELECT count(*) n FROM ${s}.${t}`)).rows[0].n);return c}
async function verify(s,full,reference){
 const n=100000,oracle=full?(await pool.query(oracleSql(s))).rows:null,expected=full?digest(oracle):null;
 for(const v of variants)for(const m of methods){
  if(full){const all=(await pool.query(sql(v,m,s),[n,0])).rows;if(digest(all)!==expected)throw Error('all-row oracle mismatch '+[s,v,m]);}
  for(const fraction of [0,.5,.95]){
   const offset=Math.floor(n*fraction),rows=(await pool.query(sql(v,m,s),[25,offset])).rows;
   const want=full?oracle.slice(offset,offset+25):reference[offset];
   if(digest(rows)!==digest(want))throw Error('page oracle mismatch '+[s,v,m,offset]);
  }
  emit({type:'correctness',schema:s,variant:v,method:m,full_result_check:full,page_checks:3,status:'PASS'});
 }
 return full?oracle:null;
}
(async()=>{try{
 const base=await pool.query('SELECT (SELECT count(*) FROM public.products)::int products');
 if(base.rows[0].products!==5000)throw Error('base dump incomplete');
 // 1. s100000: identical construction to the primary study (cloned base blocks).
 let s='s100000';await pool.query(`DROP SCHEMA IF EXISTS ${s} CASCADE; CREATE SCHEMA ${s}`);
 for(const t of tables)await pool.query(`CREATE TABLE ${s}.${t} (LIKE public.${t} INCLUDING ALL)`);
 const specs={users:"id+k*10000,name,email||'.rep'||k,created_at",categories:'id,name',products:'id+k*5000,name,description,price,category_id,created_at',orders:'id+k*20000,user_id+k*10000,total_amount,created_at',order_items:'id+k*50000,order_id+k*20000,product_id+k*5000,quantity,unit_price',reviews:'id+k*30000,user_id+k*10000,product_id+k*5000,rating,comment,created_at',inventory:'product_id+k*5000,stock,last_updated',tags:'id,name',product_tags:'product_id,tag_id'};
 for(const t of tables){const copies=['categories','tags','product_tags'].includes(t)?1:20;await pool.query(`INSERT INTO ${s}.${t} SELECT ${specs[t]} FROM public.${t} CROSS JOIN generate_series(0,${copies-1}) k`);}
 for(const t of tables)await pool.query(`VACUUM (ANALYZE) ${s}.${t}`);
 emit({type:'counts',schema:s,counts:await counts(s)});
 const oracle100=await verify(s,true);
 // 2. skew100000: independently generated, heavy-tailed fan-out, same row totals.
 s='skew100000';await pool.query(`DROP SCHEMA IF EXISTS ${s} CASCADE; CREATE SCHEMA ${s}`);
 for(const t of tables)await pool.query(`CREATE TABLE ${s}.${t} (LIKE public.${t} INCLUDING ALL)`);
 await pool.query('SELECT setseed(0.20261022)');
 await pool.query(`INSERT INTO ${s}.categories SELECT id,name FROM public.categories`);
 await pool.query(`INSERT INTO ${s}.tags SELECT id,name FROM public.tags`);
 await pool.query(`INSERT INTO ${s}.users SELECT g,'User '||g,'user'||g||'@skew.example',now() FROM generate_series(1,200000) g`);
 await pool.query(`INSERT INTO ${s}.products SELECT g,'Product '||g,'Synthetic skew product '||g,round((10+random()*990)::numeric,2),1+floor(random()*10)::int,now() FROM generate_series(1,100000) g`);
 await pool.query(`INSERT INTO ${s}.orders SELECT g,1+floor(random()*200000)::int,round((random()*500)::numeric,2),now() FROM generate_series(1,400000) g`);
 // rank = floor(N*u^a) is heavy-tailed; multiplying by a prime coprime to N spreads heavy products across ids.
 await pool.query(`INSERT INTO ${s}.order_items SELECT g,1+floor(random()*400000)::int,1+((floor(100000*power(random(),3))::bigint*7919)%100000)::int,1+floor(random()*5)::int,round((5+random()*95)::numeric,2) FROM generate_series(1,1000000) g`);
 await pool.query(`INSERT INTO ${s}.reviews SELECT g,1+floor(random()*200000)::int,1+((floor(100000*power(random(),2))::bigint*104729)%100000)::int,1+floor(random()*5)::int,'Review '||g,now() FROM generate_series(1,600000) g`);
 await pool.query(`INSERT INTO ${s}.inventory SELECT g,floor(random()*500)::int,now() FROM generate_series(1,100000) g`);
 for(const t of tables)await pool.query(`VACUUM (ANALYZE) ${s}.${t}`);
 emit({type:'counts',schema:s,counts:await counts(s)});
 const stat=(await pool.query(`SELECT (SELECT max(c) FROM (SELECT count(*) c FROM ${s}.order_items GROUP BY product_id) q)::int max_items,(SELECT percentile_disc(.5) WITHIN GROUP (ORDER BY c) FROM (SELECT count(*) c FROM ${s}.order_items GROUP BY product_id) q)::int median_items,(SELECT percentile_disc(.99) WITHIN GROUP (ORDER BY c) FROM (SELECT count(*) c FROM ${s}.order_items GROUP BY product_id) q)::int p99_items,(SELECT count(*) FROM ${s}.products p WHERE NOT EXISTS (SELECT 1 FROM ${s}.order_items x WHERE x.product_id=p.id))::int products_without_items,(SELECT max(c) FROM (SELECT count(*) c FROM ${s}.reviews GROUP BY product_id) q)::int max_reviews,(SELECT percentile_disc(.5) WITHIN GROUP (ORDER BY c) FROM (SELECT count(*) c FROM ${s}.reviews GROUP BY product_id) q)::int median_reviews,(SELECT percentile_disc(.99) WITHIN GROUP (ORDER BY c) FROM (SELECT count(*) c FROM ${s}.reviews GROUP BY product_id) q)::int p99_reviews,(SELECT count(*) FROM ${s}.products p WHERE NOT EXISTS (SELECT 1 FROM ${s}.reviews x WHERE x.product_id=p.id))::int products_without_reviews`)).rows[0];
 const base_stat=(await pool.query(`SELECT (SELECT max(c) FROM (SELECT count(*) c FROM s100000.order_items GROUP BY product_id) q)::int max_items,(SELECT max(c) FROM (SELECT count(*) c FROM s100000.reviews GROUP BY product_id) q)::int max_reviews`)).rows[0];
 emit({type:'fanout',schema:s,skew:stat,cloned_base:base_stat});
 await verify(s,true);
 // 3. noidx100000: byte-identical copy of s100000 with only the child product_id indexes removed.
 s='noidx100000';await pool.query(`DROP SCHEMA IF EXISTS ${s} CASCADE; CREATE SCHEMA ${s}`);
 for(const t of tables){await pool.query(`CREATE TABLE ${s}.${t} (LIKE s100000.${t} INCLUDING ALL)`);await pool.query(`INSERT INTO ${s}.${t} SELECT * FROM s100000.${t}`);}
 const dropped=[];
 for(const r of (await pool.query(`SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='${s}' AND tablename IN ('order_items','reviews') AND indexdef LIKE '%(product_id)%'`)).rows){await pool.query(`DROP INDEX ${s}.${r.indexname}`);dropped.push(r);}
 if(dropped.length!==2)throw Error('expected exactly two child product_id indexes');
 for(const t of tables)await pool.query(`VACUUM (ANALYZE) ${s}.${t}`);
 emit({type:'counts',schema:s,counts:await counts(s)});
 emit({type:'dropped_indexes',schema:s,dropped});
 // Window checks only: per-product oracle subqueries without the indexes would be quadratic. Data are identical to s100000.
 const reference={};for(const f of [0,.5,.95])reference[Math.floor(100000*f)]=oracle100.slice(Math.floor(100000*f),Math.floor(100000*f)+25);
 await verify(s,false,reference);
 const settings=(await pool.query(`SELECT name,setting,unit FROM pg_settings WHERE name IN ('server_version','shared_buffers','work_mem','max_parallel_workers_per_gather','jit','random_page_cost','track_io_timing') ORDER BY name`)).rows;
 const indexes=(await pool.query(`SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes WHERE schemaname IN ('s100000','skew100000','noidx100000') ORDER BY schemaname,tablename,indexname`)).rows;
 emit({type:'environment',settings,indexes});
 emit({type:'complete',status:'PASS'});
}finally{await pool.end()}})().catch(e=>{console.error(e);process.exitCode=1});
