import React, { useEffect, useState } from 'react';
import api from '@/services/apiClient';
import { summariseSettlements } from '../../lib/dashboardData';
import { tr } from '../../lib/bilingual';
import {
  PageHead, Panel, Kpi, Pill, DataTable, LinkButton, EmptyNote,
  formatINR, formatCount, formatDate, humanStatus, statusTone, NO_VALUE,
} from '../dashboard/Premium';

function FinanceHome({ onNavigate }) {
  const [finance, setFinance] = useState(null);
  const [settlements, setSettlements] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    Promise.allSettled([api.get('/payments/finance/dashboard'), api.get('/admin/settlements/')]).then(([f, s]) => {
      if (!alive) return;
      if (f.status === 'fulfilled') setFinance(f.value.data);
      if (s.status === 'fulfilled') setSettlements(s.value.data.settlements || []);
      setLoading(false);
    });
    return () => { alive = false; };
  }, []);

  const { due, total } = summariseSettlements(settlements);
  const gateways = finance?.gateways || [];
  const go = (tab) => () => onNavigate(tab);

  return (
    <div data-testid="finance-home">
      <PageHead eyebrow={tr('Finance', 'वित्त')} title={tr('Ledger', 'लेजर')}>
        <button onClick={go('pending_settlements')} className="px-5 py-2.5 text-sm font-semibold bg-lime text-black hover:bg-lime/90">
          {tr('Review payouts', 'भुगतान देखें')}
        </button>
      </PageHead>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <Kpi label={tr('Collected today', 'आज प्राप्त')} value={formatINR(finance?.today_transactions?.total_amount)}
          note={finance ? tr(`${finance.today_transactions?.count || 0} payments`, `${finance.today_transactions?.count || 0} भुगतान`) : null} />
        <Kpi label={tr('Operator payouts due', 'ऑपरेटर भुगतान बाकी')} value={settlements ? formatINR(total) : NO_VALUE}
          note={settlements ? tr(`${due.length} settlements`, `${due.length} सेटलमेंट`) : null} tone={due.length ? 'amber' : 'default'} onClick={go('pending_settlements')} />
        <Kpi label={tr('Approvals waiting', 'अनुमोदन बाकी')} value={formatCount(finance?.pending_approvals)}
          tone={finance?.pending_approvals ? 'amber' : 'default'} onClick={go('pending_approvals')} />
        <Kpi label={tr('TDS this quarter', 'इस तिमाही TDS')} value={formatINR(finance?.tds_summary?.total_tds)}
          note={finance?.tds_summary?.quarter} onClick={go('tds_config')} />
      </div>

      <div className="grid lg:grid-cols-3 gap-6 mb-6">
        <Panel className="lg:col-span-2" title={tr('Payout queue', 'भुगतान कतार')} bodyClassName=""
          action={<LinkButton onClick={go('all_settlements')}>{tr('All settlements', 'सभी सेटलमेंट')}</LinkButton>} testId="payout-queue">
          <DataTable
            rows={due.slice(0, 8)}
            onRowClick={go('pending_settlements')}
            empty={loading ? tr('Loading…', 'लोड हो रहा है…') : settlements ? tr('Nothing to pay out right now.', 'अभी कोई भुगतान बाकी नहीं।') : tr('Settlements could not be loaded.', 'सेटलमेंट लोड नहीं हो सके।')}
            columns={[
              { key: 'operator', label: tr('Operator', 'ऑपरेटर'), render: (r) => <div><div>{r.operator_name || NO_VALUE}</div><div className="font-mono text-xs text-slate-400">{r.settlement_number}</div></div> },
              { key: 'period', label: tr('Created', 'बनाया'), render: (r) => formatDate(r.created_at) },
              { key: 'status', label: tr('Status', 'स्थिति'), render: (r) => <Pill tone={statusTone(r.status)}>{humanStatus(r.status)}</Pill> },
              { key: 'amount', label: tr('Amount', 'राशि'), align: 'right', render: (r) => formatINR(r.payout_amount ?? r.net_amount ?? r.amount) },
            ]}
          />
        </Panel>

        <Panel title={tr('Payment gateways', 'पेमेंट गेटवे')} bodyClassName="">
          {gateways.length === 0 ? (
            <div className="p-6"><EmptyNote>{loading ? tr('Loading…', 'लोड हो रहा है…') : tr('No gateway reported.', 'कोई गेटवे नहीं मिला।')}</EmptyNote></div>
          ) : gateways.map((g) => (
            <div key={g.name} className="flex items-center justify-between px-6 py-4 border-b border-slate-700 last:border-b-0">
              <span className="text-slate-100">{g.display_name || g.name}</span>
              {g.is_configured && !g.is_mock
                ? <Pill tone="lime">{tr('Live', 'चालू')}</Pill>
                : <Pill tone="amber">{tr('Keys not set', 'कुंजी नहीं')}</Pill>}
            </div>
          ))}
        </Panel>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        {[
          ['bulk_salary', tr('Salary run', 'सैलरी भुगतान'), tr('Pay staff in one batch', 'एक साथ स्टाफ भुगतान')],
          ['vendor_bills', tr('Vendor bills', 'वेंडर बिल'), tr(`${finance?.pending_vendor_bills ?? NO_VALUE} approved, unpaid`, `${finance?.pending_vendor_bills ?? NO_VALUE} स्वीकृत, अदत्त`)],
          ['invoices', tr('Invoices', 'चालान'), tr('GST invoices to customers', 'ग्राहकों के GST चालान')],
          ['gst_dashboard', tr('GST', 'जीएसटी'), tr('Returns and payments', 'रिटर्न और भुगतान')],
        ].map(([tab, title, sub]) => (
          <button key={tab} onClick={go(tab)} className="bg-slate-800 border border-slate-700 p-5 text-left hover:border-lime transition-colors">
            <div className="font-heading font-extrabold uppercase text-xl text-slate-100">{title}</div>
            <div className="text-sm text-slate-400 mt-1">{sub}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default FinanceHome;
