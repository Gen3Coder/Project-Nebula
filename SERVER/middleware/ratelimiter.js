// Lightweight in-memory rate limiter (avoids missing dependency crashes)
const attempts = new Map();

export const limitAuth = (req, res, next) => {
  const ip = req.ip || req.connection.remoteAddress || 'local';
  const now = Date.now();
  const windowMs = 15 * 60 * 1000;
  const maxAttempts = 50;

  const record = attempts.get(ip) || { count: 0, resetTime: now + windowMs };

  if (now > record.resetTime) {
    record.count = 0;
    record.resetTime = now + windowMs;
  }

  record.count += 1;
  attempts.set(ip, record);

  if (record.count > maxAttempts) {
    return res.status(429).json({
      status: 'fail',
      message: 'Too many authentication attempts. Please slow down and try again later.',
    });
  }

  next();
};

export default limitAuth;
