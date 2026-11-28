"use client";

import * as React from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { FileText, Server, ShieldAlert, ShieldCheck, Activity, Download } from "lucide-react";
import { getExecutiveReport, generateExecutiveReport } from "@/lib/api-reports";
import { getErrorMessage } from "@/lib/api";
import type { ExecutiveReport } from "@/types/report";

export default function ExecutiveReportPage() {
  const [report, setReport] = React.useState<ExecutiveReport | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [generating, setGenerating] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getExecutiveReport();
      setReport(data);
    } catch (e) {
      setError(getErrorMessage(e, "Failed to load executive report"));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  async function handleGenerate(format: "json" | "pdf" | "csv") {
    setGenerating(true);
    setError(null);
    try {
      const data = await generateExecutiveReport(format);
      setReport(data);
      setToast(`Report generated at ${data.generated_at ?? "now"} (${format.toUpperCase()})`);
      setTimeout(() => setToast(null), 4000);
    } catch (e) {
      setError(getErrorMessage(e, "Failed to generate report"));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="page-container-md py-6">
      <PageHeader
        title="Executive Reporting"
        description="Organization-wide security posture at a glance."
        icon={<FileText className="h-5 w-5" />}
        actions={
          <button
            onClick={() => handleGenerate("json")}
            disabled={generating}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            {generating ? "Generating…" : "Generate Report"}
          </button>
        }
      />

      {toast && (
        <div className="mb-4 rounded-lg border border-success/40 bg-success/10 px-4 py-2 text-sm text-success">
          {toast}
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading report…</p>
      ) : report ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total Assets" value={report.total_assets} icon={<Server className="h-5 w-5" />} accent="brand" />
            <StatCard label="Scans" value={report.total_scans} hint={`${report.active_scans} active`} icon={<Activity className="h-5 w-5" />} accent="info" />
            <StatCard label="Critical findings" value={report.critical_vulns} icon={<ShieldAlert className="h-5 w-5" />} accent="danger" />
            <StatCard label="High findings" value={report.high_vulns} icon={<ShieldCheck className="h-5 w-5" />} accent="warning" />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <SectionCard title="Top Exposed Assets" description="By exposure score (desc)">
              {(report.top_exposed_assets ?? []).length === 0 ? (
                <EmptyState title="No exposure data" description="Run a scan to surface your top exposed assets." />
              ) : (
                <ul className="divide-y divide-border/50">
                  {report.top_exposed_assets.map((a) => (
                    <li key={a.asset_id} className="flex items-center justify-between py-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{a.value ?? a.asset_id}</p>
                        <p className="text-xs text-muted-foreground">{a.asset_type ?? "asset"}</p>
                      </div>
                      <span className="rounded-full bg-destructive/10 px-2.5 py-0.5 text-xs font-medium text-destructive">
                        {a.exposure_score.toFixed(1)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>

            <SectionCard title="Executive Summary">
              <p className="text-sm leading-relaxed text-muted-foreground">{report.summary_text}</p>
            </SectionCard>
          </div>
        </>
      ) : (
        <EmptyState title="No report data" description="Unable to load the executive report." />
      )}
    </div>
  );
}
