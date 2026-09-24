import React, { useState } from 'react';
import {
  Users,
  Compass,
  FileSearch,
  Activity,
  ScrollText,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
  Sparkles,
  TrendingUp,
  AlertCircle,
  Clock,
  Building,
  DollarSign,
  Briefcase
} from 'lucide-react';

export const FeaturesSection: React.FC = () => {
  const [activeFeature, setActiveFeature] = useState<number>(0);

  const features = [
    {
      id: 'relationship-intelligence',
      title: 'Relationship intelligence',
      subtitle: 'Passive graph capture',
      description:
        "Every email, meeting and intro is captured automatically, with no manual logging. See relationship strength and warm paths across your whole team's network.",
      badge: 'Zero manual logging',
      icon: Users,
      stats: '100% network coverage',
      mockData: {
        type: 'graph',
        title: 'Warm Path Discovery',
        entity: 'Elena Rostova (CTO, NexaBio)',
        paths: [
          {
            person: 'David K. (GP, Horizon)',
            strength: 'Strong (84 emails, 4 meetings)',
            connection: 'Co-invested with Elena in 2023',
            badge: 'Direct warm intro'
          },
          {
            person: 'Marcus Vance (Venture Partner)',
            strength: 'Moderate (Met at Slush 2024)',
            connection: 'Alumni Stanford AI Lab',
            badge: 'Secondary path'
          }
        ],
        interactionCount: '34 touchpoints indexed across 3 team members'
      }
    },
    {
      id: 'thesis-sourcing',
      title: 'Thesis-driven sourcing',
      subtitle: 'Continuous market radar',
      description:
        'Define your thesis once. Firstlook tracks funding rounds, hiring, traffic, founder moves and news, then ranks the companies that fit, each with a written rationale.',
      badge: 'Real-time thesis scoring',
      icon: Compass,
      stats: '24/7 autonomous monitoring',
      mockData: {
        type: 'ranking',
        thesis: 'Enterprise DevTools & Infrastructure in Emerging Hubs',
        candidates: [
          {
            name: 'KiteFlow Engine',
            score: '98% Thesis Match',
            metrics: 'ARR: $1.2M (+220% YoY) · Team: ex-Stripe, ex-AWS',
            rationale: 'Breakout SDK adoption in Nairobi & Lagos; meets Seed-stage multi-tenant criteria.',
            stage: 'Raising $2.5M Seed'
          },
          {
            name: 'VectorMesh',
            score: '91% Thesis Match',
            metrics: 'GitHub: 3.4k stars · Headcount +40% in 60d',
            rationale: 'Founder left Datadog 4 mos ago; stealth enterprise telemetry proxy.',
            stage: 'Pre-seed round assembling'
          }
        ]
      }
    },
    {
      id: 'diligence-copilot',
      title: 'Diligence copilot',
      subtitle: 'Cited analysis & fact checking',
      description:
        "Drop in a deck or data room. Get a cited fact sheet, a market map and a first-draft memo in your firm's template in hours instead of weeks. Inconsistencies are flagged automatically.",
      badge: 'Every fact verified & cited',
      icon: FileSearch,
      stats: 'Hours instead of weeks',
      mockData: {
        type: 'memo',
        dealName: 'Aura Compute — Series A Memo Draft',
        sections: [
          {
            label: 'Net Revenue Retention',
            value: '138% NRR (FY25)',
            citation: 'Page 14, Aura_Cohort_Analysis.xlsx [Cell D28]',
            verified: true
          },
          {
            label: 'Founder Cap Table',
            value: '68.4% common equity post-unallocated pool',
            citation: 'Series_Seed_CapTable_Final.pdf [Exhibit A]',
            verified: true
          },
          {
            label: 'Flagged Inconsistency',
            value: 'Customer churn stated at 0.4% in deck vs 1.8% in Stripe export',
            citation: 'Deck slide 8 vs raw_stripe_mrr_2025.csv',
            verified: false,
            flag: true
          }
        ]
      }
    },
    {
      id: 'portfolio-monitoring',
      title: 'Portfolio monitoring',
      subtitle: 'Normalized telemetry & alerts',
      description:
        'Founders submit KPIs through a simple portal. Firstlook normalizes metrics and currencies, benchmarks performance, and alerts you to risks like short runway before the board meeting.',
      badge: 'Runway & burn risk alerts',
      icon: Activity,
      stats: 'Multi-currency normalization',
      mockData: {
        type: 'portfolio',
        portfolioSummary: '24 Active Portfolio Companies',
        alerts: [
          {
            company: 'PayGrid Africa',
            metric: '5.2 Months Runway Remaining',
            status: 'Action Required',
            note: 'Net burn increased by 18% in Q2 due to expansion. Board meeting in 12 days.',
            severity: 'high'
          },
          {
            company: 'Solaria Solar ERP',
            metric: '$340k MRR (+24% MoM)',
            status: 'Outperforming',
            note: 'Crossing Series A metric threshold. Ready for intro to Tier-1 growth funds.',
            severity: 'positive'
          }
        ]
      }
    },
    {
      id: 'terms-reporting',
      title: 'Terms and LP reporting',
      subtitle: 'Playbook guardrails & fund letters',
      description:
        'Flag non-standard term sheet clauses against your own playbook and history. Draft quarterly LP letters and fund metrics straight from live portfolio data.',
      badge: 'Playbook clause checking',
      icon: ScrollText,
      stats: 'Zero spreadsheet scramble',
      mockData: {
        type: 'terms',
        title: 'Term Sheet & LP Intelligence',
        clauses: [
          {
            clause: '2.5x Liquidation Preference (Participating)',
            status: 'Flagged: Non-standard',
            detail: 'Your fund standard is 1.0x Non-participating. Deviates from 18 prior seed deals.',
            warning: true
          },
          {
            clause: 'Q3 LP Fund Letter Auto-Draft',
            status: 'Ready for Review',
            detail: 'Net TVPI: 2.14x · Net IRR: 31.8% · 3 portfolio markups integrated from verified audits.',
            warning: false
          }
        ]
      }
    }
  ];

  const current = features[activeFeature];

  return (
    <section id="platform" className="py-24 sm:py-32 bg-[#FAF8F5] relative">
      <div className="max-w-6xl mx-auto px-6">
        {/* Section Header */}
        <div className="max-w-3xl mb-16">
          <div className="text-xs font-semibold uppercase tracking-widest text-amber-700 mb-3">
            Core Platform Architecture
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-[#111317] tracking-tight mb-5 leading-tight text-balance">
            One platform for the whole investment lifecycle.
          </h2>
          <p className="text-lg text-neutral-600 font-normal leading-relaxed">
            Eliminate fragmented tools. From initial founder ping to quarterly LP reporting, Firstlook unifies every interaction into an actionable intelligence system.
          </p>
        </div>

        {/* Interactive Feature Navigation Tabs */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-2 p-1.5 bg-[#EAE7DF] rounded-2xl mb-10 border border-neutral-300/70">
          {features.map((feat, index) => {
            const Icon = feat.icon;
            const isActive = activeFeature === index;
            return (
              <button
                key={feat.id}
                onClick={() => setActiveFeature(index)}
                className={`flex items-center md:flex-col md:items-start p-3.5 sm:p-4 rounded-xl text-left transition-all duration-200 cursor-pointer ${
                  isActive
                    ? 'bg-white text-neutral-900 shadow-sm border border-neutral-200'
                    : 'text-neutral-600 hover:text-neutral-900 hover:bg-white/40'
                }`}
              >
                <div className="flex items-center gap-2.5 mb-1">
                  <Icon
                    className={`w-4 h-4 ${isActive ? 'text-amber-600' : 'text-neutral-500'}`}
                  />
                  <span className="text-xs font-semibold uppercase tracking-wider hidden md:inline text-neutral-400">
                    0{index + 1}
                  </span>
                </div>
                <div className="font-semibold text-xs sm:text-sm truncate w-full">
                  {feat.title}
                </div>
              </button>
            );
          })}
        </div>

        {/* Active Feature Showcase Stage */}
        <div className="bg-white rounded-3xl border border-neutral-300/80 shadow-[0_8px_30px_rgba(0,0,0,0.04)] p-6 sm:p-10 lg:p-12 transition-all">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
            {/* Feature Prose description */}
            <div className="lg:col-span-5 flex flex-col justify-between">
              <div>
                <div className="inline-flex items-center gap-2 text-xs font-semibold text-amber-800 bg-amber-50 border border-amber-200/80 px-3 py-1 rounded-full mb-4">
                  <Sparkles className="w-3.5 h-3.5 text-amber-600" />
                  <span>{current.badge}</span>
                </div>

                <h3 className="text-2xl sm:text-3xl font-bold text-neutral-900 mb-4 tracking-tight">
                  {current.title}
                </h3>

                <p className="text-base sm:text-lg text-neutral-600 leading-relaxed mb-6 font-normal">
                  {current.description}
                </p>
              </div>

              <div className="pt-6 border-t border-neutral-100 flex items-center justify-between text-xs sm:text-sm text-neutral-500">
                <span>Architecture benefit:</span>
                <span className="font-semibold text-neutral-800">{current.stats}</span>
              </div>
            </div>

            {/* Live Interactive UI Simulation */}
            <div className="lg:col-span-7 bg-[#FAF9F5] rounded-2xl border border-neutral-200 p-5 sm:p-6 shadow-inner font-sans">
              {/* Simulated Window Top Bar */}
              <div className="flex items-center justify-between pb-3 mb-4 border-b border-neutral-200 text-xs text-neutral-500">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-neutral-300" />
                  <span className="w-2.5 h-2.5 rounded-full bg-neutral-300" />
                  <span className="w-2.5 h-2.5 rounded-full bg-neutral-300" />
                  <span className="ml-2 font-mono text-neutral-600 font-medium">firstlook://intelligence/{current.id}</span>
                </div>
                <span className="text-[11px] text-emerald-700 bg-emerald-100/80 font-medium px-2 py-0.5 rounded">
                  Live sync
                </span>
              </div>

              {/* Render dynamic mock based on active feature */}
              {current.mockData.type === 'graph' && (
                <div className="space-y-4">
                  <div className="p-3.5 bg-white rounded-xl border border-neutral-200">
                    <div className="text-xs text-neutral-400 font-medium uppercase tracking-wider mb-1">Target Entity</div>
                    <div className="text-base font-bold text-neutral-900 flex items-center justify-between">
                      <span>{current.mockData.entity}</span>
                      <span className="text-xs font-medium text-amber-700 bg-amber-100/70 px-2 py-0.5 rounded-md">Proprietary Target</span>
                    </div>
                  </div>

                  <div className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
                    Computed Warm Paths
                  </div>

                  <div className="space-y-2.5">
                    {current.mockData.paths?.map((path, idx) => (
                      <div key={idx} className="p-3.5 bg-white rounded-xl border border-neutral-200/90 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div>
                          <div className="text-sm font-bold text-neutral-900 flex items-center gap-2">
                            <span>{path.person}</span>
                            <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                              {path.badge}
                            </span>
                          </div>
                          <div className="text-xs text-neutral-500 mt-0.5">{path.connection}</div>
                        </div>
                        <div className="text-xs font-mono font-medium text-amber-800 bg-amber-50 px-2 py-1 rounded self-start sm:self-center">
                          {path.strength}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="p-2.5 rounded-lg bg-neutral-100 text-[11px] text-neutral-600 text-center font-mono">
                    {current.mockData.interactionCount}
                  </div>
                </div>
              )}

              {current.mockData.type === 'ranking' && (
                <div className="space-y-3.5">
                  <div className="text-xs font-medium text-neutral-500 bg-neutral-100 p-2.5 rounded-lg">
                    Active Thesis: <strong className="text-neutral-900">{current.mockData.thesis}</strong>
                  </div>

                  {current.mockData.candidates?.map((item, idx) => (
                    <div key={idx} className="p-4 bg-white rounded-xl border border-neutral-200">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-bold text-sm text-neutral-900">{item.name}</span>
                        <span className="text-xs font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                          {item.score}
                        </span>
                      </div>
                      <div className="text-xs font-mono text-neutral-500 mb-2">{item.metrics}</div>
                      <div className="text-xs text-neutral-700 bg-amber-50/70 p-2.5 rounded-lg border border-amber-200/50 mb-2 leading-relaxed">
                        <strong className="text-amber-900 font-semibold">AI Rationale: </strong>
                        {item.rationale}
                      </div>
                      <div className="text-[11px] font-semibold text-neutral-400">
                        Status: <span className="text-neutral-800">{item.stage}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {current.mockData.type === 'memo' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold uppercase tracking-wider text-neutral-700">
                      {current.mockData.dealName}
                    </span>
                    <span className="text-xs font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      IC Template v4
                    </span>
                  </div>

                  {current.mockData.sections?.map((sec, idx) => (
                    <div
                      key={idx}
                      className={`p-3.5 rounded-xl border ${
                        sec.flag
                          ? 'bg-rose-50/80 border-rose-200 text-rose-900'
                          : 'bg-white border-neutral-200 text-neutral-900'
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs font-semibold mb-1">
                        <span className={sec.flag ? 'text-rose-800' : 'text-neutral-500'}>{sec.label}</span>
                        {sec.flag ? (
                          <span className="flex items-center gap-1 text-[11px] text-rose-700 font-bold bg-rose-100 px-2 py-0.5 rounded">
                            <AlertCircle className="w-3 h-3" /> Discrepancy Found
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-[11px] text-emerald-700 font-medium bg-emerald-50 px-2 py-0.5 rounded">
                            <CheckCircle2 className="w-3 h-3" /> Cited & Verified
                          </span>
                        )}
                      </div>
                      <div className="text-sm font-bold mb-1.5">{sec.value}</div>
                      <div className="text-xs font-mono opacity-75 flex items-center gap-1">
                        <ExternalLink className="w-3 h-3" /> Source: {sec.citation}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {current.mockData.type === 'portfolio' && (
                <div className="space-y-3">
                  <div className="text-xs font-medium text-neutral-500 flex justify-between items-center mb-1">
                    <span>{current.mockData.portfolioSummary}</span>
                    <span className="text-xs text-neutral-400">Next Board Cycle: Oct 2026</span>
                  </div>

                  {current.mockData.alerts?.map((alert, idx) => (
                    <div
                      key={idx}
                      className={`p-4 rounded-xl border ${
                        alert.severity === 'high'
                          ? 'bg-amber-50/90 border-amber-200'
                          : 'bg-emerald-50/80 border-emerald-200'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-bold text-sm text-neutral-900">{alert.company}</span>
                        <span
                          className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                            alert.severity === 'high'
                              ? 'bg-amber-200/80 text-amber-900'
                              : 'bg-emerald-200 text-emerald-900'
                          }`}
                        >
                          {alert.status}
                        </span>
                      </div>
                      <div className="text-xs font-mono font-bold text-neutral-800 mb-1.5">
                        {alert.metric}
                      </div>
                      <p className="text-xs text-neutral-600 leading-relaxed">
                        {alert.note}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {current.mockData.type === 'terms' && (
                <div className="space-y-3">
                  <div className="text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-1">
                    Playbook Compliance Check
                  </div>

                  {current.mockData.clauses?.map((item, idx) => (
                    <div
                      key={idx}
                      className={`p-4 rounded-xl border ${
                        item.warning
                          ? 'bg-amber-50 border-amber-200'
                          : 'bg-white border-neutral-200'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-sm text-neutral-900">{item.clause}</span>
                        <span
                          className={`text-xs font-bold px-2 py-0.5 rounded ${
                            item.warning ? 'bg-amber-200 text-amber-900' : 'bg-emerald-100 text-emerald-800'
                          }`}
                        >
                          {item.status}
                        </span>
                      </div>
                      <p className="text-xs text-neutral-600 leading-relaxed mt-1">
                        {item.detail}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
