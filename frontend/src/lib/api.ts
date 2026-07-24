import axios from "axios";
import type {
  Scan,
  ScanDetail,
  Subdomain,
  Port,
  SSLCertificate,
  Technology,
  AuthorizedScope,
  ScopeCheckResult,
} from "@/types";

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

// Auth interceptor — attach JWT if present
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Response interceptor — transparently retry rate-limited (429) GETs with backoff.
const MAX_RETRIES = 3;
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error?.config;
    const status = error?.response?.status;
    if (status === 429 && config && (config.method ?? "get").toLowerCase() === "get") {
      config.__retryCount = (config.__retryCount ?? 0) + 1;
      if (config.__retryCount <= MAX_RETRIES) {
        const retryAfter = Number(error.response?.headers?.["retry-after"]);
        const delay = Number.isFinite(retryAfter) && retryAfter > 0
          ? retryAfter * 1000
          : 500 * 2 ** (config.__retryCount - 1);
        await new Promise((r) => setTimeout(r, delay));
        return api(config);
      }
    }
    return Promise.reject(error);
  }
);

export default api;

// --- Auth ---
export async function register(email: string, password: string, fullName?: string) {
  const { data } = await api.post("/auth/register", {
    email,
    password,
    full_name: fullName,
  });
  return data;
}

export async function login(email: string, password: string, rememberMe = true) {
  const { data } = await api.post("/auth/login", { email, password });
  if (typeof window !== "undefined") {
    const storage = rememberMe ? localStorage : sessionStorage;
    storage.setItem("access_token", data.access_token);
    storage.setItem("refresh_token", data.refresh_token);
    // Clear the other storage to avoid stale tokens
    const other = rememberMe ? sessionStorage : localStorage;
    other.removeItem("access_token");
    other.removeItem("refresh_token");
  }
  return data;
}

export async function loginWithGoogle(credential: string) {
  const { data } = await api.post("/auth/google", { credential });
  if (typeof window !== "undefined") {
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
  }
  return data;
}

export function logout() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("refresh_token");
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token") || sessionStorage.getItem("access_token");
}

// Normalize an API error into a human-readable string. FastAPI returns 422
// validation errors as `detail: [{ type, loc, msg, ... }]` (an array of objects)
// which must never be rendered directly as a React child.
export function getErrorMessage(err: unknown, fallback = "Something went wrong"): string {
  const detail = (err as any)?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msg = detail
      .map((d) => (typeof d === "string" ? d : d?.msg))
      .filter(Boolean)
      .join(", ");
    if (msg) return msg;
  }
  if (detail && typeof detail === "object" && typeof detail.msg === "string") {
    return detail.msg;
  }
  if (typeof (err as any)?.message === "string") return (err as any).message;
  return fallback;
}

// --- Auth (new endpoints) ---
export async function forgotPassword(email: string) {
  const { data } = await api.post("/auth/forgot-password", { email });
  return data;
}

export async function resetPassword(token: string, newPassword: string) {
  const { data } = await api.post("/auth/reset-password", { token, new_password: newPassword });
  return data;
}

export async function verifyEmail(token: string) {
  const { data } = await api.post("/auth/verify-email", { token });
  return data;
}

export async function setup2FA() {
  const { data } = await api.post("/auth/2fa/setup");
  return data;
}

export async function enable2FA(code: string) {
  const { data } = await api.post("/auth/2fa/enable", { code });
  return data;
}

export async function disable2FA(code: string) {
  const { data } = await api.post("/auth/2fa/disable", { code });
  return data;
}

// --- Scans ---
export async function createScan(
  domain: string,
  scanType = "full",
  scanOptions?: {
    scan_size?: string;
    max_subdomains?: number;
    port_mode?: string;
    include_nuclei?: boolean;
    subdomain_tools?: string[];
  }
): Promise<Scan> {
  const payload: Record<string, any> = { domain, scan_type: scanType };
  if (scanOptions) {
    payload.scan_options = {
      scan_size: "large",
      max_subdomains: 0,
      port_mode: "full",
      include_nuclei: true,
      subdomain_tools: ["default", "subfinder", "amass"],
      ...scanOptions,
    };
  }
  const { data } = await api.post("/scans", payload);
  return data;
}

