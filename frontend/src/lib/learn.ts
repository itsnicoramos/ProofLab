// The study model that learns from the student's own answers (SPEC §15.3). No AI: it's
// spaced repetition (FSRS-4.5 formulas, published and deterministic) plus two things fitted to
// this student's history:
//
// 1. A personal memory factor k. FSRS predicts how likely you are to still remember an item
//    after t days; k stretches or shrinks that curve. It is fitted to every past review by
//    minimising log loss (a one-number fit, golden-section search), so the schedule tunes itself
//    to how fast *you* forget, and every due date moves when k does.
// 2. A skill estimate per chapter (an Elo-style rating). Self-tuning tests weight chapters by it
//    and pull in problems that are due for review.
//
// What's stored is only the review log, one event per grade (SPEC §17): in this browser for
// speed, and in the SQLite progress database through the outbox. Everything else (each card's
// memory state, the fit, the skills) is rebuilt from the log by replaying it in time order, so
// reviews made on a phone and a laptop merge without conflicts.

import { useSyncExternalStore } from "react";

import { enqueue } from "./outbox";
import { emit, readRaw, subscribe, writeRaw } from "./storage";
import type { VerdictStatus } from "./types";

const KEY = "prooflab:v1:reviews";
const OLD_KEY = "prooflab:v1:learn"; // before the review log (state blob, no sync)
const DAY = 86_400_000;
const MINUTE = 60_000;
export const MIN_REVIEWS_TO_FIT = 12;
const RETENTION = 0.9;

// FSRS-4.5 default weights.
const W = [
  0.4872, 1.4003, 3.7145, 13.8206, 5.1618, 1.2298, 0.8975, 0.031, 1.6474, 0.1367, 1.0461, 2.1072,
  0.0793, 0.3246, 1.587, 0.2272, 2.8755,
];
const DECAY = -0.5;
const FACTOR = 19 / 81; // with DECAY, R = 0.9 exactly when t = S

export type Grade = 1 | 2 | 3 | 4; // again, hard, good, easy
export const GRADE_LABEL: Record<Grade, string> = { 1: "Again", 2: "Hard", 3: "Good", 4: "Easy" };

/** One grade of one card or problem: the only thing the model stores. */
export interface Review {
  uid: string;
  item: string;
  kind: "card" | "problem" | "note";
  course: string;
  topic: string;
  difficulty: number | null;
  grade: Grade;
  at: number;
}

export interface ItemState {
  s: number; // stability (days), standard FSRS curve
  d: number; // difficulty, 1..10
  last: number; // ms
  due: number; // ms, with the personal factor applied
  reps: number;
  lapses: number;
  lastGrade: Grade;
  kind: Review["kind"];
  course: string;
  topic: string;
}

export interface ReviewLog {
  id: string;
  at: number;
  t: number; // days since the previous review
  s: number; // stability before this review (0 for a first review)
  grade: Grade;
}

export interface Ability {
  theta: number;
  n: number;
}

export interface Fit {
  k: number;
  n: number;
  loss: number; // with the fitted k
  baseLoss: number; // with k = 1
}

export interface LearnState {
  items: Record<string, ItemState>;
  log: ReviewLog[];
  ability: Record<string, Ability>; // "<course>/<topic>"
  fit: Fit | null;
}

const EMPTY: LearnState = { items: {}, log: [], ability: {}, fit: null };

// ---------------------------------------------------------------- FSRS

const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));

export function retrievability(tDays: number, stability: number, k = 1): number {
  if (stability <= 0) return 0;
  return Math.pow(1 + (FACTOR * Math.max(0, tDays)) / (k * stability), DECAY);
}

const initDifficulty = (g: Grade) => clamp(W[4] - (g - 3) * W[5], 1, 10);

function nextDifficulty(d: number, g: Grade): number {
  const moved = d - W[6] * (g - 3);
  return clamp(W[7] * initDifficulty(4) + (1 - W[7]) * moved, 1, 10);
}

