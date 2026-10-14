import React, { useState, useEffect } from 'react';
import { 
  AlertTriangle, Phone, MapPin, Users, Clock, Send, Loader2, 
  Ambulance, Siren, UserCheck, Building2, Heart, Timer
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import LandingPointSelector from '../shared/LandingPointSelector';
import { bi, tr } from '../../lib/bilingual';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Emergency Booking Form Component
 * For priority emergency bookings with instant operator notification
 */
const EmergencyBookingForm = ({
  user,
  onSuccess,
  onCancel,
  className = ''
}) => {
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState(null);
  const [formData, setFormData] = useState({
    from_location: '',
    from_latitude: 0,
    from_longitude: 0,
    to_location: '',
    to_latitude: 0,
    to_longitude: 0,
    urgency_level: 'high',
    urgency_reason: 'medical_emergency',
    required_by: '',
    passengers: 1,
    aircraft_type: 'any',
    special_requirements: '',
    emergency_contact_name: '',
    emergency_contact_phone: ''
  });
  const [pickupPoint, setPickupPoint] = useState(null);
  const [dropPoint, setDropPoint] = useState(null);

  // Load emergency config
  useEffect(() => {
    fetchConfig();
    // Pre-fill contact if user is logged in
    if (user) {
      setFormData(prev => ({
        ...prev,
        emergency_contact_name: user.full_name || '',
        emergency_contact_phone: user.phone || ''
      }));
    }
  }, [user]);

  const fetchConfig = async () => {
    try {
      const res = await fetch(`${API_URL}/api/emergency/config`);
      const data = await res.json();
      setConfig(data);
    } catch (error) {
      console.error('Failed to load emergency config:', error);
    }
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  // Handle landing point selection
  const handlePickupSelect = (data) => {
    setPickupPoint(data);
    if (data) {
      setFormData(prev => ({
        ...prev,
        from_location: data.landing_point_name || '',
        from_latitude: data.latitude || 0,
        from_longitude: data.longitude || 0
      }));
    }
  };

  const handleDropSelect = (data) => {
    setDropPoint(data);
    if (data) {
      setFormData(prev => ({
        ...prev,
        to_location: data.landing_point_name || '',
        to_latitude: data.latitude || 0,
        to_longitude: data.longitude || 0
      }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!user) {
      toast.error(tr('Please login to create emergency booking', 'आपातकालीन बुकिंग के लिए कृपया लॉगिन करें'));
      return;
    }
    
    if (!formData.from_location || !formData.to_location) {
      toast.error(tr('Please select pickup and drop locations', 'कृपया पिकअप और ड्रॉप स्थान चुनें'));
      return;
    }
    
    if (!formData.emergency_contact_name || !formData.emergency_contact_phone) {
      toast.error(tr('Emergency contact details required', 'आपातकालीन संपर्क विवरण आवश्यक है'));
      return;
    }
    
    setLoading(true);
    
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/emergency/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(formData)
      });
      
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to create emergency booking');
      }
      
      toast.success(
        <div>
          <p className="font-semibold">{tr('🚨 Emergency Request Sent!', '🚨 आपातकालीन अनुरोध भेजा गया!')}</p>
          <p className="text-sm">{data.message}</p>
          <p className="text-xs mt-1">{tr('Request #:', 'अनुरोध #:')} {data.emergency_number}</p>
        </div>
      );
      
      if (onSuccess) {
        onSuccess(data);
      }
      
    } catch (error) {
      toast.error(error.message || 'Failed to submit emergency request');
    } finally {
      setLoading(false);
    }
  };

  const urgencyLevels = config?.urgency_levels || {
    critical: { label: bi('Critical / अत्यंत जरूरी'), color: 'red', surcharge_percent: 50 },
    high: { label: bi('High / उच्च'), color: 'orange', surcharge_percent: 25 },
    medium: { label: bi('Medium / मध्यम'), color: 'yellow', surcharge_percent: 10 }
  };

  const urgencyReasons = config?.urgency_reasons || {
    medical_emergency: { label: bi('Medical Emergency / चिकित्सा आपातकाल'), icon: '🏥' },
    time_critical: { label: bi('Time Critical / समय-महत्वपूर्ण'), icon: '⏰' },
    vip_travel: { label: bi('VIP Travel / वीआईपी यात्रा'), icon: '👔' },
    disaster_relief: { label: bi('Disaster Relief / आपदा राहत'), icon: '🆘' },
    organ_transport: { label: bi('Organ Transport / अंग परिवहन'), icon: '❤️' }
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Emergency Header */}
      <div className="bg-red-500/10 border border-red-500/30 rounded-sm p-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-red-500/20 rounded-full animate-pulse">
            <Siren className="h-6 w-6 text-red-400" />
          </div>
          <div>
            <h2 className="text-red-400 font-bold text-xl">
              {bi("Emergency Booking / आपातकालीन बुकिंग")}
            </h2>
            <p className="text-red-400/70 text-sm">
              {tr('Priority queue + Instant operator notification', 'प्राथमिकता कतार + ऑपरेटर को तुरंत सूचना')}
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Urgency Level */}
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-white text-base flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-400" />
              {bi("Urgency Level / आवश्यकता स्तर")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {Object.entries(urgencyLevels).map(([key, value]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => handleInputChange('urgency_level', key)}
                  className={`p-4 rounded-lg border-2 transition-all text-left ${
                    formData.urgency_level === key
                      ? key === 'critical' ? 'border-red-500 bg-red-500/20' :
                        key === 'high' ? 'border-lime bg-lime/20' :
                        'border-yellow-500 bg-yellow-500/20'
                      : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
                  }`}
                >
                  <div className={`text-lg font-bold ${
                    key === 'critical' ? 'text-red-400' :
                    key === 'high' ? 'text-lime' : 'text-yellow-400'
                  }`}>
                    {value.label}
                  </div>
                  <div className="text-slate-400 text-sm mt-1">
                    +{value.surcharge_percent}{tr('% surcharge', '% अधिभार')}
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Urgency Reason */}
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-white text-base flex items-center gap-2">
              <Heart className="h-4 w-4 text-pink-400" />
              {bi("Reason / कारण")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(urgencyReasons).map(([key, value]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => handleInputChange('urgency_reason', key)}
                  className={`p-3 rounded-lg border-2 transition-all text-left flex items-center gap-3 ${
                    formData.urgency_reason === key
                      ? 'border-lime bg-lime/20'
                      : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
                  }`}
                >
                  <span className="text-2xl">{value.icon}</span>
                  <span className="text-white text-sm">{value.label}</span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Locations */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-white text-base flex items-center gap-2">
                <MapPin className="h-4 w-4 text-green-400" />
                {bi("Pickup / पिकअप")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <LandingPointSelector
                label={tr('Select pickup point', 'पिकअप स्थान चुनें')}
                type="pickup"
                onSelect={handlePickupSelect}
                selectedPoint={pickupPoint}
                compact={true}
              />
            </CardContent>
          </Card>

          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-white text-base flex items-center gap-2">
                <MapPin className="h-4 w-4 text-red-400" />
                {bi("Drop / गंतव्य")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <LandingPointSelector
                label={tr('Select drop point', 'ड्रॉप स्थान चुनें')}
                type="drop"
                onSelect={handleDropSelect}
                selectedPoint={dropPoint}
                compact={true}
              />
            </CardContent>
          </Card>
        </div>

        {/* Flight Details */}
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-white text-base flex items-center gap-2">
              <Users className="h-4 w-4 text-amber" />
              {bi("Flight Details / उड़ान विवरण")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label className="text-slate-300 mb-2 block">{bi("Passengers / यात्री")}</Label>
                <Input
                  type="number"
                  min="1"
                  max="10"
                  value={formData.passengers}
                  onChange={(e) => handleInputChange('passengers', parseInt(e.target.value))}
                  className="bg-slate-900 border-slate-600 text-white"
                />
              </div>
              
              <div>
                <Label className="text-slate-300 mb-2 block">{tr('Aircraft Type', 'विमान का प्रकार')}</Label>
                <select
                  value={formData.aircraft_type}
                  onChange={(e) => handleInputChange('aircraft_type', e.target.value)}
                  className="w-full p-2 bg-slate-900 border border-slate-600 rounded-md text-white"
                >
                  <option value="any">{tr('Any Available', 'जो भी उपलब्ध हो')}</option>
                  <option value="helicopter">{tr('Helicopter', 'हेलीकॉप्टर')}</option>
                  <option value="light_jet">{tr('Light Jet', 'लाइट जेट')}</option>
                </select>
              </div>
              
              <div>
                <Label className="text-slate-300 mb-2 block">{tr('Required By (Optional)', 'कब तक चाहिए (वैकल्पिक)')}</Label>
                <Input
                  type="datetime-local"
                  value={formData.required_by}
                  onChange={(e) => handleInputChange('required_by', e.target.value)}
                  className="bg-slate-900 border-slate-600 text-white"
                />
              </div>
            </div>
            
            <div className="mt-4">
              <Label className="text-slate-300 mb-2 block">{tr('Special Requirements', 'विशेष आवश्यकताएं')}</Label>
              <Textarea
                value={formData.special_requirements}
                onChange={(e) => handleInputChange('special_requirements', e.target.value)}
                placeholder={tr('Medical equipment needed, stretcher required, oxygen support...', 'चिकित्सा उपकरण, स्ट्रेचर, ऑक्सीजन सहायता...')}
                className="bg-slate-900 border-slate-600 text-white"
                rows={2}
              />
            </div>
          </CardContent>
        </Card>

        {/* Emergency Contact */}
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-white text-base flex items-center gap-2">
              <Phone className="h-4 w-4 text-green-400" />
              {bi("Emergency Contact / आपातकालीन संपर्क")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label className="text-slate-300 mb-2 block">{tr('Contact Name *', 'संपर्क नाम *')}</Label>
                <Input
                  value={formData.emergency_contact_name}
                  onChange={(e) => handleInputChange('emergency_contact_name', e.target.value)}
                  placeholder={tr('Full name', 'पूरा नाम')}
                  className="bg-slate-900 border-slate-600 text-white"
                  required
                />
              </div>
              
              <div>
                <Label className="text-slate-300 mb-2 block">{tr('Phone Number *', 'फ़ोन नंबर *')}</Label>
                <Input
                  type="tel"
                  value={formData.emergency_contact_phone}
                  onChange={(e) => handleInputChange('emergency_contact_phone', e.target.value)}
                  placeholder="+91 XXXXX XXXXX"
                  className="bg-slate-900 border-slate-600 text-white"
                  required
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Surcharge Notice */}
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-yellow-400 shrink-0" />
            <div className="text-yellow-400 text-sm">
              <p className="font-medium">{bi("Emergency Surcharge Notice / आपातकालीन अधिभार")}</p>
              <p className="mt-1 text-yellow-400/70">
                {tr('Emergency bookings include a', 'आपातकालीन बुकिंग में')} {urgencyLevels[formData.urgency_level]?.surcharge_percent}{tr('% priority surcharge for immediate processing and dedicated operator response.', '% प्राथमिकता अधिभार शामिल है, ताकि तुरंत प्रोसेसिंग और समर्पित ऑपरेटर प्रतिक्रिया मिले।')}
              </p>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-4">
          {onCancel && (
            <Button 
              type="button" 
              variant="outline" 
              onClick={onCancel}
              className="flex-1 border-slate-600"
            >
              {tr('Cancel', 'रद्द करें')}
            </Button>
          )}
          <Button 
            type="submit" 
            disabled={loading}
            className="flex-1 bg-red-600 hover:bg-red-700"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                {tr('Sending...', 'भेजा जा रहा है...')}
              </>
            ) : (
              <>
                <Siren className="h-4 w-4 mr-2" />
                {tr('Send Emergency Request', 'आपातकालीन अनुरोध भेजें')}
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default EmergencyBookingForm;
