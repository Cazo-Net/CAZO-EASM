"use client";

import { ErrorLayout } from "@/components/error";
import { errorConfigs } from "@/types/errorConfigs";

export function ErrorPage({ code }: { code: string }) {
  const config = errorConfigs[code];
  if (!config) return null;
  return <ErrorLayout config={config} />;
}
