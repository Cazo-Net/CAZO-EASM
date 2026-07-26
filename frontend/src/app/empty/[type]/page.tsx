"use client";

import { EmptyState } from "@/components/error";
import { Globe, Plus, FileText, ScanSearch, Bell, Bug, Building2 } from "lucide-react";
import Link from "next/link";

const emptyStates: Record<string, { title: string; description: string; icon: React.ReactNode; action: { label: string; href: string }; tips: string[] }> = {
  assets: {
    title: "Your surface is empty",
    description: "No assets found. A scan will map your subdomains, ports, certs, and services.",
    icon: <Globe className="h-7 w-7" />,
    action: { label: "Run First Scan", href: "/scan/new" },
    tips: [
      "Start with your root domain",
      "Asset discovery runs automatically during scans",
      "Results stream in as they resolve",
    ],
  },
  reports: {
    title: "No reports yet",
    description: "Finish a scan, then export what you found.",
    icon: <FileText className="h-7 w-7" />,
    action: { label: "Run a Scan", href: "/scan/new" },
    tips: [
      "Reports are generated from completed scans",
      "Executive, Technical, or Weekly — pick what your team needs",
      "Export as PDF or share a link",
    ],
  },
  scans: {
    title: "No scan history",
    description: "Enter a domain to get started.",
    icon: <ScanSearch className="h-7 w-7" />,
    action: { label: "Start First Scan", href: "/scan/new" },
    tips: [
      "Enter your root domain to begin",
      "Most scans finish in under a minute",
      "Set up continuous monitoring to stay ahead",
    ],
  },
  notifications: {
    title: "Nothing new",
    description: "No alerts right now. We'll surface anything worth seeing.",
    icon: <Bell className="h-7 w-7" />,
    action: { label: "Dashboard", href: "/dashboard" },
    tips: [
      "Notifications fire when scans complete",
      "You'll see critical findings immediately",
      "Certificate expiry warnings show up here",
    ],
  },
  vulnerabilities: {
    title: "No findings",
    description: "That either means you're clean or we haven't scanned yet.",
    icon: <Bug className="h-7 w-7" />,
    action: { label: "View Assets", href: "/assets" },
    tips: [
      "Run regular scans to catch new issues",
      "CVE matches are labeled version-correlated, not confirmed",
      "Monitor cert and config changes between scans",
    ],
  },
  organizations: {
    title: "No organizations yet",
    description: "Create one to share scans and findings with your team.",
    icon: <Building2 className="h-7 w-7" />,
    action: { label: "Create Organization", href: "/settings" },
    tips: [
      "Organizations separate business units or projects",
      "Each org has its own assets and members",
      "You can belong to multiple organizations",
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
