import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { 
  Plane, Shield, Users, TrendingUp, CheckCircle, Crown, Building2, Lock,
  ChevronLeft, ChevronRight, MapPin, Mail, Phone, Clock, Star, Award, 
  Briefcase, HeartHandshake, Globe, Headphones, FileCheck, Zap
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import LanguageSwitcher from '../components/shared/LanguageSwitcher';
import TestimonialsSlider from '../components/landing/TestimonialsSlider';
import InvestorInterestSection from '../components/landing/InvestorInterestSection';
import { bi, tr } from '../lib/bilingual';

// Hero Slider Images
const HERO_SLIDES = [
  {
    id: 1,
    image: "https://images.unsplash.com/photo-1619659085985-f51a00f0160a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1OTN8MHwxfHNlYXJjaHw0fHxsdXh1cnklMjBwcml2YXRlJTIwamV0JTIwY2hhcnRlciUyMGF2aWF0aW9ufGVufDB8fHx8MTc4NTY3MjI4NHww&ixlib=rb-4.1.0&q=85",
    title: tr('Premium Charter Flights', 'प्रीमियम चार्टर उड़ानें'),
    subtitle: tr('Experience luxury in the skies with our world-class fleet', 'हमारे विश्व-स्तरीय बेड़े के साथ आसमान में विलासिता का अनुभव करें'),
    titleHi: "प्रीमियम चार्टर फ्लाइट्स"
  },
  {
    id: 2,
    image: "https://images.unsplash.com/photo-1474302770737-173ee21bab63?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1OTN8MHwxfHNlYXJjaHwzfHxsdXh1cnklMjBwcml2YXRlJTIwamV0JTIwY2hhcnRlciUyMGF2aWF0aW9ufGVufDB8fHx8MTc4NTY3MjI4NHww&ixlib=rb-4.1.0&q=85",
    title: tr('Private Jet Excellence', 'प्राइवेट जेट की उत्कृष्टता'),
    subtitle: tr('Your personal aircraft awaits for seamless journeys', 'सहज यात्रा के लिए आपका निजी विमान तैयार है'),
    titleHi: "प्राइवेट जेट एक्सीलेंस"
  },
  {
    id: 3,
    image: "https://images.unsplash.com/photo-1782865423531-27f6fab92fe8?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2OTV8MHwxfHNlYXJjaHwyfHxoZWxpY29wdGVyJTIwYWVyaWFsJTIwdG91ciUyMGNpdHlzY2FwZXxlbnwwfHx8fDE3ODU2NzIyODl8MA&ixlib=rb-4.1.0&q=85",
    title: tr('Helicopter Services', 'हेलीकॉप्टर सेवाएं'),
    subtitle: tr('City tours, transfers & emergency medical services', 'शहर भ्रमण, ट्रांसफर और आपातकालीन चिकित्सा सेवाएं'),
    titleHi: "हेलीकॉप्टर सेवाएं"
  },
  {
    id: 4,
    image: "https://images.unsplash.com/photo-1625513123245-fcb02d69ad12?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1OTN8MHwxfHNlYXJjaHwxfHxsdXh1cnklMjBwcml2YXRlJTIwamV0JTIwY2hhcnRlciUyMGF2aWF0aW9ufGVufDB8fHx8MTc4NTY3MjI4NHww&ixlib=rb-4.1.0&q=85",
    title: tr('Luxury Interiors', 'शानदार इंटीरियर'),
    subtitle: tr('Travel in comfort with premium cabin amenities', 'प्रीमियम केबिन सुविधाओं के साथ आराम से यात्रा करें'),
    titleHi: "लग्जरी इंटीरियर्स"
  },
  {
    id: 5,
    image: "https://images.unsplash.com/photo-1661954864180-e61dea14208a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1OTN8MHwxfHNlYXJjaHwyfHxsdXh1cnklMjBwcml2YXRlJTIwamV0JTIwY2hhcnRlciUyMGF2aWF0aW9ufGVufDB8fHx8MTc4NTY3MjI4NHww&ixlib=rb-4.1.0&q=85",
    title: tr('In-Flight Dining', 'उड़ान में भोजन'),
    subtitle: tr('Gourmet cuisine served at 40,000 feet', '40,000 फीट पर परोसा गया उम्दा भोजन'),
    titleHi: "इन-फ्लाइट डाइनिंग"
  }
];

// Company Info
const COMPANY_INFO = {
  address: "Office No 7,8 Daynemic Granduer, D Wing, Ground Floor, Undri-Wadachi Road, Undri, Pune - 411060",
  email: "airyatraadmin@gmail.com",
  phone: "+91 98765 43210",
  hours: "Mon - Sat: 9:00 AM - 7:00 PM"
};

function LandingPage({ user }) {
  const { t } = useTranslation();
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);

  // Auto-slide effect
  useEffect(() => {
    if (!isAutoPlaying) return;
    
    const interval = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % HERO_SLIDES.length);
    }, 5000);
    
    return () => clearInterval(interval);
  }, [isAutoPlaying]);

  const nextSlide = () => {
    setIsAutoPlaying(false);
    setCurrentSlide((prev) => (prev + 1) % HERO_SLIDES.length);
  };

  const prevSlide = () => {
    setIsAutoPlaying(false);
    setCurrentSlide((prev) => (prev - 1 + HERO_SLIDES.length) % HERO_SLIDES.length);
  };

  const goToSlide = (index) => {
    setIsAutoPlaying(false);
    setCurrentSlide(index);
  };

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 bg-slate-950/90 backdrop-blur-lg border-b border-slate-800" data-testid="landing-nav">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <Plane className="h-8 w-8 text-lime" />
            <span className="text-2xl font-bold text-white tracking-tight">AirYatra</span>
          </div>
          
          {/* Navigation Links */}
          <div className="hidden lg:flex items-center space-x-8">
            <a href="#services" className="text-slate-300 hover:text-lime transition-colors">{tr('Services', 'सेवाएं')}</a>
            <Link to="/fleet" className="text-slate-300 hover:text-lime transition-colors">{tr('Fleet', 'बेड़ा')}</Link>
            <Link to="/blog" className="text-slate-300 hover:text-lime transition-colors">{tr('Blog', 'ब्लॉग')}</Link>
            <a href="#about" className="text-slate-300 hover:text-lime transition-colors">{tr('About', 'हमारे बारे में')}</a>
            <a href="#contact" className="text-slate-300 hover:text-lime transition-colors">{tr('Contact', 'संपर्क')}</a>
          </div>
          
          <div className="flex items-center space-x-3">
            <LanguageSwitcher />
            {user ? (
              <Link to={`/${user.roles[0]}`}>
                <Button variant="default" className="bg-lime text-black hover:bg-lime/90 font-semibold rounded-sm" data-testid="dashboard-btn">
                  {t('nav.dashboard')}
                </Button>
              </Link>
            ) : (
              <>
                <Link to="/login">
                  <Button variant="ghost" className="text-white hidden sm:inline-flex" data-testid="login-btn">
                    {t('nav.login')}
                  </Button>
                </Link>
                <Link to="/booking">
                  <Button className="bg-lime text-black hover:bg-lime/90 font-semibold rounded-sm" data-testid="book-now-btn">
                    {t('nav.bookNow')}
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section with 5-Slide Carousel */}
      <section className="relative h-screen" data-testid="hero-section">
        {/* Slides */}
        <div className="absolute inset-0 overflow-hidden">
          {HERO_SLIDES.map((slide, index) => (
            <div
              key={slide.id}
              className={`absolute inset-0 transition-opacity duration-1000 ${
                index === currentSlide ? 'opacity-100' : 'opacity-0'
              }`}
            >
              <img
                src={slide.image}
                alt={slide.title}
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-b from-slate-950/70 via-slate-950/50 to-slate-950"></div>
            </div>
          ))}
        </div>
        
        {/* Slide Content */}
        <div className="relative h-full flex items-center justify-center px-6">
          <div className="max-w-5xl mx-auto text-center space-y-6">
            <div className="mb-4">
              <span className="ay-overline">{tr("India's Premier Aviation Platform", 'भारत का प्रमुख विमानन प्लेटफ़ॉर्म')}</span>
            </div>
            
            <h1 className="text-5xl md:text-7xl font-black text-white tracking-tight animate-fade-in" data-testid="hero-title">
              {HERO_SLIDES[currentSlide].title}
            </h1>
            <p className="text-xl md:text-2xl text-slate-300 max-w-3xl mx-auto font-light">
              {HERO_SLIDES[currentSlide].subtitle}
            </p>
            
            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-4">
              <Link to="/booking">
                <Button size="lg" className="bg-lime text-black hover:bg-lime/90 font-semibold text-lg px-10 py-6 rounded-sm" data-testid="hero-book-btn">
                  <Plane className="mr-2 h-5 w-5" />
                  {tr('Book Your Flight', 'अपनी उड़ान बुक करें')}
                </Button>
              </Link>
              <Link to="/login">
                <Button size="lg" variant="outline" className="border-slate-600 bg-transparent text-white hover:bg-slate-800 text-lg px-10 py-6 rounded-sm" data-testid="become-operator-btn">
                  {tr('Become an Operator', 'ऑपरेटर बनें')}
                </Button>
              </Link>
            </div>
          </div>
        </div>

        {/* Slide Navigation Arrows */}
        <button
          onClick={prevSlide}
          className="absolute left-4 top-1/2 -translate-y-1/2 p-3 bg-black/30 hover:bg-black/50 rounded-full text-white transition-all z-10"
          aria-label={tr('Previous slide', 'पिछली स्लाइड')}
        >
          <ChevronLeft className="h-6 w-6" />
        </button>
        <button
          onClick={nextSlide}
          className="absolute right-4 top-1/2 -translate-y-1/2 p-3 bg-black/30 hover:bg-black/50 rounded-full text-white transition-all z-10"
          aria-label={tr('Next slide', 'अगली स्लाइड')}
        >
          <ChevronRight className="h-6 w-6" />
        </button>

        {/* Slide Indicators */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex gap-3 z-10">
          {HERO_SLIDES.map((_, index) => (
            <button
              key={index}
              onClick={() => goToSlide(index)}
              className={`w-3 h-3 rounded-full transition-all ${
                index === currentSlide 
                  ? 'bg-lime w-8' 
                  : 'bg-white/40 hover:bg-white/60'
              }`}
              aria-label={`Go to slide ${index + 1}`}
            />
          ))}
        </div>
      </section>

      {/* Services Section */}
      <section id="services" className="py-24 px-6 bg-slate-900" data-testid="services-section">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <span className="ay-overline">{tr('Our Services', 'हमारी सेवाएं')}</span>
            <h2 className="text-4xl md:text-5xl font-bold text-white mt-3 mb-4">
              {tr('Premium Aviation Solutions', 'प्रीमियम विमानन समाधान')}
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              {tr('From private jets to helicopters, we provide end-to-end aviation services tailored to your needs', 'प्राइवेट जेट से हेलीकॉप्टर तक, हम आपकी ज़रूरतों के अनुसार संपूर्ण विमानन सेवाएं देते हैं')}
            </p>
          </div>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {/* Service Card 1 */}
            <div className="group bg-slate-800/50 border border-slate-700 rounded-sm p-8 hover:border-lime/50 transition-colors">
              <div className="bg-slate-900 border border-slate-700 p-4 rounded-sm w-fit mb-6">
                <Plane className="h-8 w-8 text-lime" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">{tr('Private Jet Charter', 'प्राइवेट जेट चार्टर')}</h3>
              <p className="text-slate-400 mb-4">
                {tr('Luxury private jets for business and leisure travel. Fly on your schedule with maximum comfort and privacy.', 'व्यवसाय और अवकाश यात्रा के लिए शानदार प्राइवेट जेट। पूरे आराम और गोपनीयता के साथ अपने समय पर उड़ान भरें।')}
              </p>
              <ul className="space-y-2">
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Flexible scheduling', 'लचीला शेड्यूल')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('VIP ground handling', 'VIP ग्राउंड हैंडलिंग')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('In-flight catering', 'उड़ान में खानपान')}
                </li>
              </ul>
            </div>

            {/* Service Card 2 */}
            <div className="group bg-slate-800/50 border border-slate-700 rounded-sm p-8 hover:border-lime/50 transition-colors">
              <div className="bg-slate-900 border border-slate-700 p-4 rounded-sm w-fit mb-6">
                <Globe className="h-8 w-8 text-lime" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">{tr('Helicopter Services', 'हेलीकॉप्टर सेवाएं')}</h3>
              <p className="text-slate-400 mb-4">
                {tr('Quick city transfers, aerial tours, and emergency medical evacuations with our helicopter fleet.', 'हमारे हेलीकॉप्टर बेड़े से तेज़ शहर ट्रांसफर, हवाई भ्रमण और आपातकालीन चिकित्सा निकासी।')}
              </p>
              <ul className="space-y-2">
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('City-to-city transfers', 'शहर से शहर ट्रांसफर')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Scenic aerial tours', 'मनोरम हवाई भ्रमण')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Medical evacuation', 'चिकित्सा निकासी')}
                </li>
              </ul>
            </div>

            {/* Service Card 3 */}
            <div className="group bg-slate-800/50 border border-slate-700 rounded-sm p-8 hover:border-lime/50 transition-colors">
              <div className="bg-slate-900 border border-slate-700 p-4 rounded-sm w-fit mb-6">
                <Building2 className="h-8 w-8 text-lime" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">{tr('Corporate Solutions', 'कॉर्पोरेट समाधान')}</h3>
              <p className="text-slate-400 mb-4">
                {tr('Dedicated aviation solutions for enterprises with volume discounts and priority booking.', 'कंपनियों के लिए वॉल्यूम छूट और प्राथमिकता बुकिंग के साथ समर्पित विमानन समाधान।')}
              </p>
              <ul className="space-y-2">
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Corporate accounts', 'कॉर्पोरेट खाते')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Travel analytics', 'यात्रा विश्लेषण')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Dedicated manager', 'समर्पित मैनेजर')}
                </li>
              </ul>
            </div>

            {/* Service Card 4 */}
            <div className="group bg-slate-800/50 border border-slate-700 rounded-sm p-8 hover:border-lime/50 transition-colors">
              <div className="bg-slate-900 border border-slate-700 p-4 rounded-sm w-fit mb-6">
                <FileCheck className="h-8 w-8 text-lime" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">{tr('Aircraft Management', 'विमान प्रबंधन')}</h3>
              <p className="text-slate-400 mb-4">
                {tr('Complete aircraft management including maintenance, crew, and charter revenue optimization.', 'रखरखाव, क्रू और चार्टर आय बढ़ाने सहित संपूर्ण विमान प्रबंधन।')}
              </p>
              <ul className="space-y-2">
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Maintenance scheduling', 'रखरखाव शेड्यूलिंग')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Crew management', 'क्रू प्रबंधन')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Revenue optimization', 'आय अनुकूलन')}
                </li>
              </ul>
            </div>

            {/* Service Card 5 */}
            <div className="group bg-slate-800/50 border border-slate-700 rounded-sm p-8 hover:border-lime/50 transition-colors">
              <div className="bg-slate-900 border border-slate-700 p-4 rounded-sm w-fit mb-6">
                <Zap className="h-8 w-8 text-lime" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">{tr('Emergency Services', 'आपातकालीन सेवाएं')}</h3>
              <p className="text-slate-400 mb-4">
                {tr('24/7 emergency aviation support for medical, rescue, and urgent travel requirements.', 'चिकित्सा, बचाव और अत्यावश्यक यात्रा के लिए 24/7 आपातकालीन विमानन सहायता।')}
              </p>
              <ul className="space-y-2">
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Air ambulance', 'एयर एम्बुलेंस')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Organ transport', 'अंग परिवहन')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Disaster relief', 'आपदा राहत')}
                </li>
              </ul>
            </div>

            {/* Service Card 6 */}
            <div className="group bg-slate-800/50 border border-slate-700 rounded-sm p-8 hover:border-lime/50 transition-colors">
              <div className="bg-slate-900 border border-slate-700 p-4 rounded-sm w-fit mb-6">
                <HeartHandshake className="h-8 w-8 text-lime" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">{tr('Concierge Services', 'कंसीयर्ज सेवाएं')}</h3>
              <p className="text-slate-400 mb-4">
                {tr('End-to-end travel assistance including hotel bookings, ground transport, and event planning.', 'होटल बुकिंग, ज़मीनी परिवहन और कार्यक्रम योजना सहित संपूर्ण यात्रा सहायता।')}
              </p>
              <ul className="space-y-2">
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Luxury hotel booking', 'लक्ज़री होटल बुकिंग')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Limousine service', 'लिमोज़ीन सेवा')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {tr('Event coordination', 'कार्यक्रम समन्वय')}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* About Section */}
      <section id="about" className="py-24 px-6 bg-slate-950" data-testid="about-section">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            {/* About Content */}
            <div>
              <span className="ay-overline">{tr('About Us', 'हमारे बारे में')}</span>
              <h2 className="text-4xl md:text-5xl font-bold text-white mt-3 mb-6">
                {tr("India's Trusted Aviation Partner Since 2020", '2020 से भारत का भरोसेमंद विमानन साथी')}
              </h2>
              <p className="text-slate-400 text-lg mb-6">
                {tr("AirYatra is India's premier aviation operating system, connecting travelers with verified charter operators, helicopter services, and luxury aviation experiences. We have revolutionized how India flies private.", 'AirYatra भारत का प्रमुख विमानन ऑपरेटिंग सिस्टम है, जो यात्रियों को सत्यापित चार्टर ऑपरेटरों, हेलीकॉप्टर सेवाओं और लक्ज़री विमानन अनुभवों से जोड़ता है। हमने भारत में निजी उड़ान का तरीका बदल दिया है।')}
              </p>
              <p className="text-slate-400 mb-8">
                {tr('Our platform combines cutting-edge technology with personalized service to deliver seamless aviation experiences. From corporate executives to leisure travelers, we serve clients who value time, comfort, and reliability.', 'हमारा प्लेटफ़ॉर्म आधुनिक तकनीक और व्यक्तिगत सेवा को जोड़कर सहज विमानन अनुभव देता है। कॉर्पोरेट अधिकारियों से लेकर पर्यटकों तक, हम उन सभी की सेवा करते हैं जो समय, आराम और भरोसे को महत्व देते हैं।')}
              </p>
              
              {/* Stats */}
              <div className="grid grid-cols-3 gap-6 mb-8">
                <div className="text-center">
                  <div className="text-4xl font-bold text-lime">500+</div>
                  <div className="text-slate-400 text-sm">{tr('Flights Completed', 'पूरी हुई उड़ानें')}</div>
                </div>
                <div className="text-center">
                  <div className="text-4xl font-bold text-lime">50+</div>
                  <div className="text-slate-400 text-sm">{tr('Aircraft Fleet', 'विमान बेड़ा')}</div>
                </div>
                <div className="text-center">
                  <div className="text-4xl font-bold text-lime">100%</div>
                  <div className="text-slate-400 text-sm">{tr('Safety Record', 'सुरक्षा रिकॉर्ड')}</div>
                </div>
              </div>

              {/* Badges */}
              <div className="flex flex-wrap gap-4">
                <div className="flex items-center gap-2 bg-slate-800 border border-slate-700 px-4 py-2 rounded-sm">
                  <Award className="h-5 w-5 text-yellow-500" />
                  <span className="text-slate-300 text-sm">{tr('DGCA Approved', 'DGCA स्वीकृत')}</span>
                </div>
                <div className="flex items-center gap-2 bg-slate-800 border border-slate-700 px-4 py-2 rounded-sm">
                  <Shield className="h-5 w-5 text-green-500" />
                  <span className="text-slate-300 text-sm">{tr('ISO Certified', 'ISO प्रमाणित')}</span>
                </div>
                <div className="flex items-center gap-2 bg-slate-800 border border-slate-700 px-4 py-2 rounded-sm">
                  <Star className="h-5 w-5 text-lime" />
                  <span className="text-slate-300 text-sm">{tr('5-Star Rated', '5-स्टार रेटिंग')}</span>
                </div>
              </div>
            </div>

            {/* About Image Grid */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-4">
                <img 
                  src="https://images.unsplash.com/photo-1619659085985-f51a00f0160a?crop=entropy&cs=srgb&fm=jpg&w=400&q=80" 
                  alt={tr('Private Jet', 'प्राइवेट जेट')} 
                  className="rounded-sm w-full h-48 object-cover"
                />
                <img 
                  src="https://images.unsplash.com/photo-1625513123245-fcb02d69ad12?crop=entropy&cs=srgb&fm=jpg&w=400&q=80" 
                  alt={tr('Luxury Interior', 'शानदार इंटीरियर')} 
                  className="rounded-sm w-full h-64 object-cover"
                />
              </div>
              <div className="space-y-4 pt-8">
                <img 
                  src="https://images.unsplash.com/photo-1782865423531-27f6fab92fe8?crop=entropy&cs=srgb&fm=jpg&w=400&q=80" 
                  alt={tr('Helicopter', 'हेलीकॉप्टर')} 
                  className="rounded-sm w-full h-64 object-cover"
                />
                <img 
                  src="https://images.unsplash.com/photo-1474302770737-173ee21bab63?crop=entropy&cs=srgb&fm=jpg&w=400&q=80" 
                  alt={tr('Aircraft', 'विमान')} 
                  className="rounded-sm w-full h-48 object-cover"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-6 bg-slate-900" data-testid="features-section">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-4xl font-bold text-white text-center mb-12" data-testid="features-title">
            {t('landing.whyChoose')}
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="glass p-8 rounded-lg text-center hover:scale-105 transition-transform">
              <Shield className="h-12 w-12 text-lime mb-4 mx-auto" />
              <h3 className="text-2xl font-bold text-white mb-3">{t('landing.verifiedOperators')}</h3>
              <p className="text-slate-400">
                {t('landing.verifiedOperatorsDesc')}
              </p>
            </div>
            <div className="glass p-8 rounded-lg text-center hover:scale-105 transition-transform">
              <Users className="h-12 w-12 text-lime mb-4 mx-auto" />
              <h3 className="text-2xl font-bold text-white mb-3">{t('landing.multipleOptions')}</h3>
              <p className="text-slate-400">
                {t('landing.multipleOptionsDesc')}
              </p>
            </div>
            <div className="glass p-8 rounded-lg text-center hover:scale-105 transition-transform">
              <TrendingUp className="h-12 w-12 text-lime mb-4 mx-auto" />
              <h3 className="text-2xl font-bold text-white mb-3">{t('landing.transparentPricing')}</h3>
              <p className="text-slate-400">
                {t('landing.transparentPricingDesc')}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Products Section */}
      <section className="py-20 px-6 bg-slate-950" data-testid="products-section">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold text-white mb-4">{t('landing.products')}</h2>
            <p className="text-slate-400 text-lg">{tr('Complete aviation solutions for every stakeholder', 'हर हितधारक के लिए संपूर्ण विमानन समाधान')}</p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Corporate Card */}
            <div className="bg-slate-800 p-8 rounded-sm border border-slate-700 hover:border-lime/50 transition-colors group">
              <div className="bg-slate-900 border border-slate-700 p-4 rounded-sm w-fit mb-6">
                <Building2 className="h-10 w-10 text-lime" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">{t('landing.corporateSolutions')}</h3>
              <p className="text-slate-400 mb-6">
                {t('landing.corporateDesc')}
              </p>
              <ul className="space-y-2 mb-6">
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {t('landing.dedicatedManager')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {t('landing.volumeDiscounts')}
                </li>
                <li className="flex items-center gap-2 text-slate-300 text-sm">
                  <CheckCircle className="h-4 w-4 text-lime" /> {t('landing.travelAnalytics')}
                </li>
              </ul>
              <Link to="/corporate">
                <Button className="w-full bg-slate-700 hover:bg-slate-600 text-white rounded-sm" data-testid="explore-corporate-btn">
                  {t('landing.corporateRegistration')}
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <TestimonialsSlider />

      {/* Investor Interest Section */}
      <InvestorInterestSection />

      {/* CTA Section */}
      <section className="py-20 px-6 bg-lime" data-testid="cta-section">
        <div className="max-w-4xl mx-auto text-center space-y-6">
          <h2 className="text-5xl font-black text-black" data-testid="cta-title">
            {t('landing.readyTakeOff')}
          </h2>
          <p className="text-xl text-black/80">
            {t('landing.ctaSubtitle')}
          </p>
          <Link to="/booking">
            <Button size="lg" className="bg-slate-900 hover:bg-slate-800 text-white text-lg px-12 py-6 rounded-sm" data-testid="cta-book-btn">
              {t('landing.startBooking')}
            </Button>
          </Link>
        </div>
      </section>

      {/* Contact Section */}
      <section id="contact" className="py-20 px-6 bg-slate-900" data-testid="contact-section">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <span className="ay-overline">{tr('Contact Us', 'संपर्क करें')}</span>
            <h2 className="text-4xl font-bold text-white mt-3 mb-4">{tr('Get In Touch', 'हमसे जुड़ें')}</h2>
            <p className="text-slate-400">{tr('We are here to help with all your aviation needs', 'आपकी सभी विमानन ज़रूरतों में मदद के लिए हम यहां हैं')}</p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Address Card */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-sm p-6 text-center hover:border-lime/50 transition-colors">
              <div className="bg-slate-900 border border-slate-700 p-3 rounded-sm w-fit mx-auto mb-4">
                <MapPin className="h-6 w-6 text-lime" />
              </div>
              <h3 className="text-white font-semibold mb-2">{tr('Head Office', 'मुख्य कार्यालय')}</h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                {COMPANY_INFO.address}
              </p>
            </div>

            {/* Email Card */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-sm p-6 text-center hover:border-lime/50 transition-colors">
              <div className="bg-slate-900 border border-slate-700 p-3 rounded-sm w-fit mx-auto mb-4">
                <Mail className="h-6 w-6 text-lime" />
              </div>
              <h3 className="text-white font-semibold mb-2">{tr('Email Us', 'ईमेल करें')}</h3>
              <a href={`mailto:${COMPANY_INFO.email}`} className="text-amber hover:text-amber/80 text-sm">
                {COMPANY_INFO.email}
              </a>
            </div>

            {/* Phone Card */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-sm p-6 text-center hover:border-lime/50 transition-colors">
              <div className="bg-slate-900 border border-slate-700 p-3 rounded-sm w-fit mx-auto mb-4">
                <Phone className="h-6 w-6 text-lime" />
              </div>
              <h3 className="text-white font-semibold mb-2">{tr('Call Us', 'कॉल करें')}</h3>
              <a href={`tel:${COMPANY_INFO.phone}`} className="text-amber hover:text-amber/80 text-sm">
                {COMPANY_INFO.phone}
              </a>
            </div>

            {/* Hours Card */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-sm p-6 text-center hover:border-lime/50 transition-colors">
              <div className="bg-slate-900 border border-slate-700 p-3 rounded-sm w-fit mx-auto mb-4">
                <Clock className="h-6 w-6 text-lime" />
              </div>
              <h3 className="text-white font-semibold mb-2">{tr('Working Hours', 'कार्य समय')}</h3>
              <p className="text-slate-400 text-sm">
                {COMPANY_INFO.hours}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Premium Footer */}
      <footer className="bg-slate-950 py-16 px-6 border-t border-slate-800">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-5 gap-8 mb-12">
            {/* Brand */}
            <div className="col-span-2 md:col-span-1">
              <div className="flex items-center space-x-2 mb-4">
                <Plane className="h-8 w-8 text-lime" />
                <span className="text-2xl font-bold text-white">AirYatra</span>
              </div>
              <p className="text-slate-400 text-sm mb-4">
                {tr("India's Premier Aviation Operating System. Connecting travelers with verified charter operators.", 'भारत का प्रमुख विमानन ऑपरेटिंग सिस्टम। यात्रियों को सत्यापित चार्टर ऑपरेटरों से जोड़ता है।')}
              </p>
              <div className="flex gap-3">
                <a href="https://www.facebook.com/profile.php?id=61592460343465" target="_blank" rel="noopener noreferrer" className="bg-slate-800 p-2 rounded-lg hover:bg-slate-700 transition-colors" aria-label="Facebook">
                  <svg className="h-5 w-5 text-slate-400" fill="currentColor" viewBox="0 0 24 24"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
                </a>
                <a href="https://www.instagram.com/airyatra_official/?hl=en" target="_blank" rel="noopener noreferrer" className="bg-slate-800 p-2 rounded-lg hover:bg-slate-700 transition-colors" aria-label="Instagram">
                  <svg className="h-5 w-5 text-slate-400" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
                </a>
                <a href="https://x.com/AirYatraoffical" target="_blank" rel="noopener noreferrer" className="bg-slate-800 p-2 rounded-lg hover:bg-slate-700 transition-colors" aria-label="Twitter">
                  <svg className="h-5 w-5 text-slate-400" fill="currentColor" viewBox="0 0 24 24"><path d="M24 4.557c-.883.392-1.832.656-2.828.775 1.017-.609 1.798-1.574 2.165-2.724-.951.564-2.005.974-3.127 1.195-.897-.957-2.178-1.555-3.594-1.555-3.179 0-5.515 2.966-4.797 6.045-4.091-.205-7.719-2.165-10.148-5.144-1.29 2.213-.669 5.108 1.523 6.574-.806-.026-1.566-.247-2.229-.616-.054 2.281 1.581 4.415 3.949 4.89-.693.188-1.452.232-2.224.084.626 1.956 2.444 3.379 4.6 3.419-2.07 1.623-4.678 2.348-7.29 2.04 2.179 1.397 4.768 2.212 7.548 2.212 9.142 0 14.307-7.721 13.995-14.646.962-.695 1.797-1.562 2.457-2.549z"/></svg>
                </a>
                <a href="https://www.linkedin.com/in/airyatra-offical-704677426/" target="_blank" rel="noopener noreferrer" className="bg-slate-800 p-2 rounded-lg hover:bg-slate-700 transition-colors" aria-label="LinkedIn">
                  <svg className="h-5 w-5 text-slate-400" fill="currentColor" viewBox="0 0 24 24"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/></svg>
                </a>
              </div>
            </div>

            {/* Quick Links */}
            <div>
              <h4 className="text-white font-semibold mb-4">{tr('Quick Links', 'त्वरित लिंक')}</h4>
              <ul className="space-y-2">
                <li><Link to="/booking" className="text-slate-400 hover:text-lime text-sm transition-colors">{tr('Book a Flight', 'उड़ान बुक करें')}</Link></li>
                <li><Link to="/corporate" className="text-slate-400 hover:text-lime text-sm transition-colors">{tr('Corporate Solutions', 'कॉर्पोरेट समाधान')}</Link></li>
                <li><a href="#services" className="text-slate-400 hover:text-lime text-sm transition-colors">{tr('Our Services', 'हमारी सेवाएं')}</a></li>
              </ul>
            </div>

            {/* Support */}
            <div>
              <h4 className="text-white font-semibold mb-4">{tr('Support', 'सहायता')}</h4>
              <ul className="space-y-2">
                <li><a href="#contact" className="text-slate-400 hover:text-lime text-sm transition-colors">{tr('Help Center', 'सहायता केंद्र')}</a></li>
                <li><Link to="/about" className="text-slate-400 hover:text-lime text-sm transition-colors">{tr('Safety Guidelines', 'सुरक्षा दिशानिर्देश')}</Link></li>
                <li><a href="mailto:care@airyatra.co.in" className="text-slate-400 hover:text-lime text-sm transition-colors">{tr('Contact Support', 'सहायता से संपर्क करें')}</a></li>
              </ul>
            </div>

            {/* Legal */}
            <div>
              <h4 className="text-white font-semibold mb-4">{bi("Legal / कानूनी")}</h4>
              <ul className="space-y-2">
                <li><Link to="/legal/terms" className="text-slate-400 hover:text-lime text-sm transition-colors">{bi("Terms & Conditions / नियम एवं शर्तें")}</Link></li>
                <li><Link to="/legal/privacy" className="text-slate-400 hover:text-lime text-sm transition-colors">{bi("Privacy Policy / गोपनीयता नीति")}</Link></li>
                <li><Link to="/legal/cancellation" className="text-slate-400 hover:text-lime text-sm transition-colors">{bi("Refund & Cancellation / धनवापसी और रद्दीकरण")}</Link></li>
              </ul>
            </div>

            {/* Contact */}
            <div>
              <h4 className="text-white font-semibold mb-4">{tr('Contact', 'संपर्क')}</h4>
              <ul className="space-y-3">
                <li className="flex items-start gap-2">
                  <MapPin className="h-4 w-4 text-lime mt-1 flex-shrink-0" />
                  <span className="text-slate-400 text-sm">{COMPANY_INFO.address}</span>
                </li>
                <li className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-lime flex-shrink-0" />
                  <a href={`mailto:${COMPANY_INFO.email}`} className="text-slate-400 hover:text-lime text-sm transition-colors">
                    {COMPANY_INFO.email}
                  </a>
                </li>
                <li className="flex items-center gap-2">
                  <Phone className="h-4 w-4 text-lime flex-shrink-0" />
                  <a href={`tel:${COMPANY_INFO.phone}`} className="text-slate-400 hover:text-lime text-sm transition-colors">
                    {COMPANY_INFO.phone}
                  </a>
                </li>
              </ul>
            </div>
          </div>

          {/* Bottom Bar */}
          <div className="border-t border-slate-800 pt-8">
            {/* Legal Links Row */}
            <div className="flex flex-wrap justify-center gap-4 mb-4 text-xs">
              <Link to="/legal/terms" className="text-slate-500 hover:text-lime transition-colors">{tr('Terms & Conditions', 'नियम और शर्तें')}</Link>
              <span className="text-slate-700">|</span>
              <Link to="/legal/privacy" className="text-slate-500 hover:text-lime transition-colors">{tr('Privacy Policy', 'गोपनीयता नीति')}</Link>
              <span className="text-slate-700">|</span>
              <Link to="/legal/cancellation" className="text-slate-500 hover:text-lime transition-colors">{tr('Refund & Cancellation Policy', 'रिफंड और रद्दीकरण नीति')}</Link>
            </div>
            
            {/* Copyright Row */}
            <div className="flex flex-col md:flex-row justify-between items-center gap-4">
              <p className="text-slate-500 text-sm">
                {tr("© 2026 Lucuma Corporation Pvt. Ltd. (AirYatra). All rights reserved. India's Premier Aviation Platform.", '© 2026 Lucuma Corporation Pvt. Ltd. (AirYatra). सर्वाधिकार सुरक्षित। भारत का प्रमुख विमानन प्लेटफ़ॉर्म।')}
              </p>
              <div className="flex items-center gap-4">
                <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Visa_Inc._logo.svg/100px-Visa_Inc._logo.svg.png" alt="Visa" className="h-6 opacity-60" />
                <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/Mastercard-logo.svg/100px-Mastercard-logo.svg.png" alt="Mastercard" className="h-6 opacity-60" />
                <span className="text-slate-600 text-xs">{tr('Secure Payments', 'सुरक्षित भुगतान')}</span>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage;