function nextStability(s: number, d: number, r: number, g: Grade): number {
  if (g === 1) {
    return Math.min(
      s,
      W[11] * Math.pow(d, -W[12]) * (Math.pow(s + 1, W[13]) - 1) * Math.exp(W[14] * (1 - r)),
    );
  }
  const hard = g === 2 ? W[15] : 1;
  const easy = g === 4 ? W[16] : 1;
  return (
    s *
    (Math.exp(W[8]) *
      (11 - d) *
      Math.pow(s, -W[9]) *
      (Math.exp(W[10] * (1 - r)) - 1) *
      hard *
      easy +
      1)
  );
}

/** The standard FSRS state after grading (personal factor not applied here). */
function step(prev: ItemState | undefined, g: Grade, at: number): { s: number; d: number } {
  if (!prev) return { s: W[g - 1], d: initDifficulty(g) };
  const r = retrievability((at - prev.last) / DAY, prev.s);
  return { s: Math.max(0.05, nextStability(prev.s, prev.d, r, g)), d: nextDifficulty(prev.d, g) };
}

/** When an item comes back: "Again" in 10 minutes, otherwise when recall drops to 90%. */
function dueAfter(s: number, g: Grade, last: number, k: number, first: boolean): number {
  if (g === 1) return last + 10 * MINUTE;
  const days = ((k * s) / FACTOR) * (Math.pow(RETENTION, 1 / DECAY) - 1);
  return last + clamp(days * DAY, DAY, first ? Infinity : 365 * DAY);
}

// ---------------------------------------------------------------- training the factor

function logLoss(log: ReviewLog[], k: number): number {
  let total = 0;
  for (const e of log) {
    const p = clamp(retrievability(e.t, e.s, k), 0.001, 0.999);
    total += e.grade > 1 ? -Math.log(p) : -Math.log(1 - p);
  }
  return total / Math.max(1, log.length);
}

/** Fit the personal factor k to every past review (golden-section search on log k). */
export function fitFactor(log: ReviewLog[]): Fit | null {
  const usable = log.filter((e) => e.s > 0 && e.t > 0);
  if (usable.length < MIN_REVIEWS_TO_FIT) return null;
  const f = (x: number) => logLoss(usable, Math.exp(x));
  let a = Math.log(0.2);
  let b = Math.log(5);
  const g = (Math.sqrt(5) - 1) / 2;
  let c = b - g * (b - a);
  let d = a + g * (b - a);
  for (let i = 0; i < 40; i++) {
    if (f(c) < f(d)) b = d;
    else a = c;
    c = b - g * (b - a);
    d = a + g * (b - a);
  }
  const k = Math.exp((a + b) / 2);
  return { k, n: usable.length, loss: f(Math.log(k)), baseLoss: f(0) };
}

// ---------------------------------------------------------------- replay

const OUTCOME: Record<Grade, number> = { 1: 0, 2: 0.6, 3: 1, 4: 1 };

function updateAbility(prev: Ability | undefined, difficulty: number, grade: Grade): Ability {
  const a = prev ?? { theta: 0, n: 0 };
  const b = (clamp(difficulty, 1, 3) - 2) * 0.8;
  const expected = 1 / (1 + Math.exp(-(a.theta - b)));
  const rate = Math.max(0.15, 0.6 / Math.sqrt(1 + a.n));
  return { theta: clamp(a.theta + rate * (OUTCOME[grade] - expected), -4, 4), n: a.n + 1 };
}

const byTime = (a: Review, b: Review) => a.at - b.at || (a.uid < b.uid ? -1 : a.uid > b.uid ? 1 : 0);

