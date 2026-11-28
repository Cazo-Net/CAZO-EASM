"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  ExternalLink,
  Eye,
  FlaskConical,
  Globe,
  Loader2,
  Mail,
  Plus,
  RefreshCw,
  ShieldAlert,
  Trash2,
  Plug,
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  checkThreatIntelMonitor,
  createThreatIntelMonitor,
  deleteThreatIntelMonitor,
  getErrorMessage,
  getExploitedIntel,
  getThreatIntelSample,
  getThreatIntelSources,
  listThreatIntelFindings,
  listThreatIntelMonitors,
  updateThreatIntelFinding,
  type ExploitedIntel,
  type KevItem,
  type ThreatIntelFinding,
  type ThreatIntelMonitor,
  type ThreatIntelSource,
} from "@/lib/api";

const SEVERITY_CLASS: Record<string, string> = {
  critical: "text-red-400 bg-red-500/10 border-red-500/20",
  high: "text-orange-400 bg-orange-500/10 border-orange-500/20",
  medium: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
  low: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  info: "text-green-400 bg-green-500/10 border-green-500/20",
};

const CATEGORY_LABEL: Record<string, string> = {
  breach_site: "Your site was breached",
  breach_domain: "Staff addresses in a breach",
  breach_account: "Address in a breach",
  malware_url: "Malware URL",
  blocklist: "On a blocklist",
  threat_ioc: "Malware indicator",
  lookalike_domain: "Look-alike domain",
};

const SOURCE_LABEL: Record<string, string> = {
  hibp: "Have I Been Pwned",
  urlhaus: "abuse.ch URLhaus",
  threatfox: "abuse.ch ThreatFox",
  dns: "Live DNS",
};

const STATUS_TEXT: Record<string, string> = {
  ok: "checked",
  not_configured: "not configured",
  domain_not_verified_in_hibp: "verify the domain in HIBP",
  invalid_key: "key rejected",
  rate_limited: "rate limited, retry later",
  not_authorized: "not in scope",
};

function fmtDate(s?: string | null) {
  if (!s) return "";
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString();
}

function SampleBanner({ notice }: { notice: string }) {
  return (
    <div className="mb-4 flex items-start gap-2 rounded-lg border-2 border-dashed border-amber-500/50 bg-amber-500/10 p-3 text-sm text-amber-300">
      <FlaskConical className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{notice}</span>
    </div>
  );
}

