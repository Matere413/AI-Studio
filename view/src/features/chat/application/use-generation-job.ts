// ─── Generation Job WebSocket Hook ────────────────────────────
// useReducer-based hook for managing a generation job's lifecycle
// over WebSocket. Exposes a pure wsReducer for testing.
//
// Connection lifecycle:
//   connecting → streaming → completed (terminal)
//   connecting → streaming → error (terminal, or retryable)
//   error (retry < 3) → connecting (auto-retry via backoff)
//   error → exhausted (retry >= 3, user must click Retry)
//   exhausted → connecting (via retry())

import { useEffect, useReducer, useRef, useCallback, useState } from "react";
import { getWsUrl } from "../../../shared/infrastructure/api-client.ts";
import type { JobEvent } from "../../../features/studio/domain/dto.ts";

// ─── Types ────────────────────────────────────────────────────

export type ConnectionState =
  | "connecting"
  | "streaming"
  | "completed"
  | "error"
  | "exhausted";

export interface WsState {
  state: ConnectionState;
  events: JobEvent[];
  progress: number;
  retryCount: number;
}

export type WsAction =
  | { type: "CONNECTING" }
  | { type: "CONNECTED" }
  | { type: "MESSAGE"; event: JobEvent }
  | { type: "WS_ERROR" }
  | { type: "RETRY_RESET" }
  | { type: "RESET" };

// ─── Initial State ────────────────────────────────────────────

export const initialState: WsState = {
  state: "connecting",
  events: [],
  progress: 0,
  retryCount: 0,
};

// ─── Pure Reducer ─────────────────────────────────────────────

/**
 * Pure state machine for WebSocket job lifecycle.
 *
 * Transitions:
 * - CONNECTING → state = "connecting" (any state)
 * - CONNECTED → "connecting" → "streaming"
 * - MESSAGE with event "completed" → "streaming" → "completed"
 * - MESSAGE with event "error" → "streaming" → "error"
 * - WS_ERROR → increments retryCount:
 *     retryCount < 3 → "error"
 *     retryCount ≥ 3 → "exhausted"
 * - RETRY_RESET → any → "connecting", retryCount = 0
 */
export function wsReducer(state: WsState, action: WsAction): WsState {
  switch (action.type) {
    case "CONNECTING":
      return { ...state, state: "connecting" };

    case "CONNECTED":
      if (state.state !== "connecting") return state;
      return { ...state, state: "streaming" };

    case "MESSAGE": {
      if (state.state !== "streaming") return state;
      const event = action.event;
      const nextEvents = [...state.events, event];

      if (event.event === "completed") {
        return { ...state, state: "completed", events: nextEvents };
      }
      if (event.event === "error") {
        return { ...state, state: "error", events: nextEvents };
      }

      return {
        ...state,
        events: nextEvents,
        progress: event.progress ?? state.progress,
      };
    }

    case "WS_ERROR": {
      // Completed is terminal — no more retries
      if (state.state === "completed") return state;

      const nextRetry = state.retryCount + 1;
      const isExhausted = nextRetry >= 3 || state.retryCount >= 3;

      if (isExhausted) {
        // Cap retryCount at 3 for exhausted state
        return {
          ...state,
          state: "exhausted",
          retryCount: Math.min(nextRetry, 3),
        };
      }
      return { ...state, state: "error", retryCount: nextRetry };
    }

    case "RETRY_RESET":
      return { ...state, state: "connecting", retryCount: 0 };

    case "RESET":
      return { ...initialState };

    default:
      return state;
  }
}

// ─── Backoff Constants ────────────────────────────────────────

/** Exponential backoff delays in ms: 1s → 2s → 4s. */
export const RETRY_DELAYS_MS = [1_000, 2_000, 4_000];

// ─── Hook ─────────────────────────────────────────────────────

export interface UseGenerationJobResult {
  events: JobEvent[];
  state: ConnectionState;
  progress: number;
  retryCount: number;
  retry: () => void;
}

/**
 * React hook that manages a generation job WebSocket lifecycle.
 *
 * @param jobId - The job ID to connect to, or null to do nothing.
 * @param webSocketCtor - Optional WebSocket constructor (for testing/mocking).
 *
 * Returns the current connection state, accumulated events,
 * progress percentage, retry count, and a `retry()` function.
 */
export function useGenerationJob(
  jobId: string | null,
  webSocketCtor?: typeof WebSocket,
): UseGenerationJobResult {
  const [wsState, dispatch] = useReducer(wsReducer, initialState);
  const [connectKey, setConnectKey] = useState(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const disconnectedRef = useRef(false);

  const retry = useCallback(() => {
    dispatch({ type: "RETRY_RESET" });
    setConnectKey((k) => k + 1);
  }, []);

  // Reset state when jobId changes to prevent event bleed between jobs
  useEffect(() => {
    dispatch({ type: "RESET" });
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;

    const WsClass = webSocketCtor ?? WebSocket;
    const url = getWsUrl(jobId);

    let cancelled = false;
    disconnectedRef.current = false;

    function cleanupWs() {
      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onmessage = null;
        wsRef.current.onerror = null;
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    }

    cleanupWs();
    dispatch({ type: "CONNECTING" });

    const ws = new WsClass(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (cancelled) return;
      dispatch({ type: "CONNECTED" });
    };

    ws.onmessage = (event: MessageEvent) => {
      if (cancelled) return;
      try {
        const jobEvent = JSON.parse(event.data as string) as JobEvent;
        dispatch({ type: "MESSAGE", event: jobEvent });
      } catch {
        // Malformed message — ignore
      }
    };

    ws.onclose = () => {
      if (cancelled) return;
      // Use a ref to prevent double-dispatch from onerror + onclose
      if (disconnectedRef.current) return;
      disconnectedRef.current = true;
      dispatch({ type: "WS_ERROR" });
    };

    return () => {
      cancelled = true;
      if (retryTimerRef.current !== null) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      cleanupWs();
    };
  }, [jobId, webSocketCtor, connectKey]);

  // Auto-retry with backoff when in error state
  useEffect(() => {
    if (!jobId) return;
    if (wsState.state !== "error") return;

    const attemptIndex = Math.min(
      wsState.retryCount - 1,
      RETRY_DELAYS_MS.length - 1,
    );
    const delay = RETRY_DELAYS_MS[attemptIndex];

    retryTimerRef.current = setTimeout(() => {
      dispatch({ type: "CONNECTING" });
      setConnectKey((k) => k + 1);
    }, delay);

    return () => {
      if (retryTimerRef.current !== null) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
    };
  }, [jobId, wsState.state, wsState.retryCount, setConnectKey]);

  return {
    events: wsState.events,
    state: wsState.state,
    progress: wsState.progress,
    retryCount: wsState.retryCount,
    retry,
  };
}
