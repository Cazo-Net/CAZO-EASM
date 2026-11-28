"use client";

import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Loader2, Lock, RefreshCw, Trash2, Users } from "lucide-react";
import api, { getErrorMessage } from "@/lib/api";

interface TeamMessage {
  id: string;
  author_email: string;
  author_name: string;
  message: string;
  created_at: string | null;
  mine: boolean;
}

interface Member {
  email: string;
  name: string;
}

const REFRESH_MS = 5000;
const PAGE = 50;
const MAX_LEN = 4000;

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function fmtDay(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return "Today";
  if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
  return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric", year: "numeric" });
}

function initials(name: string): string {
  const parts = name.replace(/@.*/, "").split(/[\s._-]+/).filter(Boolean);
  return ((parts[0]?.[0] || "?") + (parts[1]?.[0] || "")).toUpperCase();
}

// Stable colour per person, from a small palette that reads on the dark theme.
const AVATAR_COLOURS = [
  "bg-blue-500/20 text-blue-300", "bg-emerald-500/20 text-emerald-300", "bg-amber-500/20 text-amber-300",
  "bg-fuchsia-500/20 text-fuchsia-300", "bg-cyan-500/20 text-cyan-300", "bg-rose-500/20 text-rose-300",
];
function avatarColour(email: string): string {
  let h = 0;
  for (let i = 0; i < email.length; i++) h = (h * 31 + email.charCodeAt(i)) >>> 0;
  return AVATAR_COLOURS[h % AVATAR_COLOURS.length];
}

const before = (a: TeamMessage, b: TeamMessage) =>
  (a.created_at || "") < (b.created_at || "") || ((a.created_at || "") === (b.created_at || "") && a.id < b.id);

/**
 * Team chat: one shared room for platform admins. Customers never see it.
 * Messages are plain text, rendered as text (never as HTML or links).
 */
