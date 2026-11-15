import {findDyingGridsByFarmQ,insertHealthLogQ,readingsForGridsOnFarmQ} from '../repositories/cropHealthRepository.js';
import { getGridsByFarmIdQ } from '../repositories/gridRepository.js';
import { fetchAPIDataS } from './APIServices.js';
import { evaluateCropHealthRules } from './cropHealthRegionalAssesmentService.js';

// Gets the latest database readings for all grids on a farm.
 
export const getFarmGridHealthS = async (farmId) => {
  return readingsForGridsOnFarmQ(farmId);};

//Finds all failing grids on a farm for alert notifications.
 
export const findDyingGridsByFarmS = async (farmId) => {
  return findDyingGridsByFarmQ(farmId);};

// Detailed Grid Sync:
// Takes regional API data, applies micro-climate jitter per grid,
 // runs diagnosis, and saves records into the database.
 
export const syncFarmHealthFromApi = async (farmId, regionId = 1, cropType = 'WHEAT') => {
  const baseMetrics = await fetchAPIDataS(regionId);
  const grids = await getGridsByFarmIdQ(farmId);

  if (!grids || grids.length === 0) {
    return [];
  }

  // Process all grids in parallel
  const logPromises = grids.map(async (grid) => {
    // Spatial micro-climate jitter for sub-plots
    const rawNdvi = (baseMetrics.ndvi ?? 0.5) + (Math.random() * 0.04 - 0.02);
    const ndvi = Number(Math.max(-1.0, Math.min(1.0, rawNdvi)).toFixed(3));

    const rawMoisture = (baseMetrics.soil_moisture ?? 40) + (Math.random() * 4 - 2);
    const soil_moisture = Number(Math.max(0, Math.min(100, rawMoisture)).toFixed(2));

    const vegetation_coverage = Math.max(
      0,
      Math.min(100, Number(((ndvi + 1) / 2 * 100).toFixed(2)))
    );

    const gridMetrics = {
      temperature: Number(baseMetrics.temperature || 0),
      humidity: Math.max(0, Math.min(100, Number(baseMetrics.humidity || 0))),
      rainfall: Math.max(0, Number(baseMetrics.rainfall || 0)),
      soil_moisture,
      ndvi,
      vegetation_coverage,
    };

    const diagnosis = evaluateCropHealthRules(gridMetrics, cropType);

    return insertHealthLogQ({
      grid_id: grid.id,
      ...gridMetrics,
      health_score: diagnosis.healthScore,
      status: diagnosis.status, // 'HEALTHY', 'STRESSED', or 'FAILING'
      primary_stress_factor: diagnosis.primaryStressFactor,
    });
  });

  return Promise.all(logPromises);
};