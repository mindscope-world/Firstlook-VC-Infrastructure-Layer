import React, { useState } from 'react';
import { Clock, AlertTriangle, ArrowRight, CheckCircle2, Layers, Zap } from 'lucide-react';

export const ProblemSection: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'comparison' | 'breakdown'>('comparison');

  return (
    <section id="problem" className="py-24 sm:py-32 bg-[#FAF8F5] relative overflow-hidden border-b border-neutral-200">
      <div className="max-w-6xl mx-auto px-6">
        {/* Section Header */}
        <div className="max-w-3xl mb-16">
          <div className="text-xs font-semibold uppercase tracking-widest text-amber-700 mb-3">
            The Industry Bottleneck
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-[#111317] tracking-tight mb-6 leading-tight text-balance">
            The best deals go to the fastest firms.
          </h2>
          <p className="text-lg sm:text-xl text-neutral-600 leading-relaxed font-normal mb-4">
            Your team spends its week logging emails, chasing founders for KPIs and rebuilding the same spreadsheets. Meanwhile, the companies you should be meeting are already in someone else's pipeline.
          </p>
          <p className="text-base sm:text-lg text-neutral-600 leading-relaxed font-normal">
            Most firms stitch together a CRM, data vendors, spreadsheets and chat assistants by hand. <strong className="text-neutral-900 font-semibold">Firstlook</strong> replaces that glue with one source of truth that every workflow reads from and writes to.
          </p>
        </div>

        {/* Interactive Comparison Cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-stretch">
          {/* Legacy Stitch Card */}
          <div className="p-8 sm:p-10 rounded-3xl bg-[#F0ECE1]/70 border border-neutral-300/80 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-6">
                <span className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
                  The Fragmented Stack
                </span>
                <span className="flex items-center gap-1.5 text-xs font-medium text-amber-800 bg-amber-100/80 px-2.5 py-1 rounded-full">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-700" />
                  14+ hrs lost / partner / week
                </span>
              </div>
              <h3 className="text-2xl font-bold text-neutral-900 mb-4">
                Manual glue & fragmented silos
              </h3>
              <p className="text-sm text-neutral-600 mb-6 leading-relaxed">
                Critical relationship notes trapped in personal inboxes. Junior associates manually transcribing pitch deck tables into Google Sheets. Sourcing happens when founders announce rounds on Twitter.
              </p>

              <div className="space-y-3">
                {[
                  { title: 'Manual CRM logging', desc: 'Missed warm intros because partner inbox threads are siloed' },
                  { title: 'Hallucinated generic chat AI', desc: 'Generic LLMs making up unit economics without verifiable citations' },
                  { title: 'KPI chasing every quarter', desc: 'Endless email ping-pongs to get founders to upload runway spreadsheets' },
                  { title: 'Stale IC memos', desc: 'Days spent building first drafts that are outdated before partner meeting' },
                ].map((item, idx) => (
                  <div key={idx} className="flex items-start gap-3 p-3 rounded-xl bg-white/50 border border-neutral-200/60">
                    <div className="w-5 h-5 rounded-full bg-rose-100 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-rose-600 text-xs font-bold">✕</span>
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-neutral-800">{item.title}</div>
                      <div className="text-xs text-neutral-500">{item.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-8 pt-6 border-t border-neutral-300/60 text-xs text-neutral-500 flex items-center justify-between">
              <span>Outcome: Slower response times & missed allocations</span>
              <span className="text-rose-700 font-semibold font-mono">High deal friction</span>
            </div>
          </div>

          {/* Firstlook Unified Architecture Card */}
          <div className="p-8 sm:p-10 rounded-3xl bg-neutral-950 text-white border border-neutral-800 flex flex-col justify-between relative shadow-xl">
            {/* Ambient amber glow */}
            <div className="absolute -top-24 -right-24 w-72 h-72 bg-amber-500/10 blur-[90px] rounded-full pointer-events-none" />

            <div>
              <div className="flex items-center justify-between mb-6">
                <span className="text-xs font-semibold uppercase tracking-wider text-amber-400">
                  The Firstlook Unified Graph
                </span>
                <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-2.5 py-1 rounded-full">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  Instant verified diligence
                </span>
              </div>
              <h3 className="text-2xl font-bold text-white mb-4">
                One living intelligence layer
              </h3>
              <p className="text-sm text-neutral-300 mb-6 leading-relaxed">
                Firstlook continually ingests emails, calendar intros, data rooms, and market signals into a secure knowledge graph. Every agent proposal is verifiable with direct citation links back to source material.
              </p>

              <div className="space-y-3">
                {[
                  { title: 'Zero-effort relationship capture', desc: 'Autonomous discovery of warm intros and founder network paths' },
                  { title: '100% cited diligence copilot', desc: 'Instant extraction of ARR, burn, churn with clickable PDF page proof' },
                  { title: 'Continuous founder KPI sync', desc: 'Clean founder portal normalizes currencies and benchmarks metrics' },
                  { title: 'Proactive thesis alerts', desc: 'Real-time detection of stealth spinouts and key engineering hires' },
                ].map((item, idx) => (
                  <div key={idx} className="flex items-start gap-3 p-3 rounded-xl bg-neutral-900/90 border border-neutral-800">
                    <div className="w-5 h-5 rounded-full bg-emerald-900/60 text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-xs font-bold">✓</span>
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-neutral-100">{item.title}</div>
                      <div className="text-xs text-neutral-400">{item.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-8 pt-6 border-t border-neutral-800 text-xs text-neutral-400 flex items-center justify-between">
              <span>Speed advantage: First to term sheet on proprietary deals</span>
              <span className="text-emerald-400 font-semibold font-mono">4x faster close</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
