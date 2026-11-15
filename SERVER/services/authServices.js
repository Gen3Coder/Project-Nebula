import bcrypt from 'bcryptjs';
import { pool } from '../db.js';
import * as authRepo from '../repositories/authRepository.js';
import { jwtTokens, hashToken, verifyRefreshToken } from '../utils/jwtHelpers.js';
import AppError from '../utils/AppError.js';
import { roles } from '../utils/constants.js';

export const signUpS = async ({
  firstName,
  fatherName,
  phone,
  faydaId,
  email = null,
  password,
  region = 'Arsi',
  role = roles.farmer,
  registeredBy = 'self',
}) => {
  const cleanPhone = phone.trim();
  const cleanFayda = faydaId.trim();
  const cleanEmail = email && email.trim() ? email.trim().toLowerCase() : null;

  // 1. Uniqueness checks
  const phoneCheck = await authRepo.phoneCheckQ(cleanPhone);
  if (phoneCheck.rows.length > 0) {
    throw AppError.conflict('Phone number is already registered.');
  }

  const faydaCheck = await authRepo.faydaCheckQ(cleanFayda);
  if (faydaCheck.rows.length > 0) {
    throw AppError.conflict('Fayda identification number is already registered.');
  }

  if (cleanEmail) {
    const emailCheck = await authRepo.emailCheckQ(cleanEmail);
    if (emailCheck.rows.length > 0) {
      throw AppError.conflict('Email is already registered.');
    }
  }

  // 2. Transaction for creation + session
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const hashedPassword = await bcrypt.hash(password, 10);
    const userRes = await authRepo.newbieQ(client, {
      firstName: firstName.trim(),
      fatherName: fatherName.trim(),
      phone: cleanPhone,
      faydaId: cleanFayda,
      email: cleanEmail,
      hashedPassword,
      role: role || roles.farmer,
      region: region || 'Arsi',
      registeredBy,
    });
    const newUser = userRes.rows[0];

    const tokens = jwtTokens({
      userId: newUser.user_id,
      firstName: newUser.first_name,
      fatherName: newUser.father_name,
      phone: newUser.phone,
      role: newUser.role,
    });

    await authRepo.refreshTokenLogInQ(hashToken(tokens.refreshToken), newUser.user_id, client);

    await client.query('COMMIT');

    return {
      status: 'OK',
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      user: {
        userId: newUser.user_id,
        firstName: newUser.first_name,
        fatherName: newUser.father_name,
        fullName: `${newUser.first_name} ${newUser.father_name}`.trim(),
        phone: newUser.phone,
        faydaId: newUser.fayda_id,
        email: newUser.email,
        role: newUser.role,
        region: newUser.region,
        registeredBy: newUser.registered_by,
      },
    };
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
};

export const logInS = async ({ identifier, password }) => {
  const cleanId = (identifier || '').trim();
  const userRes = await authRepo.logInQ(cleanId);

  if (userRes.rows.length === 0) {
    throw AppError.unauthorized('Invalid login credentials (check Phone, Fayda ID, or Password).');
  }

  const user = userRes.rows[0];
  const isMatch = await bcrypt.compare(password, user.password_hash);
  if (!isMatch) {
    throw AppError.unauthorized('Invalid login credentials (check Phone, Fayda ID, or Password).');
  }

  if (user.is_banned) {
    throw AppError.forbidden('Your account has been suspended.');
  }

  const userRole = (user.role || roles.farmer).toLowerCase();

  const tokens = jwtTokens({
    userId: user.user_id,
    firstName: user.first_name,
    fatherName: user.father_name,
    phone: user.phone,
    role: userRole,
  });

  await authRepo.refreshTokenLogInQ(hashToken(tokens.refreshToken), user.user_id);

  return {
    status: 'OK',
    accessToken: tokens.accessToken,
    refreshToken: tokens.refreshToken,
    user: {
      userId: user.user_id,
      firstName: user.first_name,
      fatherName: user.father_name,
      fullName: `${user.first_name} ${user.father_name}`.trim(),
      phone: user.phone,
      faydaId: user.fayda_id,
      email: user.email,
      role: userRole,
      region: user.region,
    },
  };
};

export const refreshTokenS = async (refreshToken) => {
  if (!refreshToken) {
    throw AppError.badRequest('No refresh token provided.');
  }

  let decoded;
  try {
    decoded = verifyRefreshToken(refreshToken);
  } catch (err) {
    throw AppError.unauthorized('Invalid or expired refresh token. Please log in again.');
  }

  const tokens = jwtTokens(decoded);

  const updateRes = await authRepo.updateRefreshTokenQ(
    hashToken(tokens.refreshToken),
    decoded.userId,
    hashToken(refreshToken)
  );

  if (updateRes.rowCount === 0) {
    throw AppError.unauthorized('Refresh token is invalid or has already been used. Please log in again.');
  }

  return {
    accessToken: tokens.accessToken,
    refreshToken: tokens.refreshToken,
    user: {
      userId: decoded.userId,
      firstName: decoded.firstName,
      fatherName: decoded.fatherName,
      fullName: `${decoded.firstName} ${decoded.fatherName || ''}`.trim(),
      phone: decoded.phone,
      role: decoded.role,
    },
  };
};

export const logOutS = async (refreshToken, userId = null) => {
  let targetUserId = userId;

  if (refreshToken) {
    try {
      const decoded = verifyRefreshToken(refreshToken);
      targetUserId = decoded.userId;
    } catch {
      // Ignored
    }
  }

  if (targetUserId) {
    await authRepo.sessionRevokeQ(targetUserId);
  }

  return { message: 'Logged out successfully.' };
};

export const getFarmersListS = async () => {
  const result = await authRepo.getFarmersListQ();
  return result.rows.map((r) => ({
    userId: r.user_id,
    firstName: r.first_name,
    fatherName: r.father_name,
    fullName: `${r.first_name} ${r.father_name}`.trim(),
    phone: r.phone,
    faydaId: r.fayda_id,
    email: r.email,
    region: r.region,
    registeredBy: r.registered_by,
    createdAt: r.created_at,
  }));
};
