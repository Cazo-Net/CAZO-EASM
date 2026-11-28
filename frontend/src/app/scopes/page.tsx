"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import {
  ShieldCheck,
  Plus,
  Trash2,
  Search,
  Globe,
  Asterisk,
  Network,
  CheckCircle2,
  XCircle,
  Loader2,
  Info,
  ExternalLink,
  Copy,
  BadgeCheck,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useChecklistAutoComplete } from "@/components/onboarding/GettingStartedChecklist";
import {
  listScopes,
  createScope,
  deleteScope,
  checkScope,
  verifyScope,
  getErrorMessage,
} from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { cn } from "@/lib/utils";
import type { AuthorizedScope, ScopeType, ScopeCheckResult } from "@/types";

const SCOPE_TYPE_META: Record<
  ScopeType,
  { label: string; icon: React.ComponentType<{ className?: string }>; hint: string }
> = {
  domain: { label: "Domain", icon: Globe, hint: "example.com" },
  wildcard: { label: "Wildcard", icon: Asterisk, hint: "*.example.com" },
  ip: { label: "IP", icon: Network, hint: "1.2.3.4" },
  cidr: { label: "CIDR", icon: Network, hint: "10.0.0.0/24" },
};

function ScopeIcon({ type, className }: { type: ScopeType; className?: string }) {
  const Icon = SCOPE_TYPE_META[type]?.icon ?? Globe;
  return <Icon className={className} />;
}

