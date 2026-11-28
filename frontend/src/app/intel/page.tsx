"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Search,
  Loader2,
  Globe2,
  Server,
  ShieldAlert,
  Lock,
  Network,
  Cpu,
  CornerDownLeft,
  AlertTriangle,
  Zap,
  Download,
  CheckCircle2,
  MapPin,
  Building,
  Clock,
  RotateCcw,
  Mail,
  ShieldCheck,
  Gauge,
  ExternalLink,
  KeyRound,
  Radar,
  Unlink,
  Copy,
  Database,
} from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/common/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { getErrorMessage, osintImport, type OsintResult, type OsintSource } from "@/lib/api";
import { useIntelStore } from "@/lib/intelStore";

function sevVariant(sev: string | null): "destructive" | "warning" | "secondary" {
  if (!sev) return "secondary";
  const s = sev.toLowerCase();
  if (s === "critical" || s === "high") return "destructive";
  return "warning";
}

function SourceLink({ href, label }: { href?: string | null; label?: string }) {
  if (!href) return null;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-0.5 text-[10px] text-brand hover:underline"
      title={href}
    >
      {label || "source"}
      <ExternalLink className="h-2.5 w-2.5" />
    </a>
  );
}

function sourceTone(status: string): string {
  if (status === "ok" || /^\d+ /.test(status)) return "text-success";
  if (status === "needs_key") return "text-warning";
  if (status.startsWith("error") || status.startsWith("http_") || status === "refused") return "text-destructive";
  return "text-muted-foreground";
}

function sourceLabel(status: string): string {
  const map: Record<string, string> = {
    ok: "ok",
    no_results: "nothing found",
    needs_key: "needs key",
    rate_limited: "rate limited",
    refused: "refused",
    not_run: "not run",
    no_targets: "nothing to check",
    skipped_cdn: "skipped (CDN IPs)",
  };
  return map[status] || status;
}

function SourcesPanel({
  sources,
  subscriptions,
}: {
  sources: OsintSource[];
  subscriptions?: { name: string; why: string; home: string }[];
}) {
  const missingKeys = sources.filter((s) => s.status === "needs_key");
  return (
    <SectionCard
      title="Sources"
      description="Every result below comes from one of these public sources. Open a link to check the data yourself."
      icon={<ShieldCheck className="h-4 w-4" />}
    >
      <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3" data-testid="osint-sources">
        {sources.map((s) => (
          <div key={s.id} className="flex items-center justify-between gap-2 rounded-md border border-border bg-surface-2 px-2 py-1.5">
            <div className="min-w-0">
              <p className="truncate text-xs font-medium">{s.name}</p>
              <p className="truncate text-[10px] text-muted-foreground">{s.category}</p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-0.5">
              <span className={`font-mono text-[10px] ${sourceTone(s.status)}`}>
                {s.status === "needs_key" ? (
                  <span className="inline-flex items-center gap-0.5"><KeyRound className="h-2.5 w-2.5" />needs key</span>
                ) : sourceLabel(s.status)}
              </span>
              <SourceLink href={s.link} label="open" />
            </div>
          </div>
        ))}
      </div>
      {missingKeys.length > 0 && (
        <p className="mt-3 text-[11px] text-muted-foreground">
          Not checked because no API key is configured:{" "}
          {missingKeys.map((s) => `${s.name} (${s.key_env})`).join(", ")}. Nothing is guessed for these sources.
        </p>
      )}
      {subscriptions && subscriptions.length > 0 && (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Not included (paid subscription needed):{" "}
          {subscriptions.map((s, i) => (
            <span key={s.name}>
              {i > 0 ? "; " : ""}
              <a href={s.home} target="_blank" rel="noopener noreferrer" className="hover:underline" title={s.why}>
                {s.name}
              </a>
            </span>
          ))}
          .
        </p>
      )}
    </SectionCard>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="text-sm">{children}</div>
    </div>
  );
}