export async function getScan(scanId: string): Promise<ScanDetail> {
  const { data } = await api.get(`/scans/${scanId}`);
  return data;
}

export async function listScans(params?: { limit?: number; status?: string }): Promise<Scan[]> {
  const { data } = await api.get("/scans", { params: { limit: 20, ...params } });
  return data;
}

export async function listImportableScans(limit = 50): Promise<Scan[]> {
  const { data } = await api.get("/scans/importable", { params: { limit } });
  return data;
}

export async function getDashboardStats(): Promise<{
  scans: number;
  subdomains: number;
  ports: number;
  vulnerabilities: number;
  running: number;
  completed: number;
  failed: number;
  ssl_certificates: number;
  technologies: number;
  dns_records: number;
}> {
  const { data } = await api.get("/scans/stats");
  return data;
}

export async function deleteScan(scanId: string): Promise<void> {
  await api.delete(`/scans/${scanId}`);
}

// --- Assets ---
export async function listSubdomains(scanId?: string): Promise<Subdomain[]> {
  const { data } = await api.get("/assets/subdomains", {
    params: scanId ? { scan_id: scanId } : {},
  });
  return data;
}

export async function listPorts(scanId?: string): Promise<Port[]> {
  const { data } = await api.get("/assets/ports", {
    params: scanId ? { scan_id: scanId } : {},
  });
  return data;
}

export async function listSSLCertificates(scanId?: string): Promise<SSLCertificate[]> {
  const { data } = await api.get("/assets/ssl", {
    params: scanId ? { scan_id: scanId } : {},
  });
  return data;
}

export async function listTechnologies(scanId?: string): Promise<Technology[]> {
  const { data } = await api.get("/assets/technologies", {
    params: scanId ? { scan_id: scanId } : {},
  });
  return data;
}

// --- Vulnerabilities ---
export async function listVulnerabilities(scanId?: string, severity?: string): Promise<any[]> {
  const params: Record<string, string> = {};
  if (scanId) params.scan_id = scanId;
  if (severity) params.severity = severity;
  const { data } = await api.get("/assets/vulnerabilities", { params });
  return data;
}

export async function getVulnerabilitySummary(scanId?: string): Promise<any> {
  const params: Record<string, string> = {};
  if (scanId) params.scan_id = scanId;
  const { data } = await api.get("/assets/vulnerabilities/summary", { params });
  return data;
}

// --- DNS & WHOIS ---
export async function listDNSRecords(scanId?: string): Promise<any[]> {
  const { data } = await api.get("/assets/dns", {
    params: scanId ? { scan_id: scanId } : {},
  });
  return data;
}

export async function listWhoisRecords(scanId?: string): Promise<any[]> {
  const { data } = await api.get("/assets/whois", {
    params: scanId ? { scan_id: scanId } : {},
  });
  return data;
}

// --- Graph ---
export async function getAssetGraph(scanId: string): Promise<any> {
  const { data } = await api.get("/assets/graph", {
    params: { scan_id: scanId },
  });
  return data;
}

// --- Compare ---
export async function compareScans(scanA: string, scanB: string): Promise<any> {
  const { data } = await api.get("/compare", {
    params: { scan_a: scanA, scan_b: scanB },
  });
  return data;
}

// --- Notifications ---
export async function listNotifications(params?: { unread_only?: boolean; limit?: number; skip?: number }): Promise<any> {
  const { data } = await api.get("/notifications", { params });
  return data;
}

export async function getUnreadCount(): Promise<{ count: number }> {
  const { data } = await api.get("/notifications/unread-count");
  return data;
}

export async function markNotificationRead(id: string): Promise<void> {
  await api.put(`/notifications/${id}/read`);
}

export async function markAllNotificationsRead(): Promise<void> {
  await api.put("/notifications/read-all");
}

export async function deleteNotification(id: string): Promise<void> {
  await api.delete(`/notifications/${id}`);
}

export async function clearAllNotifications(): Promise<void> {
  await api.delete("/notifications");
}

// --- User ---
export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await api.put("/users/me/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function deleteAccount(): Promise<void> {
  await api.delete("/users/me");
}

export async function getUserPreferences(): Promise<any> {
  const { data } = await api.get("/users/me/preferences");
  return data;
}

