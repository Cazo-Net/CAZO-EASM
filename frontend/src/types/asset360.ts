export interface Asset360Score {
  health_score: number | null;
  exposure_score: number | null;
  health_factors: unknown[] | null;
  exposure_factors: unknown[] | null;
  scored_at: string | null;
}

export interface Asset360Relationship {
  id: string;
  relationship_type: string;
  direction: "outgoing" | "incoming";
  related_asset_id: string;
  related_asset_label: string | null;
  related_asset_type: string | null;
  last_seen: string | null;
}

export interface Asset360Change {
  id: string;
  change_type: string;
  entity_type: string;
  entity_key: string;
  detail: Record<string, unknown> | null;
  detected_at: string | null;
}

export interface Asset360Counts {
  subdomains: number;
  ports: number;
  vulnerabilities: number;
  relationships: number;
}

export interface Asset360Summary {
  id: string;
  organization_id: string;
  asset_type: string;
  value: string;
  label: string | null;
  is_alive: boolean;
  first_seen: string | null;
  last_seen: string | null;
  attributes: Record<string, unknown> | null;
}

export interface Asset360Response {
  asset: Asset360Summary;
  score: Asset360Score | null;
  relationships: Asset360Relationship[];
  changes: Asset360Change[];
  counts: Asset360Counts;
  first_seen: string | null;
  last_seen: string | null;
}

export interface Asset360ListItem {
  id: string;
  asset_type: string;
  value: string;
  label: string | null;
  is_alive: boolean;
  first_seen: string | null;
  last_seen: string | null;
}
