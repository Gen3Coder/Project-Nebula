import { verifyAccessToken } from '../utils/jwtHelpers.js';
import AppError from '../utils/AppError.js';

export function authToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = (authHeader && authHeader.startsWith('Bearer ') ? authHeader.split(' ')[1] : null) || req.cookies?.accessToken;
  if (!token) return next(AppError.unauthorized('Access token required.'));
  try {
    const decoded = verifyAccessToken(token);
    req.user = decoded;
    next();
  } catch (err) {
    return next(AppError.unauthorized('Invalid or expired access token.'));
  }
}

export function requireRole(role) {
  return (req, res, next) => {
    if (!req.user) {
      return next(AppError.unauthorized('Authentication required.'));
    }
    const userRole = String(req.user.role || '').toLowerCase();
    const required = String(role || '').toLowerCase();
    if (userRole !== required) {
      return next(AppError.forbidden(`Access restricted to ${role} role.`));
    }
    next();
  };
}

export default { authToken, requireRole };
