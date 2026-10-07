/**
 * Scan success rate and time to result (issue #39), kept on the device as three counters and a
 * running sum. No image, no barcode, no location: just "did it work, and how long did it take".
 * `trackEvent` has no scan event in the API contract (`EventIn.name`), so nothing is sent to the
 * server until that contract grows one; `scanStats()` is what Profile or the beta dashboard can read.
 */
import { readJson, writeJson } from "@/state/storage";

export const SCAN_LOG_KEY = "sc-scan-log-v1";

export type ScanLog = {
  version: 1;
  attempts: number;
  found: number;
  notFound: number;
  failed: number;
  /** Sum of milliseconds from "camera on" (or "search") to a result, over found + notFound. */
  totalMs: number;
  /** Which input produced the attempts. */
  byInput: { camera: number; manual: number };
};

const EMPTY: ScanLog = {
  version: 1,
  attempts: 0,
  found: 0,
  notFound: 0,
  failed: 0,
  totalMs: 0,
  byInput: { camera: 0, manual: 0 },
};

const count = (v: unknown) => (typeof v === "number" && Number.isFinite(v) && v >= 0 ? v : 0);

export function readScanLog(): ScanLog {
  const raw = readJson<Partial<ScanLog> | null>(SCAN_LOG_KEY, null);
  if (!raw || raw.version !== 1) return EMPTY;
  return {
    version: 1,
    attempts: count(raw.attempts),
    found: count(raw.found),
    notFound: count(raw.notFound),
    failed: count(raw.failed),
    totalMs: count(raw.totalMs),
    byInput: { camera: count(raw.byInput?.camera), manual: count(raw.byInput?.manual) },
  };
}

export type ScanOutcome = "found" | "not_found" | "failed";

export function recordScan(outcome: ScanOutcome, input: "camera" | "manual", ms: number): void {
  const log = readScanLog();
  const next: ScanLog = {
    ...log,
    attempts: log.attempts + 1,
    found: log.found + (outcome === "found" ? 1 : 0),
    notFound: log.notFound + (outcome === "not_found" ? 1 : 0),
    failed: log.failed + (outcome === "failed" ? 1 : 0),
    totalMs: log.totalMs + (outcome === "failed" ? 0 : Math.max(0, Math.round(ms))),
    byInput: { ...log.byInput, [input]: log.byInput[input] + 1 },
  };
  writeJson(SCAN_LOG_KEY, next);
}

/** Success rate (found over attempts) and the mean time to a result, or null with no data. */
export function scanStats(log: ScanLog = readScanLog()) {
  const answered = log.found + log.notFound;
  return {
    attempts: log.attempts,
    successRate: log.attempts > 0 ? log.found / log.attempts : null,
    meanMs: answered > 0 ? log.totalMs / answered : null,
  };
}
