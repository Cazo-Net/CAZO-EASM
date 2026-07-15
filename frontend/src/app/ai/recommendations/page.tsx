"use client";

import { useEffect, useState } from "react";
import {
  Lightbulb,
  Loader2,
  RefreshCw,
  Check,
  X,
  AlertTriangle,
  Info,
  Shield,
} from "lucide-react";
import { motion } from "framer-motion";
import { getAIRecommendations, dismissAIRecommendation } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import type { AIRecommendation } from "@/types";

const priorityConfig: Record<string, { color: string; bg: string; icon: any }> = {
  critical: { color: "text-red-400", bg: "bg-red-500/10", icon: AlertTriangle },
  high: { color: "text-amber-400", bg: "bg-amber-500/10", icon: AlertTriangle },
  medium: { color: "text-blue-400", bg: "bg-blue-500/10", icon: Info },
  low: { color: "text-muted-foreground", bg: "bg-muted/50", icon: Info },
};

function RecommendationsContent() {
  const [recommendations, setRecommendations] = useState<AIRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    loadRecommendations();
  }, []);

  const loadRecommendations = async () => {
    setLoading(true);
    try {
      const data = await getAIRecommendations();
      setRecommendations(data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const data = await getAIRecommendations();
      setRecommendations(data);
    } catch {
      // silently fail
    } finally {
      setGenerating(false);
    }
  };

  const handleDismiss = async (id: string) => {
    try {
      await dismissAIRecommendation(id);
      setRecommendations((prev) => prev.filter((r) => r.id !== id));
    } catch {
      // silently fail
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <div className="border-b border-border/50 bg-card/30 backdrop-blur-xl sticky top-0 z-10">
        <div className="mx-auto max-w-4xl px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                <Lightbulb className="h-6 w-6 text-amber-400" />
                Recommendations
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                AI-powered suggestions to improve your security posture.
              </p>
            </div>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-2 rounded-lg bg-primary/10 px-3 py-2 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
            >
              {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              Generate
            </button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-6 py-8">
        {recommendations.length === 0 ? (
          <div className="flex flex-col items-center py-24 text-center">
            <Lightbulb className="h-12 w-12 text-muted-foreground/30 mb-4" />
            <h3 className="text-lg font-semibold mb-2">No recommendations yet</h3>
            <p className="text-sm text-muted-foreground mb-6">
              Click Generate to get AI-powered recommendations based on your platform data.
            </p>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lightbulb className="h-4 w-4" />}
              Generate Recommendations
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {recommendations.map((rec) => {
              const config = priorityConfig[rec.priority] || priorityConfig.medium;
              const Icon = config.icon;
              return (
                <motion.div
                  key={rec.id}
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-xl border border-border/50 bg-card/60 p-5"
                >
                  <div className="flex items-start gap-3">
                    <div className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", config.bg)}>
                      <Icon className={cn("h-4 w-4", config.color)} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="text-sm font-semibold">{rec.title}</h3>
                        <button
                          onClick={() => handleDismiss(rec.id)}
                          className="shrink-0 p-1 rounded hover:bg-muted/30 text-muted-foreground hover:text-foreground transition-colors"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">{rec.description}</p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-medium",
                          config.bg, config.color
                        )}>
                          {rec.priority}
                        </span>
                        <span className="text-[10px] text-muted-foreground">{rec.category}</span>
                        {rec.entity_type && (
                          <span className="text-[10px] text-muted-foreground">· {rec.entity_type}</span>
                        )}
                      </div>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AIRecommendationsPage() {
  return (
    <ProtectedRoute>
      <RecommendationsContent />
    </ProtectedRoute>
  );
}
