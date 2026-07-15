"use client";

import { ScanForm } from "@/components/scan/ScanForm";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ProtectedRoute } from "@/components/ProtectedRoute";

function NewScanContent() {
  return (
    <div className="min-h-screen">
      <div className="border-b bg-card/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="mx-auto max-w-2xl px-6 py-5">
          <div className="flex items-center gap-3">
            <Link href="/scans">
              <Button variant="ghost" size="icon" className="rounded-xl">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#09090B] border border-border/50 overflow-hidden">
                <img src="/icon.ico" alt="AttackSec" className="h-7 w-7 object-contain" />
              </div>
              <div>
                <h1 className="text-lg font-bold tracking-tight">
                  New Scan
                </h1>
                <p className="text-xs text-muted-foreground">
                  Start a new attack surface scan
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-2xl px-6 py-12">
        <ScanForm />
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
