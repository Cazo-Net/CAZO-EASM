import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: 'What "unverified" means on a CVE — CAZO Docs',
  description: "Why CAZO labels CVE findings as version-correlated vs. exploit-verified.",
};

export default function UnverifiedCvesDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="font-display text-3xl font-semibold text-foreground">
          What &ldquo;unverified&rdquo; means on a CVE finding
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          When CAZO reports a CVE (Common Vulnerability and Exposure), it labels
          each finding as either <strong className="text-phosphor">verified</strong> or{" "}
          <strong className="text-amber">unverified</strong>. This distinction
          matters, and we want you to understand what it means.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Version-correlated (unverified)
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          Most CVE findings in CAZO are <strong className="text-amber">version-correlated</strong>.
          This means:
        </p>
        <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              CAZO detected the software and version running on your service
              (e.g., nginx 1.24.0)
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              NVD (National Vulnerability Database) lists CVE-2026-XXXX as
              affecting that software version
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              CAZO correlates the two and reports: &ldquo;this version may be
              affected&rdquo;
            </span>
          </li>
        </ul>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          What this <strong>does not</strong> mean: it does not mean the
          vulnerability is actively exploitable on your host. It does not mean
          someone has exploited it. It means the version match is there and you
          should investigate.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Verified
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          A <strong className="text-phosphor">verified</strong> finding means
          CAZO directly observed evidence of the vulnerability — not just a
          version match. This includes:
        </p>
        <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              Exposed AWS credentials, environment files, or directory listings
              that were directly accessible
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              Security misconfigurations directly observed in HTTP headers or
              responses
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              Services returning sensitive data that shouldn&rsquo;t be public
            </span>
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Why we label them this way
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          We could label every CVE as &ldquo;confirmed&rdquo; and make our
          findings look more alarming. But that would be dishonest.
        </p>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          The reality is: version-correlation is useful but imprecise. A host
          running nginx 1.24.0 might have the CVE patched out-of-band, might
          have a WAF blocking exploitation, or might not even be using the
          affected module. Without checking the actual host, we can&rsquo;t
          tell.
        </p>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          So we tell you what we know and what we don&rsquo;t. Unverified means{" "}
          <em>&ldquo;investigate this.&rdquo;</em> Verified means{" "}
          <em>&ldquo;we saw it.&rdquo;</em>
        </p>

        <div className="mt-6 rounded-lg border border-phosphor/20 bg-phosphor/5 p-4">
          <p className="text-sm text-muted-foreground">
            <strong className="text-foreground">What to do:</strong> Treat
            unverified CVEs as a prioritization signal. Check whether the
            vulnerability applies to your specific configuration, whether
            you&rsquo;ve patched, and whether any compensating controls are in
            place. Don&rsquo;t ignore them — but don&rsquo;t panic either.
          </p>
        </div>

        <div className="mt-10 rounded-xl border border-border/50 bg-card/40 p-5">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
            <Link href="/docs/threat-score" className="text-phosphor hover:underline">
              Threat Exposure Score
            </Link>{" "}
            &middot;{" "}
            <Link href="/docs/evidence-panel" className="text-phosphor hover:underline">
              Reading the Evidence Panel
            </Link>
          </p>
        </div>
      </article>
    </DocsLayout>
  );
}
