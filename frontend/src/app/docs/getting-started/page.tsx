import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Getting Started — CAZO Docs",
  description: "Quick start guide to running your first scan and understanding your results.",
};

export default function GettingStartedDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="font-display text-3xl font-semibold text-foreground">
          Getting Started
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          This guide walks you through your first scan and explains how to read
          the results.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Step 1: Add an authorized scope
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          Before scanning, you need to declare what you&rsquo;re authorized to
          test. CAZO enforces scopes server-side — no scan runs against a target
          that isn&rsquo;t in your scope.
        </p>
        <ol className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">1.</span>
            <span>
              Go to <strong className="text-foreground">Scans → Authorized Scopes</strong>.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">2.</span>
            <span>
              Click <strong className="text-foreground">Add Scope</strong> and enter your
              domain (e.g., <code className="text-xs text-foreground/70">example.com</code>).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">3.</span>
            <span>
              Use <code className="text-xs text-foreground/70">*.example.com</code> as a
              wildcard to cover all subdomains.
            </span>
          </li>
        </ol>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Step 2: Run a scan
        </h2>
        <ol className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">1.</span>
            <span>
              Go to <strong className="text-foreground">Scans → New Scan</strong>.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">2.</span>
            <span>
              Enter your target domain and select <strong className="text-foreground">Full Scan</strong>.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">3.</span>
            <span>
              Click <strong className="text-foreground">Start Scan</strong>. The scan runs
              in the background — you can track progress in real time.
            </span>
          </li>
        </ol>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Step 3: Read your results
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          Once the scan completes, review these key areas:
        </p>
        <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              <strong className="text-foreground">Dashboard:</strong> Your
              overall risk score, subdomain count, open ports, and findings at a
              glance.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-signal" />
            <span>
              <strong className="text-foreground">Vulnerabilities:</strong>{" "}
              Prioritized findings with severity, confidence level, and
              evidence.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-neon-violet" />
            <span>
              <strong className="text-foreground">Shadow Assets:</strong>{" "}
              Discovered resources you may not have inventoried.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              <strong className="text-foreground">Supply Chain:</strong> Third-party
              vendors and concentration risk.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-signal-red" />
            <span>
              <strong className="text-foreground">Attack Graph:</strong>{" "}
              Visual map of how your assets connect.
            </span>
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Step 4: Set up monitoring
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          For ongoing visibility, configure:
        </p>
        <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-green-400" />
            <span>
              <strong className="text-foreground">Scheduled scans:</strong>{" "}
              Set up recurring scans to catch new assets and changes.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-green-400" />
            <span>
              <strong className="text-foreground">Webhooks:</strong> Get
              notified when scans complete or critical findings appear.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-green-400" />
            <span>
              <strong className="text-foreground">Integrations:</strong> Push
              findings to your SIEM or ticketing system.
            </span>
          </li>
        </ul>

        <div className="mt-10 rounded-xl border border-border/50 bg-card/40 p-5">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
            <Link href="/docs/authorized-scope" className="text-phosphor hover:underline">
              Authorized Scope
            </Link>{" "}
            &middot;{" "}
            <Link href="/docs/threat-score" className="text-phosphor hover:underline">
              Threat Exposure Score
            </Link>{" "}
            &middot;{" "}
            <Link href="/docs/shadow-assets" className="text-phosphor hover:underline">
              What is a Shadow Asset?
            </Link>
          </p>
        </div>
      </article>
    </DocsLayout>
  );
}
