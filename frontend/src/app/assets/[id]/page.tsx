"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Boxes,
  Loader2,
  ShieldAlert,
  Activity,
  CalendarPlus,
  CalendarClock,
  Network,
  History,
  LayoutGrid,
  ArrowUpRight,
  ArrowDownLeft,
  PlusCircle,
  MinusCircle,
  Pencil,
  Circle,
  Server,
  Cpu,
  Lock,
  ShieldCheck,
  Globe2,
  TerminalSquare,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";
import { getAsset360, getHostIntelligence } from "@/lib/api-asset360";
import type { Asset360Response } from "@/types/asset360";
import type { HostIntelligence } from "@/types/asset360";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function scoreDisplay(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return String(Math.round(value));
}

function changeIcon(type: string) {
  switch (type) {
    case "added":
      return <PlusCircle className="h-4 w-4 text-success" />;
    case "removed":
      return <MinusCircle className="h-4 w-4 text-destructive" />;
    case "modified":
      return <Pencil className="h-4 w-4 text-amber-500" />;
    default:
      return <Circle className="h-4 w-4 text-muted-foreground" />;
  }
}

export default function Asset360Page() {
  const params = useParams();
  const assetId = Array.isArray(params?.id) ? params.id[0] : (params?.id as string);
  const { user, loading: authLoading } = useAuth();
  const orgId = user?.organization_id;

  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<Asset360Response | null>(null);
  const [host, setHost] = useState<HostIntelligence | null>(null);
  const [tab, setTab] = useState("overview");

  const load = useCallback(async () => {
    if (!assetId) return;
    setLoading(true);
    setError("");
    setNotFound(false);
    try {
      const res = await getAsset360(assetId);
      setData(res);
      try {
        setHost(await getHostIntelligence(assetId));
      } catch {
        setHost(null);
      }
    } catch (e) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status === 404) {
        setNotFound(true);
      } else {
        setError("Failed to load asset intelligence.");
      }
    } finally {
      setLoading(false);
    }
  }, [assetId]);

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  if (loading || authLoading) {
    return (
      <div className="page-container-lg">
        <div className="flex items-center justify-center py-32 text-muted-foreground">
          <Loader2 className="mr-2 h-6 w-6 animate-spin" /> Loading asset...
        </div>
      </div>
    );
  }

  if (notFound || (!data && !error)) {
    return (
      <div className="page-container-lg">
        <EmptyState
          icon={<Boxes className="h-8 w-8" />}
          title="Asset not found"
          description="This asset does not exist or you do not have access to it."
          action={
            <Link href="/assets">
              <Button variant="outline">Back to Assets</Button>
            </Link>
          }
        />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page-container-lg">
        <EmptyState
          icon={<ShieldAlert className="h-8 w-8" />}
          title="Something went wrong"
          description={error || "Unable to load this asset."}
          action={<Button onClick={load}>Retry</Button>}
        />
      </div>
    );
  }

  const { asset, score, relationships, changes, counts } = data;
  const title = asset.label || asset.value;
  const attributes = asset.attributes || {};
  const attributeEntries = Object.entries(attributes);

  return (
    <div className="page-container-lg">
      <PageHeader
        title={title}
        description={asset.value}
        icon={<Boxes className="h-5 w-5" />}
        breadcrumbs={[{ label: "Assets", href: "/assets" }, { label: "360° View" }]}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="capitalize">
              {asset.asset_type}
            </Badge>
            <Badge variant={asset.is_alive ? "success" : "secondary"}>
              {asset.is_alive ? "Alive" : "Inactive"}
            </Badge>
            {orgId && (
              <Link href="/assets">
                <Button variant="outline" size="sm">
                  Back
                </Button>
              </Link>
            )}
          </div>
        }
      />

      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Exposure Score"
          value={scoreDisplay(score?.exposure_score)}
          icon={<ShieldAlert className="h-5 w-5" />}
          accent="danger"
        />
        <StatCard
          label="Health Score"
          value={scoreDisplay(score?.health_score)}
          icon={<Activity className="h-5 w-5" />}
          accent="success"
        />
        <StatCard
          label="First Seen"
          value={<span className="text-lg">{formatDate(data.first_seen)}</span>}
          icon={<CalendarPlus className="h-5 w-5" />}
          accent="info"
        />
        <StatCard
          label="Last Seen"
          value={<span className="text-lg">{formatDate(data.last_seen)}</span>}
          icon={<CalendarClock className="h-5 w-5" />}
          accent="brand"
        />
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="overview" className="gap-1.5">
            <LayoutGrid className="h-3.5 w-3.5" /> Overview
          </TabsTrigger>
          <TabsTrigger value="relationships" className="gap-1.5">
            <Network className="h-3.5 w-3.5" /> Relationships
            {relationships.length > 0 && (
              <Badge variant="secondary" className="ml-1 px-1.5 py-0 text-[10px]">
                {relationships.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="timeline" className="gap-1.5">
            <History className="h-3.5 w-3.5" /> Timeline
            {changes.length > 0 && (
              <Badge variant="secondary" className="ml-1 px-1.5 py-0 text-[10px]">
                {changes.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="host" className="gap-1.5">
            <Globe2 className="h-3.5 w-3.5" /> Host
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid gap-4 md:grid-cols-2">
            <SectionCard
              title="Details"
              description="Core asset information"
              icon={<Boxes className="h-4 w-4" />}
            >
              <dl className="space-y-3 text-sm">
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-muted-foreground">Label</dt>
                  <dd className="truncate font-medium">{asset.label || "—"}</dd>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-muted-foreground">Value</dt>
                  <dd className="truncate font-mono text-xs">{asset.value}</dd>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-muted-foreground">Type</dt>
                  <dd className="capitalize">{asset.asset_type}</dd>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-muted-foreground">Status</dt>
                  <dd>
                    <Badge variant={asset.is_alive ? "success" : "secondary"}>
                      {asset.is_alive ? "Alive" : "Inactive"}
                    </Badge>
                  </dd>
                </div>
              </dl>

              <div className="mt-4 grid grid-cols-3 gap-3 border-t border-border pt-4 text-center">
                <div>
                  <p className="text-lg font-semibold tabular-nums">{counts.subdomains}</p>
                  <p className="text-[11px] uppercase text-muted-foreground">Subdomains</p>
                </div>
                <div>
                  <p className="text-lg font-semibold tabular-nums">{counts.ports}</p>
                  <p className="text-[11px] uppercase text-muted-foreground">Ports</p>
                </div>
                <div>
                  <p className="text-lg font-semibold tabular-nums">
                    {counts.vulnerabilities}
                  </p>
                  <p className="text-[11px] uppercase text-muted-foreground">Vulns</p>
                </div>
              </div>
            </SectionCard>

            <SectionCard
              title="Attributes"
              description="Discovered metadata"
              icon={<LayoutGrid className="h-4 w-4" />}
            >
              {attributeEntries.length === 0 ? (
                <EmptyState
                  icon={<LayoutGrid className="h-8 w-8" />}
                  title="No attributes"
                  description="No metadata has been recorded for this asset."
                />
              ) : (
                <dl className="space-y-2.5 text-sm">
                  {attributeEntries.map(([key, value]) => (
                    <div
                      key={key}
                      className="flex items-start justify-between gap-4 border-b border-border pb-2 last:border-0 last:pb-0"
                    >
                      <dt className="capitalize text-muted-foreground">
                        {key.replace(/_/g, " ")}
                      </dt>
                      <dd className="max-w-[60%] truncate text-right font-mono text-xs">
                        {typeof value === "object"
                          ? JSON.stringify(value)
                          : String(value)}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </SectionCard>
          </div>
        </TabsContent>

        <TabsContent value="relationships">
          <SectionCard
            title="Related Assets"
            description="Connections in the attack-surface graph"
            icon={<Network className="h-4 w-4" />}
          >
            {relationships.length === 0 ? (
              <EmptyState
                icon={<Network className="h-8 w-8" />}
                title="No relationships"
                description="This asset has no recorded connections to other assets."
              />
            ) : (
              <div className="divide-y divide-border/40">
                {relationships.map((rel) => (
                  <div
                    key={rel.id}
                    className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-brand">
                      {rel.direction === "outgoing" ? (
                        <ArrowUpRight className="h-4 w-4" />
                      ) : (
                        <ArrowDownLeft className="h-4 w-4" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <Link
                        href={`/assets/${rel.related_asset_id}`}
                        className="truncate text-sm font-medium hover:text-brand"
                      >
                        {rel.related_asset_label || rel.related_asset_id}
                      </Link>
                      <p className="truncate text-xs text-muted-foreground">
                        {rel.direction} · {rel.relationship_type.replace(/_/g, " ")}
                      </p>
                    </div>
                    {rel.related_asset_type && (
                      <Badge variant="outline" className="capitalize">
                        {rel.related_asset_type}
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
        </TabsContent>

        <TabsContent value="timeline">
          <SectionCard
            title="Change Timeline"
            description="Recorded changes affecting this asset"
            icon={<History className="h-4 w-4" />}
          >
            {changes.length === 0 ? (
              <EmptyState
                icon={<History className="h-8 w-8" />}
                title="No changes"
                description="No change events have been detected for this asset."
              />
            ) : (
              <div className="space-y-3">
                {changes.map((c) => (
                  <div
                    key={c.id}
                    className="flex items-start gap-3 rounded-lg border border-border bg-muted/20 p-3"
                  >
                    <div className="mt-0.5">{changeIcon(c.change_type)}</div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium capitalize">
                        {c.change_type}{" "}
                        <span className="text-muted-foreground">{c.entity_type}</span>
                      </p>
                      <p className="truncate font-mono text-xs text-muted-foreground">
                        {c.entity_key}
                      </p>
                    </div>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {formatDate(c.detected_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
        </TabsContent>

        <TabsContent value="host">
          {!host ? (
            <EmptyState
              icon={<Globe2 className="h-8 w-8" />}
              title="No host intelligence"
              description="Host-level data is only available for host or IP assets."
            />
          ) : (
            <div className="space-y-4">
              {/* Shodan-style header strip */}
              <div className="grid gap-4 md:grid-cols-4">
                <SectionCard title="Network" icon={<Network className="h-4 w-4" />}>
                  <dl className="space-y-2.5 text-sm">
                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-muted-foreground">ASN</dt>
                      <dd className="font-mono text-xs">{host.asn || "—"}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-muted-foreground">ISP</dt>
                      <dd className="text-xs">{host.isp || "—"}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-muted-foreground">Organization</dt>
                      <dd className="truncate text-xs">{host.org || "—"}</dd>
                    </div>
                  </dl>
                </SectionCard>

                <SectionCard title="IP Addresses" icon={<Server className="h-4 w-4" />}>
                  {host.ip_addresses.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No IPs resolved.</p>
                  ) : (
                    <ul className="space-y-1.5 font-mono text-xs">
                      {host.ip_addresses.map((ip) => (
                        <li
                          key={ip}
                          className="flex items-center gap-2 rounded-md bg-muted/20 px-2 py-1"
                        >
                          <span className="h-1.5 w-1.5 rounded-full bg-success" />
                          {ip}
                        </li>
                      ))}
                    </ul>
                  )}
                </SectionCard>

                <SectionCard title="Open Ports" icon={<Server className="h-4 w-4" />}>
                  <p className="text-3xl font-semibold tabular-nums">
                    {host.ports.filter((p) => p.state === "open").length}
                    <span className="ml-1 text-sm font-normal text-muted-foreground">
                      / {host.ports.length}
                    </span>
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">exposed services</p>
                </SectionCard>

                <SectionCard title="Exposure" icon={<ShieldCheck className="h-4 w-4" />}>
                  <p className="text-3xl font-semibold tabular-nums">
                    {host.vulnerabilities.length}
                    <span className="ml-1 text-sm font-normal text-muted-foreground">
                      vulns
                    </span>
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {host.technologies.length} technologies detected
                  </p>
                </SectionCard>
              </div>

              {/* Open ports + banners */}
              <SectionCard
                title="Open Ports & Banners"
                description="Services observed on this host"
                icon={<TerminalSquare className="h-4 w-4" />}
              >
                {host.ports.length === 0 ? (
                  <EmptyState
                    icon={<Server className="h-8 w-8" />}
                    title="No ports recorded"
                  />
                ) : (
                  <div className="divide-y divide-border/40">
                    {host.ports.map((p, i) => (
                      <div
                        key={i}
                        className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 md:flex-row md:items-start md:gap-4"
                      >
                        <div className="flex shrink-0 items-center gap-2">
                          <span className="inline-flex items-center justify-center rounded-lg bg-brand-2/10 px-2.5 py-1 font-mono text-base font-semibold text-brand-2">
                            {p.port}
                          </span>
                          <Badge
                            variant={p.state === "open" ? "success" : "warning"}
                            className="text-xs"
                          >
                            {p.state || "unknown"}
                          </Badge>
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium">
                            {p.service || "Unknown Service"}
                            {p.version ? (
                              <span className="ml-1 font-mono text-xs text-muted-foreground">
                                {p.version}
                              </span>
                            ) : null}
                          </p>
                          {p.banner ? (
                            <pre className="mt-1.5 overflow-x-auto rounded-md border border-border bg-surface-2 p-2 font-mono text-[11px] text-muted-foreground">
                              {p.banner}
                            </pre>
                          ) : (
                            <p className="mt-1 text-xs text-muted-foreground">
                              No banner captured.
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>

              <div className="grid gap-4 md:grid-cols-2">
                {/* Technologies */}
                <SectionCard
                  title="Web Technologies"
                  description="Detected on this host"
                  icon={<Cpu className="h-4 w-4" />}
                >
                  {host.technologies.length === 0 ? (
                    <EmptyState
                      icon={<Cpu className="h-8 w-8" />}
                      title="No technologies"
                    />
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {host.technologies.map((t, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-2.5 py-1 text-xs"
                        >
                          <span className="font-medium">{t.name}</span>
                          {t.version ? (
                            <span className="font-mono text-muted-foreground">
                              {t.version}
                            </span>
                          ) : null}
                          {t.confidence > 0 ? (
                            <span className="text-[10px] text-muted-foreground">
                              {t.confidence}%
                            </span>
                          ) : null}
                        </span>
                      ))}
                    </div>
                  )}
                </SectionCard>

                {/* Certificates */}
                <SectionCard
                  title="SSL Certificates"
                  description="TLS certificates observed"
                  icon={<Lock className="h-4 w-4" />}
                >
                  {host.certificates.length === 0 ? (
                    <EmptyState
                      icon={<Lock className="h-8 w-8" />}
                      title="No certificates"
                    />
                  ) : (
                    <div className="space-y-3">
                      {host.certificates.map((c, i) => (
                        <div
                          key={i}
                          className="rounded-lg border border-border bg-muted/20 p-3"
                        >
                          <div className="flex items-center justify-between">
                            <p className="truncate font-mono text-xs">
                              {c.subject || "—"}
                            </p>
                            {c.grade ? (
                              <Badge variant="outline" className="text-xs">
                                {c.grade}
                              </Badge>
                            ) : null}
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {c.issuer || "Unknown issuer"}
                            {c.protocol ? ` · ${c.protocol}` : ""}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </SectionCard>
              </div>

              {/* Vulnerabilities */}
              {host.vulnerabilities.length > 0 && (
                <SectionCard
                  title="Vulnerabilities"
                  description="Known issues on this host"
                  icon={<ShieldAlert className="h-4 w-4" />}
                >
                  <div className="space-y-2">
                    {host.vulnerabilities.map((v) => (
                      <div
                        key={v.id}
                        className="flex items-center justify-between rounded-lg border border-border bg-muted/20 p-3"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{v.name}</p>
                          {v.host ? (
                            <p className="truncate font-mono text-xs text-muted-foreground">
                              {v.host}
                            </p>
                          ) : null}
                        </div>
                        {v.severity ? (
                          <Badge
                            variant={
                              v.severity.toLowerCase() === "critical"
                                ? "destructive"
                                : "warning"
                            }
                            className="text-xs capitalize"
                          >
                            {v.severity}
                          </Badge>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </SectionCard>
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
