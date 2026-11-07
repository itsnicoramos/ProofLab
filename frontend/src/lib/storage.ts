"use client";

// Attempt drafts and progress, kept in this browser (localStorage). Exposed as external stores
// for useSyncExternalStore, so the server render and hydration use a default value and the
// saved value appears right after, with no hydration mismatch. Best verdicts and test records
// are also queued for the SQLite progress database (lib/outbox.ts, SPEC §17); drafts stay here.

import { useSyncExternalStore } from "react";

import { enqueue } from "./outbox";
import type { StepInput, Verdict, VerdictStatus } from "./types";

const VERSION = "v1";
const attemptKey = (problemId: string) => `prooflab:${VERSION}:attempt:${problemId}`;
const PROGRESS_KEY = `prooflab:${VERSION}:progress`;

export interface DraftStep extends StepInput {
  id: string;
}

export interface Attempt {
  steps: DraftStep[];
  answer: string;
  /** Authored hints already shown, in order. */
  hints: string[];
  /** When this browser last changed the draft (ms since epoch); absent on old drafts. */
  updatedAt?: number;
}

export type Progress = Record<string, VerdictStatus>;

// ---------------------------------------------------------------- low-level storage

export function readRaw(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeRaw(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Private mode or full storage: the in-memory copy still works for this visit.
  }
}

const listeners = new Set<() => void>();

export function emit(): void {
  for (const listener of listeners) listener();
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key.startsWith("prooflab:")) listener();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

// ---------------------------------------------------------------- attempts

const memory = new Map<string, Attempt>();
const defaults = new Map<string, Attempt>();

