import React, { useState } from 'react';
import { X, ArrowRight, Shield } from 'lucide-react';

// The product app's sign-in page. Sign-in happens there (dev login locally,
// WorkOS SSO when configured); this modal only hands off to it.
const APP_URL = (import.meta.env.VITE_APP_URL as string | undefined) ?? 'http://localhost:13000';

function goToApp(email?: string) {
  const url = new URL('/login', APP_URL);
  if (email) url.searchParams.set('email', email);
  window.location.href = url.toString();
}

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({ isOpen, onClose }) => {
  const [email, setEmail] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    goToApp(email);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/70 backdrop-blur-sm animate-in fade-in">
      <div className="bg-[#FAF8F5] border border-neutral-300 rounded-3xl w-full max-w-md overflow-hidden shadow-2xl relative">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 flex items-center justify-between border-b border-neutral-200">
          <div className="flex items-center gap-2">
            <span className="relative flex items-center justify-center w-5 h-5 rounded-full border-[2.2px] border-[#F97316]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#F97316]" />
            </span>
            <span className="font-extrabold text-lg text-neutral-900">Firstlook Portal</span>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-neutral-200 hover:bg-neutral-300 flex items-center justify-center text-neutral-600 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-bold text-neutral-900 tracking-tight">
                  Sign in to your firm's enclave
                </h3>
                <p className="text-xs text-neutral-600 mt-1">
                  Sign in with your firm's SSO or your work email. You'll go straight to your Firstlook workspace.
                </p>
              </div>

              {/* SSO Providers */}
              <div className="space-y-2 pt-2">
                <button
                  type="button"
                  onClick={() => goToApp()}
                  className="w-full py-2.5 px-4 rounded-xl bg-white hover:bg-neutral-50 border border-neutral-300 text-neutral-800 text-xs font-semibold flex items-center justify-center gap-2 transition-colors"
                >
                  <span className="font-bold text-blue-600">G</span>
                  <span>Continue with Google Workspace</span>
                </button>
                <button
                  type="button"
                  onClick={() => goToApp()}
                  className="w-full py-2.5 px-4 rounded-xl bg-white hover:bg-neutral-50 border border-neutral-300 text-neutral-800 text-xs font-semibold flex items-center justify-center gap-2 transition-colors"
                >
                  <span className="font-bold text-blue-500">M</span>
                  <span>Continue with Microsoft 365 / Azure AD</span>
                </button>
                <button
                  type="button"
                  onClick={() => goToApp()}
                  className="w-full py-2.5 px-4 rounded-xl bg-white hover:bg-neutral-50 border border-neutral-300 text-neutral-800 text-xs font-semibold flex items-center justify-center gap-2 transition-colors"
                >
                  <span className="font-bold text-neutral-900">O</span>
                  <span>Sign in with Okta SAML</span>
                </button>
              </div>

              <div className="relative flex items-center justify-center py-2">
                <div className="border-t border-neutral-200 w-full" />
                <span className="bg-[#FAF8F5] px-3 text-[11px] uppercase tracking-wider text-neutral-400 font-medium">
                  Or Email
                </span>
              </div>

              <form onSubmit={handleSubmit} className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-700 mb-1">
                    Partner / Analyst Email
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="name@fund.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full py-3 px-4 rounded-full bg-neutral-900 hover:bg-neutral-800 text-white font-semibold text-xs transition-colors flex items-center justify-center gap-2"
                >
                  <span>Continue to sign in</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </form>

              <div className="flex items-center justify-center gap-1.5 text-[11px] text-neutral-400 pt-2">
                <Shield className="w-3 h-3 text-emerald-600" />
                <span>Protected by firm-specific biometric and 2FA policies</span>
              </div>
            </div>
        </div>
      </div>
    </div>
  );
};
