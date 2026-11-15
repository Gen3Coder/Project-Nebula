const API = process.env.API || 'http://localhost:8000';

const ZONE_NAMES = {
  1: 'Arsi',
  2: 'Jimma',
  3: 'Bale',
  arsi: 'Arsi',
  jimma: 'Jimma',
  bale: 'Bale',
};

export const fetchAPIDataS = async (regionIdentifier = 1) => {
  const key = typeof regionIdentifier === 'string' ? regionIdentifier.toLowerCase() : regionIdentifier;
  const zone = ZONE_NAMES[key] || 'Arsi';

  try {
    const [tempRes, humRes, soilRes, vegRes] = await Promise.all([
      fetch(`${API}/temperature/${zone}`),
      fetch(`${API}/humidity/${zone}`),
      fetch(`${API}/soil-moisture/${zone}`),
      fetch(`${API}/vegetation/${zone}`),
    ]);

    if (!tempRes.ok || !humRes.ok || !soilRes.ok || !vegRes.ok) {
      throw new Error(
        `External API fetch failed for zone ${zone} (status: ${tempRes.status}/${humRes.status}/${soilRes.status}/${vegRes.status})`
      );
    }

    const [tempData, humData, soilData, vegData] = await Promise.all([
      tempRes.json(),
      humRes.json(),
      soilRes.json(),
      vegRes.json(),
    ]);

    const temperature = Number(tempData.value ?? tempData.temperature);
    const humidity = Number(humData.value ?? humData.humidity);

    if (isNaN(temperature) || isNaN(humidity)) {
      throw new Error(`API returned invalid data for ${zone}: temp=${tempData.value}, humidity=${humData.value}`);
    }

    const ndvi = Number(vegData.ndvi ?? vegData.value ?? 0.5);
    const vegetation_coverage = Math.max(0, Math.min(100, Number((ndvi * 100).toFixed(2))));
    
    const rawSoil = soilData.root !== undefined ? soilData.root * 100 : (soilData.value ?? 20);
    const soil_moisture = Math.max(0, Math.min(100, Number(rawSoil.toFixed(2))));
    const rainfall = Number(tempData.rainfall ?? soilData.rainfall ?? 0.0);

    return {
      zone,
      temperature,
      humidity,
      soil_moisture,
      ndvi,
      rainfall,
      vegetation_coverage,
    };
  } catch (error) {
    console.error(`Error fetching API data for zone ${zone}:`, error.message);
    throw error;
  }
};