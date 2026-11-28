import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: 'Why "blocked by CDN" instead of a result? — CAZO Docs',
  description: "How honest status badges work and why CAZO reports failures instead of hiding them.",
};

export default function ScanStatusesDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="text-3xl font-semibold text-foreground">
          Why did this show as &ldquo;blocked by CDN&rdquo; instead of a result?
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          When a scanner runs against a target, it might not always get a clean
          result. The target might be behind a CDN, rate-limited, or
          unreachable. Most tools would silently drop these failures and show you
          an empty result — making it look like everything is clean.
        </p>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          CAZO doesn&rsquo;t do that. We report the status honestly.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          The status badges
        </h2>
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-phosphor" />
            <div>
              <span className="text-sm font-semibold text-foreground">ok</span>
              <p className="text-xs text-muted-foreground">
                The scan completed successfully. The results are trustworthy.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-warning" />
            <div>
              <span className="text-sm font-semibold text-foreground">
                rate-limited
              </span>
              <p className="text-xs text-muted-foreground">
                The target&rsquo;s rate limiting kicked in. CAZO retried but
                got partial or no data. Results may be incomplete.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-warning" />
            <div>
              <span className="text-sm font-semibold text-foreground">
                blocked-by-cdn
              </span>
              <p className="text-xs text-muted-foreground">
                The target is behind a CDN or WAF that blocked the scan
                request. We couldn&rsquo;t reach the actual origin server.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-destructive" />
            <div>
              <span className="text-sm font-semibold text-foreground">error</span>
              <p className="text-xs text-muted-foreground">
                The scan failed entirely — network timeout, DNS failure, or
                other error. No data was returned.
              </p>
            </div>
          </div>
        </div>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Why we show these instead of hiding them
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          A security tool that silently drops failed checks is lying to you. If
          a scanner can&rsquo;t reach a host, it has two honest options:
        </p>
        <ol className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">
              1.
            </span>
            <span>
              Say &ldquo;we couldn&rsquo;t check&rdquo; (what CAZO does)
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">
              2.
            </span>
            <span>
              Say nothing and let you assume it&rsquo;s clean (what most tools
              do)
            </span>
          </li>
        </ol>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Option 2 is how real exposure hides in plain sight. A host behind a
          Cloudflare WAF might have critical vulnerabilities — but if the
          scanner can&rsquo;t get through, you&rsquo;d never know. The WAF is
          masking the problem, not solving it.
        </p>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          By showing you the status, CAZO lets you decide: &ldquo;This host is
          behind a CDN and I can&rsquo;t verify its state directly &mdash; I
          need to check it from inside the network.&rdquo;
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          What to do about blocked scans
        </h2>
        <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              <strong className="text-foreground">blocked-by-cdn:</strong>{" "}
              Consider scanning from a different vantage point, or verify the
              origin server directly if you have internal access.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              <strong className="text-foreground">rate-limited:</strong> Wait
              and re-run the scan. If it persists, the target may need
              whitelisting.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-signal-red" />
            <span>
              <strong className="text-foreground">error:</strong> Check
              network connectivity, DNS resolution, and whether the target is
              actually reachable.
            </span>
          </li>
        </ul>

        <div className="mt-10 rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
            <Link href="/docs/evidence-panel" className="text-phosphor hover:underline">
              Reading the Evidence Panel
            </Link>{" "}
            &middot;{" "}
            <Link href="/docs/authorized-scope" className="text-phosphor hover:underline">
              Authorized Scope
            </Link>
          </p>
        </div>
      </article>
    </DocsLayout>
  );
}
