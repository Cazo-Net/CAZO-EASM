"use client";

interface RiskSummaryProps {
  vendorTypeCounts: Record<string, number>;
}

const VENDOR_TYPE_RISKS: Record<string, { label: string; risk: "high" | "medium" | "low"; color: string }> = {
  third_party_service: { label: "Third-Party Services", risk: "high", color: "bg-red-400" },
  saas_platform: { label: "SaaS Platforms", risk: "medium", color: "bg-yellow-400" },
  security_tool: { label: "Security Tools", risk: "medium", color: "bg-orange-400" },
  cloud_provider: { label: "Cloud Providers", risk: "medium", color: "bg-blue-400" },
  devops_tool: { label: "DevOps Tools", risk: "low", color: "bg-green-400" },
  first_party_infra: { label: "First-Party Infrastructure", risk: "low", color: "bg-green-400" },
};

const RISK_COLORS = {
  high: { bar: "bg-red-400", text: "text-red-400", border: "border-red-500/20" },
  medium: { bar: "bg-yellow-400", text: "text-yellow-400", border: "border-yellow-500/20" },
  low: { bar: "bg-green-400", text: "text-green-400", border: "border-green-500/20" },
};

export function RiskSummary({ vendorTypeCounts }: RiskSummaryProps) {
  const entries = Object.entries(vendorTypeCounts)
    .map(([type, count]) => ({
      type,
      count,
      ...VENDOR_TYPE_RISKS[type] || { label: type, risk: "low" as const, color: "bg-gray-400" },
    }))
    .sort((a, b) => {
      const riskOrder = { high: 0, medium: 1, low: 2 };
      return riskOrder[a.risk] - riskOrder[b.risk] || b.count - a.count;
    });

  const maxCount = Math.max(...entries.map((e) => e.count), 1);

  if (entries.length === 0) return null;

  return (
    <div className="mt-6 border border-border/50 rounded-lg p-4 bg-muted/5">
      <h3 className="text-sm font-medium mb-4">Vendor Concentration Risk</h3>
      <div className="space-y-3">
        {entries.map((entry) => {
          const riskStyle = RISK_COLORS[entry.risk];
          const percentage = (entry.count / maxCount) * 100;
          return (
            <div key={entry.type} className="flex items-center gap-3">
              <div className="w-40 text-xs text-muted-foreground truncate">
                {entry.label}
              </div>
              <div className="flex-1 h-2 bg-border/30 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${riskStyle.bar}`}
                  style={{ width: `${percentage}%` }}
                />
              </div>
              <div className="w-16 text-right text-xs">
                <span className={`font-medium ${riskStyle.text}`}>{entry.count}</span>
                <span className="text-muted-foreground ml-1">services</span>
              </div>
              <div
                className={`w-14 text-center text-[10px] px-1.5 py-0.5 rounded border ${riskStyle.border} ${riskStyle.text}`}
              >
                {entry.risk}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
