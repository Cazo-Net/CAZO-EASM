import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Exposure Validation — CAZO Docs",
  description: "How CAZO validates real exposures vs. theoretical vulnerabilities.",
};

export default function ExposureValidationDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="text-3xl font-semibold text-foreground">
          Exposure Validation
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          CAZO doesn&rsquo;t just tell you what <em>might</em> be wrong — it
          validates whether a finding is a real exposure. The exposure validation
          scanner probes your infrastructure to confirm actual
          misconfigurations, not just theoretical ones.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          What it checks
        </h2>
        <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-signal-red" />
            <span>
              <strong className="text-foreground">Sensitive file detection:</strong>{" "}
              Probes 50+ common paths (.env, .git, backup files, debug
              endpoints, admin panels).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-signal-red" />
            <span>
              <strong className="text-foreground">Security header audit:</strong>{" "}
              Checks for HSTS, CSP, X-Content-Type-Options, X-Frame-Options,
              and 3 more security headers.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              <strong className="text-foreground">CORS misconfiguration:</strong>{" "}
              Tests wildcard origins, null origins, reflected origins, and
              credentials flag handling.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              <strong className="text-foreground">Open redirect detection:</strong>{" "}
              Tests 9 common URL parameters (url, next, redirect, return,
              continue, goto, redir, dest, destination).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              <strong className="text-foreground">Subdomain takeover:</strong>{" "}
              Checks for dangling CNAMEs against 40+ vulnerable services
              (GitHub Pages, Heroku, AWS, Azure, Shopify, etc.).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-signal" />
            <span>
              <strong className="text-foreground">SSRF surface mapping:</strong>{" "}
              Probes 25 common paths that are vulnerable to Server-Side Request
              Forgery.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-neon-violet" />
            <span>
              <strong className="text-foreground">SSL/TLS validation:</strong>{" "}
              Checks certificate expiry, weak protocols, and cipher strength.
            </span>
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Why validation matters
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          Most vulnerability scanners report theoretical issues. &ldquo;This
          software version has CVE-2024-XXXXX&rdquo; doesn&rsquo;t mean
          it&rsquo;s actually exploitable on <em>your</em> host. CAZO goes
          further by actively probing to confirm whether a misconfiguration
          actually exists. This dramatically reduces false positives and lets
          you focus on real exposures.
        </p>

        <div className="mt-10 rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
            <Link href="/docs/unverified-cves" className="text-phosphor hover:underline">
              What &ldquo;unverified&rdquo; means on a CVE
            </Link>{" "}
            &middot;{" "}
            <Link href="/docs/threat-score" className="text-phosphor hover:underline">
              Threat Exposure Score
            </Link>
          </p>
        </div>
      </article>
    </DocsLayout>
  );
}
