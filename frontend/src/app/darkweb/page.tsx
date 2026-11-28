"use client";

import { useCallback, useState } from "react";
import {
  Search,
  Loader2,
  AlertTriangle,
  Shield,
  Eye,
  FileText,
  Globe,
  Lock,
  Database,
  Radio,
  Newspaper,
  MessageSquare,
  RotateCcw,
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useDarkWebStore } from "@/lib/darkwebStore";

const SOURCE_ICONS: Record<string, any> = {
  tor_search: Globe,
  onion_crawl: Lock,
  marketplace: Database,
  forum: MessageSquare,
  paste_site: FileText,
  telegram: Radio,
  irc: Radio,
  feed: Newspaper,
};

const THREAT_COLORS: Record<string, string> = {
  critical: "text-destructive bg-destructive/10 border-red-500/20",
  high: "text-orange-400 bg-orange-500/10 border-orange-500/20",
  medium: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
  low: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  info: "text-success bg-success/10 border-green-500/20",
};

const CONTENT_TYPE_LABELS: Record<string, string> = {
  credential: "Credential Exposure",
  data_dump: "Data Dump",
  malware: "Malware",
  exploit: "Exploit",
  marketplace_listing: "Marketplace Listing",
  forum_post: "Forum Post",
  announcement: "Announcement",
  contact: "Contact",
  other: "Other",
};

function DarkWebContent() {
  const {
    searchQuery,
    searchResults,
    searchLoading,
    searchError,
    monitors,
    monitorsLoading,
    search,
    loadMonitors,
    reset,
  } = useDarkWebStore();

  const [localQuery, setLocalQuery] = useState(searchQuery);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (localQuery.trim()) {
        search(localQuery);
      }
    },
    [localQuery, search]
  );

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <PageHeader
          title="Dark Web Intelligence"
          description="Monitor dark web mentions, credential exposures, and threat actor activity"
          icon={<Eye className="h-5 w-5" />}
        />

        {/* Search */}
        <SectionCard title="Dark Web Search" icon={<Search className="h-4 w-4" />} className="mt-6">
          <form onSubmit={handleSearch} className="flex gap-3">
            <Input
              placeholder="Search domains, emails, brands, or keywords..."
              value={localQuery}
              onChange={(e) => setLocalQuery(e.target.value)}
              className="flex-1"
            />
            <Button type="submit" disabled={searchLoading || !localQuery.trim()}>
              {searchLoading ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Search className="w-4 h-4 mr-2" />
              )}
              Search
            </Button>
          </form>

          {/* Quick search examples */}
          {!searchResults && !searchLoading && (
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="text-xs text-muted-foreground mr-1">Try:</span>
              {["example.com", "company breach", "leaked credentials", "ransomware"].map((q) => (
                <button
                  key={q}
                  onClick={() => {
                    setLocalQuery(q);
                    search(q);
                  }}
                  className="text-xs text-muted-foreground hover:text-foreground border border-border rounded px-2 py-1 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          )}
        </SectionCard>

        {/* Error */}
        {searchError && (
          <div className="mt-4 p-4 border border-red-500/20 bg-red-500/5 rounded-lg text-destructive text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            {searchError}
          </div>
        )}

        {/* Search Results */}
        {searchResults && (
          <div className="mt-6">
            <SectionCard title="Search Results" icon={<Eye className="h-4 w-4" />}>
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm text-muted-foreground">
                  {searchResults.total} results for &ldquo;{searchResults.query}&rdquo;
                </span>
                <Button variant="outline" size="sm" onClick={reset}>
                  <RotateCcw className="w-4 h-4 mr-1" />
                  Clear
                </Button>
              </div>

              {searchResults.results.length > 0 ? (
                <div className="space-y-3">
                  {searchResults.results.map((result) => {
                    const SourceIcon = SOURCE_ICONS[result.source] || Globe;
                    const threatColor = THREAT_COLORS[result.threat_level] || THREAT_COLORS.info;
                    return (
                      <div
                        key={result.id}
                        className="border border-border rounded-lg p-4 hover:bg-muted/20 transition-colors"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex items-start gap-3 flex-1 min-w-0">
                            <SourceIcon className="w-5 h-5 text-muted-foreground mt-0.5 shrink-0" />
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium truncate">
                                  {result.title || result.source_url}
                                </span>
                                <Badge variant="outline" className="text-[10px] shrink-0">
                                  {CONTENT_TYPE_LABELS[result.content_type] || result.content_type}
                                </Badge>
                              </div>
                              {result.summary && (
                                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                  {result.summary}
                                </p>
                              )}
                              <div className="flex items-center gap-3 mt-2">
                                <span className="text-[10px] text-muted-foreground">
                                  Source: {result.source}
                                </span>
                                <span className="text-[10px] text-muted-foreground">
                                  Confidence: {result.confidence}%
                                </span>
                                <span className="text-[10px] text-muted-foreground">
                                  {new Date(result.discovered_at).toLocaleDateString()}
                                </span>
                              </div>
                              {result.keywords.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-2">
                                  {result.keywords.slice(0, 5).map((kw) => (
                                    <span
                                      key={kw}
                                      className="text-[10px] px-1.5 py-0.5 bg-muted rounded"
                                    >
                                      {kw}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                          <Badge variant="outline" className={`text-[10px] shrink-0 ${threatColor}`}>
                            {result.threat_level}
                          </Badge>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <EmptyState
                  icon={<Search className="h-8 w-8" />}
                  title="No results found"
                  description="Try different keywords or broaden your search."
                />
              )}
            </SectionCard>
          </div>
        )}

        {/* Empty state */}
        {!searchResults && !searchLoading && !searchError && (
          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-destructive/10 rounded-lg">
                    <Shield className="w-5 h-5 text-destructive" />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium">Credential Monitoring</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Detect leaked credentials before they&apos;re exploited.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-orange-500/10 rounded-lg">
                    <Eye className="w-5 h-5 text-orange-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium">Threat Intelligence</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Track threat actors and emerging attack campaigns.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-500/10 rounded-lg">
                    <Globe className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium">Onion Service Discovery</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Identify unauthorized .onion services and dark web exposure.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DarkWebPage() {
  return (
    <ProtectedRoute>
      <DarkWebContent />
    </ProtectedRoute>
  );
}
