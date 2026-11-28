import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Supply Chain Intelligence — CAZO Docs",
  description: "Third-party vendor analysis, concentration risk, and dependency mapping for your attack surface.",
};

export default function SupplyChainDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="text-3xl font-semibold text-foreground">
          Supply Chain Intelligence
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Every website depends on third-party services — analytics, CDNs,
          payment processors, chat widgets, authentication providers. CAZO
          identifies every external dependency in your stack, classifies it by
          risk, and maps concentration risk across your vendor portfolio.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          What CAZO detects
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          CAZO fingerprints 140+ technologies across 27 categories, including:
        </p>
        <div className="mt-4 grid grid-cols-2 gap-2 text-sm text-muted-foreground">
          {[
            "CDN & WAF",
            "Analytics & Tracking",
            "Payment Processors",
            "Authentication Providers",
            "CRM & Support",
            "Cloud Hosting",
            "Email Services",
            "A/B Testing",
            "Feature Flags",
            "Monitoring & APM",
            "CMS & E-commerce",
            "JavaScript Frameworks",
          ].map((cat) => (
            <div key={cat} className="flex items-center gap-2">
              <span className="h-1 w-1 rounded-full bg-phosphor" />
              {cat}
            </div>
          ))}
        </div>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Vendor classification
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          Each detected service is classified into a vendor type:
        </p>
        <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-green-400" />
            <span>
              <strong className="text-foreground">First-party infrastructure:</strong>{" "}
              Software you run yourself (nginx, React, WordPress).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
            <span>
              <strong className="text-foreground">Third-party service:</strong>{" "}
              External services you depend on (Stripe, Google Analytics,
              Cloudflare).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-purple-400" />
            <span>
              <strong className="text-foreground">SaaS platform:</strong>{" "}
              Platforms that host your content (Shopify, Wix, Squarespace).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-orange-400" />
            <span>
              <strong className="text-foreground">Security tool:</strong>{" "}
              WAFs, DDoS protection, and security services (Cloudflare WAF,
              AWS WAF, Sucuri).
            </span>
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Concentration risk
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          If 80% of your stack depends on a single vendor (e.g., AWS), a
          outage or compromise at that vendor affects most of your
          infrastructure. CAZO visualizes this as{" "}
          <strong className="text-foreground">vendor concentration risk</strong>{" "}
          — showing you which vendor categories have the most services and
          therefore the highest blast radius.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          How to use it
        </h2>
        <ol className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">1.</span>
            <span>
              Run a scan on your target domain (the tech detection scanner
              runs automatically).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">2.</span>
            <span>
              Navigate to <strong className="text-foreground">Supply Chain</strong> in the
              sidebar.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">3.</span>
            <span>
              Select a completed scan from the dropdown.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">4.</span>
            <span>
              Review the summary stats, concentration risk bars, and filter
              services by vendor type or risk level.
            </span>
          </li>
        </ol>

        <div className="mt-10 rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
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