function FindingRow({
  f,
  onStatus,
}: {
  f: ThreatIntelFinding;
  onStatus?: (id: string, s: ThreatIntelFinding["status"]) => void;
}) {
  const addrs: string[] = f.data?.affected_addresses || [];
  const classes: string[] = f.data?.data_classes || [];
  return (
    <div className={`rounded-lg border p-4 ${f.is_sample ? "border-dashed border-amber-500/40" : "border-border"}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {f.is_sample && (
              <Badge variant="outline" className="border-amber-500/50 text-[10px] text-amber-400">
                SAMPLE
              </Badge>
            )}
            <span className="text-sm font-medium">{f.title}</span>
          </div>
          {f.summary && <p className="mt-1 line-clamp-3 text-xs text-muted-foreground">{f.summary}</p>}
          {classes.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {classes.slice(0, 8).map((c) => (
                <span key={c} className="rounded bg-muted px-1.5 py-0.5 text-[10px]">{c}</span>
              ))}
            </div>
          )}
          {addrs.length > 0 && (
            <details className="mt-2 text-xs">
              <summary className="cursor-pointer text-muted-foreground">
                {addrs.length} affected address{addrs.length === 1 ? "" : "es"}
              </summary>
              <div className="mt-1 font-mono text-[11px] text-muted-foreground">{addrs.join(", ")}</div>
            </details>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
            <span>{CATEGORY_LABEL[f.category] || f.category}</span>
            <span>Source: {SOURCE_LABEL[f.source] || f.source}</span>
            {f.observed_at && <span>Date: {fmtDate(f.observed_at)}</span>}
            {f.first_seen && <span>First seen here: {fmtDate(f.first_seen)}</span>}
            {f.reference_url && (
              <a href={f.reference_url} target="_blank" rel="noopener noreferrer"
                 className="inline-flex items-center gap-1 hover:text-foreground">
                Evidence <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <Badge variant="outline" className={`text-[10px] capitalize ${SEVERITY_CLASS[f.severity] || SEVERITY_CLASS.info}`}>
            {f.severity}
          </Badge>
          {onStatus && !f.is_sample && (
            <select
              value={f.status}
              onChange={(e) => onStatus(f.id, e.target.value as ThreatIntelFinding["status"])}
              className="rounded border border-border bg-background px-1.5 py-0.5 text-[11px]"
              aria-label="Finding status"
            >
              <option value="open">Open</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved</option>
            </select>
          )}
        </div>
      </div>
    </div>
  );
}

function MonitorStatus({ m }: { m: ThreatIntelMonitor }) {
  const entries = Object.entries(m.last_status || {}).filter(([k]) => k !== "reason");
  if (!m.last_checked_at) return <span className="text-[11px] text-muted-foreground">Not checked yet</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([k, v]) => (
        <span key={k} className={`rounded px-1.5 py-0.5 text-[10px] ${v === "ok" ? "bg-green-500/10 text-green-400" : "bg-muted text-muted-foreground"}`}
              title={m.last_status.reason || v}>
          {k}: {STATUS_TEXT[v] || v}
        </span>
      ))}
    </div>
  );
}

function ExposureTab({ showSample }: { showSample: boolean }) {
  const [monitors, setMonitors] = useState<ThreatIntelMonitor[]>([]);
  const [findings, setFindings] = useState<ThreatIntelFinding[]>([]);
  const [sample, setSample] = useState<{ notice: string; findings: ThreatIntelFinding[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [kind, setKind] = useState<"domain" | "email">("domain");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [filter, setFilter] = useState<"open" | "all">("open");

  const load = useCallback(async () => {
    try {
      const [m, f] = await Promise.all([listThreatIntelMonitors(), listThreatIntelFindings()]);
      setMonitors(m);
      setFindings(f);
    } catch (e) {
      setError(getErrorMessage(e, "Could not load monitors"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (showSample && !sample) {
      getThreatIntelSample().then(setSample).catch(() => setSample(null));
    }
  }, [showSample, sample]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    setBusy("add");
    setError("");
    try {
      const m = await createThreatIntelMonitor(kind, value.trim());
      setValue("");
      setBusy(m.id);
      await checkThreatIntelMonitor(m.id);
      await load();
    } catch (err) {
      setError(getErrorMessage(err, "Could not add monitor"));
    } finally {
      setBusy(null);
    }
  };

  const check = async (id: string) => {
    setBusy(id);
    setError("");
    try {
      await checkThreatIntelMonitor(id);
      await load();
    } catch (err) {
      setError(getErrorMessage(err, "Check failed"));
    } finally {
      setBusy(null);
    }
  };

  const remove = async (id: string) => {
    setBusy(id);
    try {
      await deleteThreatIntelMonitor(id);
      await load();
    } catch (err) {
      setError(getErrorMessage(err, "Could not remove monitor"));
    } finally {
      setBusy(null);
    }
  };

  const setStatus = async (id: string, s: ThreatIntelFinding["status"]) => {
    try {
      const updated = await updateThreatIntelFinding(id, s);
      setFindings((prev) => prev.map((f) => (f.id === id ? updated : f)));
    } catch (err) {
      setError(getErrorMessage(err, "Could not update finding"));
    }
  };

  const shown = filter === "open" ? findings.filter((f) => f.status !== "resolved") : findings;

  return (
    <div className="space-y-6">
      <SectionCard title="What we monitor" icon={<Eye className="h-4 w-4" />}
        description="Only domains in your authorized scope, and addresses on them, can be monitored.">
        <form onSubmit={add} className="flex flex-col gap-2 sm:flex-row">
          <select value={kind} onChange={(e) => setKind(e.target.value as "domain" | "email")}
                  className="rounded-md border border-border bg-background px-2 text-sm" aria-label="Monitor type">
            <option value="domain">Domain</option>
            <option value="email">Email address</option>
          </select>
          <Input value={value} onChange={(e) => setValue(e.target.value)} className="flex-1"
                 placeholder={kind === "domain" ? "yourcompany.com" : "ceo@yourcompany.com"} />
          <Button type="submit" disabled={!value.trim() || busy !== null}>
            {busy === "add" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
            Monitor
          </Button>
        </form>
        <p className="mt-2 text-xs text-muted-foreground">
          Need to add a domain first? Go to <Link href="/scopes" className="underline">Scopes</Link>.
        </p>
        {error && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-sm text-red-400">
            <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
          </div>
        )}
        <div className="mt-4 space-y-2">
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          ) : monitors.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing monitored yet.</p>
          ) : (
            monitors.map((m) => (
              <div key={m.id} className="flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    {m.kind === "domain" ? <Globe className="h-4 w-4" /> : <Mail className="h-4 w-4" />}
                    <span className="truncate font-mono">{m.value}</span>
                    {m.open_findings > 0 && <Badge variant="destructive" className="text-[10px]">{m.open_findings} open</Badge>}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    {m.last_checked_at && <span className="text-[11px] text-muted-foreground">Checked {fmtDate(m.last_checked_at)}</span>}
                    <MonitorStatus m={m} />
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => check(m.id)} disabled={busy !== null}>
                    {busy === m.id ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="mr-1 h-3.5 w-3.5" />}
                    Check now
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => remove(m.id)} disabled={busy !== null} aria-label="Remove monitor">
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="Findings"
        icon={<ShieldAlert className="h-4 w-4" />}
        description="Each finding links to the source that reported it."
        actions={
          <select value={filter} onChange={(e) => setFilter(e.target.value as "open" | "all")}
                  className="rounded border border-border bg-background px-2 py-1 text-xs" aria-label="Filter findings">
            <option value="open">Open and acknowledged</option>
            <option value="all">All, including resolved</option>
          </select>
        }
      >
        {shown.length === 0 ? (
          <EmptyState icon={<CheckCircle2 className="h-8 w-8" />} title="No findings"
            description={monitors.length ? "The connected sources reported nothing for what you monitor." : "Add a domain or address to start monitoring."} />
        ) : (
          <div className="space-y-3">
            {shown.map((f) => <FindingRow key={f.id} f={f} onStatus={setStatus} />)}
          </div>
        )}
      </SectionCard>

      {showSample && sample && (
        <SectionCard title="Sample findings" icon={<FlaskConical className="h-4 w-4" />}>
          <SampleBanner notice={sample.notice} />
          <div className="space-y-3">
            {sample.findings.map((f) => <FindingRow key={f.id} f={f} />)}
          </div>
        </SectionCard>
      )}
    </div>
  );
}

function KevList({ items, empty }: { items: KevItem[]; empty: string }) {
  if (items.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <div className="space-y-2">
      {items.map((k) => (
        <div key={k.cve_id + (k.technology || "")} className="rounded-lg border border-border/60 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <a href={k.reference_url} target="_blank" rel="noopener noreferrer" className="font-mono text-sm font-semibold hover:underline">
                {k.cve_id}
              </a>
              <span className="text-xs text-muted-foreground">{k.vendor} {k.product}</span>
              {k.ransomware_use === "Known" && <Badge variant="destructive" className="text-[10px]">Used by ransomware</Badge>}
            </div>
            {k.epss != null && (
              <span className="text-[11px] text-muted-foreground" title="FIRST EPSS: probability of exploitation in the next 30 days">
                EPSS {(k.epss * 100).toFixed(1)}%
              </span>
            )}
          </div>
          {k.name && <p className="mt-1 text-xs">{k.name}</p>}
          {k.description && <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{k.description}</p>}
          <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-muted-foreground">
            {k.date_added && <span>Added to KEV {k.date_added}</span>}
            {k.technology && <span>Matched technology: {k.technology}{k.detected_versions?.length ? ` (${k.detected_versions.join(", ")})` : ""}</span>}
            {k.hosts && k.hosts.length > 0 && <span>Hosts: {k.hosts.slice(0, 5).join(", ")}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function ExploitedTab() {
  const [data, setData] = useState<ExploitedIntel | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getExploitedIntel().then(setData).catch((e) => setError(getErrorMessage(e, "Could not load threat feed")));
  }, []);

  if (error) return <p className="text-sm text-red-400">{error}</p>;
  if (!data) return <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />;
  return (
    <div className="space-y-6">
      {data.sources_status.cisa_kev !== "ok" && (
        <p className="text-sm text-amber-400">The CISA KEV feed could not be reached ({data.sources_status.cisa_kev}). Results may be incomplete.</p>
      )}
      <SectionCard title="Exploited vulnerabilities found by your scans" icon={<ShieldAlert className="h-4 w-4" />}
        description="CVEs your scans reported on your assets that CISA lists as exploited in the wild. Fix these first.">
        <KevList items={data.confirmed} empty="None of your open scan findings are on the CISA KEV list." />
      </SectionCard>
      <SectionCard title="Possibly affected products" icon={<AlertTriangle className="h-4 w-4" />}
        description="Exploited vulnerabilities in products your scans detected. Versions are not compared, so check whether yours is affected.">
        <KevList items={data.possible} empty="No detected technology matches a KEV product." />
      </SectionCard>
      <SectionCard title="Newly exploited (last 30 days)" icon={<Eye className="h-4 w-4" />}
        description={`Latest additions to the CISA catalog (${data.kev_total} entries in total).`}>
        <KevList items={data.recent} empty="No new entries in the last 30 days." />
      </SectionCard>
    </div>
  );
}

function SourcesTab() {
  const [sources, setSources] = useState<ThreatIntelSource[] | null>(null);
  useEffect(() => { getThreatIntelSources().then(setSources).catch(() => setSources([])); }, []);
  if (!sources) return <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />;
  return (
    <SectionCard title="Data sources" icon={<Plug className="h-4 w-4" />}
      description="A source that is not configured shows no results. Nothing is filled in or simulated.">
      <div className="space-y-2">
        {sources.map((s) => (
          <div key={s.id} className="flex items-start justify-between gap-3 rounded-lg border border-border/60 p-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm font-medium">
                {s.configured ? <CheckCircle2 className="h-4 w-4 text-green-400" /> : <Circle className="h-4 w-4 text-muted-foreground" />}
                {s.name}
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">{s.provides}</p>
              {!s.configured && (
                <p className="mt-1 text-xs">
                  Needs: {s.requires}
                  {s.url && (
                    <a href={s.url} target="_blank" rel="noopener noreferrer" className="ml-1 inline-flex items-center gap-0.5 underline">
                      get one <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </p>
              )}
            </div>
            <Badge variant={s.configured ? "success" : s.commercial ? "secondary" : "warning"} className="shrink-0 text-[10px]">
              {s.configured ? "Connected" : s.commercial ? "Subscription needed" : "Key needed"}
            </Badge>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

function DarkWebContent() {
  const [showSample, setShowSample] = useState(false);
  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <PageHeader
          title="Dark Web & Threat Intelligence"
          description="Breaches, malware reports and look-alike domains for what you own, plus vulnerabilities being exploited right now. Every result links to its source."
          icon={<Eye className="h-5 w-5" />}
        />
        <div className="mt-2 flex justify-end">
          <Button variant="outline" size="sm" onClick={() => setShowSample((v) => !v)}>
            <FlaskConical className="mr-1 h-3.5 w-3.5" />
            {showSample ? "Hide sample data" : "Show sample data"}
          </Button>
        </div>
        <Tabs defaultValue="exposure" className="mt-4">
          <TabsList>
            <TabsTrigger value="exposure">Exposure</TabsTrigger>
            <TabsTrigger value="exploited">Exploited vulnerabilities</TabsTrigger>
            <TabsTrigger value="sources">Sources</TabsTrigger>
          </TabsList>
          <TabsContent value="exposure" className="mt-4"><ExposureTab showSample={showSample} /></TabsContent>
          <TabsContent value="exploited" className="mt-4"><ExploitedTab /></TabsContent>
          <TabsContent value="sources" className="mt-4"><SourcesTab /></TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export default function DarkWebPage() {
  return (
    <ProtectedRoute>
      <DarkWebContent />
    </ProtectedRoute>
  );
}