export async function updateUserPreferences(prefs: {
  email_notifications: boolean;
  ssl_expiry_alerts: boolean;
  weekly_reports: boolean;
  scan_complete_alerts: boolean;
}): Promise<void> {
  await api.put("/users/me/preferences", prefs);
}

// --- Notification Preferences (per-type/per-channel) ---
export interface NotificationPreferenceItem {
  notification_type: string;
  in_app_enabled: boolean;
  email_enabled: boolean;
}

export async function getNotificationPreferences(): Promise<NotificationPreferenceItem[]> {
  const { data } = await api.get("/notification-preferences");
  return data?.preferences ?? data ?? [];
}

export async function updateNotificationPreference(
  notificationType: string,
  updates: { in_app_enabled?: boolean; email_enabled?: boolean }
): Promise<void> {
  await api.put(`/notification-preferences/${notificationType}`, updates);
}

// --- API Keys ---
export async function listApiKeys(): Promise<any[]> {
  const { data } = await api.get("/api-keys");
  return data;
}

export async function createApiKey(name: string): Promise<any> {
  const { data } = await api.post("/api-keys", { name });
  return data;
}

export async function revokeApiKey(keyId: string): Promise<void> {
  await api.delete(`/api-keys/${keyId}`);
}

// --- Activity ---
export async function getRecentActivity(limit = 10): Promise<any[]> {
  const { data } = await api.get("/scans/activity", { params: { limit } });
  return data;
}

// --- Export ---
export function exportToCSV(data: any[], filename: string) {
  if (!data || data.length === 0) return;

  const headers = Object.keys(data[0]);
  const csvContent = [
    headers.join(","),
    ...data.map((row) =>
      headers
        .map((h) => {
          const val = row[h];
          if (val === null || val === undefined) return "";
          const str = Array.isArray(val) ? val.join("; ") : String(val);
          return str.includes(",") || str.includes('"') || str.includes("\n")
            ? `"${str.replace(/"/g, '""')}"`
            : str;
        })
        .join(",")
    ),
  ].join("\n");

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${filename}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

// ==================== TAGS ====================

export async function createTag(data: { name: string; color?: string }) {
  const res = await api.post("/tags", data);
  return res.data;
}

export async function listTags() {
  const res = await api.get("/tags");
  return res.data;
}

export async function updateTag(id: string, data: { name: string; color: string }) {
  const res = await api.put(`/tags/${id}`, data);
  return res.data;
}

export async function deleteTag(id: string) {
  await api.delete(`/tags/${id}`);
}

export async function addTagToAsset(assetType: string, assetId: string, tagId: string) {
  const res = await api.post(`/tags/${assetType}/${assetId}/tags`, { tag_id: tagId });
  return res.data;
}

export async function getAssetTags(assetType: string, assetId: string) {
  const res = await api.get(`/tags/${assetType}/${assetId}/tags`);
  return res.data;
}

export async function removeTagFromAsset(assetType: string, assetId: string, tagId: string) {
  await api.delete(`/tags/${assetType}/${assetId}/tags/${tagId}`);
}

// ==================== AUDIT LOGS ====================

export async function listAuditLogs(params?: { action?: string; entity_type?: string; limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.action) query.set("action", params.action);
  if (params?.entity_type) query.set("entity_type", params.entity_type);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const res = await api.get(`/tags/audit-logs?${query.toString()}`);
  return res.data;
}

// ==================== FAVORITES ====================

export async function addFavorite(assetType: string, assetId: string) {
  const res = await api.post("/tags/favorites", { asset_type: assetType, asset_id: assetId });
  return res.data;
}

export async function listFavorites(assetType?: string) {
  const query = assetType ? `?asset_type=${assetType}` : "";
  const res = await api.get(`/tags/favorites${query}`);
  return res.data;
}

export async function removeFavorite(assetType: string, assetId: string) {
  await api.delete(`/tags/favorites/${assetType}/${assetId}`);
}

// ==================== AI INTELLIGENCE ====================

export async function aiChat(message: string, conversationId?: string, orgId?: string, projectId?: string) {
  const params = new URLSearchParams();
  if (conversationId) params.set("conversation_id", conversationId);
  const res = await api.post(`/ai/chat?${params.toString()}`, {
    content: message,
    org_id: orgId,
    project_id: projectId,
  });
  return res.data;
}

export async function listAIConversations(limit = 20) {
  const res = await api.get(`/ai/conversations?limit=${limit}`);
  return res.data;
}

export async function getAIConversation(id: string) {
  const res = await api.get(`/ai/conversations/${id}`);
  return res.data;
}

export async function deleteAIConversation(id: string) {
  await api.delete(`/ai/conversations/${id}`);
}

export async function getAIDashboard(orgId?: string) {
  const query = orgId ? `?org_id=${orgId}` : "";
  const res = await api.get(`/ai/dashboard${query}`);
  return res.data;
}

export async function aiSearch(query: string, orgId?: string, projectId?: string) {
  const res = await api.post("/ai/search", { query, org_id: orgId, project_id: projectId });
  return res.data;
}

export async function aiGenerateReport(reportType: string, orgId?: string, projectId?: string) {
  const res = await api.post("/ai/reports/generate", { report_type: reportType, org_id: orgId, project_id: projectId });
  return res.data;
}

export async function getAIRecommendations(orgId?: string, projectId?: string) {
  const params = new URLSearchParams();
  if (orgId) params.set("org_id", orgId);
  if (projectId) params.set("project_id", projectId);
  const res = await api.get(`/ai/recommendations?${params.toString()}`);
  return res.data;
}

export async function dismissAIRecommendation(id: string) {
  await api.put(`/ai/recommendations/${id}/dismiss`);
}

export async function listAIKnowledge(category?: string, query?: string) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (query) params.set("query", query);
  const res = await api.get(`/ai/knowledge?${params.toString()}`);
  return res.data;
}

