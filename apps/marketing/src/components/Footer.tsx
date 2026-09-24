import React from 'react';
import { ArrowUp } from 'lucide-react';

export const Footer: React.FC = () => {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <footer className="bg-[#FAF8F5] border-t border-neutral-300 py-16 text-neutral-600">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-10 pb-12 border-b border-neutral-200">
          {/* Brand & Mission (5 cols) */}
          <div className="md:col-span-5">
            <div className="flex items-center gap-2.5 mb-4">
              <span className="relative flex items-center justify-center w-5 h-5 rounded-full border-[2.2px] border-[#F97316]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#F97316]" />
              </span>
              <span className="font-extrabold text-lg tracking-tight text-neutral-900">
                Firstlook
              </span>
            </div>
            <p className="text-sm text-neutral-600 leading-relaxed max-w-sm font-normal mb-4">
              The AI infrastructure layer for venture firms. Sourcing, diligence and portfolio intelligence unified into one living graph.
            </p>
            <div className="text-xs text-neutral-500 font-mono">
              Nairobi · London · San Francisco
            </div>
          </div>

          {/* Links Column 1: Platform (2 cols) */}
          <div className="md:col-span-2">
            <div className="text-xs font-bold uppercase tracking-wider text-neutral-900 mb-3">
              Platform
            </div>
            <ul className="space-y-2 text-sm">
              <li><a href="#platform" className="hover:text-neutral-950 transition-colors">Relationship Graph</a></li>
              <li><a href="#platform" className="hover:text-neutral-950 transition-colors">Thesis Sourcing</a></li>
              <li><a href="#platform" className="hover:text-neutral-950 transition-colors">Diligence Copilot</a></li>
              <li><a href="#platform" className="hover:text-neutral-950 transition-colors">Portfolio Monitor</a></li>
              <li><a href="#platform" className="hover:text-neutral-950 transition-colors">LP Reporting</a></li>
            </ul>
          </div>

          {/* Links Column 2: Roles (2 cols) */}
          <div className="md:col-span-2">
            <div className="text-xs font-bold uppercase tracking-wider text-neutral-900 mb-3">
              Workflows
            </div>
            <ul className="space-y-2 text-sm">
              <li><a href="#use-cases" className="hover:text-neutral-950 transition-colors">General Partners</a></li>
              <li><a href="#use-cases" className="hover:text-neutral-950 transition-colors">Investment Team</a></li>
              <li><a href="#use-cases" className="hover:text-neutral-950 transition-colors">Platform & Operations</a></li>
              <li><a href="#use-cases" className="hover:text-neutral-950 transition-colors">Finance & IR</a></li>
              <li><a href="#security" className="hover:text-neutral-950 transition-colors">Security Architecture</a></li>
            </ul>
          </div>

          {/* Links Column 3: Trust & Legal (3 cols) */}
          <div className="md:col-span-3">
            <div className="text-xs font-bold uppercase tracking-wider text-neutral-900 mb-3">
              Compliance & Trust
            </div>
            <ul className="space-y-2 text-sm">
              <li><span className="text-neutral-700 font-medium">GDPR & Kenya DPA Compliant</span></li>
              <li><span className="text-neutral-700 font-medium">Isolated Tenant Enclaves</span></li>
              <li><span className="text-neutral-700 font-medium">Zero-Retention LLM Contracts</span></li>
              <li><a href="#security" className="hover:text-neutral-950 underline underline-offset-2 transition-colors">Security Whitepaper</a></li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-neutral-500">
          <div>
            © {new Date().getFullYear()} Firstlook Systems, Inc. All rights reserved.
          </div>

          <div className="flex items-center gap-6">
            <a href="#" className="hover:text-neutral-800 transition-colors">Privacy Notice</a>
            <a href="#" className="hover:text-neutral-800 transition-colors">Terms of Service</a>
            <button
              onClick={scrollToTop}
              className="flex items-center gap-1 hover:text-neutral-900 transition-colors cursor-pointer"
            >
              <span>Back to top</span>
              <ArrowUp className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
};
