import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plane, ShieldCheck, Sparkles, Star } from 'lucide-react';
import api, { customerAPI } from '../../services/api';
import { pickNextTrip, countdown } from '../../lib/dashboardData';
import { tr } from '../../lib/bilingual';
import {
  PageHead, Panel, Label, Pill, DataTable, LinkButton, EmptyNote,
  formatDate, formatINR, formatCount, humanStatus, statusTone, NO_VALUE,
} from '../dashboard/Premium';

function CountBlock({ value, label }) {
  return (
    <div className="text-center">
      <div className="font-heading font-extrabold text-4xl text-lime leading-none">{String(value).padStart(2, '0')}</div>
      <Label className="mt-1">{label}</Label>
    </div>
  );
}

function CustomerHome({ user }) {
  const navigate = useNavigate();
  const [trips, setTrips] = useState([]);
  const [stats, setStats] = useState(null);
  const [loyalty, setLoyalty] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    Promise.allSettled([customerAPI.getTrips(), api.get('/loyalty/my-status')]).then(([t, l]) => {
      if (!alive) return;
      if (t.status === 'fulfilled') {
        setTrips(t.value.data.trips || []);
        setStats(t.value.data.statistics || null);
      }
      if (l.status === 'fulfilled') setLoyalty(l.value.data);
      setLoading(false);
    });
    return () => { alive = false; };
  }, []);

  const next = pickNextTrip(trips);
  const left = next ? countdown(next.departure_date || next.travel_date) : null;
  const firstName = (user?.full_name || '').split(' ')[0];
  const tier = loyalty?.current_tier?.name || loyalty?.profile?.tier;

  return (
    <div data-testid="customer-home">
      <PageHead eyebrow={tr('My flights', 'मेरी उड़ानें')} title={firstName ? tr(`Hello, ${firstName}`, `नमस्ते, ${firstName}`) : tr('My flights', 'मेरी उड़ानें')}>
        <button onClick={() => navigate('/booking')} className="px-5 py-2.5 text-sm font-semibold bg-lime text-black hover:bg-lime/90" data-testid="create-first-booking-btn">
          {tr('Book a flight', 'फ्लाइट बुक करें')}
        </button>
      </PageHead>

      <div className="grid lg:grid-cols-3 gap-6 mb-6">
        <Panel className="lg:col-span-2" bodyClassName="p-6 lg:p-8" testId="next-flight">
          <Label>{tr('Next flight', 'अगली उड़ान')}</Label>
          {loading ? (
            <EmptyNote>{tr('Loading…', 'लोड हो रहा है…')}</EmptyNote>
          ) : next ? (
            <>
              <div className="flex flex-wrap items-center gap-4 mt-4">
                <span className="font-heading font-extrabold uppercase text-5xl lg:text-6xl text-slate-100 leading-none">{next.from_location || NO_VALUE}</span>
                <Plane className="h-8 w-8 text-lime" />
                <span className="font-heading font-extrabold uppercase text-5xl lg:text-6xl text-slate-100 leading-none">{next.to_location || NO_VALUE}</span>
              </div>
              <div className="flex flex-wrap gap-x-8 gap-y-2 mt-4 text-sm text-slate-300">
                <span>{formatDate(next.departure_date || next.travel_date)}</span>
                <span>{next.passengers ? tr(`${next.passengers} passengers`, `${next.passengers} यात्री`) : null}</span>
                <span>{next.aircraft?.aircraft_type}</span>
                <span>{next.operator?.company_name}</span>
              </div>
              <div className="flex flex-wrap items-end justify-between gap-6 mt-8">
                {left ? (
                  <div className="flex gap-6">
                    <CountBlock value={left.days} label={tr('Days', 'दिन')} />
                    <CountBlock value={left.hours} label={tr('Hours', 'घंटे')} />
                    <CountBlock value={left.mins} label={tr('Mins', 'मिनट')} />
                  </div>
                ) : <Pill tone={statusTone(next.status)}>{humanStatus(next.status)}</Pill>}
                <button onClick={() => navigate('/customer/trips')} className="px-5 py-2.5 text-sm font-semibold border border-slate-600 text-slate-100 hover:border-lime">
                  {tr('Trip details', 'यात्रा विवरण')}
                </button>
              </div>
            </>
          ) : (
            <div className="mt-4">
              <p className="font-heading font-extrabold uppercase text-4xl text-slate-100 m-0">{tr('No flight booked yet', 'अभी कोई उड़ान बुक नहीं')}</p>
              <p className="text-slate-400 mt-2">{tr('Shirdi, Lonavala, Mahabaleshwar and more are a short hop away.', 'शिर्डी, लोनावला, महाबलेश्वर और भी बहुत कुछ पास ही है।')}</p>
            </div>
          )}
        </Panel>

        <div className="grid gap-6">
          <Panel bodyClassName="p-6" testId="loyalty-card">
            <div className="flex items-center justify-between">
              <Label>{tr('VIP points', 'वीआईपी अंक')}</Label>
              <Star className="h-4 w-4 text-amber" />
            </div>
            <div className="font-heading font-extrabold text-5xl text-slate-100 leading-none mt-3">
              {formatCount(loyalty?.profile?.available_points)}
            </div>
            <div className="flex items-center justify-between mt-3">
              {tier ? <Pill tone="amber">{tier}</Pill> : <span />}
              <LinkButton onClick={() => navigate('/customer/loyalty')}>{tr('Rewards', 'पुरस्कार')}</LinkButton>
            </div>
          </Panel>
          <div className="grid grid-cols-2 gap-6">
            <button onClick={() => navigate('/customer/kyc')} className="bg-slate-800 border border-slate-700 p-5 text-left hover:border-lime transition-colors">
              <ShieldCheck className="h-5 w-5 text-lime mb-3" />
              <div className="text-slate-100 font-semibold">{tr('Documents', 'दस्तावेज़')}</div>
              <div className="text-sm text-slate-400">{tr('ID for boarding', 'बोर्डिंग के लिए पहचान')}</div>
            </button>
            <button onClick={() => window.dispatchEvent(new Event('airyatra:open-chat'))} className="bg-slate-800 border border-slate-700 p-5 text-left hover:border-lime transition-colors">
              <Sparkles className="h-5 w-5 text-lime mb-3" />
              <div className="text-slate-100 font-semibold">{tr('Ask AirYatra', 'AirYatra से पूछें')}</div>
              <div className="text-sm text-slate-400">{tr('Maharashtra trips', 'महाराष्ट्र यात्राएं')}</div>
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <StatTile label={tr('Total trips', 'कुल यात्राएं')} value={formatCount(stats?.total_trips)} testId="total-bookings" />
        <StatTile label={tr('Upcoming', 'आगामी')} value={formatCount(stats?.upcoming_count)} />
        <StatTile label={tr('Awaiting quotes', 'कोटेशन बाकी')} value={formatCount(stats?.pending_count)} tone="amber" testId="pending-bookings" />
        <StatTile label={tr('Spent with us', 'कुल खर्च')} value={formatINR(stats?.total_spent)} />
      </div>

      <Panel title={tr('Recent trips', 'हाल की यात्राएं')} action={<LinkButton onClick={() => navigate('/customer/trips')}>{tr('View all', 'सभी देखें')}</LinkButton>} bodyClassName="">
        <DataTable
          rows={trips.slice(0, 6)}
          rowKey={(r) => r.id}
          onRowClick={() => navigate('/customer/trips')}
          empty={loading ? tr('Loading…', 'लोड हो रहा है…') : tr('Your trips will show here.', 'आपकी यात्राएं यहां दिखेंगी।')}
          columns={[
            { key: 'route', label: tr('Route', 'मार्ग'), render: (r) => `${r.from_location || NO_VALUE} → ${r.to_location || NO_VALUE}` },
            { key: 'date', label: tr('Date', 'तारीख'), render: (r) => formatDate(r.departure_date || r.travel_date || r.created_at) },
            { key: 'ref', label: tr('Reference', 'संदर्भ'), render: (r) => <span className="font-mono text-slate-400">{r.booking_number || r.inquiry_number || NO_VALUE}</span> },
            { key: 'status', label: tr('Status', 'स्थिति'), render: (r) => <Pill tone={statusTone(r.status)}>{humanStatus(r.status)}</Pill> },
            { key: 'amount', label: tr('Amount', 'राशि'), align: 'right', render: (r) => formatINR(r.total_amount || null) },
          ]}
        />
      </Panel>
    </div>
  );
}

function StatTile({ label, value, tone, testId }) {
  return (
    <div className="bg-slate-800 border border-slate-700 p-5">
      <Label>{label}</Label>
      <div className={`font-heading font-extrabold text-4xl leading-none mt-3 ${tone === 'amber' ? 'text-amber' : 'text-slate-100'}`} data-testid={testId}>{value}</div>
    </div>
  );
}

export default CustomerHome;
