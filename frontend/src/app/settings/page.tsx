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
  CreditCard,
  ShieldCheck,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
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
import { PageHeader } from "@/components/common/PageHeader";
import { cn } from "@/lib/utils";
import { AuditLogViewer } from "@/components/AuditLogViewer";
import type { User as UserType } from "@/types";

const settingsTabs = [
  { id: "profile", label: "Profile", icon: User },
  { id: "billing", label: "Billing", icon: CreditCard, href: "/billing" },
  { id: "organization", label: "Organization", icon: Building, href: "/settings/organization" },
  { id: "security", label: "Security", icon: Shield },
  { id: "security-center", label: "Security Center", icon: ShieldCheck, href: "/security-center" },
  { id: "api-keys", label: "API Keys", icon: Key },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "integrations", label: "Integrations", icon: Link2 },
  { id: "danger", label: "Danger Zone", icon: AlertTriangle },
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
      <div className="page-container-sm">
        <div className="py-6 space-y-4">
          <div className="h-10 w-40 skeleton" />
          <div className="h-4 w-64 skeleton" />
          <div className="flex gap-6 mt-6">
            <div className="w-48 h-64 skeleton rounded-xl" />
            <div className="flex-1 space-y-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-48 rounded-xl skeleton" />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container-sm">
      <div className="py-6">
        <PageHeader
          title="Settings"
          description="Manage your account, preferences, and security."
          icon={<Shield className="h-5 w-5" />}
          breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "Settings" }]}
        />

        <div className="mt-6 flex gap-6">
          {/* Tab Navigation */}
          <nav className="w-48 shrink-0 hidden md:block" aria-label="Settings navigation">
            <div className="space-y-0.5">
              {settingsTabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => {
                      if (tab.href) {
                        router.push(tab.href);
                      } else {
                        setActiveTab(tab.id);
                      }
                    }}
                    className={cn(
                      "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200 text-left",
                      isActive
                        ? "bg-brand/10 text-brand"
                        : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                    )}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="truncate">{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </nav>

          {/* Mobile Tab Selector */}
          <div className="md:hidden mb-4 -mx-4 px-4">
            <select
              value={activeTab}
              onChange={(e) => {
                const tab = settingsTabs.find((t) => t.id === e.target.value);
                if (tab?.href) {
                  router.push(tab.href);
                } else {
                  setActiveTab(e.target.value);
                }
              }}
              className="flex h-10 w-full rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-sm text-foreground"
            >
              {settingsTabs.map((tab) => (
                <option key={tab.id} value={tab.id}>{tab.label}</option>
              ))}
            </select>
          </div>

          {/* Tab Content */}
          <div className="flex-1 min-w-0">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
              >
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
                {activeTab === "organization" && (
                  <OrganizationTab user={user} />
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
                    sessions={sessions}
                    revokingSession={revokingSession}
                    handleRevokeSession={handleRevokeSession}
                    handleSignOutAll={handleSignOutAll}
                    trustedDevices={trustedDevices}
                    handleRevokeDevice={handleRevokeDevice}
                    recoveryCodes={recoveryCodes}
                    newRecoveryCodes={newRecoveryCodes}
                    setNewRecoveryCodes={setNewRecoveryCodes}
                    showRecoveryCodes={showRecoveryCodes}
                    setShowRecoveryCodes={setShowRecoveryCodes}
                    generatingCodes={generatingCodes}
                    handleGenerateRecoveryCodes={handleGenerateRecoveryCodes}
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
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================
   TAB COMPONENTS
   ============================================ */

function ProfileTab({ user, setUser, initials, saving, saveMessage, editingEmail, setEditingEmail, emailValue, setEmailValue, onSaveProfile }: any) {
  return (
    <div className="space-y-6">
      <div className="settings-card">
        <div className="settings-card-header">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand/10">
            <User className="h-4 w-4 text-brand" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">Profile</h2>
            <p className="text-xs text-muted-foreground">Your account information</p>
          </div>
        </div>
        <div className="settings-card-body">
          <div className="flex items-center gap-5 mb-6">
            <div className="relative">
              <div className="absolute -inset-1 rounded-full bg-gradient-to-r gradient-brand opacity-60 blur-sm" />
              <Avatar className="relative h-20 w-20 border-2 border-card">
                <AvatarFallback className="bg-gradient-to-br gradient-brand text-xl font-bold text-brand-foreground">
                  {initials}
                </AvatarFallback>
              </Avatar>
            </div>
            <div className="space-y-1">
              <p className="text-lg font-semibold text-foreground">{user?.full_name || "No name set"}</p>
              <p className="text-sm text-muted-foreground">{user?.email}</p>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="secondary" className="capitalize text-xs">{user?.role || "member"}</Badge>
                <span className="text-xs text-muted-foreground">
                  Member since {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
                </span>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Full Name</label>
              <Input
                value={user?.full_name || ""}
                onChange={(e) => setUser({ ...user!, full_name: e.target.value })}
                className="bg-muted/30 border-border/50"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">Email</label>
                {!editingEmail && (
                  <button onClick={() => { setEditingEmail(true); setEmailValue(user?.email || ""); }}
                    className="text-xs text-brand hover:text-brand/80 transition-colors">Edit</button>
                )}
              </div>
              {editingEmail ? (
                <div className="flex gap-2">
                  <Input value={emailValue} onChange={(e) => setEmailValue(e.target.value)} className="bg-muted/30 border-border/50 flex-1" />
                  <Button size="sm" variant="outline" onClick={() => setEditingEmail(false)}>Cancel</Button>
                </div>
              ) : (
                <Input value={user?.email || ""} disabled className="bg-muted/20 border-border/50 opacity-60" />
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 mt-6">
            <Button onClick={onSaveProfile} disabled={saving} className="bg-gradient-to-r gradient-brand hover:from-primary/90 hover:to-cyan-500/90 shadow-lg shadow-primary/25">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save Changes
            </Button>
            {saveMessage === "success" && (
              <span className="flex items-center gap-1.5 text-sm text-success"><Check className="h-4 w-4" /> Saved</span>
            )}
            {saveMessage === "error" && (
              <span className="text-sm text-destructive">Failed to save. Try again.</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function OrganizationTab({ user }: { user: UserType | null }) {
  return (
    <div className="settings-card">
      <div className="settings-card-header">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-400/10">
          <Building className="h-4 w-4 text-cyan-400" />
        </div>
        <div>
          <h2 className="text-sm font-semibold">Organization</h2>
          <p className="text-xs text-muted-foreground">Team and billing details</p>
        </div>
      </div>
      <div className="settings-card-body">
        {user?.organization_id ? (
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-lg border border-border/30 bg-muted/20 p-4">
              <p className="text-xs text-muted-foreground mb-1">Plan</p>
              <Badge variant="info" className="text-xs">Professional</Badge>
            </div>
            <div className="rounded-lg border border-border/30 bg-muted/20 p-4">
              <p className="text-xs text-muted-foreground mb-1">Organization ID</p>
              <p className="text-xs font-mono truncate">{user.organization_id}</p>
            </div>
            <div className="rounded-lg border border-border/30 bg-muted/20 p-4">
              <p className="text-xs text-muted-foreground mb-1">Scans</p>
              <p className="text-sm font-semibold">Unlimited</p>
            </div>
          </div>
        ) : (
          <div className="text-center py-8">
            <Building className="h-10 w-10 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-sm text-muted-foreground mb-3">You are not part of any organization.</p>
            <Button variant="outline" size="sm">Create Organization</Button>
          </div>
        )}
      </div>
    </div>
  );
}

function SecurityTab(props: any) {
  const {
    user, setUser, showPasswordForm, setShowPasswordForm,
    currentPassword, setCurrentPassword, newPassword, setNewPassword,
    confirmPassword, setConfirmPassword, showCurrentPw, setShowCurrentPw,
    showNewPw, setShowNewPw, changingPassword, passwordError, passwordSuccess,
    handleChangePassword, twoFASetup, setTwoFASetup, twoFACode, setTwoFACode,
    showManual2FA, setShowManual2FA, sessions, revokingSession,
    handleRevokeSession, handleSignOutAll, trustedDevices, handleRevokeDevice,
    recoveryCodes, newRecoveryCodes, setNewRecoveryCodes, showRecoveryCodes, setShowRecoveryCodes,
    generatingCodes, handleGenerateRecoveryCodes,
  } = props;

  return (
    <div className="space-y-6">
      {/* Password */}
      <div className="settings-card">
        <div className="settings-card-header">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-success/10">
            <Shield className="h-4 w-4 text-success" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">Password</h2>
            <p className="text-xs text-muted-foreground">Account protection settings</p>
          </div>
        </div>
        <div className="settings-card-body">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Password</p>
              <p className="text-xs text-muted-foreground">
                {passwordSuccess ? "Password changed successfully" : "Last changed: —"}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => setShowPasswordForm(!showPasswordForm)}>
              {showPasswordForm ? "Cancel" : "Change Password"}
            </Button>
          </div>
          {showPasswordForm && (
            <div className="mt-4 space-y-3 rounded-lg border border-border/30 bg-muted/20 p-4">
              <div className="space-y-2">
                <label className="text-xs font-medium">Current Password</label>
                <div className="relative">
                  <Input type={showCurrentPw ? "text" : "password"} value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)} className="bg-muted/30 border-border/50 pr-10" placeholder="Enter current password" />
                  <button type="button" onClick={() => setShowCurrentPw(!showCurrentPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showCurrentPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium">New Password</label>
                <div className="relative">
                  <Input type={showNewPw ? "text" : "password"} value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)} className="bg-muted/30 border-border/50 pr-10" placeholder="Enter new password" />
                  <button type="button" onClick={() => setShowNewPw(!showNewPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showNewPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium">Confirm New Password</label>
                <Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                  className="bg-muted/30 border-border/50" placeholder="Confirm new password" />
              </div>
              {passwordError && <p className="text-xs text-destructive">{passwordError}</p>}
              <Button size="sm" onClick={handleChangePassword} disabled={changingPassword} className="bg-gradient-to-r gradient-brand">
                {changingPassword ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : null}
                Update Password
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* 2FA */}
      <div className="settings-card">
        <div className="settings-card-header">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-success/10">
            <Shield className="h-4 w-4 text-success" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">Two-Factor Authentication</h2>
            <p className="text-xs text-muted-foreground">Add an extra layer of security</p>
          </div>
        </div>
        <div className="settings-card-body">
          {user?.totp_enabled ? (
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-success">2FA is enabled</p>
                <p className="text-xs text-muted-foreground">Your account is protected with TOTP authentication.</p>
              </div>
              <Button variant="outline" size="sm" onClick={async () => {
                const code = prompt("Enter your TOTP code to disable 2FA:");
                if (code) { try { await disable2FA(code); setUser({ ...user!, totp_enabled: false }); } catch { alert("Invalid code"); } }
              }}>Disable</Button>
            </div>
          ) : twoFASetup ? (
            <div className="space-y-3">
              <p className="text-sm font-medium">Scan this QR code with your authenticator app:</p>
              <div className="rounded-lg bg-card/90 backdrop-blur-sm p-4 inline-block">
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
                }}>Verify</Button>
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
              }}>Enable 2FA</Button>
            </div>
          )}
        </div>
      </div>

      {/* Sessions */}
      <div className="settings-card">
        <div className="settings-card-header">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-info/10">
            <History className="h-4 w-4 text-info" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-semibold">Active Sessions</h2>
            <p className="text-xs text-muted-foreground">Manage your login sessions</p>
          </div>
          {sessions.length > 1 && (
            <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={handleSignOutAll}>
              Revoke All Others
            </Button>
          )}
        </div>
        <div className="divide-y divide-border/30">
          {sessions.length === 0 ? (
            <div className="px-6 py-4 text-sm text-muted-foreground">No active sessions.</div>
          ) : sessions.map((session: any) => (
            <div key={session.id} className="flex items-center justify-between px-6 py-3">
              <div>
                <p className="text-sm font-medium">{session.browser} on {session.os}</p>
                <p className="text-xs text-muted-foreground">
                  IP: <span className="font-mono">{session.ip_address}</span> &middot; Last active: {new Date(session.last_activity).toLocaleString()}
                </p>
              </div>
              <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive"
                onClick={() => handleRevokeSession(session.id)} disabled={revokingSession === session.id}>
                {revokingSession === session.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Revoke"}
              </Button>
            </div>
          ))}
        </div>
      </div>

      {/* Trusted Devices */}
      <div className="settings-card">
        <div className="settings-card-header">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-400/10">
            <Shield className="h-4 w-4 text-amber-400" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">Trusted Devices</h2>
            <p className="text-xs text-muted-foreground">Devices that skip 2FA verification</p>
          </div>
        </div>
        <div className="divide-y divide-border/30">
          {trustedDevices.length === 0 ? (
            <div className="px-6 py-4 text-sm text-muted-foreground">No trusted devices.</div>
          ) : trustedDevices.map((device: any) => (
            <div key={device.id} className="flex items-center justify-between px-6 py-3">
              <div>
                <p className="text-sm font-medium">{device.browser} on {device.os}</p>
                <p className="text-xs text-muted-foreground">
                  IP: <span className="font-mono">{device.ip_address}</span> &middot; Trusted: {new Date(device.trusted_at).toLocaleDateString()}
                </p>
              </div>
              <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive"
                onClick={() => handleRevokeDevice(device.id)}>Remove</Button>
            </div>
          ))}
        </div>
      </div>

      {/* Recovery Codes */}
      <div className="settings-card">
        <div className="settings-card-header">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-pink-400/10">
            <Key className="h-4 w-4 text-pink-400" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-semibold">Recovery Codes</h2>
            <p className="text-xs text-muted-foreground">Backup codes for account access</p>
          </div>
          <Button variant="outline" size="sm" onClick={handleGenerateRecoveryCodes} disabled={generatingCodes}>
            {generatingCodes ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : <Key className="h-3.5 w-3.5 mr-1.5" />}
            Generate New Codes
          </Button>
        </div>
        <div className="settings-card-body">
          {newRecoveryCodes.length > 0 && showRecoveryCodes ? (
            <div className="space-y-3">
              <div className="p-3 bg-warning/10 border border-warning/30 rounded-lg">
                <p className="text-xs text-amber-400 font-medium mb-1">Save these codes somewhere safe. Each code can only be used once.</p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {newRecoveryCodes.map((code: string, i: number) => (
                  <div key={i} className="font-mono text-sm bg-muted/30 px-3 py-2 rounded border border-border/30">{code}</div>
                ))}
              </div>
              <Button variant="outline" size="sm" onClick={() => { setShowRecoveryCodes(false); setNewRecoveryCodes([]); }}>Done</Button>
            </div>
          ) : recoveryCodes.length > 0 ? (
            <div>
              <p className="text-sm text-muted-foreground mb-2">{recoveryCodes.filter((c: any) => c.is_active).length} active recovery codes</p>
              <Button variant="outline" size="sm" onClick={() => setShowRecoveryCodes(true)}>View Codes</Button>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No recovery codes generated yet.</p>
          )}
        </div>
      </div>

      {/* Audit Logs */}
      <div className="settings-card">
        <div className="settings-card-header">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-400/10">
            <History className="h-4 w-4 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">Audit Logs</h2>
            <p className="text-xs text-muted-foreground">Track all account activity</p>
          </div>
        </div>
        <div className="settings-card-body">
          <AuditLogViewer />
        </div>
      </div>
    </div>
  );
}

function ApiKeysTab({ apiKeys, createdKey, newKeyName, setNewKeyName, creatingKey, revokingKey, handleCreateApiKey, handleRevokeApiKey, handleCopyKey }: any) {
  return (
    <div className="settings-card">
      <div className="settings-card-header">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-400/10">
          <Key className="h-4 w-4 text-amber-400" />
        </div>
        <div>
          <h2 className="text-sm font-semibold">API Keys</h2>
          <p className="text-xs text-muted-foreground">Programmatic access to the platform</p>
        </div>
      </div>
      <div className="settings-card-body space-y-4">
        {createdKey && (
          <div className="rounded-lg border border-success/30 bg-success/5 p-4">
            <p className="text-xs font-medium text-success mb-2">
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
        {apiKeys.length > 0 ? (
          apiKeys.map((key: any) => (
            <div key={key.id} className="flex items-center gap-3 rounded-lg border border-border/30 bg-muted/20 p-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{key.name || "API Key"}</p>
                <p className="text-xs text-muted-foreground">
                  Created {key.created_at ? new Date(key.created_at).toLocaleDateString() : "—"}
                </p>
              </div>
              <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive hover:bg-destructive/10 shrink-0"
                onClick={() => handleRevokeApiKey(key.id)} disabled={revokingKey === key.id}>
                {revokingKey === key.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                Revoke
              </Button>
            </div>
          ))
        ) : !createdKey && (
          <p className="text-sm text-muted-foreground">No API keys yet.</p>
        )}
        <div className="flex items-center gap-2">
          <Input value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)} placeholder="Key name (optional)"
            className="bg-muted/30 border-border/50 max-w-[200px]" />
          <Button variant="outline" size="sm" onClick={handleCreateApiKey} disabled={creatingKey}>
            {creatingKey ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Key className="h-3.5 w-3.5" />}
            Create New Key
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">API keys grant full access to your account. Keep them secret.</p>
      </div>
    </div>
  );
}

function NotificationsTab({ notifications, setNotifications, savingPrefs, handleSavePreferences }: any) {
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

  const categories = [...new Set(notifTypes.map((t) => t.category))];

  return (
    <div className="space-y-4">
      <div className="settings-card">
        <div className="settings-card-header">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-400/10">
            <Bell className="h-4 w-4 text-violet-400" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-semibold">Notification Preferences</h2>
            <p className="text-xs text-muted-foreground">Control in-app and email notifications per category</p>
          </div>
        </div>
        {loadingPrefs ? (
          <div className="flex items-center justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
        ) : (
          <div className="divide-y divide-border/30">
            {categories.map((cat) => (
              <div key={cat}>
                <div className="px-6 py-2 bg-muted/30">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{cat}</p>
                </div>
                {notifTypes.filter((t) => t.category === cat).map((item) => {
                  const pref = notifPrefs.find((p) => p.notification_type === item.type);
                  return (
                    <div key={item.type} className="flex items-center justify-between px-6 py-3">
                      <p className="text-sm font-medium">{item.label}</p>
                      <div className="flex gap-4">
                        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <span>In-app</span>
                          <button
                            onClick={() => togglePref(item.type, "in_app")}
                            className={cn(
                              "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
                              pref?.in_app_enabled ? "bg-primary" : "bg-muted"
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
                              pref?.email_enabled ? "bg-primary" : "bg-muted"
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
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function IntegrationsTab() {
  return (
    <div className="settings-card">
      <div className="settings-card-header">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-info/10">
            <Link2 className="h-4 w-4 text-info" />
        </div>
        <div>
          <h2 className="text-sm font-semibold">Integrations</h2>
          <p className="text-xs text-muted-foreground">Connect with third-party services</p>
        </div>
      </div>
      <div className="settings-card-body">
        <div className="text-center py-8">
          <Link2 className="h-10 w-10 text-muted-foreground/30 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground mb-1">Integrations coming soon</p>
          <p className="text-xs text-muted-foreground/60">Connect with Slack, Jira, PagerDuty, and more.</p>
        </div>
      </div>
    </div>
  );
}

function DangerTab({ showDeleteConfirm, setShowDeleteConfirm, deleting, handleDeleteAccount }: any) {
  return (
    <div className="settings-card border-destructive/20 bg-destructive/5">
      <div className="settings-card-header border-red-500/10">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/10">
          <AlertTriangle className="h-4 w-4 text-red-400" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-red-400">Danger Zone</h2>
          <p className="text-xs text-red-400/60">Irreversible actions</p>
        </div>
      </div>
      <div className="settings-card-body">
        {!showDeleteConfirm ? (
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Delete Account</p>
              <p className="text-xs text-muted-foreground">Permanently delete your account and all associated data</p>
            </div>
            <Button variant="destructive" size="sm"
              className="bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20"
              onClick={() => setShowDeleteConfirm(true)}>
              <Trash2 className="h-3.5 w-3.5" />
              Delete Account
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-red-400">
              Are you sure? This action cannot be undone. All your data will be permanently deleted.
            </p>
            <div className="flex items-center gap-3">
              <Button variant="destructive" size="sm" className="bg-red-500 text-white hover:bg-red-600"
                onClick={handleDeleteAccount} disabled={deleting}>
                {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : null}
                Yes, delete my account
              </Button>
              <Button variant="outline" size="sm" onClick={() => setShowDeleteConfirm(false)}>Cancel</Button>
            </div>
          </div>
        )}
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
