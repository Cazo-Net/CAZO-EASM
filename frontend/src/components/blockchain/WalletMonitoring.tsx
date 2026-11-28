"use client";

/**
 * Watched wallets and the alerts the monitoring engine raised for them.
 *
 * Everything here belongs to the signed-in user's organization only. Alerts
 * come from live chain data and the OFAC SDN list; nothing is simulated.
 */
import { useCallback, useEffect, useState } from "react";
import {
  Bell,
  CheckCircle,
  ExternalLink,
  Eye,
  Loader2,
  Plus,
  RefreshCw,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { authFetch } from "@/lib/api";
import { CHAIN_META } from "@/lib/blockchainStore";
import { SectionCard } from "@/components/common/SectionCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export const WATCHES_CHANGED = "cazo:blockchain-watches-changed";

const BASE = "/api/v1/blockchain";

interface Watch {
  id: string;
  chain: string;
  address: string;
  label: string | null;
  alert_on_new_tx: boolean;
  alert_on_sanctions: boolean;
  is_active: boolean;
  last_checked_at: string | null;
  last_activity_at: string | null;
  last_status: { result?: string; message?: string; setting?: string; new_transactions?: number };
  open_alerts: number;
  explorer_url: string | null;
}

interface Alert {
  id: string;
  chain: string;
  address: string;
  alert_type: string;
  severity: string;
  title: string;
  message: string | null;
  tx_hash: string | null;
  counterparty: string | null;
  source: string | null;
  reference_url: string | null;
  acknowledged: boolean;
  created_at: string | null;
}

const SEVERITY_STYLE: Record<string, string> = {
  critical: "text-destructive border-red-500/30 bg-destructive/10",
  high: "text-orange-400 border-orange-500/30 bg-orange-500/10",
  medium: "text-yellow-400 border-yellow-500/30 bg-yellow-500/10",
  info: "text-muted-foreground border-border bg-muted/40",
};

function short(addr: string) {
  return addr.length > 18 ? `${addr.slice(0, 10)}…${addr.slice(-6)}` : addr;
}

function when(iso: string | null) {
  if (!iso) return "never";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export async function addWatch(address: string, chain: string, label?: string): Promise<string | null> {
  const res = await authFetch(`${BASE}/watches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address, chain, label: label || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const d = err.detail;
    return typeof d === "string" ? d : Array.isArray(d) ? d[0]?.msg || "Invalid input" : "Could not add the watch.";
  }
  if (typeof window !== "undefined") window.dispatchEvent(new Event(WATCHES_CHANGED));
  return null;
}

function StatusLine({ w }: { w: Watch }) {
  const s = w.last_status || {};
  if (!w.last_checked_at) return <span className="text-muted-foreground">Not checked yet</span>;
  if (s.result === "not_configured") {
    return (
      <span className="text-yellow-400">
        Live data not connected{s.setting ? ` (needs ${s.setting})` : ""}
      </span>
    );
  }
  if (s.result === "upstream_error") return <span className="text-yellow-400">Data source did not answer; will retry</span>;
  return <span className="text-muted-foreground">Checked {when(w.last_checked_at)}</span>;
}

export function WalletMonitoring({ defaultChain = "ethereum" }: { defaultChain?: string }) {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [limit, setLimit] = useState<number | null>(null);
  const [every, setEvery] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [address, setAddress] = useState("");
  const [chain, setChain] = useState(defaultChain);
  const [label, setLabel] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [showAcked, setShowAcked] = useState(false);

  const load = useCallback(async () => {
    try {
      const [wRes, aRes] = await Promise.all([
        authFetch(`${BASE}/watches`),
        authFetch(`${BASE}/alerts?limit=100`),
      ]);
      if (wRes.ok) {
        const d = await wRes.json();
        setWatches(d.watches || []);
        setLimit(d.limit ?? null);
        setEvery(d.check_every_minutes ?? null);
      }
      if (aRes.ok) setAlerts((await aRes.json()).alerts || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const h = () => load();
    window.addEventListener(WATCHES_CHANGED, h);
    return () => window.removeEventListener(WATCHES_CHANGED, h);
  }, [load]);

  const onAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!address.trim()) return;
    setAdding(true);
    setError("");
    const err = await addWatch(address.trim(), chain, label.trim());
    setAdding(false);
    if (err) {
      setError(err);
      return;
    }
    setAddress("");
    setLabel("");
  };

  const checkNow = async (id: string) => {
    setBusy(id);
    await authFetch(`${BASE}/watches/${id}/check`, { method: "POST" });
    setBusy(null);
    load();
  };

  const remove = async (id: string) => {
    setBusy(id);
    await authFetch(`${BASE}/watches/${id}`, { method: "DELETE" });
    setBusy(null);
    load();
  };

  const ack = async (id: string) => {
    await authFetch(`${BASE}/alerts/${id}/acknowledge`, { method: "POST" });
    setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, acknowledged: true } : a)));
    load();
  };

  const visibleAlerts = alerts.filter((a) => showAcked || !a.acknowledged);
  const openCount = alerts.filter((a) => !a.acknowledged).length;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mt-6">
      <SectionCard
        className="lg:col-span-3"
        title="Watched wallets"
        description={
          every
            ? `Checked against live chain data and the OFAC sanctions list every ${every >= 60 ? `${Math.round(every / 60)}h` : `${every} min`}.`
            : undefined
        }
        icon={<Eye className="h-4 w-4" />}
      >
        <form onSubmit={onAdd} className="flex flex-col sm:flex-row gap-2">
          <Input
            placeholder="Wallet or contract address"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className="font-mono text-sm flex-1"
            aria-label="Address to watch"
          />
          <Input
            placeholder="Label (e.g. Treasury)"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className="text-sm sm:w-40"
            aria-label="Label"
          />
          <select
            value={chain}
            onChange={(e) => setChain(e.target.value)}
            className="border border-border rounded-md bg-background px-3 text-sm h-10"
            aria-label="Chain"
          >
            {Object.entries(CHAIN_META).map(([v, m]) => (
              <option key={v} value={v}>
                {m.label}
              </option>
            ))}
          </select>
          <Button type="submit" disabled={adding || !address.trim()}>
            {adding ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
            Watch
          </Button>
        </form>
        {error && <p className="mt-2 text-xs text-destructive">{error}</p>}

        <div className="mt-4 divide-y divide-border">
          {loading ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin inline mr-2" />
              Loading…
            </div>
          ) : watches.length === 0 ? (
            <p className="py-6 text-sm text-muted-foreground text-center">
              No wallets watched yet. Add your organization&apos;s treasury, hot wallets or deployed contracts to be
              alerted on new activity and sanctioned counterparties.
            </p>
          ) : (
            watches.map((w) => (
              <div key={w.id} className="py-3 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium">{w.label || short(w.address)}</span>
                    <Badge variant="outline" className="text-[10px] capitalize">
                      {CHAIN_META[w.chain]?.label || w.chain}
                    </Badge>
                    {w.open_alerts > 0 && (
                      <Badge variant="outline" className="text-[10px] text-destructive border-red-500/30">
                        {w.open_alerts} open alert{w.open_alerts === 1 ? "" : "s"}
                      </Badge>
                    )}
                  </div>
                  <code className="text-xs text-muted-foreground font-mono break-all">{w.address}</code>
                  <div className="text-xs mt-1">
                    <StatusLine w={w} />
                    {w.last_activity_at && (
                      <span className="text-muted-foreground"> · last on-chain activity {when(w.last_activity_at)}</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {w.explorer_url && (
                    <a
                      href={w.explorer_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 text-muted-foreground hover:text-foreground"
                      title="Open in block explorer"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => checkNow(w.id)} disabled={busy === w.id} title="Check now">
                    {busy === w.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => remove(w.id)} disabled={busy === w.id} title="Stop watching">
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
        {limit != null && watches.length > 0 && (
          <p className="mt-2 text-[11px] text-muted-foreground">
            {watches.length} of {limit} watches used.
          </p>
        )}
      </SectionCard>

      <SectionCard
        className="lg:col-span-2"
        title={`Alerts${openCount ? ` (${openCount} open)` : ""}`}
        icon={<Bell className="h-4 w-4" />}
        actions={
          <button
            onClick={() => setShowAcked((v) => !v)}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            {showAcked ? "Hide acknowledged" : "Show acknowledged"}
          </button>
        }
      >
        {visibleAlerts.length === 0 ? (
          <p className="py-6 text-sm text-muted-foreground text-center">
            {alerts.length === 0 ? "No alerts yet." : "No open alerts."}
          </p>
        ) : (
          <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
            {visibleAlerts.map((a) => (
              <div key={a.id} className={`rounded-md border p-3 text-xs ${SEVERITY_STYLE[a.severity] || SEVERITY_STYLE.info}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2 min-w-0">
                    {a.alert_type === "new_transaction" ? (
                      <Bell className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    ) : (
                      <ShieldAlert className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    )}
                    <div className="min-w-0">
                      <div className="font-medium text-foreground">{a.title}</div>
                      {a.message && <div className="mt-1 text-muted-foreground break-words">{a.message}</div>}
                      <div className="mt-1 text-muted-foreground">
                        {a.source ? `Source: ${a.source}` : null}
                        {a.created_at ? ` · ${when(a.created_at)}` : null}
                      </div>
                      {a.reference_url && (
                        <a
                          href={a.reference_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 mt-1 underline underline-offset-2"
                        >
                          View evidence <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>
                  {a.acknowledged ? (
                    <CheckCircle className="w-4 h-4 text-success shrink-0" />
                  ) : (
                    <button
                      onClick={() => ack(a.id)}
                      className="text-[11px] border border-border rounded px-2 py-0.5 text-muted-foreground hover:text-foreground shrink-0"
                    >
                      Acknowledge
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