/** Rebuild the whole model from the review log. Same log, same model, on every device. */
export function replay(reviews: Review[]): LearnState {
  const items: Record<string, ItemState> = {};
  const ability: Record<string, Ability> = {};
  const log: ReviewLog[] = [];
  for (const r of [...reviews].sort(byTime)) {
    const prev = items[r.item];
    const { s, d } = step(prev, r.grade, r.at);
    log.push({
      id: r.item,
      at: r.at,
      t: prev ? (r.at - prev.last) / DAY : 0,
      s: prev ? prev.s : 0,
      grade: r.grade,
    });
    items[r.item] = {
      s,
      d,
      last: r.at,
      due: 0,
      reps: (prev?.reps ?? 0) + 1,
      lapses: (prev?.lapses ?? 0) + (prev && r.grade === 1 ? 1 : 0),
      lastGrade: r.grade,
      kind: r.kind,
      course: r.course,
      topic: r.topic,
    };
    if (r.kind === "problem" && r.difficulty) {
      const key = `${r.course}/${r.topic}`;
      ability[key] = updateAbility(ability[key], r.difficulty, r.grade);
    }
  }
  const fit = fitFactor(log);
  const k = fit?.k ?? 1;
  for (const it of Object.values(items)) it.due = dueAfter(it.s, it.lastGrade, it.last, k, it.reps === 1);
  return { items, log, ability, fit };
}

// ---------------------------------------------------------------- storage

function parseReviews(raw: string | null): Review[] {
  try {
    const data = raw ? (JSON.parse(raw) as unknown) : [];
    return Array.isArray(data)
      ? (data as Review[]).filter((r) => r && typeof r.uid === "string" && typeof r.at === "number")
      : [];
  } catch {
    return [];
  }
}

const newUid = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

/** One-time move from the old state blob to the review log (and into the outbox). */
function migrateOldState(): void {
  if (readRaw(KEY) !== null) return;
  const old = readRaw(OLD_KEY);
  if (!old) return;
  try {
    const state = JSON.parse(old) as {
      items?: Record<string, { kind: Review["kind"]; course: string; topic: string }>;
      log?: { id: string; at: number; grade: Grade }[];
    };
    const reviews: Review[] = (state.log ?? []).flatMap((e, i) => {
      const meta = state.items?.[e.id];
      if (!meta) return [];
      return [
        {
          uid: `migrated-${e.at}-${i}`,
          item: e.id,
          kind: meta.kind,
          course: meta.course,
          topic: meta.topic,
          difficulty: meta.kind === "problem" ? 2 : null,
          grade: e.grade,
          at: e.at,
        },
      ];
    });
    writeRaw(KEY, JSON.stringify(reviews));
    enqueue(...reviews.map((r) => ({ op: "review" as const, ...r })));
  } catch {
    writeRaw(KEY, "[]");
  }
}

let cache: { raw: string | null; value: LearnState } | null = null;

function read(): LearnState {
  if (typeof window === "undefined") return EMPTY;
  migrateOldState();
  const raw = readRaw(KEY);
  if (cache && cache.raw === raw) return cache.value;
  const value = replay(parseReviews(raw));
  cache = { raw, value };
  return value;
}

/** The raw review log in this browser (the sync agent merges it with the database's). */
export function readReviews(): Review[] {
  migrateOldState();
  return parseReviews(readRaw(KEY));
}

/** Replace the local log with a merged one (used by the sync agent). */
export function writeReviews(reviews: Review[]): void {
  writeRaw(KEY, JSON.stringify([...reviews].sort(byTime)));
  emit();
}

/** The whole study model; re-renders when it changes (in this tab, another tab, or a sync). */
export function useLearn(): LearnState {
  return useSyncExternalStore(subscribe, read, () => EMPTY);
}

/** True once the browser's copy has been read (false during server rendering). */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}

// ---------------------------------------------------------------- recording

export interface ItemMeta {
  kind: Review["kind"];
  course: string;
  topic: string;
}

