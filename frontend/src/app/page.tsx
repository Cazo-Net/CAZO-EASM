"use client";

import { useEffect, useRef, useState } from "react";
import { Hero } from "@/components/marketing/Hero";
import {
  LandingNav,
  MetricsBarSection,
  TrustSection,
  HowItWorksSection,
  ShadowAssetsSection,
  ProductPreviewSection,
  HonestReportingSection,
  ComparisonSection,
  FaqSection,
  FinalCtaSection,
  LandingFooter,
} from "@/components/marketing/LandingSections";

export default function LandingPage() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => setScrolled(el.scrollTop > 8);
    onScroll();
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      ref={scrollRef}
      className="dark h-screen overflow-y-auto scroll-smooth bg-void text-foreground"
    >
      <LandingNav scrolled={scrolled} />
      <main>
        <Hero />
        <MetricsBarSection />
        <HowItWorksSection />
        <TrustSection />
        <ShadowAssetsSection />
        <ProductPreviewSection />
        <HonestReportingSection />
        <ComparisonSection />
        <FaqSection />
        <FinalCtaSection />
      </main>
      <LandingFooter />
    </div>
  );
}
