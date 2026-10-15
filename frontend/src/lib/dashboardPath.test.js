import { dashboardPath } from './dashboardPath';

test('super admin opens the admin console', () => {
  expect(dashboardPath(['super_admin', 'admin'])).toBe('/admin');
  expect(dashboardPath(['super_admin'])).toBe('/admin');
});

test('each staff role opens its own dashboard', () => {
  expect(dashboardPath(['operations'])).toBe('/employee');
  expect(dashboardPath(['marketing'])).toBe('/sales');
  expect(dashboardPath(['cfo'])).toBe('/finance');
  expect(dashboardPath(['pilot'])).toBe('/pilot-portal');
  expect(dashboardPath(['operator'])).toBe('/operator');
});

test('the first role with a dashboard wins', () => {
  expect(dashboardPath(['finance', 'admin'])).toBe('/finance');
  expect(dashboardPath(['unknown', 'hr'])).toBe('/hr');
});

test('no known role goes to the home page', () => {
  expect(dashboardPath([])).toBe('/');
  expect(dashboardPath(undefined)).toBe('/');
});