export function newStepId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `s${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

function defaultAttempt(problemId: string, firstKind: string): Attempt {
  const key = `${problemId}|${firstKind}`;
  let value = defaults.get(key);
  if (!value) {
    value = { steps: [{ id: "first", kind: firstKind, content: "" }], answer: "", hints: [] };
    defaults.set(key, value);
  }
  return value;
}

function parseAttempt(raw: string | null): Attempt | null {
  if (!raw) return null;
  try {
    const data = JSON.parse(raw) as Partial<Attempt>;
    if (!Array.isArray(data.steps) || data.steps.length === 0) return null;
    const steps = data.steps
      .filter((s) => typeof s?.kind === "string" && typeof s?.content === "string")
      .map((s) => ({
        id: typeof s.id === "string" ? s.id : newStepId(),
        kind: s.kind,
        content: s.content,
      }));
    if (steps.length === 0) return null;
    return {
      steps,
      answer: typeof data.answer === "string" ? data.answer : "",
      hints: Array.isArray(data.hints) ? data.hints.filter((h) => typeof h === "string") : [],
      updatedAt: typeof data.updatedAt === "number" ? data.updatedAt : undefined,
    };
  } catch {
    return null;
  }
}

function readAttempt(problemId: string, firstKind: string): Attempt {
  let value = memory.get(problemId);
  if (!value) {
    value = parseAttempt(readRaw(attemptKey(problemId))) ?? defaultAttempt(problemId, firstKind);
    memory.set(problemId, value);
  }
  return value;
}

export function saveAttempt(problemId: string, attempt: Attempt): void {
  const stamped = { ...attempt, updatedAt: Date.now() };
  memory.set(problemId, stamped);
  writeRaw(attemptKey(problemId), JSON.stringify(stamped));
  emit();
}

/** The latest saved attempt for `key` (a problem id, or a test question's draft key). */
export function getAttempt(key: string, firstKind: string): Attempt {
  return readAttempt(key, firstKind);
}

/** Apply a change to the latest saved attempt (safe to call after an await). */
export function updateAttempt(
  problemId: string,
  firstKind: string,
  change: (attempt: Attempt) => Attempt,
): void {
  saveAttempt(problemId, change(readAttempt(problemId, firstKind)));
}

/** Forget a draft entirely (used when a practice test is retaken). */
export function clearAttempt(key: string): void {
  memory.delete(key);
  try {
    window.localStorage.removeItem(attemptKey(key));
  } catch {
    // nothing stored
  }
  emit();
}

const isTyped = (a: Attempt) =>
  a.answer.trim() !== "" || a.steps.some((s) => s.content.trim() !== "");

/**
 * For each draft, "1" if anything is typed, else "0" (a string, so the snapshot is stable).
 * `null` during the server render and hydration.
 */
export function useTypedFlags(drafts: { key: string; firstKind: string }[]): string | null {
  return useSyncExternalStore(
    subscribe,
    () => drafts.map((d) => (isTyped(readAttempt(d.key, d.firstKind)) ? "1" : "0")).join(""),
    () => null,
  );
}

export function resetAttempt(problemId: string, firstKind: string): void {
  saveAttempt(problemId, {
    steps: [{ id: newStepId(), kind: firstKind, content: "" }],
    answer: "",
    hints: [],
  });
}

export function useAttempt(problemId: string, firstKind: string): Attempt {
  return useSyncExternalStore(
    subscribe,
    () => readAttempt(problemId, firstKind),
    () => defaultAttempt(problemId, firstKind),
  );
}

// ---------------------------------------------------------------- progress

const RANK: Record<VerdictStatus, number> = { invalid: 0, incorrect: 1, partial: 2, correct: 3 };
let progressCache: { raw: string | null; value: Progress } | null = null;
const EMPTY_PROGRESS: Progress = {};

function readProgress(): Progress {
  const raw = readRaw(PROGRESS_KEY);
  if (progressCache && progressCache.raw === raw) return progressCache.value;
  let value: Progress = EMPTY_PROGRESS;
  try {
    const parsed = raw ? (JSON.parse(raw) as unknown) : null;
    if (parsed && typeof parsed === "object") value = parsed as Progress;
  } catch {
    value = EMPTY_PROGRESS;
  }
  progressCache = { raw, value };
  return value;
}

/** Remember the best verdict this browser has seen for a problem. */
export function recordProgress(problemId: string, status: VerdictStatus): void {
  const current = readProgress();
  const previous = current[problemId];
  if (previous && RANK[previous] >= RANK[status]) return;
  writeRaw(PROGRESS_KEY, JSON.stringify({ ...current, [problemId]: status }));
  emit();
  enqueue({ op: "progress", problem_id: problemId, status, at: Date.now() });
}

/** Merge best verdicts from the database (the sync agent): each one only ever goes up. */
export function mergeProgress(incoming: Progress): void {
  const current = readProgress();
  const merged: Progress = { ...current };
  let changed = false;
  for (const [id, status] of Object.entries(incoming)) {
    if (!(status in RANK)) continue;
    if (!merged[id] || RANK[merged[id]] < RANK[status]) {
      merged[id] = status;
      changed = true;
    }
  }
  if (changed) {
    writeRaw(PROGRESS_KEY, JSON.stringify(merged));
    emit();
  }
}

/** Every best verdict in this browser (to send the database what it hasn't seen). */
export function readAllProgress(): Progress {
  return readProgress();
}

export function useProgress(): Progress {
  return useSyncExternalStore(subscribe, readProgress, () => EMPTY_PROGRESS);
}

// ---------------------------------------------------------------- started, not solved

export interface StartedProblem {
  id: string;
  updatedAt: number;
  status: VerdictStatus | null;
}

const ATTEMPT_PREFIX = `prooflab:${VERSION}:attempt:`;
const SERVER_STARTED = "server";

/** A stable string snapshot (strings compare by value, so React won't loop). */
function readStartedSnapshot(): string {
  const progress = readProgress();
  const started: StartedProblem[] = [];
  let keys: string[] = [];
  try {
    keys = Object.keys(window.localStorage).filter((k) => k.startsWith(ATTEMPT_PREFIX));
  } catch {
    keys = [];
  }
  for (const key of keys) {
    const id = key.slice(ATTEMPT_PREFIX.length);
    const attempt = parseAttempt(readRaw(key));
    const status = progress[id] ?? null;
    const typed = attempt !== null && isTyped(attempt);
    if (status === "correct" || (!typed && status === null)) continue;
    started.push({ id, updatedAt: attempt?.updatedAt ?? 0, status });
  }
  started.sort((a, b) => b.updatedAt - a.updatedAt || a.id.localeCompare(b.id));
  return JSON.stringify(started);
}

/**
 * Problems this browser has started but not solved, most recently edited first.
 * `null` during the server render and hydration, before localStorage can be read.
 */
export function useStartedProblems(): StartedProblem[] | null {
  const raw = useSyncExternalStore(subscribe, readStartedSnapshot, () => SERVER_STARTED);
  return raw === SERVER_STARTED ? null : (JSON.parse(raw) as StartedProblem[]);
}

// ---------------------------------------------------------------- practice tests

/** One graded test question: the verdict plus exactly what was submitted. */
export interface ExamResult {
  verdict: Verdict;
  steps: DraftStep[];
  answer: string;
  /** Multiple-choice questions: what was picked, the right key, and why. */
  choice?: { picked: string; correct: string; explanation: string | null; solution: string[] };
}

export interface TestMeta {
  title: string;
  /** Canonical link back to this exact test. */
  href: string;
  questions: number;
}

export interface TestRecord extends TestMeta {
  startedAt: number;
  /** Last change (ms), so the newest copy wins when devices sync. */
  updatedAt?: number;
  submittedAt?: number;
  /** Points earned (correct 1, partly right 0.5), set on submit. */
  score?: number;
  results?: Record<string, ExamResult>;
}

const testKey = (testId: string) => `prooflab:${VERSION}:test:${testId}`;

/** Draft key for one question of one test, so test drafts never mix with practice drafts. */
export const testDraftKey = (testId: string, problemId: string) => `test~${testId}~${problemId}`;

export function saveTestRecord(
  testId: string,
  record: TestRecord | null,
  options: { sync?: boolean } = {},
): void {
  const now = Date.now();
  if (record === null) {
    try {
      window.localStorage.removeItem(testKey(testId));
    } catch {
      // nothing stored
    }
    if (options.sync !== false) enqueue({ op: "test_delete", id: testId, updated_at: now });
  } else {
    const stamped = { ...record, updatedAt: options.sync === false ? record.updatedAt : now };
    writeRaw(testKey(testId), JSON.stringify(stamped));
    if (options.sync !== false) enqueue({ op: "test", id: testId, record: stamped, updated_at: now });
  }
  emit();
}

/** Every test record in this browser, by id (for the sync agent). */
export function readAllTestRecords(): Record<string, TestRecord> {
  const out: Record<string, TestRecord> = {};
  let keys: string[] = [];
  try {
    keys = Object.keys(window.localStorage).filter((k) => k.startsWith(TEST_PREFIX));
  } catch {
    keys = [];
  }
  for (const key of keys) {
    const record = parseTestRecord(readRaw(key));
    if (record) out[key.slice(TEST_PREFIX.length)] = record;
  }
  return out;
}

/** When a record last changed (older records have no `updatedAt`). */
export const recordTime = (r: TestRecord) => r.updatedAt ?? r.submittedAt ?? r.startedAt;

/** Start the clock the first time a test is opened (no-op afterwards). */
export function ensureTestStarted(testId: string, meta: TestMeta): void {
  if (readRaw(testKey(testId)) === null) saveTestRecord(testId, { ...meta, startedAt: Date.now() });
}

export function parseTestRecord(raw: string | null): TestRecord | null {
  if (!raw) return null;
  try {
    const data = JSON.parse(raw) as TestRecord;
    return typeof data?.startedAt === "number" && typeof data.href === "string" ? data : null;
  } catch {
    return null;
  }
}

const TEST_PREFIX = `prooflab:${VERSION}:test:`;

export interface TestHistoryItem extends TestMeta {
  id: string;
  startedAt: number;
  submittedAt: number | null;
  score: number | null;
}

function readHistorySnapshot(): string {
  let keys: string[] = [];
  try {
    keys = Object.keys(window.localStorage).filter((k) => k.startsWith(TEST_PREFIX));
  } catch {
    keys = [];
  }
  const items: TestHistoryItem[] = [];
  for (const key of keys) {
    const record = parseTestRecord(readRaw(key));
    if (!record) continue;
    items.push({
      id: key.slice(TEST_PREFIX.length),
      title: record.title,
      href: record.href,
      questions: record.questions,
      startedAt: record.startedAt,
      submittedAt: record.submittedAt ?? null,
      score: record.score ?? null,
    });
  }
  items.sort((a, b) => b.startedAt - a.startedAt);
  return JSON.stringify(items);
}

/** Practice tests this browser has opened, newest first. `null` before hydration. */
export function useTestHistory(): TestHistoryItem[] | null {
  const raw = useSyncExternalStore(subscribe, readHistorySnapshot, () => SERVER_STARTED);
  return raw === SERVER_STARTED ? null : (JSON.parse(raw) as TestHistoryItem[]);
}

// ---------------------------------------------------------------- clock

function subscribeClock(listener: () => void): () => void {
  const timer = window.setInterval(listener, 15_000);
  return () => window.clearInterval(timer);
}

/** The time, refreshed every 15 seconds (stable between ticks). `null` on the server. */
export function useClock(): number | null {
  return useSyncExternalStore(
    subscribeClock,
    () => Math.floor(Date.now() / 15_000) * 15_000,
    () => null,
  );
}

/** The stored record as a raw string (stable for useSyncExternalStore); parse with useMemo. */
export function useTestRecordRaw(testId: string): string | null {
  return useSyncExternalStore(
    subscribe,
    () => readRaw(testKey(testId)),
    () => null,
  );
}
