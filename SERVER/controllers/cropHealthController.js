import { getRegionalCropHealthS } from '../services/cropHealthRegionalAssesmentService.js';
import { getRegionalHealthHistoryQ } from '../repositories/regionalCropHealthRepository.js';

/**
 * Controller: GET /api/mock/crops/:id/health  (Or /api/crops/health)
 *
 * Returns:
 *   1. Regional Assessment from live API
 *   2. Hardcoded notice that grid analysis was bypassed
 */
export const getCropHealthC = async (req, res) => {
  try {
    const region = req.query.region || req.params.region || 'Arsi';
    const crop = req.query.crop || null;

    // 1. Fetch live API Regional Assessment
    const regionalData = await getRegionalCropHealthS(region, crop);

    // 2. Return both the live Regional Assessment and the Grid note
    return res.status(200).json({
      success: true,
      gridAnalysis: {
        available: false,
        message: 'Data pulling took Wayyy too long for grid analysis',
        note: 'Sub-grid satellite pipeline requires 5+ days. Displaying regional area assessment instead.',
      },
      regionalAssessment: regionalData.data,
      // Root-level 'data' keeps full compatibility with your current React App.jsx
      data: {
        ...regionalData.data,
        gridNotice: 'Data pulling took Wayyy too long for grid analysis',
      },
    });
  } catch (error) {
    console.error('Error in getCropHealthC:', error.message);
    return res.status(500).json({
      success: false,
      gridAnalysis: {
        available: false,
        message: 'Data pulling took Wayyy too long for grid analysis',
      },
      message: `Failed to fetch crop health for region ${req.query.region || 'Arsi'}`,
      error: error.message,
    });
  }
};

/**
 * Controller: GET /api/crops/grids/:farmId
 * Hardcoded response for explicit grid requests
 */
export const getGridAnalysisC = async (req, res) => {
  return res.status(200).json({
    success: false,
    available: false,
    message: 'Data pulling took Wayyy too long for grid analysis',
    recommendation: 'Use Regional Assessment for real-time Arsi, Bale, and Jimma climate data.',
  });
};

/**
 * Controller: GET /api/crops/history
 * Retrieves saved history from `regional_health_logs` for trends and charts
 */
export const getRegionalHistoryC = async (req, res) => {
  try {
    const regionNameMap = { arsi: 1, jimma: 2, bale: 3 };
    const rawRegion = req.query.regionId || req.query.region || 1;
    const regionId = typeof rawRegion === 'string' && isNaN(Number(rawRegion))
      ? regionNameMap[rawRegion.toLowerCase()] || 1
      : Number(rawRegion) || 1;

    const limit = Number(req.query.limit) || 14;
    const history = await getRegionalHealthHistoryQ(regionId, limit);

    return res.status(200).json({
      success: true,
      regionId,
      count: history.length,
      data: history,
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