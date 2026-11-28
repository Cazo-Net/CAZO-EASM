"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Radar,
  CheckCircle,
  Circle,
  X,
  ArrowRight,
  Shield,
  Bug,
  Network,
  Bell,
  Settings,
  FileText,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ChecklistItem {
  id: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
  hrefLabel: string;
}

const CHECKLIST_ITEMS: ChecklistItem[] = [
  {
    id: "first_scan",
    label: "Run your first scan",
    description: "Enter a domain and let the engine map your surface.",
    icon: Radar,
    href: "/scans",
    hrefLabel: "Open Scans",
  },
  {
    id: "review_findings",
    label: "Review your findings",
    description: "Sort by severity, check what matters most.",
    icon: Bug,
    href: "/vulnerabilities",
    hrefLabel: "View Findings",
  },
  {
    id: "evidence_panel",
    label: "Open the Evidence Panel",
    description: "Click a finding, expand the evidence. Understand the data behind each signal.",
    icon: FileText,
    href: "/vulnerabilities",
    hrefLabel: "Open a Finding",
  },
  {
    id: "attack_graph",
    label: "See your attack graph",
    description: "Assets connected by shared infrastructure — your real surface.",
    icon: Network,
    href: "/graph",
    hrefLabel: "View Graph",
  },
  {
    id: "add_scope",
    label: "Add a monitored scope",
    description: "Persistent scopes trigger recurring scans and track drift over time.",
    icon: Shield,
    href: "/scopes",
    hrefLabel: "Manage Scopes",
  },
  {
    id: "notifications",
    label: "Set up notifications",
    description: "Get alerted when new findings appear or scopes drift.",
    icon: Bell,
    href: "/settings",
    hrefLabel: "Configure Alerts",
  },
];

function StepIndicator({ completed }: { completed: boolean }) {
  return completed ? (
    <CheckCircle className="h-4 w-4 text-phosphor shrink-0" />
  ) : (
    <Circle className="h-4 w-4 text-muted-foreground shrink-0" />
  );
}

export function GettingStartedChecklist() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, updateOnboardingState } = useAuth();
  const [dismissed, setDismissed] = useState(false);

  const onboarding = (user?.preferences as any)?.onboarding;
  const completedSteps: string[] = onboarding?.checklist_completed || [];
  const isDismissed = onboarding?.checklist_dismissed === true;

  // Don't show if dismissed or if onboarding wizard not completed
  if (isDismissed || !onboarding?.completed) {
    return null;
  }

  const allComplete = CHECKLIST_ITEMS.every((item) =>
    completedSteps.includes(item.id)
  );

  if (allComplete) {
    return null;
  }

  const completedCount = CHECKLIST_ITEMS.filter((item) =>
    completedSteps.includes(item.id)
  ).length;

  const handleDismiss = async () => {
    setDismissed(true);
    await updateOnboardingState({ checklist_dismissed: true });
  };

  const handleStepClick = (item: ChecklistItem) => {
    router.push(item.href);
  };

  const handleMarkComplete = async (itemId: string) => {
    if (completedSteps.includes(itemId)) return;
    await updateOnboardingState({
      checklist_completed: [...completedSteps, itemId],
    });
  };

  // Progress bar
  const progress = (completedCount / CHECKLIST_ITEMS.length) * 100;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border bg-card overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-phosphor/10">
            <Radar className="h-4 w-4 text-phosphor" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">Getting Started</p>
            <p className="text-xs text-muted-foreground">
              {completedCount} of {CHECKLIST_ITEMS.length} complete
            </p>
          </div>
        </div>
        <button
          onClick={handleDismiss}
          className="rounded-md p-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Progress bar */}
      <div className="h-0.5 bg-border/30">
        <motion.div
          className="h-full bg-phosphor"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>

      {/* Steps */}
      <div className="divide-y divide-border/30">
        {CHECKLIST_ITEMS.map((item, i) => {
          const isComplete = completedSteps.includes(item.id);
          const Icon = item.icon;
          return (
            <motion.div
              key={item.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: i * 0.04 }}
              className={cn(
                "flex items-center gap-3 px-5 py-3 transition-colors",
                !isComplete && "hover:bg-muted/30 cursor-pointer"
              )}
              onClick={() => !isComplete && handleStepClick(item)}
            >
              <StepIndicator completed={isComplete} />
              <div className="flex-1 min-w-0">
                <p
                  className={cn(
                    "text-sm font-medium",
                    isComplete ? "text-muted-foreground line-through" : "text-foreground"
                  )}
                >
                  {item.label}
                </p>
                <p className="text-xs text-muted-foreground truncate">
                  {item.description}
                </p>
              </div>
              {!isComplete && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="shrink-0 text-xs h-7"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleStepClick(item);
                  }}
                >
                  {item.hrefLabel}
                  <ArrowRight className="ml-1 h-3 w-3" />
                </Button>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Dismiss */}
      <div className="px-5 py-3 border-t border-border text-center">
        <button
          onClick={handleDismiss}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          Skip getting started
        </button>
      </div>
    </motion.div>
  );
}

// Hook to mark checklist steps as complete from other pages
export function useChecklistAutoComplete() {
  const { user, updateOnboardingState } = useAuth();
  const pathname = usePathname();

  const markComplete = async (stepId: string) => {
    const onboarding = (user?.preferences as any)?.onboarding;
    const completed: string[] = onboarding?.checklist_completed || [];
    if (completed.includes(stepId)) return;
    await updateOnboardingState({
      checklist_completed: [...completed, stepId],
    });
  };

  return { markComplete };
}
