import express from 'express';
import * as authController from '../controllers/authController.js';
import { authToken, requireRole } from '../middleware/authjwt.js';
import limitAuth from '../middleware/ratelimiter.js';
import { validate, farmerSignUp, moderatorRegisterFarmer, regular } from '../middleware/GeneralZOD.js';

const auth = express.Router();

// Farmer self-signup
auth.post('/signup', limitAuth, validate(farmerSignUp), authController.signUpC);

// Unified login for Farmer or Moderator
auth.post('/login', limitAuth, validate(regular), authController.logInC);

// Token refresh & logout
auth.post('/refresh-token', limitAuth, authController.refreshTokenC);
auth.post('/logout', authToken, authController.logOutC);

// Moderator: 3 Regional Cards and Readings
auth.get('/moderator/summary', authController.getModeratorSummaryC);

// Moderator: Register Farmer (with assigned password)
auth.post('/moderator/register-farmer', validate(moderatorRegisterFarmer), authController.registerFarmerByModeratorC);

// Moderator: Get list of registered farmers
auth.get('/moderator/farmers', authController.getFarmersListC);

export default auth;
