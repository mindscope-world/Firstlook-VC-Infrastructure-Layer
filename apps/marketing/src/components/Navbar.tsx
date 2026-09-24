import React, { useState, useEffect } from 'react';
import { Menu, X, ArrowUpRight } from 'lucide-react';
import { Wordmark } from './Logo';

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
        className={`fixed left-1/2 z-50 w-[calc(100%-32px)] max-w-[860px] -translate-x-1/2 transition-all duration-300 ${
          isScrolled ? 'top-3' : 'top-[30px]'
        }`}
      >
        <div className="flex h-[64px] items-center justify-between rounded-full bg-[#FBFCFD]/95 pl-6 pr-2.5 shadow-[0_12px_40px_rgba(16,19,26,0.08),0_1px_2px_rgba(16,19,26,0.04)] backdrop-blur-md">
          <a href="#" className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E7893A]">
            <Wordmark />
          </a>

          <nav className="hidden md:flex items-center gap-[30px]">
            {navLinks.map((link, i) => (
              <a
                key={link.label}
                href={link.href}
                className={`text-[16px] font-medium transition-colors hover:text-[#10131A] ${
                  i === 0 ? 'text-[#10131A]' : 'text-[#55565e]'
                }`}
              >
                {link.label}
              </a>
            ))}
          </nav>

          <div className="hidden sm:flex items-center gap-5">
            <button onClick={onLogin} className="text-[16px] font-medium text-[#10131A] hover:opacity-70">
              Log in
            </button>
            <button
              onClick={onBookDemo}
              className="h-[46px] rounded-full bg-[#10131A] px-6 text-[16px] font-medium text-white transition hover:bg-[#262a33] active:scale-95"
            >
              Book a demo
            </button>
          </div>

          <div className="flex sm:hidden items-center gap-2">
            <button onClick={onBookDemo} className="rounded-full bg-[#10131A] px-3.5 py-2 text-xs font-medium text-white">
              Demo
            </button>
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="rounded-full p-1.5 text-neutral-700 hover:bg-neutral-200/60"
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