export async function getAISettings() {
  const res = await api.get("/ai/settings");
  return res.data;
}

export async function updateAISettings(settings: Record<string, any>) {
  const res = await api.put("/ai/settings", settings);
  return res.data;
}

export async function getAIUsage() {
  const res = await api.get("/ai/usage");
  return res.data;
}

// ==================== INTELLIGENCE CANVAS ====================

export async function listCanvases(projectId?: string) {
  const query = projectId ? `?project_id=${projectId}` : "";
  const res = await api.get(`/canvases${query}`);
  return res.data;
}

export async function getCanvas(id: string) {
  const res = await api.get(`/canvases/${id}`);
  return res.data;
}

export async function createCanvas(data: { name?: string; description?: string; project_id?: string }) {
  const res = await api.post("/canvases", data);
  return res.data;
}

export async function updateCanvas(id: string, data: Record<string, any>) {
  const res = await api.put(`/canvases/${id}`, data);
  return res.data;
}

export async function deleteCanvas(id: string) {
  await api.delete(`/canvases/${id}`);
}

export async function addCanvasNode(canvasId: string, data: Record<string, any>) {
  const res = await api.post(`/canvases/${canvasId}/nodes`, data);
  return res.data;
}

export async function updateCanvasNode(canvasId: string, nodeId: string, data: Record<string, any>) {
  const res = await api.put(`/canvases/${canvasId}/nodes/${nodeId}`, data);
  return res.data;
}

export async function deleteCanvasNode(canvasId: string, nodeId: string) {
  await api.delete(`/canvases/${canvasId}/nodes/${nodeId}`);
}

export async function addCanvasEdge(canvasId: string, data: Record<string, any>) {
  const res = await api.post(`/canvases/${canvasId}/edges`, data);
  return res.data;
}

export async function deleteCanvasEdge(canvasId: string, edgeId: string) {
  await api.delete(`/canvases/${canvasId}/edges/${edgeId}`);
}

export async function importScanToCanvas(canvasId: string, scanId: string, options?: { asset_types?: string[]; asset_ids?: string[] }) {
  const res = await api.post(`/canvases/${canvasId}/import`, {
    scan_id: scanId,
    asset_types: options?.asset_types,
    asset_ids: options?.asset_ids,
  });
  return res.data;
}

export async function previewScanAssets(scanId: string): Promise<{
  scan_id: string;
  domain: string;
  status: string;
  assets: Record<string, { asset_type: string; asset_id: string; label: string; detail: Record<string, any>; is_alive?: boolean; risk_level: string }[]>;
  counts: Record<string, number>;
}> {
  const { data } = await api.get(`/canvases/scan/${scanId}/preview`);
  return data;
}

export async function exportCanvas(canvasId: string, format = "json") {
  const res = await api.get(`/canvases/${canvasId}/export?format=${format}`);
  return res.data;
}

