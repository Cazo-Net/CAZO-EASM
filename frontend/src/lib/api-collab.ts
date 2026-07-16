import api from "@/lib/api";
import type { AssetComment } from "@/types/collab";

export async function getAssetComments(assetId: string): Promise<AssetComment[]> {
  const { data } = await api.get(`/collaboration/assets/${assetId}/comments`);
  return data;
}

export async function createAssetComment(
  assetId: string,
  content: string,
  parentId?: string
): Promise<AssetComment> {
  const { data } = await api.post(`/collaboration/assets/${assetId}/comments`, {
    content,
    parent_id: parentId,
  });
  return data;
}

export async function deleteComment(commentId: string): Promise<{ message: string; id: string }> {
  const { data } = await api.delete(`/collaboration/comments/${commentId}`);
  return data;
}
