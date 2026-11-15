import pg from 'pg';
import dotenv from 'dotenv';
dotenv.config();

const { Pool } = pg;

export const pool = new Pool({
  user: process.env.DBUSER || 'postgres',
  host: process.env.DBHOST || 'localhost',
  database: process.env.DBNAME || 'projectNebula',
  password: process.env.DBPASSWORD || 'something',
  port: parseInt(process.env.DBPORT || '5432', 10),
});

pool.query('SELECT NOW()', (err, res) => {
  if (err) {
    console.error('FAILURE in a KOREAN Accent:', err.message);
  } else {
    console.log('Connected at:', res.rows[0].now);
  }
});

const db = {
  query: (text, params) => pool.query(text, params),
  pool,
};

export default db;