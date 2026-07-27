"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { osintLookup, type OsintResult } from "@/lib/api";

interface IntelState {
  query: string;
  loading: boolean;
  error: string;
  data: OsintResult | null;
  elapsed: number;
  startedAt: number | null;
}

const _listeners: Set<() => void> = new Set();
let _state: IntelState = {
  query: "",
  loading: false,
  error: "",
  data: null,
  elapsed: 0,
  startedAt: null,
};
let _timer: ReturnType<typeof setInterval> | null = null;
let _abortController: AbortController | null = null;

function _emit() {
  _listeners.forEach((l) => l());
}

function _startTimer() {
  _stopTimer();
  const t0 = Date.now();
  _timer = setInterval(() => {
    _state = { ..._state, elapsed: Math.floor((Date.now() - t0) / 1000) };
    _emit();
  }, 1000);
}

function _stopTimer() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
}

export function useIntelStore() {
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    const listener = () => forceUpdate((c) => c + 1);
    _listeners.add(listener);
    return () => {
      _listeners.delete(listener);
    };
  }, []);

  const run = useCallback(async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;

    _abortController?.abort();
    _abortController = new AbortController();

    _state = {
      query: trimmed,
      loading: true,
      error: "",
      data: null,
      elapsed: 0,
      startedAt: Date.now(),
    };
    _emit();
    _startTimer();

    try {
      const res = await osintLookup(trimmed);
      _state = { ..._state, loading: false, data: res };
    } catch (e: any) {
      if (e?.name === "AbortError") return;
      const detail = e?.response?.data?.detail;
      _state = {
        ..._state,
        loading: false,
        error: typeof detail === "string" ? detail : e?.message || "Intelligence lookup failed.",
      };
    } finally {
      _stopTimer();
      _state = { ..._state, loading: false };
      _emit();
    }
  }, []);

  const reset = useCallback(() => {
    _abortController?.abort();
    _stopTimer();
    _state = {
      query: "",
      loading: false,
      error: "",
      data: null,
      elapsed: 0,
      startedAt: null,
    };
    _emit();
  }, []);

  return {
    ..._state,
    run,
    reset,
  };
}
