import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Documentation — CAZO EASM",
  description: "Learn how CAZO works, what the terms mean, and how to get the most from your external attack surface management.",
};

export default function DocsIndexPage() {
  return (
    <DocsLayout>
      <div className="max-w-2xl">
        <h1 className="font-display text-3xl font-semibold text-foreground">
          Documentation
        </h1>
        <p className="mt-3 text-base text-muted-foreground">
          Plain-language explanations of how CAZO works, what the terms mean, and
          how to get the most from your external attack surface management.
        </p>
      </div>

      {/* Quick start */}
      <div className="mt-10 rounded-xl border border-phosphor/20 bg-phosphor/5 p-5">
        <h2 className="text-sm font-semibold text-phosphor mb-2">New to CAZO?</h2>
        <p className="text-xs text-muted-foreground mb-3">
          Start here to run your first scan and understand your results.
        </p>
        <Link
          href="/docs/getting-started"
          className="text-sm font-medium text-phosphor hover:underline"
        >
          Getting Started Guide →
        </Link>
      </div>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <Link
          href="/docs/getting-started"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            Getting Started
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            Run your first scan in 3 minutes. Add a scope, click scan, read results.
          </p>
        </Link>

        <Link
          href="/docs/blockchain-intel"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            Blockchain Intelligence
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            Cross-chain wallet analysis, entity attribution, and sanctions screening across 10 blockchains.
          </p>
        </Link>

        <Link
          href="/docs/supply-chain"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            Supply Chain Intelligence
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            Third-party vendor detection, concentration risk, and dependency mapping.
          </p>
        </Link>

        <Link
          href="/docs/exposure-validation"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            Exposure Validation
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            How CAZO validates real exposures vs. theoretical vulnerabilities.
          </p>
        </Link>

        <Link
          href="/docs/webhooks"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            Webhooks
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            Real-time event notifications when scans complete, findings appear, or risk scores change.
          </p>
        </Link>

        <Link
          href="/docs/integrations"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            Integrations
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            Connect with Splunk, Elastic, Sentinel, Jira, Slack, and Teams.
          </p>
        </Link>

        <Link
          href="/docs/shadow-assets"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            What is a Shadow Asset?
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            The assets you forgot you own — how they&rsquo;re discovered and what the confidence score means.
          </p>
        </Link>

        <Link
          href="/docs/threat-score"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            Threat Exposure Score
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            What factors go into your risk score and why it changes between scans.
          </p>
        </Link>

        <Link
          href="/docs/unverified-cves"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            What &ldquo;unverified&rdquo; means on a CVE
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            Version-correlation vs. exploit-verification — and why we label them differently.
          </p>
        </Link>

        <Link
          href="/docs/evidence-panel"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            Reading the Evidence Panel
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            What discovery method, first seen, and confirming scans tell you.
          </p>
        </Link>

        <Link
          href="/docs/authorized-scope"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            Authorized Scope
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            What it is, why you need it, and how enforcement works.
          </p>
        </Link>

        <Link
          href="/docs/scan-statuses"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            Why &ldquo;blocked by CDN&rdquo;?
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            Honest status badges — why we report failures instead of hiding them.
          </p>
        </Link>

        <Link
          href="/docs/glossary"
          className="group rounded-xl border border-border/50 bg-card/40 p-5 transition-colors hover:border-phosphor/30 sm:col-span-2"
        >
          <h3 className="text-sm font-semibold text-foreground group-hover:text-phosphor">
            Glossary
          </h3>
          <p className="mt-1.5 text-xs text-muted-foreground">
            Short, plain-language definitions of the technical terms used throughout CAZO.
          </p>
        </Link>
      </div>
    </DocsLayout>
  );
}
