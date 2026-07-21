"use client";

import { ErrorLayout } from "@/components/error";
import { statusPageConfigs } from "@/types/errorConfigs";

export function StatusPage({ type }: { type: string }) {
  const config = statusPageConfigs[type];
  if (!config) return null;
  return <ErrorLayout config={config} />;
}
