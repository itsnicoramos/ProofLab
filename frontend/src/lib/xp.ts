// The activity log behind XP, streaks and the daily goal (SPEC §19). Like the review log in
// lib/learn.ts, only what happened is stored (a solve, a revealed solution, a submitted test, a
// graded card): in this browser for speed, and in the SQLite progress database through the
// outbox. XP itself is recomputed from the log by lib/xpRules.ts, so it is the same on every
// device and never needs migrating.

import { useMemo, useSyncExternalStore } from "react";

import { isCourseId } from "./labels";
import { readReviews } from "./learn";
import { enqueue } from "./outbox";
import { emit, readAllProgress, readAllTestRecords, readRaw, subscribe, writeRaw } from "./storage";
import {
  type Activity,
  backfillEvents,
  DEFAULT_GOAL,
  GOALS,
  isDay,
  localDay,
  scoreActivity,
  type SolveData,
  type Streak,
  streakFor,
  type TestData,
  type XpSummary,
} from "./xpRules";

const KEY = "prooflab:v1:activity";
const BACKFILLED = "prooflab:v1:activity-backfilled";
const GOAL_KEY = "prooflab:v1:goal";
const TYPES = new Set(["solve", "reveal", "test", "card"]);

// ---------------------------------------------------------------- storage

function parseActivity(raw: string | null): Activity[] {
  try {
    const data = raw ? (JSON.parse(raw) as unknown) : [];
    if (!Array.isArray(data)) return [];
    return (data as Activity[]).filter(
      (e) =>
        e &&
        typeof e.uid === "string" &&
        typeof e.at === "number" &&
        typeof e.item === "string" &&
        TYPES.has(e.type) &&
        (e.day === null || isDay(e.day)),
    );
  } catch {
    return [];
  }
}

const newUid = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

/**
 * One-time: work done before XP existed counts too (xpRules.backfillEvents says exactly what).
 * The sync agent calls this after the browser's first sync has merged other devices' events,
 * or once it knows there is no database, so anything with a live event is skipped. The uids
 * are fixed, so two devices that both backfill don't count anything twice.
 */
export function backfillEarlierWork(resetAt: number | null = null): void {
  if (typeof window === "undefined" || readRaw(BACKFILLED) !== null) return;
  const mine = parseActivity(readRaw(KEY));
  const events = backfillEvents({
    progress: readAllProgress(),
    tests: readAllTestRecords(),
    reviews: readReviews(),
    isLiveCourse: isCourseId,
    dayOf: localDay,
    existing: mine,
    resetAt,
  });
  const seen = new Set(mine.map((e) => e.uid));
  const fresh = events.filter((e) => !seen.has(e.uid));
  if (fresh.length) {
    const next = JSON.stringify([...mine, ...fresh]);
    writeRaw(KEY, next);
    // writeRaw swallows a full-storage error: only mark the backfill done once it's really
    // stored, so the next load tries again instead of losing the earlier work for good.
    if (readRaw(KEY) !== next) return;
  }
  writeRaw(BACKFILLED, String(Date.now()));
  if (fresh.length) {
    emit();
    enqueue(...fresh.map((e) => ({ op: "activity" as const, ...e })));
  }
}

/** The raw activity log in this browser (the sync agent merges it with the database's). */
export function readActivity(): Activity[] {
  if (typeof window === "undefined") return [];
  return parseActivity(readRaw(KEY));
}

/** Replace the local log with a merged one (used by the sync agent). */
export function writeActivity(activity: Activity[]): void {
  writeRaw(KEY, JSON.stringify([...activity].sort((a, b) => a.at - b.at)));
  emit();
}

// ---------------------------------------------------------------- recording

function record(event: Omit<Activity, "uid" | "day" | "at">, now = Date.now()): string {
  const e: Activity = { uid: newUid(), day: localDay(now), at: now, ...event };
  writeRaw(KEY, JSON.stringify([...readActivity(), e]));
  emit();
  enqueue({ op: "activity", ...e });
  return e.uid;
}

interface ItemRef {
  item: string;
  course: string;
  topic: string;
}

/** A practice problem checked until it said Correct. Returns the event's uid. */
export const recordSolve = (ref: ItemRef, data: SolveData) =>
  record({ type: "solve", ...ref, data });

/** The worked solution was opened: no XP for this problem for the rest of the day. */
export const recordReveal = (ref: ItemRef) => record({ type: "reveal", ...ref });

/** A submitted practice test. Returns the event's uid. */
export const recordTest = (testId: string, course: string, data: TestData) =>
  record({ type: "test", item: testId, course, topic: "", data });

/** A graded flashcard or quiz answer. Returns the event's uid. */
export const recordCard = (ref: ItemRef) => record({ type: "card", ...ref });

/** Forget all XP and streaks, here and in the database (after a confirmation). */
export function resetXp(): void {
  writeRaw(BACKFILLED, String(Date.now())); // earlier work doesn't come back either
  writeRaw(KEY, "[]");
  emit();
  enqueue({ op: "reset_activity", at: Date.now() });
}

// ---------------------------------------------------------------- reading

interface XpState {
  activity: Activity[];
  summary: XpSummary;
}

const EMPTY: XpState = { activity: [], summary: scoreActivity([]) };
let cache: { raw: string | null; value: XpState } | null = null;

function read(): XpState {
  if (typeof window === "undefined") return EMPTY;
  const raw = readRaw(KEY);
  if (cache && cache.raw === raw) return cache.value;
  const activity = parseActivity(raw);
  const value = { activity, summary: scoreActivity(activity) };
  cache = { raw, value };
  return value;
}

/** XP from the activity log; re-renders when it changes (this tab, another tab, or a sync). */
export function useXp(): XpState & { ready: boolean } {
  const state = useSyncExternalStore(subscribe, read, () => EMPTY);
  const ready = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  return { ...state, ready };
}

// ---------------------------------------------------------------- today and the goal

function subscribeDay(listener: () => void): () => void {
  const timer = window.setInterval(listener, 60_000);
  const onVisible = () => listener();
  document.addEventListener("visibilitychange", onVisible);
  return () => {
    window.clearInterval(timer);
    document.removeEventListener("visibilitychange", onVisible);
  };
}

/** Today's local date ("2026-11-08"); null during server rendering. Changes at midnight. */
export function useToday(): string | null {
  return useSyncExternalStore(subscribeDay, () => localDay(Date.now()), () => null);
}

function readGoal(): number {
  const n = Number(readRaw(GOAL_KEY));
  return (GOALS as readonly number[]).includes(n) ? n : DEFAULT_GOAL;
}

/** The daily XP goal (20, 50 or 100), kept in this browser. */
export function useGoal(): number {
  return useSyncExternalStore(subscribe, readGoal, () => DEFAULT_GOAL);
}

export function setGoal(goal: number): void {
  if (!(GOALS as readonly number[]).includes(goal)) return;
  writeRaw(GOAL_KEY, String(goal));
  emit();
}

/** Everything the XP displays need: the summary, today, the goal and the streak. */
export function useXpToday(): XpState & {
  ready: boolean;
  today: string | null;
  todayXp: number;
  goal: number;
  streak: Streak | null;
} {
  const { activity, summary, ready } = useXp();
  const today = useToday();
  const goal = useGoal();
  const streak = useMemo(
    () => (today ? streakFor(summary.byDay, today) : null),
    [summary, today],
  );
  return {
    activity,
    summary,
    ready: ready && today !== null,
    today,
    todayXp: today ? (summary.byDay[today] ?? 0) : 0,
    goal,
    streak,
  };
}
