"use client";

import { useEffect, useState, useMemo } from "react";
import { listDNSRecords } from "@/lib/api";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import {
  Network,
  Search,
  Loader2,
  Globe,
  Server,
  Copy,
  Check,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

type DNSRecord = {
  id: string;
  subdomain_id: string;
  hostname: string;
  record_type: string;
  value: string;
  ttl: number | null;
  created_at: string;
};

type RecordTypeFilter = "all" | "A" | "AAAA" | "MX" | "NS" | "TXT" | "CNAME" | "SOA" | "SRV";

const RECORD_TYPE_COLORS: Record<string, { badge: string; dot: string; bg: string }> = {
  A:     { badge: "bg-brand/10 text-brand border-brand/30",    dot: "bg-brand",    bg: "hover:border-brand/30 hover:shadow-brand/5" },
  AAAA:  { badge: "bg-brand-2/10 text-brand-2 border-brand-2/30",   dot: "bg-brand-2",    bg: "hover:border-brand-2/30 hover:shadow-brand-2/5" },
  MX:    { badge: "bg-success/10 text-success border-success/30", dot: "bg-success", bg: "hover:border-success/30 hover:shadow-success/5" },
  NS:    { badge: "bg-warning/10 text-warning border-warning/30", dot: "bg-warning",   bg: "hover:border-warning/30 hover:shadow-warning/5" },
  TXT:   { badge: "bg-accent-2/10 text-accent-2 border-accent-2/30", dot: "bg-accent-2", bg: "hover:border-accent-2/30 hover:shadow-accent-2/5" },
  CNAME: { badge: "bg-info/10 text-info border-info/30",   dot: "bg-info",    bg: "hover:border-info/30 hover:shadow-info/5" },
  SOA:   { badge: "bg-destructive/10 text-destructive border-destructive/30",      dot: "bg-destructive",     bg: "hover:border-destructive/30 hover:shadow-destructive/5" },
  SRV:   { badge: "bg-severity-high/10 text-severity-high border-severity-high/30", dot: "bg-severity-high", bg: "hover:border-severity-high/30 hover:shadow-severity-high/5" },
};

const RECORD_TYPES: RecordTypeFilter[] = ["all", "A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "SRV"];

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
      onClick={handleCopy}
    >
      {copied ? (
        <Check className="h-3 w-3 text-success" />
      ) : (
        <Copy className="h-3 w-3" />
      )}
    </Button>
  );
}

