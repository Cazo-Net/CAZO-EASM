"use client";

import { SectionCard } from "@/components/common/SectionCard";
import { Badge } from "@/components/ui/badge";
import { ArrowRight } from "lucide-react";

interface Technology {
  name: string;
  category: string;
  vendor_type: string;
  confidence: number;
}

interface DataFlowDiagramProps {
  technologies: Technology[];
  categoryCounts: Record<string, number>;
}

const VENDOR_TYPE_BADGE: Record<string, string> = {
  third_party_service: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  saas_platform: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  first_party_infra: "bg-green-500/10 text-green-400 border-green-500/20",
  security_tool: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  cloud_provider: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  devops_tool: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
};

const VENDOR_TYPE_LABELS: Record<string, string> = {
  third_party_service: "Third-Party Service",
  saas_platform: "SaaS Platform",
  first_party_infra: "First-Party Infra",
  security_tool: "Security Tool",
  cloud_provider: "Cloud Provider",
  devops_tool: "DevOps Tool",
};

export function DataFlowDiagram({ technologies, categoryCounts }: DataFlowDiagramProps) {
  // Group by vendor type
  const byVendorType: Record<string, Technology[]> = {};
  technologies.forEach((t) => {
    const vt = t.vendor_type || "unknown";
    if (!byVendorType[vt]) byVendorType[vt] = [];
    byVendorType[vt].push(t);
  });

  const sortedCategories = Object.entries(categoryCounts)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 12);

  return (
    <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Data flow table */}
      <SectionCard title="Data Flow Summary" icon={<ArrowRight className="h-4 w-4" />}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 text-muted-foreground font-medium">Service</th>
                <th className="text-left py-2 text-muted-foreground font-medium">Type</th>
                <th className="text-left py-2 text-muted-foreground font-medium">Data Category</th>
                <th className="text-right py-2 text-muted-foreground font-medium">Risk</th>
              </tr>
            </thead>
            <tbody>
              {technologies.slice(0, 20).map((tech, i) => {
                const risk =
                  tech.confidence >= 80
                    ? { label: "High", color: "text-red-400" }
                    : tech.confidence >= 50
                    ? { label: "Medium", color: "text-yellow-400" }
                    : { label: "Low", color: "text-green-400" };
                return (
                  <tr key={`${tech.name}-${i}`} className="border-b border-border">
                    <td className="py-2 font-medium">{tech.name}</td>
                    <td className="py-2">
                      <Badge
                        variant="outline"
                        className={`text-[10px] ${
                          VENDOR_TYPE_BADGE[tech.vendor_type] || ""
                        }`}
                      >
                        {VENDOR_TYPE_LABELS[tech.vendor_type] || tech.vendor_type}
                      </Badge>
                    </td>
                    <td className="py-2 text-muted-foreground">{tech.category}</td>
                    <td className={`py-2 text-right font-medium ${risk.color}`}>
                      {risk.label}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {technologies.length > 20 && (
            <div className="text-center text-[10px] text-muted-foreground mt-2">
              Showing 20 of {technologies.length} services
            </div>
          )}
        </div>
      </SectionCard>

      {/* Category breakdown */}
      <SectionCard title="Service Categories" icon={<ArrowRight className="h-4 w-4" />}>
        <div className="space-y-2">
          {sortedCategories.map(([category, count]) => (
            <div key={category} className="flex items-center gap-3">
              <div className="w-32 text-xs text-muted-foreground truncate">
                {category}
              </div>
              <div className="flex-1 h-1.5 bg-border/30 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary/60 rounded-full"
                  style={{
                    width: `${(count / Math.max(...sortedCategories.map(([, c]) => c))) * 100}%`,
                  }}
                />
              </div>
              <div className="w-8 text-right text-xs text-muted-foreground">
                {count}
              </div>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}
