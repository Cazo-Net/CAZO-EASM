"use client";

import { Badge } from "@/components/ui/badge";

interface Technology {
  name: string;
  category: string;
  vendor_type: string;
  confidence: number;
  version?: string;
}

const VENDOR_TYPE_COLORS: Record<string, string> = {
  third_party_service: "border-blue-500/20 bg-blue-500/5",
  saas_platform: "border-purple-500/20 bg-purple-500/5",
  first_party_infra: "border-green-500/20 bg-green-500/5",
  security_tool: "border-orange-500/20 bg-orange-500/5",
  cloud_provider: "border-cyan-500/20 bg-cyan-500/5",
  devops_tool: "border-yellow-500/20 bg-yellow-500/5",
};

const VENDOR_TYPE_BADGE: Record<string, string> = {
  third_party_service: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  saas_platform: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  first_party_infra: "bg-success/10 text-success border-green-500/20",
  security_tool: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  cloud_provider: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  devops_tool: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
};

const VENDOR_TYPE_LABELS: Record<string, string> = {
  third_party_service: "3rd Party",
  saas_platform: "SaaS",
  first_party_infra: "1st Party",
  security_tool: "Security",
  cloud_provider: "Cloud",
  devops_tool: "DevOps",
};

function getRiskLevel(confidence: number): { label: string; color: string } {
  if (confidence >= 80) return { label: "High", color: "text-destructive" };
  if (confidence >= 50) return { label: "Medium", color: "text-yellow-400" };
  return { label: "Low", color: "text-success" };
}

interface VendorGridProps {
  technologies: Technology[];
}

export function VendorGrid({ technologies }: VendorGridProps) {
  if (technologies.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-muted-foreground">
        No services match the current filters.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {technologies.map((tech, i) => {
        const risk = getRiskLevel(tech.confidence);
        return (
          <div
            key={`${tech.name}-${tech.category}-${i}`}
            className={`border rounded-lg p-3 transition-colors hover:border-border ${
              VENDOR_TYPE_COLORS[tech.vendor_type] || "border-border bg-muted/5"
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{tech.name}</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {tech.category}
                </div>
              </div>
              <Badge
                variant="outline"
                className={`text-[10px] shrink-0 ml-2 ${
                  VENDOR_TYPE_BADGE[tech.vendor_type] || ""
                }`}
              >
                {VENDOR_TYPE_LABELS[tech.vendor_type] || tech.vendor_type}
              </Badge>
            </div>

            <div className="flex items-center justify-between mt-3">
              <div className="text-xs text-muted-foreground">
                Confidence:{" "}
                <span className={`font-medium ${risk.color}`}>
                  {tech.confidence}%
                </span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-12 h-1.5 bg-border/30 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      tech.confidence >= 80
                        ? "bg-red-400"
                        : tech.confidence >= 50
                        ? "bg-yellow-400"
                        : "bg-green-400"
                    }`}
                    style={{ width: `${tech.confidence}%` }}
                  />
                </div>
                <span className={`text-[10px] ${risk.color}`}>{risk.label}</span>
              </div>
            </div>

            {tech.version && (
              <div className="mt-2 text-[10px] text-muted-foreground">
                v{tech.version}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
