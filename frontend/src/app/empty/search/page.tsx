"use client";

import { EmptyState } from "@/components/error";
import { Search } from "lucide-react";
import Link from "next/link";

export default function EmptySearchPage() {
  return (
    <div className="min-h-screen bg-background px-4 py-12">
      <div className="mx-auto max-w-lg">
        <EmptyState
          title="No Results Found"
          description="No results match your search query. Try adjusting your filters or search terms."
          icon={<Search className="h-7 w-7" />}
          action={{ label: "Clear Search", href: "/dashboard" }}
          tips={[
            "Check for typos in your search terms",
            "Try using fewer or different keywords",
            "Clear any active filters and try again",
          ]}
        />
      </div>
    </div>
  );
}
