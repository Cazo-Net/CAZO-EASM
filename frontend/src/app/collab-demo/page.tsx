"use client";

import { ProtectedRoute } from "@/components/ProtectedRoute";
import * as React from "react";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { CommentThread } from "@/components/collab/CommentThread";
import { MessagesSquare } from "lucide-react";

function CollabDemoContent() {
  const params = useSearchParams();
  const [assetId, setAssetId] = React.useState(params.get("assetId") || "");

  return (
    <SectionCard title="Asset Comments">
      <div className="mb-4 flex items-center gap-2">
        <input
          value={assetId}
          onChange={(e) => setAssetId(e.target.value)}
          placeholder="Enter assetId…"
          className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-brand"
        />
      </div>
      {assetId ? (
        <CommentThread assetId={assetId} />
      ) : (
        <p className="text-sm text-muted-foreground">
          Provide an assetId (or use ?assetId=…) to view comments.
        </p>
      )}
    </SectionCard>
  );
}

function CollabDemoShell() {
  return (
    <div className="page-container-md">
      <PageHeader
        title="Team Collaboration Demo"
        description="Discuss findings with your team. Tag assets, leave notes."
        icon={<MessagesSquare className="h-5 w-5" />}
      />
      <Suspense fallback={<div className="text-sm text-muted-foreground">Loading…</div>}>
        <CollabDemoContent />
      </Suspense>
    </div>
  );
}

export default function CollabDemoPage() {
  return (
    <ProtectedRoute>
      <CollabDemoShell />
    </ProtectedRoute>
  );
}
