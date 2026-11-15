import db from '../db.js';

/**
 * Retrieves a region using its database ID.
 *
 * @param {number} regionId
 * @returns {Promise<Object|null>}
 */
export const getRegionByIdQ = async (regionId) => {
  const query = `
    SELECT id, name, crop
    FROM regions
    WHERE id = $1;
  `;

  const result = await db.query(query, [regionId]);

  return result.rows[0] || null;
};

/**
 * Retrieves all farmers registered in a selected region.
 *
 * @param {number} regionId
 * @returns {Promise<Array<Object>>}
 */
export const getFarmRecipientsByRegionIdQ = async (regionId) => {
  const query = `
    SELECT
      id AS farm_id,
      owner_name,
      owner_phone_number,
      crop_type
    FROM farms
    WHERE region_id = $1
      AND owner_phone_number IS NOT NULL
      AND TRIM(owner_phone_number) <> ''
    ORDER BY id ASC;
  `;

  const result = await db.query(query, [regionId]);

  return result.rows;
};
