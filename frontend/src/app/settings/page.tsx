"use client";

import { useEffect, useState, useCallback } from "react";
import { QRCodeSVG } from "qrcode.react";
import {
  User,
  Key,
  Bell,
  Shield,
  Save,
  Loader2,
  Copy,
  Trash2,
  Building,
  AlertTriangle,
  Eye,
  EyeOff,
  Check,
  LogOut,
  History,
  Link2,
  ShieldCheck,
  ChevronRight,
} from "lucide-react";
import api, {
  changePassword,
  deleteAccount,
  getUserPreferences,
  updateUserPreferences,
  listApiKeys,
  createApiKey,
  revokeApiKey,
  setup2FA,
  enable2FA,
  disable2FA,
  listSecurityCenterSessions,
  revokeSecurityCenterSession,
  revokeAllSecurityCenterSessions,
  listTrustedDevices,
  revokeTrustedDevice,
  generateRecoveryCodes,
  listRecoveryCodes,
  requestEmailChange,
  getErrorMessage,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { cn } from "@/lib/utils";
import { AuditLogViewer } from "@/components/AuditLogViewer";
import { useChecklistAutoComplete } from "@/components/onboarding/GettingStartedChecklist";
import type { User as UserType } from "@/types";

/* ─── Sidebar navigation structure ─── */
interface NavSection {
  label?: string;
  items: NavItem[];
}

interface NavItem {
  id: string;
  label: string;
  icon: any;
  href?: string;
  danger?: boolean;
}

const navSections: NavSection[] = [
  {
    items: [
      { id: "profile", label: "Public profile", icon: User },
      { id: "organization", label: "Organization", icon: Building, href: "/settings/organization" },
    ],
  },
  {
    label: "Security",
    items: [
      { id: "security", label: "Password & MFA", icon: Shield },
      { id: "security-center", label: "Security Center", icon: ShieldCheck, href: "/security-center" },
      { id: "sessions", label: "Sessions", icon: History },
    ],
  },
  {
    label: "Access",
    items: [
      { id: "api-keys", label: "API Keys", icon: Key },
      { id: "notifications", label: "Notifications", icon: Bell },
      { id: "integrations", label: "Integrations", icon: Link2 },
    ],
  },
  {
    label: "Danger Zone",
    items: [
      { id: "danger", label: "Delete account", icon: AlertTriangle, danger: true },
    ],
  },
];

function SettingsContent() {
  const { user: authUser, logout } = useAuth();
  const router = useRouter();
  const [user, setUser] = useState<UserType | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("profile");
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<"success" | "error" | null>(null);

  // Notifications
  const [notifications, setNotifications] = useState({
    email_notifications: true,
    ssl_expiry_alerts: true,
    weekly_reports: false,
    scan_complete_alerts: true,
  });
  const [savingPrefs, setSavingPrefs] = useState(false);

  // API Keys
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);
  const [creatingKey, setCreatingKey] = useState(false);
  const [revokingKey, setRevokingKey] = useState<string | null>(null);

  // Change Password
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  // Delete Account
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // 2FA
  const [twoFASetup, setTwoFASetup] = useState<{ secret: string; provisioning_uri: string } | null>(null);
  const [twoFACode, setTwoFACode] = useState("");
  const [showManual2FA, setShowManual2FA] = useState(false);

  // Email
  const [editingEmail, setEditingEmail] = useState(false);
  const [emailValue, setEmailValue] = useState("");

  // Sessions
  const [sessions, setSessions] = useState<any[]>([]);
  const [revokingSession, setRevokingSession] = useState<string | null>(null);

  // Trusted Devices
  const [trustedDevices, setTrustedDevices] = useState<any[]>([]);

  // Recovery Codes
  const [recoveryCodes, setRecoveryCodes] = useState<any[]>([]);
  const [newRecoveryCodes, setNewRecoveryCodes] = useState<string[]>([]);
  const [showRecoveryCodes, setShowRecoveryCodes] = useState(false);
  const [generatingCodes, setGeneratingCodes] = useState(false);

  // Email Change
  const [changeEmailPassword, setChangeEmailPassword] = useState("");

  const fetchUser = useCallback(async () => {
    try {
      const response = await api.get("/auth/me");
      setUser(response.data);
      setEmailValue(response.data.email || "");
      if (response.data.preferences) {
        setNotifications(response.data.preferences);
      }
    } catch (error) {
      console.error("Failed to fetch user:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchApiKeys = useCallback(async () => {
    try {
      const keys = await listApiKeys();
      setApiKeys(keys);
    } catch { /* ignore */ }
  }, []);

  const fetchSessions = useCallback(async () => {
    try {
      const data = await listSecurityCenterSessions();
      setSessions(Array.isArray(data) ? data : []);
    } catch { /* ignore */ }
  }, []);

  const fetchTrustedDevices = useCallback(async () => {
    try {
      const data = await listTrustedDevices();
      setTrustedDevices(data);
    } catch { /* ignore */ }
  }, []);

  const fetchRecoveryCodes = useCallback(async () => {
    try {
      const data = await listRecoveryCodes();
      setRecoveryCodes(data);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchUser();
    fetchApiKeys();
    fetchSessions();
    fetchTrustedDevices();
    fetchRecoveryCodes();
  }, [fetchUser, fetchApiKeys, fetchSessions, fetchTrustedDevices, fetchRecoveryCodes]);

  const handleSaveProfile = async () => {
    if (!user) return;
    setSaving(true);
    setSaveMessage(null);
    try {
      const payload: any = { full_name: user.full_name };
      if (editingEmail && emailValue !== user.email) {
        payload.email = emailValue;
      }
      await api.put("/users/me", payload);
      setSaveMessage("success");
      setEditingEmail(false);
      if (emailValue !== user.email) {
        setUser({ ...user, email: emailValue });
      }
    } catch (error: any) {
      console.error("Failed to save profile:", error);
      setSaveMessage("error");
    } finally {
      setSaving(false);
    }
  };

  const handleSavePreferences = async () => {
    setSavingPrefs(true);
    try {
      await updateUserPreferences(notifications);
    } catch { /* ignore */ } finally { setSavingPrefs(false); }
  };

  const handleChangePassword = async () => {
    setPasswordError(null);
    setPasswordSuccess(false);
    if (!currentPassword || !newPassword) { setPasswordError("Both fields are required"); return; }
    if (newPassword.length < 8) { setPasswordError("Password must be at least 8 characters"); return; }
    if (newPassword !== confirmPassword) { setPasswordError("Passwords do not match"); return; }
    if (currentPassword === newPassword) { setPasswordError("New password must be different"); return; }
    setChangingPassword(true);
    try {
      await changePassword(currentPassword, newPassword);
      setPasswordSuccess(true);
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      setTimeout(() => { setShowPasswordForm(false); setPasswordSuccess(false); }, 2000);
    } catch (error: any) {
      setPasswordError(getErrorMessage(error, "Failed to change password"));
    } finally { setChangingPassword(false); }
  };

  const handleCreateApiKey = async () => {
    setCreatingKey(true);
    try {
      const key = await createApiKey(newKeyName || "API Key");
      setCreatedKey(key.key); setNewKeyName(""); await fetchApiKeys();
    } catch { /* ignore */ } finally { setCreatingKey(false); }
  };

  const handleRevokeApiKey = async (keyId: string) => {
    setRevokingKey(keyId);
    try { await revokeApiKey(keyId); setCreatedKey(null); await fetchApiKeys(); }
    catch { /* ignore */ } finally { setRevokingKey(null); }
  };

  const handleCopyKey = (key: string) => { navigator.clipboard.writeText(key); };

  const handleDeleteAccount = async () => {
    setDeleting(true);
    try { await deleteAccount(); logout(); } catch { setDeleting(false); }
  };

  const handleSignOutAll = async () => {
    try { await revokeAllSecurityCenterSessions(); } catch { /* ignore */ } logout();
  };

  const handleRevokeSession = async (sessionId: string) => {
    setRevokingSession(sessionId);
    try { await revokeSecurityCenterSession(sessionId); setSessions(sessions.filter((s: any) => s.id !== sessionId)); }
    catch { /* ignore */ } finally { setRevokingSession(null); }
  };

  const handleRevokeDevice = async (deviceId: string) => {
    try { await revokeTrustedDevice(deviceId); setTrustedDevices(trustedDevices.filter((d: any) => d.id !== deviceId)); }
    catch { /* ignore */ }
  };

  const handleGenerateRecoveryCodes = async () => {
    setGeneratingCodes(true);
    try { const result = await generateRecoveryCodes(); setNewRecoveryCodes(result.codes); setShowRecoveryCodes(true); fetchRecoveryCodes(); }
    catch { /* ignore */ } finally { setGeneratingCodes(false); }
  };

  const handleChangeEmail = async () => {
    if (!changeEmailPassword || !emailValue) return;
    try { await requestEmailChange(emailValue, changeEmailPassword); alert("Verification email sent to new address."); setChangeEmailPassword(""); }
    catch (err: any) { alert(getErrorMessage(err, "Failed to request email change")); }
  };

  const initials = user?.full_name
    ? user.full_name.split(" ").map((n) => n[0]).join("").toUpperCase()
    : user?.email?.[0]?.toUpperCase() || "U";

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1280px] px-6 py-8">
      {/* ─── Header ─── */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Avatar className="h-10 w-10 border border-border/50">
                <AvatarFallback className="bg-gradient-to-br from-[#10B981] to-[#06B6D4] text-xs font-bold text-black">
                  {initials}
                </AvatarFallback>
              </Avatar>
            </div>
            <div>
              <h1 className="text-lg font-semibold text-foreground">
                {user?.full_name || user?.email || "Settings"}
              </h1>
              <p className="text-xs text-muted-foreground">Your personal account</p>
            </div>
          </div>
          {user?.organization_id && (
            <Button variant="outline" size="sm" onClick={() => router.push("/settings/organization")}
              className="text-xs text-muted-foreground border-border/50">
              Go to organization settings
              <ChevronRight className="h-3 w-3 ml-1" />
            </Button>
          )}
        </div>
      </div>

      {/* ─── Main layout: sidebar + content ─── */}
      <div className="flex gap-12">
        {/* ─── Sidebar ─── */}
        <nav className="w-[220px] shrink-0 hidden md:block" aria-label="Settings navigation">
          <div className="sticky top-8 space-y-6">
            {navSections.map((section, si) => (
              <div key={si}>
                {section.label && (
                  <h3 className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                    {section.label}
                  </h3>
                )}
                <div className="space-y-0.5">
                  {section.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = activeTab === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => {
                          if (item.href) {
                            router.push(item.href);
                          } else {
                            setActiveTab(item.id);
                          }
                        }}
                        className={cn(
                          "flex w-full items-center gap-2.5 rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors text-left",
                          isActive
                            ? "bg-[#10B981]/10 text-[#10B981] font-semibold"
                            : item.danger
                              ? "text-red-400/80 hover:text-red-400 hover:bg-red-500/5"
                              : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
                        )}
                        aria-current={isActive ? "page" : undefined}
                      >
                        <Icon className="h-4 w-4 shrink-0 opacity-70" />
                        <span className="truncate">{item.label}</span>
                      </button>
                    );
                  })}
                </div>
                {si < navSections.length - 1 && (
                  <div className="mt-4 border-b border-border/20" />
                )}
              </div>
            ))}
          </div>
        </nav>

        {/* ─── Mobile Tab Selector ─── */}
        <div className="md:hidden fixed bottom-0 left-0 right-0 z-30 border-t border-border/50 bg-card/95 backdrop-blur-sm px-4 py-2">
          <select
            value={activeTab}
            onChange={(e) => {
              const tab = navSections.flatMap(s => s.items).find((t) => t.id === e.target.value);
              if (tab?.href) {
                router.push(tab.href);
              } else {
                setActiveTab(e.target.value);
              }
            }}
            className="flex h-10 w-full rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-sm text-foreground"
          >
            {navSections.flatMap(s => s.items).map((tab) => (
              <option key={tab.id} value={tab.id}>{tab.label}</option>
            ))}
          </select>
        </div>

        {/* ─── Content ─── */}
        <div className="flex-1 min-w-0 pb-16">
          {activeTab === "profile" && (
            <ProfileTab
              user={user!}
              setUser={setUser}
              initials={initials}
              saving={saving}
              saveMessage={saveMessage}
              editingEmail={editingEmail}
              setEditingEmail={setEditingEmail}
              emailValue={emailValue}
              setEmailValue={setEmailValue}
              onSaveProfile={handleSaveProfile}
            />
          )}
          {activeTab === "security" && (
            <SecurityTab
              user={user!}
              setUser={setUser}
              showPasswordForm={showPasswordForm}
              setShowPasswordForm={setShowPasswordForm}
              currentPassword={currentPassword}
              setCurrentPassword={setCurrentPassword}
              newPassword={newPassword}
              setNewPassword={setNewPassword}
              confirmPassword={confirmPassword}
              setConfirmPassword={setConfirmPassword}
              showCurrentPw={showCurrentPw}
              setShowCurrentPw={setShowCurrentPw}
              showNewPw={showNewPw}
              setShowNewPw={setShowNewPw}
              changingPassword={changingPassword}
              passwordError={passwordError}
              passwordSuccess={passwordSuccess}
              handleChangePassword={handleChangePassword}
              twoFASetup={twoFASetup}
              setTwoFASetup={setTwoFASetup}
              twoFACode={twoFACode}
              setTwoFACode={setTwoFACode}
              showManual2FA={showManual2FA}
              setShowManual2FA={setShowManual2FA}
              recoveryCodes={recoveryCodes}
              newRecoveryCodes={newRecoveryCodes}
              setNewRecoveryCodes={setNewRecoveryCodes}
              showRecoveryCodes={showRecoveryCodes}
              setShowRecoveryCodes={setShowRecoveryCodes}
              generatingCodes={generatingCodes}
              handleGenerateRecoveryCodes={handleGenerateRecoveryCodes}
            />
          )}
          {activeTab === "sessions" && (
            <SessionsTab
              sessions={sessions}
              revokingSession={revokingSession}
              handleRevokeSession={handleRevokeSession}
              handleSignOutAll={handleSignOutAll}
              trustedDevices={trustedDevices}
              handleRevokeDevice={handleRevokeDevice}
            />
          )}
          {activeTab === "api-keys" && (
            <ApiKeysTab
              apiKeys={apiKeys}
              createdKey={createdKey}
              newKeyName={newKeyName}
              setNewKeyName={setNewKeyName}
              creatingKey={creatingKey}
              revokingKey={revokingKey}
              handleCreateApiKey={handleCreateApiKey}
              handleRevokeApiKey={handleRevokeApiKey}
              handleCopyKey={handleCopyKey}
            />
          )}
          {activeTab === "notifications" && (
            <NotificationsTab
              notifications={notifications}
              setNotifications={setNotifications}
              savingPrefs={savingPrefs}
              handleSavePreferences={handleSavePreferences}
            />
          )}
          {activeTab === "integrations" && <IntegrationsTab />}
          {activeTab === "danger" && (
            <DangerTab
              showDeleteConfirm={showDeleteConfirm}
              setShowDeleteConfirm={setShowDeleteConfirm}
              deleting={deleting}
              handleDeleteAccount={handleDeleteAccount}
            />
          )}
        </div>
      </div>
    </div>
  );
}

