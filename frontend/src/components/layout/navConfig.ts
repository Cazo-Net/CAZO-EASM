import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard, ScanSearch, Globe, Layers, FileText, Bug, Network, Search, Waypoints,
  ShieldCheck, Ghost, Zap, History, BarChart3, MessagesSquare, Boxes, BookOpen, Wallet, Eye,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

// The sidebar menu. Every app page renders the same list, so a label must
// name one page only: two items with the same label cannot be told apart.
export const navSections: NavSection[] = [
  {
    label: "Overview",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/change-feed", label: "Change feed", icon: History },
    ],
  },
  {
    label: "Attack surface",
    items: [
      { href: "/inventory", label: "Asset inventory", icon: Layers },
      { href: "/assets", label: "Assets by scan", icon: Globe },
      { href: "/shadow-assets", label: "Shadow assets", icon: Ghost },
      { href: "/assets/360", label: "Asset 360°", icon: Boxes },
      { href: "/graph", label: "Attack graph", icon: Waypoints },
      { href: "/dns", label: "DNS records", icon: Network },
      { href: "/whois", label: "WHOIS", icon: Search },
    ],
  },
  {
    label: "Risk",
    items: [
      { href: "/vulnerabilities", label: "Findings", icon: Bug },
      { href: "/supply-chain", label: "Supply chain", icon: Boxes },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/scans", label: "Scans", icon: ScanSearch },
      { href: "/scopes", label: "Authorized scopes", icon: ShieldCheck },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/intel", label: "OSINT lookup", icon: Zap },
      { href: "/darkweb", label: "Threat intel", icon: Eye },
      { href: "/blockchain", label: "Blockchain", icon: Wallet },
    ],
  },
  {
    label: "Reporting",
    items: [
      { href: "/reports", label: "Reports", icon: FileText },
      { href: "/reports/executive", label: "Executive report", icon: BarChart3 },
      { href: "/compare", label: "Compare scans", icon: Waypoints },
      { href: "/canvas", label: "Investigation canvas", icon: Network },
    ],
  },
  {
    label: "Team",
    items: [
      { href: "/collab-demo", label: "Comments", icon: MessagesSquare },
      { href: "/docs", label: "Docs", icon: BookOpen },
    ],
  },
];
