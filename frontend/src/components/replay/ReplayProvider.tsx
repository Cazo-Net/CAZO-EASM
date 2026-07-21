"use client";

import { createContext, useContext, useReducer, useCallback, useRef, useEffect } from "react";
import type {
  ReplayState,
  ReplayContextType,
  ReplayMode,
  ReplaySpeed,
  ReplayFilters,
  HistoricalSnapshot,
  ReplayDiff,
  AssetChange,
  HistoricalAsset,
  ReplayBookmark,
  ExposureEvolution,
} from "@/types/replay";

const initialState: ReplayState = {
  currentTimestamp: new Date().toISOString(),
  fromTimestamp: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(),
  toTimestamp: new Date().toISOString(),
  scans: [],
  selectedScan: null,
  mode: "daily",
  speed: 1,
  isPlaying: false,
  bookmarks: [],
  events: [],
  diff: null,
  exposureHistory: [],
  filters: {
    organization_id: null,
    project_id: null,
    environment: null,
    technology: null,
    asset_type: null,
    critical_only: false,
  },
  loading: false,
};

type Action =
  | { type: "INIT_DATA"; payload: { scans: HistoricalSnapshot[]; events: any[]; exposureHistory: ExposureEvolution[] } }
  | { type: "SET_TIMESTAMP"; payload: string }
  | { type: "SET_FROM_TIMESTAMP"; payload: string }
  | { type: "SET_TO_TIMESTAMP"; payload: string }
  | { type: "SET_SCANS"; payload: HistoricalSnapshot[] }
  | { type: "SET_SELECTED_SCAN"; payload: HistoricalSnapshot | null }
  | { type: "SET_MODE"; payload: ReplayMode }
  | { type: "SET_SPEED"; payload: ReplaySpeed }
  | { type: "SET_PLAYING"; payload: boolean }
  | { type: "SET_BOOKMARKS"; payload: ReplayBookmark[] }
  | { type: "ADD_BOOKMARK"; payload: ReplayBookmark }
  | { type: "REMOVE_BOOKMARK"; payload: string }
  | { type: "SET_EVENTS"; payload: any[] }
  | { type: "SET_DIFF"; payload: ReplayDiff | null }
  | { type: "SET_EXPOSURE_HISTORY"; payload: ExposureEvolution[] }
  | { type: "SET_FILTERS"; payload: Partial<ReplayFilters> }
  | { type: "SET_LOADING"; payload: boolean };

function reducer(state: ReplayState, action: Action): ReplayState {
  switch (action.type) {
    case "INIT_DATA": {
      const { scans, events, exposureHistory } = action.payload;
      const latestScan = scans.length > 0 ? scans[scans.length - 1] : null;
      return {
        ...state,
        scans,
        events,
        exposureHistory,
        selectedScan: latestScan,
        currentTimestamp: latestScan?.timestamp || state.currentTimestamp,
        toTimestamp: scans.length > 0 ? scans[scans.length - 1].timestamp : state.toTimestamp,
        fromTimestamp: scans.length > 0 ? scans[0].timestamp : state.fromTimestamp,
      };
    }
    case "SET_TIMESTAMP":
      return { ...state, currentTimestamp: action.payload };
    case "SET_FROM_TIMESTAMP":
      return { ...state, fromTimestamp: action.payload };
    case "SET_TO_TIMESTAMP":
      return { ...state, toTimestamp: action.payload };
    case "SET_SCANS":
      return { ...state, scans: action.payload };
    case "SET_SELECTED_SCAN":
      return { ...state, selectedScan: action.payload };
    case "SET_MODE":
      return { ...state, mode: action.payload };
    case "SET_SPEED":
      return { ...state, speed: action.payload };
    case "SET_PLAYING":
      return { ...state, isPlaying: action.payload };
    case "SET_BOOKMARKS":
      return { ...state, bookmarks: action.payload };
    case "ADD_BOOKMARK":
      return { ...state, bookmarks: [...state.bookmarks, action.payload] };
    case "REMOVE_BOOKMARK":
      return { ...state, bookmarks: state.bookmarks.filter((b) => b.id !== action.payload) };
    case "SET_EVENTS":
      return { ...state, events: action.payload };
    case "SET_DIFF":
      return { ...state, diff: action.payload };
    case "SET_EXPOSURE_HISTORY":
      return { ...state, exposureHistory: action.payload };
    case "SET_FILTERS":
      return { ...state, filters: { ...state.filters, ...action.payload } };
    case "SET_LOADING":
      return { ...state, loading: action.payload };
    default:
      return state;
  }
}

