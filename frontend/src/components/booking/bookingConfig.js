import { bi, tr } from '../../lib/bilingual';
// Booking Configuration - Shared constants for booking flow
// This file contains all dropdown options, aircraft types, and pricing multipliers

// Aircraft Types
export const aircraftTypes = [
  { value: 'helicopter', label: bi('Helicopter / हेलीकॉप्टर'), icon: '🚁', maxPassengers: 6 },
  { value: 'chartered_plane', label: bi('Chartered Plane / चार्टर्ड प्लेन'), icon: '✈️', maxPassengers: 19 },
];

// ============ 9 BOOKING TYPES (NEW) ============
// Matches backend BOOKING_TYPES from aircraft_catalog_routes.py

export const bookingTypes = [
  { 
    value: 'one_way', 
    label: tr('One Way', 'एक तरफ़ा'), 
    labelHi: 'एकतरफा',
    icon: '→',
    description: tr('Single journey from A to B', 'A से B तक एक यात्रा'),
    descriptionHi: 'A से B तक एक तरफ़ा यात्रा',
    multiplier: 1.0,
    minHours: null,
    minDays: null,
    discountHint: null
  },
  { 
    value: 'round_trip', 
    label: tr('Round Trip', 'आना-जाना'), 
    labelHi: 'वापसी यात्रा',
    icon: '↔',
    description: tr('Return journey A to B to A', 'A से B और वापस A की यात्रा'),
    descriptionHi: 'A से B और वापस A तक',
    multiplier: 1.85, // 7.5% discount on 2x
    minHours: null,
    minDays: null,
    discountHint: 'Save 5-10%'
  },
  { 
    value: 'multi_city', 
    label: 'Multi-City', 
    labelHi: 'बहु-शहर',
    icon: '◇',
    description: tr('Multiple destinations in one trip', 'एक यात्रा में कई गंतव्य'),
    descriptionHi: 'एक यात्रा में कई गंतव्य',
    multiplier: 1.0, // Per leg pricing
    minHours: null,
    minDays: null,
    discountHint: 'Per-leg discounts'
  },
  { 
    value: 'hourly_charter', 
    label: tr('Hourly Charter', 'प्रति घंटा चार्टर'), 
    labelHi: 'प्रति घंटा चार्टर',
    icon: '⏱',
    description: tr('Book by the hour', 'घंटे के हिसाब से बुक करें'),
    descriptionHi: 'घंटे के हिसाब से बुक करें',
    multiplier: 1.0,
    minHours: 1,
    minDays: null,
    discountHint: null
  },
  { 
    value: 'daily_charter', 
    label: tr('Daily Charter', 'दैनिक चार्टर'), 
    labelHi: 'दैनिक चार्टर',
    icon: '📅',
    description: tr('Full day aircraft at your disposal', 'पूरे दिन विमान आपकी सेवा में'),
    descriptionHi: 'पूरे दिन के लिए विमान',
    multiplier: 0.9, // 10% discount for full day
    minHours: 8,
    minDays: 1,
    discountHint: '10% off daily rate'
  },
  { 
    value: 'multi_day', 
    label: 'Multi-Day', 
    labelHi: 'बहु-दिवसीय',
    icon: '📆',
    description: tr('3+ days charter with discounts', 'छूट के साथ 3+ दिन का चार्टर'),
    descriptionHi: '3+ दिन की चार्टर छूट के साथ',
    multiplier: 0.85, // 15% discount for 3+ days
    minHours: null,
    minDays: 3,
    discountHint: '10-15% off'
  },
  { 
    value: 'group_booking', 
    label: tr('Group Booking', 'समूह बुकिंग'), 
    labelHi: 'समूह बुकिंग',
    icon: '👥',
    description: tr('5+ passengers, special rates', '5+ यात्री, विशेष दरें'),
    descriptionHi: '5+ यात्री, विशेष दरें',
    multiplier: 0.92, // 8% group discount
    minHours: null,
    minDays: null,
    minPassengers: 5,
    discountHint: 'Group discounts'
  },
  { 
    value: 'emergency', 
    label: tr('Emergency', 'आपातकाल'), 
    labelHi: 'आपातकालीन',
    icon: '🚨',
    description: tr('Urgent medical or time-critical', 'अत्यावश्यक चिकित्सा या समय-संवेदनशील'),
    descriptionHi: 'तत्काल चिकित्सा या समय-महत्वपूर्ण',
    multiplier: 1.25, // 25% priority surcharge
    minHours: null,
    minDays: null,
    discountHint: 'Priority surcharge',
    priority: true
  },
  { 
    value: 'event_based', 
    label: tr('Event Package', 'इवेंट पैकेज'), 
    labelHi: 'इवेंट पैकेज',
    icon: '🎉',
    description: tr('Weddings, Corporate events, Film shoots', 'शादियां, कॉर्पोरेट कार्यक्रम, फ़िल्म शूटिंग'),
    descriptionHi: 'शादी, कॉर्पोरेट इवेंट, फिल्म शूटिंग',
    multiplier: 1.0, // Custom quote
    minHours: null,
    minDays: null,
    discountHint: 'Custom quote',
    customQuote: true
  }
];

