import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Clock, Check, X, DollarSign, Users, MapPin, Plane, Calendar, 
  CreditCard, ChevronRight, RefreshCw, Bell, AlertCircle, Star,
  FileText, Loader2, TreePine
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { customerAPI, bookingAPI, landingAPI } from '@/services/api';
import api from '@/services/api';
import { toast } from 'sonner';
import PassengerDetailsForm from './PassengerDetailsForm';
import VillageLandingDocuments from './VillageLandingDocuments';
import { bi, tr } from '../../lib/bilingual';

const STATUS_STEPS = [
  { id: 'pending_acceptance', label: tr('Inquiry Sent', 'पूछताछ भेजी गई'), labelHi: 'इंक्वायरी भेजी गई', icon: Clock },
  { id: 'quote_received', label: tr('Quotes Received', 'कोटेशन मिले'), labelHi: 'कोट प्राप्त', icon: Bell },
  { id: 'quote_accepted', label: tr('Quote Accepted', 'कोटेशन स्वीकृत'), labelHi: 'कोट स्वीकृत', icon: Check },
  { id: 'passenger_details_filled', label: tr('Details Filled', 'विवरण भरा गया'), labelHi: 'विवरण भरा', icon: Users },
  { id: 'payment_pending', label: tr('Payment', 'भुगतान'), labelHi: 'भुगतान', icon: CreditCard },
  { id: 'confirmed', label: tr('Confirmed', 'पुष्टि हुई'), labelHi: 'पुष्टि', icon: Check },
];

