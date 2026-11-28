"use client";

import { Radar } from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { ScannerV2Panel } from "@/components/scan/ScannerV2Panel";

export default function ScannerV2Page() {
  return (
    <ProtectedRoute>
      <div className="page-container">
        <div className="py-6">
          <PageHeader
            title="Scanner v2"
            description="Deep recon pipeline — watch each stage resolve in real time"
            icon={<Radar className="h-5 w-5" />}
            breadcrumbs={[
              { label: "Home", href: "/dashboard" },
              { label: "Scans", href: "/scans" },
              { label: "Scanner v2" },
            ]}
          />
          <div className="mt-8">
            <ScannerV2Panel />
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
