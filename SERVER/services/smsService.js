import {
  getRegionByIdQ,
  getFarmRecipientsByRegionIdQ,
  getAllFarmerRecipientsQ,
} from '../repositories/farmRepository.js';
import { fetchAPIDataS } from './APIServices.js';
import { evaluateCropHealthRules } from './cropHealthRegionalAssesmentService.js';

const AFRO_API_URL = process.env.AFRO_API_URL || 'https://api.afromessage.com/api/send';

// Amharic recommendations organized by crop and stress factor
export const AMHARIC_RECOMMENDATIONS = {
  WHEAT: {
    DROUGHT:
      'በስንዴ እርሻዎ የአፈር እርጥበት ቀንሷል። የውሃ እጥረቱን ለመቀነስ ተጨማሪ መስኖ ያድርጉ።',
    'HEAT STRESS':
      'በአካባቢዎ ያለው ሙቀት ከ26°C በላይ ነው። ይህ በወጣት የስንዴ ተክሎች ላይ ጫና ሊፈጥር ይችላል። እርሻዎን ይከታተሉ።',
    WATERLOGGING:
      'በስንዴ እርሻዎ ውስጥ ከመጠን በላይ ውሃ ተሰብስቧል። ውሃው እንዲወጣ የፍሳሽ ቦዮችን ይክፈቱ።',
    'LOW VEGETATION':
      'የስንዴ እርሻዎ የእፅዋት እድገት ከተጠበቀው በታች ነው። ተክሎቹን ለበሽታና ለምግብ ንጥረ ነገር እጥረት ምልክቶች ይመርምሩ።',
    NONE:
      'በአካባቢዎ የስንዴ እድገት ሁኔታ ጥሩ ነው። እንደተለመደው እርሻዎን ይከታተሉ።',
  },
  COFFEE: {
    'FUNGAL RISK':
      'በአካባቢዎ ያለው ከፍተኛ እርጥበትና ሙቀት የቡና ፍሬ በሽታ አደጋን ይጨምራል። የቡና ተክሎችዎን ይመርምሩ።',
    DROUGHT:
      'በቡና እርሻዎ የአፈር እርጥበት ቀንሷል። የቡና ችግኞችን ውሃ ያጠጡ፤ በቂ ጥላ እንዲያገኙ ያድርጉ።',
    'HEAT STRESS':
      'ከፍተኛ ሙቀት የቡና አበባዎችን ሊያበላሽ ይችላል። የቡና ዛፎችዎ በቂ የጥላ ሽፋን እንዲኖራቸው ያድርጉ።',
    WATERLOGGING:
      'በቡና እርሻዎ ውስጥ የአፈር እርጥበት ከመጠን በላይ ጨምሯል። የተሰበሰበው ውሃ እንዲወጣ የፍሳሽ ቦዮችን ያስተካክሉ።',
    'LOW VEGETATION':
      'የቡና ዛፎችዎ የእድገት ሁኔታ ከተጠበቀው በታች ነው። የደረቁ ቅርንጫፎችን ያስወግዱ፤ ኮምፖስት ይጠቀሙ።',
    NONE:
      'በአካባቢዎ የቡና እድገት ሁኔታ ጥሩ ነው። የአሁኑን የእርሻ እንክብካቤ ይቀጥሉ።',
  },
};

/**
 * Converts Ethiopian local phone numbers to international E.164 format.
 * Examples: '0912345678' -> '+251912345678'
 */
export const normalizePhoneNumber = (phone) => {
  if (!phone) throw new Error('Phone number is missing');
  const cleaned = String(phone).replace(/[\s()\-]/g, '');

  if (/^\+251[79]\d{8}$/.test(cleaned)) {
    return cleaned;
  }
  if (/^251[79]\d{8}$/.test(cleaned)) {
    return `+${cleaned}`;
  }
  if (/^0[79]\d{8}$/.test(cleaned)) {
    return `+251${cleaned.slice(1)}`;
  }
  if (/^[79]\d{8}$/.test(cleaned)) {
    return `+251${cleaned}`;
  }

  throw new Error(`Invalid Ethiopian phone number: ${phone}`);
};

/**
 * Formats personalized SMS with the farmer's name, crop health label, and Amharic text.
 * Pattern: "Greetings [Name], crop health report then the amharic text"
 */
export const formatFarmerSMS = (farmerName, crop, amharicText) => {
  const displayName = (farmerName || 'Farmer').trim();
  const cropPrefix = crop ? `${crop} ` : '';
  return `Greetings ${displayName}, ${cropPrefix}crop health report:\n${amharicText}`;
};

/**
 * Sends a single SMS message via AfroMessage API.
 */
export const sendAfroSMS = async ({ to, message }) => {
  const token = process.env.AFRO_API_TOKEN;
  const identifierId = process.env.AFRO_IDENTIFIER_ID;

  if (!token || !identifierId) {
    throw new Error('AfroMessage credentials (AFRO_API_TOKEN or AFRO_IDENTIFIER_ID) are not configured in .env');
  }

  const response = await fetch(AFRO_API_URL, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: identifierId,
      to,
      message,
    }),
  });

  const rawText = await response.text();
  let data;

  try {
    data = JSON.parse(rawText);
  } catch {
    if (rawText.includes('Oops, an error') || response.status === 500) {
      throw new Error(
        'AfroMessage server error (HTTP 500): The session or AFRO_API_TOKEN in SERVER/.env is expired or invalid. Please log in to afromessage.com and generate a fresh API token.'
      );
    }
    throw new Error(`AfroMessage returned invalid response (${response.status}): ${rawText.slice(0, 100)}`);
  }

  if (!response.ok || data.acknowledge !== 'success') {
    const errorMsg =
      data.response?.errors?.join(', ') ||
      data.errors?.join(', ') ||
      data.response?.message ||
      data.message ||
      `AfroMessage failed with status ${response.status}`;

    if (errorMsg.includes('Session has expired') || errorMsg.includes('expired')) {
      throw new Error(
        'Your AFRO_API_TOKEN in SERVER/.env has expired. Please log in to your AfroMessage dashboard (afromessage.com), generate a fresh API token, and update AFRO_API_TOKEN in .env.'
      );
    }

    throw new Error(errorMsg);
  }

  return data.response || data;
};

