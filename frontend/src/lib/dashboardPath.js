// Where each role's dashboard lives (the routes in App.js). A user's first role that has a
// dashboard wins, so ['super_admin', 'admin'] opens /admin and ['finance', 'admin'] opens /finance.
const ROLE_HOME = {
  super_admin: '/admin',
  admin: '/admin',
  customer: '/customer',
  operator: '/operator',
  regional_manager: '/regional',
  helipad_owner: '/helipad-owner',
  hr: '/hr',
  sales: '/sales',
  marketing: '/sales',
  support: '/support',
  finance: '/finance',
  cfo: '/finance',
  finance_head: '/finance',
  accounts_manager: '/finance',
  treasury_analyst: '/finance',
  operations: '/employee',
  employee: '/employee',
  pilot: '/pilot-portal',
};

export function dashboardPath(roles) {
  const home = (roles || []).map((role) => ROLE_HOME[role]).find(Boolean);
  return home || '/';
}
