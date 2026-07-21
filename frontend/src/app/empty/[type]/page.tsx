"use client";

import { EmptyState } from "@/components/error";
import { Globe, Plus, FileText, ScanSearch, Bell, Bug, Building2 } from "lucide-react";
import Link from "next/link";

const emptyStates: Record<string, { title: string; description: string; icon: React.ReactNode; action: { label: string; href: string }; tips: string[] }> = {
  assets: {
    title: "No Assets Yet",
    description: "You haven't discovered any assets yet. Start your first scan to map your external attack surface.",
    icon: <Globe className="h-7 w-7" />,
    action: { label: "Run First Scan", href: "/scan/new" },
    tips: [
      "Start by adding your root domain",
      "Asset discovery runs automatically during scans",
      "You can also manually add assets from the Assets page",
    ],
  },
  reports: {
    title: "No Reports Yet",
    description: "No reports have been generated yet. Complete a scan and generate your first report.",
    icon: <FileText className="h-7 w-7" />,
    action: { label: "Run a Scan", href: "/scan/new" },
    tips: [
      "Reports are generated from completed scans",
      "Choose from Executive, Technical, or Weekly report types",
      "Reports can be exported as PDF or shared via link",
    ],
  },
  scans: {
    title: "No Scans Yet",
    description: "You haven't run any scans yet. Start your first scan to discover and monitor your external attack surface.",
    icon: <ScanSearch className="h-7 w-7" />,
    action: { label: "Start First Scan", href: "/scan/new" },
    tips: [
      "Enter your root domain to begin",
      "Scans typically complete in under 60 seconds",
      "Enable continuous monitoring for automatic rescans",
    ],
  },
  notifications: {
    title: "No Notifications",
    description: "You're all caught up! No new notifications at this time.",
    icon: <Bell className="h-7 w-7" />,
    action: { label: "Dashboard", href: "/dashboard" },
    tips: [
      "Notifications appear when scans complete",
      "You'll be alerted for critical vulnerabilities",
      "Certificate expiry warnings appear here",
    ],
  },
  vulnerabilities: {
    title: "No Vulnerabilities Found",
    description: "No vulnerabilities have been detected in your attack surface. Keep monitoring for changes.",
    icon: <Bug className="h-7 w-7" />,
    action: { label: "View Assets", href: "/assets" },
    tips: [
      "Run regular scans to detect new vulnerabilities",
      "Enable nuclei templates for comprehensive checks",
      "Monitor certificate and configuration changes",
    ],
  },
  organizations: {
    title: "No Organizations",
    description: "Create your first organization to start managing your security posture across teams.",
    icon: <Building2 className="h-7 w-7" />,
    action: { label: "Create Organization", href: "/settings" },
    tips: [
      "Organizations help separate different business units",
      "Each organization has its own assets and team members",
      "You can be a member of multiple organizations",
    ],
  },
};

export default function EmptyStatePage({ params }: { params: { type: string } }) {
  const state = emptyStates[params.type];
  if (!state) {
    return (
      <div className="min-h-screen bg-background px-4 py-12">
        <div className="mx-auto max-w-lg text-center">
          <h2 className="text-xl font-semibold text-foreground mb-2">Nothing here yet</h2>
          <p className="text-sm text-muted-foreground mb-4">This section doesn&apos;t have any content.</p>
          <Link href="/dashboard" className="text-sm text-brand hover:underline">Go to Dashboard</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-4 py-12">
      <div className="mx-auto max-w-lg">
        <EmptyState
          title={state.title}
          description={state.description}
          icon={state.icon}
          action={state.action}
          tips={state.tips}
        />
      </div>
    </div>
  );
}
