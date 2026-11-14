import db from '../db.js';

export const insertGridsBatchQ = async (grids) => {

  if (!grids || !Array.isArray(grids) || grids.length === 0) {
    return [];
  }

  const values = [];
  const valueRows = [];

 
  grids.forEach((grid, index) => {
    const offset = index * 6;
    valueRows.push(
      `($${offset + 1}, $${offset + 2}, $${offset + 3}, $${offset + 4}, $${offset + 5}, $${offset + 6})`
    );

    values.push(
      grid.farm_id,
      grid.grid_code,
      grid.min_lat,
      grid.max_lat,
      grid.min_lon,
      grid.max_lon
    );
  });

  const query = `
    INSERT INTO grids (
      farm_id,
      grid_code,
      min_lat,
      max_lat,
      min_lon,
      max_lon
    )
    VALUES ${valueRows.join(', ')}
    RETURNING *;
  `;

  try {
    const result = await db.query(query, values);
    return result.rows;
  } catch (error) {
    console.error('Error batch inserting grids:', error.message);
    throw error;
  }
};


export const getGridsByFarmIdQ = async (farmId) => {
  const query = `
    SELECT *
    FROM grids
    WHERE farm_id = $1
    ORDER BY grid_code ASC;
  `;

  const result = await db.query(query, [farmId]);
  return result.rows;
};