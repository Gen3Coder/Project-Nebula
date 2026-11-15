import { pool } from '../db.js';

// Saves a regional data from API
 
export const insertRegionalHealthLogQ = async ({
  region_id,
  crop,
  temperature,
  humidity,
  soil_moisture,
  rainfall ,
  vegetation_coverage,
  ndvi,
  health_score,
  status,
  primary_stress_factor = 'NONE',
  recommendation = '',
}) => {
  const query = `INSERT INTO regional_health_logs (
      region_id, crop, temperature, humidity, soil_moisture, rainfall,
      vegetation_coverage, ndvi, health_score, status, primary_stress_factor, recommendation )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
    RETURNING *;`;

  const values = [
    region_id,
    crop,
    temperature,
    humidity,
    soil_moisture,
    rainfall,
    vegetation_coverage,
    ndvi,
    health_score,
    status,
    primary_stress_factor,
    recommendation,
  ];

  const { rows } = await pool.query(query, values);
  return rows[0];
};

// Retrieves the last N historical records for a region to power trend charts (e.g. 14 days)
 
export const getRegionalHealthHistoryQ = async (region_id, limit = 14) => {
  const query = `SELECT id, crop, temperature, humidity, soil_moisture, rainfall,
      vegetation_coverage, ndvi, health_score, status,
      primary_stress_factor, recommendation, recorded_at
    FROM regional_health_logs
    WHERE region_id = $1
    ORDER BY recorded_at DESC
    LIMIT $2;`;

  const { rows } = await pool.query(query, [region_id, limit]);
  return rows;
};