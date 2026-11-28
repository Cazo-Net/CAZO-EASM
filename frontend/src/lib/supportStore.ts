"use client";

import { useEffect, useSyncExternalStore } from "react";

/**
 * Support chat state, shared by every mounted widget.
 *
 * Two modes, picked from whether an access token is present:
 *  - "user":  signed-in customer; conversations belong to the account.
 *  - "guest": website visitor; the conversation id and its secret token live
 *             in this browser's localStorage.
 */

export const MAX_MESSAGE_LENGTH = 4000;
const GUEST_KEY = "cazo_support_guest";
const POLL_OPEN_MS = 5000;
const POLL_CLOSED_MS = 30000;

export interface SupportMessage {
  id: string;
  sender_type: "user" | "admin";
  sender_name?: string;
  message: string;
  created_at: string | null;
}

interface GuestSession {
  id: string;
  token: string;
  name?: string;
  email?: string;
}

interface SupportState {
  mode: "user" | "guest";
  isOpen: boolean;
  conversationId: string | null;
  status: string | null;
  messages: SupportMessage[];
  unreadCount: number;
  loading: boolean;
  sending: boolean;
  error: string | null;
}

const INITIAL: SupportState = {
  mode: "guest",
  isOpen: false,
  conversationId: null,
  status: null,
  messages: [],
  unreadCount: 0,
  loading: false,
  sending: false,
  error: null,
};

let state: SupportState = INITIAL;
// Whose conversation is in memory. When the signed-in account changes (sign
// out, another user signs in on the same browser) everything is dropped.
let identity: string | null = null;
let ready = false;
let mounted = 0;
let timer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<() => void>();

function set(patch: Partial<SupportState>) {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem("access_token") || sessionStorage.getItem("access_token");
  } catch {
    return null;
  }
}

