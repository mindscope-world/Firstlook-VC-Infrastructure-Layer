import React, { useState } from 'react';
import { Link2, Network, Cpu, ArrowRight, Check, ShieldCheck } from 'lucide-react';

export const HowItWorksSection: React.FC = () => {
  const [selectedStep, setSelectedStep] = useState<number>(0);

  const steps = [
    {
      number: '01',
      title: 'Connect',
      subtitle: 'Zero-friction integration',
      description:
        'Link email, calendar, Slack and documents in minutes. You can migrate from your existing CRM without disrupting ongoing deals.',
      icon: Link2,
      integrations: ['Google Workspace', 'Microsoft 365', 'Slack', 'Affinity / Salesforce migration', 'DocSend / Dropbox'],
      highlight: 'Set up in < 15 minutes'
    },
    {
      number: '02',
      title: 'Unify',
      subtitle: 'Knowledge graph resolution',
      description:
        "Firstlook resolves every person, company and deal into your firm's private knowledge graph with entity deduplication and role history.",
      icon: Network,
      integrations: ['Identity Resolution', 'Multi-tenant Isolation', 'Private Graph Schema', 'Historical Round Reconstruction'],
      highlight: '100% private to your firm'
    },
    {
      number: '03',
      title: 'Act',
      subtitle: 'Human-in-the-loop autonomous copilots',
      description:
        'AI agents screen deals, draft memos and monitor your portfolio. Your team reviews and decides every action before it leaves the firm.',
      icon: Cpu,
      integrations: ['IC Brief Drafter', 'Redline Term Sheet Verifier', 'Runway Risk Sentry', 'LP Quarterly Letter Engine'],
      highlight: 'Human partner sign-off required'
    }
  ];

  return (
    <section id="how-it-works" className="py-24 sm:py-32 bg-[#FAF8F5] border-t border-neutral-200">
      <div className="max-w-6xl mx-auto px-6">
        {/* Header */}
        <div className="max-w-3xl mb-16">
          <div className="text-xs font-semibold uppercase tracking-widest text-amber-700 mb-3">
            Operational Blueprint
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-[#111317] tracking-tight mb-5 leading-tight text-balance">
            How Firstlook works.
          </h2>
          <p className="text-lg text-neutral-600 leading-relaxed font-normal">
            A three-step architecture designed to turn unstructured communication into unfair sourcing speed.
          </p>
        </div>

        {/* 3 Step Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-8">
          {steps.map((step, idx) => {
            const Icon = step.icon;
            const isSelected = selectedStep === idx;
            return (
              <div
                key={step.number}
                onClick={() => setSelectedStep(idx)}
                className={`p-8 rounded-3xl transition-all duration-300 border flex flex-col justify-between cursor-pointer ${
                  isSelected
                    ? 'bg-white border-neutral-400 shadow-md ring-1 ring-neutral-300'
                    : 'bg-[#F3EFE6]/70 border-neutral-300/70 hover:bg-white hover:border-neutral-300'
                }`}
              >
                <div>
                  {/* Step index & badge */}
                  <div className="flex items-center justify-between mb-6">
                    <span className="text-2xl font-black tracking-tight text-neutral-900 font-mono">
                      {step.number}
                    </span>
                    <span className="text-xs font-medium text-neutral-600 bg-neutral-200/70 px-2.5 py-1 rounded-full">
                      {step.highlight}
                    </span>
                  </div>

                  <div className="w-10 h-10 rounded-2xl bg-neutral-900 text-white flex items-center justify-center mb-5 shadow-sm">
                    <Icon className="w-5 h-5" />
                  </div>

                  <h3 className="text-2xl font-bold text-neutral-900 mb-2">
                    {step.title}
                  </h3>
                  <div className="text-xs font-semibold uppercase tracking-wider text-amber-700 mb-3">
                    {step.subtitle}
                  </div>

                  <p className="text-sm sm:text-base text-neutral-600 leading-relaxed mb-6 font-normal">
                    {step.description}
                  </p>
                </div>

                {/* Sub features list */}
                <div className="pt-5 border-t border-neutral-200/80">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-neutral-400 mb-2.5">
                    Engine Capabilities
                  </div>
                  <ul className="space-y-1.5">
                    {step.integrations.map((item, itemIdx) => (
                      <li key={itemIdx} className="text-xs font-medium text-neutral-700 flex items-center gap-2">
                        <Check className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
