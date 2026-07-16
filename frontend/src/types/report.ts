export interface ExecAsset {
  asset_id: string;
  value: string | null;
  asset_type: string | null;
  exposure_score: number;
}

export interface ExecutiveReport {
  total_assets: number;
  total_scans: number;
  active_scans: number;
  critical_vulns: number;
  high_vulns: number;
  medium_vulns: number;
  low_vulns: number;
  top_exposed_assets: ExecAsset[];
  summary_text: string;
  generated_at: string | null;
}

export interface ExecutiveReportGenerated extends ExecutiveReport {
  format: string;
  note: string | null;
}