function readGuest(): GuestSession | null {
  try {
    const raw = localStorage.getItem(GUEST_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    return parsed && parsed.id && parsed.token ? parsed : null;
  } catch {
    return null;
  }
}

function writeGuest(session: GuestSession | null) {
  try {
    if (session) localStorage.setItem(GUEST_KEY, JSON.stringify(session));
    else localStorage.removeItem(GUEST_KEY);
  } catch {
    /* private mode: the chat still works until the tab is closed */
  }
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function api(path: string, options: RequestInit = {}, guestToken?: string): Promise<any> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (guestToken) headers["X-Support-Token"] = guestToken;
  else if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`/api/v1/support${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    let detail = body?.detail;
    if (Array.isArray(detail)) detail = detail[0]?.msg?.replace(/^Value error, /, "");
    throw new ApiError(res.status, typeof detail === "string" ? detail : "Something went wrong. Please try again.");
  }
  return res.json();
}

function describe(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return "Couldn't reach CAZO. Check your connection and try again.";
}

/** The account a token belongs to, so a refreshed token keeps the chat. */
function accountOf(token: string): string {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(payload)).sub || token;
  } catch {
    return token;
  }
}

/** Reset the store when the signed-in account (or lack of one) changed. */
function syncIdentity(): boolean {
  const token = getToken();
  const current = token ? `user:${accountOf(token)}` : "guest";
  if (current === identity) return false;
  identity = current;
  ready = false;
  state = { ...INITIAL, isOpen: state.isOpen, mode: token ? "user" : "guest" };
  listeners.forEach((l) => l());
  return true;
}

async function refresh() {
  const mine = identity;
  try {
    if (state.mode === "user") {
      if (!ready) {
        // Pick up the most recent conversation that is still open.
        const data = await api("/conversations");
        if (mine !== identity) return;
        const current = (data.conversations || []).find((c: any) => c.status === "open");
        ready = true;
        set({ conversationId: current?.id ?? null, status: current?.status ?? null });
      }
      if (state.conversationId && state.isOpen) {
        const data = await api(`/conversations/${state.conversationId}/messages`);
        if (mine !== identity) return;
        set({ messages: data.messages || [], status: data.status ?? state.status, unreadCount: 0 });
      } else {
        const data = await api("/unread");
        if (mine !== identity) return;
        set({ unreadCount: data.count || 0 });
      }
    } else {
      const guest = readGuest();
      ready = true;
      if (!guest) {
        if (state.conversationId) set({ conversationId: null, messages: [], unreadCount: 0 });
        return;
      }
      if (state.isOpen) {
        const data = await api(`/guest/conversations/${guest.id}/messages`, {}, guest.token);
        if (mine !== identity) return;
        set({ conversationId: guest.id, messages: data.messages || [], status: data.status, unreadCount: 0 });
      } else {
        const data = await api(`/guest/conversations/${guest.id}/unread`, {}, guest.token);
        if (mine !== identity) return;
        set({ conversationId: guest.id, unreadCount: data.count || 0 });
      }
    }
  } catch (e) {
    if (mine !== identity) return;
    if (e instanceof ApiError && e.status === 404 && state.mode === "guest") {
      // The conversation was removed on our side; start fresh.
      writeGuest(null);
      set({ conversationId: null, messages: [], unreadCount: 0 });
    }
    // Background refreshes fail quietly; sending reports its own errors.
  } finally {
    if (mine === identity && state.loading) set({ loading: false });
  }
}

function schedule() {
  if (timer) clearTimeout(timer);
  if (mounted === 0) return;
  timer = setTimeout(async () => {
    syncIdentity();
    if (typeof document === "undefined" || !document.hidden) await refresh();
    schedule();
  }, state.isOpen ? POLL_OPEN_MS : POLL_CLOSED_MS);
}

function start() {
  syncIdentity();
  refresh();
  schedule();
}

export function openSupport() {
  syncIdentity();
  set({ isOpen: true, error: null, loading: state.messages.length === 0 && (!ready || !!state.conversationId) });
  refresh();
  schedule();
}

export function closeSupport() {
  set({ isOpen: false });
  schedule();
}

export interface GuestDetails {
  name: string;
  email: string;
  /** Honeypot; always empty for real visitors. */
  website?: string;
}

/** Returns true when the message was accepted. */
export async function sendSupportMessage(message: string, guest?: GuestDetails): Promise<boolean> {
  const text = message.trim();
  if (!text || state.sending) return false;
  syncIdentity();
  const mine = identity;
  set({ sending: true, error: null });
  try {
    if (state.mode === "user") {
      if (!state.conversationId) {
        const conv = await api("/conversations", { method: "POST", body: JSON.stringify({ message: text }) });
        if (mine !== identity) return false;
        set({ conversationId: conv.id, status: conv.status });
        await refresh();
      } else {
        const sent = await api(`/conversations/${state.conversationId}/messages`, {
          method: "POST",
          body: JSON.stringify({ message: text }),
        });
        if (mine !== identity) return false;
        set({ messages: [...state.messages, sent], status: "open" });
      }
    } else {
      const session = readGuest();
      if (!session) {
        if (!guest) throw new ApiError(400, "Please enter your email address.");
        const conv = await api("/guest/conversations", {
          method: "POST",
          body: JSON.stringify({ name: guest.name, email: guest.email, website: guest.website || "", message: text }),
        });
        writeGuest({ id: conv.id, token: conv.token, name: guest.name, email: guest.email });
        set({ conversationId: conv.id, status: conv.status });
        await refresh();
      } else {
        const sent = await api(
          `/guest/conversations/${session.id}/messages`,
          { method: "POST", body: JSON.stringify({ message: text }) },
          session.token
        );
        set({ messages: [...state.messages, sent], status: "open" });
      }
    }
    set({ sending: false });
    return true;
  } catch (e) {
    if (mine === identity) set({ sending: false, error: describe(e) });
    return false;
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const getSnapshot = () => state;
const getServerSnapshot = () => INITIAL;

export function useSupportStore() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  useEffect(() => {
    mounted += 1;
    if (mounted === 1) start();
    return () => {
      mounted -= 1;
      if (mounted === 0 && timer) {
        clearTimeout(timer);
        timer = null;
      }
    };
  }, []);

  return {
    ...snapshot,
    open: openSupport,
    close: closeSupport,
    toggle: () => (state.isOpen ? closeSupport() : openSupport()),
    sendMessage: sendSupportMessage,
  };
}
