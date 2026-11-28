"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Layers,
  Loader2,
  RefreshCw,
  Download,
  Search,
  Server,
  Plug,
  Lock,
  Sparkles,
  EyeOff,
  ChevronLeft,
  ChevronRight,
  History,
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  downloadInventoryCsv,
  getInventorySummary,
  listInventoryAssets,
  listInventoryChanges,
  rebuildInventory,
  type AssetType,
  type InventoryAsset,
  type InventoryChange,
  type InventorySummary,
} from "@/lib/api-inventory";
import {
  ChangeRow,
  StateBadge,
  TYPE_META,
  TYPE_ORDER,
  assetDetails,
  assetTitle,
  formatDate,
  relativeTime,
} from "@/components/inventory/shared";
import { AssetDrawer } from "@/components/inventory/AssetDrawer";
import { AlertSettingsPanel } from "@/components/inventory/AlertSettingsPanel";

type Tab = "assets" | "changes" | "alerts";
type StateFilter = "active" | "missing" | "all";
const PAGE = 50;

const CHANGE_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "All changes" },
  { key: "new_asset", label: "New assets" },
  { key: "new_service", label: "New open ports" },
  { key: "new_critical_finding", label: "New findings" },
  { key: "certificate_expiring", label: "Certificates expiring" },
  { key: "certificate_changed", label: "Certificates changed" },
  { key: "asset_disappeared", label: "Disappeared" },
];

const selectCls =
  "h-9 rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

function Chip({
  active,
  onClick,
  children,
  count,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "border-primary/60 bg-primary/10 text-foreground"
          : "border-border bg-card text-muted-foreground hover:text-foreground"
      )}
    >
      {children}
      {count !== undefined && <span className="tabular-nums text-xs opacity-70">{count.toLocaleString()}</span>}
    </button>
  );
}

function Pager({
  skip,
  total,
  onChange,
}: {
  skip: number;
  total: number;
  onChange: (skip: number) => void;
}) {
  if (total <= PAGE) return null;
  return (
    <div className="flex items-center justify-between border-t border-border px-4 py-2.5 text-xs text-muted-foreground">
      <span className="tabular-nums">
        {skip + 1}–{Math.min(skip + PAGE, total)} of {total.toLocaleString()}
      </span>
      <div className="flex gap-1">
        <Button variant="outline" size="sm" disabled={skip === 0} onClick={() => onChange(Math.max(0, skip - PAGE))}>
          <ChevronLeft /> Previous
        </Button>
        <Button variant="outline" size="sm" disabled={skip + PAGE >= total} onClick={() => onChange(skip + PAGE)}>
          Next <ChevronRight />
        </Button>
      </div>
    </div>
  );
}

