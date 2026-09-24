import React from 'react';
import { Check, Sparkles, ArrowRight } from 'lucide-react';

interface PricingSectionProps {
  onApplyDesignPartner: () => void;
  onBookDemo: () => void;
}

export const PricingSection: React.FC<PricingSectionProps> = ({
  onApplyDesignPartner,
  onBookDemo,
}) => {
  return (
    <section id="pricing" className="py-24 sm:py-32 bg-[#FAF8F5] border-t border-neutral-200">
      <div className="max-w-6xl mx-auto px-6">
        {/* Header */}
        <div className="max-w-3xl mb-16">
          <div className="text-xs font-semibold uppercase tracking-widest text-amber-700 mb-3">
            Investment & Access
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-[#111317] tracking-tight mb-5 leading-tight text-balance">
            Transparent fund partnership tiers.
          </h2>
          <p className="text-lg text-neutral-600 leading-relaxed font-normal">
            Whether participating as an early design-partner fund or scaling across a multi-stage firm, Firstlook scales with your fund size.
          </p>
        </div>

        {/* 3 Tier Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-stretch">
          {/* Tier 1: Design Partner */}
          <div className="p-8 rounded-3xl bg-white border-2 border-amber-400 shadow-sm flex flex-col justify-between relative">
            <div className="absolute -top-3.5 left-8 bg-amber-500 text-neutral-950 font-bold text-xs px-3 py-1 rounded-full uppercase tracking-wider">
              Now Onboarding
            </div>

            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-amber-800 mb-2">
                Cohort 2
              </div>
              <h3 className="text-2xl font-bold text-neutral-900 mb-2">
                Design Partner
              </h3>
              <p className="text-sm text-neutral-600 mb-6 leading-relaxed">
                For active seed and Series A funds ready to replace manual CRM friction and shape the AI infrastructure roadmap.
              </p>

              <div className="mb-6 pb-6 border-b border-neutral-200">
                <span className="text-4xl font-extrabold text-neutral-900">Custom</span>
                <span className="text-neutral-500 text-sm ml-2">/ pilot agreement</span>
              </div>

              <ul className="space-y-3 mb-8 text-xs sm:text-sm text-neutral-700">
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>White-glove CRM & data migration</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>Full relationship intelligence graph</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>Diligence copilot with cited memos</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>Weekly advisory sync with founders</span>
                </li>
              </ul>
            </div>

            <button
              onClick={onApplyDesignPartner}
              className="w-full py-3 px-4 rounded-full bg-neutral-900 hover:bg-neutral-800 text-white font-semibold text-sm transition-all duration-200 text-center"
            >
              Apply for Cohort 2
            </button>
          </div>

          {/* Tier 2: Standard Fund */}
          <div className="p-8 rounded-3xl bg-white border border-neutral-300/80 shadow-sm flex flex-col justify-between">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-2">
                Seed to Series B
              </div>
              <h3 className="text-2xl font-bold text-neutral-900 mb-2">
                Core Fund
              </h3>
              <p className="text-sm text-neutral-600 mb-6 leading-relaxed">
                For established investment teams seeking autonomous sourcing radar, memo automation, and portfolio runway alerting.
              </p>

              <div className="mb-6 pb-6 border-b border-neutral-200">
                <span className="text-4xl font-extrabold text-neutral-900">$1,500</span>
                <span className="text-neutral-500 text-sm ml-2">/ month billed annually</span>
              </div>

              <ul className="space-y-3 mb-8 text-xs sm:text-sm text-neutral-700">
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>Up to 10 partner & associate seats</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>Continuous thesis-driven sourcing</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>Portfolio KPI intake portal</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>Slack & email proactive digests</span>
                </li>
              </ul>
            </div>

            <button
              onClick={onBookDemo}
              className="w-full py-3 px-4 rounded-full bg-neutral-100 hover:bg-neutral-200 text-neutral-900 font-semibold text-sm transition-all duration-200 text-center"
            >
              Book a demo
            </button>
          </div>

          {/* Tier 3: Enterprise / Multi-Stage */}
          <div className="p-8 rounded-3xl bg-neutral-950 text-white border border-neutral-800 shadow-xl flex flex-col justify-between">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-amber-400 mb-2">
                Institutional
              </div>
              <h3 className="text-2xl font-bold text-white mb-2">
                Private Cloud
              </h3>
              <p className="text-sm text-neutral-300 mb-6 leading-relaxed">
                For multi-stage funds requiring isolated VPC deployment, custom MCP servers, and strict multi-jurisdiction compliance.
              </p>

              <div className="mb-6 pb-6 border-b border-neutral-800">
                <span className="text-4xl font-extrabold text-white">Custom</span>
                <span className="text-neutral-400 text-sm ml-2">/ annual contract</span>
              </div>

              <ul className="space-y-3 mb-8 text-xs sm:text-sm text-neutral-300">
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <span>Single-tenant VPC deployment (AWS/GCP)</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <span>Custom Model Context Protocol (MCP) server</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <span>Bring-your-own encryption keys (BYOK)</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <span>24/7 dedicated engineering SLA</span>
                </li>
              </ul>
            </div>

            <button
              onClick={onBookDemo}
              className="w-full py-3 px-4 rounded-full bg-white hover:bg-neutral-100 text-neutral-900 font-semibold text-sm transition-all duration-200 text-center"
            >
              Contact Enterprise
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};
