import React from 'react';
import { ArrowRight, Play, ShieldCheck, Sparkles } from 'lucide-react';
import { HeroSkyline } from './HeroSkyline';

interface HeroSectionProps {
  onBookDemo: () => void;
  onWatchDemo: () => void;
  onApplyDesignPartner: () => void;
}

export const HeroSection: React.FC<HeroSectionProps> = ({
  onBookDemo,
  onWatchDemo,
  onApplyDesignPartner,
}) => {
  const scrollToProblem = () => {
    const el = document.getElementById('problem');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section className="relative min-h-[92vh] pt-32 sm:pt-36 md:pt-40 flex flex-col justify-between overflow-hidden bg-gradient-to-b from-[#FAF8F5] via-[#EFECE5] to-[#12141A]">
      {/* Subtle radial ambient highlight behind headline */}
      <div
        className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[380px] bg-amber-200/25 blur-[120px] rounded-full pointer-events-none"
        aria-hidden="true"
      />

      {/* Main Hero Content */}
      <div className="relative z-10 max-w-4xl mx-auto px-6 text-center flex flex-col items-center">
        {/* Onboarding design partner pill tag from PDF */}
        <button
          onClick={onApplyDesignPartner}
          className="group inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/75 hover:bg-white border border-neutral-300/80 hover:border-amber-400/80 text-xs sm:text-sm font-medium text-neutral-800 shadow-[0_2px_8px_rgba(0,0,0,0.03)] backdrop-blur-md transition-all duration-200 hover:scale-[1.02] cursor-pointer mb-7 sm:mb-8"
        >
          <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          <span>Now onboarding design-partner funds</span>
          <span className="text-neutral-400 group-hover:text-amber-600 group-hover:translate-x-0.5 transition-all">
            →
          </span>
        </button>

        {/* Headline strictly following the PDF page 1 display typography */}
        <h1 className="text-5xl sm:text-6xl md:text-7xl lg:text-[80px] font-extrabold text-[#111317] tracking-tight leading-[1.06] mb-6 text-balance">
          See the deal first.
          <span className="block text-[#3B404D] font-bold text-4xl sm:text-5xl md:text-6xl mt-2">
            Close it faster.
          </span>
        </h1>

        {/* Subheadline matching both PDF and copy brief */}
        <p className="max-w-2xl text-lg sm:text-xl text-neutral-600 font-normal leading-relaxed mb-8 sm:mb-10 text-balance">
          The AI infrastructure layer for venture firms. Sourcing, diligence and portfolio intelligence in one place. Firstlook unifies your relationships, deal flow and portfolio data into one intelligent graph.
        </p>

        {/* Action Buttons from PDF */}
        <div className="flex flex-col sm:flex-row items-center gap-3 sm:gap-4 w-full sm:w-auto mb-8">
          <button
            onClick={onBookDemo}
            className="w-full sm:w-auto px-7 py-3.5 rounded-full bg-white hover:bg-neutral-50 text-[#111317] font-semibold text-sm sm:text-base border border-neutral-300/80 shadow-[0_4px_14px_rgba(0,0,0,0.06)] hover:shadow-[0_6px_20px_rgba(0,0,0,0.1)] flex items-center justify-center gap-2 transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0"
          >
            <span>Book a demo</span>
            <ArrowRight className="w-4 h-4 text-neutral-700" />
          </button>

          <button
            onClick={onWatchDemo}
            className="w-full sm:w-auto px-6 py-3.5 rounded-full bg-white/40 hover:bg-white/70 text-neutral-800 font-medium text-sm sm:text-base border border-neutral-300/60 backdrop-blur-md flex items-center justify-center gap-2 transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0"
          >
            <div className="w-5 h-5 rounded-full bg-neutral-900/10 flex items-center justify-center text-neutral-800">
              <Play className="w-2.5 h-2.5 fill-current ml-0.5" />
            </div>
            <span>Watch demo</span>
          </button>
        </div>

        {/* Trust Line from Copy brief */}
        <div className="flex items-center justify-center gap-2 text-xs sm:text-sm text-neutral-500 font-medium max-w-xl text-center">
          <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>
            Built for seed to Series B funds. Your data stays yours: encrypted, isolated, and never used to train shared models.
          </span>
        </div>
      </div>

      {/* Hero Skyline pixel silhouette & golden highways with SCROLL button */}
      <HeroSkyline onScrollClick={scrollToProblem} />
    </section>
  );
};
