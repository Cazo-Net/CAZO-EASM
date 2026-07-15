export interface Scan {
  id: string;
  domain: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  scan_type: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ScanDetail extends Scan {
  subdomains_count: number;
  vulnerabilities_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  risk_score: number | null;
  error_message: string | null;
}

export interface Subdomain {
  id: string;
  hostname: string;
  ip_addresses: string[];
  is_alive: boolean;
  scan_id: string;
  discovered_at: string;
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
  } | null;
  created_at: string;
  last_login: string | null;
}

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
