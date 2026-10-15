import { tr } from './bilingual';

// Pure helpers behind the role home screens, kept apart from the components so they can be unit tested.

const UPCOMING = ['confirmed', 'pending', 'quote_accepted', 'passenger_details_filled'];
const PENDING_SETTLEMENT = ['pending', 'approved'];

// Picks the trip that leaves soonest from now; trips without a date come last.
export function pickNextTrip(trips, now = new Date()) {
  const upcoming = (trips || []).filter((t) => UPCOMING.includes(t.status));
  const dated = upcoming
    .map((t) => ({ t, at: new Date(t.departure_date || t.travel_date || 0) }))
    .filter(({ at }) => !Number.isNaN(at.getTime()) && at >= now)
    .sort((a, b) => a.at - b.at);
  if (dated.length) return dated[0].t;
  return upcoming[0] || null;
}

export function countdown(target, now = new Date()) {
  const at = new Date(target);
  if (!target || Number.isNaN(at.getTime())) return null;
  const ms = at - now;
  if (ms <= 0) return null;
  const days = Math.floor(ms / 86400000);
  const hours = Math.floor((ms % 86400000) / 3600000);
  const mins = Math.floor((ms % 3600000) / 60000);
  return { days, hours, mins };
}

// An operator only gets inquiries once admin has approved them (see inquiry_broadcast_service).
export function isApproved(operator) {
  return operator?.status === 'active' && ['verified', 'approved'].includes(operator?.verification_status);
}

export function summariseSettlements(settlements) {
  const due = (settlements || []).filter((s) => PENDING_SETTLEMENT.includes(s.status));
  const total = due.reduce((sum, s) => sum + (Number(s.payout_amount ?? s.net_amount ?? s.amount) || 0), 0);
  return { due, total };
}

// Counts each from → to pair and returns the busiest first.
export function topRoutes(bookings, limit = 5) {
  const counts = {};
  (bookings || []).forEach((b) => {
    const from = b.from_location || b.pickup_location;
    const to = b.to_location || b.drop_location;
    if (!from || !to) return;
    const key = `${from} → ${to}`;
    counts[key] = (counts[key] || 0) + 1;
  });
  return Object.entries(counts)
    .map(([route, count]) => ({ route, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}

// Turns dashboard counters into the "needs you" list; only non-zero items are shown.
export function pendingItems(data) {
  const s = data?.statistics || {};
  const docs = (s.expiring_pilot_documents || 0) + (s.expiring_aircraft_documents || 0);
  return [
    { id: 'operators', tab: 'verification_queue', count: s.pending_operator_approvals || 0,
      title: tr('Operator verification', 'ऑपरेटर सत्यापन'), subtitle: tr('New operators waiting for approval', 'मंज़ूरी के इंतज़ार में नए ऑपरेटर') },
    { id: 'landing', tab: 'permissions', count: s.pending_landing_permissions || 0,
      title: tr('Landing permissions', 'लैंडिंग अनुमति'), subtitle: tr('Helipad and village landing requests', 'हेलीपैड और गांव लैंडिंग अनुरोध') },
    { id: 'docs', tab: 'document_expiry', count: docs,
      title: tr('Documents expiring', 'दस्तावेज़ समाप्त हो रहे'), subtitle: tr('Pilot and aircraft papers due in 30 days', '30 दिनों में पायलट और विमान कागज़ात') },
    { id: 'sos', tab: 'sos', count: (data?.emergency_alerts || []).length,
      title: tr('Safety alerts', 'सुरक्षा अलर्ट'), subtitle: tr('Emergency or safety-related bookings', 'आपातकालीन या सुरक्षा संबंधी बुकिंग') },
  ].filter((i) => i.count > 0);
}
