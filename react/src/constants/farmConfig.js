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

export const sampleDrySpellRisk = 'medium'
export const sampleRainfallReference = 2