// ==================== SESSIONS (security-center) ====================

// Note: session management is in the SECURITY CENTER section below

// ==================== INVITATIONS ====================

export async function createInvitation(email: string, role = "member") {
  const res = await api.post("/invitations", { email, role });
  return res.data;
}

export async function listInvitations(status?: string) {
  const params = status ? `?status=${status}` : "";
  const res = await api.get(`/invitations${params}`);
  return res.data;
}

export async function acceptInvitation(token: string) {
  const res = await api.post(`/invitations/accept`, null, { params: { token } });
  return res.data;
}

export async function revokeInvitation(invitationId: string) {
  await api.delete(`/invitations/${invitationId}`);
}

export async function resendInvitation(invitationId: string) {
  const res = await api.post(`/invitations/${invitationId}/resend`);
  return res.data;
}

// ==================== ADMIN ====================

export async function adminListUsers(params?: { search?: string; skip?: number; limit?: number }) {
  const res = await api.get("/admin/users", { params });
  return res.data;
}

export async function adminDisableUser(userId: string) {
  await api.put(`/admin/users/${userId}/disable`);
}

export async function adminEnableUser(userId: string) {
  await api.put(`/admin/users/${userId}/enable`);
}

export async function adminUnlockUser(userId: string) {
  await api.put(`/admin/users/${userId}/unlock`);
}

export async function adminForcePasswordReset(userId: string) {
  await api.put(`/admin/users/${userId}/force-password-reset`);
}

export async function adminRevokeUserSessions(userId: string) {
  await api.delete(`/admin/users/${userId}/sessions`);
}

// ==================== SECURITY ====================

export async function requestEmailChange(newEmail: string, password: string) {
  const res = await api.post("/security/change-email", { new_email: newEmail, password });
  return res.data;
}

export async function listTrustedDevices() {
  const res = await api.get("/security/trusted-devices");
  return res.data;
}

export async function revokeTrustedDevice(deviceId: string) {
  await api.delete(`/security/trusted-devices/${deviceId}`);
}

export async function generateRecoveryCodes() {
  const res = await api.post("/security/recovery-codes");
  return res.data;
}

export async function listRecoveryCodes() {
  const res = await api.get("/security/recovery-codes");
  return res.data;
}

// --- Authorized Scopes ---
export async function listScopes(): Promise<AuthorizedScope[]> {
  const res = await api.get("/scopes");
  return res.data;
}

export async function createScope(
  scopeType: string,
  value: string,
  note?: string
): Promise<AuthorizedScope> {
  const res = await api.post("/scopes", { scope_type: scopeType, value, note });
  return res.data;
}

export async function deleteScope(scopeId: string): Promise<void> {
  await api.delete(`/scopes/${scopeId}`);
}

export async function checkScope(value: string): Promise<ScopeCheckResult> {
  const res = await api.post("/scopes/check", { scope_type: "domain", value });
  return res.data;
}

// ==================== BILLING & SUBSCRIPTION ====================

export async function listPlans() {
  const res = await api.get("/billing/plans");
  return res.data;
}

export async function getSubscription() {
  const res = await api.get("/billing/subscription");
  return res.data;
}

export async function createCheckoutSession(data: {
  plan: string;
  success_url: string;
  cancel_url: string;
}) {
  const res = await api.post("/billing/checkout", data);
  return res.data;
}

export async function getBillingPortal(returnUrl: string) {
  const res = await api.get(`/billing/portal?return_url=${encodeURIComponent(returnUrl)}`);
  return res.data;
}

export async function upgradePlan(plan: string) {
  const res = await api.post("/billing/subscription/upgrade", { plan });
  return res.data;
}

export async function downgradePlan(plan: string) {
  const res = await api.post("/billing/subscription/downgrade", { plan });
  return res.data;
}

export async function cancelSubscription(atPeriodEnd = true) {
  const res = await api.post("/billing/subscription/cancel", { at_period_end: atPeriodEnd });
  return res.data;
}

export async function resumeSubscription() {
  const res = await api.post("/billing/subscription/resume");
  return res.data;
}

export async function startTrial() {
  const res = await api.post("/billing/subscription/trial");
  return res.data;
}

