"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { AnimatedBackground } from "./AnimatedBackground";
import { ErrorIllustration } from "./ErrorIllustration";
import { ErrorActions } from "./ErrorActions";
import { ErrorFooter } from "./ErrorFooter";
import { StatusBadge } from "./StatusBadge";
import type { ErrorPageConfig } from "@/types/error";

export function ErrorLayout({ config }: { config: ErrorPageConfig }) {
  return (
    <div className="relative flex min-h-screen flex-col bg-background">
      <AnimatedBackground />

      <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="flex flex-col items-center text-center"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.1 }}
          >
            <ErrorIllustration size="lg" />
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="mt-8"
          >
            <StatusBadge severity={config.severity} label={`Error ${config.code}`} />
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="mt-6 text-7xl font-black tracking-tighter text-foreground sm:text-8xl"
          >
            {config.code}
          </motion.h1>

          <motion.h2
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.5 }}
            className="mt-4 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl"
          >
            {config.title}
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.6 }}
            className="mt-4 max-w-lg text-sm leading-relaxed text-muted-foreground sm:text-base"
          >
            {config.description}
          </motion.p>

          {config.estimatedDowntime && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.7 }}
              className="mt-6 rounded-xl border border-border bg-card px-6 py-4"
            >
              <p className="text-xs text-muted-foreground">Estimated downtime</p>
              <p className="mt-1 text-lg font-semibold text-foreground">{config.estimatedDowntime}</p>
              {config.progress !== undefined && (
                <div className="mt-3 h-1.5 w-48 overflow-hidden rounded-full bg-muted/30">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${config.progress}%` }}
                    transition={{ duration: 1.5, delay: 0.8, ease: "easeOut" }}
                    className="h-full rounded-full bg-brand"
                  />
                </div>
              )}
            </motion.div>
          )}

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.7 }}
            className="mt-8"
          >
            <ErrorActions actions={config.actions} />
          </motion.div>

          {config.helpfulLinks && config.helpfulLinks.length > 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.9 }}
              className="mt-10"
            >
              <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Helpful Links
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {config.helpfulLinks.map((link) => (
                  <a
                    key={link.href}
                    href={link.href}
                    className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-border hover:text-foreground"
                  >
                    {link.label}
                  </a>
                ))}
              </div>
            </motion.div>
          )}
        </motion.div>
      </div>

      <ErrorFooter />
    </div>
  );
}
