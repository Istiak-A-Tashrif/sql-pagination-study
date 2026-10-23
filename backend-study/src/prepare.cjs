const {Pool}=require('pg'),fs=require('fs'),crypto=require('crypto');
const {sql,variants,methods,scales}=require('./queries.cjs');
const pool=new Pool({host:'db',user:'unibackend',password:'local-study-only',database:'unibackend',max:1});
const emit=x=>console.log(JSON.stringify({at:new Date().toISOString(),...x}));
const tables=['users','categories','products','orders','order_items','reviews','inventory','tags','product_tags'];
(async()=>{try{
 const base=await pool.query('SELECT (SELECT count(*) FROM public.products)::int products,(SELECT count(*) FROM public.reviews)::int reviews,(SELECT count(*) FROM public.order_items)::int order_items');
 if(base.rows[0].products!==5000||base.rows[0].reviews!==30000||base.rows[0].order_items!==50000)throw Error('base dump incomplete');
 for(const n of scales){
 const s=`s${n}`,rep=n/5000;
 await pool.query(`DROP SCHEMA IF EXISTS ${s} CASCADE; CREATE SCHEMA ${s}`);
 for(const t of tables)await pool.query(`CREATE TABLE ${s}.${t} (LIKE public.${t} INCLUDING ALL)`);
 const specs={users:'id+k*10000,name,email||\'.rep\'||k,created_at',categories:'id,name',products:'id+k*5000,name,description,price,category_id,created_at',orders:'id+k*20000,user_id+k*10000,total_amount,created_at',order_items:'id+k*50000,order_id+k*20000,product_id+k*5000,quantity,unit_price',reviews:'id+k*30000,user_id+k*10000,product_id+k*5000,rating,comment,created_at',inventory:'product_id+k*5000,stock,last_updated',tags:'id,name',product_tags:'product_id,tag_id'};
 for(const t of tables){
  const copies=['categories','tags','product_tags'].includes(t)?1:rep;
  await pool.query(`INSERT INTO ${s}.${t} SELECT ${specs[t]} FROM public.${t} CROSS JOIN generate_series(0,${copies-1}) k`);
 }
 for(const t of tables)await pool.query(`VACUUM (ANALYZE) ${s}.${t}`);
 const counts={};for(const t of tables)counts[t]=Number((await pool.query(`SELECT count(*) n FROM ${s}.${t}`)).rows[0].n);
 if(counts.products!==n||counts.reviews!==n*6||counts.order_items!==n*10)throw Error('scaled counts incorrect');
 emit({type:'counts',scale:n,counts});
 // Correlated oracle uses independent scalar subqueries; all products are checked.
 const oracle=(await pool.query(`SELECT p.id,p.name,c.name category,(SELECT count(DISTINCT order_id) FROM ${s}.order_items x WHERE x.product_id=p.id) total_orders,COALESCE((SELECT avg(rating) FROM ${s}.reviews x WHERE x.product_id=p.id),0) avg_rating,COALESCE((SELECT stock FROM ${s}.inventory x WHERE x.product_id=p.id),0) stock FROM ${s}.products p LEFT JOIN ${s}.categories c ON c.id=p.category_id ORDER BY p.id`)).rows;
 const digest=rows=>crypto.createHash('sha256').update(JSON.stringify(rows)).digest('hex');const expected=digest(oracle);
 for(const v of variants)for(const m of methods){
  const all=(await pool.query(sql(v,m,n),[n,0])).rows;
  if(digest(all)!==expected)throw Error('all-row oracle mismatch '+[n,v,m]);
  for(const limit of [10,25,100])for(const fraction of [0,.5,.95]){
   const offset=Math.floor(n*fraction),rows=(await pool.query(sql(v,m,n),[limit,offset])).rows;
   if(digest(rows)!==digest(oracle.slice(offset,offset+limit)))throw Error('page oracle mismatch '+[n,v,m,limit,offset]);
  }
  emit({type:'correctness',scale:n,variant:v,method:m,products:all.length,page_checks:9,oracle_sha256:expected,status:'PASS'});
 }
 }
 const settings=(await pool.query(`SELECT name,setting,unit FROM pg_settings WHERE name IN ('server_version','shared_buffers','work_mem','max_parallel_workers_per_gather','jit','effective_cache_size','random_page_cost','track_io_timing') ORDER BY name`)).rows;
 const indexes=(await pool.query(`SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes WHERE schemaname IN ('s5000','s25000','s100000') ORDER BY schemaname,tablename,indexname`)).rows;
 emit({type:'environment',settings,indexes,base_dump:'shared unchanged synthetic dump; cloned deterministically'});
 emit({type:'complete',status:'PASS'});
 }finally{await pool.end()}})().catch(e=>{console.error(e);process.exitCode=1});
