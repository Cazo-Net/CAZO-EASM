"use client";

import { ProtectedRoute } from "@/components/ProtectedRoute";
import * as React from "react";
import Link from "next/link";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Boxes } from "lucide-react";
import { listAssets360 } from "@/lib/api-asset360";
import { getErrorMessage } from "@/lib/api";
import type { Asset360ListItem } from "@/types/asset360";

function Asset360IndexContent() {
  const [assets, setAssets] = React.useState<Asset360ListItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    listAssets360({ limit: 100 })
      .then((data) => {
        if (active) setAssets(data);
      })
      .catch((e) => {
        if (active) setError(getErrorMessage(e, "Failed to load assets"));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="page-container-md">
      <PageHeader
        title="Asset 360°"
        description="Select an asset to view its unified intelligence profile."
        icon={<Boxes className="h-5 w-5" />}
        breadcrumbs={[{ label: "Assets", href: "/assets" }, { label: "360°" }]}
      />

      {error && (
        <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <SectionCard title="Assets">
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading assets…</p>
        ) : assets.length === 0 ? (
          <EmptyState
            title="No assets yet"
            description="Discovered assets show up here after your first scan."
          />
        ) : (
          <ul className="divide-y divide-border/50">
            {assets.map((a) => (
              <li key={a.id}>
                <Link
                  href={`/assets/${a.id}`}
                  className="flex items-center justify-between py-3 transition-colors hover:text-brand"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{a.label || a.value}</p>
                    <p className="text-xs text-muted-foreground">{a.asset_type}</p>
                  </div>
                  <span
                    className={
                      "rounded-full px-2.5 py-0.5 text-xs font-medium " +
                      (a.is_alive
                        ? "bg-success/10 text-success"
                        : "bg-muted text-muted-foreground")
                    }
                  >
                    {a.is_alive ? "Alive" : "Unknown"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  );
}

export default function Asset360IndexPage() {
  return (
    <ProtectedRoute>
      <Asset360IndexContent />
    </ProtectedRoute>
  );
}
