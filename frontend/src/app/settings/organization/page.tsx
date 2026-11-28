"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Building,
  Users,
  Shield,
  Save,
  Loader2,
  Mail,
  Crown,
  Trash2,
  UserPlus,
  Globe,
  Briefcase,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  Plus,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import api, {
  getOrganization,
  createOrganization,
  updateOrganization,
  listOrganizationMembers,
  updateMemberRole,
  removeOrganizationMember,
  getOrganizationStats,
  inviteMember,
} from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Select, SelectItem } from "@/components/ui/select";
import { useAuth } from "@/contexts/AuthContext";
import type {
  Organization,
  OrganizationMember,
  OrganizationStats,
  OrgRole,
} from "@/types";

const ROLE_LABELS: Record<OrgRole, string> = {
  owner: "Owner",
  admin: "Administrator",
  security_manager: "Security Manager",
  analyst: "Analyst",
  viewer: "Viewer",
};

  const ROLE_ACCENT: Record<OrgRole, "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info"> = {
  owner: "default",
  admin: "secondary",
  security_manager: "warning",
  analyst: "success",
  viewer: "info",
};

export default function OrganizationSettingsPage() {
  const { user, refreshUser } = useAuth();
  const orgId = user?.organization_id;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [org, setOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [stats, setStats] = useState<OrganizationStats | null>(null);
  const [tab, setTab] = useState("profile");
  const [saveMsg, setSaveMsg] = useState<"" | "success" | "error">("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<OrgRole>("analyst");
  const [inviting, setInviting] = useState(false);
  const [error, setError] = useState("");
  const [orgName, setOrgName] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    if (!orgId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [o, m, s] = await Promise.all([
        getOrganization(orgId),
        listOrganizationMembers(orgId),
        getOrganizationStats(orgId),
      ]);
      setOrg(o);
      setMembers(m);
      setStats(s);
    } catch (e) {
      setError("Failed to load organization data.");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    load();
  }, [load]);

  const canManage = user?.role === "owner" || user?.role === "admin";

  async function handleSaveProfile() {
    if (!orgId || !org) return;
    setSaving(true);
    setSaveMsg("");
    try {
      const updated = await updateOrganization(orgId, {
        name: org.name,
        description: org.description,
        website: org.website,
        industry: org.industry,
        company_size: org.company_size,
        mfa_enforced: org.mfa_enforced,
      });
      setOrg(updated);
      setSaveMsg("success");
    } catch {
      setSaveMsg("error");
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(""), 2500);
    }
  }

  async function handleRoleChange(memberId: string, role: OrgRole) {
    if (!orgId) return;
    try {
      const updated = await updateMemberRole(orgId, memberId, role);
      setMembers((prev) => prev.map((m) => (m.id === memberId ? updated : m)));
    } catch {
      setError("Failed to update member role.");
    }
  }

  async function handleRemove(memberId: string) {
    if (!orgId) return;
    try {
      await removeOrganizationMember(orgId, memberId);
      setMembers((prev) => prev.filter((m) => m.id !== memberId));
    } catch {
      setError("Failed to remove member.");
    }
  }

  async function handleInvite() {
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setError("");
    try {
      await inviteMember(inviteEmail.trim(), inviteRole);
      setInviteEmail("");
      await load();
    } catch {
      setError("Failed to send invitation.");
    } finally {
      setInviting(false);
    }
  }

  async function handleCreateOrg() {
    if (!orgName.trim()) return;
    setCreating(true);
    setError("");
    try {
      await createOrganization({ name: orgName.trim() });
      await refreshUser();
      await load();
    } catch {
      setError("Failed to create organization.");
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return (
      <div className="page-container-md">
        <div className="flex items-center justify-center py-32 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin mr-2" /> Loading organization...
        </div>
      </div>
    );
  }

  if (!orgId || !org) {
    return (
      <div className="page-container-md">
        <PageHeader
          title="Organization"
          description="Create your organization to get started with scanning"
          icon={<Building className="h-5 w-5" />}
          breadcrumbs={[
            { label: "Settings", href: "/settings" },
            { label: "Organization" },
          ]}
        />

        <SectionCard
          title="Create Organization"
          description="Set up your organization to enable scanning, asset management, and team collaboration."
          icon={<Building className="h-4 w-4" />}
        >
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              You need an organization to use the scanner. Creating one gives you the <strong>Owner</strong> role with full permissions including scan creation.
            </p>
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  Organization Name
                </label>
                <Input
                  placeholder="My Security Team"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreateOrg()}
                />
              </div>
              <Button
                onClick={handleCreateOrg}
                disabled={creating || !orgName.trim()}
                
              >
                {creating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                Create
              </Button>
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" /> {error}
              </div>
            )}
          </div>
        </SectionCard>
      </div>
    );
  }

  return (
    <div className="page-container-md">
      <PageHeader
        title="Organization"
        description="Manage your team, profile, and security settings"
        icon={<Building className="h-5 w-5" />}
        breadcrumbs={[
          { label: "Settings", href: "/settings" },
          { label: "Organization" },
        ]}
        actions={
          <Link href="/settings">
            <Button variant="outline" size="sm">
              Back to Settings
            </Button>
          </Link>
        }
      />

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {/* Stats row */}
      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard
            label="Members"
            value={stats.member_count}
            icon={<Users className="h-5 w-5" />}
            accent="brand"
          />
          <StatCard
            label="Scans"
            value={stats.scan_count}
            icon={<Briefcase className="h-5 w-5" />}
            accent="success"
            hint={`${stats.active_scan_count} active`}
          />
          <StatCard
            label="Assets"
            value={stats.asset_count}
            icon={<Globe className="h-5 w-5" />}
            accent="info"
          />
          <StatCard
            label="Plan"
            value={<span className="text-xl capitalize">{stats.plan}</span>}
            icon={<ShieldCheck className="h-5 w-5" />}
            accent="warning"
          />
        </div>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="profile" className="gap-1.5">
            <Building className="h-3.5 w-3.5" /> Profile
          </TabsTrigger>
          <TabsTrigger value="members" className="gap-1.5">
            <Users className="h-3.5 w-3.5" /> Members
            {members.length > 0 && (
              <Badge variant="secondary" className="ml-1 px-1.5 py-0 text-[10px]">
                {members.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="security" className="gap-1.5">
            <Shield className="h-3.5 w-3.5" /> Security
          </TabsTrigger>
        </TabsList>

        {/* PROFILE TAB */}
        <TabsContent value="profile">
          <SectionCard
            title="Organization Profile"
            description="Basic information about your organization"
            icon={<Building className="h-4 w-4" />}
          >
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    Name
                  </label>
                  <Input
                    value={org.name}
                    disabled={!canManage}
                    onChange={(e) => setOrg({ ...org, name: e.target.value })}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    Slug
                  </label>
                  <Input value={org.slug} disabled className="bg-muted/20 opacity-60" />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    Website
                  </label>
                  <Input
                    placeholder="https://example.com"
                    value={org.website || ""}
                    disabled={!canManage}
                    onChange={(e) => setOrg({ ...org, website: e.target.value })}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    Industry
                  </label>
                  <Input
                    placeholder="Cybersecurity"
                    value={org.industry || ""}
                    disabled={!canManage}
                    onChange={(e) => setOrg({ ...org, industry: e.target.value })}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    Company Size
                  </label>
                  <Input
                    placeholder="11-50"
                    value={org.company_size || ""}
                    disabled={!canManage}
                    onChange={(e) => setOrg({ ...org, company_size: e.target.value })}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    Plan
                  </label>
                  <Input
                    value={org.plan}
                    disabled
                    className="bg-muted/20 opacity-60 capitalize"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  Description
                </label>
                <textarea
                  className="h-24 w-full rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm focus:border-primary/50 focus:ring-primary/20"
                  placeholder="Describe your organization..."
                  value={org.description || ""}
                  disabled={!canManage}
                  onChange={(e) => setOrg({ ...org, description: e.target.value })}
                />
              </div>

              {canManage && (
                <div className="flex items-center gap-3 pt-2">
                  <Button
                    onClick={handleSaveProfile}
                    disabled={saving}
                    
                  >
                    {saving ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    Save Changes
                  </Button>
                  {saveMsg === "success" && (
                    <span className="flex items-center gap-1.5 text-sm text-emerald-400">
                      <CheckCircle2 className="h-4 w-4" /> Saved
                    </span>
                  )}
                  {saveMsg === "error" && (
                    <span className="text-sm text-destructive">Failed to save.</span>
                  )}
                </div>
              )}
            </div>
          </SectionCard>
        </TabsContent>

        {/* MEMBERS TAB */}
        <TabsContent value="members">
          <SectionCard
            title="Team Members"
            description="People with access to this organization"
            icon={<Users className="h-4 w-4" />}
            actions={
              canManage ? (
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="invite@email.com"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    className="h-9 w-48"
                  />
                  <Select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as OrgRole)}
                    className="h-9 w-36"
                  >
                    {Object.entries(ROLE_LABELS).map(([key, label]) => (
                      <SelectItem key={key} value={key}>
                        {label}
                      </SelectItem>
                    ))}
                  </Select>
                  <Button
                    size="sm"
                    onClick={handleInvite}
                    disabled={inviting || !inviteEmail.trim()}
                    className="bg-primary"
                  >
                    {inviting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <UserPlus className="h-4 w-4" />
                    )}
                    Invite
                  </Button>
                </div>
              ) : undefined
            }
          >
            {members.length === 0 ? (
              <EmptyState
                icon={<Users className="h-8 w-8" />}
            title="No members"
            description="Invite your team to share scans and findings."
              />
            ) : (
              <div className="divide-y divide-border/40">
                {members.map((m) => {
                  const role = m.role as OrgRole;
                  const isSelf = m.id === user?.id;
                  return (
                    <div
                      key={m.id}
                      className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"
                    >
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-brand">
                        {(m.full_name || m.email).slice(0, 2).toUpperCase()}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">
                          {m.full_name || m.email}
                          {isSelf && (
                            <span className="ml-2 text-xs text-muted-foreground">(you)</span>
                          )}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">{m.email}</p>
                      </div>

                      {canManage && !isSelf ? (
                        <Select
                          value={role}
                          onChange={(e) => handleRoleChange(m.id, e.target.value as OrgRole)}
                          className="h-8 w-40"
                        >
                          {Object.entries(ROLE_LABELS).map(([key, label]) => (
                            <SelectItem key={key} value={key}>
                              {label}
                            </SelectItem>
                          ))}
                        </Select>
                      ) : (
                        <Badge variant={ROLE_ACCENT[role]}>
                          {role === "owner" && <Crown className="mr-1 h-3 w-3" />}
                          {ROLE_LABELS[role]}
                        </Badge>
                      )}

                      {canManage && !isSelf && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-destructive"
                          onClick={() => handleRemove(m.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </SectionCard>
        </TabsContent>

        {/* SECURITY TAB */}
        <TabsContent value="security">
          <SectionCard
            title="Security Policies"
            description="Enforce security controls across your organization"
            icon={<Shield className="h-4 w-4" />}
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-lg border border-border bg-muted/20 p-4">
                <div className="flex items-start gap-3">
                  <ShieldCheck className="mt-0.5 h-5 w-5 text-brand" />
                  <div>
                    <p className="text-sm font-medium">Require MFA for all members</p>
                    <p className="text-xs text-muted-foreground">
                      Force two-factor authentication on every account in this org.
                    </p>
                  </div>
                </div>
                {canManage ? (
                  <button
                    onClick={() => setOrg({ ...org, mfa_enforced: !org.mfa_enforced })}
                    className={`relative h-6 w-11 rounded-full transition-colors ${
                      org.mfa_enforced ? "bg-brand" : "bg-muted-foreground/30"
                    }`}
                    aria-label="Toggle MFA enforcement"
                  >
                    <span
                      className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                        org.mfa_enforced ? "translate-x-5" : "translate-x-0.5"
                      }`}
                    />
                  </button>
                ) : (
                  <Badge variant={org.mfa_enforced ? "success" : "secondary"}>
                    {org.mfa_enforced ? "Enabled" : "Disabled"}
                  </Badge>
                )}
              </div>

              {canManage && (
                <div className="flex items-center gap-3 pt-2">
                  <Button
                    onClick={handleSaveProfile}
                    disabled={saving}
                    
                  >
                    {saving ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    Save Security Settings
                  </Button>
                </div>
              )}

              <div className="rounded-lg border border-border bg-muted/20 p-4">
                <p className="text-xs font-medium text-muted-foreground mb-2">
                  Role distribution
                </p>
                {stats && Object.keys(stats.role_distribution).length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(stats.role_distribution).map(([role, count]) => (
                      <Badge
                        key={role}
                        variant={ROLE_ACCENT[role as OrgRole] || "secondary"}
                      >
                        {ROLE_LABELS[role as OrgRole] || role}: {count}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">No data available.</p>
                )}
              </div>
            </div>
          </SectionCard>
        </TabsContent>
      </Tabs>
    </div>
  );
}
