"use client";

import { useReplay } from "./ReplayProvider";
import { Filter } from "lucide-react";

export function ReplayFilters() {
  const { state, setFilters } = useReplay();

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold flex items-center gap-2">
        <Filter className="h-4 w-4 text-muted-foreground" />
        Filters
      </h3>

      <div className="space-y-2">
        <div>
          <label className="text-[10px] font-medium text-muted-foreground mb-1 block">Technology</label>
          <select
            value={state.filters.technology || ""}
            onChange={(e) => setFilters({ technology: e.target.value || null })}
            className="w-full rounded-lg border border-border/30 bg-card/10 px-3 py-1.5 text-xs outline-none focus:border-brand/50"
          >
            <option value="">All Technologies</option>
            <option value="nginx">Nginx</option>
            <option value="apache">Apache</option>
            <option value="cloudflare">Cloudflare</option>
            <option value="aws">AWS</option>
            <option value="docker">Docker</option>
          </select>
        </div>

        <div>
          <label className="text-[10px] font-medium text-muted-foreground mb-1 block">Asset Type</label>
          <select
            value={state.filters.asset_type || ""}
            onChange={(e) => setFilters({ asset_type: e.target.value || null })}
            className="w-full rounded-lg border border-border/30 bg-card/10 px-3 py-1.5 text-xs outline-none focus:border-brand/50"
          >
            <option value="">All Types</option>
            <option value="subdomain">Subdomains</option>
            <option value="ip">IP Addresses</option>
            <option value="domain">Domains</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="critical-only"
            checked={state.filters.critical_only}
            onChange={(e) => setFilters({ critical_only: e.target.checked })}
            className="h-3.5 w-3.5 rounded border-border bg-muted/30 accent-brand"
          />
          <label htmlFor="critical-only" className="text-xs text-muted-foreground">
            Critical assets only
          </label>
        </div>
      </div>
    </div>
  );
}
