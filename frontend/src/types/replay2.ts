// TS types for the real Exposure Replay data (do not edit types/replay.ts).

export interface ReplaySnapshot {
  scan_id: string;
  domain: string;
  started_at: string | null;
  completed_at: string | null;
  subdomain_count: number;
  port_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  overall_risk_score: number | null;
}

export interface ReplayTimelineResponse {
  organization_id: string;
  snapshots: ReplaySnapshot[];
}

export interface ReplayChangeItem {
  id: string;
  change_type: "added" | "removed" | "modified";
  entity_type: string;
  entity_key: string;
  detail: Record<string, unknown>;
}

export interface ReplayChangesResponse {
  from_scan_id: string | null;
  to_scan_id: string | null;
  added: ReplayChangeItem[];
  removed: ReplayChangeItem[];
  modified: ReplayChangeItem[];
  summary: string;
}

export interface ReplayExposureResponse {
  scan_id: string;
  domain: string;
  completed_at: string | null;
  total_assets: number;
  subdomain_count: number;
  port_count: number;
  certificate_count: number;
  technology_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  overall_risk_score: number | null;
  risk_breakdown: Record<string, unknown>;
}
