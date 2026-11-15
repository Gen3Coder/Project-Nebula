import { fetchAPIDataS } from './APIServices.js';
import { insertRegionalHealthLogQ } from '../repositories/regionalHealthRepository.js';
// Default crops for each zone
const REGION_CROPS = {
  Arsi: 'WHEAT',
  Bale: 'WHEAT',
  Jimma: 'COFFEE',
};

// Agronomic recommendations
const STRESS_RECOMMENDATIONS = {
  WHEAT: {
    'DROUGHT': 'Soil moisture depleted for wheat root zone. Supplementary irrigation recommended.',
    'HEAT STRESS': 'Temperatures exceed 26°C. High heat stresses developing wheat seedlings.',
    'WATERLOGGING': 'Excess rainfall detected. Open drainage ditches to prevent root rot.',
    'LOW VEGETATION': 'Abnormally low NDVI. Inspect field for rust or nutrient deficiencies.',
    'NONE': 'Optimal wheat growing conditions in this region.',
  },
  COFFEE: {
    'FUNGAL RISK': 'High humidity and warm temperatures increase Coffee Berry Disease risk. Spray copper fungicides.',
    'DROUGHT': 'Topsoil moisture is critical. Water nursery beds and maintain shade cover.',
    'HEAT STRESS': 'Direct heat exposure causes blossom abort. Ensure shade tree canopy is maintained.',
    'WATERLOGGING': 'Volcanic soils saturated. Improve trench drainage around tree basins.',
    'LOW VEGETATION': 'Canopy density low. Prune dead branches and apply organic compost.',
    'NONE': 'Optimal coffee development conditions in this forest zone.',
  },
};

//Diagnostic scoring engine for Wheat & Coffee. Reused by both Regional and Grid-level services.
export const evaluateCropHealthRules = (metrics, cropType = 'WHEAT') => {
  const crop = cropType.toUpperCase();
  const { temperature, humidity, soil_moisture, ndvi, rainfall = 0 } = metrics;
  
  let score = 100;
  const detectedStresses = [];

  if (crop === 'COFFEE') {
    if (humidity > 75 && temperature > 22) {
      score -= 40;
      detectedStresses.push({ factor: 'FUNGAL RISK', severity: 40 });
    }
    if (soil_moisture < 30) {
      score -= 35;
      detectedStresses.push({ factor: 'DROUGHT', severity: 35 });
    }
    if (temperature > 30) {
      score -= 30;
      detectedStresses.push({ factor: 'HEAT STRESS', severity: 30 });
    }
    if (ndvi < 0.45) {
      score -= 30;
      detectedStresses.push({ factor: 'LOW VEGETATION', severity: 30 });
    }
    if (soil_moisture > 90 || rainfall > 60) {
      score -= 35;
      detectedStresses.push({ factor: 'WATERLOGGING', severity: 35 });
    }
  } else {
    // WHEAT (Arsi & Bale)
    if (soil_moisture < 25) {
      score -= 40;
      detectedStresses.push({ factor: 'DROUGHT', severity: 40 });
    }
    if (temperature > 26) {
      score -= 30;
      detectedStresses.push({ factor: 'HEAT STRESS', severity: 30 });
    }
    if (ndvi < 0.35) {
      score -= 30;
      detectedStresses.push({ factor: 'LOW VEGETATION', severity: 30 });
    }
    if (soil_moisture > 85 || rainfall > 50) {
      score -= 35;
      detectedStresses.push({ factor: 'WATERLOGGING', severity: 35 });
    }
  }

  score = Math.max(0, Math.min(100, score));

  let status = 'HEALTHY';
  if (score < 50) {
    status = 'FAILING';
  } else if (score < 75) {
    status = 'STRESSED';
  }

  let primaryStressFactor = 'NONE';
  if (status !== 'HEALTHY' && detectedStresses.length > 0) {
    detectedStresses.sort((a, b) => b.severity - a.severity);
    primaryStressFactor = detectedStresses[0].factor;
  }

  const recommendation =
    STRESS_RECOMMENDATIONS[crop]?.[primaryStressFactor] ||
    STRESS_RECOMMENDATIONS[crop]?.['NONE'];

  return {
    healthScore: score,
    status,
    primaryStressFactor,
    recommendation,
  };
};

// Directly pulls API data for Arsi, Bale, or Jimma and evaluates health.
 
export const getRegionalCropHealthS = async (regionIdentifier = 'Arsi', customCrop = null) => {
  const apiMetrics = await fetchAPIDataS(regionIdentifier);
  const crop = (customCrop || REGION_CROPS[apiMetrics.zone] || 'WHEAT').toUpperCase();
  const diagnosis = evaluateCropHealthRules(apiMetrics, crop);
  // Map zone to region_id (1: Arsi, 2: Jimma, 3: Bale)
  const regionMap = { Arsi: 1, Jimma: 2, Bale: 3 };
  const region_id = regionMap[apiMetrics.zone] || 1;

  await insertRegionalHealthLogQ({
    region_id,                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          
    crop: crop === 'COFFEE' ? 'Coffee' : 'Wheat',
    temperature: apiMetrics.temperature,
    humidity: apiMetrics.humidity,
    soil_moisture: apiMetrics.soil_moisture,
    rainfall: apiMetrics.rainfall,
    vegetation_coverage: apiMetrics.vegetation_coverage,
    ndvi: apiMetrics.ndvi,
    health_score: diagnosis.healthScore,
    status: diagnosis.status,
    primary_stress_factor: diagnosis.primaryStressFactor,
    recommendation: diagnosis.recommendation,
  });
  return {
    success: true,
    data: {
      region: apiMetrics.zone,
      crop: crop === 'COFFEE' ? 'Coffee' : 'Wheat',
      status: diagnosis.status === 'FAILING' ? 'Critical' : diagnosis.status === 'STRESSED' ? 'Warning' : 'Healthy',
      healthScore: diagnosis.healthScore,
      primaryStressFactor: diagnosis.primaryStressFactor,
      recommendation: diagnosis.recommendation,
      metrics: {
        soilMoisture: apiMetrics.soil_moisture,
        temperature: apiMetrics.temperature,
        humidity: apiMetrics.humidity,
        windSpeed: 12,
        rainfall: apiMetrics.rainfall,
        ndvi: apiMetrics.ndvi,
      },
    },
  };
};