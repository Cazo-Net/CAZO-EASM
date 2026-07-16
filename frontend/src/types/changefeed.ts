export type ChangeType = "added" | "removed" | "modified";

export interface ChangeFeedItem {
  id: string;
  change_type: string;
  entity_type: string;
  entity_key: string;
  detail: Record<string, unknown> | null;
  from_scan_id: string | null;
  to_scan_id: string | null;
  asset_label: string | null;
  detected_at: string | null;
}

export interface ChangeFeedSummary {
  added: number;
  removed: number;
  modified: number;
  total: number;
  since: string | null;
}
