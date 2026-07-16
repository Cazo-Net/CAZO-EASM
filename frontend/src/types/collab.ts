export interface AssetCommentReply {
  id: string;
  organization_id: string;
  asset_id: string;
  user_id: string;
  author_email: string | null;
  author_name: string | null;
  content: string;
  parent_id: string | null;
  created_at: string | null;
}

export interface AssetComment {
  id: string;
  organization_id: string;
  asset_id: string;
  user_id: string;
  author_email: string | null;
  author_name: string | null;
  content: string;
  parent_id: string | null;
  created_at: string | null;
  replies: AssetCommentReply[];
}
