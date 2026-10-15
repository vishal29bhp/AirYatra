import React from 'react';
import { ChevronRight } from 'lucide-react';

// Building blocks for the role home screens (Vaayu Prive look): square flat cards, condensed uppercase headings,
// mono labels, lime for the one primary action and amber for things that need attention.

export const NO_VALUE = '—';

export function formatINR(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return NO_VALUE;
  const n = Number(value);
  if (Math.abs(n) >= 10000000) return `₹${(n / 10000000).toFixed(2)} Cr`;
  if (Math.abs(n) >= 100000) return `₹${(n / 100000).toFixed(1)} L`;
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

export function formatCount(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return NO_VALUE;
  return Number(value).toLocaleString('en-IN');
}

export function formatDate(value) {
  if (!value) return NO_VALUE;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return NO_VALUE;
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function humanStatus(status) {
  return (status || '').replace(/_/g, ' ') || NO_VALUE;
}

export function Label({ children, className = '' }) {
  return (
    <p className={`font-mono text-[11px] uppercase tracking-[0.14em] text-slate-400 m-0 ${className}`}>{children}</p>
  );
}

export function PageHead({ eyebrow, title, children }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div>
        {eyebrow && <Label className="mb-1">{eyebrow}</Label>}
        <h1 className="font-heading font-extrabold uppercase text-4xl lg:text-5xl leading-none text-slate-100 m-0" data-testid="page-title">
          {title}
        </h1>
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  );
}

export function Panel({ title, action, children, className = '', bodyClassName = 'p-6', testId }) {
  return (
    <section className={`bg-slate-800 border border-slate-700 ${className}`} data-testid={testId}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-4 px-6 pt-5 pb-4 border-b border-slate-700">
          {title && <h2 className="font-heading font-extrabold uppercase text-2xl leading-none text-slate-100 m-0">{title}</h2>}
          {action}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

const TONES = {
  default: 'text-slate-100',
  lime: 'text-lime',
  amber: 'text-amber',
};

export function Kpi({ label, value, note, tone = 'default', noteTone, onClick, testId }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      onClick={onClick}
      data-testid={testId}
      className={`bg-slate-800 border border-slate-700 p-5 text-left w-full ${onClick ? 'hover:border-lime transition-colors' : ''}`}
    >
      <Label>{label}</Label>
      <div className={`font-heading font-extrabold text-4xl lg:text-5xl leading-none mt-3 ${TONES[tone]}`}>{value}</div>
      {note && <p className={`text-sm mt-2 m-0 ${noteTone === 'amber' ? 'text-amber' : noteTone === 'lime' ? 'text-lime' : 'text-slate-400'}`}>{note}</p>}
    </Tag>
  );
}

export function Pill({ children, tone = 'default' }) {
  const styles = {
    default: 'border-slate-600 text-slate-300',
    lime: 'border-lime/60 text-lime',
    amber: 'border-amber/60 text-amber',
    red: 'border-red-400/60 text-red-300',
  };
  return (
    <span className={`inline-block font-mono text-[11px] uppercase tracking-[0.1em] border px-2 py-0.5 whitespace-nowrap ${styles[tone]}`}>
      {children}
    </span>
  );
}

export function statusTone(status) {
  if (['completed', 'confirmed', 'paid', 'active', 'approved', 'verified'].includes(status)) return 'lime';
  if (['cancelled', 'rejected', 'failed', 'suspended'].includes(status)) return 'red';
  if (['pending', 'pending_quotes', 'quotes_received', 'pending_acceptance', 'quote_received', 'under_review'].includes(status)) return 'amber';
  return 'default';
}

export function BarRow({ label, value, max, suffix = '' }) {
  const pct = max > 0 ? Math.max(4, Math.round((value / max) * 100)) : 0;
  return (
    <div className="mb-4 last:mb-0">
      <div className="flex justify-between text-sm text-slate-200 mb-1.5">
        <span className="truncate pr-4">{label}</span>
        <span className="font-mono text-slate-400">{value}{suffix}</span>
      </div>
      <div className="h-2 bg-slate-700">
        <div className="h-2 bg-lime" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function ActionRow({ title, subtitle, actionLabel, onAction, primary = false, right }) {
  return (
    <div className="flex items-center justify-between gap-4 px-6 py-4 border-b border-slate-700 last:border-b-0">
      <div className="min-w-0">
        <div className="text-slate-100 font-semibold truncate">{title}</div>
        {subtitle && <div className="text-sm text-slate-400 truncate">{subtitle}</div>}
      </div>
      {right}
      {actionLabel && (
        <button
          onClick={onAction}
          className={`shrink-0 px-4 py-2 text-sm font-semibold border transition-colors ${
            primary ? 'bg-lime text-black border-lime hover:bg-lime/90' : 'border-slate-600 text-slate-100 hover:border-lime'
          }`}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

export function LinkButton({ children, onClick }) {
  return (
    <button onClick={onClick} className="flex items-center gap-1 text-sm text-lime hover:text-lime/80">
      {children} <ChevronRight className="h-4 w-4" />
    </button>
  );
}

export function SegButton({ active, children, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-5 py-2.5 text-sm font-semibold border transition-colors ${
        active ? 'bg-lime text-black border-lime' : 'border-slate-600 text-slate-100 hover:border-lime'
      }`}
    >
      {children}
    </button>
  );
}

export function EmptyNote({ children }) {
  return <p className="text-sm text-slate-400 m-0">{children}</p>;
}

export function DataTable({ columns, rows, empty, rowKey = (r) => r.id, onRowClick }) {
  if (!rows || rows.length === 0) return <div className="p-6"><EmptyNote>{empty}</EmptyNote></div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            {columns.map((c) => (
              <th key={c.key} className={`px-6 py-3 font-mono text-[11px] uppercase tracking-[0.14em] text-slate-400 font-normal ${c.align === 'right' ? 'text-right' : 'text-left'}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={rowKey(r)}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
              className={`border-b border-slate-700 last:border-b-0 ${onRowClick ? 'cursor-pointer hover:bg-slate-700/40' : ''}`}
            >
              {columns.map((c) => (
                <td key={c.key} className={`px-6 py-3 text-slate-200 ${c.align === 'right' ? 'text-right' : ''}`}>
                  {c.render ? c.render(r) : r[c.key] ?? NO_VALUE}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Brand mark used in every dashboard's top bar.
export function BrandMark({ tag }) {
  return (
    <div className="flex items-center gap-2">
      <span className="font-heading font-extrabold uppercase text-2xl tracking-wide text-slate-100 leading-none">AirYatra</span>
      {tag && <span className="font-mono text-[10px] uppercase tracking-[0.12em] bg-amber text-black px-1.5 py-0.5">{tag}</span>}
    </div>
  );
}
