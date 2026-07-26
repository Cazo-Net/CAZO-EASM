export interface ScanOptions {
  scan_size: "small" | "large";
  max_subdomains: number;
  port_mode: "quick" | "full";
  include_nuclei: boolean;
  subdomain_tools: ("default" | "subfinder" | "amass")[];
}

export interface Scan {
  id: string;
  domain: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  scan_type: string;
  scan_options: ScanOptions | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ScanDetail extends Scan {
  subdomains_count: number;
  ports_count: number;
  vulnerabilities_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  risk_score: number | null;
  error_message: string | null;
  scanner_status: Record<string, string> | null;
}

export interface Subdomain {
  id: string;
  hostname: string;
  ip_addresses: string[];
  is_alive: boolean;
  scan_id: string;
  discovered_at: string;
  first_seen: string | null;
}

export interface Port {
  id: string;
  subdomain_id: string;
  hostname: string;
  port_number: number;
  state: string;
  service: string | null;
  version: string | null;
  banner: string | null;
  scanned_at: string;
}

export interface SSLCertificate {
  id: string;
  subdomain_id: string;
  hostname: string;
  issuer: string | null;
  subject: string | null;
  not_before: string | null;
  not_after: string | null;
  is_valid: boolean;
  grade: string | null;
  protocol: string | null;
  cipher_suite: string | null;
  scanned_at: string;
}

export interface DNSRecord {
  id: string;
  subdomain_id: string;
  hostname: string;
  record_type: string;
  value: string;
  ttl: number | null;
  created_at: string;
}

export interface Technology {
  id: string;
  subdomain_id: string;
  hostname: string;
  name: string;
  category: string | null;
  version: string | null;
  confidence: number;
  detected_at: string;
}

export interface Vulnerability {
  id: string;
  scan_id: string;
  subdomain_id: string | null;
  template_id: string;
  name: string;
  severity: "critical" | "high" | "medium" | "low" | "unknown";
  vuln_type: string | null;
  host: string;
  matched_at: string | null;
  description: string | null;
  reference: string[];
  tags: string[];
  curl_command: string | null;
  extracted_results: string[];
  found_at: string;
}

export interface WhoisRecord {
  id: string;
  domain: string;
  scan_id: string;
  registrar: string | null;
  creation_date: string | null;
  expiration_date: string | null;
  name_servers: string[];
  registrant_name: string | null;
  registrant_org: string | null;
  registrant_country: string | null;
  scanned_at: string;
}

export interface RiskScore {
  id: string;
  overall_score: number;
  breakdown: Record<string, number>;
  factors: string[];
  calculated_at: string;
}

export interface ScanResults {
  scan: Scan;
  subdomains: Subdomain[];
  risk_score: RiskScore | null;
  subdomains_count: number;
}

export type RiskLabel = "Low" | "Medium" | "High" | "Critical";

export function getRiskLabel(score: number): RiskLabel {
  if (score <= 25) return "Low";
  if (score <= 50) return "Medium";
  if (score <= 75) return "High";
  return "Critical";
}

export function getRiskColor(score: number): string {
  if (score <= 25) return "text-emerald-600 bg-emerald-50";
  if (score <= 50) return "text-amber-600 bg-amber-50";
  if (score <= 75) return "text-orange-600 bg-orange-50";
  return "text-red-600 bg-red-50";
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  organization_id: string | null;
  is_active: boolean;
  email_verified: boolean;
  totp_enabled: boolean;
  preferences: {
    email_notifications: boolean;
    ssl_expiry_alerts: boolean;
    weekly_reports: boolean;
    scan_complete_alerts: boolean;
    onboarding?: {
      completed: boolean;
      first_scan_domain?: string;
      first_scan_id?: string;
      hints_seen?: string[];
      checklist_dismissed?: boolean;
      checklist_completed?: string[];
    };
  } | null;
  created_at: string;
  last_login: string | null;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  plan: string;
  settings: Record<string, unknown> | null;
  logo_url: string | null;
  website: string | null;
  description: string | null;
  industry: string | null;
  company_size: string | null;
  trial_ends_at: string | null;
  mfa_enforced: boolean;
  allowed_email_domains: string[] | null;
  is_active: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface OrganizationMember {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  email_verified: boolean;
  last_login: string | null;
  created_at: string;
}

export interface OrganizationStats {
  member_count: number;
  project_count: number;
  scan_count: number;
  active_scan_count: number;
  asset_count: number;
  invitation_count: number;
  role_distribution: Record<string, number>;
  plan: string;
  is_active: boolean;
  created_at: string;
}

export type OrgRole =
  | "owner"
  | "admin"
  | "security_manager"
  | "analyst"
  | "viewer";

export interface Tag {
  id: string;
  name: string;
  color: string;
  user_id: string;
  created_at: string;
}

export interface AuditLog {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  entity_name: string | null;
  details: string;
  ip_address: string | null;
  created_at: string;
  user_name: string | null;
}

export interface Favorite {
  id: string;
  user_id: string;
  asset_type: string;
  asset_id: string;
  created_at: string;
}

export interface AIConversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface AIMessage {
  id: string;
  role: string;
  content: string;
  model_used: string | null;
  response_time_ms: number | null;
  created_at: string;
}

export interface AIChatResponse {
  conversation_id: string;
  message: AIMessage;
  suggestions: string[];
  references: Record<string, any>[];
}

export interface AIRecommendation {
  id: string;
  category: string;
  title: string;
  description: string;
  priority: string;
  entity_type: string | null;
  entity_id: string | null;
  status: string;
  created_at: string;
}

export interface AIDashboard {
  today_summary: Record<string, any>;
  recent_changes: Record<string, any>[];
  recommendations: AIRecommendation[];
  certificate_alerts: Record<string, any>;
  technology_changes: Record<string, any>;
  platform_health: Record<string, any>;
}

export interface AIKnowledge {
  id: string;
  title: string;
  category: string;
  content: string;
  related_pages: string[];
  tags: string[];
}

export interface AISettings {
  id: string;
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number;
  language: string;
  tone: string;
  enabled: boolean;
}

export interface AIUsage {
  total_questions: number;
  total_reports: number;
  avg_response_time_ms: number;
  total_tokens: number;
  estimated_cost: number;
}

export interface Canvas {
  id: string;
  name: string;
  description: string;
  user_id: string;
  project_id: string | null;
  viewport_x: number;
  viewport_y: number;
  viewport_zoom: number;
  node_count: number;
  edge_count: number;
  created_at: string;
  updated_at: string;
}

export interface CanvasNode {
  id: string;
  canvas_id: string;
  asset_type: string;
  asset_id: string | null;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  color: string | null;
  icon: string | null;
  risk_level: string;
  data_json: Record<string, any>;
  notes: string;
  tags: string[];
  hidden: boolean;
  locked: boolean;
  created_at: string;
}

export interface CanvasEdge {
  id: string;
  canvas_id: string;
  source_node_id: string;
  target_node_id: string;
  label: string;
  edge_type: string;
  animated: boolean;
  style_json: Record<string, any>;
  created_at: string;
}

export interface CanvasDetail extends Canvas {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
}

export interface ScanAssetPreview {
  asset_type: string;
  asset_id: string;
  label: string;
  detail: Record<string, any>;
  is_alive?: boolean;
  risk_level: string;
}

export interface ScanPreviewResponse {
  scan_id: string;
  domain: string;
  status: string;
  assets: Record<string, ScanAssetPreview[]>;
  counts: Record<string, number>;
}

export type ScopeType = "domain" | "wildcard" | "ip" | "cidr";

export interface AuthorizedScope {
  id: string;
  organization_id: string;
  scope_type: ScopeType;
  value: string;
  verified: boolean;
  note: string | null;
  added_by: string | null;
  created_at: string | null;
}

export interface ScopeCheckResult {
  target: string;
  authorized: boolean;
  reason: string | null;
  matched_scope_id: string | null;
}

// ==================== SECURITY CENTER ====================

export interface SecurityFactor {
  name: string;
  points: number;
  status: "good" | "warning" | "critical" | "info";
  detail?: string;
  recommendation?: string;
}

export interface SecurityDashboard {
  security_score: { score: number; factors: SecurityFactor[] };
  mfa_enabled: boolean;
  email_verified: boolean;
  last_login: string | null;
  active_sessions: number;
  trusted_devices: number;
  active_api_keys: number;
  recovery_codes_available: number;
  failed_logins_30d: number;
  password_age_days: number | null;
}

export interface SessionInfo {
  id: string;
  browser: string | null;
  os: string | null;
  ip_address: string | null;
  location_city: string | null;
  location_country: string | null;
  is_trusted: boolean;
  last_activity: string | null;
  created_at: string | null;
}

export interface TrustedDeviceInfo {
  id: string;
  device_name: string | null;
  browser: string | null;
  os: string | null;
  ip_address: string | null;
  trusted_at: string | null;
  last_used: string | null;
}

export interface LoginHistoryEntry {
  id: string;
  event_type: string;
  success: boolean;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string | null;
}

// ==================== API KEYS V2 ====================

export interface ApiKeyV2 {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  expires_at: string | null;
  last_used_at: string | null;
  last_used_ip: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ApiKeyCreateResponse {
  id: string;
  key: string;
  name: string;
  prefix: string;
  scopes: string[];
  expires_at: string | null;
  created_at: string;
}

// ==================== PASSKEYS ====================

export interface PasskeyInfo {
  id: string;
  device_name: string | null;
  aaguid: string | null;
  created_at: string | null;
  last_used_at: string | null;
}

// ==================== INVITATIONS ====================

export interface Invitation {
  id: string;
  email: string;
  role: string;
  status: string;
  invited_by: string;
  created_at: string;
  expires_at: string;
}

// ==================== FEATURE TYPES (Phases 1.2 - 4.2) ====================
export * from "./asset360";
export * from "./changefeed";
export * from "./replay2";
export * from "./collab";
export * from "./report";
