"use client";

import {
  AlertTriangle,
  CheckCircle,
  Info,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

interface Finding {
  category: string;
  detail: string;
  points: number;
}

interface FindingsTableProps {
  findings: Finding[];
}

function severityConfig(points: number) {
  if (points >= 25)
    return {
      icon: AlertTriangle,
      iconColor: "text-red-500",
      badge: "destructive" as const,
    };
  if (points >= 15)
    return {
      icon: AlertTriangle,
      iconColor: "text-orange-500",
      badge: "warning" as const,
    };
  if (points > 0)
    return {
      icon: Info,
      iconColor: "text-amber-500",
      badge: "warning" as const,
    };
  return {
    icon: CheckCircle,
    iconColor: "text-success",
    badge: "success" as const,
  };
}

export function FindingsTable({ findings }: FindingsTableProps) {
  const [expanded, setExpanded] = useState(true);

  if (findings.length === 0) {
    return (
      <div className="rounded-xl border bg-card p-8 text-center shadow-sm">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
          <CheckCircle className="h-6 w-6 text-success" />
        </div>
        <p className="font-medium">No issues found</p>
        <p className="text-sm text-muted-foreground">
          Your scan came back clean
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between p-4 text-left hover:bg-muted/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <h3 className="font-semibold">Security Findings</h3>
          <Badge variant="secondary">{findings.length}</Badge>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {expanded && (
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead className="w-12">Severity</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Detail</TableHead>
              <TableHead className="text-right w-20">Points</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {findings.map((f, i) => {
              const config = severityConfig(f.points);
              const Icon = config.icon;
              return (
                <TableRow key={i}>
                  <TableCell>
                    <Icon className={`h-4 w-4 ${config.iconColor}`} />
                  </TableCell>
                  <TableCell>
                    <Badge variant={config.badge}>
                      {f.category.replace(/_/g, " ")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm">{f.detail}</TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    +{f.points}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
