"use client";

import { useCallback, useEffect, useState } from "react";
import { getErrorMessage, runScanV2, type ScanV2Health, type ScanV2Result } from "@/lib/api";

interface PipelineState {
  progress: Record<string, number>;
  status: Record<string, "pending" | "running" | "complete" | "error">;
  currentStage: string | null;
}

interface ScannerV2State {
  domain: string;
  loading: boolean;
  health: ScanV2Health | null;
  scanResult: ScanV2Result | null;
  pipeline: PipelineState;
  error: string;
  scanType: "full" | "quick";
}

const _listeners: Set<() => void> = new Set();
let _state: ScannerV2State = {
  domain: "",
  loading: false,
  health: null,
  scanResult: null,
  pipeline: { progress: {}, status: {}, currentStage: null },
  error: "",
  scanType: "full",
};

function _emit() {
  _listeners.forEach((l) => l());
}

export function useScannerV2Store() {
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    const listener = () => forceUpdate((c) => c + 1);
    _listeners.add(listener);
    return () => {
      _listeners.delete(listener);
    };
  }, []);

  const setDomain = useCallback((domain: string) => {
    _state = { ..._state, domain };
    _emit();
  }, []);

  const setScanType = useCallback((scanType: "full" | "quick") => {
    _state = { ..._state, scanType };
    _emit();
  }, []);

  const setHealth = useCallback((health: ScanV2Health | null) => {
    _state = { ..._state, health };
    _emit();
  }, []);

  const updatePipeline = useCallback((update: Partial<PipelineState>) => {
    _state = { ..._state, pipeline: { ..._state.pipeline, ...update } };
    _emit();
  }, []);

  const runScan = useCallback(async () => {
    if (!_state.domain.trim()) return;
    _state = {
      ..._state,
      loading: true,
      error: "",
      scanResult: null,
      pipeline: { progress: {}, status: {}, currentStage: null },
    };
    _emit();

    try {
      const result = await runScanV2({
        domain: _state.domain.trim(),
        scan_type: _state.scanType,
      });
      _state = { ..._state, loading: false, scanResult: result };
    } catch (err: any) {
      _state = {
        ..._state,
        loading: false,
        error: getErrorMessage(err, "Scan failed"),
      };
    }
    _emit();
  }, []);

  const setError = useCallback((error: string) => {
    _state = { ..._state, error };
    _emit();
  }, []);

  const setLoading = useCallback((loading: boolean) => {
    _state = { ..._state, loading };
    _emit();
  }, []);

  const setScanResult = useCallback((scanResult: ScanV2Result | null) => {
    _state = { ..._state, scanResult };
    _emit();
  }, []);

  const reset = useCallback(() => {
    _state = {
      ..._state,
      loading: false,
      scanResult: null,
      pipeline: { progress: {}, status: {}, currentStage: null },
      error: "",
    };
    _emit();
  }, []);

  return {
    ..._state,
    setDomain,
    setScanType,
    setHealth,
    updatePipeline,
    runScan,
    setError,
    setLoading,
    setScanResult,
    reset,
  };
}
