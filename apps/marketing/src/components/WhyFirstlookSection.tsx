import React, { useState } from 'react';
import {
  Quote,
  ShieldAlert,
  MessageSquare,
  Terminal,
  Globe2,
  CheckCircle,
  ExternalLink,
  Code2
} from 'lucide-react';

export const WhyFirstlookSection: React.FC = () => {
  const [activeCitationDemo, setActiveCitationDemo] = useState(false);

  return (
    <section id="why-firstlook" className="py-24 sm:py-32 bg-[#FAF8F5] border-t border-neutral-200 relative">
      <div className="max-w-6xl mx-auto px-6">
        {/* Section Header */}
        <div className="max-w-3xl mb-16">
          <div className="text-xs font-semibold uppercase tracking-widest text-amber-700 mb-3">
            Architectural Principles
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-[#111317] tracking-tight mb-5 leading-tight text-balance">
            Why venture firms choose Firstlook.
          </h2>
          <p className="text-lg text-neutral-600 leading-relaxed font-normal">
            Built from first principles for partner meetings, strict IC standards, and confidential high-stakes allocations.
          </p>
        </div>

        {/* Bento Grid layout */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          {/* Card 1: Every answer is cited (Featured 7 cols) */}
          <div className="md:col-span-7 p-8 sm:p-10 rounded-3xl bg-white border border-neutral-300/80 shadow-sm flex flex-col justify-between">
            <div>
              <div className="inline-flex items-center gap-2 text-xs font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-full mb-5">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                Zero Hallucinations Policy
              </div>
              <h3 className="text-2xl sm:text-3xl font-bold text-neutral-900 mb-3">
                Every answer is cited.
              </h3>
              <p className="text-base text-neutral-600 leading-relaxed mb-6 font-normal">
                Each AI-generated claim links back to its source. Hover or click any metric in a memo to instantly inspect the deck slide, spreadsheet cell, or email thread where it originated.
              </p>

              {/* Interactive citation preview widget */}
              <div className="p-4 rounded-2xl bg-[#FAF9F5] border border-neutral-200/90 text-xs">
                <div className="text-neutral-700 leading-relaxed mb-3">
                  “The target enterprise reported{' '}
                  <span
                    onClick={() => setActiveCitationDemo(!activeCitationDemo)}
                    className="cursor-pointer bg-amber-100 hover:bg-amber-200 text-amber-900 px-1.5 py-0.5 rounded font-mono font-medium border-b-2 border-amber-400 transition-colors"
                  >
                    $2.4M ARR with 142% NRR [1]
                  </span>{' '}
                  across 42 enterprise logos, driven by a 14-day sales velocity.”
                </div>

                <div className="p-3 bg-white rounded-xl border border-neutral-200 shadow-sm">
                  <div className="flex items-center justify-between text-[11px] font-mono font-semibold text-neutral-500 mb-1">
                    <span>Source Reference [1]</span>
                    <span className="text-emerald-700">Verified Match</span>
                  </div>
                  <div className="text-xs font-medium text-neutral-800 flex items-center gap-1.5">
                    <ExternalLink className="w-3.5 h-3.5 text-amber-600" />
                    <span>DataRoom/Fin_Model_Q2.xlsx &gt; Tab: MRR_Bridge &gt; Cell L42</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-neutral-100 text-xs text-neutral-500 flex items-center justify-between">
              <span>Audited source traceability</span>
              <span className="font-semibold text-neutral-800">100% verifiable memos</span>
            </div>
          </div>

          {/* Card 2: Humans stay in control (5 cols) */}
          <div className="md:col-span-5 p-8 sm:p-10 rounded-3xl bg-[#FAF8F5] border border-neutral-300/80 flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-2xl bg-neutral-900 text-amber-400 flex items-center justify-center mb-5">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <h3 className="text-2xl font-bold text-neutral-900 mb-3">
                Humans stay in control.
              </h3>
              <p className="text-sm text-neutral-600 leading-relaxed mb-6">
                Agents propose, and your team approves anything that leaves the firm. No automated emails or communications go out without explicit partner confirmation.
              </p>

              <div className="p-3.5 rounded-xl bg-white border border-neutral-200 space-y-2 text-xs">
                <div className="flex items-center justify-between font-medium text-neutral-700">
                  <span>Founder Intro Draft</span>
                  <span className="text-amber-700 bg-amber-50 px-2 py-0.5 rounded font-mono">Pending Approval</span>
                </div>
                <div className="text-neutral-500 text-[11px]">
                  Agent proposed email reply with Calendly link. Awaiting GP click to dispatch.
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-neutral-200/80 text-xs text-neutral-500">
              Zero autonomous external side-effects
            </div>
          </div>

          {/* Card 3: It works where you work (4 cols) */}
          <div className="md:col-span-4 p-8 rounded-3xl bg-white border border-neutral-300/80 flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-2xl bg-amber-100 text-amber-800 flex items-center justify-center mb-5">
                <MessageSquare className="w-5 h-5" />
              </div>
              <h3 className="text-xl font-bold text-neutral-900 mb-2">
                It works where you work.
              </h3>
              <p className="text-sm text-neutral-600 leading-relaxed mb-4">
                Alerts and briefs arrive directly in email, Slack and Microsoft Teams. You never have to switch tabs to review a deal summary.
              </p>
            </div>
            <div className="pt-4 border-t border-neutral-100 flex items-center gap-3 text-xs font-semibold text-neutral-600">
              <span className="px-2.5 py-1 rounded-md bg-neutral-100">Slack</span>
              <span className="px-2.5 py-1 rounded-md bg-neutral-100">Teams</span>
              <span className="px-2.5 py-1 rounded-md bg-neutral-100">Email Digest</span>
            </div>
          </div>

          {/* Card 4: It's open by design (4 cols) */}
          <div className="md:col-span-4 p-8 rounded-3xl bg-white border border-neutral-300/80 flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-2xl bg-neutral-900 text-white flex items-center justify-center mb-5">
                <Terminal className="w-5 h-5" />
              </div>
              <h3 className="text-xl font-bold text-neutral-900 mb-2">
                It's open by design.
              </h3>
              <p className="text-sm text-neutral-600 leading-relaxed mb-4">
                APIs, webhooks and an MCP server let you plug in your own proprietary fine-tuned models, vector indexes, and custom internal tools.
              </p>
            </div>
            <div className="pt-4 border-t border-neutral-100 flex items-center justify-between text-xs font-mono text-neutral-600">
              <span>Model Context Protocol (MCP)</span>
              <span className="text-amber-700 font-semibold">v1.0 API</span>
            </div>
          </div>

          {/* Card 5: Built for emerging markets too (4 cols) */}
          <div className="md:col-span-4 p-8 rounded-3xl bg-neutral-900 text-white border border-neutral-800 flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-2xl bg-amber-500/20 text-amber-400 flex items-center justify-center mb-5">
                <Globe2 className="w-5 h-5" />
              </div>
              <h3 className="text-xl font-bold text-white mb-2">
                Built for emerging markets too.
              </h3>
              <p className="text-sm text-neutral-300 leading-relaxed mb-4">
                Multi-currency KPIs, WhatsApp integration and local data sources for funds investing across Nairobi, Lagos, São Paulo, Jakarta, and beyond Silicon Valley.
              </p>
            </div>
            <div className="pt-4 border-t border-neutral-800 text-xs text-neutral-400 flex items-center justify-between">
              <span>KES, NGN, BRL, USD</span>
              <span className="text-emerald-400 font-medium">WhatsApp Sync</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
