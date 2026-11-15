import dotenv from 'dotenv';
dotenv.config();
import { pool } from './db.js';
import { evaluateCropHealthRules } from './services/cropHealthRegionalAssesmentService.js';

const RAW_API = process.env.API || 'https://project-nebula-3.onrender.com';
const API = RAW_API.trim().replace(/\/docs\/?$/, '').replace(/\/+$/, '');

const REGIONS = [
  { id: 1, name: 'Arsi', remoteZone: 'Arsi', crop: 'Wheat' },
  { id: 2, name: 'Jimma', remoteZone: 'Jimma', crop: 'Coffee' },
  { id: 3, name: 'Bale', remoteZone: 'Bale,Robe', crop: 'Wheat' },
];

async function seedRealHistory() {
  try {
    console.log('1. Deleting old mock data from regional_health_logs...');
    const delRes = await pool.query('DELETE FROM regional_health_logs');
    console.log(`Deleted ${delRes.rowCount} mock rows.`);

    for (const reg of REGIONS) {
      console.log(`Fetching 30 days history from ${API} for ${reg.name} (${reg.remoteZone})...`);
      
      const [rainRes, tempRes, humRes, soilRes] = await Promise.all([
        fetch(`${API}/history/${encodeURIComponent(reg.remoteZone)}?variable=rainfall&limit=30`).then(r => r.json()),
        fetch(`${API}/history/${encodeURIComponent(reg.remoteZone)}?variable=temperature&limit=30`).then(r => r.json()),
        fetch(`${API}/history/${encodeURIComponent(reg.remoteZone)}?variable=humidity&limit=30`).then(r => r.json()),
        fetch(`${API}/history/${encodeURIComponent(reg.remoteZone)}?variable=soil_moisture&limit=30`).then(r => r.json()).catch(() => ({ data: [] })),
      ]);

      const rainMap = new Map((rainRes.data || []).map(d => [d.date, Number(d.rain_mm_day || 0)]));
      const tempMap = new Map((tempRes.data || []).map(d => [d.date, Number(d.T2M ?? d.temperature ?? 18)]));
      const humMap = new Map((humRes.data || []).map(d => [d.date, Number(d.RH2M ?? d.humidity ?? 65)]));
      const soilMap = new Map((soilRes.data || []).map(d => [d.date, Number(((d.GWETROOT ?? d.GWETTOP ?? 0.45) * 100).toFixed(2))]));

      // Get sorted unique dates
      const allDates = Array.from(new Set([...rainMap.keys(), ...tempMap.keys()])).sort();
      console.log(`Found ${allDates.length} historical dates for ${reg.name}.`);

      for (const d of allDates) {
        const rainfall = Number((rainMap.get(d) ?? 0).toFixed(2));
        const temperature = Number((tempMap.get(d) ?? 18).toFixed(2));
        const humidity = Number((humMap.get(d) ?? 65).toFixed(2));
        const soil_moisture = Number((soilMap.get(d) ?? 45).toFixed(2));
        const ndvi = 0.52;
        const vegetation_coverage = 52.0;

        const diagnosis = evaluateCropHealthRules({
          temperature,
          humidity,
          soil_moisture,
          rainfall,
          ndvi,
        }, reg.crop);

        await pool.query(
          `INSERT INTO regional_health_logs (
            region_id, crop, temperature, humidity, soil_moisture, rainfall,
            vegetation_coverage, ndvi, health_score, status, primary_stress_factor,
            recommendation, recorded_at
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)`,
          [
            reg.id,
            reg.crop,
            temperature,
            humidity,
            soil_moisture,
            rainfall,
            vegetation_coverage,
            ndvi,
            diagnosis.healthScore,
            diagnosis.status,
            diagnosis.primaryStressFactor,
            diagnosis.recommendation,
            new Date(`${d}T12:00:00Z`),
          ]
        );
      }
      console.log(`Inserted ${allDates.length} rows for ${reg.name}.`);
    }

    const check = await pool.query('SELECT region_id, COUNT(*) as cnt, MIN(recorded_at) as earliest, MAX(recorded_at) as latest FROM regional_health_logs GROUP BY region_id ORDER BY region_id');
    console.log('Database summary after seeding:');
    console.table(check.rows);
  } catch (err) {
    console.error('Seed error:', err);
  } finally {
    await pool.end();
  }
}

seedRealHistory();
