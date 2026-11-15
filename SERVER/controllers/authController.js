import * as authServices from '../services/authServices.js';
import { fetchAPIDataS } from '../services/APIServices.js';
import { evaluateCropHealthRules } from '../services/cropHealthRegionalAssesmentService.js';
import { asyncHandler } from '../utils/asyncHandler.js';
import { env } from '../utils/env.js';

const COOKIE_OPTIONS = {
  httpOnly: true,
  secure: env.NODE_ENV === 'production',
  sameSite: 'lax',
  maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
};

export const signUpC = asyncHandler(async (req, res) => {
  const result = await authServices.signUpS({
    firstName: req.body.firstName,
    fatherName: req.body.fatherName,
    phone: req.body.phone,
    faydaId: req.body.faydaId,
    email: req.body.email,
    password: req.body.password,
    region: req.body.region || 'Arsi',
    role: 'farmer',
    registeredBy: 'self',
  });

  if (result.refreshToken) {
    res.cookie('refreshToken', result.refreshToken, COOKIE_OPTIONS);
  }

  res.status(201).json({
    success: true,
    ...result,
  });
});

export const registerFarmerByModeratorC = asyncHandler(async (req, res) => {
  const result = await authServices.signUpS({
    firstName: req.body.firstName,
    fatherName: req.body.fatherName,
    phone: req.body.phone,
    faydaId: req.body.faydaId,
    email: req.body.email,
    password: req.body.password,
    region: req.body.region || 'Arsi',
    role: 'farmer',
    registeredBy: 'moderator',
  });

  res.status(201).json({
    success: true,
    message: `Farmer ${result.user.fullName} registered successfully by moderator.`,
    user: result.user,
  });
});

export const logInC = asyncHandler(async (req, res) => {
  const identifier = req.body.identifier || req.body.phone || req.body.email;
  const result = await authServices.logInS({
    identifier,
    password: req.body.password,
  });

  if (result.refreshToken) {
    res.cookie('refreshToken', result.refreshToken, COOKIE_OPTIONS);
  }

  res.status(200).json({
    success: true,
    ...result,
  });
});

export const refreshTokenC = asyncHandler(async (req, res) => {
  const incomingRefreshToken = req.cookies?.refreshToken || req.body?.refreshToken;
  const result = await authServices.refreshTokenS(incomingRefreshToken);

  if (result.refreshToken) {
    res.cookie('refreshToken', result.refreshToken, COOKIE_OPTIONS);
  }

  res.status(200).json({
    success: true,
    ...result,
  });
});

export const logOutC = asyncHandler(async (req, res) => {
  const incomingRefreshToken = req.cookies?.refreshToken;
  const userId = req.user?.userId;

  const result = await authServices.logOutS(incomingRefreshToken, userId);

  const clearCookieOptions = {
    httpOnly: true,
    secure: env.NODE_ENV === 'production',
    sameSite: 'lax',
  };

  res.clearCookie('refreshToken', clearCookieOptions);
  res.clearCookie('accessToken', clearCookieOptions);

  res.status(200).json({
    success: true,
    ...result,
  });
});

export const getFarmersListC = asyncHandler(async (req, res) => {
  const farmers = await authServices.getFarmersListS();
  res.status(200).json({
    success: true,
    count: farmers.length,
    farmers,
  });
});

/**
 * Controller for Moderator Page:
 * Returns the 3 regional cards (Arsi, Bale, Jimma) and their current readings
 */
export const getModeratorSummaryC = asyncHandler(async (req, res) => {
  const regionConfigs = [
    { name: 'Arsi', crop: 'WHEAT', zone: 'Highland / Cool Sub-humid' },
    { name: 'Bale', crop: 'WHEAT', zone: 'Highland / Semi-arid Plateau' },
    { name: 'Jimma', crop: 'COFFEE', zone: 'Highland / Humid Tropical Forest' },
  ];

  const regionsData = await Promise.all(
    regionConfigs.map(async (r) => {
      const metrics = await fetchAPIDataS(r.name);
      const diagnosis = evaluateCropHealthRules(metrics, r.crop);
      return {
        region: r.name,
        primaryCrop: r.crop === 'COFFEE' ? 'Coffee' : 'Wheat',
        zone: r.zone,
        status: diagnosis.status === 'FAILING' ? 'Critical' : diagnosis.status === 'STRESSED' ? 'Warning' : 'Healthy',
        healthScore: diagnosis.healthScore,
        primaryStressFactor: diagnosis.primaryStressFactor,
        recommendation: diagnosis.recommendation,
        metrics: {
          soilMoisture: metrics.soil_moisture,
          temperature: metrics.temperature,
          humidity: metrics.humidity,
          windSpeed: 12,
          rainfall: metrics.rainfall,
          ndvi: metrics.ndvi,
        },
      };
    })
  );

  res.status(200).json({
    success: true,
    regions: regionsData,
  });
});
