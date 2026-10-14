import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Wallet, CreditCard, Receipt, Download, RefreshCw, CheckCircle, 
  Clock, AlertTriangle, Plane, Calendar, ArrowRight, FileText
} from 'lucide-react';
import { toast } from 'sonner';
import { tr } from '../../lib/bilingual';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function CustomerPaymentHistory({ user }) {
  const [transactions, setTransactions] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState({});

  useEffect(() => {
    loadPaymentHistory();
  }, []);

  const loadPaymentHistory = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      
      // Fetch customer's bookings/inquiries
      const bookingsRes = await fetch(`${API_URL}/api/customer/trips`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (bookingsRes.ok) {
        const bookingsData = await bookingsRes.json();
        const allBookings = [...(bookingsData.confirmed || []), ...(bookingsData.pending || []), ...(bookingsData.completed || [])];
        setBookings(allBookings);
        
        // Fetch transactions for each booking
        const allTxns = [];
        for (const booking of allBookings) {
          try {
            const txnRes = await fetch(`${API_URL}/api/payments/transactions/${booking.id}`, {
              headers: { Authorization: `Bearer ${token}` },
            });
            if (txnRes.ok) {
              const txnData = await txnRes.json();
              if (txnData.transactions && txnData.transactions.length > 0) {
                allTxns.push({
                  booking,
                  transactions: txnData.transactions,
                  summary: txnData,
                });
              }
            }
          } catch (err) {
            console.error(`Failed to fetch transactions for booking ${booking.id}`);
          }
        }
        setTransactions(allTxns);
      }
    } catch (err) {
      console.error('Failed to load payment history:', err);
      toast.error(tr('Failed to load payment history', 'भुगतान इतिहास लोड नहीं हो सका'));
    } finally {
      setLoading(false);
    }
  };

  const downloadReceipt = async (sessionId, txnId) => {
    setDownloading(prev => ({ ...prev, [txnId]: true }));
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/payments/receipt/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `AirYatra_Receipt_${sessionId.slice(0, 12)}.pdf`;
        a.click();
        window.URL.revokeObjectURL(url);
        toast.success(tr('Receipt downloaded!', 'रसीद डाउनलोड हुई!'));
      } else {
        toast.error(tr('Failed to download receipt', 'रसीद डाउनलोड नहीं हो सकी'));
      }
    } catch (err) {
      toast.error(tr('Download failed', 'डाउनलोड विफल'));
    } finally {
      setDownloading(prev => ({ ...prev, [txnId]: false }));
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(amount || 0);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Calculate totals
  const totalPaid = transactions.reduce((sum, t) => {
    return sum + t.transactions.filter(tx => tx.payment_status === 'paid').reduce((s, tx) => s + (tx.amount || 0), 0);
  }, 0);

  const totalPending = transactions.reduce((sum, t) => {
    return sum + (t.summary?.remaining || 0);
  }, 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="payments-loading">
        <RefreshCw className="h-8 w-8 animate-spin text-lime" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6" data-testid="customer-payment-history">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Wallet className="h-7 w-7 text-lime" />
            {tr('Payment History', 'भुगतान इतिहास')}
          </h1>
          <p className="text-slate-400 mt-1">{tr('View all your payments and download receipts', 'अपने सभी भुगतान देखें और रसीदें डाउनलोड करें')}</p>
        </div>
        <Button 
          onClick={loadPaymentHistory} 
          variant="outline" 
          className="border-slate-600 text-slate-300 hover:bg-slate-800"
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          {tr('Refresh', 'रीफ़्रेश करें')}
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-gradient-to-br from-green-600 to-green-700 border-0">
          <CardContent className="p-5">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-green-100 text-sm font-medium">{tr('Total Paid', 'कुल भुगतान')}</p>
                <p className="text-3xl font-bold text-white mt-1">{formatCurrency(totalPaid)}</p>
                <p className="text-green-200 text-sm mt-1">{transactions.length} {tr('bookings', 'बुकिंग')}</p>
              </div>
              <div className="p-3 bg-white/20 rounded-sm">
                <CheckCircle className="h-6 w-6 text-white" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-800 border border-slate-700">
          <CardContent className="p-5">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-slate-300 text-sm font-medium">{tr('Pending Balance', 'लंबित शेष')}</p>
                <p className="text-3xl font-bold text-white mt-1">{formatCurrency(totalPending)}</p>
                <p className="text-slate-300 text-sm mt-1">{tr('Remaining to pay', 'भुगतान बाकी')}</p>
              </div>
              <div className="p-3 bg-white/20 rounded-sm">
                <Clock className="h-6 w-6 text-white" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-800 border border-slate-700">
          <CardContent className="p-5">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-slate-300 text-sm font-medium">{tr('Total Receipts', 'कुल रसीदें')}</p>
                <p className="text-3xl font-bold text-white mt-1">
                  {transactions.reduce((sum, t) => sum + t.transactions.filter(tx => tx.payment_status === 'paid').length, 0)}
                </p>
                <p className="text-slate-300 text-sm mt-1">{tr('Available for download', 'डाउनलोड के लिए उपलब्ध')}</p>
              </div>
              <div className="p-3 bg-white/20 rounded-sm">
                <Receipt className="h-6 w-6 text-white" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Transactions List */}
      {transactions.length === 0 ? (
        <Card className="bg-slate-800/50 border-slate-700">
          <CardContent className="py-16 text-center">
            <Wallet className="h-16 w-16 mx-auto text-slate-600 mb-4" />
            <h3 className="text-xl font-semibold text-white mb-2">{tr('No Payment History', 'कोई भुगतान इतिहास नहीं')}</h3>
            <p className="text-slate-400">{tr('Your payment transactions will appear here once you make a booking.', 'बुकिंग करने के बाद आपके भुगतान लेन-देन यहां दिखेंगे।')}</p>
            <Button 
              className="mt-6 bg-lime text-black hover:bg-lime/90"
              onClick={() => window.location.href = '/booking'}
            >
              <Plane className="h-4 w-4 mr-2" />
              {tr('Book a Flight', 'उड़ान बुक करें')}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {transactions.map((item, idx) => (
            <Card key={idx} className="bg-slate-800/50 border-slate-700 overflow-hidden">
              {/* Booking Header */}
              <div className="bg-slate-700/50 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-lime/20 rounded-sm flex items-center justify-center">
                    <Plane className="h-6 w-6 text-lime" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-semibold">
                        {item.booking.from_location || tr('Origin', 'प्रस्थान स्थान')} → {item.booking.to_location || tr('Destination', 'गंतव्य')}
                      </span>
                      <Badge className="bg-lime/20 text-lime border-0 text-xs">
                        #{item.booking.inquiry_number || item.booking.id?.slice(0, 8)}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3 text-slate-400 text-sm mt-1">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {item.booking.departure_date || 'TBD'}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-slate-400 text-sm">{tr('Total Amount', 'कुल राशि')}</p>
                  <p className="text-xl font-bold text-white">{formatCurrency(item.summary?.total_amount)}</p>
                  {item.summary?.remaining > 0 && (
                    <Badge className="bg-amber-500/20 text-amber-400 border-0 mt-1">
                      {formatCurrency(item.summary.remaining)} {tr('pending', 'लंबित')}
                    </Badge>
                  )}
                  {item.summary?.remaining <= 0 && item.summary?.total_amount > 0 && (
                    <Badge className="bg-green-500/20 text-green-400 border-0 mt-1">
                      <CheckCircle className="h-3 w-3 mr-1" />
                      {tr('Fully Paid', 'पूरा भुगतान')}
                    </Badge>
                  )}
                </div>
              </div>

              {/* Transactions Table */}
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700 bg-slate-800/30">
                      <th className="text-left py-3 px-6 text-slate-400 font-medium">{tr('Date', 'तारीख')}</th>
                      <th className="text-left py-3 px-6 text-slate-400 font-medium">{tr('Type', 'प्रकार')}</th>
                      <th className="text-right py-3 px-6 text-slate-400 font-medium">{tr('Amount', 'राशि')}</th>
                      <th className="text-center py-3 px-6 text-slate-400 font-medium">{tr('Status', 'स्थिति')}</th>
                      <th className="text-center py-3 px-6 text-slate-400 font-medium">{tr('Receipt', 'रसीद')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {item.transactions.map((txn, tIdx) => (
                      <tr key={tIdx} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                        <td className="py-4 px-6 text-slate-300">
                          {formatDate(txn.updated_at || txn.created_at)}
                        </td>
                        <td className="py-4 px-6">
                          <Badge className={`border-0 ${
                            txn.payment_type === 'balance' 
                              ? 'bg-purple-500/20 text-purple-400' 
                              : 'bg-amber/20 text-amber'
                          }`}>
                            {txn.payment_type === 'balance' ? tr('Balance', 'शेष') : tr('Advance', 'अग्रिम')}
                          </Badge>
                        </td>
                        <td className="py-4 px-6 text-right">
                          <span className="text-green-400 font-semibold text-base">
                            {formatCurrency(txn.amount)}
                          </span>
                          {txn.voucher_discount > 0 && (
                            <div className="text-xs text-slate-500">
                              +₹{txn.voucher_discount} {tr('voucher', 'वाउचर')}
                            </div>
                          )}
                        </td>
                        <td className="py-4 px-6 text-center">
                          {txn.payment_status === 'paid' ? (
                            <Badge className="bg-green-500/20 text-green-400 border-0">
                              <CheckCircle className="h-3 w-3 mr-1" />
                              {tr('Paid', 'भुगतान हुआ')}
                            </Badge>
                          ) : txn.payment_status === 'pending' ? (
                            <Badge className="bg-yellow-500/20 text-yellow-400 border-0">
                              <Clock className="h-3 w-3 mr-1" />
                              {tr('Pending', 'लंबित')}
                            </Badge>
                          ) : (
                            <Badge className="bg-red-500/20 text-red-400 border-0">
                              {txn.payment_status}
                            </Badge>
                          )}
                        </td>
                        <td className="py-4 px-6 text-center">
                          {txn.payment_status === 'paid' && txn.session_id ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-8 px-3 text-lime hover:bg-lime/20"
                              onClick={() => downloadReceipt(txn.session_id, txn.id)}
                              disabled={downloading[txn.id]}
                              data-testid={`download-receipt-${tIdx}`}
                            >
                              {downloading[txn.id] ? (
                                <RefreshCw className="h-4 w-4 animate-spin" />
                              ) : (
                                <>
                                  <Download className="h-4 w-4 mr-1" />
                                  PDF
                                </>
                              )}
                            </Button>
                          ) : (
                            <span className="text-slate-600">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
