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
  Globe,
  Eye,
  ShieldCheck,
  FileWarning,
  Fingerprint,
  Gauge,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { getErrorMessage, osintImport, type OsintResult } from "@/lib/api";
import { useIntelStore } from "@/lib/intelStore";

function sevVariant(sev: string | null): "destructive" | "warning" | "secondary" {
  if (!sev) return "secondary";
  const s = sev.toLowerCase();
  if (s === "critical" || s === "high") return "destructive";
  return "warning";
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
        title="OSINT Intelligence Engine"
        description="Live, key-free OSINT for any domain or company — subdomains, certificates, vulnerabilities, and exposed services, like Shodan."
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
          className="h-12 pl-11 pr-24 font-mono text-sm bg-surface-2/50 border-border/60 focus:border-brand/40 focus:ring-brand/20"
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
        Sources: hackertarget, certspotter, live TLS/DNS, NVD, CISA KEV. No API keys required. Live lookups take ~30-60s.
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
            <p className="text-sm">Probing external intelligence sources…</p>
            <p className="mt-1 text-xs text-brand font-mono">{elapsed}s elapsed</p>
            <p className="mt-1 text-xs">subdomains · certificates · ports · CVEs</p>
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
            title="Investigate any target"
            description="Enter a domain or company to gather live public intelligence — subdomains, certs, exposed ports, and known CVEs."
          />
        ) : (
          <div className="space-y-4">
            {/* Source status strip */}
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.sources_status).map(([k, v]) => {
                const isError = typeof v === "string" && (v.startsWith("error") || v.startsWith("http_"));
                const isWarn = typeof v === "string" && (v === "rate_limited" || v === "no_results" || v === "skipped_no_tech" || v === "no-cert" || v === "no_targets");
                return (
                  <span
                    key={k}
                    className="inline-flex items-center gap-1 rounded-md border border-border/40 bg-surface-2/40 px-2 py-0.5 font-mono text-[10px] text-muted-foreground"
                  >
                    <span className="text-brand">{k}</span>
                    <span className={isError ? "text-destructive" : isWarn ? "text-warning" : "text-success"}>{v}</span>
                  </span>
                );
              })}
            </div>

            {/* Summary stats */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <SectionCard title="Subdomains" icon={<Globe2 className="h-4 w-4" />}>
                <p className="text-3xl font-bold tabular-nums font-mono">{data.subdomains.length}</p>
              </SectionCard>
              <SectionCard title="Open Ports" icon={<Server className="h-4 w-4" />}>
                <p className="text-3xl font-bold tabular-nums font-mono">{data.ports.length}</p>
              </SectionCard>
              <SectionCard title="Certificates" icon={<Lock className="h-4 w-4" />}>
                <p className="text-3xl font-bold tabular-nums font-mono">{data.certificates.length}</p>
              </SectionCard>
              <SectionCard title="CVEs" icon={<ShieldAlert className="h-4 w-4" />}>
                <p className="text-3xl font-bold tabular-nums font-mono text-signal-red">
                  {data.vulnerabilities.length}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {data.vulnerabilities.filter((v) => v.is_kev).length} in CISA KEV
                </p>
              </SectionCard>
            </div>

            {/* Exposed services / ports */}
            <SectionCard
              title="Exposed Services"
              description="Live-probed open ports with service banners"
              icon={<Server className="h-4 w-4" />}
            >
              {data.ports.length === 0 ? (
                <EmptyState
                  icon={<Server className="h-8 w-8" />}
                  title={
                    data.sources_status["port-scan"] === "no_targets"
                      ? "No targets to probe"
                      : data.sources_status["hackertarget"] === "rate_limited" && data.subdomains.length <= 1
                        ? "No ports detected — subdomain enumeration was rate-limited, only apex domain probed"
                        : "No open ports detected"
                  }
                  description={
                    data.sources_status["port-scan"] === "no_targets"
                      ? "No IP addresses could be resolved for this domain."
                      : undefined
                  }
                />
              ) : (
                <div className="divide-y divide-border/40">
                  {data.ports.map((p, i) => (
                    <div key={i} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 md:flex-row md:items-start md:gap-4">
                      <div className="flex shrink-0 items-center gap-2">
                        <span className="inline-flex items-center justify-center rounded-lg bg-brand-2/10 px-2.5 py-1 font-mono text-base font-bold text-brand-2">
                          {p.port}
                        </span>
                        <Badge variant={p.state === "open" ? "success" : "warning"} className="text-xs">
                          {p.state}
                        </Badge>
                        {p.tls ? <Badge variant="outline" className="text-xs">TLS</Badge> : null}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium">
                          {p.service || "Unknown"}
                          {p.title ? (
                            <span className="ml-2 text-xs text-muted-foreground">“{p.title}”</span>
                          ) : null}
                        </p>
                        {p.banner ? (
                          <pre className="mt-1.5 max-h-32 overflow-auto rounded-md border border-border/40 bg-surface-2/60 p-2 font-mono text-[11px] text-muted-foreground">
                            {p.banner}
                          </pre>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>

            <div className="grid gap-4 md:grid-cols-2">
              {/* Subdomains */}
              <SectionCard title="Discovered Subdomains" icon={<Network className="h-4 w-4" />}>
                {data.subdomains.length === 0 ? (
                  <EmptyState icon={<Network className="h-8 w-8" />} title="Nothing returned" />
                ) : (
                  <ul className="space-y-1.5">
                    {data.subdomains.map((s, i) => (
                      <li key={i} className="rounded-md bg-muted/20 px-2 py-1.5">
                        <p className="truncate font-mono text-xs font-medium">{s.hostname}</p>
                        {s.ips.length > 0 ? (
                          <p className="truncate font-mono text-[10px] text-muted-foreground">
                            {s.ips.join(", ")}
                          </p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </SectionCard>

              {/* Technologies */}
              <SectionCard title="Detected Technologies" icon={<Cpu className="h-4 w-4" />}>
                {data.technologies.length === 0 ? (
                  <EmptyState
                    icon={<Cpu className="h-8 w-8" />}
                    title={
                      data.ports.length === 0
                        ? "No technologies — no ports open to fingerprint"
                        : "No technologies detected from service banners"
                    }
                  />
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {data.technologies.map((t, i) => (
                      <span
                        key={i}
                        className="rounded-lg border border-border/50 bg-surface-2/50 px-2.5 py-1 text-xs font-medium"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </SectionCard>
            </div>

            {/* Certificates */}
            {data.certificates.length > 0 && (
              <SectionCard title="TLS Certificates" icon={<Lock className="h-4 w-4" />}>
                <div className="space-y-3">
                  {data.certificates.map((c, i) => (
                    <div key={i} className="rounded-lg border border-border/40 bg-muted/20 p-3">
                      <div className="flex items-center justify-between">
                        <p className="truncate font-mono text-xs">{c.subject || "—"}</p>
                        {c.source ? (
                          <Badge variant="outline" className="text-[10px]">
                            {c.source}
                          </Badge>
                        ) : null}
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

            {/* Vulnerabilities */}
            <SectionCard
              title="Known Vulnerabilities"
              description="CVEs from NVD, flagged if present in CISA KEV"
              icon={<ShieldAlert className="h-4 w-4" />}
            >
              {data.vulnerabilities.length === 0 ? (
                <EmptyState
                  icon={<ShieldAlert className="h-8 w-8" />}
                  title={
                    data.sources_status["nvd"] === "skipped_no_tech"
                      ? "No CVEs — no technologies detected to match against"
                      : "No CVEs found"
                  }
                  description={
                    data.sources_status["nvd"] === "skipped_no_tech"
                      ? "CVE lookup requires detected technologies from port/service fingerprinting."
                      : undefined
                  }
                />
              ) : (
                <div className="space-y-2">
                  {data.vulnerabilities.map((v, i) => (
                    <div
                      key={i}
                      className="flex items-start justify-between gap-3 rounded-lg border border-border/40 bg-muted/20 p-3"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm font-semibold">{v.cve_id}</span>
                          {v.is_kev ? (
                            <Badge variant="destructive" className="text-[10px]">
                              KEV
                            </Badge>
                          ) : null}
                        </div>
                        <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                          {v.description}
                        </p>
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

            {/* IP Reputation */}
            {data.ip_reputation && data.ip_reputation.length > 0 && (
              <SectionCard
                title="IP Reputation"
                description="Geolocation, ASN, and threat intelligence for resolved IPs"
                icon={<MapPin className="h-4 w-4" />}
              >
                <div className="space-y-2">
                  {data.ip_reputation.map((r, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between gap-3 rounded-lg border border-border/40 bg-muted/20 p-3"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm font-semibold">{r.ip}</span>
                          {r.country && <Badge variant="outline" className="text-[10px]">{r.country}</Badge>}
                          {r.classification && <Badge variant={r.classification === "malicious" ? "destructive" : "secondary"} className="text-[10px]">{r.classification}</Badge>}
                          {r.noise && <Badge variant="warning" className="text-[10px]">Noise</Badge>}
                          {r.riot && <Badge variant="success" className="text-[10px]">RIOT</Badge>}
                        </div>
                        {r.org && <p className="mt-0.5 text-xs text-muted-foreground truncate max-w-md">{r.org}</p>}
                        {r.hostname && <p className="text-[10px] font-mono text-muted-foreground">{r.hostname}</p>}
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {r.abuse_confidence > 0 && (
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

            {/* WHOIS / Domain Registration */}
            {data.whois && (
              <SectionCard
                title="Domain Registration (WHOIS)"
                description="Domain registration details from RDAP"
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
              </SectionCard>
            )}

            {/* Historical Subdomains (Wayback Machine) */}
            {data.historical_subdomains && data.historical_subdomains.length > 0 && (
              <SectionCard
                title="Historical Subdomains"
                description="Previously discovered subdomains from Wayback Machine"
                icon={<Clock className="h-4 w-4" />}
              >
                <div className="flex flex-wrap gap-2">
                  {data.historical_subdomains.slice(0, 50).map((h, i) => (
                    <span key={i} className="rounded-md border border-border/40 bg-surface-2/40 px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                      {h}
                    </span>
                  ))}
                  {data.historical_subdomains.length > 50 && (
                    <span className="text-xs text-muted-foreground">+{data.historical_subdomains.length - 50} more</span>
                  )}
                </div>
              </SectionCard>
            )}

            {/* Reverse IP */}
            {data.reverse_ip && data.reverse_ip.length > 0 && (
              <SectionCard
                title="Reverse IP Lookup"
                description="Other domains hosted on the same IP addresses"
                icon={<RotateCcw className="h-4 w-4" />}
              >
                <div className="flex flex-wrap gap-2">
                  {data.reverse_ip.map((h, i) => (
                    <span key={i} className="rounded-md border border-border/40 bg-surface-2/40 px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                      {h}
                    </span>
                  ))}
                </div>
              </SectionCard>
            )}

            {/* Risk Score */}
            {data.risk_score && (
              <SectionCard
                title="Risk Assessment"
                description="Automated security posture score"
                icon={<Gauge className="h-4 w-4" />}
              >
                <div className="flex items-center gap-6">
                  <div className={`flex h-20 w-20 items-center justify-center rounded-xl text-2xl font-bold ${
                    data.risk_score.grade === "A" ? "bg-green-500/10 text-green-400" :
                    data.risk_score.grade === "B" ? "bg-blue-500/10 text-blue-400" :
                    data.risk_score.grade === "C" ? "bg-yellow-500/10 text-yellow-400" :
                    data.risk_score.grade === "D" ? "bg-orange-500/10 text-orange-400" :
                    "bg-red-500/10 text-red-400"
                  }`}>
                    {data.risk_score.grade}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-muted-foreground">Score: <span className="font-mono text-foreground">{data.risk_score.score}/100</span></p>
                    <div className="mt-2 flex gap-3 text-xs text-muted-foreground">
                      <span>{data.risk_score.exposed_services} exposed ports</span>
                      <span>{data.risk_score.missing_security_headers} missing headers</span>
                      <span>{data.risk_score.sensitive_paths_found} sensitive paths</span>
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
                        <span className="text-muted-foreground">{f.detail}</span>
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            )}

            {/* WAF / CDN */}
            {data.waf_cdn && (
              <SectionCard
                title="WAF / CDN Detection"
                description="Web application firewall and CDN identification"
                icon={<ShieldCheck className="h-4 w-4" />}
              >
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-muted-foreground">Server</span>
                    <p className="mt-0.5 font-mono text-foreground">{data.waf_cdn.server || "Unknown"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">CDN</span>
                    <p className="mt-0.5 font-mono text-foreground">{data.waf_cdn.cdn || "None detected"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">WAF</span>
                    <p className="mt-0.5 font-mono text-foreground">{data.waf_cdn.waf || "None detected"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Powered By</span>
                    <p className="mt-0.5 font-mono text-foreground">{data.waf_cdn.powered_by || "Unknown"}</p>
                  </div>
                </div>
                {data.waf_cdn.technologies_from_headers.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {data.waf_cdn.technologies_from_headers.map((t, i) => (
                      <span key={i} className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary">{t}</span>
                    ))}
                  </div>
                )}
              </SectionCard>
            )}

            {/* Email Security */}
            {data.email_security && (
              <SectionCard
                title="Email Security"
                description="DMARC, SPF, DKIM, and MX analysis"
                icon={<Mail className="h-4 w-4" />}
              >
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-muted-foreground">DMARC</span>
                    <p className="mt-0.5 font-mono text-foreground">
                      {data.email_security.dmarc_policy ? (
                        <span className="text-green-400">v=DMARC1; p={data.email_security.dmarc_policy}</span>
                      ) : (
                        <span className="text-red-400">Not found</span>
                      )}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">SPF</span>
                    <p className="mt-0.5 font-mono text-foreground">
                      {data.email_security.spf_record ? (
                        <span className="text-green-400">Found</span>
                      ) : (
                        <span className="text-red-400">Not found</span>
                      )}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">DKIM</span>
                    <p className="mt-0.5 font-mono text-foreground">
                      {data.email_security.dkim_found.length > 0 ? (
                        <span className="text-green-400">{data.email_security.dkim_found.length} selectors</span>
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

            {/* Security Headers */}
            {data.security_headers && (
              <SectionCard
                title="Security Headers"
                description={`Security header audit — score: ${data.security_headers.score}/100`}
                icon={<Eye className="h-4 w-4" />}
              >
                <div className="flex items-center gap-4 mb-3">
                  <div className={`flex h-12 w-12 items-center justify-center rounded-lg text-lg font-bold ${
                    data.security_headers.score >= 80 ? "bg-green-500/10 text-green-400" :
                    data.security_headers.score >= 50 ? "bg-yellow-500/10 text-yellow-400" :
                    "bg-red-500/10 text-red-400"
                  }`}>
                    {data.security_headers.score}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {data.security_headers.issues.length === 0
                      ? "All security headers present"
                      : `${data.security_headers.issues.length} issues detected`}
                  </div>
                </div>
                {data.security_headers.issues.length > 0 && (
                  <div className="space-y-1">
                    {data.security_headers.issues.map((issue, i) => (
                      <div key={i} className="flex items-center gap-2 text-[10px] text-muted-foreground">
                        <AlertTriangle className="h-3 w-3 text-yellow-400 shrink-0" />
                        {issue}
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            )}

            {/* Sensitive Paths */}
            {data.sensitive_paths && data.sensitive_paths.length > 0 && (
              <SectionCard
                title="Sensitive Paths Found"
                description="Exposed files and endpoints discovered"
                icon={<FileWarning className="h-4 w-4" />}
              >
                <div className="space-y-1.5">
                  {data.sensitive_paths.map((p, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <Badge variant={p.status === 200 ? "destructive" : "warning"} className="shrink-0 text-[9px]">
                        {p.status}
                      </Badge>
                      <span className="font-mono text-foreground">{p.path}</span>
                      <span className="text-muted-foreground ml-auto">{p.category}</span>
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}

            {/* Web Fingerprint */}
            {data.web_fingerprint && data.web_fingerprint.technologies.length > 0 && (
              <SectionCard
                title="Web Fingerprint"
                description="Technologies detected from the main page"
                icon={<Fingerprint className="h-4 w-4" />}
              >
                {data.web_fingerprint.title && (
                  <p className="mb-2 text-xs text-muted-foreground">Title: <span className="text-foreground">{data.web_fingerprint.title}</span></p>
                )}
                <div className="flex flex-wrap gap-1.5">
                  {data.web_fingerprint.technologies.map((tech, i) => (
                    <span key={i} className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary">{tech}</span>
                  ))}
                </div>
                {data.web_fingerprint.email_addresses.length > 0 && (
                  <div className="mt-3">
                    <p className="text-[10px] text-muted-foreground mb-1">Emails found:</p>
                    <div className="flex flex-wrap gap-1.5">
                      {data.web_fingerprint.email_addresses.map((e, i) => (
                        <span key={i} className="font-mono text-[10px] text-muted-foreground">{e}</span>
                      ))}
                    </div>
                  </div>
                )}
                {data.web_fingerprint.social_links.length > 0 && (
                  <div className="mt-3">
                    <p className="text-[10px] text-muted-foreground mb-1">Social links:</p>
                    <div className="flex flex-wrap gap-1.5">
                      {data.web_fingerprint.social_links.map((link, i) => (
                        <span key={i} className="font-mono text-[10px] text-primary truncate max-w-[200px]">{link}</span>
                      ))}
                    </div>
                  </div>
                )}
              </SectionCard>
            )}
          </div>
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
