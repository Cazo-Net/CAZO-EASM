"use client";

import { EmptyState } from "@/components/error";
import { Search } from "lucide-react";
import Link from "next/link";

export default function EmptySearchPage() {
  return (
    <div className="min-h-screen bg-background px-4 py-12">
      <div className="mx-auto max-w-lg">
        <EmptyState
          title="No results"
          description="Nothing matched your query. Try a different search term or adjust your filters."
          icon={<Search className="h-7 w-7" />}
          action={{ label: "Clear Search", href: "/dashboard" }}
          tips={[
            "Check for typos",
            "Try broader keywords",
            "Clear any active filters",
          ]}
        />
      </div>
    </div>
  );
}
