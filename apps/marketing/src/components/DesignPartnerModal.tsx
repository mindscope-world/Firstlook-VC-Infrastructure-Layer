import React, { useState } from 'react';
import { X, Sparkles, CheckCircle2, ArrowRight, ShieldCheck } from 'lucide-react';
import { LogoMark } from './Logo';

interface DesignPartnerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DesignPartnerModal: React.FC<DesignPartnerModalProps> = ({ isOpen, onClose }) => {
  const [submitted, setSubmitted] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    fund: '',
    stage: 'Seed to Series A',
    crm: 'Affinity',
    primaryGoal: 'Relationship intelligence & warm intro discovery',
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/70 backdrop-blur-sm animate-in fade-in">
      <div className="bg-[#FAF8F5] border border-neutral-300 rounded-3xl w-full max-w-lg overflow-hidden shadow-2xl relative">
        {/* Header */}
        <div className="px-6 sm:px-8 pt-6 sm:pt-8 pb-4 flex items-center justify-between border-b border-neutral-200">
          <div className="flex items-center gap-2">
            <LogoMark />
            <span className="font-extrabold text-lg text-neutral-900">Design Partner Intake</span>
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
          {!submitted ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-800 bg-amber-100/70 px-2.5 py-0.5 rounded-full mb-2">
                  <Sparkles className="w-3 h-3 text-amber-600" />
                  Cohort 2 (Limited to 8 Funds)
                </div>
                <h3 className="text-2xl font-bold text-neutral-900 tracking-tight">
                  Shape the future of venture intelligence
                </h3>
                <p className="text-xs sm:text-sm text-neutral-600 mt-1">
                  Design partners receive white-glove migration, direct Slack channel with our engineering team, and custom memo template integration.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">
                    Your Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Maya Lin"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">
                    Fund Email
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="maya@summitcap.com"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
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
                    placeholder="e.g. Summit Capital"
                    value={formData.fund}
                    onChange={(e) => setFormData({ ...formData, fund: e.target.value })}
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">
                    Current CRM / Stack
                  </label>
                  <select
                    value={formData.crm}
                    onChange={(e) => setFormData({ ...formData, crm: e.target.value })}
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  >
                    <option>Affinity</option>
                    <option>Salesforce Ventures</option>
                    <option>HubSpot / Notion</option>
                    <option>Google Sheets / AirTable</option>
                    <option>Other Custom Stack</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-700 mb-1">
                  Primary Capability to Validate
                </label>
                <select
                  value={formData.primaryGoal}
                  onChange={(e) => setFormData({ ...formData, primaryGoal: e.target.value })}
                  className="w-full px-3.5 py-2 rounded-xl bg-white border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                >
                  <option>Relationship intelligence & warm intro discovery</option>
                  <option>Automated diligence memos with cited source slides</option>
                  <option>Founder KPI intake & runway risk monitoring</option>
                  <option>Emerging markets multi-currency & WhatsApp sync</option>
                  <option>Automated LP quarterly letter & fund returns</option>
                </select>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  className="w-full py-3.5 px-4 rounded-full bg-[#111317] hover:bg-neutral-800 text-white font-bold text-sm shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  <span>Submit Design Partner Application</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>

              <div className="flex items-center justify-center gap-1.5 text-[11px] text-neutral-500 pt-1">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span>Strict data confidentiality · Dedicated engineering sponsor</span>
              </div>
            </form>
          ) : (
            <div className="text-center py-6">
              <div className="w-14 h-14 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <h3 className="text-2xl font-bold text-neutral-900 mb-2">
                Application Received
              </h3>
              <p className="text-sm text-neutral-600 mb-6 max-w-sm mx-auto">
                Thank you, <strong className="text-neutral-900">{formData.name || 'Partner'}</strong>. Our founding team reviews design-partner submissions within 24 hours.
              </p>

              <div className="p-4 bg-white rounded-2xl border border-neutral-200 text-xs text-left mb-6 space-y-1.5">
                <div className="font-semibold text-neutral-900">What happens next:</div>
                <div className="text-neutral-600">1. We review your fund's existing stack ({formData.crm}).</div>
                <div className="text-neutral-600">2. Our CTO schedules a 20-minute architecture discovery call.</div>
                <div className="text-neutral-600">3. We provision your firm's isolated tenant enclave.</div>
              </div>

              <button
                onClick={() => {
                  setSubmitted(false);
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
