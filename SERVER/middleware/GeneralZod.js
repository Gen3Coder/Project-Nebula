import { z } from 'zod';
import AppError from '../utils/AppError.js';

export const validate = (schema) => (req, res, next) => {
  const result = schema.safeParse(req.body);
  if (!result.success) {
    const neatErrors = result.error.issues
      .map((issue) => `${issue.path.join('.') || 'field'}: ${issue.message}`)
      .join(', ');
    return next(AppError.badRequest(neatErrors));
  }
  req.body = result.data;
  next();
};

export const farmerSignUp = z.object({
  firstName: z.string({ required_error: 'First name is required' })
    .trim()
    .min(1, 'First name cannot be empty')
    .max(50, 'First name cannot exceed 50 characters'),

  fatherName: z.string({ required_error: 'Father name is required' })
    .trim()
    .min(1, 'Father name cannot be empty')
    .max(50, 'Father name cannot exceed 50 characters'),

  phone: z.string({ required_error: 'Phone number is required' })
    .trim()
    .min(9, 'Phone number must be at least 9 digits')
    .max(20, 'Phone number cannot exceed 20 characters'),

  faydaId: z.string({ required_error: 'Fayda ID is required' })
    .trim()
    .regex(/^\d{16}$/, 'Fayda number must be exactly 16 numeric digits'),

  email: z.string().email('Invalid email address').trim().toLowerCase().optional().nullable().or(z.literal('')),

  password: z.string({ required_error: 'Password is required' })
    .min(6, 'Password must be at least 6 characters long'),

  region: z.string().trim().optional().default('Arsi'),
});

// Moderator registering farmer (same schema, explicit assigned password)
export const moderatorRegisterFarmer = farmerSignUp;

// Backwards-compatible alias for signUp
export const signUp = farmerSignUp;

// Login can be via Phone, Fayda ID, or Email
export const regular = z.object({
  identifier: z.string({ required_error: 'Phone, Fayda ID, or Email is required' })
    .trim()
    .min(1, 'Login identifier cannot be empty')
    .optional(),
  
  // Also accept email or phone if passed directly
  email: z.string().trim().optional(),
  phone: z.string().trim().optional(),

  password: z.string({ required_error: 'Password is required' })
    .min(1, 'Password cannot be empty'),
}).refine(data => data.identifier || data.email || data.phone, {
  message: 'Must provide phone number, Fayda ID, or email to log in',
  path: ['identifier'],
});
