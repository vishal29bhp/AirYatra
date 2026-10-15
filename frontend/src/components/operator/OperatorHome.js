import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { operatorAPI, quoteAPI, fleetAPI } from '../../services/api';
import { isApproved } from '../../lib/dashboardData';
import { tr } from '../../lib/bilingual';
import DocumentExpiryAlerts from './DocumentExpiryAlerts';
import {
  PageHead, Panel, Kpi, Pill, DataTable, ActionRow, LinkButton, EmptyNote, Label,
  formatCount, formatDate, humanStatus, statusTone, NO_VALUE,
} from '../dashboard/Premium';

export function timeAgo(value, now = new Date()) {
  const at = new Date(value);
  if (!value || Number.isNaN(at.getTime())) return NO_VALUE;
  const mins = Math.max(0, Math.round((now - at) / 60000));
  if (mins < 60) return tr(`${mins} min ago`, `${mins} मिनट पहले`);
  const hours = Math.round(mins / 60);
  if (hours < 48) return tr(`${hours} h ago`, `${hours} घंटे पहले`);
  return formatDate(value);
}

function OperatorHome({ operator }) {
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [inquiries, setInquiries] = useState([]);
  const [aircraft, setAircraft] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    Promise.allSettled([operatorAPI.getDashboard(), quoteAPI.getInquiries(), fleetAPI.getAll()]).then(([d, q, f]) => {
      if (!alive) return;
      if (d.status === 'fulfilled') setDashboard(d.value.data);
      if (q.status === 'fulfilled') setInquiries(q.value.data.inquiries || []);
      if (f.status === 'fulfilled') setAircraft(f.value.data.aircraft || []);
      setLoading(false);
    });
    return () => { alive = false; };
  }, []);

  const go = (path) => () => navigate(`/operator/${path}`);
  const stats = dashboard?.statistics || {};
  const open = inquiries.filter((i) => i.status === 'pending');
  const approved = isApproved(operator);

  return (
    <div data-testid="operator-home">
      <PageHead eyebrow={tr('Flight desk', 'फ्लाइट डेस्क')} title={<span data-testid="welcome-title">{operator?.company_name || tr('Operator', 'ऑपरेटर')}</span>}>
        <button onClick={go('fleet')} className="px-5 py-2.5 text-sm font-semibold border border-slate-600 text-slate-100 hover:border-lime">
          {tr('Add aircraft', 'विमान जोड़ें')}
        </button>
        <button onClick={go('new-inquiries')} className="px-5 py-2.5 text-sm font-semibold bg-lime text-black hover:bg-lime/90">
          {tr('Open inquiries', 'पूछताछ खोलें')}
        </button>
      </PageHead>

      {!approved && (
        <div className="border border-amber/60 bg-amber/10 p-5 mb-6 flex items-start gap-3" data-testid="verification-alert">
          <AlertCircle className="h-5 w-5 text-amber mt-0.5 shrink-0" />
          <div className="flex-1">
            <div className="text-amber font-semibold">{tr('Verification pending', 'सत्यापन लंबित')}</div>
            <p className="text-slate-300 text-sm m-0">
              {tr('AirYatra is reviewing your documents. You can add aircraft and pilots now; customer inquiries start once you are approved.',
                'AirYatra आपके दस्तावेज़ देख रहा है। आप अभी विमान और पायलट जोड़ सकते हैं; मंज़ूरी के बाद ग्राहक पूछताछ मिलने लगेगी।')}
            </p>
          </div>
          <button onClick={go('profile')} className="shrink-0 px-4 py-2 text-sm font-semibold border border-amber/60 text-amber hover:bg-amber/10">
            {tr('Check documents', 'दस्तावेज़ देखें')}
          </button>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <Kpi label={tr('Open inquiries', 'खुली पूछताछ')} value={<span data-testid="pending-inquiries">{formatCount(stats.pending_inquiries)}</span>} tone="lime" onClick={go('inquiries')} />
        <Kpi label={tr('Bookings', 'बुकिंग')} value={<span data-testid="total-bookings">{formatCount(stats.total_bookings)}</span>} onClick={go('revenue')} />
        <Kpi label={tr('Aircraft', 'विमान')} value={<span data-testid="total-aircraft">{formatCount(stats.total_aircraft)}</span>}
          note={tr(`${aircraft.filter((a) => a.is_available).length} available`, `${aircraft.filter((a) => a.is_available).length} उपलब्ध`)} onClick={go('fleet')} />
        <Kpi label={tr('Pilots', 'पायलट')} value={<span data-testid="total-pilots">{formatCount(stats.total_pilots)}</span>} onClick={go('pilots')} />
      </div>

      <div className="grid lg:grid-cols-5 gap-6 mb-6">
        <Panel className="lg:col-span-3" title={tr('New inquiries', 'नई पूछताछ')} bodyClassName=""
          action={<LinkButton onClick={go('inquiries')}>{tr('All inquiries', 'सभी पूछताछ')}</LinkButton>} testId="new-inquiries">
          {open.length === 0 ? (
            <div className="p-6"><EmptyNote>{loading ? tr('Loading…', 'लोड हो रहा है…') : approved
              ? tr('No open inquiries. New ones show here as customers ask.', 'कोई खुली पूछताछ नहीं। नई पूछताछ यहां दिखेगी।')
              : tr('Inquiries start arriving after approval.', 'मंज़ूरी के बाद पूछताछ आनी शुरू होगी।')}</EmptyNote></div>
          ) : open.slice(0, 5).map((i) => {
            const b = i.booking || {};
            return (
              <ActionRow
                key={i.id}
                title={`${b.from_location || NO_VALUE} → ${b.to_location || NO_VALUE}`}
                subtitle={[formatDate(b.departure_date), b.passengers ? tr(`${b.passengers} pax`, `${b.passengers} यात्री`) : null].filter(Boolean).join(' · ')}
                right={<span className="font-mono text-xs text-amber whitespace-nowrap">{timeAgo(i.created_at)}</span>}
                actionLabel={tr('Send quote', 'कोटेशन भेजें')}
                primary
                onAction={go('inquiries')}
              />
            );
          })}
        </Panel>

        <Panel className="lg:col-span-2" title={tr('Recent bookings', 'हाल की बुकिंग')} bodyClassName="">
          <DataTable
            rows={(dashboard?.recent_bookings || []).slice(0, 5)}
            onRowClick={go('inquiries')}
            empty={loading ? tr('Loading…', 'लोड हो रहा है…') : tr('No bookings yet.', 'अभी कोई बुकिंग नहीं।')}
            columns={[
              { key: 'route', label: tr('Route', 'मार्ग'), render: (r) => `${r.from_location || r.pickup_location || NO_VALUE} → ${r.to_location || r.drop_location || NO_VALUE}` },
              { key: 'status', label: tr('Status', 'स्थिति'), align: 'right', render: (r) => <Pill tone={statusTone(r.status)}>{humanStatus(r.status)}</Pill> },
            ]}
          />
        </Panel>
      </div>

      <Panel title={tr('Fleet', 'फ्लीट')} action={<LinkButton onClick={go('fleet')}>{tr('Manage fleet', 'फ्लीट प्रबंधन')}</LinkButton>} className="mb-6">
        {aircraft.length === 0 ? (
          <EmptyNote>{loading ? tr('Loading…', 'लोड हो रहा है…') : tr('Add your first aircraft so customers can be matched to it.', 'पहला विमान जोड़ें ताकि ग्राहक उससे जुड़ सकें।')}</EmptyNote>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {aircraft.slice(0, 8).map((a) => (
              <button key={a.id} onClick={go('fleet')} className="border border-slate-700 p-4 text-left hover:border-lime transition-colors">
                <div className="font-heading font-extrabold uppercase text-2xl text-slate-100 leading-none">{a.registration_number || NO_VALUE}</div>
                <div className="text-sm text-slate-300 mt-1">{a.aircraft_type}</div>
                <Label className="mt-3">{a.base_location || NO_VALUE}</Label>
                <div className="mt-2">
                  {a.maintenance_status && a.maintenance_status !== 'operational'
                    ? <Pill tone="amber">{humanStatus(a.maintenance_status)}</Pill>
                    : a.is_available ? <Pill tone="lime">{tr('Ready', 'तैयार')}</Pill> : <Pill>{tr('Busy', 'व्यस्त')}</Pill>}
                </div>
              </button>
            ))}
          </div>
        )}
      </Panel>

      <DocumentExpiryAlerts />
    </div>
  );
}

export default OperatorHome;
