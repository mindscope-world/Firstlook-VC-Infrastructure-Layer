import React from 'react';
import { Quote } from 'lucide-react';

export const SocialProofSection: React.FC = () => {
  return (
    <section className="py-20 sm:py-28 bg-[#F5F2EA] border-t border-neutral-200">
      <div className="max-w-4xl mx-auto px-6 text-center">
        <div className="w-12 h-12 rounded-2xl bg-white border border-neutral-300/80 shadow-sm flex items-center justify-center mx-auto mb-8 text-amber-700">
          <Quote className="w-6 h-6" />
        </div>

        <blockquote className="text-2xl sm:text-3xl md:text-4xl font-semibold text-neutral-900 tracking-tight leading-snug mb-8 text-balance">
          “Firstlook replaced three disconnected tools for our firm. We now receive verified diligence memos in hours, while our partners can instantly see who actually holds the strongest warm intro to a founder.”
        </blockquote>

        <div className="flex flex-col items-center">
          <div className="font-bold text-neutral-900 text-base">
            Sarah Chen
          </div>
          <div className="text-neutral-500 text-sm mt-0.5">
            General Partner · Horizon Ventures (Fund II, $60M)
          </div>
          <div className="mt-3 text-xs font-mono font-medium text-amber-800 bg-amber-100/70 border border-amber-200/60 px-3 py-1 rounded-full">
            Early Design Partner Fund
          </div>
        </div>
      </div>
    </section>
  );
};
