"use client";

/**
 * TEMPORARY review route for the hero scroll sequence, viewed in isolation.
 * Provides its own scroll container because the app shell sets
 * `overflow:hidden` on <body>. Remove once the hero is wired into `/`.
 */

import { useRef } from "react";
import { HeroSequence } from "@/components/marketing/HeroSequence";
import {
  TrustSection,
  HowItWorksSection,
  ShadowAssetsSection,
  ProductPreviewSection,
  HonestReportingSection,
  SocialProofSection,
  FinalCtaSection,
  LandingFooter,
} from "@/components/marketing/LandingSections";

export default function HeroPreviewPage() {
  const scrollRef = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={scrollRef}
      className="h-screen overflow-y-auto bg-void text-foreground"
    >
      {/* Intro block above the sequence so scroll behaviour matches the real page */}
      <section className="min-h-[70vh] flex flex-col items-center justify-center text-center px-6">
        <span className=" text-[11px] uppercase tracking-wide text-phosphor mb-4">
          hero sequence preview
        </span>
        <h1 className="text-4xl md:text-6xl font-semibold max-w-3xl leading-[1.05]">
          You can&apos;t defend what you forgot you own.
        </h1>
        <p className="mt-5 max-w-xl text-muted-foreground">
          CAZO maps your external attack surface — subdomains, ports, certs,
          services, misconfigurations — and shows the evidence behind every
          finding.
        </p>
        <p className="mt-10 font-mono text-[11px] text-muted-foreground animate-bounce">
          scroll to walk the sequence ↓
        </p>
      </section>

      <HeroSequence scrollContainerRef={scrollRef} />

      <TrustSection />

      <HowItWorksSection />

      <ShadowAssetsSection />

      <ProductPreviewSection />

      <HonestReportingSection />

      <SocialProofSection />

      <FinalCtaSection />

      <LandingFooter />
    </div>
  );
}
