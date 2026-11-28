"use client";

import * as React from "react";
import Link from "next/link";
import { Loader2, X, ExternalLink } from "lucide-react";
import { getInventoryAsset, type AssetDetail, type InventoryAsset } from "@/lib/api-inventory";
import {
  TYPE_META,
  ChangeRow,
  SeverityTag,
  StateBadge,
  assetDetails,
  assetTitle,
  daysUntil,
  formatDate,
} from "./shared";

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 break-words text-sm">{children}</dd>
    </div>
  );
}

function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <section className="border-t border-border px-5 py-4">
      <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
        {count !== undefined && <span className="font-normal tabular-nums">{count}</span>}
      </h3>
      {children}
    </section>
  );
}

function ChildList({ items, onOpen }: { items: InventoryAsset[]; onOpen: (id: string) => void }) {
  return (
    <ul className="divide-y divide-border rounded-lg border border-border">
      {items.map((c) => (
        <li key={c.id}>
          <button
            type="button"
            onClick={() => onOpen(c.id)}
            className="flex w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-muted/40 focus-visible:bg-muted/40 focus-visible:outline-none"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-[13px]">
                {c.type === "service" ? `${c.attributes.port}/tcp` : c.type === "technology" ? c.label : assetTitle(c)}
              </p>
              <p className="truncate text-xs text-muted-foreground">{assetDetails(c)}</p>
            </div>
            <StateBadge asset={c} />
          </button>
        </li>
      ))}
    </ul>
  );
}

