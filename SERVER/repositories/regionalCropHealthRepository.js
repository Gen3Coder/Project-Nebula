import { pool } from '../db.js';

// Saves a regional health log into the database
export const insertRegionalHealthLogQ = async ({
  region_id,
  crop,
  temperature,
  humidity,
  soil_moisture,
  rainfall = 0.0,
  vegetation_coverage,
  ndvi,
  health_score,
  status,
  primary_stress_factor = 'NONE',
  recommendation = '',
  recorded_at = null,
}) => {
  const query = `INSERT INTO regional_health_logs (
      region_id, crop, temperature, humidity, soil_moisture, rainfall,
      vegetation_coverage, ndvi, health_score, status, primary_stress_factor, recommendation, recorded_at )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, COALESCE($13, CURRENT_TIMESTAMP))
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
    recorded_at,
  ];

  const { rows } = await pool.query(query, values);
  return rows[0];
};

// Retrieves the last N historical records for a region
export const getRegionalHealthHistoryQ = async (region_id, limit = 14) => {
  const query = `SELECT id, region_id, crop, temperature, humidity, soil_moisture, rainfall,
      vegetation_coverage, ndvi, health_score, status,
      primary_stress_factor, recommendation, recorded_at
    FROM regional_health_logs
    WHERE region_id = $1
    ORDER BY recorded_at DESC
    LIMIT $2;`;

  const { rows } = await pool.query(query, [region_id, limit]);
  return rows;
};

// Retrieves chronological rainfall history (oldest to newest) to power graphs
export const getRecentRainfallHistoryQ = async (region_id, limit = 14) => {
  const query = `
    SELECT TO_CHAR(recorded_at, 'YYYY-MM-DD') AS date, rainfall
    FROM (
      SELECT recorded_at, rainfall
      FROM regional_health_logs
      WHERE region_id = $1
      ORDER BY recorded_at DESC
      LIMIT $2
    ) sub
    ORDER BY recorded_at ASC;
  `;

  const { rows } = await pool.query(query, [region_id, limit]);
  return rows.map((r) => ({
    date: r.date,
    rainfall: Number(parseFloat(r.rainfall || 0).toFixed(1)),
  }));
};

// Delete old / mock logs for clean reset if needed
export const clearRegionalHealthLogsQ = async (region_id = null) => {
  if (region_id) {
    const { rowCount } = await pool.query('DELETE FROM regional_health_logs WHERE region_id = $1', [region_id]);
    return rowCount;
  }
  const { rowCount } = await pool.query('DELETE FROM regional_health_logs');
  return rowCount;
};
