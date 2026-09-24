import React, { useState } from 'react';
import { UserCheck, Sparkles, Check, ArrowRight, Shield, BarChart3, LineChart, FileText } from 'lucide-react';

export const WhoItsForSection: React.FC = () => {
  const [activeRole, setActiveRole] = useState<number>(0);

  const roles = [
    {
      role: 'Partners',
      headline: 'A live pipeline view, IC-ready briefs and relationship insight',
      description:
        'Stop walking into partner meetings relying on memory or outdated sheets. See network relationship temperature, warm intro paths, and IC-ready executive memos on demand.',
      highlights: [
        'Instant relationship strength scores before every meeting',
        'Concise IC-ready briefs with verifiable source citations',
        'Zero manual CRM logging required from your day'
      ],
      previewSnippet: {
        title: 'Partner Intelligence Dossier',
        deal: 'NexaFlow AI (Series A)',
        status: 'Term Sheet Stage',
        relationship: '94% warmth · 2 co-founders known by Marcus V.',
        action: 'Recommended Allocation: $3.0M'
      }
    },
    {
      role: 'Associates',
      headline: 'Less data entry, faster screening and memo drafts in hours',
      description:
        'Spend your energy on high-judgment conviction rather than transcribing tables. Drop in a data room to receive auto-extracted ARR metrics, cap table models, and drafted memos.',
      highlights: [
        'First-draft investment memos formatted in your firm’s template',
        'Automatic cross-checking of deck claims against financial models',
        'Screen 5x more companies without burnout'
      ],
      previewSnippet: {
        title: 'Diligence Extraction Matrix',
        deal: 'OmniChain Logistics (Seed)',
        status: 'Memo Drafted in 42 mins',
        relationship: 'Deck vs Stripe CSV verified · 1 discrepancy flagged',
        action: 'Export to IC Template →'
      }
    },
    {
      role: 'Platform teams',
      headline: 'Automated KPI collection and portfolio alerts',
      description:
        'Say goodbye to endless email reminders chasing quarterly updates. Founders submit their numbers via a friction-free portal, and Firstlook flags short runway before board meetings.',
      highlights: [
        'Automated founder KPI intake with multi-currency conversion',
        'Early warnings on cash burn, key talent departures, and hiring stops',
        'Cross-portfolio benchmarking across cohort stages'
      ],
      previewSnippet: {
        title: 'Portfolio Health Monitor',
        deal: '32 Active Seed Portfolio Companies',
        status: '96% Q3 KPI Submission Rate',
        relationship: '2 companies flagged with < 6 months runway',
        action: 'Prepare Board Briefing Pack →'
      }
    },
    {
      role: 'Finance and IR',
      headline: 'LP reports and fund metrics without the spreadsheet scramble',
      description:
        'Generate quarterly LP letters, TVPI, DPI, and gross/net IRR calculations directly from verified portfolio records. No manual reconciliation errors or broken VLOOKUPs.',
      highlights: [
        'Automated LP quarterly letter drafts with fund metrics',
        'Real-time valuation models based on verified round closings',
        'Audit-ready logs compliant with LP institutional standards'
      ],
      previewSnippet: {
        title: 'Fund II Performance Overview',
        deal: '$75M Seed Fund',
        status: 'Net TVPI: 2.18x · Net IRR: 32.4%',
        relationship: 'Audited against bank cash flows & cap tables',
        action: 'Generate Q3 LP Letter Draft →'
      }
    }
  ];

  const currentRole = roles[activeRole];

  return (
    <section id="use-cases" className="py-24 sm:py-32 bg-[#FAF8F5] border-t border-neutral-200">
      <div className="max-w-6xl mx-auto px-6">
        {/* Header */}
        <div className="max-w-3xl mb-16">
          <div className="text-xs font-semibold uppercase tracking-widest text-amber-700 mb-3">
            Tailored Workflows
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-[#111317] tracking-tight mb-5 leading-tight text-balance">
            Engineered for every seat at the table.
          </h2>
          <p className="text-lg text-neutral-600 leading-relaxed font-normal">
            Whether leading the investment committee or reconciling fund cash flows, Firstlook amplifies your team's throughput.
          </p>
        </div>

        {/* Role Tab Navigation */}
        <div className="flex flex-wrap gap-2 p-1.5 bg-[#EBE7DF] rounded-2xl mb-10 max-w-2xl border border-neutral-300/80">
          {roles.map((r, idx) => (
            <button
              key={r.role}
              onClick={() => setActiveRole(idx)}
              className={`px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all duration-200 cursor-pointer ${
                activeRole === idx
                  ? 'bg-white text-neutral-900 shadow-sm border border-neutral-200'
                  : 'text-neutral-600 hover:text-neutral-950 hover:bg-white/40'
              }`}
            >
              {r.role}
            </button>
          ))}
        </div>

        {/* Active Role Content Card */}
        <div className="bg-white rounded-3xl border border-neutral-300/80 shadow-sm p-8 sm:p-10 lg:p-12">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
            {/* Left side: Role details */}
            <div className="lg:col-span-7">
              <div className="text-xs font-semibold uppercase tracking-wider text-amber-700 mb-2 font-mono">
                Role: {currentRole.role}
              </div>
              <h3 className="text-2xl sm:text-3xl font-bold text-neutral-900 mb-4 tracking-tight leading-tight">
                {currentRole.headline}
              </h3>
              <p className="text-base text-neutral-600 leading-relaxed mb-6 font-normal">
                {currentRole.description}
              </p>

              <div className="space-y-3">
                {currentRole.highlights.map((h, i) => (
                  <div key={i} className="flex items-start gap-3 text-sm text-neutral-800">
                    <div className="w-5 h-5 rounded-full bg-amber-100 flex items-center justify-center shrink-0 mt-0.5">
                      <Check className="w-3.5 h-3.5 text-amber-700" />
                    </div>
                    <span>{h}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Right side: Interactive snapshot */}
            <div className="lg:col-span-5 bg-[#FAF9F5] rounded-2xl border border-neutral-200 p-6 shadow-inner">
              <div className="flex items-center justify-between pb-3 mb-4 border-b border-neutral-200 text-xs">
                <span className="font-semibold text-neutral-500 uppercase tracking-wider">
                  {currentRole.previewSnippet.title}
                </span>
                <span className="text-amber-700 font-mono text-[11px] bg-amber-100/70 px-2 py-0.5 rounded">
                  Live View
                </span>
              </div>

              <div className="space-y-4">
                <div>
                  <div className="text-xs text-neutral-400 font-medium">Active Context</div>
                  <div className="text-lg font-bold text-neutral-900">{currentRole.previewSnippet.deal}</div>
                </div>

                <div className="p-3 bg-white rounded-xl border border-neutral-200">
                  <div className="text-xs text-neutral-400 mb-1">Status</div>
                  <div className="text-sm font-semibold text-emerald-700">{currentRole.previewSnippet.status}</div>
                </div>

                <div className="p-3 bg-white rounded-xl border border-neutral-200">
                  <div className="text-xs text-neutral-400 mb-1">Intelligence Insight</div>
                  <div className="text-xs text-neutral-700 leading-relaxed">{currentRole.previewSnippet.relationship}</div>
                </div>

                <div className="pt-2 text-xs font-semibold text-neutral-900 flex items-center justify-between">
                  <span>{currentRole.previewSnippet.action}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
