/**
 * Living Internet — shared types & brand constants.
 *
 * A custom WebGL (PixiJS) infrastructure visualization for the CAZO landing
 * hero. Not a particle library — every element models a piece of real Internet
 * infrastructure (domains, IPs, certs, CDNs, clouds…) and the scene continuously
 * discovers, connects, monitors and re-shapes itself.
 */

export const BRAND = {
  bg: 0x050608,
  primary: 0x18f2b2, // phosphor / discovery
  secondary: 0x00d9ff, // cyan / infrastructure links
  highlight: 0x7a5cff, // violet / relationships
  critical: 0xff4d6d, // red / exposure
  soft: 0xe8edf5, // soft white / labels
} as const;

export type NodeKind =
  | "domain"
  | "subdomain"
  | "ip"
  | "api"
  | "cloud"
  | "cdn"
  | "dns"
  | "certificate"
  | "firewall"
  | "gateway"
  | "server"
  | "container"
  | "loadbalancer"
  | "database"
  | "technology";

export interface NodeStyle {
  kind: NodeKind;
  color: number;
  /** base radius in CSS px (before DPR + parallax scaling) */
  radius: number;
  /** glyph drawn inside the node (short, mono) */
  glyph: string;
}

/** Per-type visual identity — distinct color family + glyph + size. */
export const NODE_STYLES: Record<NodeKind, NodeStyle> = {
  cloud: { kind: "cloud", color: BRAND.secondary, radius: 9, glyph: "☁" },
  server: { kind: "server", color: BRAND.primary, radius: 8, glyph: "▤" },
  database: { kind: "database", color: BRAND.highlight, radius: 8, glyph: "▦" },
  domain: { kind: "domain", color: BRAND.soft, radius: 8, glyph: "◈" },
  subdomain: { kind: "subdomain", color: BRAND.primary, radius: 6, glyph: "◇" },
  api: { kind: "api", color: BRAND.secondary, radius: 6, glyph: "{}" },
  cdn: { kind: "cdn", color: BRAND.secondary, radius: 7, glyph: "≋" },
  dns: { kind: "dns", color: BRAND.highlight, radius: 6, glyph: "⌘" },
  ip: { kind: "ip", color: BRAND.soft, radius: 5, glyph: "·" },
  certificate: { kind: "certificate", color: BRAND.primary, radius: 6, glyph: "⚿" },
  firewall: { kind: "firewall", color: BRAND.critical, radius: 7, glyph: "▚" },
  gateway: { kind: "gateway", color: BRAND.secondary, radius: 7, glyph: "⇄" },
  container: { kind: "container", color: BRAND.primary, radius: 6, glyph: "▣" },
  loadbalancer: { kind: "loadbalancer", color: BRAND.highlight, radius: 7, glyph: "⋔" },
  technology: { kind: "technology", color: BRAND.soft, radius: 5, glyph: "λ" },
};

/** Kinds that read as "main infrastructure" (larger, foreground focus). */
export const INFRA_KINDS: NodeKind[] = [
  "cloud",
  "server",
  "database",
  "domain",
  "cdn",
  "gateway",
  "loadbalancer",
  "firewall",
];

/** Smaller peripheral kinds spawned by discovery. */
export const DISCOVERY_KINDS: NodeKind[] = [
  "subdomain",
  "api",
  "dns",
  "ip",
  "certificate",
  "container",
  "technology",
];

export interface Discovery {
  label: string;
  kind: NodeKind;
}

/** Discovery event vocabulary — pulled from CAZO's real product surface. */
export const DISCOVERY_EVENTS: Discovery[] = [
  { label: "New Subdomain", kind: "subdomain" },
  { label: "Certificate Found", kind: "certificate" },
  { label: "Open Port", kind: "server" },
  { label: "DNS Record", kind: "dns" },
  { label: "Cloud Asset", kind: "cloud" },
  { label: "Technology Detected", kind: "technology" },
  { label: "API Endpoint", kind: "api" },
  { label: "CDN Edge", kind: "cdn" },
  { label: "Container Host", kind: "container" },
];

/** Security event vocabulary. */
export const SECURITY_EVENTS: string[] = [
  "Vulnerability",
  "Cert Expired",
  "Outdated Tech",
  "Exposure Detected",
  "Weak TLS",
  "Open Admin Port",
];

/** Floating activity-feed lines. */
export const ACTIVITY_LINES: string[] = [
  "New Certificate",
  "DNS Updated",
  "Subdomain Found",
  "Asset Verified",
  "TLS Detected",
  "Port Scanned",
  "Cloud Asset Mapped",
  "Technology Fingerprinted",
];

/** Dynamic labels that occasionally fade in near infra nodes. */
export const DYNAMIC_LABELS: string[] = [
  "api.company.com",
  "cdn.company.com",
  "mail.company.com",
  "app.company.com",
  "AWS",
  "Azure",
  "Cloudflare",
  "FastAPI",
  "React",
  "TLS 1.3",
  "443",
  "HTTP/2",
  "Let's Encrypt",
  "Nginx",
  "PostgreSQL",
  "Redis",
];

export interface QualityTier {
  stars: number;
  mesh: number;
  infra: number;
  maxPulses: number;
  maxLabels: number;
  blur: boolean;
}

export function resolveQuality(): QualityTier {
  if (typeof window === "undefined") {
    return { stars: 300, mesh: 200, infra: 50, maxPulses: 90, maxLabels: 8, blur: true };
  }
  const cores = navigator.hardwareConcurrency ?? 4;
  const mem = (navigator as unknown as { deviceMemory?: number }).deviceMemory ?? 4;
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const w = window.innerWidth;

  // Low-end / mobile
  if (coarse || cores <= 4 || mem <= 3 || w < 768) {
    return { stars: 120, mesh: 80, infra: 34, maxPulses: 36, maxLabels: 5, blur: false };
  }
  // Mid
  if (cores <= 8 || mem <= 6 || w < 1440) {
    return { stars: 240, mesh: 150, infra: 46, maxPulses: 64, maxLabels: 7, blur: true };
  }
  // High-end
  return { stars: 360, mesh: 230, infra: 56, maxPulses: 100, maxLabels: 8, blur: true };
}
