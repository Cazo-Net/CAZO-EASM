import api from "@/lib/api";
import type { Asset360Response, Asset360ListItem, HostIntelligence } from "@/types/asset360";

export async function getAsset360(assetId: string): Promise<Asset360Response> {
  const { data } = await api.get(`/asset360/${assetId}`);
  return data;
}

export async function listAssets360(params?: {
  skip?: number;
  limit?: number;
}): Promise<Asset360ListItem[]> {
  const { data } = await api.get("/asset360", {
    params: { skip: 0, limit: 50, ...params },
  });
  return data;
}

export async function getHostIntelligence(
  assetId: string
): Promise<HostIntelligence> {
  const { data } = await api.get(`/assets/host/${assetId}`);
  return data;
}