// Udan Ka Prakar (Flight Type) Options - Legacy support
export const udanPrakarOptions = [
  { value: 'one_hour', label: bi('1 Hour Flight / 1 घंटे की उड़ान'), icon: '⏱️' },
  { value: 'two_hour', label: bi('2 Hour Flight / 2 घंटे की उड़ान'), icon: '⏰' },
  { value: 'half_day', label: bi('Half Day / आधा दिन'), icon: '🌤️' },
  { value: 'full_day', label: bi('Full Day / पूरा दिन'), icon: '☀️' },
  { value: 'multi_city', label: bi('Multi-City / बहु-शहर'), icon: '🗺️' },
  { value: 'point_to_point', label: bi('Point-to-Point / पॉइंट-टू-पॉइंट'), icon: '📍' },
];

// Booking For Options
export const bookingForOptions = [
  { value: 'self', label: bi('Self / खुद के लिए'), icon: '👤' },
  { value: 'friend_family', label: bi('Friend & Family / दोस्त और परिवार'), icon: '👨‍👩‍👧' },
  { value: 'company', label: bi('Company / Corporate / कंपनी'), icon: '🏢' },
  { value: 'political', label: bi('Political / VIP / राजनीतिक'), icon: '🎖️' },
  { value: 'other', label: bi('Other / अन्य'), icon: '📝' },
];

// Booking Purpose Options
export const bookingPurposeOptions = [
  { value: 'wedding', label: bi('Wedding / शादी'), icon: '💒' },
  { value: 'temple_yatra', label: bi('Temple Yatra / मंदिर यात्रा'), icon: '🛕' },
  { value: 'company_tour', label: bi('Corporate Tour / कॉर्पोरेट टूर'), icon: '🏢' },
  { value: 'election_tour', label: bi('Election Campaign / चुनाव प्रचार'), icon: '🗳️' },
  { value: 'medical_emergency', label: bi('Medical Emergency / मेडिकल'), icon: '🏥' },
  { value: 'film_shooting', label: bi('Film Shooting / फिल्म शूटिंग'), icon: '🎬' },
  { value: 'general_tour', label: bi('General Tour / सामान्य यात्रा'), icon: '✈️' },
  { value: 'pilgrimage', label: bi('Pilgrimage / तीर्थ यात्रा'), icon: '🙏' },
  { value: 'business', label: bi('Business Meeting / बिज़नेस'), icon: '💼' },
  { value: 'other', label: bi('Other / अन्य'), icon: '📝' },
];

// Booking Steps Configuration
export const bookingSteps = [
  { id: 'passengers', title: bi('यात्री / Passengers') },
  { id: 'booking_type', title: tr('Booking Type', 'बुकिंग प्रकार') },
  { id: 'route', title: bi('मार्ग / Route') },
  { id: 'price_inquiry', title: bi('मूल्य / Price') },
];

// Udan Prakar Pricing Multipliers
export const udanPrakarMultipliers = {
  one_hour: 0.8,
  two_hour: 1,
  half_day: 1.5,
  full_day: 2.5,
  multi_city: 3,
  point_to_point: 1,
};

// Default Pricing Settings (fallback)
export const defaultPricingSettings = {
  base_price: 50000,
  rate_per_km: 500,
  helicopter_multiplier: 1,
  plane_multiplier: 1.5,
  dynamic_pricing_enabled: true,
  custom_price_enabled: true,
};

// Village Landing Required Documents
export const villageLandingDocuments = [
  { key: 'collector_noc', label: bi('Collector NOC / कलेक्टर NOC') },
  { key: 'fire_dept', label: bi('Fire Department Acknowledgment / फायर विभाग की पावती') },
  { key: 'police_station', label: bi('Local Police Station Acknowledgment / स्थानीय थाना की पावती') },
  { key: 'sp_dcp', label: bi('SP/DCP Acknowledgment / SP/DCP की पावती') },
];

// Helper function to get label by value
export const getOptionLabel = (options, value) => {
  const option = options.find(opt => opt.value === value);
  return option ? option.label : value;
};

// Helper function to calculate distance using Haversine formula
export const calculateDistance = (lat1, lon1, lat2, lon2) => {
  const R = 6371; // Earth's radius in km
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
};
