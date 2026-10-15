import { pickNextTrip, countdown, isApproved, summariseSettlements, topRoutes, pendingItems } from './dashboardData';

const NOW = new Date('2026-10-15T10:00:00Z');

test('next flight is the soonest upcoming trip, past and cancelled ones are skipped', () => {
  const trips = [
    { id: 'past', status: 'confirmed', departure_date: '2026-10-01T09:00:00Z' },
    { id: 'later', status: 'confirmed', departure_date: '2026-11-02T09:00:00Z' },
    { id: 'soon', status: 'pending', departure_date: '2026-10-20T09:00:00Z' },
    { id: 'off', status: 'cancelled', departure_date: '2026-10-16T09:00:00Z' },
  ];
  expect(pickNextTrip(trips, NOW).id).toBe('soon');
  expect(pickNextTrip([], NOW)).toBeNull();
  expect(pickNextTrip([{ id: 'x', status: 'completed' }], NOW)).toBeNull();
});

test('countdown splits the time left and stops once departed', () => {
  expect(countdown('2026-10-16T12:30:00Z', NOW)).toEqual({ days: 1, hours: 2, mins: 30 });
  expect(countdown('2026-10-14T10:00:00Z', NOW)).toBeNull();
  expect(countdown(null, NOW)).toBeNull();
});

test('an operator is approved only when active and verified', () => {
  expect(isApproved({ status: 'active', verification_status: 'approved' })).toBe(true);
  expect(isApproved({ status: 'active', verification_status: 'pending' })).toBe(false);
  expect(isApproved({ status: 'pending', verification_status: 'approved' })).toBe(false);
  expect(isApproved(null)).toBe(false);
});

test('payouts due add up pending and approved settlements only', () => {
  const { due, total } = summariseSettlements([
    { status: 'pending', payout_amount: 1000 },
    { status: 'approved', payout_amount: 500 },
    { status: 'paid', payout_amount: 9999 },
  ]);
  expect(due).toHaveLength(2);
  expect(total).toBe(1500);
  expect(summariseSettlements(null).total).toBe(0);
});

test('top routes are counted and ordered busiest first', () => {
  const routes = topRoutes([
    { from_location: 'Mumbai', to_location: 'Shirdi' },
    { from_location: 'Pune', to_location: 'Lonavala' },
    { from_location: 'Mumbai', to_location: 'Shirdi' },
    { from_location: 'Mumbai' },
  ]);
  expect(routes).toEqual([
    { route: 'Mumbai → Shirdi', count: 2 },
    { route: 'Pune → Lonavala', count: 1 },
  ]);
});

test('needs-you lists only counters above zero', () => {
  const items = pendingItems({
    statistics: { pending_operator_approvals: 3, pending_landing_permissions: 0, expiring_pilot_documents: 1, expiring_aircraft_documents: 1 },
    emergency_alerts: [],
  });
  expect(items.map((i) => [i.tab, i.count])).toEqual([['verification_queue', 3], ['document_expiry', 2]]);
  expect(pendingItems(null)).toEqual([]);
});
