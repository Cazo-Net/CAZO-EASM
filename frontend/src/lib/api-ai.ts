// AI Intelligence Engine API client (multi-provider + recommendations).
// Uses the shared axios instance from @/lib/api.

import api from "@/lib/api";
import type {
  ProviderStatusResponse,
  AISettings,
  AIRecommendation,
} from "@/types/ai2";

export async function getAIProviders(): Promise<ProviderStatusResponse> {
  const { data } = await api.get("/ai/providers");
  return data;
}

export async function setAIProvider(
  provider: string,
  model?: string | null
): Promise<AISettings> {
  const { data } = await api.put("/ai/settings/provider", {
    provider,
    model: model ?? undefined,
  });
  return data;
}

export async function getAIRecommendations(
  orgId?: string,
  projectId?: string
): Promise<AIRecommendation[]> {
  const params = new URLSearchParams();
  if (orgId) params.set("org_id", orgId);
  if (projectId) params.set("project_id", projectId);
  const { data } = await api.get(
    `/ai/recommendations${params.toString() ? `?${params.toString()}` : ""}`
  );
  // The existing endpoint returns a RecommendationSet dict; normalize to array.
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.recommendations)) return data.recommendations;
  if (Array.isArray(data?.items)) return data.items;
  return [];
}

export async function getAIRecommendationsForAsset(
  assetId: string
): Promise<AIRecommendation[]> {
  const { data } = await api.get(`/ai/recommendations/asset/${assetId}`);
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.recommendations)) return data.recommendations;
  return [];
}

export async function getAIRecommendationsForScan(
  scanId: string
): Promise<AIRecommendation[]> {
  const { data } = await api.get(`/ai/recommendations/scan/${scanId}`);
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.recommendations)) return data.recommendations;
  return [];
}

export async function dismissAIRecommendation(
  id: string
): Promise<{ id: string; status: string; dismissed: boolean }> {
  const { data } = await api.post(`/ai/recommendations/${id}/dismiss`);
  return data;
}
