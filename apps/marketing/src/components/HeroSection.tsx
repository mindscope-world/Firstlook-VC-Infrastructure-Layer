import React from 'react';
import { ArrowRight, CirclePlay } from 'lucide-react';
import { HeroSkyline } from './HeroSkyline';

interface HeroSectionProps {
  onBookDemo: () => void;
  onWatchDemo: () => void;
  onApplyDesignPartner: () => void;
}

// Matches "Hero — dawn city": dawn sky, one-line display headline, two-line
// subhead, and the pixel city along the bottom half.
export const HeroSection: React.FC<HeroSectionProps> = ({ onBookDemo, onWatchDemo, onApplyDesignPartner }) => {
  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });

  return (
    <section
      className="relative h-[100svh] min-h-[680px] max-h-[1100px] overflow-hidden"
      style={{
        background:
          'linear-gradient(180deg, #d4e1ee 0%, #e2e8ef 18%, #eceef2 30%, #f3efec 47%, #f7e9dc 60%, #f7dcc6 78%, #f4d4bc 100%)',
      }}
    >
      {/* Soft light behind the headline */}
      <div
        className="pointer-events-none absolute left-1/2 top-[40%] h-[46%] w-[70%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/45 blur-[90px]"
        aria-hidden="true"
      />

      <div className="relative z-10 mx-auto flex max-w-[1100px] flex-col items-center px-6 pt-[max(120px,27.5vh)] text-center">
        <button
          onClick={onApplyDesignPartner}
          className="group inline-flex items-center gap-2.5 whitespace-nowrap rounded-full border border-white bg-white/80 py-2 pl-4 pr-3.5 text-[13px] sm:text-[15px] font-medium text-[#1a1b22] shadow-[0_1px_3px_rgba(16,19,26,0.06)] backdrop-blur transition hover:bg-white"
        >
          <span className="h-2 w-2 rounded-full bg-[#E7893A]" />
          Now onboarding design-partner funds
          <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" strokeWidth={2.4} />
        </button>

        <h1
          className="mt-[clamp(20px,3.2vh,34px)] text-[clamp(50px,7.6vw,110px)] font-extrabold leading-[0.98] tracking-[-0.055em] text-[#111318]"
          style={{ fontVariationSettings: "'opsz' 14" }}
        >
          See the deal first.
        </h1>

        <p className="mt-[clamp(24px,4.2vh,44px)] text-[clamp(17px,1.55vw,22px)] leading-[1.62] text-[#2f3038]">
          The AI infrastructure layer for venture firms.
          <br />
          Sourcing, diligence and portfolio intelligence in one place.
        </p>

        <div className="mt-[clamp(24px,4.2vh,44px)] flex items-center gap-5 sm:gap-8 whitespace-nowrap">
          <button
            onClick={onBookDemo}
            className="inline-flex h-[50px] sm:h-[54px] items-center gap-3 rounded-full bg-white px-6 sm:px-7 text-[16px] sm:text-[17px] font-semibold text-[#10131A] shadow-[0_10px_30px_rgba(16,19,26,0.08),0_1px_2px_rgba(16,19,26,0.06)] transition hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(16,19,26,0.12)]"
          >
            Book a demo
            <ArrowRight className="h-4 w-4" strokeWidth={2.4} />
          </button>
          <button
            onClick={onWatchDemo}
            className="inline-flex items-center gap-2.5 text-[16px] sm:text-[17px] font-semibold text-[#10131A] transition hover:opacity-70"
          >
            <CirclePlay className="h-5 w-5" strokeWidth={2} />
            Watch demo
          </button>
        </div>
      </div>

      <HeroSkyline onScrollClick={() => scrollTo('problem')} onSearchClick={() => scrollTo('faq')} />
    </section>
  );
};
