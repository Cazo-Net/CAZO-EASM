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

export interface HostIntelligence {
  asset_id: string;
  asset_type?: string | null;
  asn: string | null;
  isp: string | null;
  org: string | null;
  ip_addresses: string[];
  ports: {
    port: string | number;
    state: string | null;
    service: string | null;
    version: string | null;
    banner: string | null;
    hostname: string | null;
  }[];
  technologies: {
    name: string;
    category: string;
    version: string | null;
    confidence: number;
    hostname: string | null;
  }[];
  certificates: {
    issuer: string | null;
    subject: string | null;
    grade: string | null;
    protocol: string | null;
    cipher_suite: string | null;
    not_after: string | null;
    hostname: string | null;
  }[];
  vulnerabilities: {
    id: string;
    name: string;
    severity: string | null;
    host: string | null;
    matched_at: string | null;
    status: string | null;
  }[];
}