export async function listInvoices(limit = 20) {
  const res = await api.get(`/billing/invoices?limit=${limit}`);
  return res.data;
}

export async function listPaymentMethods() {
  const res = await api.get("/billing/payment-methods");
  return res.data;
}

export async function addPaymentMethod(paymentMethodId: string, setAsDefault = false) {
  const res = await api.post("/billing/payment-methods", {
    payment_method_id: paymentMethodId,
    set_as_default: setAsDefault,
  });
  return res.data;
}

export async function removePaymentMethod(paymentMethodId: string) {
  await api.delete(`/billing/payment-methods/${paymentMethodId}`);
}

export async function setDefaultPaymentMethod(paymentMethodId: string) {
  await api.put(`/billing/payment-methods/${paymentMethodId}/default`);
}

export async function getUsageSummary() {
  const res = await api.get("/billing/usage");
  return res.data;
}

export async function refreshUsage() {
  const res = await api.post("/billing/usage/refresh");
  return res.data;
}

// ==================== SECURITY CENTER ====================

export async function getSecurityDashboard() {
  const res = await api.get("/security-center/dashboard");
  return res.data;
}

export async function listSecurityCenterSessions() {
  const res = await api.get("/security-center/sessions");
  return res.data;
}

export async function revokeSecurityCenterSession(sessionId: string) {
  await api.delete(`/security-center/sessions/${sessionId}`);
}

export async function revokeAllSecurityCenterSessions() {
  const res = await api.delete("/security-center/sessions");
  return res.data;
}

export async function listSecurityCenterDevices() {
  const res = await api.get("/security-center/devices");
  return res.data;
}

export async function removeSecurityCenterDevice(deviceId: string) {
  await api.delete(`/security-center/devices/${deviceId}`);
}

export async function getSecurityCenterLoginHistory(limit = 20) {
  const res = await api.get(`/security-center/login-history?limit=${limit}`);
  return res.data;
}

export async function getSecurityCenterAuditTrail(limit = 50) {
  const res = await api.get(`/security-center/audit-trail?limit=${limit}`);
  return res.data;
}

// ==================== ORGANIZATION MANAGEMENT ====================

export async function listOrganizations(): Promise<import("@/types").Organization[]> {
  const res = await api.get("/organizations");
  return res.data;
}

export async function getOrganization(orgId: string): Promise<import("@/types").Organization> {
  const res = await api.get(`/organizations/${orgId}`);
  return res.data;
}

export async function createOrganization(data: {
  name: string;
  slug?: string;
  plan?: string;
}): Promise<import("@/types").Organization> {
  const res = await api.post("/organizations", data);
  return res.data;
}

export async function updateOrganization(
  orgId: string,
  data: Record<string, unknown>
): Promise<import("@/types").Organization> {
  const res = await api.put(`/organizations/${orgId}`, data);
  return res.data;
}

export async function deleteOrganization(orgId: string): Promise<void> {
  await api.delete(`/organizations/${orgId}`);
}

export async function listOrganizationMembers(
  orgId: string
): Promise<import("@/types").OrganizationMember[]> {
  const res = await api.get(`/organizations/${orgId}/members`);
  return res.data;
}

export async function updateMemberRole(
  orgId: string,
  userId: string,
  role: string
): Promise<import("@/types").OrganizationMember> {
  const res = await api.put(`/organizations/${orgId}/members/${userId}/role`, { role });
  return res.data;
}

export async function removeOrganizationMember(
  orgId: string,
  userId: string
): Promise<void> {
  await api.delete(`/organizations/${orgId}/members/${userId}`);
}

export async function getOrganizationStats(
  orgId: string
): Promise<import("@/types").OrganizationStats> {
  const res = await api.get(`/organizations/${orgId}/stats`);
  return res.data;
}

export async function inviteMember(email: string, role = "analyst") {
  const res = await api.post("/invitations", { email, role });
  return res.data;
}

// revokeInvitation and resendInvitation are in the INVITATIONS section above

// ==================== API KEYS V2 ====================

export async function listApiKeysV2() {
  const res = await api.get("/api-keys/v2");
  return res.data;
}

export async function createApiKeyV2(data: {
  name: string;
  scopes?: string[];
  expires_in_days?: number;
}) {
  const res = await api.post("/api-keys/v2", data);
  return res.data;
}