/** Record one grade of a card or problem. */
export function review(
  id: string,
  meta: ItemMeta,
  grade: Grade,
  now = Date.now(),
  difficulty: number | null = null,
): void {
  const r: Review = { uid: newUid(), item: id, ...meta, difficulty, grade, at: now };
  writeRaw(KEY, JSON.stringify([...readReviews(), r]));
  emit();
  enqueue({ op: "review", ...r });
}

export interface ProblemRef {
  id: string;
  course: string;
  topic: string;
  difficulty: number;
}

/** A checked attempt (practice or test): correct with no hints is "Good", and so on. */
export function gradeFromVerdict(status: VerdictStatus, hintsUsed = 0): Grade | null {
  if (status === "invalid") return null;
  if (status === "incorrect") return 1;
  if (status === "partial") return 2;
  return hintsUsed > 0 ? 2 : 3;
}

/** Record a checked problem: schedules it for review and updates the chapter's skill. */
export function recordProblem(p: ProblemRef, grade: Grade, now = Date.now()): void {
  review(p.id, { kind: "problem", course: p.course, topic: p.topic }, grade, now, p.difficulty);
}

/** What each grade would schedule next, for the buttons ("Good · 3 days"). */
export function previewIntervals(state: LearnState, id: string, now = Date.now()) {
  const k = state.fit?.k ?? 1;
  const prev = state.items[id];
  return ([1, 2, 3, 4] as Grade[]).map((g) => {
    const { s } = step(prev, g, now);
    return { grade: g, ms: dueAfter(s, g, now, k, !prev) - now };
  });
}

// ---------------------------------------------------------------- reading the model

/** Chapter skill as a 0..1 chance of getting a medium problem right, or null if untried. */
export function mastery(state: LearnState, course: string, topic: string): number | null {
  const a = state.ability[`${course}/${topic}`];
  return a && a.n > 0 ? 1 / (1 + Math.exp(-a.theta)) : null;
}

/**
 * Inputs for a self-tuning test: weak chapters weigh more (untried ones a little), and problems
 * due for review go first. Same history, same weights, so the test stays reproducible.
 */
export function focusFor(state: LearnState, course: string, topics: string[], now = Date.now()) {
  const weights = topics.map((t) => {
    const m = mastery(state, course, t);
    const w = m === null ? 1.5 : 0.5 + 2.5 * (1 - m);
    return `${t}:${w.toFixed(2)}`;
  });
  const prefer = Object.entries(state.items)
    .filter(([, it]) => it.kind === "problem" && it.course === course && topics.includes(it.topic))
    .filter(([, it]) => it.due <= now)
    .sort((a, b) => a[1].due - b[1].due)
    .slice(0, 20)
    .map(([id]) => id);
  return { weights: weights.join(","), prefer };
}

export interface ModelSummary {
  reviews: number;
  fitted: boolean;
  k: number;
  improvement: number; // relative log-loss improvement over the default curve
  needed: number;
}

export function summarize(state: LearnState): ModelSummary {
  const usable = state.log.filter((e) => e.s > 0 && e.t > 0).length;
  const fit = state.fit;
  return {
    reviews: state.log.length,
    fitted: !!fit,
    k: fit?.k ?? 1,
    improvement: fit && fit.baseLoss > 0 ? Math.max(0, 1 - fit.loss / fit.baseLoss) : 0,
    needed: Math.max(0, MIN_REVIEWS_TO_FIT - usable),
  };
}

/** "10 min", "3 days", "2 months". */
export function formatInterval(ms: number): string {
  const minutes = Math.round(ms / MINUTE);
  if (minutes < 60) return `${Math.max(1, minutes)} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h`;
  const days = Math.round(ms / DAY);
  if (days < 31) return days === 1 ? "1 day" : `${days} days`;
  const months = Math.round(days / 30);
  if (months < 12) return months === 1 ? "1 month" : `${months} months`;
  return "1 year";
}

/** Forget every review, here and in the database (the student asked to start over). */
export function resetLearning(): void {
  writeRaw(KEY, "[]");
  emit();
  enqueue({ op: "reset_reviews" });
}
