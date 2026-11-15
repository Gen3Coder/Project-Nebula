import {
  getRegionByIdQ,
  getFarmRecipientsByRegionIdQ,
} from '../repositories/farmsRepository.js';

import { fetchAPIDataS } from './APIServices.js';

import { evaluateCropHealthRules } from './cropHealthServices.js';

const AFRO_API_URL = 'https://api.afromessage.com/api/bulk_send';

const BATCH_SIZE = 20;
const MAX_CAMPAIGN_SIZE = 100;

// Amharic recommendations, organized by crop and stress factor.
const AMHARIC_RECOMMENDATIONS = {
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

// Convert Ethiopian local phone numbers into international format.
const normalizePhoneNumber = (phone) => {
  const cleaned = String(phone).replace(/[\s()-]/g, '');

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

// Send one batch to AfroMessage.
const sendBatch = async (phoneNumbers, message) => {
  const response = await fetch(AFRO_API_URL, {
    method: 'POST',

    headers: {
      Authorization: `Bearer ${process.env.AFRO_API_TOKEN}`,
      'Content-Type': 'application/json',
    },

    body: JSON.stringify({
      from: process.env.AFRO_IDENTIFIER_ID,
      to: phoneNumbers,
      message,
    }),
  });

  const data = await response.json();

  if (!response.ok || data.acknowledge !== 'success') {
    throw new Error(
      data.response?.errors?.join(', ') ||
      data.response?.message ||
      'AfroMessage failed to accept the SMS batch.'
    );
  }

  return data.response;
};

// Main function: sends a regional crop-health recommendation.
export const sendRegionalCropHealthSMS = async (regionId) => {
  if (!process.env.AFRO_API_TOKEN || !process.env.AFRO_IDENTIFIER_ID) {
    throw new Error('AfroMessage credentials are not configured.');
  }

  // 1. Retrieve the selected region.
  const region = await getRegionByIdQ(regionId);

  if (!region) {
    throw new Error('Selected region does not exist.');
  }

  // 2. Determine the crop from the region, NOT individual farms.
  const crop = region.crop.trim().toUpperCase();

  if (!['WHEAT', 'COFFEE'].includes(crop)) {
    throw new Error(`Unsupported regional crop: ${region.crop}`);
  }

  // 3. Retrieve all farmers in the selected region.
  const farmers = await getFarmRecipientsByRegionIdQ(regionId);

  if (farmers.length === 0) {
    throw new Error('No farmers with phone numbers were found.');
  }

  if (farmers.length > MAX_CAMPAIGN_SIZE) {
    throw new Error(
      `Beta limit exceeded. This campaign has ${farmers.length} farmers. Maximum is ${MAX_CAMPAIGN_SIZE}.`
    );
  }

  // 4. Fetch current regional environmental metrics.
  const metrics = await fetchAPIDataS(region.name);

  // 5. Reuse the existing crop-health evaluation engine.
  const diagnosis = evaluateCropHealthRules(metrics, crop);

  // 6. Generate the Amharic SMS.
  const message =
    AMHARIC_RECOMMENDATIONS[crop][diagnosis.primaryStressFactor];

  if (!message) {
    throw new Error('No Amharic recommendation exists for this condition.');
  }

  // 7. Validate phone numbers before sending anything.
  const recipients = farmers.map((farmer) => ({
    farmId: farmer.farm_id,
    phone: normalizePhoneNumber(farmer.owner_phone_number),
  }));

  // Remove duplicate numbers to avoid duplicate messages.
  const uniqueRecipients = [
    ...new Map(recipients.map((r) => [r.phone, r])).values(),
  ];

  // 8. Send batches of 20.
  const results = [];

  for (let i = 0; i < uniqueRecipients.length; i += BATCH_SIZE) {
    const batch = uniqueRecipients.slice(i, i + BATCH_SIZE);

    try {
      const result = await sendBatch(
        batch.map((recipient) => recipient.phone),
        message
      );

      results.push({
        count: batch.length,
        campaign: result,
      });
    } catch (error) {
      return {
        success: false,
        region: region.name,
        attempted: i + batch.length,
        accepted: results.reduce((sum, r) => sum + r.count, 0),
        error: error.message,
      };
    }
  }

  return {
    success: true,
    region: region.name,
    crop,
    healthScore: diagnosis.healthScore,
    status: diagnosis.status,
    primaryStressFactor: diagnosis.primaryStressFactor,
    message,
    totalRecipients: uniqueRecipients.length,
    batches: results,
  };
};
