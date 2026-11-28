"use client";

import { Suspense } from "react";
import { ScanForm } from "@/components/scan/ScanForm";
import { ScannerV2Panel } from "@/components/scan/ScannerV2Panel";
import { ArrowLeft, Radar, ScanSearch, Workflow } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { cn } from "@/lib/utils";

type Engine = "standard" | "v2";

const ENGINES: { id: Engine; title: string; description: string; icon: typeof ScanSearch }[] = [
  {
    id: "standard",
    title: "Standard scan",
    description: "Quick, full or custom scan. Results are saved to Scans.",
    icon: ScanSearch,
  },
  {
    id: "v2",
    title: "Scanner v2",
    description: "Deep recon pipeline. Watch each stage resolve live.",
    icon: Workflow,
  },
];

function NewScanContent() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const engine: Engine = params.get("engine") === "v2" ? "v2" : "standard";

  const choose = (next: Engine) => {
    router.replace(next === "v2" ? `${pathname}?engine=v2` : pathname, { scroll: false });
  };

  return (
    <div className={engine === "v2" ? "page-container" : "page-container-sm"}>
      <div className="py-6">
        <PageHeader
          title="New Scan"
          description="Start a new attack surface scan"
          icon={<Radar className="h-5 w-5" />}
          breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "Scans", href: "/scans" }, { label: "New Scan" }]}
          actions={
            <Link href="/scans">
              <Button variant="ghost" size="icon" className="rounded-xl" aria-label="Back to scans">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
          }
        />

        <div role="radiogroup" aria-label="Scanner" className="mt-8 grid gap-3 sm:grid-cols-2">
          {ENGINES.map((e) => {
            const selected = engine === e.id;
            return (
              <button
                key={e.id}
                type="button"
                role="radio"
                aria-checked={selected}
                data-testid={`scanner-choice-${e.id}`}
                onClick={() => choose(e.id)}
                className={cn(
                  "flex items-start gap-3 rounded-lg border p-4 text-left transition-colors",
                  selected
                    ? "border-primary bg-primary/10"
                    : "border-border bg-card hover:border-primary/50 hover:bg-muted/40"
                )}
              >
                <span
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-md",
                    selected ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"
                  )}
                >
                  <e.icon className="h-4 w-4" />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-foreground">{e.title}</span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">{e.description}</span>
                </span>
              </button>
            );
          })}
        </div>

        <div className="mt-6">{engine === "v2" ? <ScannerV2Panel /> : <ScanForm />}</div>
      </div>
    </div>
  );
}

export default function NewScanPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={null}>
        <NewScanContent />
      </Suspense>
    </ProtectedRoute>
  );
}
