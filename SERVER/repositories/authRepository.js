import { pool } from '../db.js';

export const phoneCheckQ = async (phone, client = pool) => {
  return client.query(
    'SELECT user_id FROM users WHERE phone = $1',
    [phone]
  );
};

export const faydaCheckQ = async (faydaId, client = pool) => {
  return client.query(
    'SELECT user_id FROM users WHERE fayda_id = $1',
    [faydaId]
  );
};

export const emailCheckQ = async (email, client = pool) => {
  if (!email) return { rows: [] };
  return client.query(
    'SELECT user_id FROM users WHERE LOWER(email) = LOWER($1)',
    [email]
  );
};

export const newbieQ = async (client, {
  firstName,
  fatherName,
  phone,
  faydaId,
  email = null,
  hashedPassword,
  role = 'farmer',
  region = 'Arsi',
  registeredBy = 'self',
}) => {
  return client.query(
    `INSERT INTO users (first_name, father_name, phone, fayda_id, email, password_hash, role, region, registered_by)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
     RETURNING user_id, first_name, father_name, phone, fayda_id, email, role, region, registered_by, created_at`,
    [firstName, fatherName, phone, faydaId, email, hashedPassword, role, region, registeredBy]
  );
};

export const logInQ = async (identifier, client = pool) => {
  const clean = identifier.trim();
  return client.query(
    `SELECT user_id, first_name, father_name, phone, fayda_id, email, password_hash, role, region, is_banned
     FROM users 
     WHERE (phone = $1 OR fayda_id = $1 OR LOWER(email) = LOWER($1))
       AND deleted_at IS NULL`,
    [clean]
  );
};

export const updateRefreshTokenQ = async (newRefreshTokenHash, userId, oldRefreshTokenHash, client = pool) => {
  return client.query(
    `UPDATE users 
     SET refresh_token_hash = $1 
     WHERE user_id = $2 AND refresh_token_hash = $3
     RETURNING user_id`,
    [newRefreshTokenHash, userId, oldRefreshTokenHash]
  );
};

export const sessionRevokeQ = async (userId, client = pool) => {
  return client.query(
    'UPDATE users SET refresh_token_hash = NULL WHERE user_id = $1',
    [userId]
  );
};

export const refreshTokenLogInQ = async (refreshTokenHash, userId, client = pool) => {
  return client.query(
    'UPDATE users SET refresh_token_hash = $1 WHERE user_id = $2',
    [refreshTokenHash, userId]
  );
};

export const getFarmersListQ = async (limit = 50, client = pool) => {
  return client.query(
    `SELECT user_id, first_name, father_name, phone, fayda_id, email, role, region, registered_by, created_at
     FROM users
     WHERE role = 'farmer' AND deleted_at IS NULL
     ORDER BY created_at DESC
     LIMIT $1`,
    [limit]
  );
};
