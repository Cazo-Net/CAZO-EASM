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
        <h1 className="text-3xl font-semibold text-foreground">
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
              name: "Slack",
              description: "Post new findings and alerts to a Slack channel.",
              need: "An incoming webhook URL",
              setup:
                "In Slack, open Apps, add Incoming Webhooks to the channel you want, and copy the URL it gives you.",
            },
            {
              name: "Microsoft Teams",
              description: "Post new findings and alerts to a Teams channel.",
              need: "A workflow webhook URL",
              setup:
                "In the channel, open Workflows, choose \"Post to a channel when a webhook request is received\", and copy the URL.",
            },
            {
              name: "Jira",
              description:
                "Open an issue for each new finding. The same alert never opens a second issue.",
              need: "Your Jira site, an account email, an API token and a project key",
              setup:
                "Create an API token at id.atlassian.com under Security. Use a service account that can create issues in the project.",
            },
            {
              name: "Splunk",
              description:
                "Send every event to Splunk through the HTTP Event Collector, as JSON.",
              need: "Your HEC URL and a HEC token",
              setup:
                "In Splunk, go to Settings, Data Inputs, HTTP Event Collector and create a token. The collector must be reachable from the internet.",
            },
            {
              name: "Other SIEMs and your own systems",
              description:
                "Elastic, Microsoft Sentinel, QRadar and anything else that accepts HTTPS can receive the same events as signed webhooks.",
              need: "An HTTPS endpoint",
              setup:
                "Add a webhook under Settings, Access, Webhooks and verify the signature on your side.",
            },
          ].map((int) => (
            <div
              key={int.name}
              className="rounded-xl border border-border bg-card p-5"
            >
              <h3 className="text-sm font-semibold text-foreground">
                {int.name}
              </h3>
              <p className="mt-1 text-xs text-muted-foreground">
                {int.description}
              </p>
              <div className="mt-3 rounded-lg bg-muted/20 p-3">
                <div className="text-[10px] text-muted-foreground mb-1">
                  What you need:
                </div>
                <span className="text-xs text-foreground/70">{int.need}</span>
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
        <p className="mt-3 text-sm text-muted-foreground">
          Owners and administrators can set up integrations. Each organization has its own, and
          every change is recorded in the audit log.
        </p>
        <ol className="mt-3 space-y-3 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">1.</span>
            <span>
              Go to <strong className="text-foreground">Settings → Access → Integrations</strong>.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">2.</span>
            <span>
              Pick the tool you want to connect and enter its details. Credentials are stored encrypted and are never shown again.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">3.</span>
            <span>
              Choose which events to send, such as new critical findings or expiring certificates.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">4.</span>
            <span>
              Click <strong className="text-foreground">Test</strong> to check it works. For Jira the test checks access without opening an issue.
            </span>
          </li>
        </ol>

        <div className="mt-10 rounded-xl border border-border bg-card p-5">
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
