export type ReplayMode = "hourly" | "daily" | "weekly" | "monthly" | "quarterly" | "yearly";
export type ReplaySpeed = 0.25 | 0.5 | 1 | 2 | 4 | 8;
export type AssetLifecycle = "discovered" | "verified" | "observed" | "changed" | "deprecated" | "removed" | "rediscovered";
export type ChangeType = "added" | "removed" | "modified" | "unchanged";

export interface ReplayBookmark {
  id: string;
  name: string;
  timestamp: string;
  notes: string;
  created_at: string;
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  type: "scan_completed" | "asset_discovered" | "asset_removed" | "dns_changed" | "cert_renewed" | "cert_expired" | "tech_changed" | "port_opened" | "port_closed" | "exposure_spike" | "risk_reduction" | "infrastructure_expansion" | "technology_migration";
  title: string;
  description: string;
  severity: "info" | "warning" | "critical" | "success";
  metadata: Record<string, any>;
}

export interface HistoricalAsset {
  id: string;
  hostname: string;
  asset_type: string;
  ip_addresses: string[];
  first_seen: string;
  last_seen: string;
  status: AssetLifecycle;
  technologies: string[];
  certificates: string[];
  dns_records: string[];
  ports: number[];
  exposure_score: number;
  risk_level: string;
  metadata: Record<string, any>;
}

export interface HistoricalSnapshot {
  timestamp: string;
  scan_id: string;
  scan_name: string;
  domain: string;
  assets: HistoricalAsset[];
  total_assets: number;
  total_subdomains: number;
  total_ports: number;
  total_certificates: number;
  total_technologies: number;
  exposure_score: number;
  risk_score: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
}

export interface AssetChange {
  id: string;
  asset_id: string;
  hostname: string;
  change_type: ChangeType;
  field: string;
  old_value: string;
  new_value: string;
  timestamp: string;
  scan_id: string;
}

export interface ReplayDiff {
  from_timestamp: string;
  to_timestamp: string;
  added_assets: HistoricalAsset[];
  removed_assets: HistoricalAsset[];
  modified_assets: AssetChange[];
  unchanged_count: number;
  summary: string;
}

export interface ExposureEvolution {
  timestamp: string;
  score: number;
  delta: number;
  reasons: string[];
  assets_count: number;
  critical_count: number;
}

export interface ReplayState {
  currentTimestamp: string;
  fromTimestamp: string;
  toTimestamp: string;
  scans: HistoricalSnapshot[];
  selectedScan: HistoricalSnapshot | null;
  mode: ReplayMode;
  speed: ReplaySpeed;
  isPlaying: boolean;
  bookmarks: ReplayBookmark[];
  events: TimelineEvent[];
  diff: ReplayDiff | null;
  exposureHistory: ExposureEvolution[];
  filters: ReplayFilters;
  loading: boolean;
}

export interface ReplayFilters {
  organization_id: string | null;
  project_id: string | null;
  environment: string | null;
  technology: string | null;
  asset_type: string | null;
  critical_only: boolean;
}

export interface ReplayContextType {
  state: ReplayState;
  initData: (scans: HistoricalSnapshot[], events: TimelineEvent[], exposureHistory: ExposureEvolution[]) => void;
  setTimestamp: (ts: string) => void;
  setFromTimestamp: (ts: string) => void;
  setToTimestamp: (ts: string) => void;
  setMode: (mode: ReplayMode) => void;
  setSpeed: (speed: ReplaySpeed) => void;
  play: () => void;
  pause: () => void;
  stepForward: () => void;
  stepBackward: () => void;
  jumpToScan: (scanId: string) => void;
  addBookmark: (name: string, notes: string) => void;
  removeBookmark: (id: string) => void;
  setFilters: (filters: Partial<ReplayFilters>) => void;
  computeDiff: () => void;
}
