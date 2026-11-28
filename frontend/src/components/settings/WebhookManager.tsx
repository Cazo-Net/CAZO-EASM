"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Webhook,
  Plus,
  Trash2,
  Loader2,
  Check,
  X,
  AlertTriangle,
  ExternalLink,
  RotateCcw,
  Zap,
  Bell,
  Shield,
  Globe,
  Lock,
  Server,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

const API_BASE = "";

interface WebhookItem {
  id: string;
  url: string;
  description: string | null;
  event_types: string[];
  is_active: boolean;
  custom_headers: Record<string, string>;
  max_per_minute: number;
  failure_count: number;
  last_triggered_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

interface EventType {
  type: string;
  description: string;
}

const EVENT_CATEGORIES = [
  {
    label: "Scan Events",
    icon: Globe,
    events: ["scan.started", "scan.completed", "scan.failed"],
  },
  {
    label: "Finding Events",
    icon: Shield,
    events: ["finding.critical", "finding.high", "finding.medium"],
  },
  {
    label: "Asset Events",
    icon: Server,
    events: [
      "asset.new_subdomain",
      "asset.new_port",
      "asset.new_technology",
      "asset.shadow_asset",
    ],
  },
  {
    label: "SSL Events",
    icon: Lock,
    events: ["ssl.certificate_expiring", "ssl.certificate_expired"],
  },
  {
    label: "Supply Chain",
    icon: Zap,
    events: ["supply_chain.vendor_detected", "supply_chain.high_risk_vendor"],
  },
  {
    label: "Risk Events",
    icon: AlertTriangle,
    events: ["risk.score_changed", "risk.elevated"],
  },
  {
    label: "CVE Events",
    icon: Shield,
    events: ["cve.new_match", "cve.active_exploit"],
  },
];

function getStatusColor(webhook: WebhookItem): string {
  if (!webhook.is_active) return "text-muted-foreground";
  if (webhook.failure_count >= 5) return "text-red-400";
  if (webhook.failure_count >= 1) return "text-yellow-400";
  return "text-green-400";
}

function getStatusDot(webhook: WebhookItem): string {
  if (!webhook.is_active) return "bg-muted-foreground/40";
  if (webhook.failure_count >= 5) return "bg-red-400";
  if (webhook.failure_count >= 1) return "bg-yellow-400";
  return "bg-green-400";
}

function getStatusLabel(webhook: WebhookItem): string {
  if (!webhook.is_active) return "Inactive";
  if (webhook.failure_count >= 5) return "Error";
  if (webhook.failure_count >= 1) return "Degraded";
  return "Active";
}

export function WebhookManager() {
  const [webhooks, setWebhooks] = useState<WebhookItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<WebhookItem | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; success: boolean; error?: string } | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);

  // Form state
  const [formUrl, setFormUrl] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formEvents, setFormEvents] = useState<string[]>([]);
  const [formRateLimit, setFormRateLimit] = useState(30);
  const [saving, setSaving] = useState(false);

  const fetchWebhooks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/webhooks/`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || ""}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setWebhooks(data.webhooks || []);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWebhooks();
  }, [fetchWebhooks]);

  const handleCreate = useCallback(() => {
    setEditing(null);
    setFormUrl("");
    setFormDescription("");
    setFormEvents([]);
    setFormRateLimit(30);
    setShowForm(true);
  }, []);

  const handleEdit = useCallback((webhook: WebhookItem) => {
    setEditing(webhook);
    setFormUrl(webhook.url);
    setFormDescription(webhook.description || "");
    setFormEvents(webhook.event_types || []);
    setFormRateLimit(webhook.max_per_minute);
    setShowForm(true);
  }, []);

  const handleSave = useCallback(async () => {
    if (!formUrl.trim()) return;
    setSaving(true);
    try {
      const payload = {
        url: formUrl,
        description: formDescription || null,
        event_types: formEvents,
        max_per_minute: formRateLimit,
      };

      const url = editing
        ? `${API_BASE}/api/v1/webhooks/${editing.id}`
        : `${API_BASE}/api/v1/webhooks/`;
      const method = editing ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || ""}`,
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setShowForm(false);
        setEditing(null);
        fetchWebhooks();
      }
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }, [formUrl, formDescription, formEvents, formRateLimit, editing, fetchWebhooks]);

  const handleDelete = useCallback(
    async (id: string) => {
      setDeleting(id);
      try {
        const res = await fetch(`${API_BASE}/api/v1/webhooks/${id}`, {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || ""}`,
          },
        });
        if (res.ok) {
          fetchWebhooks();
        }
      } catch {
        // ignore
      } finally {
        setDeleting(null);
      }
    },
    [fetchWebhooks]
  );

  const handleTest = useCallback(async (id: string) => {
    setTesting(id);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/webhooks/${id}/test`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || ""}`,
        },
      });
      const data = await res.json();
      setTestResult({ id, success: data.success, error: data.error });
      setTimeout(() => setTestResult(null), 4000);
    } catch {
      setTestResult({ id, success: false, error: "Request failed" });
      setTimeout(() => setTestResult(null), 4000);
    } finally {
      setTesting(null);
    }
  }, []);

  const handleToggle = useCallback(
    async (webhook: WebhookItem) => {
      setToggling(webhook.id);
      try {
        const res = await fetch(`${API_BASE}/api/v1/webhooks/${webhook.id}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || ""}`,
          },
          body: JSON.stringify({ is_active: !webhook.is_active }),
        });
        if (res.ok) {
          fetchWebhooks();
        }
      } catch {
        // ignore
      } finally {
        setToggling(null);
      }
    },
    [fetchWebhooks]
  );

  const toggleEvent = useCallback((event: string) => {
    setFormEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]
    );
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
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#10B981]/10 text-[#10B981]">
            <Webhook className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">Webhooks</h2>
            <p className="text-xs text-muted-foreground">
              Receive real-time event notifications via HTTP callbacks.
            </p>
          </div>
        </div>
        <Button size="sm" onClick={handleCreate} className="h-8 text-xs">
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          Add Webhook
        </Button>
      </div>

      {/* Webhook form */}
      {showForm && (
        <div className="border border-border rounded-lg p-4 mb-6 bg-muted/20">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium">
              {editing ? "Edit Webhook" : "New Webhook"}
            </h3>
            <button
              onClick={() => {
                setShowForm(false);
                setEditing(null);
              }}
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">URL</label>
              <Input
                placeholder="https://hooks.example.com/webhook"
                value={formUrl}
                onChange={(e) => setFormUrl(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">
                Description (optional)
              </label>
              <Input
                placeholder="Slack notification webhook"
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                className="text-xs"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">
                Rate Limit (per minute)
              </label>
              <Input
                type="number"
                min={1}
                max={100}
                value={formRateLimit}
                onChange={(e) => setFormRateLimit(Number(e.target.value))}
                className="text-xs w-24"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground mb-2 block">
                Event Types
              </label>
              <p className="text-xs text-muted-foreground mb-3">
                Leave empty to subscribe to all events.
              </p>
              <div className="space-y-3">
                {EVENT_CATEGORIES.map((cat) => (
                  <div key={cat.label}>
                    <div className="flex items-center gap-2 mb-1.5">
                      <cat.icon className="h-3 w-3 text-muted-foreground" />
                      <span className="text-xs font-medium text-muted-foreground">
                        {cat.label}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 ml-5">
                      {cat.events.map((event) => (
                        <button
                          key={event}
                          onClick={() => toggleEvent(event)}
                          className={`text-xs px-2 py-1 rounded border transition-colors ${
                            formEvents.includes(event)
                              ? "border-[#10B981]/40 bg-[#10B981]/10 text-[#10B981]"
                              : "border-border text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          {event}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs"
                onClick={() => {
                  setShowForm(false);
                  setEditing(null);
                }}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                className="h-8 text-xs"
                onClick={handleSave}
                disabled={saving || !formUrl.trim()}
              >
                {saving && <Loader2 className="h-3 w-3 animate-spin mr-1.5" />}
                {editing ? "Save Changes" : "Create Webhook"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Webhook list */}
      {webhooks.length === 0 ? (
        <div className="rounded-lg border border-border bg-muted/10 p-12 text-center">
          <Webhook className="h-10 w-10 text-muted-foreground/20 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground mb-1">No webhooks configured</p>
          <p className="text-xs text-muted-foreground">
            Add a webhook to receive event notifications.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {webhooks.map((webhook) => (
            <div
              key={webhook.id}
              className="border border-border rounded-lg p-4 hover:border-border transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-2 h-2 rounded-full ${getStatusDot(webhook)}`}
                    />
                    <span className="text-sm font-medium truncate">
                      {webhook.description || new URL(webhook.url).hostname}
                    </span>
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${getStatusColor(webhook)}`}
                    >
                      {getStatusLabel(webhook)}
                    </Badge>
                    {webhook.failure_count > 0 && webhook.is_active && (
                      <Badge variant="outline" className="text-[10px] text-yellow-400">
                        {webhook.failure_count} failures
                      </Badge>
                    )}
                  </div>
                  <div className="mt-1 font-mono text-xs text-muted-foreground truncate">
                    {webhook.url}
                  </div>
                  {webhook.event_types.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {webhook.event_types.slice(0, 5).map((event) => (
                        <Badge
                          key={event}
                          variant="secondary"
                          className="text-[10px] px-1.5 py-0"
                        >
                          {event}
                        </Badge>
                      ))}
                      {webhook.event_types.length > 5 && (
                        <Badge
                          variant="secondary"
                          className="text-[10px] px-1.5 py-0"
                        >
                          +{webhook.event_types.length - 5} more
                        </Badge>
                      )}
                    </div>
                  )}
                  {webhook.event_types.length === 0 && (
                    <div className="mt-2">
                      <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                        All events
                      </Badge>
                    </div>
                  )}
                  <div className="mt-2 text-[10px] text-muted-foreground">
                    {webhook.last_triggered_at
                      ? `Last triggered ${new Date(webhook.last_triggered_at).toLocaleString()}`
                      : "Never triggered"}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1 ml-4">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => handleToggle(webhook)}
                    disabled={toggling === webhook.id}
                    title={webhook.is_active ? "Disable" : "Enable"}
                  >
                    {toggling === webhook.id ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : webhook.is_active ? (
                      <Zap className="h-3 w-3 text-green-400" />
                    ) : (
                      <X className="h-3 w-3 text-muted-foreground" />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => handleTest(webhook.id)}
                    disabled={testing === webhook.id}
                    title="Send test payload"
                  >
                    {testing === webhook.id ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <RotateCcw className="h-3 w-3" />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => handleEdit(webhook)}
                    title="Edit"
                  >
                    <Bell className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 hover:text-red-400"
                    onClick={() => handleDelete(webhook.id)}
                    disabled={deleting === webhook.id}
                    title="Delete"
                  >
                    {deleting === webhook.id ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Trash2 className="h-3 w-3" />
                    )}
                  </Button>
                </div>
              </div>

              {/* Test result */}
              {testResult && testResult.id === webhook.id && (
                <div
                  className={`mt-3 text-xs p-2 rounded border ${
                    testResult.success
                      ? "border-green-500/20 bg-green-500/5 text-green-400"
                      : "border-red-500/20 bg-red-500/5 text-red-400"
                  }`}
                >
                  {testResult.success ? (
                    <span className="flex items-center gap-1.5">
                      <Check className="h-3 w-3" /> Test payload delivered successfully
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5">
                      <X className="h-3 w-3" /> {testResult.error || "Delivery failed"}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
