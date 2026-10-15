import React, { useState } from 'react';
import { LogOut, Plane, Home, DollarSign, FileText, CreditCard, TrendingUp, ChevronDown, ChevronRight, BarChart3, Settings, Calculator, Receipt, Wallet, PieChart, Building2, RefreshCw, Users, BanknoteIcon, Percent, CheckCircle, Shield, Clock, Activity, Landmark, CircleDollarSign, Target, Bot, Bell, Archive, History, Globe, FileDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import NotificationBell from '@/components/shared/NotificationBell';
import { useResponsiveSidebar, MobileMenuButton, ResponsiveSidebar, CollapsibleNavGroup, NavItem } from '@/components/shared/Sidebar';
import { BrandMark } from '@/components/dashboard/Premium';
import FinanceHome from '@/components/finance/FinanceHome';

// Import Finance Components
import SettlementManagement from '@/components/admin/SettlementManagement';
import InvoiceManagement from '@/components/admin/InvoiceManagement';
import DynamicPricing from '@/components/admin/DynamicPricing';
import AccountingIntegration from '@/components/admin/AccountingIntegration';
import CurrencyConverter from '@/components/admin/CurrencyConverter';
import { bi, tr } from '../lib/bilingual';

// Lazy load new Finance components
const BulkSalaryPayment = React.lazy(() => import('@/components/finance/BulkSalaryPayment'));
const VendorBillPayment = React.lazy(() => import('@/components/finance/VendorBillPayment'));
const TDSConfiguration = React.lazy(() => import('@/components/finance/TDSConfiguration'));
const ApprovalWorkflow = React.lazy(() => import('@/components/finance/ApprovalWorkflow'));
const GSTDashboard = React.lazy(() => import('@/components/finance/GSTDashboard'));
const GSTReturns = React.lazy(() => import('@/components/finance/GSTReturns'));
const GSTPayments = React.lazy(() => import('@/components/finance/GSTPayments'));
const ITCManagement = React.lazy(() => import('@/components/finance/ITCManagement'));
const VendorCompliance = React.lazy(() => import('@/components/finance/VendorCompliance'));

// Treasury ERP Components (Phase 1)
const TreasuryDashboard = React.lazy(() => import('@/components/finance/TreasuryDashboard'));
const FinanceCommandCenter = React.lazy(() => import('@/components/finance/FinanceCommandCenter'));

// Finance ERP Phase 2 & 3 Components
const GovernmentChallans = React.lazy(() => import('@/components/finance/GovernmentChallans'));
const ComplianceDashboard = React.lazy(() => import('@/components/finance/ComplianceDashboard'));
const BankReconciliation = React.lazy(() => import('@/components/finance/BankReconciliation'));

// Finance ERP Phase 4 Components
const BudgetVsActual = React.lazy(() => import('@/components/finance/BudgetVsActual'));
const AIFinanceAssistant = React.lazy(() => import('@/components/finance/AIFinanceAssistant'));
const AutoReminders = React.lazy(() => import('@/components/finance/AutoReminders'));
const BillRepository = React.lazy(() => import('@/components/finance/BillRepository'));

// Finance ERP Phase 5 Components
const AuditTrailDashboard = React.lazy(() => import('@/components/finance/AuditTrailDashboard'));
const ExpenseAnalytics = React.lazy(() => import('@/components/finance/ExpenseAnalytics'));
const MultiCurrencySupport = React.lazy(() => import('@/components/finance/MultiCurrencySupport'));
const PDFInvoiceExport = React.lazy(() => import('@/components/finance/PDFInvoiceExport'));

// Finance Analytics Dashboard (Revenue Trends, Gateway Reconciliation)
const FinanceAnalyticsDashboard = React.lazy(() => import('@/components/finance/FinanceAnalyticsDashboard'));

// Payment Reconciliation & Finance Reports
const PaymentReconciliation = React.lazy(() => import('@/components/finance/PaymentReconciliation'));

// Scheduled Reports & Settlement Sync
const ScheduledReportsManager = React.lazy(() => import('@/components/finance/ScheduledReportsManager'));

// Organized Navigation Structure - 8 Main Categories (with Treasury ERP)
const navGroups = [
  {
    id: 'treasury',
    label: bi('Treasury ERP / खजाना'),
    icon: Landmark,
    items: [
      { id: 'overview', label: tr('Overview', 'अवलोकन'), icon: Home },
      { id: 'treasury_dashboard', label: 'Treasury Dashboard', icon: Wallet, highlight: true },
      { id: 'command_center', label: 'Command Center 24x7', icon: Activity, highlight: true },
      { id: 'bank_accounts', label: 'Bank Accounts', icon: Building2 },
      { id: 'cashflow_forecast', label: 'Cashflow Forecast', icon: TrendingUp },
      { id: 'bank_reconciliation', label: 'Bank Reconciliation', icon: RefreshCw, highlight: true },
    ]
  },
  {
    id: 'compliance',
    label: bi('Compliance / अनुपालन'),
    icon: Shield,
    items: [
      { id: 'compliance_dashboard', label: 'Compliance Dashboard', icon: Shield, highlight: true },
      { id: 'govt_challans', label: 'Govt Challans (GST/TDS)', icon: FileText, highlight: true },
      { id: 'auto_reminders', label: 'Auto Reminders', icon: Clock, highlight: true },
    ]
  },
  {
    id: 'analytics',
    label: bi('Analytics / विश्लेषण'),
    icon: BarChart3,
    items: [
      { id: 'finance_analytics', label: 'Revenue & Recon', icon: TrendingUp, highlight: true },
      { id: 'payment_reconciliation', label: 'Payment Reconciliation', icon: RefreshCw, highlight: true },
      { id: 'budget_vs_actual', label: 'Budget vs Actual', icon: Target, highlight: true },
      { id: 'ai_assistant', label: 'AI Finance Assistant', icon: Activity, highlight: true },
      { id: 'bill_repository', label: 'Bill Repository', icon: FileText, highlight: true },
      { id: 'expense_analytics', label: 'Expense Analytics', icon: PieChart, highlight: true },
    ]
  },
  {
    id: 'advanced',
    label: bi('Advanced / उन्नत'),
    icon: Settings,
    items: [
      { id: 'scheduled_reports', label: 'Scheduled Reports', icon: Clock, highlight: true },
      { id: 'audit_trail', label: 'Audit Trail', icon: History, highlight: true },
      { id: 'multi_currency', label: 'Multi-Currency', icon: Globe, highlight: true },
      { id: 'pdf_invoice', label: 'PDF Invoice Export', icon: FileDown, highlight: true },
    ]
  },
  {
    id: 'main',
    label: bi('Dashboard / डैशबोर्ड'),
    icon: Home,
    items: [
      { id: 'overview', label: bi('Overview / ओवरव्यू'), icon: BarChart3 },
      { id: 'pending_approvals', label: 'Pending Approvals', icon: Clock, highlight: true },
    ]
  },
  {
    id: 'payroll',
    label: bi('Payroll / वेतन'),
    icon: BanknoteIcon,
    items: [
      { id: 'bulk_salary', label: 'Bulk Salary Payment', icon: Users, highlight: true },
      { id: 'approval_workflow', label: 'Approval Workflow', icon: CheckCircle },
    ]
  },
  {
    id: 'vendors',
    label: bi('Vendors / वेंडर'),
    icon: Building2,
    items: [
      { id: 'vendor_bills', label: 'Vendor Bill Payment', icon: Receipt, highlight: true },
      { id: 'tds_config', label: 'TDS Configuration', icon: Percent },
    ]
  },
  {
    id: 'billing',
    label: bi('Billing / बिलिंग'),
    icon: Receipt,
    items: [
      { id: 'invoices', label: 'Invoice & GST Billing', icon: FileText, highlight: true },
      { id: 'payments', label: bi('Payments / भुगतान'), icon: CreditCard },
      { id: 'refunds', label: bi('Refunds / वापसी'), icon: RefreshCw },
    ]
  },
  {
    id: 'gst',
    label: 'GST Compliance / GST',
    icon: FileText,
    items: [
      { id: 'gst_dashboard', label: 'GST Dashboard', icon: BarChart3, highlight: true },
      { id: 'gst_returns', label: 'File GST Returns', icon: FileText },
      { id: 'gst_payments', label: 'GST Payments', icon: CreditCard },
      { id: 'itc_management', label: 'Input/Output ITC', icon: TrendingUp },
      { id: 'vendor_compliance', label: 'Vendor Compliance', icon: Building2 },
    ]
  },
  {
    id: 'settlements',
    label: bi('Settlements / निपटान'),
    icon: DollarSign,
    items: [
      { id: 'all_settlements', label: bi('All Settlements / सभी'), icon: DollarSign },
      { id: 'operator_payouts', label: 'Operator Payouts', icon: Building2 },
      { id: 'helipad_payouts', label: 'Helipad Payouts', icon: Building2 },
    ]
  },
  {
    id: 'accounting',
    label: bi('Accounting / लेखा'),
    icon: FileText,
    items: [
      { id: 'accounting_integration', label: 'Tally/QuickBooks', icon: FileText },
      { id: 'reports', label: 'Financial Reports', icon: BarChart3 },
    ]
  },
];

function FinanceDashboard({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [expandedGroups, setExpandedGroups] = useState(['treasury']);
  const sidebar = useResponsiveSidebar();

  const toggleGroup = (groupId) => {
    setExpandedGroups(prev => 
      prev.includes(groupId) 
        ? prev.filter(id => id !== groupId)
        : [...prev, groupId]
    );
  };

  const handleNavClick = (itemId, groupId) => {
    setActiveTab(itemId);
    if (!expandedGroups.includes(groupId)) {
      setExpandedGroups(prev => [...prev, groupId]);
    }
    sidebar.closeMobile();
  };

  const getActiveGroup = () => {
    for (const group of navGroups) {
      if (group.items.some(item => item.id === activeTab)) {
        return group.id;
      }
    }
    return null;
  };

  const renderContent = () => {
    switch (activeTab) {
      // Treasury ERP Routes
      case 'treasury_dashboard':
      case 'bank_accounts':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <TreasuryDashboard />
          </React.Suspense>
        );
      case 'command_center':
      case 'cashflow_forecast':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <FinanceCommandCenter />
          </React.Suspense>
        );
      case 'bank_reconciliation':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <BankReconciliation />
          </React.Suspense>
        );
      case 'compliance_dashboard':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <ComplianceDashboard />
          </React.Suspense>
        );
      case 'govt_challans':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <GovernmentChallans />
          </React.Suspense>
        );
      case 'auto_reminders':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <AutoReminders />
          </React.Suspense>
        );
      case 'budget_vs_actual':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <BudgetVsActual />
          </React.Suspense>
        );
      case 'ai_assistant':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <AIFinanceAssistant />
          </React.Suspense>
        );
      case 'bill_repository':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <BillRepository />
          </React.Suspense>
        );
      case 'all_settlements':
      case 'pending_settlements':
        return <SettlementManagement />;
      case 'invoices':
        return <InvoiceManagement />;
      case 'dynamic_pricing':
        return <DynamicPricing />;
      case 'accounting_integration':
        return <AccountingIntegration />;
      case 'currency':
        return <CurrencyConverter />;
      case 'bulk_salary':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <BulkSalaryPayment />
          </React.Suspense>
        );
      case 'approval_workflow':
      case 'pending_approvals':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <ApprovalWorkflow userRole={user?.role} />
          </React.Suspense>
        );
      case 'vendor_bills':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <VendorBillPayment />
          </React.Suspense>
        );
      case 'tds_config':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <TDSConfiguration />
          </React.Suspense>
        );
      // GST Compliance Routes - Individual Components
      case 'gst_dashboard':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <GSTDashboard />
          </React.Suspense>
        );
      case 'gst_returns':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <GSTReturns />
          </React.Suspense>
        );
      case 'gst_payments':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <GSTPayments />
          </React.Suspense>
        );
      case 'itc_management':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <ITCManagement />
          </React.Suspense>
        );
      case 'vendor_compliance':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <VendorCompliance />
          </React.Suspense>
        );
      // Phase 5 Routes
      case 'audit_trail':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <AuditTrailDashboard />
          </React.Suspense>
        );
      case 'expense_analytics':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <ExpenseAnalytics />
          </React.Suspense>
        );
      case 'multi_currency':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <MultiCurrencySupport />
          </React.Suspense>
        );
      case 'pdf_invoice':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <PDFInvoiceExport />
          </React.Suspense>
        );
      case 'finance_analytics':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <FinanceAnalyticsDashboard />
          </React.Suspense>
        );
      case 'payment_reconciliation':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <PaymentReconciliation />
          </React.Suspense>
        );
      case 'scheduled_reports':
        return (
          <React.Suspense fallback={<div className="flex items-center justify-center h-64"><RefreshCw className="h-8 w-8 animate-spin text-emerald-500" /></div>}>
            <ScheduledReportsManager />
          </React.Suspense>
        );
      default:
        return <FinanceHome onNavigate={setActiveTab} />;
    }
  };

  const activeGroup = getActiveGroup();

  return (
    <div className="min-h-screen bg-slate-900" data-testid="finance-dashboard">
      {/* Top Navigation */}
      <nav className="bg-slate-900 border-b border-slate-700 sticky top-0 z-50">
        <div className="max-w-full mx-auto px-4 lg:px-6 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <MobileMenuButton onClick={sidebar.toggleMobile} isOpen={sidebar.isMobileOpen} />
            <BrandMark tag={tr('Finance', 'वित्त')} />
          </div>
          <div className="flex items-center space-x-2 lg:space-x-4">
            <NotificationBell user={user} />
            <span className="text-slate-300 hidden sm:inline text-sm">{user.full_name}</span>
            <Button variant="ghost" onClick={onLogout} className="text-white hover:text-lime" data-testid="logout-btn">
              <LogOut className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </nav>

      <div className="flex min-h-[calc(100vh-73px)]">
        <ResponsiveSidebar
          isCollapsed={sidebar.isCollapsed}
          isMobileOpen={sidebar.isMobileOpen}
          isHovered={sidebar.isHovered}
          setIsHovered={sidebar.setIsHovered}
          closeMobile={sidebar.closeMobile}
          toggleCollapse={sidebar.toggleCollapse}
        >
          {navGroups.map((group) => (
            <CollapsibleNavGroup
              key={group.id}
              icon={group.icon}
              label={group.label}
              isExpanded={expandedGroups.includes(group.id)}
              onToggle={() => toggleGroup(group.id)}
              isActive={activeGroup === group.id}
              isCollapsed={sidebar.effectiveCollapsed}
            >
              {group.items.map((item) => (
                <NavItem
                  key={item.id}
                  icon={item.icon}
                  label={item.label}
                  isActive={activeTab === item.id}
                  onClick={() => handleNavClick(item.id, group.id)}
                  isCollapsed={sidebar.effectiveCollapsed}
                  testId={`nav-${item.id}`}
                />
              ))}
            </CollapsibleNavGroup>
          ))}
        </ResponsiveSidebar>

        {/* Main Content */}
        <main className="flex-1 p-4 lg:p-6 overflow-y-auto">
          <div className="max-w-7xl mx-auto">
            {renderContent()}
          </div>
        </main>
      </div>
    </div>
  );
}

export default FinanceDashboard;
