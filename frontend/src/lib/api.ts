import axios from "axios";
import type {
  Scan,
  ScanDetail,
  Subdomain,
  Port,
  SSLCertificate,
  Technology,
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
export async function createScan(domain: string, scanType = "full"): Promise<Scan> {
  const { data } = await api.post("/scans", { domain, scan_type: scanType });
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

// ==================== SESSIONS ====================

export async function listSessions() {
  const res = await api.get("/sessions");
  return res.data;
}

export async function revokeSession(sessionId: string) {
  await api.delete(`/sessions/${sessionId}`);
}

export async function revokeAllSessions() {
  await api.delete("/sessions");
}

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
