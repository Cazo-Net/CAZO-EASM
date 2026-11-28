"use client";

import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield, Smartphone, Fingerprint, Clock, ArrowLeft, User, Key } from "lucide-react";
import { getSecurityDashboard, listSecurityCenterSessions, listSecurityCenterDevices, getSecurityCenterLoginHistory, revokeSecurityCenterSession, revokeAllSecurityCenterSessions, removeSecurityCenterDevice } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { LoginHistory } from "@/components/security/LoginHistory";

function SecurityCenterContent() {
  const { user } = useAuth();
  const router = useRouter();
  const [dashboard, setDashboard] = useState<any>(null);
  const [sessions, setSessions] = useState<any[]>([]);
  const [devices, setDevices] = useState<any[]>([]);
  const [loginHistory, setLoginHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [dashRes, sessionsRes, devicesRes, historyRes] = await Promise.allSettled([
        getSecurityDashboard(),
        listSecurityCenterSessions(),
        listSecurityCenterDevices(),
        getSecurityCenterLoginHistory(20),
      ]);

      if (dashRes.status === "fulfilled") setDashboard(dashRes.value);
      if (sessionsRes.status === "fulfilled") setSessions(sessionsRes.value);
      if (devicesRes.status === "fulfilled") setDevices(devicesRes.value);
      if (historyRes.status === "fulfilled") setLoginHistory(historyRes.value);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRevokeSession = async (sessionId: string) => {
    try {
      await revokeSecurityCenterSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch {
      // silently fail
    }
  };

  const handleRevokeAll = async () => {
    if (!confirm("Are you sure you want to revoke all sessions? You will be logged out.")) return;
    try {
      await revokeAllSecurityCenterSessions();
      setSessions([]);
    } catch {
      // silently fail
    }
  };

  const handleRemoveDevice = async (deviceId: string) => {
    try {
      await removeSecurityCenterDevice(deviceId);
      setDevices((prev) => prev.filter((d) => d.id !== deviceId));
    } catch {
      // silently fail
    }
  };

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center">Loading...</div>;
  }

  if (!user) {
    return <div className="min-h-screen flex items-center justify-center">Unauthorized</div>;
  }

  return (
    <div className="min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <Shield className="w-6 h-6" />
            <h1 className="text-xl font-semibold">Security Center</h1>
            <p className="text-base text-muted-foreground">Monitor and manage your account security</p>
          </div>
          <Button variant="outline" onClick={() => router.push("/settings")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Settings
          </Button>
        </div>

        {/* Quick Stats */}
        {dashboard && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4 text-center">
                <Fingerprint className="w-6 h-6 text-brand mx-auto mb-2" />
                <p className="text-2xl font-semibold text-foreground">
                  {dashboard.mfa_enabled ? "On" : "Off"}
                </p>
                <p className="text-xs text-muted-foreground">MFA Status</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <Smartphone className="w-6 h-6 text-accent-2 mx-auto mb-2" />
                <p className="text-2xl font-semibold text-foreground">{dashboard.trusted_devices}</p>
                <p className="text-xs text-muted-foreground">Trusted Devices</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <Clock className="w-6 h-6 text-warning mx-auto mb-2" />
                <p className="text-2xl font-semibold text-foreground">{dashboard.failed_logins_30d}</p>
                <p className="text-xs text-muted-foreground">Failed Logins (30d)</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <Key className="w-6 h-6 text-info mx-auto mb-2" />
                <p className="text-2xl font-semibold text-foreground">{dashboard.active_api_keys}</p>
                <p className="text-xs text-muted-foreground">Active API Keys</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Sessions */}
        {sessions.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Smartphone className="w-4 h-4" />
                Active Sessions
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <div className="space-y-2">
                {sessions.map((session) => (
                  <div
                    key={session.id}
                    className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors"
                  >
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {session.device_name || [session.browser, session.os].filter(Boolean).join(" on ") || "Unknown device"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {session.browser} on {session.os}
                        {session.ip_address && ` • ${session.ip_address}`}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Started {session.created_at ? new Date(session.created_at).toLocaleDateString() : "Unknown"}
                        {(session.last_activity || session.last_active) && ` • Last active ${new Date(session.last_activity || session.last_active).toLocaleString()}`}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRevokeSession(session.id)}
                      className="text-destructive hover:text-destructive"
                    >
                      Revoke
                    </Button>
                  </div>
                ))}
              </div>
              {sessions.length > 1 && (
                <Button variant="outline" onClick={handleRevokeAll} className="mt-4 w-full text-destructive border-destructive hover:bg-destructive hover:text-white">
                  Revoke All Sessions
                </Button>
              )}
            </CardContent>
          </Card>
        )}

        {/* Trusted Devices */}
        {devices.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Smartphone className="w-4 h-4" />
                Trusted Devices
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <div className="space-y-2">
                {devices.map((device) => (
                  <div
                    key={device.id}
                    className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors"
                  >
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {device.device_name || "Unknown Device"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {device.browser} on {device.os}
                        {device.ip_address && ` • ${device.ip_address}`}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Trusted {device.trusted_at ? new Date(device.trusted_at).toLocaleDateString() : "Unknown"}
                        {device.last_used && ` • Last used ${new Date(device.last_used).toLocaleDateString()}`}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemoveDevice(device.id)}
                      className="text-destructive hover:text-destructive"
                    >
                      Remove
                    </Button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Login History */}
        {loginHistory.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <User className="w-4 h-4" />
                Login History
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <LoginHistory entries={loginHistory} />
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

export default function SecurityCenterPage() {
  return (
    <ProtectedRoute>
      <SecurityCenterContent />
    </ProtectedRoute>
  );
}
