import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Plane, Home, Calendar, FileText, Wallet, LogOut, MapPin, MessageSquare, User, Gift, ChevronDown, ChevronRight, Settings, CreditCard, HelpCircle, Star, Shield, PieChart, TrendingUp, Sparkles, Menu, Gavel, Scale } from 'lucide-react';
import { Button } from '@/components/ui/button';
import MyTrips from '../components/customer/MyTrips';
import ChatWidget from '../components/customer/ChatWidget';
import CustomerProfile from '../components/customer/CustomerProfile';
import ReferAndEarn from '../components/customer/ReferAndEarn';
import LoyaltyRewards from '../components/customer/LoyaltyRewards';
import CustomerPaymentHistory from '../components/customer/CustomerPaymentHistory';
import CustomerBookingStats from '../components/customer/CustomerBookingStats';
import FlightPriceHistory from '../components/customer/FlightPriceHistory';
import RouteSuggestions from '../components/customer/RouteSuggestions';
import NotificationBell from '../components/shared/NotificationBell';
import GlobalSearch from '../components/shared/GlobalSearch';
import CustomerHome from '../components/customer/CustomerHome';
import CustomerKYCUpload from '../components/customer/CustomerKYCUpload';
import LoginActivityLog from '../components/auth/LoginActivityLog';
import TwoFactorSetup from '../components/auth/TwoFactorSetup';
import { CustomerAuctions } from '../components/auction/AuctionDashboard';
import { useResponsiveSidebar, MobileMenuButton, ResponsiveSidebar, CollapsibleNavGroup, navItemClass } from '../components/shared/Sidebar';
import { BrandMark } from '../components/dashboard/Premium';
import { AircraftComparison } from '../components/aircraft/AircraftComparison';
import { bi, tr } from '../lib/bilingual';

// Organized Navigation Structure - 4 Main Categories
const navGroups = [
  {
    id: 'main',
    label: bi('Main / मुख्य'),
    icon: Home,
    items: [
      { id: 'overview', label: tr('Dashboard', 'डैशबोर्ड'), icon: Home, path: '/customer' },
      { id: 'trips', label: bi('My Trips / मेरी यात्राएं'), icon: MapPin, path: '/customer/trips', highlight: true },
      { id: 'compare', label: bi('Compare Aircraft / तुलना करें'), icon: Scale, path: '/customer/compare', highlight: true },
      { id: 'stats', label: bi('My Stats / मेरे आंकड़े'), icon: PieChart, path: '/customer/stats', highlight: true },
      { id: 'price-trends', label: bi('Price Trends / कीमत रुझान'), icon: TrendingUp, path: '/customer/price-trends', highlight: true },
      { id: 'route-suggestions', label: bi('Route Ideas / मार्ग सुझाव'), icon: Sparkles, path: '/customer/route-suggestions', highlight: true },
      { id: 'booking', label: bi('New Booking / नई बुकिंग'), icon: Calendar, path: '/booking', external: true, highlight: true },
      { id: 'auctions', label: bi('Live Auctions / लाइव नीलामी'), icon: Gavel, path: '/customer/auctions', highlight: true },
    ]
  },
  {
    id: 'rewards',
    label: bi('Rewards & Offers / पुरस्कार'),
    icon: Gift,
    items: [
      { id: 'payments', label: bi('Payment History / भुगतान'), icon: CreditCard, path: '/customer/payments', highlight: true },
      { id: 'refer', label: bi('Refer & Earn / रेफर करें'), icon: Gift, path: '/customer/refer' },
      { id: 'wallet', label: bi('My Wallet / वॉलेट'), icon: Wallet, path: '/customer/wallet' },
      { id: 'loyalty', label: bi('VIP Points / वीआईपी'), icon: Star, path: '/customer/loyalty' },
    ]
  },
  {
    id: 'support',
    label: bi('Support / सहायता'),
    icon: HelpCircle,
    items: [
      { id: 'messages', label: bi('Messages / संदेश'), icon: MessageSquare, path: '/customer/messages' },
      { id: 'help', label: bi('Help Center / मदद'), icon: HelpCircle, path: '/customer/help' },
    ]
  },
  {
    id: 'account',
    label: bi('Account / खाता'),
    icon: User,
    items: [
      { id: 'profile', label: bi('Profile / प्रोफाइल'), icon: User, path: '/customer/profile' },
      { id: 'kyc', label: bi('KYC Documents / केवाईसी'), icon: Shield, path: '/customer/kyc', highlight: true },
      { id: 'security', label: bi('Security / सुरक्षा'), icon: Shield, path: '/customer/security' },
      { id: 'settings', label: bi('Settings / सेटिंग्स'), icon: Settings, path: '/customer/settings' },
    ]
  },
];

