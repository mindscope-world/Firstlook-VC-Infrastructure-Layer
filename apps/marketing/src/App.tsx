/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { HeroSection } from './components/HeroSection';
import { ProblemSection } from './components/ProblemSection';
import { FeaturesSection } from './components/FeaturesSection';
import { HowItWorksSection } from './components/HowItWorksSection';
import { WhyFirstlookSection } from './components/WhyFirstlookSection';
import { WhoItsForSection } from './components/WhoItsForSection';
import { SecuritySection } from './components/SecuritySection';
import { SocialProofSection } from './components/SocialProofSection';
import { PricingSection } from './components/PricingSection';
import { FaqSection } from './components/FaqSection';
import { FinalCtaSection } from './components/FinalCtaSection';
import { Footer } from './components/Footer';

import { BookDemoModal } from './components/BookDemoModal';
import { WatchDemoModal } from './components/WatchDemoModal';
import { DesignPartnerModal } from './components/DesignPartnerModal';
import { LoginModal } from './components/LoginModal';

export default function App() {
  const [bookDemoOpen, setBookDemoOpen] = useState(false);
  const [watchDemoOpen, setWatchDemoOpen] = useState(false);
  const [designPartnerOpen, setDesignPartnerOpen] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#FAF8F5] text-neutral-900 flex flex-col font-sans selection:bg-amber-200 selection:text-neutral-900">
      {/* Top Floating Navbar (matches PDF layout) */}
      <Navbar
        onBookDemo={() => setBookDemoOpen(true)}
        onLogin={() => setLoginOpen(true)}
      />

      {/* Hero Section with PDF Pixel Skyline & CTAs */}
      <main className="flex-grow">
        <HeroSection
          onBookDemo={() => setBookDemoOpen(true)}
          onWatchDemo={() => setWatchDemoOpen(true)}
          onApplyDesignPartner={() => setDesignPartnerOpen(true)}
        />

        {/* Problem Section: Speed is King / Fragmented vs Unified */}
        <ProblemSection />

        {/* Features Section: 5 Core Investment Lifecycle Pillars */}
        <FeaturesSection />

        {/* How It Works: Connect -> Unify -> Act */}
        <HowItWorksSection />

        {/* Why Firstlook: Citations, Human Control, Anywhere, Open, Emerging Markets */}
        <WhyFirstlookSection />

        {/* Who It's For: Partners, Associates, Platform, Finance & IR */}
        <WhoItsForSection />

        {/* Security: Confidentiality, Isolation, GDPR, Kenya DPA, SOC 2 */}
        <SecuritySection />

        {/* Social Proof: Design Partner Fund GP Testimonial */}
        <SocialProofSection />

        {/* Pricing & Access Tiers */}
        <PricingSection
          onApplyDesignPartner={() => setDesignPartnerOpen(true)}
          onBookDemo={() => setBookDemoOpen(true)}
        />

        {/* FAQ Accordion */}
        <FaqSection />

        {/* Final CTA: Onboarding Design-Partner Funds */}
        <FinalCtaSection
          onApplyDesignPartner={() => setDesignPartnerOpen(true)}
          onBookDemo={() => setBookDemoOpen(true)}
        />
      </main>

      {/* Quiet Footer */}
      <Footer />

      {/* Interactive Modals */}
      <BookDemoModal
        isOpen={bookDemoOpen}
        onClose={() => setBookDemoOpen(false)}
      />

      <WatchDemoModal
        isOpen={watchDemoOpen}
        onClose={() => setWatchDemoOpen(false)}
        onBookDemo={() => {
          setWatchDemoOpen(false);
          setBookDemoOpen(true);
        }}
      />

      <DesignPartnerModal
        isOpen={designPartnerOpen}
        onClose={() => setDesignPartnerOpen(false)}
      />

      <LoginModal
        isOpen={loginOpen}
        onClose={() => setLoginOpen(false)}
      />
    </div>
  );
}
