"use client";

import * as React from "react";
import { useAuth } from "@/contexts/AuthContext";
import { getAssetComments, createAssetComment, deleteComment } from "@/lib/api-collab";
import { getErrorMessage } from "@/lib/api";
import type { AssetComment } from "@/types/collab";
import { cn } from "@/lib/utils";

function formatTime(value: string | null): string {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString();
}

function authorLabel(email: string | null, name: string | null): string {
  if (name) return name;
  if (email) return email;
  return "Unknown";
}

export function CommentThread({ assetId }: { assetId: string }) {
  const { user } = useAuth();
  const [comments, setComments] = React.useState<AssetComment[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [content, setContent] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [replyTo, setReplyTo] = React.useState<string | null>(null);
  const [replyContent, setReplyContent] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAssetComments(assetId);
      setComments(data);
    } catch (e) {
      setError(getErrorMessage(e, "Failed to load comments"));
    } finally {
      setLoading(false);
    }
  }, [assetId]);

  React.useEffect(() => {
    load();
  }, [load]);

  async function post() {
    if (!content.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await createAssetComment(assetId, content.trim());
      setContent("");
      await load();
    } catch (e) {
      setError(getErrorMessage(e, "Failed to post comment"));
    } finally {
      setSubmitting(false);
    }
  }

  async function postReply(parentId: string) {
    if (!replyContent.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await createAssetComment(assetId, replyContent.trim(), parentId);
      setReplyContent("");
      setReplyTo(null);
      await load();
    } catch (e) {
      setError(getErrorMessage(e, "Failed to post reply"));
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(id: string) {
    setError(null);
    try {
      await deleteComment(id);
      await load();
    } catch (e) {
      setError(getErrorMessage(e, "Failed to delete comment"));
    }
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading comments…</p>;
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-border bg-surface-2 p-3">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Add a comment…"
          rows={3}
          className="w-full resize-none rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <div className="mt-2 flex justify-end">
          <button
            onClick={post}
            disabled={submitting || !content.trim()}
            className="rounded-lg bg-brand px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-brand/90 disabled:opacity-50"
          >
            Comment
          </button>
        </div>
      </div>

      {comments.length === 0 ? (
        <p className="text-sm text-muted-foreground">No comments yet. Start the discussion.</p>
      ) : (
        <ul className="space-y-3">
          {comments.map((c) => (
            <li key={c.id} className="rounded-xl border border-border bg-card p-3">
              <div className="flex items-center justify-between">
                <div className="text-sm">
                  <span className="font-medium">{authorLabel(c.author_email, c.author_name)}</span>
                  <span className="ml-2 text-xs text-muted-foreground">{formatTime(c.created_at)}</span>
                </div>
                <div className="flex items-center gap-3 text-xs">
                  <button
                    className="text-brand hover:underline"
                    onClick={() => {
                      setReplyTo(replyTo === c.id ? null : c.id);
                      setReplyContent("");
                    }}
                  >
                    Reply
                  </button>
                  {(user?.id === c.user_id || user?.role === "owner" || user?.role === "admin") && (
                    <button className="text-destructive hover:underline" onClick={() => remove(c.id)}>
                      Delete
                    </button>
                  )}
                </div>
              </div>
              <p className="mt-1 whitespace-pre-wrap text-sm">{c.content}</p>

              {replyTo === c.id && (
                <div className="mt-2 rounded-lg border border-border bg-surface-2 p-2">
                  <textarea
                    value={replyContent}
                    onChange={(e) => setReplyContent(e.target.value)}
                    placeholder="Write a reply…"
                    rows={2}
                    className="w-full resize-none rounded-lg border border-border bg-card px-2 py-1.5 text-sm outline-none focus:border-brand"
                  />
                  <div className="mt-2 flex justify-end gap-2">
                    <button
                      className="rounded-lg px-3 py-1 text-xs text-muted-foreground hover:underline"
                      onClick={() => setReplyTo(null)}
                    >
                      Cancel
                    </button>
                    <button
                      className="rounded-lg bg-brand px-3 py-1 text-xs font-medium text-white hover:bg-brand/90 disabled:opacity-50"
                      disabled={submitting || !replyContent.trim()}
                      onClick={() => postReply(c.id)}
                    >
                      Reply
                    </button>
                  </div>
                </div>
              )}

              {c.replies.length > 0 && (
                <ul className="mt-3 space-y-2 border-l-2 border-border pl-3">
                  {c.replies.map((r) => (
                    <li key={r.id}>
                      <div className="flex items-center justify-between">
                        <div className="text-sm">
                          <span className="font-medium">{authorLabel(r.author_email, r.author_name)}</span>
                          <span className="ml-2 text-xs text-muted-foreground">{formatTime(r.created_at)}</span>
                        </div>
                        {(user?.id === r.user_id || user?.role === "owner" || user?.role === "admin") && (
                          <button className="text-xs text-destructive hover:underline" onClick={() => remove(r.id)}>
                            Delete
                          </button>
                        )}
                      </div>
                      <p className="mt-1 whitespace-pre-wrap text-sm">{r.content}</p>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
