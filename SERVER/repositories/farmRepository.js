import db from '../db.js';

/**
 * Retrieves a region using its database ID.
 *
 * @param {number} regionId
 * @returns {Promise<Object|null>}
 */
export const getRegionByIdQ = async (regionId) => {
  const query = `
    SELECT
      id,
      name,
      primary_crop,
      primary_crop AS crop,
      climate_zone,
      center_latitude,
      center_longitude
    FROM regions
    WHERE id = $1;
  `;

  const result = await db.query(query, [regionId]);
  return result.rows[0] || null;
};

/**
 * Retrieves all farmers registered in a selected region.
 * Checks the farms table first, and falls back to enrolled farmers in the users table.
 *
 * @param {number} regionId
 * @returns {Promise<Array<Object>>}
 */
export const getFarmRecipientsByRegionIdQ = async (regionId) => {
  // 1. Try retrieving from farms table joined with users
  const farmsQuery = `
    SELECT
      f.id AS farm_id,
      COALESCE(CONCAT(u.first_name, ' ', u.father_name), f.name) AS owner_name,
      COALESCE(CONCAT(u.first_name, ' ', u.father_name), f.name) AS name,
      u.first_name,
      u.user_id AS farmer_id,
      COALESCE(u.phone, '') AS owner_phone_number,
      COALESCE(u.phone, '') AS phone,
      f.crop_type,
      r.name AS region_name,
      r.id AS region_id
    FROM farms f
    LEFT JOIN users u ON f.farmer_id = u.user_id
    LEFT JOIN regions r ON f.region_id = r.id
    WHERE f.region_id = $1
      AND u.phone IS NOT NULL
      AND TRIM(u.phone) <> ''
    ORDER BY f.id ASC;
  `;

  const farmsResult = await db.query(farmsQuery, [regionId]);
  if (farmsResult.rows.length > 0) {
    return farmsResult.rows;
  }

  // 2. Fallback: Retrieve directly from users enrolled in this region
  const usersQuery = `
    SELECT
      u.user_id AS farm_id,
      u.user_id AS farmer_id,
      CONCAT(u.first_name, ' ', u.father_name) AS owner_name,
      CONCAT(u.first_name, ' ', u.father_name) AS name,
      u.first_name,
      u.phone AS owner_phone_number,
      u.phone,
      COALESCE(r.primary_crop, CASE WHEN LOWER(u.region) = 'jimma' THEN 'Coffee' ELSE 'Wheat' END) AS crop_type,
      COALESCE(r.name, u.region) AS region_name,
      COALESCE(r.id, $1) AS region_id
    FROM users u
    LEFT JOIN regions r ON LOWER(TRIM(r.name)) = LOWER(TRIM(u.region))
    WHERE (r.id = $1 OR LOWER(TRIM(u.region)) = (SELECT LOWER(TRIM(name)) FROM regions WHERE id = $1))
      AND u.role = 'farmer'
      AND u.phone IS NOT NULL
      AND TRIM(u.phone) <> ''
    ORDER BY u.user_id ASC;
  `;

  const usersResult = await db.query(usersQuery, [regionId]);
  return usersResult.rows;
};

/**
 * Retrieves every single enrolled farmer in the system across all regions.
 *
 * @returns {Promise<Array<Object>>}
 */
export const getAllFarmerRecipientsQ = async () => {
  const query = `
    SELECT
      u.user_id AS farmer_id,
      u.user_id AS farm_id,
      CONCAT(u.first_name, ' ', u.father_name) AS owner_name,
      CONCAT(u.first_name, ' ', u.father_name) AS name,
      u.first_name,
      u.phone AS owner_phone_number,
      u.phone,
      u.region,
      COALESCE(r.id, CASE WHEN LOWER(u.region) = 'jimma' THEN 2 WHEN LOWER(u.region) = 'bale' THEN 3 ELSE 1 END) AS region_id,
      COALESCE(r.name, u.region) AS region_name,
      COALESCE(r.primary_crop, CASE WHEN LOWER(u.region) = 'jimma' THEN 'Coffee' ELSE 'Wheat' END) AS crop_type
    FROM users u
    LEFT JOIN regions r ON LOWER(TRIM(r.name)) = LOWER(TRIM(u.region))
    WHERE u.role = 'farmer'
      AND u.phone IS NOT NULL
      AND TRIM(u.phone) <> ''
    ORDER BY u.user_id ASC;
  `;

  const result = await db.query(query);
  return result.rows;
};