const ReplayContext = createContext<ReplayContextType | null>(null);

export function ReplayProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const setTimestamp = useCallback((ts: string) => dispatch({ type: "SET_TIMESTAMP", payload: ts }), []);
  const setFromTimestamp = useCallback((ts: string) => dispatch({ type: "SET_FROM_TIMESTAMP", payload: ts }), []);
  const setToTimestamp = useCallback((ts: string) => dispatch({ type: "SET_TO_TIMESTAMP", payload: ts }), []);
  const setMode = useCallback((mode: ReplayMode) => dispatch({ type: "SET_MODE", payload: mode }), []);
  const setSpeed = useCallback((speed: ReplaySpeed) => dispatch({ type: "SET_SPEED", payload: speed }), []);
  const setFilters = useCallback((filters: Partial<ReplayFilters>) => dispatch({ type: "SET_FILTERS", payload: filters }), []);

  const initData = useCallback(
    (scans: HistoricalSnapshot[], events: any[], exposureHistory: ExposureEvolution[]) =>
      dispatch({ type: "INIT_DATA", payload: { scans, events, exposureHistory } }),
    []
  );

  const findNearestScan = useCallback(
    (timestamp: string): HistoricalSnapshot | null => {
      if (state.scans.length === 0) return null;
      const ts = new Date(timestamp).getTime();
      let closest = state.scans[0];
      let minDiff = Math.abs(new Date(closest.timestamp).getTime() - ts);
      for (const scan of state.scans) {
        const diff = Math.abs(new Date(scan.timestamp).getTime() - ts);
        if (diff < minDiff) {
          minDiff = diff;
          closest = scan;
        }
      }
      return closest;
    },
    [state.scans]
  );

  const jumpToScan = useCallback(
    (scanId: string) => {
      const scan = state.scans.find((s) => s.scan_id === scanId);
      if (scan) {
        dispatch({ type: "SET_TIMESTAMP", payload: scan.timestamp });
        dispatch({ type: "SET_SELECTED_SCAN", payload: scan });
      }
    },
    [state.scans]
  );

  const play = useCallback(() => dispatch({ type: "SET_PLAYING", payload: true }), []);
  const pause = useCallback(() => dispatch({ type: "SET_PLAYING", payload: false }), []);

  const stepForward = useCallback(() => {
    const idx = state.scans.findIndex((s) => s.scan_id === state.selectedScan?.scan_id);
    if (idx < state.scans.length - 1) {
      const next = state.scans[idx + 1];
      dispatch({ type: "SET_TIMESTAMP", payload: next.timestamp });
      dispatch({ type: "SET_SELECTED_SCAN", payload: next });
    }
  }, [state.scans, state.selectedScan]);

  const stepBackward = useCallback(() => {
    const idx = state.scans.findIndex((s) => s.scan_id === state.selectedScan?.scan_id);
    if (idx > 0) {
      const prev = state.scans[idx - 1];
      dispatch({ type: "SET_TIMESTAMP", payload: prev.timestamp });
      dispatch({ type: "SET_SELECTED_SCAN", payload: prev });
    }
  }, [state.scans, state.selectedScan]);

  const addBookmark = useCallback((name: string, notes: string) => {
    const bookmark: ReplayBookmark = {
      id: `bm-${Date.now()}`,
      name,
      notes,
      timestamp: state.currentTimestamp,
      created_at: new Date().toISOString(),
    };
    dispatch({ type: "ADD_BOOKMARK", payload: bookmark });
  }, [state.currentTimestamp]);

  const removeBookmark = useCallback((id: string) => {
    dispatch({ type: "REMOVE_BOOKMARK", payload: id });
  }, []);

  const computeDiff = useCallback(() => {
    const fromScan = findNearestScan(state.fromTimestamp);
    const toScan = findNearestScan(state.toTimestamp);
    if (!fromScan || !toScan) return;

    const fromHostnames = new Set(fromScan.assets.map((a) => a.hostname));
    const toHostnames = new Set(toScan.assets.map((a) => a.hostname));

    const added = toScan.assets.filter((a) => !fromHostnames.has(a.hostname));
    const removed = fromScan.assets.filter((a) => !toHostnames.has(a.hostname));
    const modified: AssetChange[] = [];

    for (const toAsset of toScan.assets) {
      const fromAsset = fromScan.assets.find((a) => a.hostname === toAsset.hostname);
      if (fromAsset) {
        if (JSON.stringify(fromAsset.ip_addresses) !== JSON.stringify(toAsset.ip_addresses)) {
          modified.push({
            id: `mod-${toAsset.id}-ip`,
            asset_id: toAsset.id,
            hostname: toAsset.hostname,
            change_type: "modified",
            field: "ip_addresses",
            old_value: fromAsset.ip_addresses.join(", "),
            new_value: toAsset.ip_addresses.join(", "),
            timestamp: toScan.timestamp,
            scan_id: toScan.scan_id,
          });
        }
        if (JSON.stringify(fromAsset.technologies) !== JSON.stringify(toAsset.technologies)) {
          modified.push({
            id: `mod-${toAsset.id}-tech`,
            asset_id: toAsset.id,
            hostname: toAsset.hostname,
            change_type: "modified",
            field: "technologies",
            old_value: fromAsset.technologies.join(", "),
            new_value: toAsset.technologies.join(", "),
            timestamp: toScan.timestamp,
            scan_id: toScan.scan_id,
          });
        }
        if (fromAsset.exposure_score !== toAsset.exposure_score) {
          modified.push({
            id: `mod-${toAsset.id}-exp`,
            asset_id: toAsset.id,
            hostname: toAsset.hostname,
            change_type: "modified",
            field: "exposure_score",
            old_value: String(fromAsset.exposure_score),
            new_value: String(toAsset.exposure_score),
            timestamp: toScan.timestamp,
            scan_id: toScan.scan_id,
          });
        }
      }
    }

    const unchangedCount = toScan.assets.filter((a) => fromHostnames.has(a.hostname)).length - modified.length;

    dispatch({
      type: "SET_DIFF",
      payload: {
        from_timestamp: state.fromTimestamp,
        to_timestamp: state.toTimestamp,
        added_assets: added,
        removed_assets: removed,
        modified_assets: modified,
        unchanged_count: Math.max(0, unchangedCount),
        summary: `Added ${added.length}, removed ${removed.length}, modified ${modified.length} assets.`,
      },
    });
  }, [state.fromTimestamp, state.toTimestamp, findNearestScan]);

  // Auto-advance when playing
  useEffect(() => {
    if (state.isPlaying && state.scans.length > 0) {
      const interval = 1000 / state.speed;
      intervalRef.current = setInterval(() => {
        const current = new Date(state.currentTimestamp).getTime();
        const last = new Date(state.toTimestamp).getTime();
        if (current >= last) {
          dispatch({ type: "SET_PLAYING", payload: false });
          return;
        }
        const next = current + (interval * 60000 * state.speed);
        dispatch({ type: "SET_TIMESTAMP", payload: new Date(Math.min(next, last)).toISOString() });
      }, interval);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [state.isPlaying, state.speed, state.scans.length]);

  // Auto-select nearest scan when timestamp changes
  useEffect(() => {
    const nearest = findNearestScan(state.currentTimestamp);
    if (nearest && nearest.scan_id !== state.selectedScan?.scan_id) {
      dispatch({ type: "SET_SELECTED_SCAN", payload: nearest });
    }
  }, [state.currentTimestamp, findNearestScan, state.selectedScan?.scan_id]);

  const value: ReplayContextType = {
    state,
    initData,
    setTimestamp,
    setFromTimestamp,
    setToTimestamp,
    setMode,
    setSpeed,
    play,
    pause,
    stepForward,
    stepBackward,
    jumpToScan,
    addBookmark,
    removeBookmark,
    setFilters,
    computeDiff,
  };

  return <ReplayContext.Provider value={value}>{children}</ReplayContext.Provider>;
}

export function useReplay() {
  const ctx = useContext(ReplayContext);
  if (!ctx) throw new Error("useReplay must be used within ReplayProvider");
  return ctx;
}
