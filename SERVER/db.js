import {Pool} from 'pg';
import dotenv from 'dotenv';
dotenv.config();
const pool = new Pool({
    user: process.env.DBUSER|| 'postgres',
    host: process.env.DBHOST|| 'localhost',
    database: process.env.DBNAME||'projectNebula',
    password: process.env.DBPASSWORD||'something',
    port:parseInt(process.env.PORT,10),})
pool.query('SELECT NOW()',(err,res)=>{
    if(err){console.error("FAILURE in a KOREAN Accent:",err.message)}
    else{console.log('Connected at:',res.rows[0].now);}
})
module.exports={query:(text,params)=>pool.query(text,params),pool}