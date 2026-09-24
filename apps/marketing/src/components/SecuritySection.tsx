import React from 'react';
import { Shield, KeyRound, Lock, UserCheck, FileCheck, Server, EyeOff, CheckCircle2 } from 'lucide-react';

export const SecuritySection: React.FC = () => {
  const securityFeatures = [
    {
      title: 'Dedicated Encryption Keys',
      description: 'Each firm’s data is isolated with customer-managed or firm-dedicated encryption keys (AES-256 at rest, TLS 1.3 in transit).',
      icon: KeyRound,
    },
    {
      title: 'Zero Shared Model Training',
      description: 'Your deal flow, pitch decks, cap tables, and correspondence are strictly isolated. No data is ever fed into shared LLM models.',
      icon: EyeOff,
    },
    {
      title: 'Enterprise SSO & Granular RBAC',
      description: 'Okta, SAML 2.0, Google Workspace, and Microsoft Azure AD integration with deal-level read/write permissions.',
      icon: UserCheck,
    },
    {
      title: 'Full Tamper-Proof Audit Logs',
      description: 'Every search, file view, export, and copilot generation is immutably logged with timestamp and user attribution.',
      icon: FileCheck,
    },
    {
      title: 'Global Compliance (GDPR & Kenya DPA)',
      description: 'Full compliance with GDPR and the Kenya Data Protection Act, supporting cross-border venture funds with local jurisdiction safeguards.',
      icon: Lock,
    },
    {
      title: 'Single-Tenant Deployment Available',
      description: 'Host Firstlook in your own VPC (AWS, GCP, Azure) or a fully dedicated private cloud with SOC 2 compliance on the roadmap.',
      icon: Server,
    },
  ];

  return (
    <section id="security" className="py-24 sm:py-32 bg-[#FAF8F5] border-t border-neutral-200">
      <div className="max-w-6xl mx-auto px-6">
        {/* Header */}
        <div className="max-w-3xl mb-16">
          <div className="text-xs font-semibold uppercase tracking-widest text-amber-700 mb-3 flex items-center gap-2">
            <Shield className="w-3.5 h-3.5" />
            <span>Institutional-Grade Privacy</span>
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-[#111317] tracking-tight mb-5 leading-tight text-balance">
            Built for the most confidential data you hold.
          </h2>
          <p className="text-lg text-neutral-600 leading-relaxed font-normal">
            Each firm's data is isolated with its own encryption keys. The platform supports SSO, deal-level permissions and full audit logs, and complies with GDPR and the Kenya Data Protection Act. Single-tenant deployment is available, and SOC 2 certification is on the roadmap.
          </p>
        </div>

        {/* Security Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {securityFeatures.map((feat, idx) => {
            const Icon = feat.icon;
            return (
              <div
                key={idx}
                className="p-7 rounded-3xl bg-white border border-neutral-300/80 shadow-sm flex flex-col justify-between"
              >
                <div>
                  <div className="w-10 h-10 rounded-2xl bg-neutral-100 border border-neutral-200 flex items-center justify-center text-neutral-800 mb-5">
                    <Icon className="w-5 h-5 text-amber-700" />
                  </div>
                  <h3 className="text-lg font-bold text-neutral-900 mb-2.5">
                    {feat.title}
                  </h3>
                  <p className="text-sm text-neutral-600 leading-relaxed font-normal">
                    {feat.description}
                  </p>
                </div>

                <div className="mt-6 pt-4 border-t border-neutral-100 flex items-center gap-2 text-xs font-medium text-emerald-700">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Enforced by policy</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Certifications Banner */}
        <div className="mt-10 p-6 rounded-2xl bg-[#EFECE5] border border-neutral-300 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs sm:text-sm text-neutral-700">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="font-semibold text-neutral-900">Compliance Standard:</span>
            <span>GDPR Ready · Kenya Data Protection Act Compliant · SOC 2 Type II in Progress</span>
          </div>
          <div className="text-xs font-mono font-medium text-neutral-500">
            Zero-retention model agreements in place
          </div>
        </div>
      </div>
    </section>
  );
};
