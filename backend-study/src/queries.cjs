const fs=require('fs'),path=require('path');
const variants=['global','page_grouped','page_lateral'],methods=['offset','keyset'],scales=[5000,25000,100000];
const sql=(variant,method,scale)=>{
 if(!variants.includes(variant)||!methods.includes(method)||!scales.includes(scale))throw Error('unknown query cell');
 return fs.readFileSync(path.join(__dirname,'sql',`${variant}_${method}.sql`),'utf8').replaceAll('@S@',`s${scale}`);
};module.exports={sql,variants,methods,scales};
