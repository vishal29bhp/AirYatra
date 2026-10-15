import React, { useEffect, useState } from 'react';
import api from '@/services/apiClient';
import { topRoutes, pendingItems } from '../../lib/dashboardData';
import { tr } from '../../lib/bilingual';
import {
  PageHead, Panel, Kpi, Pill, BarRow, ActionRow, DataTable, EmptyNote, LinkButton, Label,
  formatINR, formatCount, humanStatus, statusTone, NO_VALUE,
} from '../dashboard/Premium';

function AdminCommand({ data, loading, onNavigate, isCeo }) {
  const [gateways, setGateways] = useState(null);
  const [email, setEmail] = useState(null);

  useEffect(() => {
    let alive = true;
    Promise.allSettled([api.get('/payments/gateways/available'), api.get('/email/status')]).then(([g, e]) => {
      if (!alive) return;
      if (g.status === 'fulfilled') setGateways(g.value.data.gateways || []);
      if (e.status === 'fulfilled') setEmail(e.value.data);
    });
    return () => { alive = false; };
  }, []);

  const s = data?.statistics || {};
  const revenue = data?.revenue || {};
  const recent = data?.recent_bookings || [];
  const routes = topRoutes(recent);
  const maxRoute = routes[0]?.count || 0;
  const needs = pendingItems(data);
  const go = (tab) => () => onNavigate(tab);
  const paymentsLive = gateways ? gateways.some((g) => g.is_configured && !g.is_mock) : null;

  return (
    <div data-testid="admin-command">
      <PageHead eyebrow={tr('Maharashtra network', 'महाराष्ट्र नेटवर्क')} title={isCeo ? tr('Command', 'कमांड') : tr('Admin', 'एडमिन')}>
        <button onClick={go('bookings')} className="px-5 py-2.5 text-sm font-semibold border border-slate-600 text-slate-100 hover:border-lime">
          {tr('All bookings', 'सभी बुकिंग')}
        </button>
        <button onClick={go('analytics')} className="px-5 py-2.5 text-sm font-semibold bg-lime text-black hover:bg-lime/90">
          {tr('Analytics', 'विश्लेषण')}
        </button>
      </PageHead>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <Kpi label={tr('Revenue, completed trips', 'राजस्व, पूर्ण यात्राएं')} value={loading ? NO_VALUE : formatINR(revenue.total_revenue)}
          note={revenue.total_commission ? tr(`${formatINR(revenue.total_commission)} commission`, `${formatINR(revenue.total_commission)} कमीशन`) : null} noteTone="lime" onClick={go('payments_dashboard')} />
        <Kpi label={tr('Bookings this month', 'इस महीने बुकिंग')} value={loading ? NO_VALUE : formatCount(s.month_bookings)}
          note={tr(`${formatCount(s.today_bookings)} today · ${formatCount(s.total_bookings)} all time`, `आज ${formatCount(s.today_bookings)} · कुल ${formatCount(s.total_bookings)}`)} onClick={go('bookings')} />
        <Kpi label={tr('Active operators', 'सक्रिय ऑपरेटर')} value={loading ? NO_VALUE : formatCount(s.active_operators)}
          note={s.pending_operator_approvals ? tr(`${s.pending_operator_approvals} awaiting verification`, `${s.pending_operator_approvals} सत्यापन बाकी`) : tr(`${formatCount(s.total_aircraft)} aircraft listed`, `${formatCount(s.total_aircraft)} विमान`)}
          noteTone={s.pending_operator_approvals ? 'amber' : undefined} onClick={go('operators')} />
        <Kpi label={tr('Customers', 'ग्राहक')} value={loading ? NO_VALUE : formatCount(s.total_customers)} onClick={go('users')} />
      </div>

      <div className="grid lg:grid-cols-5 gap-6 mb-6">
        <Panel className="lg:col-span-3" title={tr('Top routes', 'शीर्ष मार्ग')} action={<Label>{tr('Recent bookings', 'हाल की बुकिंग')}</Label>}>
          {routes.length === 0
            ? <EmptyNote>{loading ? tr('Loading…', 'लोड हो रहा है…') : tr('Routes appear once bookings come in.', 'बुकिंग आने पर मार्ग दिखेंगे।')}</EmptyNote>
            : routes.map((r) => <BarRow key={r.route} label={r.route} value={r.count} max={maxRoute} />)}
        </Panel>

        <Panel className="lg:col-span-2" bodyClassName="" testId="needs-you"
          title={tr('Needs you', 'आपकी ज़रूरत')}
          action={needs.length ? <span className="font-mono text-xs bg-amber text-black px-2 py-0.5">{needs.reduce((n, i) => n + i.count, 0)}</span> : null}>
          {needs.length === 0
            ? <div className="p-6"><EmptyNote>{loading ? tr('Loading…', 'लोड हो रहा है…') : tr('All clear. Nothing is waiting on you.', 'सब ठीक है। कुछ बाकी नहीं।')}</EmptyNote></div>
            : needs.map((i, idx) => (
              <ActionRow key={i.id} title={`${i.title} · ${i.count}`} subtitle={i.subtitle}
                actionLabel={tr('Review', 'देखें')} primary={idx === 0} onAction={go(i.tab)} />
            ))}
        </Panel>
      </div>

      <Panel title={tr('Latest bookings', 'नवीनतम बुकिंग')} bodyClassName="" className="mb-6"
        action={<LinkButton onClick={go('bookings')}>{tr('View all', 'सभी देखें')}</LinkButton>}>
        <DataTable
          rows={recent.slice(0, 6)}
          onRowClick={go('bookings')}
          empty={loading ? tr('Loading…', 'लोड हो रहा है…') : tr('No bookings yet.', 'अभी कोई बुकिंग नहीं।')}
          columns={[
            { key: 'ref', label: tr('Booking', 'बुकिंग'), render: (r) => <span className="font-mono text-slate-400">{r.booking_number || NO_VALUE}</span> },
            { key: 'customer', label: tr('Customer', 'ग्राहक'), render: (r) => r.customer_name || NO_VALUE },
            { key: 'route', label: tr('Route', 'मार्ग'), render: (r) => `${r.from_location || NO_VALUE} → ${r.to_location || NO_VALUE}` },
            { key: 'operator', label: tr('Operator', 'ऑपरेटर'), render: (r) => r.operator_name || NO_VALUE },
            { key: 'status', label: tr('Status', 'स्थिति'), render: (r) => <Pill tone={statusTone(r.status)}>{humanStatus(r.status)}</Pill> },
            { key: 'amount', label: tr('Amount', 'राशि'), align: 'right', render: (r) => formatINR(r.total_amount || null) },
          ]}
        />
      </Panel>

      <div className="grid lg:grid-cols-2 gap-6">
        <Panel title={tr('Teams', 'टीमें')}>
          <div className="grid grid-cols-2 gap-4">
            {[
              ['payments_dashboard', tr('Finance', 'वित्त'), tr('Payments and payouts', 'भुगतान और पेआउट')],
              ['crm', tr('Sales', 'बिक्री'), tr('Leads and follow-ups', 'लीड और फॉलो-अप')],
              ['attendance', tr('HR', 'एचआर'), tr('Attendance and payroll', 'उपस्थिति और वेतन')],
              ['support', tr('Support', 'सहायता'), tr('Customer tickets', 'ग्राहक टिकट')],
            ].map(([tab, name, sub]) => (
              <button key={tab} onClick={go(tab)} className="border border-slate-700 p-4 text-left hover:border-lime transition-colors">
                <Label>{name}</Label>
                <div className="text-slate-100 font-semibold mt-1">{sub}</div>
              </button>
            ))}
          </div>
        </Panel>

        <Panel title={tr('System', 'सिस्टम')} bodyClassName="">
          {[
            [tr('API and database', 'API और डेटाबेस'), data ? 'ok' : loading ? 'wait' : 'bad', 'settings'],
            [tr('Payments', 'भुगतान'), paymentsLive === null ? 'wait' : paymentsLive ? 'ok' : 'keys', 'payments_dashboard'],
            [tr('Email', 'ईमेल'), email === null ? 'wait' : email.status === 'configured' ? 'ok' : 'keys', 'settings'],
          ].map(([name, state, tab]) => (
            <button key={name} onClick={go(tab)} className="w-full flex items-center justify-between px-6 py-4 border-b border-slate-700 last:border-b-0 hover:bg-slate-700/40">
              <span className="text-slate-100">{name}</span>
              {state === 'ok' && <Pill tone="lime">{tr('Healthy', 'ठीक')}</Pill>}
              {state === 'keys' && <Pill tone="amber">{tr('Keys not set', 'कुंजी नहीं')}</Pill>}
              {state === 'bad' && <Pill tone="red">{tr('Not reachable', 'उपलब्ध नहीं')}</Pill>}
              {state === 'wait' && <Pill>{tr('Checking', 'जांच')}</Pill>}
            </button>
          ))}
        </Panel>
      </div>
    </div>
  );
}

export default AdminCommand;