export async function revokeApiKeyV2(keyId: string) {
  await api.delete(`/api-keys/v2/${keyId}`);
}

export async function rotateApiKeyV2(keyId: string) {
  const res = await api.post(`/api-keys/v2/${keyId}/rotate`);
  return res.data;
}

// ==================== PASSKEYS ====================

export async function listPasskeys() {
  const res = await api.get("/passkeys");
  return res.data;
}

export async function registerPasskeyBegin() {
  const res = await api.post("/passkeys/register/begin");
  return res.data;
}

export async function registerPasskeyComplete(data: {
  credential_id: string;
  public_key: string;
  device_name?: string;
  aaguid?: string;
  sign_count?: number;
}) {
  const res = await api.post("/passkeys/register/complete", data);
  return res.data;
}

export async function removePasskey(passkeyId: string) {
  await api.delete(`/passkeys/${passkeyId}`);
}

// ==================== FEATURE MODULES (Phases 1.2 - 4.2) ====================
export * from "./api-asset360";
export * from "./api-changefeed";
export * from "./api-replay";
export * from "./api-collab";
export * from "./api-reports";

// ==================== SHADOW ASSET DETECTION ====================

export interface ShadowSignal {
  type: "shared_ip" | "shared_cert" | "shared_asn";
  with: string[];
  cloud?: boolean | null;
}

export interface ShadowCandidate {
  asset_id: string;
  value: string;
  label: string | null;
  first_seen: string | null;
  confidence: number;
  signals: ShadowSignal[];
  inventory_status: string | null;
}

export interface ShadowListResponse {
  shadows: ShadowCandidate[];
  total: number;
  known_count: number;
  discovered_count: number;
}

export async function listShadowAssets(minConfidence = 0): Promise<ShadowListResponse> {
  const { data } = await api.get("/shadow-assets", {
    params: { min_confidence: minConfidence },
  });
  return data;
}

export async function reviewShadowAsset(
  assetId: string,
  action: "confirm" | "reject" | "investigate",
  note?: string
): Promise<{ asset_id: string; inventory_status: string; confirmed: boolean }> {
  const { data } = await api.post(`/shadow-assets/${assetId}/review`, {
    action,
    note,
  });
  return data;
}

export async function getShadowReviewLog(): Promise<any[]> {
  const { data } = await api.get("/shadow-assets/review-log");
  return data;
}

// ==================== SHODAN-STYLE SEARCH ====================

export interface SearchResult {
  asset_id: string | null;
  subdomain_id: string;
  hostname: string;
  ip_addresses: string[];
  is_alive: boolean;
  asn: string | null;
  org: string | null;
  open_ports: { port: string | number; service: string | null; version: string | null }[];
  port_count: number;
  vulnerability_count: number;
}

export interface SearchResponse {
  query: string;
  total: number;
  results: SearchResult[];
}

export async function searchAssets(query: string, limit = 50): Promise<SearchResponse> {
  const { data } = await api.get("/search", { params: { q: query, limit } });
  return data;
}

// ==================== OSINT INTELLIGENCE ENGINE ====================

