import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Threat Exposure Score — CAZO Docs",
  description: "What factors go into your risk score and why it changes between scans.",
};

export default function ThreatScoreDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="font-display text-3xl font-semibold text-foreground">
          Understanding your Threat Exposure Score
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Your Threat Exposure Score is a composite risk rating based on what
          CAZO has found across your attack surface. It&rsquo;s a starting point
          for prioritization &mdash; not a guarantee of safety or danger.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          What goes into the score
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          The score considers several factors, weighted by severity:
        </p>
        <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-signal-red" />
            <span>
              <strong className="text-foreground">Critical and high findings:</strong>{" "}
              Confirmed vulnerabilities (exposed AWS keys, leaked environment
              files, etc.) carry the most weight.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-signal-red" />
            <span>
              <strong className="text-foreground">Open ports and exposed services:</strong>{" "}
              The more services visible on the public internet, the larger your
              attack surface.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              <strong className="text-foreground">Certificate issues:</strong>{" "}
              Expired or soon-to-expire certificates, certificates with
              unexpected SANs.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              <strong className="text-foreground">Shadow assets:</strong>{" "}
              Unconfirmed infrastructure that probably belongs to you but
              isn&rsquo;t monitored.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-signal" />
            <span>
              <strong className="text-foreground">Technology exposure:</strong>{" "}
              Known software versions with published CVEs, outdated
              configurations.
            </span>
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Why it changes
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          Your score updates whenever new scan data comes in. It can change
          because:
        </p>
        <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>A new scan discovers additional assets or services</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>A new vulnerability is published against technology you use</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>A certificate expires or enters its renewal window</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>A previously confirmed finding is no longer present</span>
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          How to read it
        </h2>
        <div className="mt-3 space-y-2 text-sm text-muted-foreground">
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-success" />
            <span>
              <strong className="text-foreground">0–25 (Low):</strong> Your
              surface is relatively clean. Keep monitoring.
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-warning" />
            <span>
              <strong className="text-foreground">26–50 (Moderate):</strong>{" "}
              Some areas need attention. Review findings and prioritize.
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-warning" />
            <span>
              <strong className="text-foreground">51–75 (Elevated):</strong>{" "}
              Significant exposure. Investigate critical findings first.
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-destructive" />
            <span>
              <strong className="text-foreground">76–100 (Critical):</strong>{" "}
              Urgent. High-severity findings or large exposed surface. Act now.
            </span>
          </div>
        </div>

        <div className="mt-6 rounded-lg border border-warning/20 bg-warning/5 p-4">
          <p className="text-sm text-muted-foreground">
            <strong className="text-foreground">Honest caveat:</strong> The score
            is directional, not absolute. A low score doesn&rsquo;t mean
            you&rsquo;re invincible, and a high score doesn&rsquo;t mean
            you&rsquo;re already compromised. Use it to prioritize, not to
            conclude.
          </p>
        </div>

        <div className="mt-10 rounded-xl border border-border/50 bg-card/40 p-5">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
            <Link href="/docs/shadow-assets" className="text-phosphor hover:underline">
              What is a Shadow Asset?
            </Link>{" "}
            &middot;{" "}
            <Link href="/docs/unverified-cves" className="text-phosphor hover:underline">
              What &ldquo;unverified&rdquo; means on a CVE
            </Link>
          </p>
        </div>
      </article>
    </DocsLayout>
  );
}
