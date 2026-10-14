import React, { useState, useEffect } from 'react';
import { Plane, MapPin, Calendar, Clock, IndianRupee, Star, MessageSquare, FileText, X, ChevronRight, AlertTriangle, Bell, Check, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { customerAPI, feedbackAPI } from '../../services/api';
import { toast } from 'sonner';
import { bi, tr } from '../../lib/bilingual';

function MyTrips({ user }) {
  const [trips, setTrips] = useState([]);
  const [statistics, setStatistics] = useState({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('upcoming');
  const [selectedTrip, setSelectedTrip] = useState(null);
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [showReviewDialog, setShowReviewDialog] = useState(false);
  const [showQuotesDialog, setShowQuotesDialog] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [isEmergency, setIsEmergency] = useState(false);
  const [reviewData, setReviewData] = useState({ overall_rating: 5, comment: '', recommend: true });
  const [processing, setProcessing] = useState(false);
  const [pendingQuotes, setPendingQuotes] = useState([]);
  const [tripQuotes, setTripQuotes] = useState([]);

  useEffect(() => {
    loadTrips();
    loadPendingQuotes();
  }, []);

  const loadTrips = async () => {
    setLoading(true);
    try {
      const response = await customerAPI.getTrips();
      setTrips(response.data.trips || []);
      setStatistics(response.data.statistics || {});
    } catch (error) {
      toast.error(tr('Failed to load trips', 'यात्राएं लोड नहीं हो सकीं'));
    } finally {
      setLoading(false);
    }
  };

  const loadPendingQuotes = async () => {
    try {
      const response = await customerAPI.getPendingQuotes();
      setPendingQuotes(response.data.quotes || []);
    } catch (error) {
      console.error('Failed to load pending quotes');
    }
  };

  const loadTripQuotes = async (bookingId) => {
    try {
      const response = await customerAPI.getBookingQuotes(bookingId);
      setTripQuotes(response.data.quotes || []);
    } catch (error) {
      toast.error(tr('Failed to load quotes', 'कोटेशन लोड नहीं हो सके'));
    }
  };

  const handleViewQuotes = async (trip) => {
    setSelectedTrip(trip);
    await loadTripQuotes(trip.id);
    setShowQuotesDialog(true);
  };

  const handleQuoteResponse = async (quoteId, action) => {
    if (!selectedTrip) return;
    setProcessing(true);
    try {
      await customerAPI.respondToQuote(selectedTrip.id, quoteId, { action });
      toast.success(action === 'accept' 
        ? bi('🎉 Quote accepted! Proceed to payment. / कोट स्वीकार!')
        : bi('Quote rejected / कोट अस्वीकार'));
      setShowQuotesDialog(false);
      loadTrips();
      loadPendingQuotes();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to respond');
    } finally {
      setProcessing(false);
    }
  };

  const handleCancelTrip = async () => {
    if (!selectedTrip || !cancelReason) return;
    setProcessing(true);
    try {
      const response = await customerAPI.cancelTrip(selectedTrip.id, {
        reason: cancelReason,
        is_emergency: isEmergency
      });
      toast.success(`Booking cancelled. Refund: ₹${response.data.refund_amount?.toLocaleString()}`);
      setShowCancelDialog(false);
      setSelectedTrip(null);
      setCancelReason('');
      loadTrips();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to cancel');
    } finally {
      setProcessing(false);
    }
  };

  const handleSubmitReview = async () => {
    if (!selectedTrip) return;
    setProcessing(true);
    try {
      await feedbackAPI.create({
        booking_id: selectedTrip.id,
        ...reviewData
      });
      toast.success(tr('Review submitted!', 'समीक्षा भेजी गई!'));
      setShowReviewDialog(false);
      setSelectedTrip(null);
      loadTrips();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to submit review');
    } finally {
      setProcessing(false);
    }
  };

  const getStatusBadge = (status) => {
    const badges = {
      pending: 'bg-yellow-500/20 text-yellow-400',
      pending_acceptance: 'bg-yellow-500/20 text-yellow-400',
      pending_quotes: 'bg-yellow-500/20 text-yellow-400',
      quote_received: 'bg-lime/20 text-lime',
      quotes_received: 'bg-lime/20 text-lime',
      quote_accepted: 'bg-amber/20 text-amber',
      passenger_details_filled: 'bg-purple-500/20 text-purple-400',
      confirmed: 'bg-green-500/20 text-green-400',
      completed: 'bg-green-500/20 text-green-400',
      cancelled: 'bg-red-500/20 text-red-400',
    };
    return badges[status] || badges.pending;
  };

  const getStatusLabel = (status) => {
    const labels = {
      pending: 'Pending',
      pending_acceptance: bi('Awaiting Quotes / कोट का इंतजार'),
      pending_quotes: 'Awaiting Quotes',
      quote_received: bi('Quotes Received / कोट मिला'),
      quotes_received: 'Quotes Received',
      quote_accepted: bi('Quote Accepted / कोट स्वीकार'),
      passenger_details_filled: bi('Details Filled / विवरण भरा'),
      confirmed: bi('Confirmed / पुष्टि'),
      completed: bi('Completed / पूर्ण'),
      cancelled: bi('Cancelled / रद्द'),
    };
    return labels[status] || status;
  };

  const filteredTrips = trips.filter(trip => {
    if (activeTab === 'upcoming') return ['pending', 'confirmed', 'quote_accepted', 'passenger_details_filled'].includes(trip.status);
    if (activeTab === 'pending') return ['pending_acceptance', 'quote_received', 'pending_quotes', 'quotes_received'].includes(trip.status);
    if (activeTab === 'completed') return trip.status === 'completed';
    if (activeTab === 'cancelled') return trip.status === 'cancelled';
    return true;
  });

  return (
    <div className="max-w-4xl mx-auto" data-testid="my-trips">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-white">{tr('My Trips', 'मेरी यात्राएं')}</h1>
        <p className="text-slate-400 mt-1">{tr('View and manage your helicopter bookings', 'अपनी हेलीकॉप्टर बुकिंग देखें और प्रबंधित करें')}</p>
      </div>

      {/* Pending Quotes Alert */}
      {pendingQuotes.length > 0 && (
        <div className="mb-6 p-4 rounded-sm bg-lime/10 border border-lime/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-full bg-lime/20">
                <Bell className="h-5 w-5 text-lime animate-pulse" />
              </div>
              <div>
                <h3 className="text-lime font-semibold">
                  {pendingQuotes.length} {tr('New Quote', 'नया कोटेशन')}{pendingQuotes.length > 1 ? 's' : ''} {bi("Received! / नया कोट मिला!")}
                </h3>
                <p className="text-slate-400 text-sm">
                  {tr('Operators have sent revised quotes for your bookings. Please review and respond.', 'ऑपरेटरों ने आपकी बुकिंग के लिए संशोधित कोटेशन भेजे हैं। कृपया देखें और जवाब दें।')}
                </p>
              </div>
            </div>
            <Button
              onClick={() => setActiveTab('upcoming')}
              className="bg-lime text-black hover:bg-lime/90"
            >
              {tr('View Quotes', 'कोटेशन देखें')}
            </Button>
          </div>
        </div>
      )}

      {/* Statistics */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="glass p-4 rounded-lg text-center">
          <p className="text-2xl font-bold text-white">{statistics.total_trips || 0}</p>
          <p className="text-sm text-slate-400">{tr('Total Trips', 'कुल यात्राएं')}</p>
        </div>
        <div className="glass p-4 rounded-lg text-center">
          <p className="text-2xl font-bold text-amber">{statistics.upcoming_count || 0}</p>
          <p className="text-sm text-slate-400">{tr('Upcoming', 'आगामी')}</p>
        </div>
        <div className="glass p-4 rounded-lg text-center">
          <p className="text-2xl font-bold text-green-400">{statistics.completed_count || 0}</p>
          <p className="text-sm text-slate-400">{tr('Completed', 'पूर्ण')}</p>
        </div>
        <div className="glass p-4 rounded-lg text-center">
          <p className="text-2xl font-bold text-lime">₹{(statistics.total_spent || 0).toLocaleString()}</p>
          <p className="text-sm text-slate-400">{tr('Total Spent', 'कुल खर्च')}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {[
          { id: 'pending', label: bi('Pending Inquiries / इंक्वायरी') },
          { id: 'upcoming', label: tr('Upcoming', 'आगामी') },
          { id: 'completed', label: tr('Completed', 'पूर्ण') },
          { id: 'cancelled', label: tr('Cancelled', 'रद्द') },
          { id: 'all', label: tr('All', 'सभी') }
        ].map(tab => (
          <Button
            key={tab.id}
            variant={activeTab === tab.id ? 'default' : 'outline'}
            onClick={() => setActiveTab(tab.id)}
            className={activeTab === tab.id ? 'bg-lime text-black hover:bg-lime/90' : 'border-slate-600 text-slate-300'}
          >
            {tab.label}
            {tab.id === 'pending' && statistics.pending_count > 0 && (
              <span className="ml-2 px-2 py-0.5 bg-lime text-black rounded-full text-xs">
                {statistics.pending_count}
              </span>
            )}
          </Button>
        ))}
      </div>

      {/* Trips List */}
      {loading ? (
        <div className="text-center py-12 text-slate-400">{tr('Loading trips...', 'यात्राएं लोड हो रही हैं...')}</div>
      ) : filteredTrips.length === 0 ? (
        <div className="text-center py-12">
          <Plane className="h-16 w-16 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400">{tr('No trips found', 'कोई यात्रा नहीं मिली')}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredTrips.map((trip) => (
            <div key={trip.id} className="glass p-6 rounded-sm">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <p className="text-white font-semibold text-lg">
                    {trip.inquiry_number || trip.booking_number || `#${trip.id?.slice(0, 8)}`}
                    {trip.source === 'inquiry' && (
                      <span className="ml-2 text-xs px-2 py-0.5 bg-amber/20 text-amber rounded">{tr('Inquiry', 'पूछताछ')}</span>
                    )}
                  </p>
                  <div className="flex items-center gap-2 mt-2 text-slate-300">
                    <MapPin className="h-4 w-4 text-green-400" />
                    <span>{trip.pickup_location || trip.from_location}</span>
                    <ChevronRight className="h-4 w-4 text-slate-500" />
                    <MapPin className="h-4 w-4 text-red-400" />
                    <span>{trip.drop_location || trip.to_location}</span>
                  </div>
                </div>
                <span className={`px-3 py-1 rounded-full text-sm ${getStatusBadge(trip.status)}`}>
                  {getStatusLabel(trip.status)}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="flex items-center gap-2 text-slate-400">
                  <Calendar className="h-4 w-4" />
                  <span>{trip.departure_date ? new Date(trip.departure_date).toLocaleDateString() : 'TBD'}</span>
                </div>
                <div className="flex items-center gap-2 text-slate-400">
                  <Plane className="h-4 w-4" />
                  <span>{trip.operator?.company_name || tr('Operator TBD', 'ऑपरेटर तय होना बाकी')}</span>
                </div>
                <div className="flex items-center gap-2 text-white font-semibold">
                  <IndianRupee className="h-4 w-4" />
                  <span>₹{(trip.estimated_price || trip.total_amount || 0).toLocaleString()}</span>
                </div>
              </div>

              {/* Additional info for inquiries */}
              {trip.source === 'inquiry' && (
                <div className="flex items-center gap-4 text-sm text-slate-400 mb-4">
                  <span>✈️ {trip.aircraft_type === 'helicopter' ? tr('Helicopter', 'हेलीकॉप्टर') : tr('Plane', 'विमान')}</span>
                  <span>👥 {trip.total_passengers} {tr('Passengers', 'यात्री')}</span>
                  {trip.quote_count > 0 && (
                    <span className="text-lime">📋 {trip.quote_count} {tr('Quote(s) Received', 'कोटेशन मिले')}</span>
                  )}
                </div>
              )}

              {/* Latest Quote Alert */}
              {trip.latest_quote && trip.status !== 'quote_accepted' && (
                <div className="mb-4 p-3 rounded-lg bg-amber/10 border border-amber/30">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-amber font-medium flex items-center gap-2">
                        <Bell className="h-4 w-4" />
                        {tr('New Quote from', 'नया कोटेशन, भेजने वाले:')} {trip.latest_quote.operator_name}
                      </p>
                      <p className="text-white text-lg font-bold mt-1">
                        ₹{trip.latest_quote.amount?.toLocaleString()}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      className="bg-slate-700 hover:bg-slate-600"
                      onClick={() => handleViewQuotes(trip)}
                    >
                      {tr('View Quotes', 'कोटेशन देखें')}
                    </Button>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-4 border-t border-slate-700">
                {/* View Status for Inquiries */}
                {trip.source === 'inquiry' && (
                  <Button
                    size="sm"
                    className="bg-slate-700 hover:bg-slate-600"
                    onClick={() => window.location.href = `/customer/inquiry/${trip.id}`}
                  >
                    <FileText className="h-4 w-4 mr-1" /> {bi("View Status / स्थिति देखें")}
                  </Button>
                )}
                {/* View Quotes Button for pending bookings */}
                {['pending', 'pending_quotes', 'quote_sent', 'quotes_received', 'quote_received'].includes(trip.status) && trip.source !== 'inquiry' && (
                  <Button
                    size="sm"
                    className="bg-lime/20 text-lime hover:bg-lime/30"
                    onClick={() => handleViewQuotes(trip)}
                  >
                    <Bell className="h-4 w-4 mr-1" /> {tr('View Quotes', 'कोटेशन देखें')}
                  </Button>
                )}
                {trip.status === 'completed' && !trip.feedback && (
                  <Button
                    size="sm"
                    className="bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30"
                    onClick={() => { setSelectedTrip(trip); setShowReviewDialog(true); }}
                  >
                    <Star className="h-4 w-4 mr-1" /> {tr('Rate Trip', 'यात्रा को रेट करें')}
                  </Button>
                )}
                {['pending', 'confirmed'].includes(trip.status) && (
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => { setSelectedTrip(trip); setShowCancelDialog(true); }}
                  >
                    <X className="h-4 w-4 mr-1" /> {tr('Cancel', 'रद्द करें')}
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="border-slate-600 text-slate-300"
                  onClick={() => setSelectedTrip(trip)}
                >
                  <FileText className="h-4 w-4 mr-1" /> {tr('Details', 'विवरण')}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-slate-600 text-slate-300"
                >
                  <MessageSquare className="h-4 w-4 mr-1" /> {tr('Chat', 'चैट')}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Cancel Dialog */}
      <Dialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
        <DialogContent className="bg-slate-900 border-slate-700 text-white">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-400" />
              {tr('Cancel Booking', 'बुकिंग रद्द करें')}
            </DialogTitle>
          </DialogHeader>
          <div className="py-4 space-y-4">
            <p className="text-slate-400">{tr('Are you sure you want to cancel this booking?', 'क्या आप वाकई यह बुकिंग रद्द करना चाहते हैं?')}</p>
            <div>
              <label className="block text-sm text-slate-400 mb-2">{tr('Reason for cancellation *', 'रद्द करने का कारण *')}</label>
              <textarea
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                className="w-full p-3 rounded-lg bg-slate-800 border border-slate-700 text-white"
                rows={3}
                placeholder={tr('Please provide a reason...', 'कृपया कारण बताएं...')}
              />
            </div>
            <label className="flex items-center gap-2 text-slate-300">
              <input
                type="checkbox"
                checked={isEmergency}
                onChange={(e) => setIsEmergency(e.target.checked)}
                className="rounded"
              />
              <span>{tr('This is an emergency cancellation (full refund)', 'यह आपातकालीन रद्दीकरण है (पूरा रिफंड)')}</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCancelDialog(false)} className="border-slate-600 text-slate-300">
              {tr('Keep Booking', 'बुकिंग रखें')}
            </Button>
            <Button variant="destructive" onClick={handleCancelTrip} disabled={processing || !cancelReason}>
              {processing ? tr('Processing...', 'प्रोसेस हो रहा है...') : tr('Cancel Booking', 'बुकिंग रद्द करें')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Review Dialog */}
      <Dialog open={showReviewDialog} onOpenChange={setShowReviewDialog}>
        <DialogContent className="bg-slate-900 border-slate-700 text-white">
          <DialogHeader>
            <DialogTitle>{tr('Rate Your Trip', 'अपनी यात्रा को रेट करें')}</DialogTitle>
          </DialogHeader>
          <div className="py-4 space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-2">{tr('Overall Rating', 'कुल रेटिंग')}</label>
              <div className="flex gap-2">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    onClick={() => setReviewData({ ...reviewData, overall_rating: star })}
                    className={`p-2 rounded ${star <= reviewData.overall_rating ? 'text-yellow-400' : 'text-slate-600'}`}
                  >
                    <Star className="h-8 w-8" fill={star <= reviewData.overall_rating ? 'currentColor' : 'none'} />
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">{tr('Your Review', 'आपकी समीक्षा')}</label>
              <textarea
                value={reviewData.comment}
                onChange={(e) => setReviewData({ ...reviewData, comment: e.target.value })}
                className="w-full p-3 rounded-lg bg-slate-800 border border-slate-700 text-white"
                rows={3}
                placeholder={tr('Share your experience...', 'अपना अनुभव साझा करें...')}
              />
            </div>
            <label className="flex items-center gap-2 text-slate-300">
              <input
                type="checkbox"
                checked={reviewData.recommend}
                onChange={(e) => setReviewData({ ...reviewData, recommend: e.target.checked })}
                className="rounded"
              />
              <span>{tr('I would recommend this operator', 'मैं इस ऑपरेटर की सिफ़ारिश करूंगा/करूंगी')}</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowReviewDialog(false)} className="border-slate-600 text-slate-300">
              {tr('Cancel', 'रद्द करें')}
            </Button>
            <Button onClick={handleSubmitReview} disabled={processing} className="bg-lime text-black hover:bg-lime/90">
              {processing ? tr('Submitting...', 'भेजा जा रहा है...') : tr('Submit Review', 'समीक्षा भेजें')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Quotes Dialog - View & Respond to Operator Quotes */}
      <Dialog open={showQuotesDialog} onOpenChange={setShowQuotesDialog}>
        <DialogContent className="bg-slate-900 border-slate-700 text-white max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Bell className="h-5 w-5 text-lime" />
              {bi("Received Quotes / प्राप्त कोट्स")}
            </DialogTitle>
          </DialogHeader>
          <div className="py-4 space-y-4 max-h-[60vh] overflow-y-auto">
            {tripQuotes.length === 0 ? (
              <div className="text-center py-8">
                <Bell className="h-12 w-12 text-slate-600 mx-auto mb-3" />
                <p className="text-slate-400">{tr('No quotes received yet', 'अभी कोई कोटेशन नहीं मिला')}</p>
                <p className="text-slate-500 text-sm mt-1">
                  {tr('Operators will send you revised quotes soon', 'ऑपरेटर जल्द ही आपको संशोधित कोटेशन भेजेंगे')}
                </p>
              </div>
            ) : (
              tripQuotes.map((quote) => (
                <div
                  key={quote.id}
                  className={`p-4 rounded-sm border ${
                    quote.status === 'accepted'
                      ? 'bg-green-500/10 border-green-500/30'
                      : quote.status === 'rejected_by_customer'
                      ? 'bg-red-500/10 border-red-500/30'
                      : 'bg-slate-800/50 border-slate-700'
                  }`}
                >
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <p className="text-white font-semibold">
                        {quote.operator?.company_name || quote.operator_name}
                      </p>
                      {quote.operator?.average_rating && (
                        <p className="text-sm text-slate-400 flex items-center gap-1">
                          <Star className="h-3 w-3 text-yellow-400" />
                          {quote.operator.average_rating} rating
                        </p>
                      )}
                    </div>
                    <span className={`px-2 py-1 rounded text-xs ${
                      quote.status === 'accepted' ? 'bg-green-500/20 text-green-400' :
                      quote.status === 'rejected_by_customer' ? 'bg-red-500/20 text-red-400' :
                      'bg-amber/20 text-amber'
                    }`}>
                      {quote.status === 'accepted' ? tr('✓ Accepted', '✓ स्वीकृत') :
                       quote.status === 'rejected_by_customer' ? tr('✗ Rejected', '✗ अस्वीकृत') :
                       tr('Pending Response', 'जवाब लंबित')}
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-lime text-2xl font-bold">
                        ₹{quote.amount?.toLocaleString()}
                      </p>
                      {quote.revision_count > 1 && (
                        <p className="text-slate-500 text-xs">
                          {tr('Revision #', 'संशोधन #')}{quote.revision_count}
                        </p>
                      )}
                      {quote.notes && (
                        <p className="text-slate-400 text-sm mt-2">
                          "{quote.notes}"
                        </p>
                      )}
                    </div>

                    {quote.status === 'sent' || quote.status === 'pending' ? (
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          className="bg-green-600 hover:bg-green-700"
                          onClick={() => handleQuoteResponse(quote.id, 'accept')}
                          disabled={processing}
                        >
                          <Check className="h-4 w-4 mr-1" /> {tr('Accept', 'स्वीकार करें')}
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleQuoteResponse(quote.id, 'reject')}
                          disabled={processing}
                        >
                          <X className="h-4 w-4 mr-1" /> {tr('Reject', 'अस्वीकार करें')}
                        </Button>
                      </div>
                    ) : null}
                  </div>

                  {/* Quote Breakdown if available */}
                  {quote.breakdown && Object.keys(quote.breakdown).length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-700">
                      <p className="text-slate-400 text-xs mb-2">{tr('Price Breakdown:', 'कीमत का विवरण:')}</p>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        {Object.entries(quote.breakdown).map(([key, value]) => (
                          <div key={key} className="flex justify-between">
                            <span className="text-slate-500">{key}:</span>
                            <span className="text-slate-300">₹{value?.toLocaleString()}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowQuotesDialog(false)} className="border-slate-600 text-slate-300">
              {tr('Close', 'बंद करें')}
            </Button>
            <Button onClick={() => loadTripQuotes(selectedTrip?.id)} className="bg-slate-700 hover:bg-slate-600">
              <RefreshCw className="h-4 w-4 mr-1" /> {tr('Refresh', 'रीफ़्रेश करें')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default MyTrips;
