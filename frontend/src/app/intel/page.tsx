"use client";

import { useCallback, useState } from "react";
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
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { osintLookup, osintImport, type OsintResult } from "@/lib/api";

function sevVariant(sev: string | null): "destructive" | "warning" | "secondary" {
  if (!sev) return "secondary";
  const s = sev.toLowerCase();
  if (s === "critical" || s === "high") return "destructive";
  return "warning";
}

export default function IntelPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<OsintResult | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);

  const run = useCallback(async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    setLoading(true);
    setError("");
    setData(null);
    setImportResult(null);
    try {
      const res = await osintLookup(trimmed);
      setData(res);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Intelligence lookup failed.");
    } finally {
      setLoading(false);
    }
  }, []);

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
      const detail = e?.response?.data?.detail;
      setImportResult(`Import failed: ${typeof detail === "string" ? detail : "Unknown error"}`);
    } finally {
      setImporting(false);
    }
  }, [data]);

  return (
    <div className="page-container-lg">
      <PageHeader
        title="Intelligence Engine"
        description="Live, key-free OSINT for any domain or company — subdomains, certificates, vulnerabilities, and exposed services, like Shodan."
        icon={<Zap className="h-5 w-5" />}
        breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "Intelligence" }]}
      />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(query);
        }}
        className="relative"
      >
        <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          autoFocus
          placeholder="example.com"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
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
            description="Enter a domain or company to gather live public intelligence — discovered subdomains, TLS certificates, exposed ports with service banners, and known CVEs."
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
                  <EmptyState icon={<Network className="h-8 w-8" />} title="No subdomains" />
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
          </div>
        )}
      </div>
    </div>
  );
}
