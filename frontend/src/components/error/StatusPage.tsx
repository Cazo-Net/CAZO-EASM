"use client";

import { ErrorLayout } from "@/components/error";
import { statusPageConfigs } from "@/types/errorConfigs";

// Routes are kebab-case (/status/session-expired); config keys are camelCase.
const toKey = (type: string) => type.replace(/-([a-z])/g, (_, c: string) => c.toUpperCase());

export function StatusPage({ type }: { type: string }) {
  const config = statusPageConfigs[type] ?? statusPageConfigs[toKey(type)];
  if (!config) return null;
  return <ErrorLayout config={config} />;
}
