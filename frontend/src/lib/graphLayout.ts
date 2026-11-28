/**
 * Shapes of the `/assets/graph` payload. The layout itself lives in
 * `attackGraphModel.ts` (grouped, progressive, deterministic).
 */
export interface PortSummary {
  port: number;
  state?: string;
  service?: string | null;
  version?: string | null;
  banner?: string | null;
}

export interface RawGraphNode {
  id: string;
  label: string;
  type: "domain" | "subdomain" | "port" | "vulnerability" | "certificate";
  ips?: string[];
  service?: string | null;
  severity?: string;
  // Enriched fields from the backend graph endpoint:
  ports?: PortSummary[];
  port_count?: number;
  vuln_count?: number;
  port?: number;
  state?: string;
  version?: string | null;
  banner?: string | null;
  host?: string;
  os_detection?: any;
  host_scripts?: any;
}

export interface RawGraphEdge {
  source: string;
  target: string;
  label?: string;
}
