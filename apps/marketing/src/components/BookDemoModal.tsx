import React, { useState } from 'react';
import { X, Calendar, Clock, CheckCircle2, Shield, ArrowRight } from 'lucide-react';
import { LogoMark } from './Logo';

interface BookDemoModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const BookDemoModal: React.FC<BookDemoModalProps> = ({ isOpen, onClose }) => {
  const [step, setStep] = useState<'form' | 'success'>('form');
  const [formData, setFormData] = useState({
    fullName: '',
    workEmail: '',
    fundName: '',
    fundSize: '$50M - $150M',
    stage: 'Seed to Series A',
    timeSlot: 'Thursday, 2:00 PM EST',
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setStep('success');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/60 backdrop-blur-sm animate-in fade-in">
      <div className="bg-[#FAF8F5] border border-neutral-300 rounded-3xl w-full max-w-lg overflow-hidden shadow-2xl relative">
        {/* Header */}
        <div className="px-6 sm:px-8 pt-6 sm:pt-8 pb-4 flex items-center justify-between border-b border-neutral-200">
          <div className="flex items-center gap-2">
            <LogoMark />
            <span className="font-extrabold text-lg text-neutral-900">Firstlook</span>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-neutral-200/80 hover:bg-neutral-300 flex items-center justify-center text-neutral-600 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 sm:p-8">
          {step === 'form' ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <h3 className="text-2xl font-bold text-neutral-900 tracking-tight">
                  Schedule a private walkthrough
                </h3>
                <p className="text-xs sm:text-sm text-neutral-600 mt-1">
                  See how Firstlook maps your team's network, extracts cited memos, and automates portfolio tracking.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">
                    Your Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Alex Morgan"
                    value={formData.fullName}
                    onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">
                    Fund Work Email
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="alex@horizonvc.com"
                    value={formData.workEmail}
                    onChange={(e) => setFormData({ ...formData, workEmail: e.target.value })}
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">
                    Fund Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Horizon Seed Fund"
                    value={formData.fundName}
                    onChange={(e) => setFormData({ ...formData, fundName: e.target.value })}
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">
                    Fund AUM Size
                  </label>
                  <select
                    value={formData.fundSize}
                    onChange={(e) => setFormData({ ...formData, fundSize: e.target.value })}
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  >
                    <option>&lt; $25M (Micro Seed)</option>
                    <option>$25M - $75M (Seed)</option>
                    <option>$75M - $200M (Seed / Series A)</option>
                    <option>$200M+ (Multi-stage)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-700 mb-1">
                  Select Preferred Demo Window
                </label>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {['Thursday, 2:00 PM EST', 'Friday, 11:00 AM EST', 'Monday, 3:30 PM EST', 'Next Available Slot'].map((slot) => (
                    <button
                      type="button"
                      key={slot}
                      onClick={() => setFormData({ ...formData, timeSlot: slot })}
                      className={`p-2.5 rounded-xl border text-left font-medium transition-all ${
                        formData.timeSlot === slot
                          ? 'bg-neutral-900 text-white border-neutral-900'
                          : 'bg-white text-neutral-700 border-neutral-200 hover:border-neutral-400'
                      }`}
                    >
                      {slot}
                    </button>
                  ))}
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  className="w-full py-3.5 px-4 rounded-full bg-neutral-950 hover:bg-neutral-800 text-white font-bold text-sm shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  <span>Confirm Demo Reservation</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>

              <div className="flex items-center justify-center gap-1.5 text-[11px] text-neutral-500 pt-1">
                <Shield className="w-3.5 h-3.5 text-emerald-600" />
                <span>NDA protected · Zero sales spam · Partner-led walkthrough</span>
              </div>
            </form>
          ) : (
            <div className="text-center py-6">
              <div className="w-14 h-14 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <h3 className="text-2xl font-bold text-neutral-900 mb-2">
                Demo Invitation Confirmed
              </h3>
              <p className="text-sm text-neutral-600 mb-6 max-w-sm mx-auto">
                We've sent a calendar invitation and private NDA link to{' '}
                <strong className="text-neutral-900">{formData.workEmail || 'your email'}</strong> for{' '}
                <span className="font-semibold text-neutral-900">{formData.timeSlot}</span>.
              </p>

              <div className="p-4 bg-white rounded-2xl border border-neutral-200 text-xs text-left mb-6 space-y-1.5">
                <div className="font-semibold text-neutral-900">Walkthrough Agenda:</div>
                <div className="text-neutral-600">• 15m: Private knowledge graph & warm path discovery</div>
                <div className="text-neutral-600">• 15m: Live diligence deck parsing & cited fact sheet demo</div>
                <div className="text-neutral-600">• 15m: Automated founder KPI intake & LP letter generation</div>
              </div>

              <button
                onClick={() => {
                  setStep('form');
                  onClose();
                }}
                className="w-full py-3 rounded-full bg-neutral-900 text-white font-semibold text-sm hover:bg-neutral-800"
              >
                Close & Return
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