function InquiryStatus({ user }) {
  const { inquiryId } = useParams();
  const navigate = useNavigate();
  const [inquiry, setInquiry] = useState(null);
  const [quotes, setQuotes] = useState([]);
  const [paymentInfo, setPaymentInfo] = useState(null);
  const [villagePermission, setVillagePermission] = useState(null);
  const [ledger, setLedger] = useState(null);

  useEffect(() => {
    api.get(`/payments/transactions/${inquiryId}`).then((res) => setLedger(res.data)).catch(() => {});
  }, [inquiryId]);

  const downloadReceipt = async (t) => {
    try {
      const res = await api.get(`/payments/receipt/${t.session_id}`, { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `AirYatra_Receipt_${t.id.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(bi('Receipt downloaded / रसीद डाउनलोड हो गई'));
    } catch (e) { toast.error(tr('Failed to download receipt', 'रसीद डाउनलोड नहीं हो सकी')); }
  };
  const [loading, setLoading] = useState(true);
  const [showQuotesDialog, setShowQuotesDialog] = useState(false);
  const [showPassengerForm, setShowPassengerForm] = useState(false);
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    if (inquiryId) {
      loadInquiryStatus();
    }
  }, [inquiryId]);

  const loadInquiryStatus = async () => {
    setLoading(true);
    try {
      const response = await bookingAPI.getInquiryStatus(inquiryId);
      setInquiry(response.data.inquiry);
      setQuotes(response.data.operator_responses || []);
      
      // Load payment info if needed
      if (['quote_accepted', 'passenger_details_filled', 'payment_pending'].includes(response.data.inquiry?.status)) {
        const paymentResponse = await customerAPI.getPaymentInfo(inquiryId);
        setPaymentInfo(paymentResponse.data);
      }
      
      // Load village permission if applicable
      if (response.data.inquiry?.permission_required) {
        try {
          const permResponse = await landingAPI.getVillagePermissionByInquiry(inquiryId);
          setVillagePermission(permResponse.data);
        } catch (e) {
          console.log('No village permission found');
        }
      }
    } catch (error) {
      toast.error(tr('Failed to load inquiry status', 'पूछताछ की स्थिति लोड नहीं हो सकी'));
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const getCurrentStepIndex = () => {
    if (!inquiry) return 0;
    const index = STATUS_STEPS.findIndex(s => s.id === inquiry.status);
    return index >= 0 ? index : 0;
  };

  const handleAcceptQuote = async (quote) => {
    setProcessing(true);
    try {
      await customerAPI.respondToQuote(inquiryId, quote.id, { action: 'accept' });
      toast.success(bi('🎉 Quote accepted! Now fill passenger details. / कोट स्वीकार! अब यात्री विवरण भरें।'));
      setShowQuotesDialog(false);
      loadInquiryStatus();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to accept quote');
    } finally {
      setProcessing(false);
    }
  };

  const handlePassengerDetailsComplete = (data) => {
    setShowPassengerForm(false);
    toast.success(bi('✅ Passenger details saved! Proceed to payment. / यात्री विवरण सहेजा गया!'));
    loadInquiryStatus();
  };

  const handleProceedToPayment = () => {
    // Navigate to payment page with inquiry details
    navigate(`/customer/payment/${inquiryId}`, { 
      state: { 
        inquiry, 
        paymentInfo,
        amount: paymentInfo?.advance_amount || inquiry?.estimated_price 
      } 
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <RefreshCw className="h-8 w-8 text-lime animate-spin" />
      </div>
    );
  }

  if (!inquiry) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-16 w-16 text-red-400 mx-auto mb-4" />
          <p className="text-white text-xl">{tr('Inquiry not found', 'पूछताछ नहीं मिली')}</p>
          <Button onClick={() => navigate('/customer')} className="mt-4">
            {tr('Go to Dashboard', 'डैशबोर्ड पर जाएं')}
          </Button>
        </div>
      </div>
    );
  }

  const currentStep = getCurrentStepIndex();
  
  // Format date helper
  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    try {
      return new Date(dateStr).toLocaleDateString('en-IN', {
        day: '2-digit', month: 'short', year: 'numeric'
      });
    } catch (e) { return dateStr; }
  };
  
  // Format time helper
  const formatTime = (timeStr) => {
    if (!timeStr) return '-';
    try {
      if (timeStr.includes(':')) {
        const [hours, minutes] = timeStr.split(':');
        const h = parseInt(hours);
        return `${h > 12 ? h - 12 : h}:${minutes} ${h >= 12 ? 'PM' : 'AM'}`;
      }
      return timeStr;
    } catch (e) { return timeStr; }
  };

  return (
    <div className="min-h-screen bg-slate-950 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">
            {bi("Inquiry Status / इंक्वायरी स्थिति")}
          </h1>
          <p className="text-lime font-mono text-lg">
            {inquiry.inquiry_number || inquiry.id?.slice(0, 8)}
          </p>
        </div>

        {/* ========== BOOKING SUMMARY CARD ========== */}
        <div className="bg-gradient-to-r from-slate-900 to-slate-800 rounded-sm p-6 border border-lime/30 mb-8">
          <h2 className="text-lg font-bold text-lime mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5" /> {bi("Booking Details / बुकिंग विवरण")}
          </h2>
          
          {/* Main Info Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-slate-800/50 rounded-lg p-3">
              <p className="text-slate-400 text-xs mb-1">{bi("Ref No. / रेफ नं.")}</p>
              <p className="text-white font-bold text-sm">{inquiry.inquiry_number || inquiry.id?.slice(0, 8).toUpperCase()}</p>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3">
              <p className="text-slate-400 text-xs mb-1">{bi("Passengers / यात्री")}</p>
              <p className="text-white font-bold text-sm flex items-center gap-1">
                <Users className="h-4 w-4 text-amber" /> {inquiry.total_passengers || inquiry.adults_male + inquiry.adults_female || 1}
              </p>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3">
              <p className="text-slate-400 text-xs mb-1">{bi("Aircraft / विमान")}</p>
              <p className="text-white font-bold text-sm flex items-center gap-1">
                <Plane className="h-4 w-4 text-lime" /> {inquiry.aircraft_type === 'helicopter' ? tr('Helicopter', 'हेलीकॉप्टर') : tr('Plane', 'विमान')}
              </p>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3">
              <p className="text-slate-400 text-xs mb-1">{bi("Distance / दूरी")}</p>
              <p className="text-white font-bold text-sm">{inquiry.distance_km || '-'} km</p>
            </div>
          </div>

          {/* Route Info */}
          <div className="bg-slate-800/30 rounded-lg p-4 mb-4">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="flex-1 min-w-[150px]">
                <p className="text-slate-400 text-xs mb-1">{bi("From / से")}</p>
                <p className="text-white font-semibold flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-green-400" />
                  {inquiry.pickup_landing_point_name || inquiry.pickup_location || inquiry.pickup_city || '-'}
                </p>
                <p className="text-slate-500 text-xs">{inquiry.pickup_city}, {inquiry.pickup_state}</p>
              </div>
              
              <div className="flex items-center text-slate-600">
                <div className="w-8 h-0.5 bg-slate-600"></div>
                <Plane className="h-5 w-5 mx-2 text-lime rotate-90" />
                <div className="w-8 h-0.5 bg-slate-600"></div>
              </div>
              
              <div className="flex-1 min-w-[150px] text-right">
                <p className="text-slate-400 text-xs mb-1">{bi("To / तक")}</p>
                <p className="text-white font-semibold flex items-center justify-end gap-2">
                  {inquiry.drop_landing_point_name || inquiry.drop_location || inquiry.drop_city || '-'}
                  <MapPin className="h-4 w-4 text-red-400" />
                </p>
                <p className="text-slate-500 text-xs">{inquiry.drop_city}, {inquiry.drop_state}</p>
              </div>
            </div>
          </div>

          {/* Date, Time & Price Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-lime/10 rounded-lg p-3 border border-lime/20">
              <p className="text-slate-400 text-xs mb-1">{bi("Travel Date / यात्रा तारीख")}</p>
              <p className="text-lime font-bold text-sm flex items-center gap-1">
                <Calendar className="h-4 w-4" /> {formatDate(inquiry.departure_date)}
              </p>
            </div>
            <div className="bg-amber/10 rounded-lg p-3 border border-amber/20">
              <p className="text-slate-400 text-xs mb-1">{bi("Pickup Time / समय")}</p>
              <p className="text-amber font-bold text-sm flex items-center gap-1">
                <Clock className="h-4 w-4" /> {formatTime(inquiry.pickup_time)}
              </p>
            </div>
            <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/20">
              <p className="text-slate-400 text-xs mb-1">{bi("Est. Amount / अनुमानित राशि")}</p>
              <p className="text-green-400 font-bold text-sm flex items-center gap-1">
                <DollarSign className="h-4 w-4" /> ₹{(inquiry.estimated_price || 0).toLocaleString()}
              </p>
            </div>
            <div className="bg-purple-500/10 rounded-lg p-3 border border-purple-500/20">
              <p className="text-slate-400 text-xs mb-1">{bi("Inquiry Date / इंक्वायरी तारीख")}</p>
              <p className="text-purple-400 font-bold text-sm flex items-center gap-1">
                <Calendar className="h-4 w-4" /> {formatDate(inquiry.created_at)}
              </p>
            </div>
          </div>

          {/* Operator Status Row */}
          <div className="mt-4 pt-4 border-t border-slate-700">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-2">
                <span className="text-slate-400 text-sm">{tr('Operator Status:', 'ऑपरेटर स्थिति:')}</span>
                {quotes.length > 0 ? (
                  <span className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full text-sm font-medium">
                    ✅ {quotes.length} {tr('Operator(s) Accepted', 'ऑपरेटर ने स्वीकार किया')}
                  </span>
                ) : (
                  <span className="px-3 py-1 bg-yellow-500/20 text-yellow-400 rounded-full text-sm font-medium animate-pulse">
                    {tr('⏳ Waiting for Operators...', '⏳ ऑपरेटरों की प्रतीक्षा...')}
                  </span>
                )}
              </div>
              <Button 
                onClick={loadInquiryStatus} 
                variant="outline" 
                size="sm"
                className="border-slate-600 text-slate-300 hover:bg-slate-700"
              >
                <RefreshCw className="h-4 w-4 mr-1" /> {tr('Refresh', 'रीफ़्रेश करें')}
              </Button>
            </div>
          </div>
        </div>
        {/* ========== END BOOKING SUMMARY CARD ========== */}

        {/* Progress Steps */}
        <div className="bg-slate-900/50 rounded-sm p-6 border border-slate-800 mb-8">
          <div className="flex items-center justify-between overflow-x-auto pb-2">
            {STATUS_STEPS.map((step, index) => {
              const StepIcon = step.icon;
              const isCompleted = index < currentStep;
              const isCurrent = index === currentStep;
              const isPending = index > currentStep;
              
              return (
                <React.Fragment key={step.id}>
                  <div className="flex flex-col items-center min-w-[80px]">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
                      isCompleted ? 'bg-green-500 text-white' :
                      isCurrent ? 'bg-lime text-black ring-4 ring-lime/30' :
                      'bg-slate-700 text-slate-400'
                    }`}>
                      {isCompleted ? <Check className="h-6 w-6" /> : <StepIcon className="h-6 w-6" />}
                    </div>
                    <span className={`text-xs mt-2 text-center ${
                      isCurrent ? 'text-lime font-medium' : 
                      isCompleted ? 'text-green-400' : 'text-slate-500'
                    }`}>
                      {tr(step.label, step.labelHi)}
                    </span>
                  </div>
                  {index < STATUS_STEPS.length - 1 && (
                    <div className={`flex-1 h-1 mx-2 rounded ${
                      index < currentStep ? 'bg-green-500' : 'bg-slate-700'
                    }`} />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Current Status Message */}
        <div className={`rounded-sm p-6 mb-8 border ${
          inquiry.status === 'confirmed' ? 'bg-green-500/10 border-green-500/30' :
          inquiry.status === 'pending_acceptance' ? 'bg-yellow-500/10 border-yellow-500/30' :
          'bg-lime/10 border-lime/30'
        }`}>
          {inquiry.status === 'pending_acceptance' && (
            <div className="text-center">
              <Clock className="h-12 w-12 text-yellow-400 mx-auto mb-3 animate-pulse" />
              <h3 className="text-xl font-bold text-yellow-400">
                {bi("Please Wait / कृपया प्रतीक्षा करें")}
              </h3>
              <p className="text-slate-300 mt-2">
                {tr("Your booking acceptance is pending to operators.", "आपकी बुकिंग ऑपरेटर्स की स्वीकृति के लिए लंबित है।")}
              </p>
            </div>
          )}

          {inquiry.status === 'quote_received' && (
            <div className="text-center">
              <Bell className="h-12 w-12 text-amber mx-auto mb-3" />
              <h3 className="text-xl font-bold text-amber">
                {bi("Quotes Received! / कोट प्राप्त!")}
              </h3>
              <p className="text-slate-300 mt-2">
                {quotes.length} {tr('operator(s) have sent you quotes. Please review and accept one.', 'ऑपरेटरों ने आपको कोटेशन भेजे हैं। कृपया देखें और एक स्वीकार करें।')}
              </p>
              <Button 
                onClick={() => setShowQuotesDialog(true)} 
                className="mt-4 bg-slate-700 hover:bg-slate-600"
              >
                <DollarSign className="h-4 w-4 mr-2" /> {tr('View Quotes (', 'कोटेशन देखें (')}{quotes.length})
              </Button>
            </div>
          )}

          {inquiry.status === 'quote_accepted' && (
            <div className="text-center">
              <Check className="h-12 w-12 text-green-400 mx-auto mb-3" />
              <h3 className="text-xl font-bold text-green-400">
                {bi("Booking Accepted! / बुकिंग स्वीकृत!")}
              </h3>
              <p className="text-slate-300 mt-2">
                {tr('Please fill passenger details to proceed with payment.', 'भुगतान के लिए कृपया यात्री विवरण भरें।')}
              </p>
              <Button 
                onClick={() => setShowPassengerForm(true)} 
                className="mt-4 bg-lime text-black hover:bg-lime/90"
              >
                <Users className="h-4 w-4 mr-2" /> {tr('Fill Passenger Details', 'यात्री विवरण भरें')}
              </Button>
            </div>
          )}

          {inquiry.status === 'passenger_details_filled' && (
            <div className="text-center">
              <CreditCard className="h-12 w-12 text-lime mx-auto mb-3" />
              <h3 className="text-xl font-bold text-lime">
                {bi("Proceed to Payment / भुगतान करें")}
              </h3>
              <p className="text-slate-300 mt-2">
                Passenger details saved. Complete {paymentInfo?.advance_percent || 50}% advance payment to confirm booking.
              </p>
              <div className="mt-4 p-4 bg-slate-800/50 rounded-lg inline-block">
                <p className="text-slate-400 text-sm">{tr('Amount to Pay:', 'देय राशि:')}</p>
                <p className="text-lime text-3xl font-bold">
                  ₹{(paymentInfo?.advance_amount || inquiry.estimated_price)?.toLocaleString()}
                </p>
                {paymentInfo?.advance_percent < 100 && (
                  <p className="text-slate-500 text-xs mt-1">
                    {tr('Remaining ₹', 'शेष ₹')}{paymentInfo?.remaining_amount?.toLocaleString()} {tr('before flight', 'उड़ान से पहले')}
                  </p>
                )}
              </div>
              <Button 
                onClick={handleProceedToPayment} 
                className="mt-4 bg-green-600 hover:bg-green-700"
              >
                <CreditCard className="h-4 w-4 mr-2" /> {tr('Pay Now', 'अभी भुगतान करें')}
              </Button>
            </div>
          )}

          {inquiry.status === 'confirmed' && (
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-green-500 flex items-center justify-center mx-auto mb-3">
                <Check className="h-10 w-10 text-white" />
              </div>
              <h3 className="text-xl font-bold text-green-400">
                {bi("Booking Confirmed! / बुकिंग पुष्टि!")}
              </h3>
              <p className="text-slate-300 mt-2">
                {inquiry.permission_required 
                  ? tr('Please upload required documents for village landing approval.', 'गांव में लैंडिंग की स्वीकृति के लिए कृपया आवश्यक दस्तावेज़ अपलोड करें।')
                  : tr('Your booking has been confirmed. Have a safe flight!', 'आपकी बुकिंग की पुष्टि हो गई है। आपकी उड़ान सुरक्षित हो!')}
              </p>
            </div>
          )}
        </div>

        {/* Village Landing Documents Section */}
        {inquiry.permission_required && inquiry.status === 'confirmed' && (
          <div className="mb-8">
            <VillageLandingDocuments
              inquiryId={inquiryId}
              permissionId={villagePermission?.id}
              permissionData={villagePermission}
              onUpdate={loadInquiryStatus}
            />
          </div>
        )}

        {/* Village Landing Info for Non-Confirmed Status */}
        {inquiry.permission_required && inquiry.status !== 'confirmed' && (
          <div className="bg-yellow-500/10 rounded-sm p-4 border border-yellow-500/30 mb-8">
            <div className="flex items-start gap-3">
              <TreePine className="h-6 w-6 text-yellow-400 shrink-0" />
              <div>
                <h4 className="text-yellow-400 font-semibold">
                  {bi("Village Landing - Documents Required / गांव लैंडिंग - दस्तावेज़ आवश्यक")}
                </h4>
                <p className="text-yellow-400/70 text-sm mt-1">
                  {tr('After booking is confirmed, you will need to upload documents from authorities:', 'बुकिंग की पुष्टि के बाद आपको अधिकारियों से मिले दस्तावेज़ अपलोड करने होंगे:')}
                </p>
                <ul className="text-yellow-400/70 text-sm mt-2 list-disc list-inside">
                  <li>{bi("Collector NOC / कलेक्टर NOC")}</li>
                  <li>{bi("Fire Department Acknowledgment / फायर विभाग की पावती")}</li>
                  <li>{bi("Local Police Station Acknowledgment / स्थानीय थाना की पावती")}</li>
                  <li>{bi("SP/DCP Acknowledgment / SP/DCP की पावती")}</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Payments & Receipts */}
        {ledger && ledger.transactions?.length > 0 && (
          <div className="bg-slate-900/50 rounded-sm p-6 border border-slate-800 mb-8" data-testid="payments-receipts-section">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <CreditCard className="h-5 w-5 text-green-400" />
              {bi("Payments & Receipts / भुगतान और रसीदें")}
            </h3>
            <div className="space-y-2 mb-4">
              {ledger.transactions.map((t) => (
                <div key={t.id} className="flex items-center justify-between bg-slate-800/60 rounded-lg p-3 border border-slate-700/60" data-testid={`payment-txn-${t.id}`}>
                  <div>
                    <p className="text-white text-sm font-medium">
                      {t.payment_type === 'balance' ? tr('Remaining Balance', 'शेष राशि') : tr('Advance Payment', 'अग्रिम भुगतान')} — ₹{Number(t.amount).toLocaleString()}
                      {t.voucher_discount > 0 && <span className="text-green-400 text-xs ml-2">{tr('(voucher -₹', '(वाउचर -₹')}{t.voucher_discount.toLocaleString()})</span>}
                    </p>
                    <p className="text-slate-500 text-xs">{(t.paid_at || '').slice(0, 16).replace('T', ' ')} • Stripe (Test)</p>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => downloadReceipt(t)} className="border-slate-600 text-slate-300 hover:text-white h-8" data-testid={`download-receipt-${t.id}`}>
                    <FileText className="h-3.5 w-3.5 mr-1.5" />{tr('Receipt PDF', 'रसीद PDF')}
                  </Button>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between border-t border-slate-700/60 pt-3">
              <p className="text-slate-400 text-sm">
                Paid: <span className="text-green-400 font-semibold">₹{Number(ledger.paid_total).toLocaleString()}</span>
                <span className="mx-2">•</span>
                Remaining: <span className={`font-semibold ${ledger.remaining_due > 0 ? 'text-lime' : 'text-green-400'}`}>₹{Number(ledger.remaining_due).toLocaleString()}</span>
              </p>
              {ledger.remaining_due > 0 && ledger.payment_status === 'paid' && (
                <Button onClick={() => navigate(`/customer/payment/${inquiryId}?type=balance`)} className="bg-lime text-black hover:bg-lime/90" data-testid="pay-remaining-btn">
                  <CreditCard className="h-4 w-4 mr-2" />{tr('Pay Remaining ₹', 'शेष भुगतान करें ₹')}{Number(ledger.remaining_due).toLocaleString()}
                </Button>
              )}
              {ledger.payment_status === 'fully_paid' && (
                <span className="px-3 py-1.5 rounded-lg bg-green-500/20 text-green-400 text-sm font-semibold" data-testid="fully-paid-badge">{bi("✓ Fully Paid / पूर्ण भुगतान")}</span>
              )}
            </div>
          </div>
        )}

        {/* Booking Summary */}
        <div className="bg-slate-900/50 rounded-sm p-6 border border-slate-800">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5 text-lime" />
            {bi("Booking Summary / बुकिंग सारांश")}
          </h3>
          
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-slate-500">{tr('Aircraft', 'विमान')}</p>
              <p className="text-white">{inquiry.aircraft_type === 'helicopter' ? tr('🚁 Helicopter', '🚁 हेलीकॉप्टर') : tr('✈️ Plane', '✈️ विमान')}</p>
            </div>
            <div>
              <p className="text-slate-500">{tr('Passengers', 'यात्री')}</p>
              <p className="text-white">{inquiry.total_passengers} Adults + {inquiry.children_count || 0} {tr('Children', 'बच्चे')}</p>
            </div>
            <div>
              <p className="text-slate-500">{tr('Flight Type', 'उड़ान का प्रकार')}</p>
              <p className="text-white">{inquiry.udan_prakar}</p>
            </div>
            <div>
              <p className="text-slate-500">{tr('Date & Time', 'तारीख और समय')}</p>
              <p className="text-white">{inquiry.departure_date} {inquiry.pickup_time}</p>
            </div>
            <div>
              <p className="text-slate-500">{tr('Purpose', 'उद्देश्य')}</p>
              <p className="text-white">{inquiry.booking_purpose}</p>
            </div>
            <div>
              <p className="text-slate-500">{tr('Distance', 'दूरी')}</p>
              <p className="text-lime font-bold">{inquiry.distance_km} KM</p>
            </div>
          </div>

          {/* Route */}
          <div className="mt-4 pt-4 border-t border-slate-700">
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <p className="text-green-400 flex items-center gap-1 text-sm">
                  <MapPin className="h-4 w-4" /> {tr('Pickup', 'पिकअप')}
                </p>
                <p className="text-white font-medium">{inquiry.pickup_location}</p>
                <p className="text-slate-500 text-xs">{inquiry.pickup_district}, {inquiry.pickup_state}</p>
              </div>
              <ChevronRight className="h-6 w-6 text-slate-500" />
              <div className="flex-1">
                <p className="text-red-400 flex items-center gap-1 text-sm">
                  <MapPin className="h-4 w-4" /> {tr('Drop', 'ड्रॉप')}
                </p>
                <p className="text-white font-medium">{inquiry.drop_location}</p>
                <p className="text-slate-500 text-xs">{inquiry.drop_district}, {inquiry.drop_state}</p>
              </div>
            </div>
          </div>

          {/* Estimated Price */}
          <div className="mt-4 pt-4 border-t border-slate-700 flex justify-between items-center">
            <span className="text-slate-400">{tr('Estimated Amount:', 'अनुमानित राशि:')}</span>
            <span className="text-lime text-2xl font-bold">
              ₹{(inquiry.accepted_quote?.amount || inquiry.estimated_price || 0).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Back to Dashboard */}
        <div className="mt-6 text-center">
          <Button variant="outline" onClick={() => navigate('/customer')} className="border-slate-600">
            {tr('← Back to Dashboard', '← डैशबोर्ड पर वापस जाएं')}
          </Button>
        </div>
      </div>

      {/* Quotes Dialog */}
      <Dialog open={showQuotesDialog} onOpenChange={setShowQuotesDialog}>
        <DialogContent className="bg-slate-900 border-slate-800 max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-white flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-lime" />
              {bi("Operator Quotes / ऑपरेटर कोट्स")}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 max-h-[60vh] overflow-y-auto">
            {quotes.length === 0 ? (
              <p className="text-slate-400 text-center py-8">{tr('No quotes received yet', 'अभी कोई कोटेशन नहीं मिला')}</p>
            ) : (
              quotes.map((quote, idx) => (
                <div key={idx} className="bg-slate-800/50 rounded-sm p-4 border border-slate-700">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-white font-semibold">{quote.operator_name || tr('Operator', 'ऑपरेटर')}</p>
                      {quote.notes && (
                        <p className="text-slate-400 text-sm mt-1">&ldquo;{quote.notes}&rdquo;</p>
                      )}
                    </div>
                    <div className="text-right">
                      <p className="text-lime text-2xl font-bold">
                        ₹{quote.amount?.toLocaleString()}
                      </p>
                    </div>
                  </div>
                  <Button
                    onClick={() => handleAcceptQuote(quote)}
                    disabled={processing}
                    className="w-full mt-4 bg-green-600 hover:bg-green-700"
                  >
                    {processing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4 mr-2" />}
                    {tr('Accept This Quote', 'यह कोटेशन स्वीकार करें')}
                  </Button>
                </div>
              ))
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowQuotesDialog(false)} className="border-slate-600">
              {tr('Close', 'बंद करें')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Passenger Details Form Dialog */}
      <Dialog open={showPassengerForm} onOpenChange={setShowPassengerForm}>
        <DialogContent className="bg-slate-900 border-slate-800 max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-white flex items-center gap-2">
              <Users className="h-5 w-5 text-lime" />
              {bi("Passenger Details / यात्री विवरण")}
            </DialogTitle>
          </DialogHeader>
          <PassengerDetailsForm 
            inquiry={inquiry} 
            onComplete={handlePassengerDetailsComplete}
            onCancel={() => setShowPassengerForm(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default InquiryStatus;
