"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Loader2, Mail, RefreshCw, RotateCcw, Trash2 } from "lucide-react";
import api, { getErrorMessage } from "@/lib/api";

type Filter = "open" | "closed" | "all";

interface Conversation {
  id: string;
  user_name: string;
  user_email: string | null;
  organization: string | null;
  is_guest: boolean;
  subject: string | null;
  status: string;
  updated_at: string | null;
  last_message: string | null;
  last_sender: string | null;
  unread_count: number;
}

interface Message {
  id: string;
  sender_type: "user" | "admin";
  sender_name: string;
  message: string;
  created_at: string | null;
}

const REFRESH_MS = 10000;

function fmtWhen(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  if (d.toDateString() === new Date().toDateString()) return time;
  return `${d.toLocaleDateString([], { month: "short", day: "numeric" })}, ${time}`;
}

/** Support inbox: every customer and website-visitor conversation, with replies. */
export function SupportInbox({ onUnreadChange }: { onUnreadChange?: () => void }) {
  const [filter, setFilter] = useState<Filter>("open");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingList, setLoadingList] = useState(true);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(async () => {
    try {
      const res = await api.get("/support/conversations", {
        params: filter === "all" ? { limit: 100 } : { status: filter, limit: 100 },
      });
      setConversations(res.data.conversations || []);
      setError("");
    } catch (e: any) {
      setError(getErrorMessage(e));
    } finally {
      setLoadingList(false);
    }
  }, [filter]);

  const loadMessages = useCallback(
    async (id: string) => {
      try {
        const res = await api.get(`/support/conversations/${id}/messages`);
        setMessages(res.data.messages || []);
        // Opening a conversation marks it read.
        setConversations((list) => list.map((c) => (c.id === id ? { ...c, unread_count: 0 } : c)));
        onUnreadChange?.();
      } catch (e: any) {
        setError(getErrorMessage(e));
      }
    },
    [onUnreadChange]
  );

  // Keep the inbox current without a manual refresh.
  useEffect(() => {
    setLoadingList(true);
    loadConversations();
    const t = setInterval(() => !document.hidden && loadConversations(), REFRESH_MS);
    return () => clearInterval(t);
  }, [loadConversations]);

  useEffect(() => {
    if (!selected) return;
    setMessages([]);
    loadMessages(selected);
    const t = setInterval(() => !document.hidden && loadMessages(selected), REFRESH_MS);
    return () => clearInterval(t);
  }, [selected, loadMessages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);

  const current = conversations.find((c) => c.id === selected) || null;

  const send = async () => {
    const text = reply.trim();
    if (!selected || !text || sending) return;
    setSending(true);
    try {
      await api.post(`/support/conversations/${selected}/messages`, { message: text });
      setReply("");
      await loadMessages(selected);
      await loadConversations();
    } catch (e: any) {
      setError(getErrorMessage(e));
    } finally {
      setSending(false);
    }
  };

  const setStatus = async (status: "open" | "closed") => {
    if (!selected) return;
    try {
      await api.put(`/support/conversations/${selected}/status`, { status });
      if (filter !== "all" && filter !== status) setSelected(null);
      await loadConversations();
    } catch (e: any) {
      setError(getErrorMessage(e));
    }
  };

  const remove = async () => {
    if (!selected) return;
    if (!confirm("Delete this conversation and all its messages? This cannot be undone.")) return;
    try {
      await api.delete(`/support/conversations/${selected}`);
      setSelected(null);
      await loadConversations();
      onUnreadChange?.();
    } catch (e: any) {
      setError(getErrorMessage(e));
    }
  };

  return (
    <div className="flex flex-col md:flex-row gap-4 md:h-[calc(100vh-200px)]">
      {/* Conversation list */}
      <div className="md:w-80 shrink-0 max-h-72 md:max-h-none rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden flex flex-col">
        <div className="p-3 border-b border-zinc-800 flex items-center justify-between gap-2">
          <div className="flex gap-1" role="tablist" aria-label="Filter conversations">
            {(["open", "closed", "all"] as Filter[]).map((f) => (
              <button
                key={f}
                role="tab"
                aria-selected={filter === f}
                onClick={() => setFilter(f)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium capitalize ${filter === f ? "bg-blue-500/10 text-blue-400" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"}`}
              >
                {f}
              </button>
            ))}
          </div>
          <button
            onClick={loadConversations}
            aria-label="Refresh conversations"
            className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelected(c.id)}
              className={`w-full text-left px-3 py-3 border-b border-zinc-800/50 hover:bg-zinc-800/50 transition-colors ${selected === c.id ? "bg-zinc-800/70" : ""}`}
            >
              <div className="flex items-center justify-between gap-2 mb-0.5">
                <span className={`text-sm truncate ${c.unread_count > 0 ? "font-semibold text-zinc-50" : "font-medium text-zinc-300"}`}>
                  {c.user_name}
                </span>
                <span className="text-[11px] text-zinc-500 shrink-0">{fmtWhen(c.updated_at)}</span>
              </div>
              <p className="text-[11px] text-zinc-500 truncate mb-1">
                {c.is_guest ? "Website visitor" : c.organization || "No organization"}
                {c.status === "closed" && " · Closed"}
              </p>
              <div className="flex items-center justify-between gap-2">
                <p className={`text-xs truncate ${c.unread_count > 0 ? "text-zinc-200" : "text-zinc-500"}`}>
                  {c.last_sender === "admin" && "You: "}
                  {c.last_message || "No messages"}
                </p>
                {c.unread_count > 0 && (
                  <span className="shrink-0 min-w-[18px] h-[18px] px-1 flex items-center justify-center rounded-full bg-blue-600 text-white text-[11px] font-semibold">
                    {c.unread_count}
                  </span>
                )}
              </div>
            </button>
          ))}
          {conversations.length === 0 && (
            <div className="text-center py-10 text-zinc-500 text-xs">
              {loadingList ? "Loading..." : filter === "open" ? "No open conversations" : "No conversations"}
            </div>
          )}
        </div>
      </div>

      {/* Thread */}
      <div className="flex-1 min-h-[420px] rounded-xl border border-zinc-800 bg-zinc-900 flex flex-col overflow-hidden">
        {error && (
          <div role="alert" className="px-4 py-2 text-xs text-red-400 bg-red-500/10 border-b border-red-500/20">
            {error}
          </div>
        )}
        {current ? (
          <>
            <div className="p-3 border-b border-zinc-800 flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <h3 className="text-sm font-semibold truncate">{current.user_name}</h3>
                <p className="text-xs text-zinc-500 truncate">
                  {[current.user_email, current.is_guest ? "Website visitor" : current.organization]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {current.user_email && (
                  <a
                    href={`mailto:${encodeURIComponent(current.user_email)}?subject=${encodeURIComponent("Re: your message to CAZO Support")}`}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs bg-zinc-800 border border-zinc-700 hover:bg-zinc-700"
                  >
                    <Mail className="h-3.5 w-3.5" /> Email
                  </a>
                )}
                {current.status === "closed" ? (
                  <button onClick={() => setStatus("open")} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs bg-zinc-800 border border-zinc-700 hover:bg-zinc-700">
                    <RotateCcw className="h-3.5 w-3.5" /> Reopen
                  </button>
                ) : (
                  <button onClick={() => setStatus("closed")} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs bg-zinc-800 border border-zinc-700 hover:bg-zinc-700">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Mark resolved
                  </button>
                )}
                <button onClick={remove} aria-label="Delete conversation" title="Delete conversation" className="p-1.5 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-red-500/10">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.map((m) => {
                const mine = m.sender_type === "admin";
                return (
                  <div key={m.id} className={`flex flex-col ${mine ? "items-end" : "items-start"}`}>
                    <div className={`max-w-[75%] rounded-xl px-3 py-2 text-sm text-zinc-200 whitespace-pre-wrap break-words ${mine ? "bg-blue-500/10 border border-blue-500/25 rounded-br-sm" : "bg-zinc-800 border border-zinc-700 rounded-bl-sm"}`}>
                      {m.message}
                    </div>
                    <p className="text-[11px] text-zinc-500 mt-1 px-1">
                      {m.sender_name}
                      {fmtWhen(m.created_at) && ` · ${fmtWhen(m.created_at)}`}
                    </p>
                  </div>
                );
              })}
              <div ref={endRef} />
            </div>
            <div className="p-3 border-t border-zinc-800">
              <div className="flex items-end gap-2">
                <textarea
                  rows={2}
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                      e.preventDefault();
                      send();
                    }
                  }}
                  maxLength={4000}
                  placeholder="Write a reply. Enter sends, Shift+Enter adds a line."
                  aria-label="Reply"
                  className="flex-1 resize-none px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm focus:outline-none focus:border-blue-500"
                />
                <button
                  onClick={send}
                  disabled={!reply.trim() || sending}
                  className={`h-10 px-4 rounded-lg text-sm font-medium ${reply.trim() && !sending ? "bg-blue-600 hover:bg-blue-700 text-white" : "bg-zinc-800 text-zinc-500 cursor-not-allowed"}`}
                >
                  {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Send"}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm px-6 text-center">
            Select a conversation to read and reply.
          </div>
        )}
      </div>
    </div>
  );
}
