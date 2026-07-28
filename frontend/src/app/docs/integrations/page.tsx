import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Integrations — CAZO Docs",
  description: "Connect CAZO with SIEM platforms, ticketing systems, and team communication tools.",
};

export default function IntegrationsDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="font-display text-3xl font-semibold text-foreground">
          Integrations
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          CAZO integrates with security, ticketing, and communication platforms
          so findings flow directly into the tools your team already uses.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Available integrations
        </h2>
        <div className="mt-4 space-y-4">
          {[
            {
              name: "Splunk HEC",
              description:
                "Send CEF-formatted security events to Splunk via HTTP Event Collector.",
              env: "SPLUNK_HEC_URL",
              setup:
                "Create a HEC token in Splunk Settings → Data Inputs. Set SPLUNK_HEC_URL to your HEC endpoint.",
            },
            {
              name: "Elastic Security",
              description:
                "Index findings and alerts to Elasticsearch for SIEM analysis.",
              env: "ELASTIC_URL",
              setup:
                "Set ELASTIC_URL to your Elasticsearch cluster endpoint (e.g., https://localhost:9200).",
            },
            {
              name: "Microsoft Sentinel",
              description:
                "Forward security events to Azure Sentinel via the Log Analytics Data Collector API.",
              env: "SENTINEL_WORKSPACE_ID",
              setup:
                "Create a Log Analytics workspace in Azure. Set SENTINEL_WORKSPACE_ID and SENTINEL_PRIMARY_KEY.",
            },
            {
              name: "Jira",
              description:
                "Automatically create Jira tickets for critical findings and scan summaries.",
              env: "JIRA_URL",
              setup:
                "Set JIRA_URL (e.g., https://yourteam.atlassian.net) and JIRA_API_TOKEN with a project token.",
            },
            {
              name: "Slack",
              description:
                "Post security alerts and scan completion notifications to Slack channels.",
              env: "SLACK_WEBHOOK_URL",
              setup:
                "Create an Incoming Webhook in your Slack workspace settings. Set SLACK_WEBHOOK_URL.",
            },
            {
              name: "Microsoft Teams",
              description:
                "Send security notifications and alerts to Teams channels.",
              env: "TEAMS_WEBHOOK_URL",
              setup:
                "Create an Incoming Webhook connector in your Teams channel. Set TEAMS_WEBHOOK_URL.",
            },
          ].map((int) => (
            <div
              key={int.name}
              className="rounded-xl border border-border/50 bg-card/40 p-5"
            >
              <h3 className="text-sm font-semibold text-foreground">
                {int.name}
              </h3>
              <p className="mt-1 text-xs text-muted-foreground">
                {int.description}
              </p>
              <div className="mt-3 rounded-lg bg-muted/20 p-3">
                <div className="text-[10px] text-muted-foreground mb-1">
                  Environment variable:
                </div>
                <code className="text-xs text-foreground/70">{int.env}</code>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {int.setup}
              </p>
            </div>
          ))}
        </div>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          How to configure
        </h2>
        <ol className="mt-3 space-y-3 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">1.</span>
            <span>
              Go to <strong className="text-foreground">Settings → Access → Integrations</strong>.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">2.</span>
            <span>
              Find the integration you want to enable.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">3.</span>
            <span>
              Set the required environment variable in your Railway dashboard
              (or backend <code className="text-xs text-foreground/70">.env</code> file).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">4.</span>
            <span>
              Click <strong className="text-foreground">Refresh</strong> in the Integrations
              panel — the status should change to "Configured".
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">5.</span>
            <span>
              Click <strong className="text-foreground">Test Connection</strong> to verify
              everything works.
            </span>
          </li>
        </ol>

        <div className="mt-10 rounded-xl border border-border/50 bg-card/40 p-5">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
            <Link href="/docs/webhooks" className="text-phosphor hover:underline">
              Webhooks
            </Link>{" "}
            &middot;{" "}
            <Link href="/docs/blockchain-intel" className="text-phosphor hover:underline">
              Blockchain Intelligence
            </Link>
          </p>
        </div>
      </article>
    </DocsLayout>
  );
}
