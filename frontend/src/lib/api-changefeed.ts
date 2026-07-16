import api from "@/lib/api";
import type { ChangeFeedItem, ChangeFeedSummary } from "@/types/changefeed";

export async function listChangeFeed(limit = 50): Promise<ChangeFeedItem[]> {
  const { data } = await api.get("/changefeed", { params: { limit } });
  return data;
}

export async function getChangeFeedSummary(): Promise<ChangeFeedSummary> {
  const { data } = await api.get("/changefeed/summary");
  return data;
}