/**
 * Sends personalized crop health SMS to every single enrolled farmer across all regions.
 * Each farmer receives: "Greetings [Name], crop health report \n [Amharic recommendation]"
 */
export const sendCropHealthSMSToAllFarmers = async () => {
  if (!process.env.AFRO_API_TOKEN || !process.env.AFRO_IDENTIFIER_ID) {
    throw new Error('AfroMessage credentials are not configured.');
  }

  // 1. Retrieve all farmers
  const farmers = await getAllFarmerRecipientsQ();
  if (!farmers || farmers.length === 0) {
    throw new Error('No enrolled farmers with phone numbers found in the system.');
  }

  // 2. Fetch live metrics and diagnose each unique region once
  const uniqueRegions = [...new Set(farmers.map((f) => f.region_name || f.region || 'Arsi'))];
  const regionDiagnostics = {};

  for (const regName of uniqueRegions) {
    try {
      const metrics = await fetchAPIDataS(regName);
      const crop = regName.toLowerCase() === 'jimma' ? 'COFFEE' : 'WHEAT';
      const diagnosis = evaluateCropHealthRules(metrics, crop);
      const amharicText =
        AMHARIC_RECOMMENDATIONS[crop]?.[diagnosis.primaryStressFactor] ||
        AMHARIC_RECOMMENDATIONS[crop]?.['NONE'];

      regionDiagnostics[regName.toLowerCase()] = {
        crop: crop === 'COFFEE' ? 'Coffee' : 'Wheat',
        rawCrop: crop,
        metrics,
        diagnosis,
        amharicText,
      };
    } catch (err) {
      console.warn(`Could not compute live diagnostics for region ${regName}: ${err.message}`);
    }
  }

  // 3. Send personalized SMS to each farmer
  const results = [];
  const errors = [];

  for (const farmer of farmers) {
    try {
      const normalizedPhone = normalizePhoneNumber(farmer.phone || farmer.owner_phone_number);
      const regKey = (farmer.region_name || farmer.region || 'arsi').toLowerCase();
      const diag = regionDiagnostics[regKey] || regionDiagnostics['arsi'];
      const farmerName = farmer.first_name || (farmer.name ? farmer.name.split(' ')[0] : 'Farmer');

      const message = formatFarmerSMS(farmerName, diag?.crop || 'Wheat', diag?.amharicText);

      // Call AfroMessage API for this recipient
      const res = await sendAfroSMS({
        to: normalizedPhone,
        message,
      });

      results.push({
        farmerId: farmer.farmer_id || farmer.farm_id,
        name: farmer.name || farmerName,
        phone: normalizedPhone,
        region: farmer.region,
        status: 'SENT',
        campaign: res,
      });
    } catch (sendErr) {
      errors.push({
        farmerId: farmer.farmer_id || farmer.farm_id,
        name: farmer.name,
        phone: farmer.phone,
        error: sendErr.message,
      });
    }
  }

  return {
    success: results.length > 0,
    totalFarmers: farmers.length,
    sentCount: results.length,
    failedCount: errors.length,
    sentRecipients: results,
    errors,
  };
};

/**
 * Sends personalized crop health SMS to farmers within a specific region.
 */
export const sendRegionalCropHealthSMS = async (regionId) => {
  if (!process.env.AFRO_API_TOKEN || !process.env.AFRO_IDENTIFIER_ID) {
    throw new Error('AfroMessage credentials are not configured.');
  }

  const region = await getRegionByIdQ(regionId);
  if (!region) {
    throw new Error(`Selected region (id: ${regionId}) does not exist.`);
  }

  const crop = (region.crop || region.primary_crop || 'WHEAT').trim().toUpperCase();
  const farmers = await getFarmRecipientsByRegionIdQ(regionId);
  if (!farmers || farmers.length === 0) {
    throw new Error(`No farmers with phone numbers found for region ${region.name}.`);
  }

  const metrics = await fetchAPIDataS(region.name);
  const diagnosis = evaluateCropHealthRules(metrics, crop);
  const amharicText =
    AMHARIC_RECOMMENDATIONS[crop]?.[diagnosis.primaryStressFactor] ||
    AMHARIC_RECOMMENDATIONS[crop]?.['NONE'];

  const results = [];
  const errors = [];

  for (const farmer of farmers) {
    try {
      const normalizedPhone = normalizePhoneNumber(farmer.phone || farmer.owner_phone_number);
      const farmerName = farmer.first_name || (farmer.name ? farmer.name.split(' ')[0] : 'Farmer');
      const message = formatFarmerSMS(farmerName, region.name, amharicText);

      const res = await sendAfroSMS({
        to: normalizedPhone,
        message,
      });

      results.push({
        farmerId: farmer.farmer_id || farmer.farm_id,
        name: farmer.name,
        phone: normalizedPhone,
        status: 'SENT',
        campaign: res,
      });
    } catch (err) {
      errors.push({
        farmerId: farmer.farmer_id || farmer.farm_id,
        name: farmer.name,
        phone: farmer.phone,
        error: err.message,
      });
    }
  }

  return {
    success: results.length > 0,
    region: region.name,
    crop,
    totalFarmers: farmers.length,
    sentCount: results.length,
    failedCount: errors.length,
    sentRecipients: results,
    errors,
  };
};