export function AssetDrawer({
  assetId,
  onClose,
  onNavigate,
}: {
  assetId: string | null;
  onClose: () => void;
  onNavigate: (id: string) => void;
}) {
  const [detail, setDetail] = React.useState<AssetDetail | null>(null);
  const [error, setError] = React.useState("");
  const closeRef = React.useRef<HTMLButtonElement>(null);

  React.useEffect(() => {
    if (!assetId) return;
    let cancelled = false;
    setDetail(null);
    setError("");
    getInventoryAsset(assetId)
      .then((d) => !cancelled && setDetail(d))
      .catch(() => !cancelled && setError("This asset could not be loaded."));
    return () => {
      cancelled = true;
    };
  }, [assetId]);

  React.useEffect(() => {
    if (!assetId) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [assetId, onClose]);

  if (!assetId) return null;
  const a = detail?.asset;
  const at = a?.attributes || {};
  const by = (t: string) => (detail?.children || []).filter((c) => c.type === t);
  const Icon = a ? TYPE_META[a.type].icon : null;
  const certDays = a?.type === "certificate" ? daysUntil(at.not_after) : null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Asset details">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} aria-hidden="true" />
      <aside className="relative flex h-full w-full max-w-[560px] flex-col overflow-y-auto border-l border-border bg-card shadow-2xl">
        <header className="sticky top-0 z-10 flex items-start gap-3 border-b border-border bg-card px-5 py-4">
          {Icon && (
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-primary">
              <Icon className="h-[18px] w-[18px]" />
            </div>
          )}
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted-foreground">{a ? TYPE_META[a.type].label : "Asset"}</p>
            <h2 className="break-all font-mono text-[15px] font-semibold leading-snug">
              {a ? assetTitle(a) : "Loading…"}
            </h2>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        {error && <p className="px-5 py-6 text-sm text-destructive">{error}</p>}
        {!detail && !error && (
          <div className="flex items-center justify-center py-24 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading…
          </div>
        )}

        {detail && a && (
          <>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 px-5 py-4">
              <Fact label="Status">
                <StateBadge asset={a} />
              </Fact>
              <Fact label="Root domain">
                <span className="font-mono text-[13px]">{a.root_domain || "—"}</span>
              </Fact>
              <Fact label="First seen">{formatDate(a.first_seen)}</Fact>
              <Fact label={a.state === "missing" ? "Last seen" : "Last confirmed"}>{formatDate(a.last_seen)}</Fact>
              {a.state === "missing" && <Fact label="Missing since">{formatDate(a.missing_since)}</Fact>}
              {a.parent && a.parent_id && (
                <Fact label="Host">
                  <button
                    type="button"
                    onClick={() => onNavigate(a.parent_id!)}
                    className="font-mono text-[13px] text-primary hover:underline"
                  >
                    {a.parent}
                  </button>
                </Fact>
              )}
              {a.type === "host" && (at.ip_addresses || []).length > 0 && (
                <Fact label="IP addresses">
                  <span className="font-mono text-[13px]">{(at.ip_addresses as string[]).join(", ")}</span>
                </Fact>
              )}
              {a.type === "service" && (
                <>
                  <Fact label="Port">
                    <span className="font-mono text-[13px]">{at.port}/tcp</span>
                  </Fact>
                  <Fact label="Service">{[at.service, at.product, at.version].filter(Boolean).join(" ") || "—"}</Fact>
                </>
              )}
              {a.type === "certificate" && (
                <>
                  <Fact label="Issuer">{at.issuer || "—"}</Fact>
                  <Fact label="Expires">
                    {formatDate(at.not_after)}
                    {certDays !== null && (
                      <span className={certDays <= 30 ? "ml-2 text-warning" : "ml-2 text-muted-foreground"}>
                        {certDays < 0 ? `expired ${-certDays}d ago` : `in ${certDays}d`}
                      </span>
                    )}
                  </Fact>
                  <Fact label="Serial">
                    <span className="break-all font-mono text-xs">{at.serial_number || a.value}</span>
                  </Fact>
                  <Fact label="Grade">{at.grade || "—"}</Fact>
                  <div className="col-span-2">
                    <Fact label="Served by">
                      <span className="font-mono text-[13px]">{((at.hosts as string[]) || []).join(", ") || "—"}</span>
                    </Fact>
                  </div>
                </>
              )}
              {a.type === "technology" && (
                <>
                  <Fact label="Version">{at.version || "Not detected"}</Fact>
                  <Fact label="Category">{at.category || "—"}</Fact>
                </>
              )}
            </dl>

            {by("service").length > 0 && (
              <Section title="Open ports" count={by("service").filter((c) => c.state !== "missing").length}>
                <ChildList items={by("service")} onOpen={onNavigate} />
              </Section>
            )}
            {by("certificate").length > 0 && (
              <Section title="Certificates" count={by("certificate").length}>
                <ChildList items={by("certificate")} onOpen={onNavigate} />
              </Section>
            )}
            {by("technology").length > 0 && (
              <Section title="Technologies" count={by("technology").length}>
                <ChildList items={by("technology")} onOpen={onNavigate} />
              </Section>
            )}
            {by("host").length > 0 && (
              <Section title="Hosts" count={by("host").length}>
                <ChildList items={by("host")} onOpen={onNavigate} />
              </Section>
            )}

            {detail.findings.length > 0 && (
              <Section title="Findings in the latest scan" count={detail.findings.length}>
                <ul className="divide-y divide-border rounded-lg border border-border">
                  {detail.findings.slice(0, 12).map((f) => (
                    <li key={f.id} className="flex items-center gap-3 px-3 py-2">
                      <span className="min-w-0 flex-1 truncate text-sm">{f.name}</span>
                      <SeverityTag severity={f.severity} />
                    </li>
                  ))}
                </ul>
                {a.last_scan_id && (
                  <Link
                    href={`/scan/${a.last_scan_id}`}
                    className="mt-2 inline-flex items-center gap-1 text-xs text-primary hover:underline"
                  >
                    Open the scan <ExternalLink className="h-3 w-3" />
                  </Link>
                )}
              </Section>
            )}

            <Section title="History" count={detail.history.length}>
              {detail.history.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nothing has changed since this asset was first seen.</p>
              ) : (
                <div className="-mx-4 divide-y divide-border">
                  {detail.history.map((h) => (
                    <ChangeRow key={h.id} change={h} compact />
                  ))}
                </div>
              )}
            </Section>
          </>
        )}
      </aside>
    </div>
  );
}
