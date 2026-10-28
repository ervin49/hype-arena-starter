"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { EngineError, getHealth, predictCsv, type EngineFailure } from "@/lib/api";
import type { PredictCsvResponse } from "@/lib/types";

export type HealthState = { state: "checking" } | { state: "ready"; demo: boolean } | { state: "down"; error: string };

// One completed run of the engine on an uploaded file, with client-measured timing.
export interface RunRecord {
  file: string;
  startedAt: number;
  finishedAt: number;
  response: PredictCsvResponse;
}

interface RunContextValue {
  health: HealthState;
  checkHealth: () => void;
  // The file being run right now, if any.
  running: { file: string; startedAt: number } | null;
  last: RunRecord | null;
  // False until the saved run (if any) has been read, so pages don't flash an empty state.
  restored: boolean;
  error: EngineFailure | null;
  run: (file: File) => Promise<void>;
}

const RunContext = createContext<RunContextValue | null>(null);

// The last run is kept for this browser tab so a refresh or a page switch keeps it.
const STORAGE_KEY = "lastRun";
const MAX_STORED_CHARS = 4_000_000;

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [health, setHealth] = useState<HealthState>({ state: "checking" });
  const [running, setRunning] = useState<RunContextValue["running"]>(null);
  const [last, setLast] = useState<RunRecord | null>(null);
  const [restored, setRestored] = useState(false);
  const [error, setError] = useState<EngineFailure | null>(null);

  const checkHealth = useCallback(async () => {
    setHealth({ state: "checking" });
    try {
      const h = await getHealth();
      setHealth({ state: "ready", demo: h.demo_mode });
    } catch (e) {
      setHealth({ state: "down", error: e instanceof Error ? e.message : String(e) });
    }
  }, []);

  useEffect(() => {
    checkHealth();
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) setLast(JSON.parse(saved) as RunRecord);
    } catch {
      // Unreadable or blocked storage: start without a previous run.
    }
    setRestored(true);
  }, [checkHealth]);

  const run = useCallback(async (file: File) => {
    const startedAt = Date.now();
    setRunning({ file: file.name, startedAt });
    setError(null);
    try {
      const response = await predictCsv(file);
      const record = { file: file.name, startedAt, finishedAt: Date.now(), response };
      setLast(record);
      try {
        const json = JSON.stringify(record);
        if (json.length <= MAX_STORED_CHARS) sessionStorage.setItem(STORAGE_KEY, json);
        else sessionStorage.removeItem(STORAGE_KEY);
      } catch {
        // Storage full or blocked: the run still shows until the tab is closed.
      }
    } catch (e) {
      setLast(null);
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch {
        // Nothing stored to clear.
      }
      setError({
        message: e instanceof Error ? e.message : "The engine failed.",
        detail: e instanceof EngineError ? e.detail : undefined,
      });
    } finally {
      setRunning(null);
    }
  }, []);

  return <RunContext.Provider value={{ health, checkHealth, running, last, restored, error, run }}>{children}</RunContext.Provider>;
}

export function useRun(): RunContextValue {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error("useRun must be used inside <RunProvider>");
  return ctx;
}
