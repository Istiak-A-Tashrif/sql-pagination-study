const fs=require('fs'),path=require('path');
const variants=['global','page_grouped','page_lateral'],methods=['offset','keyset'],schemas=['s100000','skew100000','noidx100000'];
const sql=(variant,method,schema)=>{
 if(!variants.includes(variant)||!methods.includes(method)||!schemas.includes(schema))throw Error('unknown query cell');
 return fs.readFileSync(path.join(__dirname,'sql',`${variant}_${method}.sql`),'utf8').replaceAll('@S@',schema);
};
// Cursor discovery for a numbered page: the id of the row that precedes the requested window.
const cursorSql=schema=>{if(!schemas.includes(schema))throw Error('unknown schema');return `SELECT id FROM ${schema}.products ORDER BY id OFFSET $1 LIMIT 1`};
module.exports={sql,cursorSql,variants,methods,schemas};