/* ============================================
   SECTION HEADER — consistent across all tabs
   ============================================ */

function SectionHeader({ icon: Icon, title, description, color = "brand" }: {
  icon: any; title: string; description: string; color?: string;
}) {
  const colorMap: Record<string, string> = {
    brand: "bg-[#10B981]/10 text-[#10B981]",
    cyan: "bg-[#06B6D4]/10 text-[#06B6D4]",
    violet: "bg-[#7A5CFF]/10 text-[#7A5CFF]",
    amber: "bg-amber-400/10 text-amber-400",
    red: "bg-red-500/10 text-red-400",
    green: "bg-emerald-500/10 text-emerald-400",
    pink: "bg-pink-400/10 text-pink-400",
    info: "bg-sky-400/10 text-sky-400",
  };
  return (
    <div className="mb-6">
      <div className="flex items-center gap-3 mb-1">
        <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", colorMap[color] || colorMap.brand)}>
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-foreground">{title}</h2>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
    </div>
  );
}

/* ============================================
   PROFILE TAB
   ============================================ */

function ProfileTab({ user, setUser, initials, saving, saveMessage, editingEmail, setEditingEmail, emailValue, setEmailValue, onSaveProfile }: any) {
  return (
    <div>
      <SectionHeader icon={User} title="Public profile" description="Your profile information visible to others." color="brand" />

      <div className="space-y-6">
        {/* Profile Picture + Name */}
        <div className="flex items-start gap-6">
          <div className="shrink-0">
            <div className="relative group">
              <div className="absolute -inset-1 rounded-full bg-gradient-to-r from-[#10B981] to-[#06B6D4] opacity-20 blur-sm group-hover:opacity-40 transition-opacity" />
              <Avatar className="relative h-20 w-20 border-2 border-border/50">
                <AvatarFallback className="bg-gradient-to-br from-[#10B981] to-[#06B6D4] text-xl font-bold text-black">
                  {initials}
                </AvatarFallback>
              </Avatar>
            </div>
            <p className="text-[10px] text-muted-foreground text-center mt-2">Profile picture</p>
          </div>
          <div className="flex-1 space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Name</label>
              <Input
                value={user?.full_name || ""}
                onChange={(e) => setUser({ ...user!, full_name: e.target.value })}
                className="bg-muted/30 border-border/50 h-9"
                placeholder="Your name"
              />
              <p className="text-[11px] text-muted-foreground">
                Your name may appear around the platform where you contribute or are mentioned.
              </p>
            </div>
          </div>
        </div>

        <div className="border-b border-border/20" />

        {/* Email */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">Public email</label>
          {editingEmail ? (
            <div className="flex gap-2">
              <Input value={emailValue} onChange={(e) => setEmailValue(e.target.value)}
                className="bg-muted/30 border-border/50 h-9 flex-1" />
              <Button size="sm" variant="outline" onClick={() => setEditingEmail(false)}
                className="h-9 border-border/50">Cancel</Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Input value={user?.email || ""} disabled
                className="bg-muted/20 border-border/50 h-9 opacity-60 max-w-[320px]" />
              <button onClick={() => { setEditingEmail(true); setEmailValue(user?.email || ""); }}
                className="text-xs text-[#10B981] hover:text-[#10B981]/80 transition-colors font-medium">
                Edit
              </button>
            </div>
          )}
        </div>

        {/* Role + Member Since */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Role</label>
            <div className="h-9 flex items-center rounded-md border border-border/50 bg-muted/20 px-3">
              <Badge variant="secondary" className="capitalize text-xs">{user?.role || "member"}</Badge>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Member since</label>
            <div className="h-9 flex items-center rounded-md border border-border/50 bg-muted/20 px-3">
              <span className="text-sm text-muted-foreground">
                {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
              </span>
            </div>
          </div>
        </div>

        <div className="border-b border-border/20" />

        {/* Save */}
        <div className="flex items-center gap-3">
          <Button onClick={onSaveProfile} disabled={saving}
            className="bg-[#10B981] hover:bg-[#10B981]/90 text-black font-medium h-9 px-5">
            {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
            Save changes
          </Button>
          {saveMessage === "success" && (
            <span className="flex items-center gap-1.5 text-sm text-emerald-400">
              <Check className="h-4 w-4" /> Saved
            </span>
          )}
          {saveMessage === "error" && (
            <span className="text-sm text-red-400">Failed to save. Try again.</span>
          )}
        </div>
      </div>
    </div>
  );
}

/* ============================================
   SECURITY TAB
   ============================================ */

function SecurityTab(props: any) {
  const {
    user, setUser, showPasswordForm, setShowPasswordForm,
    currentPassword, setCurrentPassword, newPassword, setNewPassword,
    confirmPassword, setConfirmPassword, showCurrentPw, setShowCurrentPw,
    showNewPw, setShowNewPw, changingPassword, passwordError, passwordSuccess,
    handleChangePassword, twoFASetup, setTwoFASetup, twoFACode, setTwoFACode,
    showManual2FA, setShowManual2FA,
    recoveryCodes, newRecoveryCodes, setNewRecoveryCodes, showRecoveryCodes, setShowRecoveryCodes,
    generatingCodes, handleGenerateRecoveryCodes,
  } = props;

  return (
    <div className="space-y-10">
      {/* Password */}
      <div>
        <SectionHeader icon={Shield} title="Password and authentication" description="Manage your password and two-factor authentication." color="green" />
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-border/30 bg-muted/10 p-4">
            <div>
              <p className="text-sm font-medium">Password</p>
              <p className="text-xs text-muted-foreground">
                {passwordSuccess ? "Password changed successfully" : "Last changed: —"}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => setShowPasswordForm(!showPasswordForm)}
              className="h-8 border-border/50 text-xs">
              {showPasswordForm ? "Cancel" : "Change password"}
            </Button>
          </div>

          {showPasswordForm && (
            <div className="space-y-3 rounded-lg border border-border/30 bg-muted/10 p-4 ml-0">
              <div className="space-y-2">
                <label className="text-xs font-medium">Current password</label>
                <div className="relative">
                  <Input type={showCurrentPw ? "text" : "password"} value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="bg-muted/30 border-border/50 h-9 pr-10" placeholder="Enter current password" />
                  <button type="button" onClick={() => setShowCurrentPw(!showCurrentPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showCurrentPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium">New password</label>
                <div className="relative">
                  <Input type={showNewPw ? "text" : "password"} value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="bg-muted/30 border-border/50 h-9 pr-10" placeholder="Enter new password" />
                  <button type="button" onClick={() => setShowNewPw(!showNewPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showNewPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium">Confirm new password</label>
                <Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                  className="bg-muted/30 border-border/50 h-9" placeholder="Confirm new password" />
              </div>
              {passwordError && <p className="text-xs text-red-400">{passwordError}</p>}
              <Button size="sm" onClick={handleChangePassword} disabled={changingPassword}
                className="bg-[#10B981] hover:bg-[#10B981]/90 text-black h-8 text-xs font-medium">
                {changingPassword ? <Loader2 className="h-3 w-3 animate-spin mr-1.5" /> : null}
                Update password
              </Button>
            </div>
          )}
        </div>
      </div>

      <div className="border-b border-border/20" />

      {/* 2FA */}
      <div>
        <SectionHeader icon={ShieldCheck} title="Two-factor authentication" description="Add an extra layer of security to your account." color="cyan" />
        <div className="rounded-lg border border-border/30 bg-muted/10 p-4">
          {user?.totp_enabled ? (
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-emerald-400">2FA is enabled</p>
                <p className="text-xs text-muted-foreground">Your account is protected with TOTP authentication.</p>
              </div>
              <Button variant="outline" size="sm" onClick={async () => {
                const code = prompt("Enter your TOTP code to disable 2FA:");
                if (code) { try { await disable2FA(code); setUser({ ...user!, totp_enabled: false }); } catch { alert("Invalid code"); } }
              }} className="h-8 border-border/50 text-xs">Disable</Button>
            </div>
          ) : twoFASetup ? (
            <div className="space-y-3">
              <p className="text-sm font-medium">Scan this QR code with your authenticator app:</p>
              <div className="rounded-lg bg-card/90 backdrop-blur-sm p-4 inline-block border border-border/30">
                <QRCodeSVG value={twoFASetup.provisioning_uri} size={180} level="M" includeMargin />
              </div>
              <div className="text-xs text-muted-foreground">
                <button type="button" onClick={() => setShowManual2FA((v: boolean) => !v)}
                  className="underline underline-offset-2 hover:text-foreground">
                  Can&apos;t scan? Enter manually
                </button>
                {showManual2FA && (
                  <div className="mt-2 rounded-lg border border-border/30 bg-muted/20 p-3 space-y-1">
                    <p>Secret: <span className="font-mono break-all">{twoFASetup.secret}</span></p>
                    <p className="text-[10px] break-all opacity-70">{twoFASetup.provisioning_uri}</p>
                  </div>
                )}
              </div>
              <div className="flex gap-2 max-w-xs">
                <input value={twoFACode} onChange={(e) => setTwoFACode(e.target.value)}
                  placeholder="Enter 6-digit code" maxLength={6}
                  className="h-9 flex-1 rounded-lg border border-border/50 bg-muted/30 px-3 text-sm outline-none" />
                <Button size="sm" onClick={async () => {
                  try { await enable2FA(twoFACode); setUser({ ...user!, totp_enabled: true }); setTwoFASetup(null); setTwoFACode(""); setShowManual2FA(false); }
                  catch { alert("Invalid code"); }
                }} className="bg-[#10B981] hover:bg-[#10B981]/90 text-black h-9 text-xs font-medium">Verify</Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Not enabled</p>
                <p className="text-xs text-muted-foreground">Protect your account with an authenticator app.</p>
              </div>
              <Button variant="outline" size="sm" onClick={async () => {
                try { const setup = await setup2FA(); setTwoFASetup(setup); } catch { /* ignore */ }
              }} className="h-8 border-border/50 text-xs">Enable 2FA</Button>
            </div>
          )}
        </div>
      </div>

      <div className="border-b border-border/20" />

      {/* Recovery Codes */}
      <div>
        <SectionHeader icon={Key} title="Recovery codes" description="Backup codes for account access when you can't use 2FA." color="pink" />
        <div className="rounded-lg border border-border/30 bg-muted/10 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {recoveryCodes.length > 0
                ? `${recoveryCodes.filter((c: any) => c.is_active).length} active recovery codes`
                : "No recovery codes. Generate a set before you enable MFA."}
            </p>
            <Button variant="outline" size="sm" onClick={handleGenerateRecoveryCodes} disabled={generatingCodes}
              className="h-8 border-border/50 text-xs">
              {generatingCodes ? <Loader2 className="h-3 w-3 animate-spin mr-1.5" /> : <Key className="h-3 w-3 mr-1.5" />}
              Generate new codes
            </Button>
          </div>
          {newRecoveryCodes.length > 0 && showRecoveryCodes ? (
            <div className="space-y-3">
              <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                <p className="text-xs text-amber-400 font-medium">Save these codes somewhere safe. Each code can only be used once.</p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {newRecoveryCodes.map((code: string, i: number) => (
                  <div key={i} className="font-mono text-sm bg-muted/30 px-3 py-2 rounded border border-border/30">{code}</div>
                ))}
              </div>
              <Button variant="outline" size="sm" onClick={() => { setShowRecoveryCodes(false); setNewRecoveryCodes([]); }}
                className="h-8 border-border/50 text-xs">Done</Button>
            </div>
          ) : recoveryCodes.length > 0 && (
            <Button variant="outline" size="sm" onClick={() => setShowRecoveryCodes(true)}
              className="h-8 border-border/50 text-xs">View codes</Button>
          )}
        </div>
      </div>

      <div className="border-b border-border/20" />

      {/* Audit Logs */}
      <div>
        <SectionHeader icon={History} title="Audit logs" description="Track all account activity and changes." color="info" />
        <div className="rounded-lg border border-border/30 bg-muted/10 p-4">
          <AuditLogViewer />
        </div>
      </div>
    </div>
  );
}

/* ============================================
   SESSIONS TAB
   ============================================ */

function SessionsTab({ sessions, revokingSession, handleRevokeSession, handleSignOutAll, trustedDevices, handleRevokeDevice }: any) {
  return (
    <div className="space-y-10">
      {/* Active Sessions */}
      <div>
        <SectionHeader icon={History} title="Active sessions" description="Manage your login sessions across devices." color="info" />
        <div className="rounded-lg border border-border/30 overflow-hidden">
          {sessions.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">No active sessions.</div>
          ) : (
            <div className="divide-y divide-border/20">
              {sessions.map((session: any) => (
                <div key={session.id} className="flex items-center justify-between px-4 py-3 hover:bg-muted/20 transition-colors">
                  <div>
                    <p className="text-sm font-medium">{session.browser} on {session.os}</p>
                    <p className="text-xs text-muted-foreground">
                      IP: <span className="font-mono">{session.ip_address}</span> &middot; Last active: {new Date(session.last_activity).toLocaleString()}
                    </p>
                  </div>
                  <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-400 hover:bg-red-500/10 h-8 text-xs"
                    onClick={() => handleRevokeSession(session.id)} disabled={revokingSession === session.id}>
                    {revokingSession === session.id ? <Loader2 className="h-3 w-3 animate-spin" /> : "Revoke"}
                  </Button>
                </div>
              ))}
            </div>
          )}
          {sessions.length > 1 && (
            <div className="border-t border-border/20 px-4 py-2">
              <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-400 hover:bg-red-500/10 h-8 text-xs"
                onClick={handleSignOutAll}>
                <LogOut className="h-3 w-3 mr-1.5" />
                Sign out all other sessions
              </Button>
            </div>
          )}
        </div>
      </div>

      <div className="border-b border-border/20" />

      {/* Trusted Devices */}
      <div>
        <SectionHeader icon={Shield} title="Trusted devices" description="Devices that skip 2FA verification." color="amber" />
        <div className="rounded-lg border border-border/30 overflow-hidden">
          {trustedDevices.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">No trusted devices.</div>
          ) : (
            <div className="divide-y divide-border/20">
              {trustedDevices.map((device: any) => (
                <div key={device.id} className="flex items-center justify-between px-4 py-3 hover:bg-muted/20 transition-colors">
                  <div>
                    <p className="text-sm font-medium">{device.browser} on {device.os}</p>
                    <p className="text-xs text-muted-foreground">
                      IP: <span className="font-mono">{device.ip_address}</span> &middot; Trusted: {new Date(device.trusted_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-400 hover:bg-red-500/10 h-8 text-xs"
                    onClick={() => handleRevokeDevice(device.id)}>
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ============================================
   API KEYS TAB
   ============================================ */

function ApiKeysTab({ apiKeys, createdKey, newKeyName, setNewKeyName, creatingKey, revokingKey, handleCreateApiKey, handleRevokeApiKey, handleCopyKey }: any) {
  return (
    <div>
      <SectionHeader icon={Key} title="API keys" description="Programmatic access to the platform. Keep them secret." color="amber" />

      <div className="space-y-4">
        {createdKey && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
            <p className="text-xs font-medium text-emerald-400 mb-2">
              Your new API key (copy it now, it won&apos;t be shown again):
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs font-mono text-foreground bg-muted/30 rounded px-2 py-1.5 overflow-x-auto">{createdKey}</code>
              <button onClick={() => handleCopyKey(createdKey)} className="text-muted-foreground hover:text-foreground transition-colors shrink-0">
                <Copy className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        <div className="rounded-lg border border-border/30 overflow-hidden">
          {apiKeys.length > 0 ? (
            <div className="divide-y divide-border/20">
              {apiKeys.map((key: any) => (
                <div key={key.id} className="flex items-center gap-3 px-4 py-3 hover:bg-muted/20 transition-colors">
                  <Key className="h-4 w-4 text-muted-foreground/50 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{key.name || "API Key"}</p>
                    <p className="text-xs text-muted-foreground">
                      Created {key.created_at ? new Date(key.created_at).toLocaleDateString() : "—"}
                    </p>
                  </div>
                  <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-400 hover:bg-red-500/10 shrink-0 h-8 text-xs"
                    onClick={() => handleRevokeApiKey(key.id)} disabled={revokingKey === key.id}>
                    {revokingKey === key.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                  </Button>
                </div>
              ))}
            </div>
          ) : !createdKey && (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">No keys created.</div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Input value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)} placeholder="Key name (optional)"
            className="bg-muted/30 border-border/50 h-9 max-w-[200px]" />
          <Button variant="outline" size="sm" onClick={handleCreateApiKey} disabled={creatingKey}
            className="h-9 border-border/50 text-xs">
            {creatingKey ? <Loader2 className="h-3 w-3 animate-spin mr-1.5" /> : <Key className="h-3 w-3 mr-1.5" />}
            Create new key
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ============================================
   NOTIFICATIONS TAB
   ============================================ */

function NotificationsTab({ notifications, setNotifications, savingPrefs, handleSavePreferences }: any) {
  const { markComplete } = useChecklistAutoComplete();
  const [notifPrefs, setNotifPrefs] = useState<any[]>([]);
  const [loadingPrefs, setLoadingPrefs] = useState(true);

  useEffect(() => {
    import("@/lib/api").then(({ getNotificationPreferences }) => {
      getNotificationPreferences().then(setNotifPrefs).catch(() => {}).finally(() => setLoadingPrefs(false));
    });
  }, []);

  const togglePref = async (type: string, channel: "in_app" | "email") => {
    const current = notifPrefs.find((p) => p.notification_type === type);
    const updates = channel === "in_app"
      ? { in_app_enabled: !current?.in_app_enabled }
      : { email_enabled: !current?.email_enabled };
    setNotifPrefs((prev) =>
      prev.map((p) => p.notification_type === type ? { ...p, ...updates } : p)
    );
    try {
      const { updateNotificationPreference } = await import("@/lib/api");
      await updateNotificationPreference(type, updates);
      markComplete("notifications");
    } catch {
      setNotifPrefs((prev) =>
        prev.map((p) => p.notification_type === type ? {
          ...p,
          [channel === "in_app" ? "in_app_enabled" : "email_enabled"]:
            channel === "in_app" ? current?.in_app_enabled : current?.email_enabled,
        } : p)
      );
    }
  };

  const notifTypes = [
    { type: "scan_completed", label: "Scan Completed", category: "Scans" },
    { type: "scan_failed", label: "Scan Failed", category: "Scans" },
    { type: "new_shadow_asset", label: "New Shadow Asset", category: "Assets" },
    { type: "new_finding_critical", label: "Critical Finding", category: "Findings" },
    { type: "new_finding_high", label: "High Finding", category: "Findings" },
    { type: "new_finding_medium", label: "Medium Finding", category: "Findings" },
    { type: "new_cve_match", label: "CVE Match", category: "Findings" },
    { type: "ssl_expiring", label: "SSL Expiring", category: "Certificates" },
    { type: "new_login", label: "New Login", category: "Security" },
    { type: "password_changed", label: "Password Changed", category: "Security" },
    { type: "email_changed", label: "Email Changed", category: "Security" },
    { type: "weekly_digest", label: "Weekly Digest", category: "Reports" },
  ];

  const categories = Array.from(new Set(notifTypes.map((t) => t.category)));

  return (
    <div>
      <SectionHeader icon={Bell} title="Notification preferences" description="Control in-app and email notifications per category." color="violet" />

      {loadingPrefs ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="rounded-lg border border-border/30 overflow-hidden">
          {categories.map((cat) => (
            <div key={cat}>
              <div className="px-4 py-2 bg-muted/30 border-b border-border/20">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">{cat}</p>
              </div>
              <div className="divide-y divide-border/20">
                {notifTypes.filter((t) => t.category === cat).map((item) => {
                  const pref = notifPrefs.find((p) => p.notification_type === item.type);
                  return (
                    <div key={item.type} className="flex items-center justify-between px-4 py-3 hover:bg-muted/10 transition-colors">
                      <p className="text-sm">{item.label}</p>
                      <div className="flex gap-4">
                        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <span>In-app</span>
                          <button
                            onClick={() => togglePref(item.type, "in_app")}
                            className={cn(
                              "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
                              pref?.in_app_enabled ? "bg-[#10B981]" : "bg-muted"
                            )}
                            role="switch"
                            aria-checked={pref?.in_app_enabled}
                          >
                            <span className={cn(
                              "inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform shadow-sm",
                              pref?.in_app_enabled ? "translate-x-[18px]" : "translate-x-[2px]"
                            )} />
                          </button>
                        </label>
                        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <span>Email</span>
                          <button
                            onClick={() => togglePref(item.type, "email")}
                            className={cn(
                              "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
                              pref?.email_enabled ? "bg-[#10B981]" : "bg-muted"
                            )}
                            role="switch"
                            aria-checked={pref?.email_enabled}
                          >
                            <span className={cn(
                              "inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform shadow-sm",
                              pref?.email_enabled ? "translate-x-[18px]" : "translate-x-[2px]"
                            )} />
                          </button>
                        </label>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ============================================
   INTEGRATIONS TAB
   ============================================ */

function IntegrationsTab() {
  return (
    <div>
      <SectionHeader icon={Link2} title="Integrations" description="Connect with third-party services." color="info" />
      <div className="rounded-lg border border-border/30 bg-muted/10 p-12 text-center">
        <Link2 className="h-10 w-10 text-muted-foreground/20 mx-auto mb-3" />
        <p className="text-sm text-muted-foreground mb-1">Integrations coming soon</p>
        <p className="text-xs text-muted-foreground/50">Connect with Slack, Jira, PagerDuty, and more.</p>
      </div>
    </div>
  );
}

/* ============================================
   DANGER TAB
   ============================================ */

function DangerTab({ showDeleteConfirm, setShowDeleteConfirm, deleting, handleDeleteAccount }: any) {
  return (
    <div>
      <SectionHeader icon={AlertTriangle} title="Danger zone" description="Irreversible actions that affect your account." color="red" />

      <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-red-400">Delete account</p>
            <p className="text-xs text-red-400/60">Permanently delete your account and all associated data</p>
          </div>
          {!showDeleteConfirm ? (
            <Button variant="destructive" size="sm"
              className="bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 h-8 text-xs"
              onClick={() => setShowDeleteConfirm(true)}>
              <Trash2 className="h-3 w-3 mr-1.5" />
              Delete account
            </Button>
          ) : (
            <div className="flex items-center gap-2">
              <Button variant="destructive" size="sm" className="bg-red-500 text-white hover:bg-red-600 h-8 text-xs"
                onClick={handleDeleteAccount} disabled={deleting}>
                {deleting ? <Loader2 className="h-3 w-3 animate-spin mr-1.5" /> : null}
                Yes, delete
              </Button>
              <Button variant="outline" size="sm" onClick={() => setShowDeleteConfirm(false)}
                className="h-8 border-border/50 text-xs">Cancel</Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <ProtectedRoute>
      <SettingsContent />
    </ProtectedRoute>
  );
}
