"use client";

import { useEffect, useRef, useState } from "react";
import { HeroSequence } from "@/components/marketing/HeroSequence";
import { LivingInternet } from "@/components/marketing/living-internet/LivingInternet";
import { LandingIntro } from "@/components/marketing/LandingIntro";
import {
  LandingNav,
  MetricsBarSection,
  TrustSection,
  HowItWorksSection,
  ShadowAssetsSection,
  ProductPreviewSection,
  HonestReportingSection,
  ComparisonSection,
  SocialProofSection,
  FaqSection,
  FinalCtaSection,
  LandingFooter,
} from "@/components/marketing/LandingSections";

export default function LandingPage() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrolled, setScrolled] = useState(false);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      setScrolled(el.scrollTop > 8);
      const max = el.scrollHeight - el.clientHeight;
      setProgress(max > 0 ? el.scrollTop / max : 0);
    };
    onScroll();
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      ref={scrollRef}
      className="h-screen overflow-y-auto bg-void text-foreground"
    >
      <LandingIntro />

      <LandingNav scrolled={scrolled} progress={progress} />

      {/* Living Internet background — a sticky first viewport that pins while the
          hero scrolls, then the negative margin lets the hero overlap it. */}
      <div className="pointer-events-none sticky top-0 z-0 h-screen w-full">
        <LivingInternet scrollContainerRef={scrollRef} />
      </div>

      <div className="relative z-10 -mt-[100vh]">
        <HeroSequence scrollContainerRef={scrollRef} />
      </div>

      <MetricsBarSection />
      <TrustSection />
      <HowItWorksSection />
      <ShadowAssetsSection />
      <ProductPreviewSection />
      <HonestReportingSection />
      <ComparisonSection />
      <SocialProofSection />
      <FaqSection />
      <FinalCtaSection />
      <LandingFooter />
    </div>
  );
}
