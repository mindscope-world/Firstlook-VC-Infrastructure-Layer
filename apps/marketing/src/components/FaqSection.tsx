import React, { useState } from 'react';
import { ChevronDown, HelpCircle } from 'lucide-react';

export const FaqSection: React.FC = () => {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const faqs = [
    {
      question: 'Does Firstlook replace our CRM?',
      answer:
        'It can. Firstlook is fully capable of operating as your firm’s primary source of truth, pipeline tracker, and relationship graph. It can also bi-directionally sync with your existing CRM (e.g. Affinity, Salesforce, HubSpot) during transition or as a continuous passive intelligence layer.',
    },
    {
      question: 'Is our data used to train AI models?',
      answer:
        'No. Your data is never used to train shared models. All infrastructure uses private tenant endpoints, and our underlying model providers operate under zero-retention agreements where prompts and context embeddings are discarded after inference.',
    },
    {
      question: 'How long does setup take?',
      answer:
        'Connecting email and calendar takes minutes via standard Google Workspace or Microsoft 365 OAuth. A full historical CRM and document migration typically takes 2–4 business days with dedicated engineering support from our onboarding team.',
    },
    {
      question: 'Can we control what gets synced?',
      answer:
        'Yes. You choose which mailboxes, domains, and labels are included. Personal email accounts, personal calendar entries, and whitelisted confidential internal domains are strictly excluded by default.',
    },
  ];

  const toggle = (idx: number) => {
    setOpenIndex(openIndex === idx ? null : idx);
  };

  return (
    <section id="faq" className="py-24 sm:py-32 bg-[#FAF8F5] border-t border-neutral-200">
      <div className="max-w-4xl mx-auto px-6">
        {/* Header */}
        <div className="mb-14 text-center sm:text-left">
          <div className="text-xs font-semibold uppercase tracking-widest text-amber-700 mb-3 flex items-center justify-center sm:justify-start gap-1.5">
            <HelpCircle className="w-3.5 h-3.5" />
            <span>Frequently Asked Questions</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-[#111317] tracking-tight mb-4">
            Everything you need to know.
          </h2>
          <p className="text-base sm:text-lg text-neutral-600 font-normal">
            Clear answers about data privacy, migration speed, and system integration.
          </p>
        </div>

        {/* FAQ Accordion List */}
        <div className="space-y-3">
          {faqs.map((faq, idx) => {
            const isOpen = openIndex === idx;
            return (
              <div
                key={idx}
                className="bg-white rounded-2xl border border-neutral-300/80 overflow-hidden transition-all duration-200 shadow-sm"
              >
                <button
                  onClick={() => toggle(idx)}
                  className="w-full px-6 py-5 text-left flex items-center justify-between gap-4 cursor-pointer hover:bg-neutral-50/50 transition-colors"
                  aria-expanded={isOpen}
                >
                  <span className="font-bold text-base sm:text-lg text-neutral-900">
                    {faq.question}
                  </span>
                  <div
                    className={`w-7 h-7 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-500 shrink-0 transition-transform duration-200 ${
                      isOpen ? 'rotate-180 bg-neutral-200 text-neutral-800' : ''
                    }`}
                  >
                    <ChevronDown className="w-4 h-4" />
                  </div>
                </button>

                {isOpen && (
                  <div className="px-6 pb-6 pt-1 text-sm sm:text-base text-neutral-600 leading-relaxed border-t border-neutral-100 font-normal">
                    {faq.answer}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
