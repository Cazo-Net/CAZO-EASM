"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DarkWebMention {
  id: string;
  source: string;
  source_url: string;
  content_type: string;
  title: string;
  summary: string;
  discovered_at: string;
  keywords: string[];
  entities: string[];
  threat_level: string;
  confidence: number;
}

interface SearchResult {
  query: string;
  results: DarkWebMention[];
  total: number;
  page: number;
  has_next: boolean;
}

interface DarkWebState {
  // Search
  searchQuery: string;
  searchResults: SearchResult | null;
  searchLoading: boolean;
  searchError: string;

  // Monitoring
  monitors: any[];
  monitorsLoading: boolean;

  // Reports
  reports: any[];
  reportsLoading: boolean;

  // Actions
  search: (query: string) => Promise<void>;
  loadMonitors: () => Promise<void>;
  loadReports: () => Promise<void>;
  reset: () => void;
}

const _listeners: Set<() => void> = new Set();
let _state: DarkWebState = {
  searchQuery: "",
  searchResults: null,
  searchLoading: false,
  searchError: "",
  monitors: [],
  monitorsLoading: false,
  reports: [],
  reportsLoading: false,
  search: async () => {},
  loadMonitors: async () => {},
  loadReports: async () => {},
  reset: () => {},
};

function _emit() {
  _listeners.forEach((l) => l());
}

// Initialize async actions once
let _initialized = false;

function _initActions() {
  if (_initialized) return;
  _initialized = true;

  _state.search = async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) return;

    _state = { ..._state, searchQuery: trimmed, searchLoading: true, searchError: "", searchResults: null };
    _emit();

    try {
      const res = await fetch(`${API_BASE}/api/v1/darkweb/search?q=${encodeURIComponent(trimmed)}`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Search failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data: SearchResult = await res.json();
      _state = { ..._state, searchResults: data, searchLoading: false };
    } catch (e: any) {
      _state = {
        ..._state,
        searchLoading: false,
        searchError: e?.message || "Dark web search failed",
      };
    } finally {
      _emit();
    }
  };

  _state.loadMonitors = async () => {
    _state = { ..._state, monitorsLoading: true };
    _emit();
    try {
      const res = await fetch(`${API_BASE}/api/v1/darkweb/monitors`);
      if (res.ok) {
        const data = await res.json();
        _state = { ..._state, monitors: data.monitors || [], monitorsLoading: false };
      }
    } catch {
      _state = { ..._state, monitorsLoading: false };
    } finally {
      _emit();
    }
  };

  _state.loadReports = async () => {
    _state = { ..._state, reportsLoading: true };
    _emit();
    try {
      const res = await fetch(`${API_BASE}/api/v1/darkweb/reports`);
      if (res.ok) {
        const data = await res.json();
        _state = { ..._state, reports: data.reports || [], reportsLoading: false };
      }
    } catch {
      _state = { ..._state, reportsLoading: false };
    } finally {
      _emit();
    }
  };

  _state.reset = () => {
    _state = {
      ..._state,
      searchQuery: "",
      searchResults: null,
      searchError: "",
    };
    _emit();
  };
}

export function useDarkWebStore(): DarkWebState {
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    const listener = () => forceUpdate((c) => c + 1);
    _listeners.add(listener);
    return () => {
      _listeners.delete(listener);
    };
  }, []);

  if (typeof window !== "undefined" && !_initialized) {
    _initActions();
  }

  return _state;
}
