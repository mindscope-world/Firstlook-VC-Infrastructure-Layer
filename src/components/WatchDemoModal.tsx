import React, { useState } from 'react';
import { X, Play, CheckCircle2, ChevronRight, FileText, Users, AlertTriangle, Shield } from 'lucide-react';

interface WatchDemoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onBookDemo: () => void;
}

export const WatchDemoModal: React.FC<WatchDemoModalProps> = ({
  isOpen,
  onClose,
  onBookDemo,
}) => {
  const [activeTourIndex, setActiveTourIndex] = useState(0);

  if (!isOpen) return null;

  const tourSteps = [
    {
      title: 'Warm Path Discovery',
      badge: 'Relationship Graph',
      description:
        'Firstlook monitors team communication to expose who has the strongest historical tie to a target company before reaching out cold.',
      visual: (
        <div className="space-y-3 bg-[#FAF9F5] p-4 rounded-2xl border border-neutral-200">
          <div className="text-xs font-semibold uppercase text-neutral-500">Query: Target founder (David Park, CEO at HyperScale)</div>
          <div className="p-3 bg-white rounded-xl border border-neutral-200 shadow-sm">
            <div className="flex items-center justify-between text-xs font-bold text-neutral-900 mb-1">
              <span>Warmest Intro: Partner Jason Vance</span>
              <span className="text-amber-700 bg-amber-100 px-2 py-0.5 rounded">98% Strength</span>
            </div>
            <p className="text-xs text-neutral-600">
              Co-founded previous entity with Jason's portfolio CEO; 12 direct threads indexed.
            </p>
          </div>
          <div className="text-[11px] text-emerald-700 bg-emerald-50 p-2 rounded-lg border border-emerald-200 font-mono">
            ✓ Recommended action: 1-click intro dispatch template queued
          </div>
        </div>
      )
    },
    {
      title: 'Diligence Copilot & Citation Inspector',
      badge: 'Zero Hallucinations',
      description:
        'Drop in raw pitch decks and financial models. Firstlook drafts an IC memo where every claim links directly to the cited slide or spreadsheet cell.',
      visual: (
        <div className="space-y-3 bg-[#FAF9F5] p-4 rounded-2xl border border-neutral-200">
          <div className="text-xs font-semibold uppercase text-neutral-500">IC Draft Verification</div>
          <div className="p-3 bg-white rounded-xl border border-neutral-200 shadow-sm space-y-2">
            <div className="text-xs font-medium text-neutral-800">
              “ARR grew from $400k to $2.1M (5.2x YoY) with 14% gross margin expansion.”
            </div>
            <div className="text-[11px] font-mono text-neutral-500 bg-neutral-100 p-2 rounded flex items-center justify-between">
              <span>Source: Pitch_Deck_vFinal.pdf (Slide 11)</span>
              <span className="text-emerald-600 font-bold">MATCH</span>
            </div>
          </div>
          <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-[11px] text-rose-800 flex items-center justify-between">
            <span>Discrepancy: Deck claims 120 customers vs 94 in raw cohort CSV</span>
            <span className="font-bold">Flagged for IC</span>
          </div>
        </div>
      )
    },
    {
      title: 'Portfolio Runway Early Alerting',
      badge: 'Continuous Monitoring',
      description:
        'Founders submit monthly KPIs in 60 seconds. Firstlook normalizes currencies and flags burn anomalies before board meetings.',
      visual: (
        <div className="space-y-3 bg-[#FAF9F5] p-4 rounded-2xl border border-neutral-200">
          <div className="text-xs font-semibold uppercase text-neutral-500">Autonomous Sentinel Alert</div>
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl space-y-1">
            <div className="flex items-center justify-between text-xs font-bold text-amber-900">
              <span>NovaPay (Series Seed)</span>
              <span>4.8 Months Runway</span>
            </div>
            <div className="text-xs text-neutral-700">
              Monthly burn accelerated by $45,000 following engineering expansion in Nairobi.
            </div>
          </div>
          <div className="p-2.5 bg-white border border-neutral-200 rounded-xl text-xs text-neutral-600 flex justify-between items-center">
            <span>Recommended bridge or Series A prep date</span>
            <span className="font-bold text-neutral-900 font-mono">Nov 15, 2026</span>
          </div>
        </div>
      )
    }
  ];

  const currentTour = tourSteps[activeTourIndex];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/70 backdrop-blur-md animate-in fade-in">
      <div className="bg-white border border-neutral-300 rounded-3xl w-full max-w-2xl overflow-hidden shadow-2xl relative">
        {/* Header */}
        <div className="px-6 py-4 flex items-center justify-between border-b border-neutral-200 bg-[#FAF8F5]">
          <div className="flex items-center gap-2">
            <span className="relative flex items-center justify-center w-5 h-5 rounded-full border-[2.2px] border-[#F97316]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#F97316]" />
            </span>
            <span className="font-bold text-sm text-neutral-900">
              Interactive Product Walkthrough
            </span>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-neutral-200 hover:bg-neutral-300 flex items-center justify-center text-neutral-600 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tour Navigation */}
        <div className="grid grid-cols-3 border-b border-neutral-200 text-xs font-medium">
          {tourSteps.map((step, idx) => (
            <button
              key={idx}
              onClick={() => setActiveTourIndex(idx)}
              className={`py-3 px-2 text-center transition-all ${
                activeTourIndex === idx
                  ? 'border-b-2 border-amber-500 font-bold text-neutral-900 bg-amber-50/50'
                  : 'text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50'
              }`}
            >
              0{idx + 1}. {step.badge}
            </button>
          ))}
        </div>

        {/* Main Content */}
        <div className="p-6 sm:p-8 space-y-6">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-amber-700 mb-1">
              Capability 0{activeTourIndex + 1}
            </div>
            <h3 className="text-2xl font-bold text-neutral-900 mb-2">
              {currentTour.title}
            </h3>
            <p className="text-sm text-neutral-600 leading-relaxed font-normal">
              {currentTour.description}
            </p>
          </div>

          {/* Interactive visual frame */}
          <div>{currentTour.visual}</div>

          {/* Controls */}
          <div className="flex items-center justify-between pt-4 border-t border-neutral-200">
            <div className="flex gap-1.5">
              {tourSteps.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setActiveTourIndex(i)}
                  className={`w-2 h-2 rounded-full transition-all ${
                    activeTourIndex === i ? 'w-6 bg-amber-500' : 'bg-neutral-300'
                  }`}
                />
              ))}
            </div>

            <div className="flex items-center gap-3">
              {activeTourIndex < tourSteps.length - 1 ? (
                <button
                  onClick={() => setActiveTourIndex(activeTourIndex + 1)}
                  className="px-4 py-2 rounded-full bg-neutral-900 hover:bg-neutral-800 text-white text-xs font-semibold flex items-center gap-1.5"
                >
                  <span>Next Capability</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              ) : (
                <button
                  onClick={() => {
                    onClose();
                    onBookDemo();
                  }}
                  className="px-5 py-2.5 rounded-full bg-amber-500 hover:bg-amber-600 text-neutral-950 text-xs font-bold flex items-center gap-1.5 shadow-sm"
                >
                  <span>Schedule Full Team Demo</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
