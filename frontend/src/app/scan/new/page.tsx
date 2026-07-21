"use client";

import { ScanForm } from "@/components/scan/ScanForm";
import { ArrowLeft, Radar } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";

function NewScanContent() {
  return (
    <div className="page-container-sm">
      <div className="py-6">
        <PageHeader
          title="New Scan"
          description="Start a new attack surface scan"
          icon={<Radar className="h-5 w-5" />}
          breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "Scans", href: "/scans" }, { label: "New Scan" }]}
          actions={
            <Link href="/scans">
              <Button variant="ghost" size="icon" className="rounded-xl">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
          }
        />
        <div className="mt-8">
          <ScanForm />
        </div>
      </div>
    </div>
  );
}

export default function NewScanPage() {
  return (
    <ProtectedRoute>
      <NewScanContent />
    </ProtectedRoute>
  );
}
