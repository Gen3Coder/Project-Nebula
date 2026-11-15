import dotenv from 'dotenv';
dotenv.config();

const RAW_API = process.env.API || 'https://project-nebula-3.onrender.com';
export const API = RAW_API.trim().replace(/\/docs\/?$/, '').replace(/\/+$/, '');

export const ZONE_NAMES = {
  1: 'Arsi',
  2: 'Jimma',
  3: 'Bale,Robe',
  arsi: 'Arsi',
  jimma: 'Jimma',
  bale: 'Bale,Robe',
  'bale,robe': 'Bale,Robe',
};

// Maps remote zone name back to local database region name
export const DB_REGION_NAMES = {
  'Arsi': 'Arsi',
  'Jimma': 'Jimma',
  'Bale,Robe': 'Bale',
  'Bale': 'Bale',
};

export const REGION_ID_MAP = {
  arsi: 1,
  jimma: 2,
  bale: 3,
  'bale,robe': 3,
  '1': 1,
  '2': 2,
  '3': 3,
};

/**
 * Resolves region identifier to remote API zone name
 */
export const resolveRemoteZone = (regionIdentifier = 1) => {
  const key = typeof regionIdentifier === 'string' ? regionIdentifier.trim().toLowerCase() : regionIdentifier;
  return ZONE_NAMES[key] || 'Arsi';
};

/**
 * Resolves region identifier to database region ID (1: Arsi, 2: Jimma, 3: Bale)
 */
export const resolveRegionId = (regionIdentifier = 1) => {
  const key = typeof regionIdentifier === 'string' ? regionIdentifier.trim().toLowerCase() : String(regionIdentifier);
  return REGION_ID_MAP[key] || 1;
};

/**
 * Fetches the latest live climate and environmental summary for a region from the RainGuard Ethiopia API.
 */
export const fetchAPIDataS = async (regionIdentifier = 1) => {
  const zone = resolveRemoteZone(regionIdentifier);
  const dbRegion = DB_REGION_NAMES[zone] || zone;

  try {
    const summaryUrl = `${API}/summary/${encodeURIComponent(zone)}`;
    const res = await fetch(summaryUrl);

    if (!res.ok) {
      throw new Error(`Summary API fetch failed for zone ${zone} (status: ${res.status})`);
    }

    const summary = await res.json();

    const temperature = Number(summary.temperature?.value ?? summary.temperature ?? 18);
    const humidity = Number(summary.humidity?.value ?? summary.humidity ?? 65);

    if (isNaN(temperature) || isNaN(humidity)) {
      throw new Error(`API returned invalid temperature/humidity for ${zone}`);
    }

    // NASA POWER soil moisture is 0-1 wetness index; convert to percentage 0-100%
    const rawSoil = summary.soil_moisture?.root ?? summary.soil_moisture?.top ?? 0.45;
    const soil_moisture = Math.max(0, Math.min(100, Number((rawSoil * 100).toFixed(2))));

    const rainfall = Number(summary.rainfall?.value ?? 0.0);
    const rainfall_7d = Number(summary.rainfall?.last_7_days_mm ?? 0.0);
    const rainfall_30d = Number(summary.rainfall?.last_30_days_mm ?? 0.0);
    const elevation = Number(summary.elevation?.point_m ?? 2200);

    const ndvi = 0.52;
    const vegetation_coverage = Math.max(0, Math.min(100, Number((ndvi * 100).toFixed(2))));

    return {
      zone: dbRegion,
      remoteZone: zone,
      temperature,
      humidity,
      soil_moisture,
      rainfall,
      rainfall_7d,
      rainfall_30d,
      elevation,
      ndvi,
      vegetation_coverage,
      source: 'RainGuard Ethiopia API',
    };
  } catch (error) {
    console.warn(`[Climate API at ${API} unreachable for ${zone}: ${error.message}. Checking fallback]`);
    
    // Fallback if network issue
    const FALLBACKS = {
      Arsi: { temperature: 16.1, humidity: 73.5, soil_moisture: 47.0, ndvi: 0.52, rainfall: 0.0, rainfall_7d: 15.4, vegetation_coverage: 52.0 },
      Jimma: { temperature: 18.6, humidity: 81.8, soil_moisture: 66.0, ndvi: 0.65, rainfall: 4.0, rainfall_7d: 98.4, vegetation_coverage: 65.0 },
      'Bale,Robe': { temperature: 14.4, humidity: 87.7, soil_moisture: 67.0, ndvi: 0.45, rainfall: 0.0, rainfall_7d: 17.9, vegetation_coverage: 45.0 },
    };

    const fb = FALLBACKS[zone] || FALLBACKS.Arsi;
    return {
      zone: dbRegion,
      remoteZone: zone,
      ...fb,
      source: 'Cached Fallback',
    };
  }
};

/**
 * Fetches historical rainfall data from the live RainGuard Ethiopia API.
 */
export const fetchRainfallHistoryAPI = async (regionIdentifier = 1, limit = 14) => {
  const zone = resolveRemoteZone(regionIdentifier);
  try {
    const url = `${API}/history/${encodeURIComponent(zone)}?variable=rainfall&limit=${limit}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Rainfall history request failed with status: ${res.status}`);
    const data = await res.json();
    return (data.data || []).map((item) => ({
      date: item.date,
      rainfall: Number((item.rain_mm_day || 0).toFixed(1)),
      source: item.source || 'satellite',
    }));
  } catch (err) {
    console.warn(`Could not fetch rainfall history from API for ${zone}: ${err.message}`);
    return [];
  }
};
