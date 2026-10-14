import React from 'react';
import { Link } from 'react-router-dom';
import { Plane, Home, ArrowLeft, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { bi, tr } from '../lib/bilingual';

function NotFoundPage() {
  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center px-6">
      {/* Logo */}
      <div className="flex items-center gap-2 mb-8">
        <Plane className="h-10 w-10 text-lime" />
        <span className="text-3xl font-bold text-white">AirYatra</span>
      </div>

      {/* 404 Animation */}
      <div className="relative mb-8">
        <h1 className="text-[150px] font-black text-slate-800 leading-none">404</h1>
        <div className="absolute inset-0 flex items-center justify-center">
          <Plane className="h-20 w-20 text-lime animate-bounce" />
        </div>
      </div>

      {/* Message */}
      <h2 className="text-3xl font-bold text-white mb-4 text-center">
        {bi("Page Not Found / पेज नहीं मिला")}
      </h2>
      <p className="text-slate-400 text-center max-w-md mb-8">
        {tr("The page you're looking for doesn't exist or has been moved. Let's get you back on track!", 'आप जो पेज ढूंढ रहे हैं वह मौजूद नहीं है या हटा दिया गया है। चलिए आपको सही राह पर लाते हैं!')}
      </p>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-4">
        <Link to="/">
          <Button className="bg-lime text-black hover:bg-lime/90 min-w-[180px]" data-testid="home-btn">
            <Home className="mr-2 h-5 w-5" />
            {tr('Go Home', 'होम पर जाएं')}
          </Button>
        </Link>
        <Link to="/booking">
          <Button variant="outline" className="border-slate-600 text-white hover:bg-slate-800 min-w-[180px]" data-testid="book-flight-btn">
            <Plane className="mr-2 h-5 w-5" />
            {tr('Book a Flight', 'उड़ान बुक करें')}
          </Button>
        </Link>
      </div>

      {/* Quick Links */}
      <div className="mt-12 text-center">
        <p className="text-slate-500 text-sm mb-4">{bi("Quick Links / त्वरित लिंक")}</p>
        <div className="flex flex-wrap justify-center gap-4">
          <Link to="/services" className="text-lime hover:text-lime/80 text-sm">
            {tr('Services', 'सेवाएं')}
          </Link>
          <Link to="/fleet" className="text-lime hover:text-lime/80 text-sm">
            {tr('Fleet', 'बेड़ा')}
          </Link>
          <Link to="/blog" className="text-lime hover:text-lime/80 text-sm">
            {tr('Blog', 'ब्लॉग')}
          </Link>
          <Link to="/about" className="text-lime hover:text-lime/80 text-sm">
            {tr('About Us', 'हमारे बारे में')}
          </Link>
        </div>
      </div>
    </div>
  );
}

export default NotFoundPage;
