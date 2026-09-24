import React, { useState, useEffect } from 'react';
import { Menu, X, ArrowUpRight } from 'lucide-react';

interface NavbarProps {
  onBookDemo: () => void;
  onLogin: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onBookDemo, onLogin }) => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navLinks = [
    { label: 'Platform', href: '#platform' },
    { label: 'Use cases', href: '#use-cases' },
    { label: 'Security', href: '#security' },
    { label: 'Pricing', href: '#pricing' },
    { label: 'Company', href: '#why-firstlook' },
  ];

  return (
    <>
      <header
        className={`fixed top-4 sm:top-5 left-1/2 -translate-x-1/2 z-50 w-[94%] max-w-4xl transition-all duration-300 ${
          isScrolled ? 'top-3 shadow-[0_8px_30px_rgba(0,0,0,0.08)]' : 'shadow-[0_2px_16px_rgba(0,0,0,0.04)]'
        }`}
      >
        <div className="bg-[#FAF8F5]/90 backdrop-blur-md border border-[#E5E2DC] rounded-full px-4 sm:px-5 py-2.5 flex items-center justify-between">
          {/* Brand Wordmark with Firstlook target logo */}
          <a
            href="#"
            className="flex items-center gap-2.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 rounded-full group"
          >
            {/* Orange circular aperture / target icon from PDF */}
            <span className="relative flex items-center justify-center w-5 h-5 rounded-full border-[2.2px] border-[#F97316] group-hover:scale-105 transition-transform">
              <span className="w-1.5 h-1.5 rounded-full bg-[#F97316]"></span>
            </span>
            <span className="font-extrabold text-[17px] tracking-tight text-[#111317]">
              Firstlook
            </span>
          </a>

          {/* Navigation links (Desktop) */}
          <nav className="hidden md:flex items-center gap-6 lg:gap-7">
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="text-sm font-medium text-neutral-600 hover:text-neutral-950 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 rounded-sm"
              >
                {link.label}
              </a>
            ))}
          </nav>

          {/* Actions: Log in + Book a demo */}
          <div className="hidden sm:flex items-center gap-3">
            <button
              onClick={onLogin}
              className="text-sm font-medium text-neutral-700 hover:text-neutral-950 px-2.5 py-1.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 rounded-full"
            >
              Log in
            </button>
            <button
              onClick={onBookDemo}
              className="bg-[#101216] hover:bg-[#232731] text-white text-sm font-medium px-4.5 py-2 rounded-full transition-all duration-200 shadow-sm hover:shadow active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 whitespace-nowrap"
            >
              Book a demo
            </button>
          </div>

          {/* Mobile hamburger button */}
          <div className="flex sm:hidden items-center gap-2">
            <button
              onClick={onBookDemo}
              className="bg-[#101216] text-white text-xs font-medium px-3 py-1.5 rounded-full whitespace-nowrap"
            >
              Demo
            </button>
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-1.5 text-neutral-700 hover:text-neutral-900 rounded-full hover:bg-neutral-200/60 transition-colors"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-40 bg-neutral-950/40 backdrop-blur-sm md:hidden animate-in fade-in">
          <div className="absolute top-20 left-4 right-4 bg-[#FAF8F5] border border-[#E5E2DC] rounded-3xl p-6 shadow-2xl flex flex-col gap-4">
            <div className="flex flex-col gap-3">
              {navLinks.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className="text-base font-semibold text-neutral-800 hover:text-neutral-950 py-2 border-b border-neutral-200/60 flex items-center justify-between"
                >
                  <span>{link.label}</span>
                  <ArrowUpRight className="w-4 h-4 text-neutral-400" />
                </a>
              ))}
            </div>
            <div className="pt-2 flex flex-col gap-2.5">
              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  onLogin();
                }}
                className="w-full py-2.5 text-sm font-semibold text-neutral-800 bg-white border border-neutral-300 rounded-full"
              >
                Log in
              </button>
              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  onBookDemo();
                }}
                className="w-full py-2.5 text-sm font-semibold text-white bg-[#101216] rounded-full"
              >
                Book a demo
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
