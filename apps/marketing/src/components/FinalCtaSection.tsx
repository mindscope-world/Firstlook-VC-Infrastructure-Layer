import React from 'react';
import { ArrowRight, Sparkles, ShieldCheck } from 'lucide-react';

interface FinalCtaSectionProps {
  onApplyDesignPartner: () => void;
  onBookDemo: () => void;
}

export const FinalCtaSection: React.FC<FinalCtaSectionProps> = ({
  onApplyDesignPartner,
  onBookDemo,
}) => {
  return (
    <section className="py-24 sm:py-32 bg-neutral-950 text-white relative overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[350px] bg-amber-500/10 blur-[140px] rounded-full pointer-events-none" />

      <div className="relative z-10 max-w-4xl mx-auto px-6 text-center">
        <div className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-400 bg-amber-950/60 border border-amber-800/80 px-3.5 py-1 rounded-full mb-6">
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span>Limited Cohort 2 Intake</span>
        </div>

        <h2 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-white mb-6 leading-[1.1] text-balance">
          Stop showing up to conversations that are already over.
        </h2>

        <p className="max-w-2xl mx-auto text-lg sm:text-xl text-neutral-300 font-normal leading-relaxed mb-10 text-balance">
          We're onboarding a small group of design-partner funds. Get early access, dedicated integration engineering, and help shape the product.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <button
            onClick={onApplyDesignPartner}
            className="w-full sm:w-auto px-8 py-4 rounded-full bg-white hover:bg-neutral-100 text-neutral-950 font-bold text-base shadow-xl flex items-center justify-center gap-2 transition-all duration-200 hover:scale-105 active:scale-95"
          >
            <span>Apply to be a design partner</span>
            <ArrowRight className="w-4 h-4 text-neutral-900" />
          </button>

          <button
            onClick={onBookDemo}
            className="w-full sm:w-auto px-7 py-4 rounded-full bg-neutral-900 hover:bg-neutral-800 text-neutral-200 font-medium text-base border border-neutral-700/80 flex items-center justify-center gap-2 transition-all duration-200 hover:text-white"
          >
            <span>Book a demo</span>
          </button>
        </div>

        <div className="mt-10 flex items-center justify-center gap-2 text-xs text-neutral-400 font-medium">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>No long-term commitment required for early design-partner cohorts.</span>
        </div>
      </div>
    </section>
  );
};
