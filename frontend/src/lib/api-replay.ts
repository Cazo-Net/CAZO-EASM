// API client for the Exposure Replay feature (real backend data).
import api from "@/lib/api";
import type {
  ReplayTimelineResponse,
  ReplayChangesResponse,
  ReplayExposureResponse,
} from "@/types/replay2";

export async function getReplayTimeline(
  orgId?: string
): Promise<ReplayTimelineResponse> {
  const params = orgId ? { org_id: orgId } : {};
  const { data } = await api.get("/replay/timeline", { params });
  return data;
}

export async function getReplayChanges(
  fromId: string,
  toId: string
): Promise<ReplayChangesResponse> {
  const { data } = await api.get("/replay/changes", {
    params: { from_scan_id: fromId, to_scan_id: toId },
  });
  return data;
}

export async function getReplayExposure(
  scanId: string
): Promise<ReplayExposureResponse> {
  const { data } = await api.get("/replay/exposure", {
    params: { scan_id: scanId },
  });
  return data;
}
