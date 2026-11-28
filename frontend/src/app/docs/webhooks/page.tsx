import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Webhooks — CAZO Docs",
  description: "Receive real-time event notifications when scans complete, findings appear, or risk scores change.",
};

export default function WebhooksDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="text-3xl font-semibold text-foreground">
          Webhooks
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Webhooks let CAZO push real-time notifications to your systems when
          events happen — a scan completes, a critical finding is discovered, or
          a risk score changes. Instead of polling the API, your system receives
          an HTTP POST with the event data.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Setting up a webhook
        </h2>
        <ol className="mt-3 space-y-3 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">1.</span>
            <span>
              Go to <strong className="text-foreground">Settings → Access → Webhooks</strong>.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">2.</span>
            <span>
              Click <strong className="text-foreground">Add Webhook</strong>.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">3.</span>
            <span>
              Enter your endpoint URL (must accept POST requests over HTTPS).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">4.</span>
            <span>
              Select which event types to subscribe to (leave empty for all
              events).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">5.</span>
            <span>
              Click <strong className="text-foreground">Create Webhook</strong>. CAZO will
              send a test payload immediately.
            </span>
          </li>
        </ol>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Event types
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          CAZO supports 18 event types across 7 categories:
        </p>
        <div className="mt-4 space-y-4">
          {[
            {
              category: "Scan Events",
              events: ["scan.started", "scan.completed", "scan.failed"],
            },
            {
              category: "Finding Events",
              events: ["finding.critical", "finding.high", "finding.medium"],
            },
            {
              category: "Asset Events",
              events: [
                "asset.new_subdomain",
                "asset.new_port",
                "asset.new_technology",
                "asset.shadow_asset",
              ],
            },
            {
              category: "SSL Events",
              events: ["ssl.certificate_expiring", "ssl.certificate_expired"],
            },
            {
              category: "Supply Chain",
              events: [
                "supply_chain.vendor_detected",
                "supply_chain.high_risk_vendor",
              ],
            },
            {
              category: "Risk Events",
              events: ["risk.score_changed", "risk.elevated"],
            },
            {
              category: "CVE Events",
              events: ["cve.new_match", "cve.active_exploit"],
            },
          ].map((cat) => (
            <div key={cat.category}>
              <div className="text-xs font-medium text-foreground mb-1.5">
                {cat.category}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {cat.events.map((e) => (
                  <code
                    key={e}
                    className="text-[11px] px-2 py-0.5 rounded border border-border bg-muted/30 text-muted-foreground"
                  >
                    {e}
                  </code>
                ))}
              </div>
            </div>
          ))}
        </div>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Payload format
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          Each webhook delivery includes:
        </p>
        <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              <code className="text-xs text-foreground/70">X-Webhook-Signature</code>{" "}
              header — HMAC-SHA256 signature for payload verification
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              <code className="text-xs text-foreground/70">X-Webhook-Event</code>{" "}
              header — the event type that triggered the delivery
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              JSON body with event data, timestamp, and organization context
            </span>
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Verifying signatures
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          Always verify the HMAC signature to ensure the payload was sent by
          CAZO and not tampered with. Use the webhook secret (shown once at
          creation time) to compute:
        </p>
        <div className="mt-4 rounded-lg border border-border bg-muted/20 p-4">
          <code className="text-xs text-muted-foreground">
            signature = HMAC-SHA256(webhook_secret, request_body)
          </code>
        </div>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Reliability
        </h2>
        <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-green-400" />
            <span>
              <strong className="text-foreground">Automatic retries:</strong>{" "}
              Failed deliveries retry 3 times with exponential backoff.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-yellow-400" />
            <span>
              <strong className="text-foreground">Failure tracking:</strong>{" "}
              Consecutive failures are tracked. After 5 failures, the webhook
              shows a warning.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-red-400" />
            <span>
              <strong className="text-foreground">Auto-disable:</strong> After
              20 consecutive failures, the webhook is automatically disabled to
              prevent spam.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              <strong className="text-foreground">Rate limiting:</strong>{" "}
              Configurable per-webhook rate limit (default: 30/minute).
            </span>
          </li>
        </ul>

        <div className="mt-10 rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
            <Link href="/docs/integrations" className="text-phosphor hover:underline">
              Integrations
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