function DNSContent() {
  const [records, setRecords] = useState<DNSRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeType, setActiveType] = useState<RecordTypeFilter>("all");

  useEffect(() => {
    const fetchRecords = async () => {
      try {
        const data = await listDNSRecords();
        setRecords(data);
      } catch {
        // silently fail
      } finally {
        setLoading(false);
      }
    };
    fetchRecords();
  }, []);

  const filteredRecords = useMemo(() => {
    const query = searchQuery.toLowerCase();
    return records.filter((r) => {
      const matchesType = activeType === "all" || r.record_type === activeType;
      const matchesSearch =
        !query ||
        r.hostname.toLowerCase().includes(query) ||
        r.value.toLowerCase().includes(query);
      return matchesType && matchesSearch;
    });
  }, [records, activeType, searchQuery]);

  const groupedByHostname = useMemo(() => {
    const groups = new Map<string, DNSRecord[]>();
    for (const record of filteredRecords) {
      const existing = groups.get(record.hostname);
      if (existing) {
        existing.push(record);
      } else {
        groups.set(record.hostname, [record]);
      }
    }
    return Array.from(groups.entries()).sort((a, b) =>
      a[0].localeCompare(b[0])
    );
  }, [filteredRecords]);

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = { all: filteredRecords.length };
    for (const r of filteredRecords) {
      counts[r.record_type] = (counts[r.record_type] || 0) + 1;
    }
    return counts;
  }, [filteredRecords]);

  const uniqueHostnames = useMemo(
    () => new Set(filteredRecords.map((r) => r.hostname)).size,
    [filteredRecords]
  );

  return (
    <div className="page-container-lg">
      <div className="py-6">
        <PageHeader
          title="DNS Records"
          description="Every DNS record we've found — A, AAAA, MX, TXT, CNAME, NS."
          icon={<Network className="h-5 w-5" />}
          breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "DNS Records" }]}
        />

        <div className="mt-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-24">
            <Loader2 className="h-8 w-8 animate-spin text-brand mb-4" />
            <p className="text-sm text-muted-foreground">
              Loading DNS records...
            </p>
          </div>
        ) : records.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="relative mb-6">
              <div className="absolute inset-0 rounded-full bg-brand/20 blur-2xl" />
              <div className="relative flex h-20 w-20 items-center justify-center rounded-xl border border-border bg-card">
                <Network className="h-10 w-10 text-muted-foreground" />
              </div>
            </div>
            <h3 className="text-xl font-semibold mb-2">
              No DNS records found
            </h3>
            <p className="text-sm text-muted-foreground max-w-sm mb-6">
              Run a scan to discover DNS records for your domains and
              subdomains.
            </p>
            <a
              href="/scan/new"
              className="inline-flex items-center gap-2 rounded-lg gradient-brand px-5 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-all"
            >
              <Globe className="h-4 w-4" />
              Start a Scan
            </a>
          </div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
              <Card className="border-border bg-card glass">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Total Records
                  </CardTitle>
                  <Network className="h-4 w-4 text-brand" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-semibold tabular-nums">
                    {records.length}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Across {new Set(records.map((r) => r.hostname)).size} hostnames
                  </p>
                </CardContent>
              </Card>

              {(["A", "AAAA", "MX", "NS"] as const).map((type) => {
                const colors = RECORD_TYPE_COLORS[type];
                const count = records.filter(
                  (r) => r.record_type === type
                ).length;
                return (
                  <Card
                    key={type}
                    className="border-border bg-card glass"
                  >
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                      <CardTitle className="text-sm font-medium text-muted-foreground">
                        {type} Records
                      </CardTitle>
                      <div
                        className={cn(
                          "h-2.5 w-2.5 rounded-full",
                          colors.dot
                        )}
                      />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-semibold tabular-nums">{count}</div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {records.length > 0
                          ? `${Math.round((count / records.length) * 100)}% of total`
                          : "—"}
                      </p>
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            <Tabs value={activeType} onValueChange={(v) => setActiveType(v as RecordTypeFilter)} className="mb-6">
              <TabsList>
                {RECORD_TYPES.map((type) => (
                  <TabsTrigger
                    key={type}
                    value={type}
                    className={cn(
                      "data-[state=active]:bg-primary data-[state=active]:text-brand-foreground px-3 py-1.5 text-xs font-medium rounded-md transition-all",
                      type !== "all" &&
                        RECORD_TYPE_COLORS[type] &&
                        `data-[state=active]:shadow-sm`
                    )}
                  >
                    {type === "all" ? "All" : type}
                    {typeCounts[type] != null && (
                      <span className="ml-1.5 text-[10px] opacity-70">
                        {typeCounts[type]}
                      </span>
                    )}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>

            <div className="mb-6 relative">
              <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by hostname or value..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-11 pl-11 bg-muted/30 border-border focus:border-brand/50 focus:ring-brand/20"
              />
            </div>

            <div className="flex items-center gap-3 mb-4 text-sm text-muted-foreground">
              <Server className="h-4 w-4" />
              <span>
                {filteredRecords.length} record{filteredRecords.length !== 1 ? "s" : ""}{" "}
                across {uniqueHostnames} hostname{uniqueHostnames !== 1 ? "s" : ""}
              </span>
            </div>

            <AnimatePresence mode="wait">
              {filteredRecords.length === 0 ? (
                <motion.div
                  key="empty"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex flex-col items-center justify-center py-16 text-center"
                >
                  <Search className="h-10 w-10 text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground">
                    No records match your search.
                  </p>
                </motion.div>
              ) : (
                <motion.div
                  key="table"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  {groupedByHostname.map(([hostname, hostRecords]) => (
                    <div key={hostname} className="mb-6">
                      <div className="flex items-center gap-2 mb-3">
                        <Globe className="h-4 w-4 text-brand" />
                        <h3 className="text-sm font-semibold font-mono text-foreground">
                          {hostname}
                        </h3>
                        <span className="rounded-md bg-brand/10 px-1.5 py-0.5 text-[10px] font-semibold text-brand">
                          {hostRecords.length}
                        </span>
                      </div>

                      <div className="rounded-xl border border-border bg-card overflow-hidden">
                        <div className="overflow-x-auto">
                          <Table>
                            <TableHeader>
                              <TableRow className="border-border hover:bg-transparent">
                                <TableHead className="text-xs font-semibold text-muted-foreground w-[140px]">
                                  Type
                                </TableHead>
                                <TableHead className="text-xs font-semibold text-muted-foreground">
                                  Value
                                </TableHead>
                                <TableHead className="text-xs font-semibold text-muted-foreground w-[100px]">
                                  TTL
                                </TableHead>
                                <TableHead className="text-xs font-semibold text-muted-foreground w-[50px]">
                                  <span className="sr-only">Copy</span>
                                </TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {hostRecords.map((record) => {
                                const colors =
                                  RECORD_TYPE_COLORS[record.record_type] ||
                                  RECORD_TYPE_COLORS.A;
                                return (
                                  <TableRow
                                    key={record.id}
                                    className="border-border last:border-0 hover:bg-muted/20 transition-colors"
                                  >
                                    <TableCell>
                                      <Badge
                                        variant="outline"
                                        className={cn(
                                          "text-[11px] font-semibold border",
                                          colors.badge
                                        )}
                                      >
                                        {record.record_type}
                                      </Badge>
                                    </TableCell>
                                    <TableCell>
                                      <span className="text-sm font-mono text-foreground break-all">
                                        {record.value}
                                      </span>
                                    </TableCell>
                                    <TableCell>
                                      <span className="text-xs text-muted-foreground font-mono">
                                        {record.ttl != null
                                          ? `${record.ttl}s`
                                          : "—"}
                                      </span>
                                    </TableCell>
                                    <TableCell>
                                      <CopyButton text={record.value} />
                                    </TableCell>
                                  </TableRow>
                                );
                              })}
                            </TableBody>
                          </Table>
                        </div>
                      </div>
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </>
        )}
      </div>
      </div>
    </div>
  );
}

export default function DNSPage() {
  return (
    <ProtectedRoute>
      <DNSContent />
    </ProtectedRoute>
  );
}