function CompanyCard({ company }: { company: NonNullable<OsintResult["company"]> | null | undefined }) {
  if (!company) {
    return (
      <SectionCard title="Company Profile" icon={<Building className="h-4 w-4" />}>
        <p className="text-xs text-muted-foreground">
          No public company record is linked to this domain (Wikidata official website, GLEIF). Nothing is guessed from
          the name. For official registry data (incorporation, directors, shareholders) see a national company registry.
        </p>
      </SectionCard>
    );
  }
  const wd = company.wikidata;
  const le = company.legal_entity;
  const owners = Array.from(new Set([...(wd?.owners || []), ...(wd?.parents || [])]));
  return (
    <SectionCard
      title={`Company Profile${company.name ? `: ${company.name}` : ""}`}
      description={wd?.description || "Who is behind this domain, from public records linked to it"}
      icon={<Building className="h-4 w-4" />}
    >
      <div className="grid gap-3 md:grid-cols-3" data-testid="osint-company">
        {wd?.founded && <Field label="Founded">{new Date(wd.founded).getFullYear()}</Field>}
        {le?.created && <Field label="Legal entity created">{le.created}</Field>}
        {wd && wd.industries.length > 0 && <Field label="What they do">{wd.industries.join(", ")}</Field>}
        {owners.length > 0 && <Field label="Owned by / parent">{owners.join(", ")}</Field>}
        {le?.ultimate_parent?.legal_name && (
          <Field label="Ultimate parent (GLEIF)">
            {le.ultimate_parent.legal_name} <SourceLink href={le.ultimate_parent.source_url} label="LEI" />
          </Field>
        )}
        {wd && wd.founders.length > 0 && <Field label="Founded by">{wd.founders.join(", ")}</Field>}
        {wd && (wd.headquarters.length > 0 || wd.countries.length > 0) && (
          <Field label="Headquarters">{[...wd.headquarters, ...wd.countries].join(", ")}</Field>
        )}
        {wd?.employees != null && <Field label="Employees">{wd.employees.toLocaleString()}</Field>}
        {wd && wd.listings.length > 0 && <Field label="Listed on">{wd.listings.join(", ")}</Field>}
        {le && (
          <Field label="Legal entity">
            {le.legal_name} · {le.jurisdiction}
            {le.status ? ` · ${le.status.toLowerCase()}` : ""}
          </Field>
        )}
        {company.domain_registrant && <Field label="Domain registrant">{company.domain_registrant}</Field>}
        {company.domain_registered && (
          <Field label="Domain registered">{new Date(company.domain_registered).toLocaleDateString()}</Field>
        )}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {wd && <SourceLink href={wd.source_url} label="Wikidata" />}
        {le && <SourceLink href={le.source_url} label="GLEIF" />}
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">{company.note}</p>
    </SectionCard>
  );
}