function ScopesContent() {
  const { markComplete } = useChecklistAutoComplete();
  const [scopes, setScopes] = useState<AuthorizedScope[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [newType, setNewType] = useState<ScopeType>("domain");
  const [newValue, setNewValue] = useState("");
  const [newNote, setNewNote] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [scopeAuthConfirmed, setScopeAuthConfirmed] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const [openVerifyId, setOpenVerifyId] = useState<string | null>(null);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const [checkValue, setCheckValue] = useState("");
  const [checkResult, setCheckResult] = useState<ScopeCheckResult | null>(null);
  const [checking, setChecking] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listScopes();
      setScopes(data);
    } catch (e: any) {
      setError(getErrorMessage(e, "Failed to load authorized scopes."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return scopes;
    return scopes.filter(
      (s) =>
        s.value.toLowerCase().includes(q) ||
        s.scope_type.toLowerCase().includes(q) ||
        (s.note || "").toLowerCase().includes(q)
    );
  }, [scopes, search]);

  const handleCreate = async () => {
    setCreateError(null);
    if (!newValue.trim()) {
      setCreateError("A scope value is required.");
      return;
    }
    setCreating(true);
    try {
      await createScope(newType, newValue.trim(), newNote.trim() || undefined);
      setCreateOpen(false);
      markComplete("add_scope");
      setNewValue("");
      setNewNote("");
      setNewType("domain");
      setScopeAuthConfirmed(false);
      await load();
    } catch (e: any) {
      setCreateError(getErrorMessage(e, "Failed to add authorized scope."));
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await deleteScope(id);
      setScopes((prev) => prev.filter((s) => s.id !== id));
    } catch (e: any) {
      setError(getErrorMessage(e, "Failed to remove scope."));
    } finally {
      setDeletingId(null);
    }
  };

  const handleVerify = async (id: string) => {
    setVerifyingId(id);
    setVerifyError(null);
    try {
      const updated = await verifyScope(id);
      setScopes((prev) => prev.map((s) => (s.id === id ? updated : s)));
      setOpenVerifyId(null);
    } catch (e: any) {
      setVerifyError(getErrorMessage(e, "Verification failed."));
    } finally {
      setVerifyingId(null);
    }
  };

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(text);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  const handleCheck = async () => {
    if (!checkValue.trim()) return;
    setChecking(true);
    setCheckResult(null);
    try {
      const result = await checkScope(checkValue.trim());
      setCheckResult(result);
    } catch (e: any) {
      setError(getErrorMessage(e, "Scope check failed."));
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="page-container-lg">
      <div className="space-y-6">
      <PageHeader
        title="Authorized Scopes"
        description="Register the domains, hosts, and networks you are authorized to assess. Discovery is gated by these entries."
        icon={<ShieldCheck className="h-5 w-5" />}
        breadcrumbs={[{ label: "Discovery" }, { label: "Authorized Scopes" }]}
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" /> Add Scope
          </Button>
        }
      />

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="md:col-span-2 bg-card">
          <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
            <CardTitle className="text-base">Registered Scopes</CardTitle>
            <div className="relative w-56">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter scopes…"
                className="pl-9"
              />
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-12 text-muted-foreground">
                <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading…
              </div>
            ) : error ? (
              <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                <XCircle className="h-4 w-4 shrink-0" /> {error}
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 py-12 text-center text-muted-foreground">
                <ShieldCheck className="h-8 w-8 opacity-40" />
                <p className="text-sm">
                  {scopes.length === 0
                    ? "No scopes yet. Add a domain or IP to start discovering assets."
                    : "No scopes match your filter."}
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-border/50">
                <AnimatePresence initial={false}>
                  {filtered.map((s) => (
                    <motion.li
                      key={s.id}
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="py-3"
                    >
                      <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2 text-brand">
                        <ScopeIcon type={s.scope_type} className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate font-medium font-mono">{s.value}</span>
                          <Badge variant="outline" className="shrink-0 text-[10px] uppercase">
                            {s.scope_type}
                          </Badge>
                          {s.verified ? (
                            <Badge className="shrink-0 bg-success/10 text-success border-success/30 text-[10px]">
                              verified
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="shrink-0 text-[10px]">
                              unverified
                            </Badge>
                          )}
                        </div>
                        {s.note && (
                          <p className="truncate text-xs text-muted-foreground">{s.note}</p>
                        )}
                      </div>
                      {!s.verified && s.verification?.method === "dns_txt" && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="shrink-0"
                          onClick={() => {
                            setVerifyError(null);
                            setOpenVerifyId(openVerifyId === s.id ? null : s.id);
                          }}
                        >
                          <BadgeCheck className="mr-1.5 h-3.5 w-3.5" /> Verify
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-muted-foreground hover:text-destructive"
                        disabled={deletingId === s.id}
                        onClick={() => handleDelete(s.id)}
                      >
                        {deletingId === s.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                      </div>
                      {openVerifyId === s.id && s.verification?.method === "dns_txt" && (
                        <div className="mt-3 ml-12 space-y-2 rounded-lg border border-border bg-muted/30 p-3 text-xs">
                          <p className="text-muted-foreground">
                            Prove you control this domain: add this DNS record at your DNS
                            provider, then press Check now. Changes can take a few minutes to appear.
                          </p>
                          {[
                            ["Type", s.verification.record_type || "TXT"],
                            ["Name", s.verification.record_name || ""],
                            ["Value", s.verification.record_value || ""],
                          ].map(([label, value]) => (
                            <div key={label} className="flex items-center gap-2">
                              <span className="w-12 shrink-0 text-muted-foreground">{label}</span>
                              <code className="min-w-0 flex-1 truncate rounded bg-background/60 px-2 py-1 font-mono">
                                {value}
                              </code>
                              {label !== "Type" && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7 shrink-0"
                                  onClick={() => copy(value)}
                                  aria-label={`Copy ${label.toLowerCase()}`}
                                >
                                  {copied === value ? (
                                    <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                                  ) : (
                                    <Copy className="h-3.5 w-3.5" />
                                  )}
                                </Button>
                              )}
                            </div>
                          ))}
                          {verifyError && (
                            <p className="flex items-start gap-1.5 text-destructive">
                              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {verifyError}
                            </p>
                          )}
                          <Button
                            size="sm"
                            onClick={() => handleVerify(s.id)}
                            disabled={verifyingId === s.id}
                          >
                            {verifyingId === s.id ? (
                              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <BadgeCheck className="mr-1.5 h-3.5 w-3.5" />
                            )}
                            Check now
                          </Button>
                        </div>
                      )}
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className=" bg-card">
          <CardHeader>
            <CardTitle className="text-base">Authorization Check</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Verify whether a target falls within your registered scopes before
              launching a scan.
            </p>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={checkValue}
                onChange={(e) => setCheckValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCheck()}
                placeholder="example.com"
                className="pl-9"
              />
            </div>
            <Button
              variant="secondary"
              className="w-full"
              onClick={handleCheck}
              disabled={checking || !checkValue.trim()}
            >
              {checking ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 className="mr-2 h-4 w-4" />
              )}
              Check Authorization
            </Button>
            {checkResult && (
              <div
                className={cn(
                  "rounded-lg border px-3 py-2.5 text-sm",
                  checkResult.authorized
                    ? "border-success/30 bg-success/10 text-success"
                    : "border-destructive/30 bg-destructive/10 text-destructive"
                )}
              >
                <div className="flex items-center gap-2 font-medium">
                  {checkResult.authorized ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <XCircle className="h-4 w-4" />
                  )}
                  {checkResult.authorized ? "Authorized" : "Not authorized"}
                </div>
                {checkResult.reason && (
                  <p className="mt-1 text-xs opacity-80">{checkResult.reason}</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Authorized Scope</DialogTitle>
            <DialogDescription>
              Targets outside your scopes are blocked from scanning. Domains must
              be verified with a DNS TXT record before they can be scanned.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              {(Object.keys(SCOPE_TYPE_META) as ScopeType[]).map((t) => {
                const meta = SCOPE_TYPE_META[t];
                const Icon = meta.icon;
                const active = newType === t;
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setNewType(t)}
                    className={cn(
                      "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors",
                      active
                        ? "border-primary/40 bg-primary/10 text-primary"
                        : "border-border text-muted-foreground hover:bg-muted/50"
                    )}
                  >
                    <Icon className="h-4 w-4" /> {meta.label}
                  </button>
                );
              })}
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                {SCOPE_TYPE_META[newType].label} value
              </label>
              <Input
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                placeholder={SCOPE_TYPE_META[newType].hint}
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Note (optional)
              </label>
              <Input
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                placeholder="e.g. Acme Corp production perimeter"
              />
            </div>

            <div className="rounded-lg border border-phosphor/20 bg-phosphor/5 p-3">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={scopeAuthConfirmed}
                  onChange={(e) => setScopeAuthConfirmed(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-border bg-muted/30 text-phosphor focus:ring-phosphor/30"
                />
                <span className="text-sm text-muted-foreground">
                  I confirm I have authorization to scan this target and have read
                  the{" "}
                  <a
                    href="/legal/authorized-scanning"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-phosphor hover:underline"
                  >
                    Authorized Scanning Policy
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </span>
              </label>
            </div>

            {createError && (
              <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                <Info className="h-4 w-4 shrink-0" /> {createError}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={creating || !scopeAuthConfirmed}>
              {creating ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              Add Scope
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      </div>
    </div>
  );
}

export default function ScopesPage() {
  return (
    <ProtectedRoute>
      <ScopesContent />
    </ProtectedRoute>
  );
}
