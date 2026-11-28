"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Server,
  Database,
  Cloud,
  Ticket,
  MessageSquare,
  ExternalLink,
  Loader2,
  Check,
  X,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

const API_BASE = "";

interface IntegrationStatus {
  name: string;
  configured: boolean;
  env_var: string;
  description: string;
  icon: any;
  color: string;
  docs_url: string;
  endpoint_preview?: string;
}

const INTEGRATIONS: Omit<IntegrationStatus, "configured" | "endpoint_preview">[] = [
  {
    name: "Splunk HEC",
    env_var: "SPLUNK_HEC_URL",
    description:
      "Send CEF-formatted security events to your Splunk instance via HTTP Event Collector.",
    icon: Server,
    color: "bg-green-500",
    docs_url: "https://docs.splunk.com/s/cloud/splexploreHEC",
  },
  {
    name: "Elastic Security",
    env_var: "ELASTIC_URL",
    description:
      "Index findings and alerts to Elasticsearch or Elastic Security for SIEM analysis.",
    icon: Database,
    color: "bg-yellow-500",
    docs_url: "https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html",
  },
  {
    name: "Microsoft Sentinel",
    env_var: "SENTINEL_WORKSPACE_ID",
    description:
      "Forward security events to Azure Sentinel via the Log Analytics Data Collector API.",
    icon: Cloud,
    color: "bg-blue-500",
    docs_url: "https://learn.microsoft.com/en-us/azure/sentinel/",
  },
  {
    name: "Jira",
    env_var: "JIRA_URL",
    description:
      "Automatically create Jira tickets for critical findings and scan summaries.",
    icon: Ticket,
    color: "bg-blue-400",
    docs_url: "https://developer.atlassian.com/cloud/jira/platform/",
  },
  {
    name: "Slack",
    env_var: "SLACK_WEBHOOK_URL",
    description:
      "Post security alerts and scan completion notifications to Slack channels.",
    icon: MessageSquare,
    color: "bg-purple-500",
    docs_url: "https://api.slack.com/messaging/webhooks",
  },
  {
    name: "Microsoft Teams",
    env_var: "TEAMS_WEBHOOK_URL",
    description:
      "Send security notifications and alerts to Microsoft Teams channels.",
    icon: MessageSquare,
    color: "bg-indigo-500",
    docs_url: "https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/what-are-webhooks-and-connectors",
  },
];

export function IntegrationsPanel() {
  const [statuses, setStatuses] = useState<Record<string, boolean>>({});
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<
    Record<string, { success: boolean; error?: string }>
  >({});

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/status`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || ""}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setStatuses(data.configured || {});
        setPreviews(data.previews || {});
      }
    } catch {
      // If endpoint doesn't exist yet, default all to not configured
      const fallback: Record<string, boolean> = {};
      INTEGRATIONS.forEach((i) => {
        fallback[i.env_var] = false;
      });
      setStatuses(fallback);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleTest = useCallback(async (integration: { env_var: string; name: string }) => {
    setTesting(integration.env_var);
    setTestResults((prev) => {
      const next = { ...prev };
      delete next[integration.env_var];
      return next;
    });
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/integrations/${integration.name.toLowerCase().replace(/\s+/g, "-")}/test`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || ""}`,
          },
        }
      );
      if (res.ok) {
        const data = await res.json();
        setTestResults((prev) => ({
          ...prev,
          [integration.env_var]: { success: data.success, error: data.error },
        }));
      } else {
        setTestResults((prev) => ({
          ...prev,
          [integration.env_var]: { success: false, error: "Endpoint not available" },
        }));
      }
    } catch {
      setTestResults((prev) => ({
        ...prev,
        [integration.env_var]: { success: false, error: "Connection failed" },
      }));
    } finally {
      setTesting(null);
    }
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-400/10 text-sky-400">
            <ExternalLink className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">Integrations</h2>
            <p className="text-xs text-muted-foreground">
              Connect with third-party SIEM and notification services.
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="h-8 text-xs"
          onClick={fetchStatus}
        >
          <RefreshCw className="h-3 w-3 mr-1.5" />
          Refresh
        </Button>
      </div>

      {/* Integration cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {INTEGRATIONS.map((integration) => {
          const isConfigured = statuses[integration.env_var] || false;
          const Icon = integration.icon;
          const testResult = testResults[integration.env_var];

          return (
            <div
              key={integration.env_var}
              className={`border rounded-lg p-4 transition-colors ${
                isConfigured
                  ? "border-border bg-muted/5"
                  : "border-border bg-muted/20"
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center ${integration.color}/10`}
                  >
                    <Icon className={`h-4 w-4 ${integration.color.replace("bg-", "text-")}`} />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium">{integration.name}</h3>
                    <p className="text-xs text-muted-foreground mt-0.5 max-w-[250px]">
                      {integration.description}
                    </p>
                  </div>
                </div>
                <Badge
                  variant={isConfigured ? "default" : "secondary"}
                  className={`text-[10px] shrink-0 ${
                    isConfigured
                      ? "bg-success/10 text-success border-green-500/20"
                      : "text-muted-foreground"
                  }`}
                >
                  {isConfigured ? (
                    <span className="flex items-center gap-1">
                      <Check className="h-2.5 w-2.5" /> Configured
                    </span>
                  ) : (
                    <span className="flex items-center gap-1">
                      <X className="h-2.5 w-2.5" /> Not configured
                    </span>
                  )}
                </Badge>
              </div>

              {/* Endpoint preview */}
              {isConfigured && previews[integration.env_var] && (
                <div className="mt-3 font-mono text-[10px] text-muted-foreground bg-muted/30 rounded px-2 py-1 truncate">
                  {previews[integration.env_var]}
                </div>
              )}

              {/* Setup instructions */}
              {!isConfigured && (
                <div className="mt-3 text-xs text-muted-foreground bg-muted/30 rounded px-3 py-2">
                  Set <code className="text-foreground/70">{integration.env_var}</code> in your
                  Railway dashboard environment variables.
                </div>
              )}

              {/* Actions */}
              <div className="mt-3 flex items-center gap-2">
                {isConfigured && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-[10px]"
                    onClick={() => handleTest(integration)}
                    disabled={testing === integration.env_var}
                  >
                    {testing === integration.env_var ? (
                      <Loader2 className="h-2.5 w-2.5 animate-spin mr-1" />
                    ) : null}
                    Test Connection
                  </Button>
                )}
                <a
                  href={integration.docs_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1"
                >
                  <ExternalLink className="h-2.5 w-2.5" />
                  Docs
                </a>
              </div>

              {/* Test result */}
              {testResult && (
                <div
                  className={`mt-2 text-[10px] p-1.5 rounded border ${
                    testResult.success
                      ? "border-green-500/20 bg-green-500/5 text-success"
                      : "border-red-500/20 bg-red-500/5 text-destructive"
                  }`}
                >
                  {testResult.success
                    ? "Connection successful"
                    : testResult.error || "Connection failed"}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
