import api from "@/lib/api";

export type AssetType = "domain" | "host" | "ip" | "service" | "certificate" | "technology";
export type AssetState = "active" | "missing";

export interface InventoryAsset {
  id: string;
  type: AssetType;
  value: string;
  label: string;
  state: AssetState;
  is_alive: boolean;
  root_domain: string | null;
  parent_id: string | null;
  parent: string | null;
  first_seen: string | null;
  last_seen: string | null;
  missing_since: string | null;
  last_scan_id: string | null;
  attributes: Record<string, any>;
  services?: number;
  technologies?: number;
}

export interface InventoryChange {
  id: string;
  asset_id: string | null;
  event: string;
  change_type: "added" | "removed" | "modified";
  entity_type: string;
  entity_key: string;
  severity: string;
  summary: string;
  root_domain: string | null;
  detail: Record<string, any>;
  scan_id: string | null;
  detected_at: string | null;
}

export interface InventorySummary {
  by_type: Record<AssetType, { active: number; missing: number }>;
  total_active: number;
  total_missing: number;
  new_last_7_days: number;
  changes_last_7_days: number;
  certificates_expiring: number;
  cert_expiry_days: number;
  root_domains: string[];
  plan: { name: string | null; hosts_limit: number | null; hosts_used: number; at_limit: boolean };
  needs_rebuild: boolean;
  missing_after_scans: number;
}

export interface Paged<T> {
  total: number;
  skip: number;
  limit: number;
  items: T[];
}

export interface AssetDetail {
  asset: InventoryAsset;
  children: InventoryAsset[];
  history: InventoryChange[];
  findings: { id: string; name: string; severity: string; host: string; status: string; scan_id: string }[];
}

export interface AlertRule {
  in_app: boolean;
  email: boolean;
}

export interface AlertSettings {
  enabled: boolean;
  rules: Record<string, AlertRule>;
  cert_expiry_days: number;
  finding_min_severity: "critical" | "high" | "medium";
  recipients: "admins" | "all";
  extra_emails: string[];
  alert_types: { key: string; label: string; description: string }[];
  email_delivery: { provider: string; configured: boolean };
  can_edit: boolean;
  max_extra_emails: number;
}

export interface AssetQuery {
  type?: AssetType;
  state?: "active" | "missing" | "all";
  root?: string;
  q?: string;
  new_days?: number;
  sort?: string;
  order?: "asc" | "desc";
  skip?: number;
  limit?: number;
}

export async function getInventorySummary(): Promise<InventorySummary> {
  return (await api.get("/inventory/summary")).data;
}

export async function listInventoryAssets(params: AssetQuery): Promise<Paged<InventoryAsset>> {
  return (await api.get("/inventory/assets", { params })).data;
}

export async function getInventoryAsset(id: string): Promise<AssetDetail> {
  return (await api.get(`/inventory/assets/${encodeURIComponent(id)}`)).data;
}

export async function listInventoryChanges(params: {
  alert?: string;
  root?: string;
  days?: number;
  skip?: number;
  limit?: number;
}): Promise<Paged<InventoryChange>> {
  return (await api.get("/inventory/changes", { params })).data;
}

export async function getAlertSettings(): Promise<AlertSettings> {
  return (await api.get("/inventory/alert-settings")).data;
}

export async function updateAlertSettings(
  body: Partial<Pick<AlertSettings, "enabled" | "rules" | "cert_expiry_days" | "finding_min_severity" | "recipients" | "extra_emails">>
): Promise<AlertSettings> {
  return (await api.put("/inventory/alert-settings", body)).data;
}

export async function rebuildInventory(): Promise<{ scans_processed: number; assets_created: number }> {
  return (await api.post("/inventory/rebuild")).data;
}

export async function downloadInventoryCsv(params: AssetQuery): Promise<void> {
  const res = await api.get("/inventory/assets/export", { params, responseType: "blob" });
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "asset-inventory.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