export function TeamChat({ onUnreadChange }: { onUnreadChange?: () => void }) {
  const [messages, setMessages] = useState<TeamMessage[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  // Where the "New" divider goes: the read position when the room was opened.
  const [readMarker, setReadMarker] = useState<string | null | undefined>(undefined);

  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const lastMarked = useRef<string | null>(null);
  const keepOffset = useRef<number | null>(null);
  // Once older pages are loaded, "has more" follows those pages, not the newest one.
  const pagedBack = useRef(false);

  const markRead = useCallback(
    async (latestId: string | undefined) => {
      if (!latestId || latestId === lastMarked.current || document.hidden) return;
      lastMarked.current = latestId;
      try {
        await api.post("/team-chat/read");
        onUnreadChange?.();
      } catch { /* the badge is a hint */ }
    },
    [onUnreadChange]
  );

  const loadLatest = useCallback(async () => {
    try {
      const res = await api.get("/team-chat/messages", { params: { limit: PAGE } });
      const latest: TeamMessage[] = res.data.messages || [];
      setReadMarker((m) => (m === undefined ? res.data.last_read_at ?? null : m));
      if (!pagedBack.current) setHasMore(!!res.data.has_more);
      setMessages((prev) => {
        if (latest.length === 0) return [];
        // Keep older pages already loaded; the newest page replaces the rest,
        // so messages deleted by their author disappear here too.
        const oldest = latest[0];
        return [...prev.filter((m) => before(m, oldest)), ...latest];
      });
      setError("");
      markRead(latest[latest.length - 1]?.id);
    } catch (e: any) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [markRead]);

  const loadMembers = useCallback(async () => {
    try {
      setMembers((await api.get("/team-chat/members")).data.members || []);
    } catch { /* optional panel */ }
  }, []);

  useEffect(() => {
    loadLatest();
    loadMembers();
    const t = setInterval(() => !document.hidden && loadLatest(), REFRESH_MS);
    const onVisible = () => !document.hidden && loadLatest();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [loadLatest, loadMembers]);

  const loadOlder = async () => {
    if (!messages.length || loadingOlder) return;
    setLoadingOlder(true);
    try {
      const res = await api.get("/team-chat/messages", { params: { limit: PAGE, before: messages[0].id } });
      const older: TeamMessage[] = res.data.messages || [];
      const el = scrollRef.current;
      keepOffset.current = el ? el.scrollHeight - el.scrollTop : null;
      setMessages((prev) => [...older.filter((o) => !prev.some((p) => p.id === o.id)), ...prev]);
      pagedBack.current = true;
      setHasMore(!!res.data.has_more);
    } catch (e: any) {
      setError(getErrorMessage(e));
    } finally {
      setLoadingOlder(false);
    }
  };

  // Stay at the bottom for new messages; keep the reading position when older ones load.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (keepOffset.current !== null) {
      el.scrollTop = el.scrollHeight - keepOffset.current;
      keepOffset.current = null;
    } else if (stickToBottom.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (el) stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  const send = async () => {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    try {
      const res = await api.post("/team-chat/messages", { message: text });
      setDraft("");
      stickToBottom.current = true;
      setMessages((prev) => [...prev.filter((m) => m.id !== res.data.id), res.data]);
      lastMarked.current = res.data.id;
      setError("");
    } catch (e: any) {
      setError(getErrorMessage(e));
    } finally {
      setSending(false);
    }
  };

  const remove = async (m: TeamMessage) => {
    if (!confirm("Delete this message for everyone?")) return;
    try {
      await api.delete(`/team-chat/messages/${m.id}`);
      setMessages((prev) => prev.filter((x) => x.id !== m.id));
    } catch (e: any) {
      setError(getErrorMessage(e));
    }
  };

  // Index of the first message from someone else after the read position.
  const firstUnread = readMarker
    ? messages.findIndex((m) => !m.mine && (m.created_at || "") > readMarker)
    : -1;

  return (
    <div className="flex flex-col lg:flex-row gap-4 lg:h-[calc(100vh-200px)]">
      <div className="flex-1 min-h-[480px] rounded-xl border border-zinc-800 bg-zinc-900 flex flex-col overflow-hidden">
        <div className="p-3 border-b border-zinc-800 flex items-center justify-between gap-2">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold"># team</h3>
            <p className="text-xs text-zinc-500 flex items-center gap-1">
              <Lock className="h-3 w-3" /> Admins only. Customers never see this room.
            </p>
          </div>
          <button
            onClick={loadLatest}
            aria-label="Refresh team chat"
            className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>

        {error && (
          <div role="alert" className="px-4 py-2 text-xs text-red-400 bg-red-500/10 border-b border-red-500/20">
            {error}
          </div>
        )}

        <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto px-4 py-3">
          {hasMore && (
            <div className="flex justify-center mb-3">
              <button
                onClick={loadOlder}
                disabled={loadingOlder}
                className="px-3 py-1 rounded-md text-xs bg-zinc-800 border border-zinc-700 text-zinc-400 hover:bg-zinc-700"
              >
                {loadingOlder ? "Loading..." : "Load earlier messages"}
              </button>
            </div>
          )}
          {messages.length === 0 && (
            <div className="h-full flex items-center justify-center text-zinc-500 text-sm text-center px-6">
              {loading ? "Loading..." : "No messages yet. Say hello to the team."}
            </div>
          )}
          {messages.map((m, i) => {
            const prev = messages[i - 1];
            const newDay = !prev || fmtDay(prev.created_at) !== fmtDay(m.created_at);
            const grouped =
              !newDay && i !== firstUnread && prev && prev.author_email === m.author_email &&
              new Date(m.created_at || 0).getTime() - new Date(prev.created_at || 0).getTime() < 5 * 60 * 1000;
            return (
              <React.Fragment key={m.id}>
                {newDay && (
                  <div className="flex items-center gap-3 my-3">
                    <div className="flex-1 h-px bg-zinc-800" />
                    <span className="text-[11px] text-zinc-500 font-medium">{fmtDay(m.created_at)}</span>
                    <div className="flex-1 h-px bg-zinc-800" />
                  </div>
                )}
                {i === firstUnread && (
                  <div className="flex items-center gap-3 my-2">
                    <div className="flex-1 h-px bg-red-500/40" />
                    <span className="text-[11px] text-red-400 font-semibold">New</span>
                    <div className="flex-1 h-px bg-red-500/40" />
                  </div>
                )}
                <div className={`group flex gap-3 rounded-lg px-2 -mx-2 hover:bg-zinc-800/40 ${grouped ? "py-0.5" : "pt-2 pb-0.5"}`}>
                  <div className="w-8 shrink-0">
                    {!grouped && (
                      <div
                        className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold ${avatarColour(m.author_email)}`}
                        title={m.author_email}
                      >
                        {initials(m.author_name)}
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    {!grouped && (
                      <div className="flex items-baseline gap-2">
                        <span className="text-sm font-semibold text-zinc-100 truncate" title={m.author_email}>
                          {m.author_name}
                        </span>
                        {m.mine && <span className="text-[10px] text-zinc-500">you</span>}
                        <span className="text-[11px] text-zinc-500">{fmtTime(m.created_at)}</span>
                      </div>
                    )}
                    <p className="text-sm text-zinc-300 whitespace-pre-wrap break-words">{m.message}</p>
                  </div>
                  {m.mine && (
                    <button
                      onClick={() => remove(m)}
                      aria-label="Delete message"
                      title="Delete message"
                      className="self-start mt-1 p-1 rounded text-zinc-600 opacity-0 group-hover:opacity-100 focus:opacity-100 hover:text-red-400 hover:bg-red-500/10"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </React.Fragment>
            );
          })}
        </div>

        <div className="p-3 border-t border-zinc-800">
          <div className="flex items-end gap-2">
            <textarea
              rows={2}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  send();
                }
              }}
              maxLength={MAX_LEN}
              placeholder="Message the team. Enter sends, Shift+Enter adds a line."
              aria-label="Message the team"
              className="flex-1 resize-none px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={send}
              disabled={!draft.trim() || sending}
              className={`h-10 px-4 rounded-lg text-sm font-medium ${draft.trim() && !sending ? "bg-blue-600 hover:bg-blue-700 text-white" : "bg-zinc-800 text-zinc-500 cursor-not-allowed"}`}
            >
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Send"}
            </button>
          </div>
          {draft.length > MAX_LEN - 200 && (
            <p className="text-[11px] text-zinc-500 mt-1 text-right">{draft.length} / {MAX_LEN}</p>
          )}
        </div>
      </div>

      <aside className="lg:w-64 shrink-0 rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden flex flex-col">
        <div className="p-3 border-b border-zinc-800 flex items-center gap-2">
          <Users className="h-4 w-4 text-zinc-500" />
          <h3 className="text-sm font-semibold">Members</h3>
          <span className="text-xs text-zinc-500">{members.length}</span>
        </div>
        <ul className="flex-1 overflow-y-auto p-2 space-y-1">
          {members.map((p) => (
            <li key={p.email} className="flex items-center gap-2 px-2 py-1.5 rounded-lg">
              <div className={`h-7 w-7 rounded-full flex items-center justify-center text-[11px] font-semibold ${avatarColour(p.email)}`}>
                {initials(p.name)}
              </div>
              <div className="min-w-0">
                <p className="text-sm text-zinc-200 truncate">{p.name}</p>
                <p className="text-[11px] text-zinc-500 truncate">{p.email}</p>
              </div>
            </li>
          ))}
          {members.length === 0 && <li className="text-xs text-zinc-500 px-2 py-4 text-center">No members found</li>}
        </ul>
        <p className="px-3 py-2 text-[11px] text-zinc-500 border-t border-zinc-800">
          Every active platform admin can read this room.
        </p>
      </aside>
    </div>
  );
}
