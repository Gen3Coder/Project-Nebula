import express from 'express';
import {
  getCropHealthC,
  getGridAnalysisC,
  getRegionalHistoryC,
  sendCropHealthSMSC,
} from '../controllers/cropHealthController.js';

const router = express.Router();

// React Frontend Endpoint for connection testing
router.get('/mock/crops/:id/health', getCropHealthC);

// Production Crop Health Endpoint
router.get('/crops/health', getCropHealthC);

// Grid Analysis Endpoint
router.get('/crops/grids/:farmId', getGridAnalysisC);
router.get('/crops/grids', getGridAnalysisC);

// Regional History Endpoint (Past Logs from Database)
router.get('/crops/history', getRegionalHistoryC);

// SMS Broadcast Endpoint
router.post('/crops/send-sms', sendCropHealthSMSC);
router.post('/moderator/send-sms', sendCropHealthSMSC);

export default router;
