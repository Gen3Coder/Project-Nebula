import { getRegionalCropHealthS } from '../services/cropHealthRegionalAssesmentService.js';
import {
  getRegionalHealthHistoryQ,
  getRecentRainfallHistoryQ,
} from '../repositories/regionalCropHealthRepository.js';
import { resolveRegionId } from '../services/APIServices.js';
import {
  sendCropHealthSMSToAllFarmers,
  sendRegionalCropHealthSMS,
} from '../services/smsService.js';

/**
 * Controller: GET /api/mock/crops/:id/health  (Or /api/crops/health)
 *
 * Returns:
 *   1. Regional Assessment from live RainGuard Ethiopia API
 *   2. Real rainfall history array to plot graphs
 *   3. Crop health diagnosis and recommendations
 */
export const getCropHealthC = async (req, res) => {
  try {
    const region = req.query.region || req.params.region || 'Arsi';
    const crop = req.query.crop || null;

    // Fetch live API Regional Assessment & DB rainfall history
    const regionalData = await getRegionalCropHealthS(region, crop);

    return res.status(200).json({
      success: true,
      gridAnalysis: {
        available: false,
        message: 'Sub-grid analysis aggregated to regional telemetry',
        note: 'Displaying live regional satellite and climate assessment.',
      },
      regionalAssessment: regionalData.data,
      // Root-level 'data' keeps full compatibility with React App.jsx
      data: {
        ...regionalData.data,
      },
    });
  } catch (error) {
    console.error('Error in getCropHealthC:', error.message);
    return res.status(500).json({
      success: false,
      message: `Failed to fetch crop health for region ${req.query.region || 'Arsi'}`,
      error: error.message,
    });
  }
};

/**
 * Controller: GET /api/crops/grids/:farmId
 */
export const getGridAnalysisC = async (req, res) => {
  return res.status(200).json({
    success: false,
    available: false,
    message: 'Sub-grid analysis aggregated to regional telemetry',
    recommendation: 'Use Regional Assessment for real-time Arsi, Bale, and Jimma climate data.',
  });
};

/**
 * Controller: GET /api/crops/history
 * Retrieves saved history from `regional_health_logs` for trends and rainfall charts
 */
export const getRegionalHistoryC = async (req, res) => {
  try {
    const rawRegion = req.query.regionId || req.query.region || 1;
    const regionId = resolveRegionId(rawRegion);
    const limit = Number(req.query.limit) || 14;

    const [history, rainfallRecords] = await Promise.all([
      getRegionalHealthHistoryQ(regionId, limit),
      getRecentRainfallHistoryQ(regionId, limit),
    ]);

    return res.status(200).json({
      success: true,
      regionId,
      count: history.length,
      data: history,
      rainfallHistory: rainfallRecords.map((r) => r.rainfall),
      rainfallRecords,
    });
  } catch (error) {
    console.error('Error in getRegionalHistoryC:', error.message);
    return res.status(500).json({
      success: false,
      message: 'Failed to retrieve regional health history',
      error: error.message,
    });
  }
};

/**
 * Controller: POST /api/crops/send-sms or /api/moderator/send-sms
 * Dispatches crop health report SMS to enrolled farmers
 */
export const sendCropHealthSMSC = async (req, res) => {
  try {
    const regionId = req.body?.regionId || req.query?.regionId;
    let result;

    if (regionId) {
      result = await sendRegionalCropHealthSMS(Number(regionId));
    } else {
      result = await sendCropHealthSMSToAllFarmers();
    }

    if (!result.success) {
      const firstError = result.errors?.[0]?.error || 'Failed to dispatch SMS';
      return res.status(400).json({
        success: false,
        message: firstError,
        data: result,
      });
    }

    return res.status(200).json({
      success: true,
      message: 'Crop health SMS broadcast sent successfully',
      data: result,
    });
  } catch (error) {
    console.error('Error in sendCropHealthSMSC:', error.message);
    return res.status(500).json({
      success: false,
      message: 'Failed to send crop health SMS broadcast',
      error: error.message,
    });
  }
};
