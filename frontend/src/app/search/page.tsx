"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Search,
  Loader2,
  Globe2,
  Server,
  ShieldAlert,
  Network,
  CornerDownLeft,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { searchAssets, type SearchResult } from "@/lib/api";

const FILTER_SUGGESTIONS = [
  "port:443",
  "service:ssh",
  "asn:AS13335",
  "org:Cloudflare",
  "tech:WordPress",
  "hostname:api",
  "severity:high",
];

function ResultCard({ r }: { r: SearchResult }) {
  return (
    <Link
      href={`/assets?host=${encodeURIComponent(r.hostname)}`}
      className="block rounded-xl border border-border/50 bg-card/60 p-4 transition-all duration-200 hover:border-brand/30 hover:bg-card/80 hover:shadow-lg hover:shadow-brand/5"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-2">
          <Globe2 className="h-4 w-4 shrink-0 text-brand" />
          <span className="truncate font-mono text-sm font-semibold text-foreground">
            {r.hostname}
          </span>
          {r.is_alive ? (
            <span className="h-2 w-2 shrink-0 rounded-full bg-success shadow-sm shadow-success/50" />
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {r.asn ? (
            <Badge variant="outline" className="font-mono text-[10px]">
              {r.asn}
            </Badge>
          ) : null}
          {r.port_count > 0 ? (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Server className="h-3 w-3" />
              {r.port_count}
            </span>
          ) : null}
          {r.vulnerability_count > 0 ? (
            <span className="inline-flex items-center gap-1 text-xs text-signal-red">
              <ShieldAlert className="h-3 w-3" />
              {r.vulnerability_count}
            </span>
          ) : null}
        </div>
      </div>

      {r.ip_addresses.length > 0 ? (
        <p className="mt-2 truncate font-mono text-xs text-muted-foreground">
          {r.ip_addresses.join(", ")}
        </p>
      ) : null}

      {r.open_ports.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {r.open_ports.slice(0, 12).map((p, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded-md border border-border/40 bg-surface-2/50 px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground"
            >
              <span className="text-brand-2">{p.port}</span>
              {p.service ? <span>/{p.service}</span> : null}
            </span>
          ))}
          {r.open_ports.length > 12 ? (
            <span className="px-1.5 py-0.5 text-[11px] text-muted-foreground">
              +{r.open_ports.length - 12} more
            </span>
          ) : null}
        </div>
      ) : (
        <p className="mt-3 text-xs text-muted-foreground">No open ports recorded.</p>
      )}
    </Link>
  );
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [total, setTotal] = useState(0);

  const runSearch = useCallback(async (q: string) => {
    const trimmed = q.trim();
    setSubmitted(trimmed);
    if (!trimmed) {
      setResults([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await searchAssets(trimmed);
      setResults(res.results);
      setTotal(res.total);
    } catch {
      setError("Search failed. Please try again.");
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  // Run an initial empty search so the page shows the surface on load.
  useEffect(() => {
    runSearch("");
  }, [runSearch]);

  return (
    <div className="page-container-lg">
      <PageHeader
        title="Search"
        description="Query your external attack surface like Shodan — filter by port, ASN, service, technology, certificate, and more."
        icon={<Search className="h-5 w-5" />}
        breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "Search" }]}
      />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          runSearch(query);
        }}
        className="relative"
      >
        <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          autoFocus
          placeholder='port:443 asn:AS13335 org:"Cloudflare" nginx'
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-12 pl-11 pr-24 font-mono text-sm bg-surface-2/50 border-border/60 focus:border-brand/40 focus:ring-brand/20"
        />
        <Button
          type="submit"
          size="sm"
          className="absolute right-2 top-1/2 -translate-y-1/2"
        >
          <CornerDownLeft className="mr-1 h-3.5 w-3.5" />
          Search
        </Button>
      </form>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">Try:</span>
        {FILTER_SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => {
              setQuery(s);
              runSearch(s);
            }}
            className="rounded-md border border-border/40 bg-surface-2/40 px-2 py-0.5 font-mono text-[11px] text-muted-foreground transition-colors hover:border-brand/40 hover:text-foreground"
          >
            {s}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-muted-foreground">
            <Loader2 className="mr-2 h-6 w-6 animate-spin" />
            Searching...
          </div>
        ) : error ? (
          <EmptyState
            icon={<ShieldAlert className="h-8 w-8" />}
            title="Search error"
            description={error}
          />
        ) : submitted === "" ? (
          <EmptyState
            icon={<Network className="h-8 w-8" />}
            title="Search your attack surface"
            description="Use filters to find exposed hosts — combine free text with key:value pairs (port, asn, org, service, tech, hostname, severity)."
          />
        ) : results.length === 0 ? (
          <EmptyState
            icon={<Search className="h-8 w-8" />}
            title="No matching assets"
            description={`No hosts matched "${submitted}".`}
          />
        ) : (
          <>
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                <span className="font-semibold text-foreground">{total}</span> host
                {total === 1 ? "" : "s"} matched
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {results.map((r) => (
                <ResultCard key={r.subdomain_id} r={r} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
