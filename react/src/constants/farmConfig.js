/**
 * Build the crop health API URL with the user's selected region and crop.
 * Uses the Vite dev proxy (/api → http://localhost:5000) so no CORS issues.
 * Falls back to 'Arsi' / 'Wheat' when the user hasn't selected yet.
 */
export function buildCropHealthURL(region = 'Arsi', crop = 'Wheat') {
  const params = new URLSearchParams({ region, crop })
  return `/api/mock/crops/1/health?${params.toString()}`
}

// Legacy constant kept for any code that still imports it (defaults to Arsi/Wheat)
export const API_URL = '/api/mock/crops/1/health?region=Arsi&crop=Wheat'

export const sampleRainfall = [0.2, 0.1, 2.4, 6.1, 3.8, 0.4, 0.1, 0, 0, 0.2, 0, 0.1, 0, 0]
export const sampleDrySpellRisk = 'medium'
export const sampleRainfallReference = 2