function IntelContent() {
  const { query: q, loading, error, data, elapsed, run, reset } = useIntelStore();
  const [localQuery, setLocalQuery] = useState(q);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);

  useEffect(() => {
    setLocalQuery(q);
  }, [q]);

  const handleImport = useCallback(async () => {
    if (!data?.query) return;
    setImporting(true);
    setImportResult(null);
    try {
      const res = await osintImport(data.query);
      const counts = res.imported;
      const total = Object.values(counts).reduce((a, b) => a + b, 0);
      setImportResult(`Imported ${total} records: ${counts.subdomains} subdomains, ${counts.cert_assets} certs, ${counts.vulnerabilities} CVEs`);
    } catch (e: any) {
      setImportResult(`Import failed: ${getErrorMessage(e, "Unknown error")}`);
    } finally {
      setImporting(false);
    }
  }, [data]);

  const handleSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    setImportResult(null);
    run(localQuery);
  }, [localQuery, run]);

  return (
    <div className="page-container-lg">
      <PageHeader
        title="OSINT Lookup"
        description="Passive public intelligence for your authorized domains: subdomains, certificates, DNS and email security, registration, hosting, and what Shodan has seen exposed. Your servers are not contacted."
        icon={<Zap className="h-5 w-5" />}
        breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "Intelligence" }]}
      />

      <form
        onSubmit={handleSearch}
        className="relative"
      >
        <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          autoFocus
          placeholder="example.com"
          value={localQuery}
          onChange={(e) => setLocalQuery(e.target.value)}
          className="h-12 pl-11 pr-24 font-mono text-sm bg-surface-2 border-border focus:border-brand/40 focus:ring-brand/20"
        />
        <Button
          type="submit"
          size="sm"
          className="absolute right-2 top-1/2 -translate-y-1/2"
          disabled={loading}
        >
          {loading ? (
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
          ) : (
            <CornerDownLeft className="mr-1 h-3.5 w-3.5" />
          )}
          Scan
        </Button>
      </form>
      <p className="mt-2 text-xs text-muted-foreground">
        Passive only: certificate transparency, passive DNS, public DNS, RDAP, Shodan InternetDB/CVEDB, ipinfo, GreyNoise and more. Each result links to its source. Lookups take about 20-60s.
      </p>

      {data && (
        <div className="mt-3 flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={handleImport}
            disabled={importing}
            className="gap-1.5"
          >
            {importing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Download className="h-3.5 w-3.5" />
            )}
            Import to Inventory
          </Button>
          {importResult && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <CheckCircle2 className="h-3.5 w-3.5 text-success" />
              {importResult}
            </span>
          )}
        </div>
      )}

      <div className="mt-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
            <Loader2 className="mb-3 h-8 w-8 animate-spin text-brand" />
            <p className="text-sm">Querying public intelligence sources…</p>
            <p className="mt-1 text-xs text-brand font-mono">{elapsed}s elapsed</p>
            <p className="mt-1 text-xs">certificate transparency · passive DNS · registration · exposure</p>
          </div>
        ) : error ? (
          <EmptyState
            icon={<AlertTriangle className="h-8 w-8" />}
            title="Lookup failed"
            description={error}
          />
        ) : !data ? (
          <EmptyState
            icon={<Globe2 className="h-8 w-8" />}
            title="Look up one of your domains"
            description="Enter a domain from your authorized scopes. Results come from public datasets only; nothing is sent to the domain's own servers."
          />
        ) : (
          <Tabs defaultValue="overview" className="space-y-4">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="exposure">Exposure ({data.ports.length + data.vulnerabilities.length + (data.takeover_candidates?.length || 0)})</TabsTrigger>
              <TabsTrigger value="subdomains">Subdomains & certificates ({data.subdomains.length})</TabsTrigger>
              <TabsTrigger value="dns">DNS & email</TabsTrigger>
              <TabsTrigger value="infra">Hosting & registration</TabsTrigger>
              <TabsTrigger value="threats">Threats ({(data.threat_reports?.length || 0) + (data.breaches?.length || 0) + (data.lookalikes?.length || 0)})</TabsTrigger>
              <TabsTrigger value="sources">Sources</TabsTrigger>
            </TabsList>
            <TabsContent value="overview" className="space-y-4">
                {"company" in data && <CompanyCard company={data.company} />}
                {/* Summary stats */}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <SectionCard title="Subdomains" icon={<Globe2 className="h-4 w-4" />}>
                    <p className="text-3xl font-semibold tabular-nums">{data.subdomains.length}</p>
                  </SectionCard>
                  <SectionCard title="Open Ports" icon={<Server className="h-4 w-4" />}>
                    <p className="text-3xl font-semibold tabular-nums">{data.ports.length}</p>
                  </SectionCard>
                  <SectionCard title="Certificates" icon={<Lock className="h-4 w-4" />}>
                    <p className="text-3xl font-semibold tabular-nums">{data.certificates.length}</p>
                  </SectionCard>
                  <SectionCard title="CVEs" icon={<ShieldAlert className="h-4 w-4" />}>
                    <p className="text-3xl font-semibold tabular-nums text-signal-red">
                      {data.vulnerabilities.length}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {data.vulnerabilities.filter((v) => v.is_kev).length} in CISA KEV · potential, unverified
                    </p>
                  </SectionCard>
                </div>
                {/* Risk Score */}
                {data.risk_score && (
                  <SectionCard
                    title="Risk Assessment"
                    description="Scored only from the sourced facts on this page"
                    icon={<Gauge className="h-4 w-4" />}
                  >
                    <div className="flex items-center gap-6">
                      <div className={`flex h-20 w-20 items-center justify-center rounded-xl text-2xl font-semibold ${
                        data.risk_score.grade === "A" ? "bg-success/10 text-success" :
                        data.risk_score.grade === "B" ? "bg-blue-500/10 text-blue-400" :
                        data.risk_score.grade === "C" ? "bg-yellow-500/10 text-yellow-400" :
                        data.risk_score.grade === "D" ? "bg-orange-500/10 text-orange-400" :
                        "bg-destructive/10 text-destructive"
                      }`}>
                        {data.risk_score.grade}
                      </div>
                      <div className="flex-1">
                        <p className="text-sm text-muted-foreground">Score: <span className="font-mono text-foreground">{data.risk_score.score}/100</span></p>
                        <div className="mt-2 flex gap-3 text-xs text-muted-foreground">
                          <span>{data.risk_score.exposed_services} exposed services</span>
                          <span>{data.risk_score.findings.length} findings</span>
                        </div>
                      </div>
                    </div>
                    {data.risk_score.findings.length > 0 && (
                      <div className="mt-4 space-y-1.5">
                        {data.risk_score.findings.map((f, i) => (
                          <div key={i} className="flex items-start gap-2 text-xs">
                            <Badge variant={f.severity === "critical" || f.severity === "high" ? "destructive" : f.severity === "medium" ? "warning" : "secondary"} className="shrink-0 text-[9px]">
                              {f.severity}
                            </Badge>
                            <span className="text-muted-foreground">
                              {f.detail}{" "}
                              <SourceLink href={f.source_url} label={f.source || "source"} />
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </SectionCard>
                )}
            </TabsContent>
            <TabsContent value="exposure" className="space-y-4">
                {/* Exposed services / ports */}
                <SectionCard
                  title="Exposed Services"
                  description="Open ports Shodan's own crawlers last saw on this domain's IPs (not probed by us)"
                  icon={<Server className="h-4 w-4" />}
                >
                  {data.ports.length === 0 ? (
                    <EmptyState
                      icon={<Server className="h-8 w-8" />}
                      title={
                        data.sources_status["shodan-internetdb"] === "no_targets"
                          ? "No IP addresses resolved for this domain"
                          : "Shodan has no open ports on record for these IPs"
                      }
                    />
                  ) : (
                    <div className="divide-y divide-border/40">
                      {data.ports.map((p, i) => (
                        <div key={i} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 md:flex-row md:items-center md:gap-4">
                          <div className="flex shrink-0 items-center gap-2">
                            <span className="inline-flex items-center justify-center rounded-lg bg-brand-2/10 px-2.5 py-1 font-mono text-base font-semibold text-brand-2">
                              {p.port}
                            </span>
                            {p.tls ? <Badge variant="outline" className="text-xs">TLS</Badge> : null}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium">
                              {p.service || "Unknown service"}
                              {p.ip ? <span className="ml-2 font-mono text-xs text-muted-foreground">{p.ip}</span> : null}
                            </p>
                            {p.hostnames && p.hostnames.length > 0 ? (
                              <p className="truncate font-mono text-[10px] text-muted-foreground">{p.hostnames.join(", ")}</p>
                            ) : null}
                          </div>
                          <SourceLink href={p.source_url} label="Shodan InternetDB" />
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="mt-3 flex items-center justify-between gap-3 rounded-md border border-dashed border-border p-2.5 text-xs text-muted-foreground">
                    <span>Want to confirm what is open right now, with banners, TLS and web checks? Run a scan.</span>
                    <Link href="/scan/new">
                      <Button variant="outline" size="sm" className="gap-1.5">
                        <Radar className="h-3.5 w-3.5" /> Run a scan
                      </Button>
                    </Link>
                  </div>
                </SectionCard>
                {/* Vulnerabilities */}
                <SectionCard
                  title="Potential Vulnerabilities"
                  description="CVEs Shodan matched to software versions it saw on these IPs. Not verified: confirm with a scan. CVSS, EPSS and CISA KEV status from Shodan CVEDB."
                  icon={<ShieldAlert className="h-4 w-4" />}
                >
                  {data.vulnerabilities.length === 0 ? (
                    <EmptyState
                      icon={<ShieldAlert className="h-8 w-8" />}
                      title="Shodan lists no CVEs for these IPs"
                    />
                  ) : (
                    <div className="space-y-2">
                      {data.vulnerabilities.map((v, i) => (
                        <div
                          key={i}
                          className="flex items-start justify-between gap-3 rounded-lg border border-border bg-muted/20 p-3"
                        >
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-sm font-semibold">{v.cve_id}</span>
                              {v.is_kev ? (
                                <Badge variant="destructive" className="text-[10px]">
                                  KEV
                                </Badge>
                              ) : null}
                              {v.confidence === "potential" ? (
                                <Badge variant="outline" className="text-[10px]">potential</Badge>
                              ) : null}
                            </div>
                            <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                              {v.description || "No summary available."}
                            </p>
                            <div className="mt-1 flex flex-wrap items-center gap-x-3 text-[10px] text-muted-foreground">
                              {v.ips && v.ips.length > 0 ? <span className="font-mono">{v.ips.join(", ")}</span> : null}
                              {v.epss != null ? <span>EPSS {(v.epss * 100).toFixed(1)}%</span> : null}
                              <SourceLink href={v.source_url} label="Shodan" />
                              <SourceLink href={v.reference_url} label="NVD" />
                            </div>
                          </div>
                          <div className="flex shrink-0 flex-col items-end gap-1">
                            <Badge variant={sevVariant(v.severity)} className="text-xs capitalize">
                              {v.severity || "n/a"}
                            </Badge>
                            {v.cvss != null ? (
                              <span className="text-[11px] text-muted-foreground">
                                CVSS {v.cvss}
                              </span>
                            ) : null}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </SectionCard>
                {/* Subdomain takeover candidates */}
                {data.takeover_candidates && data.takeover_candidates.length > 0 && (
                  <SectionCard
                    title="Subdomain Takeover Risk"
                    description="Subdomains whose CNAME points to a name that no longer exists (from public DNS)"
                    icon={<Unlink className="h-4 w-4" />}
                  >
                    <div className="space-y-2">
                      {data.takeover_candidates.map((t, i) => (
                        <div key={i} className="rounded-lg border border-border bg-muted/20 p-3">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm font-semibold">{t.hostname}</span>
                            <Badge variant={sevVariant(t.severity)} className="text-[10px] capitalize">{t.severity}</Badge>
                            {t.service ? <Badge variant="outline" className="text-[10px]">{t.service}</Badge> : null}
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">{t.detail}</p>
                          <SourceLink href={t.source_url} label="DNS record" />
                        </div>
                      ))}
                    </div>
                  </SectionCard>
                )}
                {/* Technologies */}
                  <SectionCard
                    title="Detected Technologies"
                    description="Products and versions Shodan identified on these IPs"
                    icon={<Cpu className="h-4 w-4" />}
                  >
                    {!data.technology_details || data.technology_details.length === 0 ? (
                      <EmptyState icon={<Cpu className="h-8 w-8" />} title="Shodan has no product data for these IPs" />
                    ) : (
                      <ul className="space-y-1.5">
                        {data.technology_details.map((t, i) => (
                          <li key={i} className="flex items-center justify-between gap-2 rounded-md bg-muted/20 px-2 py-1.5">
                            <div className="min-w-0">
                              <p className="truncate text-xs font-medium">
                                {t.name}
                                {t.version ? <span className="ml-1 font-mono text-muted-foreground">{t.version}</span> : null}
                              </p>
                              <p className="truncate font-mono text-[10px] text-muted-foreground">{t.ips.join(", ")}</p>
                            </div>
                            <SourceLink href={t.source_url} label="Shodan" />
                          </li>
                        ))}
                      </ul>
                    )}
                  </SectionCard>
            </TabsContent>
            <TabsContent value="subdomains" className="space-y-4">
                {/* Subdomains */}
                  <SectionCard title="Discovered Subdomains" icon={<Network className="h-4 w-4" />}>
                    {data.subdomains.length === 0 ? (
                      <EmptyState icon={<Network className="h-8 w-8" />} title="Nothing returned" />
                    ) : (
                      <ul className="max-h-[32rem] space-y-1.5 overflow-auto">
                        {data.subdomains.map((s, i) => (
                          <li key={i} className="rounded-md bg-muted/20 px-2 py-1.5">
                            <p className="truncate font-mono text-xs font-medium">{s.hostname}</p>
                            {s.ips.length > 0 ? (
                              <p className="truncate font-mono text-[10px] text-muted-foreground">
                                {s.ips.join(", ")}
                                {s.cname ? ` · CNAME ${s.cname}` : ""}
                              </p>
                            ) : (
                              <p className="text-[10px] text-muted-foreground">does not resolve now</p>
                            )}
                            <div className="mt-0.5 flex flex-wrap gap-x-2">
                              {s.sources.map((src) =>
                                s.source_links?.[src] ? (
                                  <SourceLink key={src} href={s.source_links[src]} label={src} />
                                ) : (
                                  <span key={src} className="text-[10px] text-muted-foreground">{src}</span>
                                ),
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </SectionCard>
                {/* Certificates */}
                {data.certificates.length > 0 && (
                  <SectionCard
                    title="TLS Certificates"
                    description={`Most recent certificates in public certificate transparency logs (${data.certificates.length} shown)`}
                    icon={<Lock className="h-4 w-4" />}
                  >
                    <div className="max-h-[32rem] space-y-3 overflow-auto">
                      {data.certificates.map((c, i) => (
                        <div key={i} className="rounded-lg border border-border bg-muted/20 p-3">
                          <div className="flex items-center justify-between">
                            <p className="truncate font-mono text-xs">{c.subject || "—"}</p>
                            <SourceLink href={c.source_url} label={c.source || "source"} />
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">Issuer: {c.issuer || "—"}</p>
                          {c.san.length > 0 ? (
                            <p className="mt-1 line-clamp-2 text-[11px] text-muted-foreground">
                              SAN: {c.san.join(", ")}
                            </p>
                          ) : null}
                          {c.not_after ? (
                            <p className="mt-1 text-[11px] text-muted-foreground">
                              Expires: {new Date(c.not_after).toLocaleDateString()}
                            </p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </SectionCard>
                )}
                {/* Historical Subdomains (Wayback Machine) */}
                {data.historical_subdomains && data.historical_subdomains.length > 0 && (
                  <SectionCard
                    title="Historical Subdomains"
                    description="Hostnames the Internet Archive has captured under this domain"
                    icon={<Clock className="h-4 w-4" />}
                  >
                    <div className="flex flex-wrap gap-2">
                      {data.historical_subdomains.slice(0, 50).map((h, i) => (
                        <span key={i} className="rounded-md border border-border bg-surface-2 px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                          {h}
                        </span>
                      ))}
                      {data.historical_subdomains.length > 50 && (
                        <span className="text-xs text-muted-foreground">+{data.historical_subdomains.length - 50} more</span>
                      )}
                    </div>
                  </SectionCard>
                )}
            </TabsContent>
            <TabsContent value="dns" className="space-y-4">
                {/* Email Security */}
                {data.email_security && (
                  <SectionCard
                    title="Email Security"
                    description="SPF, DMARC, DKIM, MX, MTA-STS, TLS-RPT and BIMI from public DNS"
                    icon={<Mail className="h-4 w-4" />}
                  >
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <span className="text-muted-foreground">DMARC</span>
                        <p className="mt-0.5 font-mono text-foreground">
                          {data.email_security.dmarc_policy ? (
                            <span className="text-success">v=DMARC1; p={data.email_security.dmarc_policy}</span>
                          ) : (
                            <span className="text-destructive">Not found</span>
                          )}
                        </p>
                      </div>
                      <div>
                        <span className="text-muted-foreground">SPF</span>
                        <p className="mt-0.5 font-mono text-foreground">
                          {data.email_security.spf_record ? (
                            <span className="text-success">Found</span>
                          ) : (
                            <span className="text-destructive">Not found</span>
                          )}
                        </p>
                      </div>
                      <div>
                        <span className="text-muted-foreground">DKIM</span>
                        <p className="mt-0.5 font-mono text-foreground">
                          {data.email_security.dkim_found.length > 0 ? (
                            <span className="text-success">{data.email_security.dkim_found.length} selectors</span>
                          ) : (
                            <span className="text-yellow-400">None found</span>
                          )}
                        </p>
                      </div>
                      <div>
                        <span className="text-muted-foreground">MX Records</span>
                        <p className="mt-0.5 font-mono text-foreground">{data.email_security.mx_records.length} records</p>
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-muted-foreground md:grid-cols-3">
                      {data.email_security.spf_all ? (
                        <span>
                          SPF ends in <span className="font-mono text-foreground">{data.email_security.spf_all}</span>
                          {data.email_security.spf_lookups != null ? ` · ${data.email_security.spf_lookups} lookups` : ""}
                        </span>
                      ) : null}
                      {data.email_security.dmarc_record ? (
                        <span>
                          DMARC pct {data.email_security.dmarc_pct ?? "?"}
                          {data.email_security.dmarc_rua && data.email_security.dmarc_rua.length > 0 ? " · reports on" : " · no reports"}
                        </span>
                      ) : null}
                      <span>MTA-STS: {data.email_security.mta_sts ? "yes" : "no"}</span>
                      <span>TLS-RPT: {data.email_security.tls_rpt ? "yes" : "no"}</span>
                      <span>BIMI: {data.email_security.bimi ? "yes" : "no"}</span>
                      {data.email_security.dkim_found.length > 0 ? (
                        <span>DKIM selectors: {data.email_security.dkim_found.join(", ")}</span>
                      ) : null}
                    </div>
                    {data.email_security.mx_records.length > 0 && (
                      <div className="mt-3 space-y-1">
                        {data.email_security.mx_records.map((mx, i) => (
                          <div key={i} className="flex items-center gap-2 text-[10px]">
                            <Badge variant="secondary" className="text-[9px]">prio {mx.priority}</Badge>
                            <span className="font-mono text-muted-foreground">{mx.host}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </SectionCard>
                )}
                {/* Edge provider */}
                {data.waf_cdn?.cdn && (
                  <SectionCard
                    title="CDN / Edge Provider"
                    description="Recognised from DNS (CNAME, nameservers) and IP network owner data"
                    icon={<ShieldCheck className="h-4 w-4" />}
                  >
                    <p className="font-mono text-sm">{data.waf_cdn.cdn}</p>
                  </SectionCard>
                )}
            </TabsContent>
            <TabsContent value="infra" className="space-y-4">
                {/* WHOIS / Domain Registration */}
                {data.whois && (
                  <SectionCard
                    title="Domain Registration (WHOIS)"
                    description="Registration data from the registry's RDAP service"
                    icon={<Building className="h-4 w-4" />}
                  >
                    <div className="grid gap-3 md:grid-cols-2">
                      {data.whois.registrar && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground">Registrar</p>
                          <p className="text-sm">{data.whois.registrar}</p>
                        </div>
                      )}
                      {data.whois.registration_date && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground">Registered</p>
                          <p className="text-sm font-mono">{new Date(data.whois.registration_date).toLocaleDateString()}</p>
                        </div>
                      )}
                      {data.whois.expiration_date && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground">Expires</p>
                          <p className="text-sm font-mono">{new Date(data.whois.expiration_date).toLocaleDateString()}</p>
                        </div>
                      )}
                      {data.whois.abuse_email && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground">Registrar abuse contact</p>
                          <p className="text-sm font-mono text-xs">{data.whois.abuse_email}</p>
                        </div>
                      )}
                      {data.whois.dnssec != null && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground">DNSSEC</p>
                          <p className={`text-sm ${data.whois.dnssec ? "text-success" : "text-warning"}`}>
                            {data.whois.dnssec ? "Signed" : "Not signed"}
                          </p>
                        </div>
                      )}
                      {data.whois.nameservers.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground">Nameservers</p>
                          <p className="text-sm font-mono text-xs">{data.whois.nameservers.join(", ")}</p>
                        </div>
                      )}
                    </div>
                    {data.whois.status.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs font-medium text-muted-foreground mb-1">Status</p>
                        <div className="flex flex-wrap gap-1">
                          {data.whois.status.map((s, i) => (
                            <Badge key={i} variant="outline" className="text-[10px]">{s}</Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="mt-2">
                      <SourceLink href={data.whois.source_url} label="RDAP record" />
                    </div>
                  </SectionCard>
                )}
                {/* IP Reputation */}
                {data.ip_reputation && data.ip_reputation.length > 0 && (
                  <SectionCard
                    title="IP Reputation"
                    description="Hosting network, location and reputation for resolved IPs"
                    icon={<MapPin className="h-4 w-4" />}
                  >
                    <div className="space-y-2">
                      {data.ip_reputation.map((r, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between gap-3 rounded-lg border border-border bg-muted/20 p-3"
                        >
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-sm font-semibold">{r.ip}</span>
                              {r.country && <Badge variant="outline" className="text-[10px]">{r.country}</Badge>}
                              {r.classification && <Badge variant={r.classification === "malicious" ? "destructive" : "secondary"} className="text-[10px]">{r.classification}</Badge>}
                              {r.noise && <Badge variant="warning" className="text-[10px]">Noise</Badge>}
                              {r.riot && <Badge variant="success" className="text-[10px]">RIOT</Badge>}
                            </div>
                            {r.org && (
                              <p className="mt-0.5 max-w-md truncate text-xs text-muted-foreground">
                                {r.asn ? <span className="font-mono">{r.asn} </span> : null}
                                {r.org}
                              </p>
                            )}
                            {(() => {
                              const net = data.ip_networks?.find((n) => n.ip === r.ip);
                              return net ? (
                                <p className="text-[10px] text-muted-foreground">
                                  Network {net.cidr.join(", ") || net.range} · {net.network_name}
                                  {net.owner ? ` · ${net.owner}` : ""}
                                </p>
                              ) : null;
                            })()}
                            <div className="mt-0.5 flex gap-2">
                              {Object.entries(r.links || {}).map(([k, href]) => (
                                <SourceLink key={k} href={href} label={k} />
                              ))}
                              <SourceLink href={data.ip_networks?.find((n) => n.ip === r.ip)?.source_url} label="rdap" />
                            </div>
                            {r.hostname && <p className="text-[10px] font-mono text-muted-foreground">{r.hostname}</p>}
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            {r.abuse_confidence != null && r.abuse_confidence > 0 && (
                              <Badge variant={r.abuse_confidence > 50 ? "destructive" : "warning"} className="text-[10px]">
                                Abuse: {r.abuse_confidence}%
                              </Badge>
                            )}
                            {r.city && <span className="text-[10px] text-muted-foreground">{r.city}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </SectionCard>
                )}
                {/* Co-hosted domains */}
                {data.cohosted_domains && data.cohosted_domains.length > 0 && (
                  <SectionCard
                    title="Domains on the Same IPs"
                    description="Other domains hosted on this domain's (non-CDN) IP addresses, from reverse IP data"
                    icon={<RotateCcw className="h-4 w-4" />}
                  >
                    <div className="flex flex-wrap gap-2">
                      {data.cohosted_domains.map((c, i) => (
                        <a
                          key={i}
                          href={c.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={`${c.ip} · ${c.source}`}
                          className={`rounded-md border px-2 py-0.5 font-mono text-[10px] hover:underline ${
                            c.same_domain ? "border-brand/40 text-brand" : "border-border bg-surface-2 text-muted-foreground"
                          }`}
                        >
                          {c.domain}
                        </a>
                      ))}
                    </div>
                  </SectionCard>
                )}
            </TabsContent>
            <TabsContent value="threats" className="space-y-4">
                {/* Threat reports / blocklists */}
                {data.threat_reports && data.threat_reports.length > 0 && (
                  <SectionCard
                    title="Blocklists & Threat Reports"
                    description="Reports that name this domain in abuse.ch threat feeds"
                    icon={<AlertTriangle className="h-4 w-4" />}
                  >
                    <div className="space-y-2">
                      {data.threat_reports.map((r, i) => (
                        <div key={i} className="rounded-lg border border-border bg-muted/20 p-3">
                          <div className="flex items-center gap-2">
                            <Badge variant={sevVariant(r.severity)} className="text-[10px] capitalize">{r.severity}</Badge>
                            <span className="text-sm">{r.title}</span>
                          </div>
                          {r.summary ? <p className="mt-1 text-xs text-muted-foreground">{r.summary}</p> : null}
                          <SourceLink href={r.source_url} label={r.source} />
                        </div>
                      ))}
                    </div>
                  </SectionCard>
                )}
                {/* Breaches */}
                {data.breaches && data.breaches.length > 0 && (
                  <SectionCard
                    title="Breach Exposure"
                    description="Known data breaches from Have I Been Pwned"
                    icon={<Database className="h-4 w-4" />}
                  >
                    <div className="space-y-2">
                      {data.breaches.map((b, i) => (
                        <div key={i} className="rounded-lg border border-border bg-muted/20 p-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-medium">{b.title}</span>
                            <Badge variant={sevVariant(b.severity)} className="text-[10px] capitalize">{b.severity}</Badge>
                          </div>
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            {b.data_classes && b.data_classes.length > 0 ? `Exposed: ${b.data_classes.join(", ")}. ` : ""}
                            {b.pwn_count ? `${b.pwn_count.toLocaleString()} accounts in the breach.` : ""}
                          </p>
                          <SourceLink href={b.source_url} label="Have I Been Pwned" />
                        </div>
                      ))}
                    </div>
                  </SectionCard>
                )}
                {/* Look-alike domains */}
                {data.lookalikes && data.lookalikes.length > 0 && (
                  <SectionCard
                    title="Look-alike Domains"
                    description="Registered domains that resemble this one. Registered does not mean malicious; ones that can receive email are worth a look."
                    icon={<Copy className="h-4 w-4" />}
                  >
                    <div className="grid gap-2 sm:grid-cols-2">
                      {data.lookalikes.map((l, i) => (
                        <div key={i} className="flex items-center justify-between gap-2 rounded-md border border-border bg-muted/20 px-2 py-1.5">
                          <div className="min-w-0">
                            <p className="truncate font-mono text-xs">{l.domain}</p>
                            <p className="text-[10px] text-muted-foreground">
                              {l.technique}
                              {l.mx_records.length > 0 ? " · receives email" : ""}
                            </p>
                          </div>
                          <SourceLink href={l.source_url} label="certs" />
                        </div>
                      ))}
                    </div>
                  </SectionCard>
                )}
                {!data.threat_reports?.length && !data.breaches?.length && !data.lookalikes?.length && (
                  <EmptyState
                    icon={<ShieldCheck className="h-8 w-8" />}
                    title="No breaches, blocklist entries or look-alike domains found"
                    description="Sources that need a key are listed on the Sources tab; they were not checked."
                  />
                )}
            </TabsContent>
            <TabsContent value="sources" className="space-y-4">
                {data.sources && data.sources.length > 0 && (
                  <SourcesPanel sources={data.sources} subscriptions={data.subscription_sources} />
                )}
            </TabsContent>
          </Tabs>
        )}
      </div>
    </div>
  );
}

export default function IntelPage() {
  return (
    <ProtectedRoute>
      <IntelContent />
    </ProtectedRoute>
  );
}