function CustomerDashboard({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [expandedGroups, setExpandedGroups] = useState(['main']);
  const navigate = useNavigate();
  const location = useLocation();
  
  // Responsive sidebar hook
  const sidebar = useResponsiveSidebar();

  // Sync activeTab with URL
  useEffect(() => {
    const path = location.pathname;
    if (path.includes('/trips')) setActiveTab('trips');
    else if (path.includes('/profile')) setActiveTab('profile');
    else if (path.includes('/messages')) setActiveTab('messages');
    else if (path.includes('/refer')) setActiveTab('refer');
    else if (path.includes('/loyalty')) setActiveTab('loyalty');
    else if (path.includes('/payments')) setActiveTab('payments');
    else if (path.includes('/stats')) setActiveTab('stats');
    else if (path.includes('/price-trends')) setActiveTab('price-trends');
    else if (path.includes('/route-suggestions')) setActiveTab('route-suggestions');
    else if (path.includes('/kyc')) setActiveTab('kyc');
    else setActiveTab('overview');
  }, [location.pathname]);

  const toggleGroup = (groupId) => {
    setExpandedGroups(prev => 
      prev.includes(groupId) 
        ? prev.filter(id => id !== groupId)
        : [...prev, groupId]
    );
  };

  const handleNavClick = (item, groupId) => {
    if (item.external) {
      navigate(item.path);
    } else {
      setActiveTab(item.id);
      navigate(item.path);
    }
    if (!expandedGroups.includes(groupId)) {
      setExpandedGroups(prev => [...prev, groupId]);
    }
    // Close mobile sidebar
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
      case 'trips':
        return <MyTrips user={user} />;
      case 'profile':
        return <CustomerProfile user={user} />;
      case 'kyc':
        return <CustomerKYCUpload user={user} />;
      case 'security':
        return (
          <div className="space-y-6">
            <TwoFactorSetup user={user} />
            <LoginActivityLog user={user} />
          </div>
        );
      case 'messages':
        return <ChatWidget user={user} />;
      case 'refer':
        return <ReferAndEarn user={user} />;
      case 'loyalty':
        return <LoyaltyRewards user={user} />;
      case 'payments':
        return <CustomerPaymentHistory user={user} />;
      case 'stats':
        return <CustomerBookingStats user={user} />;
      case 'price-trends':
        return <FlightPriceHistory user={user} />;
      case 'route-suggestions':
        return <RouteSuggestions user={user} />;
      case 'auctions':
        return <CustomerAuctions />;
      case 'compare':
        return <AircraftComparison onClose={() => setActiveTab('overview')} />;
      default:
        return <CustomerHome user={user} />;
    }
  };

  const activeGroup = getActiveGroup();

  return (
    <div className="min-h-screen bg-slate-900" data-testid="customer-dashboard">
      {/* Top Navigation */}
      <nav className="bg-slate-900 border-b border-slate-700 sticky top-0 z-50">
        <div className="max-w-full mx-auto px-4 lg:px-6 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-2">
            {/* Mobile Menu Button */}
            <MobileMenuButton 
              onClick={sidebar.toggleMobile} 
              isOpen={sidebar.isMobileOpen}
            />
            <BrandMark />
          </div>
          <div className="flex items-center space-x-2 lg:space-x-4">
            <GlobalSearch user={user} />
            <NotificationBell user={user} />
            <span className="text-slate-300 hidden sm:inline text-sm lg:text-base" data-testid="user-name">{user.full_name}</span>
            <Button variant="ghost" onClick={onLogout} className="text-white hover:text-lime" data-testid="logout-btn">
              <LogOut className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </nav>

      <div className="flex min-h-[calc(100vh-73px)]">
        {/* Responsive Sidebar */}
        <ResponsiveSidebar
          isCollapsed={sidebar.isCollapsed}
          isMobileOpen={sidebar.isMobileOpen}
          isHovered={sidebar.isHovered}
          setIsHovered={sidebar.setIsHovered}
          closeMobile={sidebar.closeMobile}
          toggleCollapse={sidebar.toggleCollapse}
        >
          {navGroups.map((group) => {
            const GroupIcon = group.icon;
            const isExpanded = expandedGroups.includes(group.id);
            const isActiveGroup = activeGroup === group.id;

            return (
              <CollapsibleNavGroup
                key={group.id}
                icon={GroupIcon}
                label={group.label}
                isExpanded={isExpanded}
                onToggle={() => toggleGroup(group.id)}
                isActive={isActiveGroup}
                hasHighlight={group.items.some(item => item.highlight)}
                isCollapsed={sidebar.effectiveCollapsed}
              >
                {group.items.map((item) => {
                  const ItemIcon = item.icon;
                  return (
                    <button
                      key={item.id}
                      onClick={() => handleNavClick(item, group.id)}
                      title={sidebar.effectiveCollapsed ? item.label : undefined}
                      className={navItemClass(activeTab === item.id)}
                    >
                      <ItemIcon className="h-4 w-4 shrink-0" />
                      {!sidebar.effectiveCollapsed && (
                        <>
                          <span className="truncate">{item.label}</span>
                        </>
                      )}
                    </button>
                  );
                })}
              </CollapsibleNavGroup>
            );
          })}
        </ResponsiveSidebar>

        {/* Main Content */}
        <main className="flex-1 p-4 lg:p-6 overflow-y-auto">
          <div className="max-w-6xl mx-auto">
            {renderContent()}
          </div>
        </main>
      </div>
    </div>
  );
}

export default CustomerDashboard;