function InventoryContent() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const tab = (["assets", "changes", "alerts"].includes(params.get("tab") || "") ? params.get("tab") : "assets") as Tab;
  const changeFilter = params.get("alert") || "";
  const openAssetId = params.get("asset");

  const setParams = useCallback(
    (next: Record<string, string | null>) => {
      const sp = new URLSearchParams(params.toString());
      Object.entries(next).forEach(([k, v]) => (v ? sp.set(k, v) : sp.delete(k)));
      const qs = sp.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, pathname, router]
  );

  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);

  // Assets tab
  const [type, setType] = useState<AssetType | "">("host");
  const [state, setState] = useState<StateFilter>("active");
  const [root, setRoot] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [newOnly, setNewOnly] = useState(false);
  const [skip, setSkip] = useState(0);
  const [assets, setAssets] = useState<InventoryAsset[] | null>(null);
  const [total, setTotal] = useState(0);

  // Changes tab
  const [changes, setChanges] = useState<InventoryChange[] | null>(null);
  const [changeTotal, setChangeTotal] = useState(0);
  const [changeSkip, setChangeSkip] = useState(0);

  const assetQuery = useMemo(
    () => ({
      type: type || undefined,
      state,
      root: root || undefined,
      q: query || undefined,
      new_days: newOnly ? 7 : undefined,
    }),
    [type, state, root, query, newOnly]
  );

  // Debounce the search box.
  useEffect(() => {
    const t = setTimeout(() => {
      setQuery(search.trim());
      setSkip(0);
    }, 250);
    return () => clearTimeout(t);
  }, [search]);

  const loadSummary = useCallback(async () => {
    try {
      setSummary(await getInventorySummary());
    } catch {
      setError("The inventory could not be loaded. Check your connection and try again.");
    }
  }, []);

  const requestId = useRef(0);
  const loadAssets = useCallback(async () => {
    const id = ++requestId.current;
    try {
      const page = await listInventoryAssets({ ...assetQuery, skip, limit: PAGE });
      if (id !== requestId.current) return;
      setAssets(page.items);
      setTotal(page.total);
      setError("");
    } catch {
      if (id === requestId.current) setError("The asset list could not be loaded. Try again.");
    }
  }, [assetQuery, skip]);

  const loadChanges = useCallback(async () => {
    try {
      const page = await listInventoryChanges({
        alert: changeFilter || undefined,
        skip: changeSkip,
        limit: PAGE,
      });
      setChanges(page.items);
      setChangeTotal(page.total);
      setError("");
    } catch {
      setError("The change history could not be loaded. Try again.");
    }
  }, [changeFilter, changeSkip]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);
  useEffect(() => {
    if (tab === "assets") loadAssets();
  }, [tab, loadAssets]);
  useEffect(() => {
    if (tab === "changes") loadChanges();
  }, [tab, loadChanges]);

  const refresh = async () => {
    setRefreshing(true);
    await Promise.all([loadSummary(), tab === "changes" ? loadChanges() : loadAssets()]);
    setRefreshing(false);
  };

  const rebuild = async () => {
    setRebuilding(true);
    setError("");
    try {
      await rebuildInventory();
      await Promise.all([loadSummary(), loadAssets()]);
    } catch (e: any) {
      setError(
        e?.response?.status === 403
          ? "Only owners and admins can build the inventory from past scans."
          : "The inventory could not be built from past scans. Try again."
      );
    } finally {
      setRebuilding(false);
    }
  };

  const pick = (next: { type?: AssetType | ""; state?: StateFilter; newOnly?: boolean }) => {
    if (next.type !== undefined) setType(next.type);
    if (next.state !== undefined) setState(next.state);
    setNewOnly(next.newOnly ?? false);
    setSkip(0);
    setAssets(null);
    setParams({ tab: null });
  };

  const openAsset = useCallback((id: string) => setParams({ asset: id }), [setParams]);
  const closeAsset = useCallback(() => setParams({ asset: null }), [setParams]);

  const counts = summary?.by_type;
  const countFor = (t: AssetType) =>
    !counts ? undefined : state === "missing" ? counts[t].missing : state === "all" ? counts[t].active + counts[t].missing : counts[t].active;
  const plan = summary?.plan;
  const empty = summary !== null && summary.total_active + summary.total_missing === 0;

  return (
    <div className="page-container-md pb-12">
      <PageHeader
        title="Asset inventory"
        description="Every domain, host, service, certificate and technology your scans have found, listed once, with what changed and when."
        icon={<Layers />}
        breadcrumbs={[{ label: "Attack surface" }, { label: "Asset inventory" }]}
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              disabled={empty || tab !== "assets"}
              onClick={() => downloadInventoryCsv(assetQuery).catch(() => setError("The CSV could not be downloaded."))}
            >
              <Download /> Export CSV
            </Button>
            <Button variant="outline" size="sm" onClick={refresh} disabled={refreshing}>
              <RefreshCw className={refreshing ? "animate-spin" : ""} /> Refresh
            </Button>
          </>
        }
      />

      {error && (
        <div role="alert" className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {plan?.at_limit && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm">
          <span>
            Your {plan.name} plan covers {plan.hosts_limit?.toLocaleString()} hosts and all of them are in use. Newly
            discovered hosts are not added until you upgrade.
          </span>
          <Button asChild size="sm">
            <Link href="/billing">See plans</Link>
          </Button>
        </div>
      )}

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard
          label="Hosts"
          value={counts ? counts.host.active.toLocaleString() : "—"}
          icon={<Server className="h-5 w-5" />}
          hint={
            plan?.hosts_limit != null
              ? `of ${plan.hosts_limit.toLocaleString()} on ${plan.name}`
              : summary
                ? `${summary.root_domains.length} root domain${summary.root_domains.length === 1 ? "" : "s"}`
                : undefined
          }
          onClick={() => pick({ type: "host", state: "active" })}
        />
        <StatCard
          label="Open services"
          value={counts ? counts.service.active.toLocaleString() : "—"}
          icon={<Plug className="h-5 w-5" />}
          accent="info"
          hint="ports reachable now"
          onClick={() => pick({ type: "service", state: "active" })}
        />
        <StatCard
          label="Certificates"
          value={counts ? counts.certificate.active.toLocaleString() : "—"}
          icon={<Lock className="h-5 w-5" />}
          accent={summary?.certificates_expiring ? "warning" : "success"}
          hint={
            summary
              ? summary.certificates_expiring
                ? `${summary.certificates_expiring} expiring within ${summary.cert_expiry_days} days`
                : `none expiring within ${summary.cert_expiry_days} days`
              : undefined
          }
          onClick={() => pick({ type: "certificate", state: "active" })}
        />
        <StatCard
          label="New this week"
          value={summary ? summary.new_last_7_days.toLocaleString() : "—"}
          icon={<Sparkles className="h-5 w-5" />}
          accent="violet"
          hint="first seen in the last 7 days"
          onClick={() => pick({ type: "", state: "active", newOnly: true })}
        />
        <StatCard
          label="Missing"
          value={summary ? summary.total_missing.toLocaleString() : "—"}
          icon={<EyeOff className="h-5 w-5" />}
          accent="danger"
          hint={summary ? `not seen in ${summary.missing_after_scans} scans in a row` : undefined}
          onClick={() => pick({ type: "", state: "missing" })}
        />
      </div>

      <div role="tablist" aria-label="Inventory views" className="mb-4 flex gap-1 border-b border-border">
        {(
          [
            ["assets", "Assets"],
            ["changes", "Changes"],
            ["alerts", "Alert settings"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            role="tab"
            type="button"
            aria-selected={tab === key}
            onClick={() => setParams({ tab: key === "assets" ? null : key, alert: null })}
            className={cn(
              "-mb-px border-b-2 px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              tab === key ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {label}
            {key === "changes" && summary && summary.changes_last_7_days > 0 && (
              <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-[11px] tabular-nums text-muted-foreground">
                {summary.changes_last_7_days}
              </span>
            )}
          </button>
        ))}
      </div>

      {tab === "assets" &&
        (empty ? (
          <EmptyState
            icon={<Layers className="h-5 w-5" />}
            title={summary?.needs_rebuild ? "Your earlier scans are not in the inventory yet" : "No assets yet"}
            description={
              summary?.needs_rebuild
                ? "Build the inventory from the scans you have already run. No alerts are sent for this."
                : "Run a scan and everything it finds is listed here once, then kept up to date by later scans."
            }
            action={
              summary?.needs_rebuild ? (
                <Button onClick={rebuild} disabled={rebuilding}>
                  {rebuilding && <Loader2 className="animate-spin" />} Build from past scans
                </Button>
              ) : (
                <Button asChild>
                  <Link href="/scan/new">Start a scan</Link>
                </Button>
              )
            }
          />
        ) : (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Chip active={type === ""} onClick={() => pick({ type: "", newOnly })}>
                All
              </Chip>
              {TYPE_ORDER.map((t) => (
                <Chip key={t} active={type === t} onClick={() => pick({ type: t, newOnly })} count={newOnly ? undefined : countFor(t)}>
                  {TYPE_META[t].plural}
                </Chip>
              ))}
            </div>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <div className="relative min-w-[220px] flex-1 sm:max-w-sm">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by name, IP or port"
                  aria-label="Search assets"
                  className="h-9 pl-9"
                />
              </div>
              <select
                aria-label="Status"
                className={selectCls}
                value={state}
                onChange={(e) => {
                  setState(e.target.value as StateFilter);
                  setSkip(0);
                }}
              >
                <option value="active">Active</option>
                <option value="missing">Missing</option>
                <option value="all">Active and missing</option>
              </select>
              {summary && summary.root_domains.length > 1 && (
                <select
                  aria-label="Root domain"
                  className={selectCls}
                  value={root}
                  onChange={(e) => {
                    setRoot(e.target.value);
                    setSkip(0);
                  }}
                >
                  <option value="">All root domains</option>
                  {summary.root_domains.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              )}
              {newOnly && (
                <Chip active onClick={() => pick({ newOnly: false })}>
                  First seen in the last 7 days ✕
                </Chip>
              )}
            </div>

            <div className="overflow-hidden rounded-xl border border-border bg-card">
              {assets === null ? (
                <div className="flex items-center justify-center py-24 text-muted-foreground">
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading assets…
                </div>
              ) : assets.length === 0 ? (
                <div className="px-6 py-16 text-center">
                  <p className="text-sm font-medium">Nothing matches these filters</p>
                  <p className="mt-1 text-[13px] text-muted-foreground">
                    Try a different type or status, or clear the search.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[760px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-border text-xs text-muted-foreground">
                        <th className="px-4 py-2.5 font-medium">Asset</th>
                        <th className="px-4 py-2.5 font-medium">Details</th>
                        <th className="px-4 py-2.5 font-medium">First seen</th>
                        <th className="px-4 py-2.5 font-medium">Last seen</th>
                        <th className="px-4 py-2.5 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {assets.map((a) => {
                        const Icon = TYPE_META[a.type].icon;
                        return (
                          <tr
                            key={a.id}
                            tabIndex={0}
                            onClick={() => openAsset(a.id)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                openAsset(a.id);
                              }
                            }}
                            className="cursor-pointer transition-colors hover:bg-muted/40 focus-visible:bg-muted/40 focus-visible:outline-none"
                          >
                            <td className="max-w-[380px] px-4 py-2.5">
                              <div className="flex items-center gap-2.5">
                                <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                                <div className="min-w-0">
                                  <p className="truncate font-mono text-[13px]">{assetTitle(a)}</p>
                                  {type === "" && (
                                    <p className="text-xs text-muted-foreground">{TYPE_META[a.type].label}</p>
                                  )}
                                </div>
                              </div>
                            </td>
                            <td className="max-w-[320px] truncate px-4 py-2.5 text-[13px] text-muted-foreground">
                              {assetDetails(a)}
                            </td>
                            <td className="whitespace-nowrap px-4 py-2.5 text-[13px] tabular-nums text-muted-foreground">
                              {formatDate(a.first_seen)}
                            </td>
                            <td className="whitespace-nowrap px-4 py-2.5 text-[13px] tabular-nums text-muted-foreground">
                              {relativeTime(a.last_seen)}
                            </td>
                            <td className="px-4 py-2.5">
                              <StateBadge asset={a} />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <Pager skip={skip} total={total} onChange={setSkip} />
            </div>
          </>
        ))}

      {tab === "changes" && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            {CHANGE_FILTERS.map((f) => (
              <Chip
                key={f.key}
                active={changeFilter === f.key}
                onClick={() => {
                  setChangeSkip(0);
                  setChanges(null);
                  setParams({ alert: f.key || null });
                }}
              >
                {f.label}
              </Chip>
            ))}
          </div>
          <div className="overflow-hidden rounded-xl border border-border bg-card">
            {changes === null ? (
              <div className="flex items-center justify-center py-24 text-muted-foreground">
                <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading changes…
              </div>
            ) : changes.length === 0 ? (
              <div className="px-6 py-16 text-center">
                <History className="mx-auto mb-3 h-5 w-5 text-muted-foreground" />
                <p className="text-sm font-medium">{changeFilter ? "No changes of this kind yet" : "No changes yet"}</p>
                <p className="mt-1 text-[13px] text-muted-foreground">
                  Changes are recorded each time a scan finishes.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {changes.map((c) => (
                  <ChangeRow key={c.id} change={c} onOpenAsset={openAsset} />
                ))}
              </div>
            )}
            <Pager skip={changeSkip} total={changeTotal} onChange={setChangeSkip} />
          </div>
        </>
      )}

      {tab === "alerts" && <AlertSettingsPanel />}

      <AssetDrawer assetId={openAssetId} onClose={closeAsset} onNavigate={openAsset} />
    </div>
  );
}

export default function InventoryPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={null}>
        <InventoryContent />
      </Suspense>
    </ProtectedRoute>
  );
}