export interface OsintResult {
  query: string;
  subdomains: { hostname: string; ips: string[]; sources: string[] }[];
  dns_records: Record<string, string[]>;
  certificates: {
    issuer: string | null;
    subject: string | null;
    san: string[];
    not_before: string | null;
    not_after: string | null;
    serial: string | null;
    source: string | null;
  }[];
  ports: {
    port: number;
    state: string;
    service: string | null;
    banner: string | null;
    tls: boolean;
    title: string | null;
  }[];
  technologies: string[];
  vulnerabilities: {
    cve_id: string;
    description: string;
    severity: string | null;
    cvss: number | null;
    published: string | null;
    is_kev: boolean;
    source: string;
  }[];
  sources_status: Record<string, string>;
  ip_reputation: {
    ip: string;
    country: string | null;
    org: string | null;
    city: string | null;
    loc: string | null;
    hostname: string | null;
    abuse_confidence: number;
    noise?: boolean;
    riot?: boolean;
    classification?: string;
  }[];
  whois: {
    name: string;
    status: string[];
    nameservers: string[];
    registration_date: string | null;
    expiration_date: string | null;
    last_changed: string | null;
    registrar: string | null;
    handle: string | null;
  } | null;
  historical_subdomains: string[];
  reverse_ip: string[];
  email_security: {
    mx_records: { host: string; priority: string }[];
    dmarc_record: string | null;
    dmarc_policy: string | null;
    spf_record: string | null;
    spf_valid: boolean | null;
    dkim_found: string[];
    smtp_banner: string | null;
    emails_found: string[];
  } | null;
  waf_cdn: {
    cdn: string | null;
    waf: string | null;
    server: string | null;
    powered_by: string | null;
    technologies_from_headers: string[];
  } | null;
  security_headers: {
    hsts: string | null;
    csp: string | null;
    x_frame_options: string | null;
    x_content_type_options: string | null;
    x_xss_protection: string | null;
    referrer_policy: string | null;
    permissions_policy: string | null;
    score: number;
    issues: string[];
  } | null;
  sensitive_paths: {
    path: string;
    status: number;
    size: number;
    category: string;
  }[];
  web_fingerprint: {
    title: string | null;
    meta_generator: string | null;
    technologies: string[];
    cookies: string[];
    forms: number;
    external_links: number;
    js_files: string[];
    email_addresses: string[];
    phone_numbers: string[];
    social_links: string[];
  } | null;
  reverse_dns_range: string[];
  risk_score: {
    score: number;
    grade: string;
    findings: { severity: string; detail: string }[];
    exposed_services: number;
    missing_security_headers: number;
    sensitive_paths_found: number;
    ssl_issues: number;
    dns_misconfigs: number;
  } | null;
}

export async function osintLookup(query: string): Promise<OsintResult> {
  const { data } = await api.get("/osint", { params: { q: query }, timeout: 120000 });
  return data;
}

export async function osintImport(query: string): Promise<{
  domain: string;
  imported: Record<string, number>;
  sources_status: Record<string, string>;
}> {
  const { data } = await api.post("/osint/import", null, { params: { q: query } });
  return data;
}

// --- Scanner v2 ---

export interface ScanV2Health {
  status: string;
  engine: string;
  registered_scanners: Array<{
    name: string;
    version: string;
    category: string;
    priority: string;
  }>;
  pipeline_stages: string[];
  version: string;
}

export interface ScanV2Plugin {
  name: string;
  version: string;
  category: string;
  priority: string;
  scanner_class: string;
}

export interface ScanV2Result {
  success: boolean;
  domain: string;
  scan_engine: string;
  subdomains: string[];
  risk_score: Record<string, any>;
  graph: Record<string, any>;
  scanner_status: Record<string, string>;
  pipeline_summary: Record<string, any>;
  errors: Array<Record<string, any>>;
}

export interface MonitorSchedule {
  id: string;
  domain: string;
  interval_hours: number;
  scan_type: string;
  enabled: boolean;
  created_at: string;
  last_run: string | null;
  next_run: string | null;
}

export async function getScannerV2Health(): Promise<ScanV2Health> {
  const { data } = await api.get("/scanner-v2/health");
  return data;
}

export async function getScannerV2Plugins(): Promise<{
  total: number;
  plugins: ScanV2Plugin[];
}> {
  const { data } = await api.get("/scanner-v2/plugins");
  return data;
}

export async function runScanV2(params: {
  domain: string;
  scan_type?: string;
  max_subdomains?: number;
  port_mode?: string;
  timeout?: number;
  included_scanners?: string[];
  excluded_scanners?: string[];
}): Promise<ScanV2Result> {
  const { data } = await api.post("/scanner-v2/scan", params);
  return data;
}

export async function createMonitor(params: {
  domain: string;
  interval_hours?: number;
  scan_type?: string;
}): Promise<MonitorSchedule> {
  const { data } = await api.post("/scanner-v2/monitor", params);
  return data;
}

export async function listMonitors(): Promise<MonitorSchedule[]> {
  const { data } = await api.get("/scanner-v2/monitor");
  return data;
}

export async function deleteMonitor(monitorId: string): Promise<void> {
  await api.delete(`/scanner-v2/monitor/${monitorId}`);
}

export async function analyzeDomain(params: {
  domain: string;
  question: string;
  scan_data?: Record<string, any>;
}): Promise<{
  domain: string;
  question: string;
  answer: string;
  generated_at: string;
}> {
  const { data } = await api.post("/scanner-v2/analyze", params);
  return data;
}
