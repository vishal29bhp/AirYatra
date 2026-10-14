import React, { useState } from 'react';
import { TrendingUp, Mail, Phone, Building2, Send, CheckCircle, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { tr } from '../../lib/bilingual';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const INVESTMENT_RANGES = [
  { value: '1-5L', label: tr('₹1 - 5 Lakhs', '₹1 - 5 लाख') },
  { value: '5-25L', label: tr('₹5 - 25 Lakhs', '₹5 - 25 लाख') },
  { value: '25L-1Cr', label: tr('₹25 Lakhs - 1 Crore', '₹25 लाख - 1 करोड़') },
  { value: '1Cr+', label: tr('₹1 Crore+', '₹1 करोड़+') }
];

function InvestorInterestSection() {
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    phone: '',
    company_name: '',
    investment_range: '',
    message: ''
  });
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [referenceId, setReferenceId] = useState('');

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.full_name || !formData.email || !formData.phone || !formData.investment_range) {
      toast.error(tr('Please fill all required fields', 'कृपया सभी आवश्यक फ़ील्ड भरें'));
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/content/investor-interest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Submission failed');
      }

      setSubmitted(true);
      setReferenceId(data.reference_id);
      toast.success(tr('Thank you! We will contact you shortly.', 'धन्यवाद! हम जल्द ही आपसे संपर्क करेंगे।'));
    } catch (err) {
      toast.error(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <section className="py-20 px-6 bg-slate-950" data-testid="investor-section">
        <div className="max-w-2xl mx-auto text-center">
          <div className="bg-green-500/20 p-4 rounded-full w-fit mx-auto mb-6">
            <CheckCircle className="h-16 w-16 text-green-500" />
          </div>
          <h2 className="text-3xl font-bold text-white mb-4">{tr('Thank You for Your Interest!', 'आपकी रुचि के लिए धन्यवाद!')}</h2>
          <p className="text-slate-400 mb-4">
            {tr('Your inquiry has been received. Our investment relations team will contact you within 24-48 hours.', 'आपकी पूछताछ मिल गई है। हमारी निवेशक संबंध टीम 24-48 घंटों में आपसे संपर्क करेगी।')}
          </p>
          <p className="text-amber text-sm">
            {tr('Reference ID:', 'संदर्भ ID:')} <span className="font-mono">{referenceId}</span>
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="py-20 px-6 bg-slate-950" data-testid="investor-section">
      <div className="max-w-6xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Left: Info */}
          <div>
            <span className="ay-overline">{tr('Investor Relations', 'निवेशक संबंध')}</span>
            <h2 className="text-4xl md:text-5xl font-bold text-white mt-3 mb-6">
              {tr('Invest in the Future of Indian Aviation', 'भारतीय विमानन के भविष्य में निवेश करें')}
            </h2>
            <p className="text-slate-400 text-lg mb-8">
              {tr('Join us in revolutionizing private aviation in India. AirYatra is growing rapidly with a proven business model and ambitious expansion plans.', 'भारत में निजी विमानन को बदलने में हमारे साथ जुड़ें। AirYatra एक सिद्ध बिज़नेस मॉडल और महत्वाकांक्षी विस्तार योजनाओं के साथ तेज़ी से बढ़ रहा है।')}
            </p>

            {/* Key Metrics */}
            <div className="grid grid-cols-2 gap-4 mb-8">
              <div className="bg-slate-800/50 border border-slate-700 rounded-sm p-4">
                <div className="text-3xl font-bold text-lime">500+</div>
                <div className="text-slate-400 text-sm">{tr('Flights Completed', 'पूरी हुई उड़ानें')}</div>
              </div>
              <div className="bg-slate-800/50 border border-slate-700 rounded-sm p-4">
                <div className="text-3xl font-bold text-lime">40%</div>
                <div className="text-slate-400 text-sm">{tr('YoY Growth', 'सालाना वृद्धि')}</div>
              </div>
              <div className="bg-slate-800/50 border border-slate-700 rounded-sm p-4">
                <div className="text-3xl font-bold text-lime">15+</div>
                <div className="text-slate-400 text-sm">{tr('Cities Served', 'सेवा वाले शहर')}</div>
              </div>
              <div className="bg-slate-800/50 border border-slate-700 rounded-sm p-4">
                <div className="text-3xl font-bold text-lime">₹50Cr+</div>
                <div className="text-slate-400 text-sm">{tr('Revenue Target', 'राजस्व लक्ष्य')}</div>
              </div>
            </div>

            <div className="flex items-center gap-2 text-slate-400 text-sm">
              <TrendingUp className="h-4 w-4 text-green-500" />
              <span>{tr('Profitable unit economics with clear path to profitability', 'लाभदायक यूनिट इकोनॉमिक्स और मुनाफ़े की स्पष्ट राह')}</span>
            </div>
          </div>

          {/* Right: Form */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-sm p-8">
            <h3 className="text-2xl font-bold text-white mb-6">{tr('Express Your Interest', 'अपनी रुचि बताएं')}</h3>
            
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label className="text-slate-300">{tr('Full Name *', 'पूरा नाम *')}</Label>
                <div className="relative">
                  <User className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
                  <Input
                    name="full_name"
                    value={formData.full_name}
                    onChange={handleChange}
                    placeholder={tr('Your full name', 'आपका पूरा नाम')}
                    className="pl-10 bg-slate-900 border-slate-600 text-white"
                    required
                  />
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-slate-300">{tr('Email *', 'ईमेल *')}</Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
                    <Input
                      name="email"
                      type="email"
                      value={formData.email}
                      onChange={handleChange}
                      placeholder="your@email.com"
                      className="pl-10 bg-slate-900 border-slate-600 text-white"
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-slate-300">{tr('Phone *', 'फ़ोन *')}</Label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
                    <Input
                      name="phone"
                      value={formData.phone}
                      onChange={handleChange}
                      placeholder="+91 98765 43210"
                      className="pl-10 bg-slate-900 border-slate-600 text-white"
                      required
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-slate-300">{tr('Company (Optional)', 'कंपनी (वैकल्पिक)')}</Label>
                <div className="relative">
                  <Building2 className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
                  <Input
                    name="company_name"
                    value={formData.company_name}
                    onChange={handleChange}
                    placeholder={tr('Your company name', 'आपकी कंपनी का नाम')}
                    className="pl-10 bg-slate-900 border-slate-600 text-white"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-slate-300">{tr('Investment Range *', 'निवेश सीमा *')}</Label>
                <div className="grid grid-cols-2 gap-3">
                  {INVESTMENT_RANGES.map((range) => (
                    <button
                      key={range.value}
                      type="button"
                      onClick={() => setFormData(prev => ({ ...prev, investment_range: range.value }))}
                      className={`p-3 rounded-lg border text-sm font-medium transition-all ${
                        formData.investment_range === range.value
                          ? 'bg-lime border-lime text-black'
                          : 'bg-slate-900 border-slate-600 text-slate-300 hover:border-lime/50'
                      }`}
                    >
                      {range.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-slate-300">{tr('Message (Optional)', 'संदेश (वैकल्पिक)')}</Label>
                <textarea
                  name="message"
                  value={formData.message}
                  onChange={handleChange}
                  placeholder={tr('Tell us about your investment goals...', 'अपने निवेश लक्ष्यों के बारे में बताएं...')}
                  rows={3}
                  className="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-lime"
                />
              </div>

              <Button
                type="submit"
                disabled={loading}
                className="w-full bg-lime text-black hover:bg-lime/90 font-semibold rounded-sm h-12"
              >
                {loading ? (
                  tr('Submitting...', 'भेजा जा रहा है...')
                ) : (
                  <>
                    <Send className="mr-2 h-5 w-5" />
                    {tr('Submit Interest', 'रुचि भेजें')}
                  </>
                )}
              </Button>

              <p className="text-xs text-slate-500 text-center">
                {tr('By submitting, you agree to be contacted by our investment team', 'सबमिट करके आप हमारी निवेश टीम द्वारा संपर्क किए जाने के लिए सहमति देते हैं')}
              </p>
            </form>
          </div>
        </div>
      </div>
    </section>
  );
}

export default InvestorInterestSection;
