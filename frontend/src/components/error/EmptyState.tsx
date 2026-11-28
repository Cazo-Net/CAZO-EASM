"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Search, Plus, ArrowRight } from "lucide-react";
import Link from "next/link";

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: { label: string; href: string; icon?: React.ReactNode };
  tips?: string[];
  className?: string;
}

export function EmptyState({ title, description, icon, action, tips, className }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className={cn(
        "flex flex-col items-center rounded-xl border border-border bg-card px-8 py-16 text-center",
        className
      )}
    >
      <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-brand/10 text-brand">
        {icon || <Search className="h-7 w-7" />}
      </div>

      <h3 className="mt-6 text-lg font-semibold text-foreground">{title}</h3>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">{description}</p>

      {action && (
        <Link
          href={action.href}
          className="mt-6 inline-flex items-center gap-2 rounded-xl bg-brand px-6 py-3 text-sm font-semibold text-white transition-all hover:bg-brand/90 hover:shadow-brand/30"
        >
          {action.icon || <Plus className="h-4 w-4" />}
          {action.label}
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      )}

      {tips && tips.length > 0 && (
        <div className="mt-8 w-full max-w-sm rounded-xl border border-border bg-card p-4 text-left">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Tips
          </p>
          <ul className="space-y-1.5">
            {tips.map((tip) => (
              <li key={tip} className="flex items-start gap-2 text-xs text-muted-foreground">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-brand/50" />
                {tip}
              </li>
            ))}
          </ul>
        </div>
      )}
    </motion.div>
  );
}
