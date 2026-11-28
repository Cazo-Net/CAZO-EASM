import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Reading the Evidence Panel — CAZO Docs",
  description: "What discovery method, first seen, and confirming scans tell you about an asset.",
};

export default function EvidencePanelDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="text-3xl font-semibold text-foreground">
          Reading the Evidence Panel
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Every asset in CAZO has an Evidence Panel — a summary of how it was
          discovered, when it first appeared, and how often it&rsquo;s been
          confirmed. This is the provenance data that makes CAZO&rsquo;s
          findings trustworthy.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Discovery method
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          This tells you how CAZO originally found the asset. Common methods:
        </p>
        <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              <strong className="text-foreground">crt.sh:</strong> Found via
              Certificate Transparency logs. The asset appeared on a certificate
              that also covers your confirmed domains.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-signal" />
            <span>
              <strong className="text-foreground">DNS brute-force:</strong>{" "}
              CAZO systematically queried subdomain names and found this one
              resolving.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-neon-violet" />
            <span>
              <strong className="text-foreground">Passive DNS:</strong> Found
              through historical DNS records — this domain has pointed to IPs
              associated with your infrastructure.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              <strong className="text-foreground">Shadow correlation:</strong>{" "}
              Inferred through shared infrastructure (IP, certificate, or ASN)
              with your confirmed assets.
            </span>
          </li>
        </ul>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          The discovery method matters because it tells you the basis for the
          finding. A crt.sh discovery is strong evidence of association. A
          shared-IP discovery on shared hosting is weaker.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          First seen
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          The date and time CAZO first discovered this asset, along with the
          scan number that found it. This gives you:
        </p>
        <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              A timeline for when this asset appeared on your perimeter
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              A reference point for investigating when a configuration changed
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              Evidence of how long an asset has been exposed (if it was first
              seen 6 months ago and nobody noticed, that&rsquo;s a finding in
              itself)
            </span>
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Confirming scans
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          This shows how many times CAZO has re-verified the asset since
          discovery. For example: &ldquo;3 of 3 &middot; last 30d&rdquo; means
          the asset was checked 3 times in the last 30 days, and all 3 confirmed
          it&rsquo;s still live.
        </p>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          If an asset stops being confirmed, CAZO updates its status. This helps
          you distinguish between assets that are actively maintained and ones
          that have quietly gone offline.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Why this matters
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          Most security tools give you a list of findings and ask you to trust
          them. CAZO shows you the evidence chain so you can verify each finding
          yourself. When you hand a finding to your team or your auditor, the
          provenance comes with it.
        </p>

        <div className="mt-10 rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
            <Link href="/docs/shadow-assets" className="text-phosphor hover:underline">
              What is a Shadow Asset?
            </Link>{" "}
            &middot;{" "}
            <Link href="/docs/scan-statuses" className="text-phosphor hover:underline">
              Why &ldquo;blocked by CDN&rdquo;?
            </Link>
          </p>
        </div>
      </article>
    </DocsLayout>
  );
}
