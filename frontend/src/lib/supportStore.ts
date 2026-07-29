"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = "";

interface Message {
  id: string;
  sender_type: "user" | "admin";
  sender_name?: string;
  message: string;
  created_at: string;
}

interface Conversation {
  id: string;
  subject: string;
  status: string;
  created_at: string;
  updated_at: string;
  last_message: string | null;
  unread_count: number;
}

interface SupportState {
  isOpen: boolean;
  conversationId: string | null;
  messages: Message[];
  unreadCount: number;
  loading: boolean;
  sending: boolean;
}

const _listeners: Set<() => void> = new Set();
let _state: SupportState = {
  isOpen: false,
  conversationId: null,
  messages: [],
  unreadCount: 0,
  loading: false,
  sending: false,
};

function _emit() {
  _listeners.forEach((l) => l());
}

function _getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token") || sessionStorage.getItem("access_token");
}

async function _api(path: string, options: RequestInit = {}): Promise<any> {
  const token = _getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1/support${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export function useSupportStore() {
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    const listener = () => forceUpdate((c) => c + 1);
    _listeners.add(listener);
    // Fetch unread count on mount
    fetchUnread();
    // Poll for new messages every 10 seconds
    const interval = setInterval(() => {
      if (_state.conversationId && _state.isOpen) {
        loadMessages(_state.conversationId);
      }
      fetchUnread();
    }, 10000);
    return () => {
      _listeners.delete(listener);
      clearInterval(interval);
    };
  }, []);

  const toggle = useCallback(() => {
    _state = { ..._state, isOpen: !_state.isOpen };
    _emit();
  }, []);

  const open = useCallback(() => {
    _state = { ..._state, isOpen: true };
    _emit();
    // If we have a conversation, load messages
    if (_state.conversationId) {
      loadMessages(_state.conversationId);
    }
  }, []);

  const close = useCallback(() => {
    _state = { ..._state, isOpen: false };
    _emit();
  }, []);

  const loadMessages = useCallback(async (conversationId: string) => {
    _state = { ..._state, loading: true };
    _emit();
    try {
      const data = await _api(`/conversations/${conversationId}/messages`);
      _state = { ..._state, messages: data.messages || [], loading: false };
    } catch {
      _state = { ..._state, loading: false };
    }
    _emit();
  }, []);

  const sendMessage = useCallback(async (message: string) => {
    if (!message.trim()) return;
    _state = { ..._state, sending: true };
    _emit();

    try {
      if (!_state.conversationId) {
        // Create new conversation
        const data = await _api("/conversations", {
          method: "POST",
          body: JSON.stringify({ subject: "Support Request", message }),
        });
        _state = { ..._state, conversationId: data.id, sending: false };
        await loadMessages(data.id);
      } else {
        // Send message in existing conversation
        const data = await _api(`/conversations/${_state.conversationId}/messages`, {
          method: "POST",
          body: JSON.stringify({ message }),
        });
        _state = {
          ..._state,
          messages: [..._state.messages, data],
          sending: false,
        };
        _emit();
      }
    } catch {
      _state = { ..._state, sending: false };
      _emit();
    }
  }, [_state.conversationId, loadMessages]);

  const fetchUnread = useCallback(async () => {
    try {
      const data = await _api("/unread");
      _state = { ..._state, unreadCount: data.count || 0 };
      _emit();
    } catch {
      // Silent
    }
  }, []);

  return {
    ..._state,
    toggle,
    open,
    close,
    sendMessage,
    loadMessages,
    fetchUnread,
  };
}
