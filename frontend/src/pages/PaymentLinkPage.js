import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  Plane, MapPin, Calendar, CreditCard, CheckCircle, 
  AlertTriangle, Loader2, ArrowRight, Shield, Clock
} from 'lucide-react';
import { toast } from 'sonner';
import { tr } from '../lib/bilingual';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function PaymentLinkPage() {
  const { token } = useParams();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [processingPayment, setProcessingPayment] = useState(false);
  const cancelled = searchParams.get('cancelled') === 'true';

  useEffect(() => {
    if (token) {
      verifyPaymentLink();
    }
  }, [token]);

  const verifyPaymentLink = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/payments/link/${token}`);
      const json = await res.json();
      
      if (res.ok) {
        setData(json);
        if (!json.valid && json.already_paid) {
          setError({ type: 'paid', message: json.message });
        }
      } else {
        setError({ 
          type: res.status === 410 ? 'expired' : 'invalid', 
          message: json.detail || 'Invalid payment link' 
        });
      }
    } catch (err) {
      setError({ type: 'error', message: tr('Failed to verify payment link', 'भुगतान लिंक सत्यापित नहीं हो सका') });
    } finally {
      setLoading(false);
    }
  };

  const initiatePayment = async () => {
    setProcessingPayment(true);
    try {
      const res = await fetch(`${API_URL}/api/payments/link/${token}/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const json = await res.json();
      
      if (res.ok && json.checkout_url) {
        window.location.href = json.checkout_url;
      } else {
        toast.error(json.detail || 'Failed to initiate payment');
        setProcessingPayment(false);
      }
    } catch (err) {
      toast.error(tr('Payment initiation failed', 'भुगतान शुरू नहीं हो सका'));
      setProcessingPayment(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(amount);
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-lime mx-auto mb-4" />
          <p className="text-slate-400">{tr('Verifying payment link...', 'भुगतान लिंक सत्यापित हो रहा है...')}</p>
        </div>
      </div>
    );
  }

  // Error states
  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-slate-800/80 border-slate-700 backdrop-blur-lg">
          <CardContent className="pt-8 pb-8 text-center">
            {error.type === 'paid' ? (
              <>
                <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CheckCircle className="h-10 w-10 text-green-500" />
                </div>
                <h2 className="text-2xl font-bold text-white mb-2">{tr('Already Paid!', 'भुगतान पहले ही हो चुका है!')}</h2>
                <p className="text-slate-400 mb-6">{error.message}</p>
                <p className="text-sm text-slate-500">{tr('Thank you for your payment. Your booking is confirmed.', 'भुगतान के लिए धन्यवाद। आपकी बुकिंग की पुष्टि हो गई है।')}</p>
              </>
            ) : error.type === 'expired' ? (
              <>
                <div className="w-20 h-20 bg-lime/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Clock className="h-10 w-10 text-lime" />
                </div>
                <h2 className="text-2xl font-bold text-white mb-2">{tr('Link Expired', 'लिंक की अवधि समाप्त')}</h2>
                <p className="text-slate-400 mb-6">{error.message}</p>
                <p className="text-sm text-slate-500">{tr('Please contact AirYatra support for a new payment link.', 'नए भुगतान लिंक के लिए कृपया AirYatra सहायता से संपर्क करें।')}</p>
              </>
            ) : (
              <>
                <div className="w-20 h-20 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <AlertTriangle className="h-10 w-10 text-red-500" />
                </div>
                <h2 className="text-2xl font-bold text-white mb-2">{tr('Invalid Link', 'अमान्य लिंक')}</h2>
                <p className="text-slate-400 mb-6">{error.message}</p>
                <p className="text-sm text-slate-500">{tr('This payment link is not valid or has been used.', 'यह भुगतान लिंक मान्य नहीं है या पहले ही उपयोग हो चुका है।')}</p>
              </>
            )}
            <div className="mt-6 pt-6 border-t border-slate-700">
              <p className="text-xs text-slate-500">{tr('Need help? Contact info@airyatra.co.in', 'सहायता चाहिए? info@airyatra.co.in पर संपर्क करें')}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Cancelled state
  if (cancelled) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-slate-800/80 border-slate-700 backdrop-blur-lg">
          <CardContent className="pt-8 pb-8 text-center">
            <div className="w-20 h-20 bg-lime/20 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="h-10 w-10 text-lime" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">{tr('Payment Cancelled', 'भुगतान रद्द')}</h2>
            <p className="text-slate-400 mb-6">{tr('Your payment was not completed.', 'आपका भुगतान पूरा नहीं हुआ।')}</p>
            <Button 
              onClick={() => window.location.href = `/pay/${token}`}
              className="bg-lime text-black hover:bg-lime/90"
            >
              {tr('Try Again', 'फिर से प्रयास करें')}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Valid payment link - Show payment page
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4" data-testid="payment-link-page">
      {/* Header */}
      <div className="text-center pt-8 pb-6">
        <div className="flex items-center justify-center gap-2 mb-2">
          <div className="w-10 h-10 bg-slate-800 border border-slate-700 rounded-sm flex items-center justify-center">
            <Plane className="h-6 w-6 text-lime" />
          </div>
          <span className="text-2xl font-bold text-white">AirYatra</span>
        </div>
        <p className="text-slate-400 text-sm">{tr("India's Premium Helicopter Service", 'भारत की प्रीमियम हेलीकॉप्टर सेवा')}</p>
      </div>

      {/* Main Card */}
      <Card className="w-full max-w-lg mx-auto bg-slate-800/80 border-slate-700 backdrop-blur-lg overflow-hidden">
        {/* Gradient Header */}
        <div className="bg-slate-900 border-b border-slate-700 p-6 text-center">
          <h1 className="text-xl font-bold text-white mb-1">{tr('Complete Your Payment', 'अपना भुगतान पूरा करें')}</h1>
          <p className="text-slate-300 text-sm">{tr('Secure payment powered by Stripe', 'Stripe द्वारा सुरक्षित भुगतान')}</p>
        </div>

        <CardContent className="p-6 space-y-6">
          {/* Customer Greeting */}
          <div className="text-center">
            <p className="text-slate-400">{tr('Hello,', 'नमस्ते,')}</p>
            <p className="text-xl font-semibold text-white">{data?.customer_name}</p>
          </div>

          {/* Booking Details */}
          <div className="bg-slate-900/50 rounded-sm p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-slate-400 text-sm">{tr('Booking Ref', 'बुकिंग संदर्भ')}</span>
              <Badge className="bg-lime/20 text-lime border-0 font-mono">
                #{data?.inquiry_number}
              </Badge>
            </div>
            
            <div className="flex items-center gap-3 py-2">
              <MapPin className="h-5 w-5 text-lime shrink-0" />
              <div className="flex-1">
                <p className="text-white font-medium">{data?.route}</p>
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-slate-400" />
                <span className="text-slate-400 text-sm">{tr('Departure', 'प्रस्थान')}</span>
              </div>
              <span className="text-white font-medium">{data?.departure_date}</span>
            </div>
          </div>

          {/* Payment Summary */}
          <div className="space-y-3">
            <h3 className="text-slate-400 text-sm font-medium">{tr('Payment Summary', 'भुगतान सारांश')}</h3>
            
            <div className="flex justify-between items-center py-2 border-b border-slate-700">
              <span className="text-slate-400">{tr('Total Amount', 'कुल राशि')}</span>
              <span className="text-slate-300">{formatCurrency(data?.total_amount)}</span>
            </div>
            
            <div className="flex justify-between items-center py-2 border-b border-slate-700">
              <span className="text-slate-400">{tr('Already Paid', 'पहले से भुगतान')}</span>
              <span className="text-green-400">- {formatCurrency(data?.already_paid)}</span>
            </div>
            
            <div className="flex justify-between items-center py-3 bg-lime/10 rounded-lg px-3 -mx-3">
              <span className="text-white font-semibold">{tr('Balance Due', 'शेष देय')}</span>
              <span className="text-2xl font-bold text-lime">{formatCurrency(data?.remaining_balance)}</span>
            </div>
          </div>

          {/* Pay Button */}
          <Button 
            onClick={initiatePayment}
            disabled={processingPayment}
            className="w-full h-14 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-lg font-semibold"
            data-testid="pay-now-btn"
          >
            {processingPayment ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin mr-2" />
                {tr('Processing...', 'प्रोसेस हो रहा है...')}
              </>
            ) : (
              <>
                <CreditCard className="h-5 w-5 mr-2" />
                {tr('Pay', 'भुगतान करें')} {formatCurrency(data?.remaining_balance)}
                <ArrowRight className="h-5 w-5 ml-2" />
              </>
            )}
          </Button>

          {/* Security Badge */}
          <div className="flex items-center justify-center gap-2 text-slate-500 text-xs">
            <Shield className="h-4 w-4" />
            <span>{tr('256-bit SSL Encrypted • PCI Compliant', '256-बिट SSL एन्क्रिप्टेड • PCI अनुपालक')}</span>
          </div>

          {/* Link Expiry */}
          {data?.expires_at && (
            <p className="text-center text-slate-500 text-xs">
              {tr('Link expires:', 'लिंक की समाप्ति:')} {new Date(data.expires_at).toLocaleDateString('en-IN', {
                day: '2-digit',
                month: 'short',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
              })}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Footer */}
      <div className="text-center mt-8 pb-8">
        <p className="text-slate-500 text-sm">{tr('Need help? Contact us at info@airyatra.co.in', 'सहायता चाहिए? info@airyatra.co.in पर हमसे संपर्क करें')}</p>
        <p className="text-slate-600 text-xs mt-2">© 2025 AirYatra Aviation Pvt. Ltd.</p>
      </div>
    </div>
  );
}
