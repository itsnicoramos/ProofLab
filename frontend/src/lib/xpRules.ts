// XP, daily goals, streaks, levels and milestones (SPEC §19). Pure functions with no imports,
// so `node --test` runs them directly and every device gets the same numbers from the same log.
//
// What's stored is only what happened (lib/xp.ts keeps the log): a problem solved, a solution
// revealed, a test submitted, a flashcard graded. XP is never stored; it is recomputed here by
// replaying the log in time order. XP is only ever paid for a verdict from the deterministic
// checker (or, for flashcards, for showing up); a wrong answer pays nothing and costs nothing.

export type ActivityType = "solve" | "reveal" | "test" | "card";
export type TestKind = "quiz" | "midterm" | "final";

/** A problem checked until the checker said Correct (practice). */
export interface SolveData {
  /** 1 easy, 2 medium, 3 hard; 0 when unknown (work from before XP existed). */
  difficulty: number;
  /** Checks on this visit, the Correct one included (1 = right first time; 0 = unknown). */
  checks: number;
  /** Extra hints asked for ("Show another hint") before it was solved. The first hint, shown
   *  by itself after a wrong check, is free and not counted. */
  hints: number;
  /** A ProofLab-made version (filed under its book problem for XP, but it doesn't make the book
   *  problem itself Correct, so chapter dates ignore it). */
  variant?: boolean;
}

export interface TestQuestionFact {
  /** The book problem asked (null for a ProofLab-made version; absent on backfilled tests). */
  item?: string | null;
  difficulty: number;
  format: "written" | "choice";
  status: "correct" | "partial" | "incorrect" | "invalid";
  blank: boolean;
}

export interface TestData {
  kind: TestKind;
  questions: TestQuestionFact[];
}

export interface Activity {
  uid: string;
  type: ActivityType;
  /** The browser's local date when it happened ("2026-11-08"); null for undated earlier work. */
  day: string | null;
  at: number;
  /** Problem id (versions use their base id), test id, or card id. */
  item: string;
  course: string;
  topic: string;
  data?: SolveData | TestData;
}

// ---------------------------------------------------------------- the numbers

export const SOLVE_XP: Record<number, number> = { 1: 10, 2: 15, 3: 20 };
const UNKNOWN_XP = 10;
export const FIRST_TRY_BONUS = 5;
export const HINT_COST = 5;
export const MIN_SOLVE_XP = 5;
export const CHOICE_XP = 5;
export const FINISH_BONUS: Record<TestKind, number> = { quiz: 5, midterm: 20, final: 30 };
export const PASS_BONUS = 10;
export const PASS_SHARE = 0.7;
export const CARD_XP = 1;
export const GOALS = [20, 50, 100] as const;
export const DEFAULT_GOAL = 50;
export const FREEZE_EVERY = 7;
export const MAX_FREEZES = 2;

const baseXp = (difficulty: number) => SOLVE_XP[difficulty] ?? UNKNOWN_XP;

export interface XpPart {
  label: string;
  xp: number;
}

export interface XpEntry {
  uid: string;
  type: ActivityType;
  item: string;
  course: string;
  topic: string;
  day: string | null;
  at: number;
  xp: number;
  /** How the XP was worked out, for the one-line breakdown. */
  parts: XpPart[];
  /** Why it paid nothing (or less), when it did. */
  note: string | null;
}

export type Source = "practice" | "tests" | "cards";

export interface XpSummary {
  total: number;
  byDay: Record<string, number>;
  bySource: Record<Source, number>;
  /** Every event that can pay XP (reveals excluded), oldest first. */
  entries: XpEntry[];
  byUid: Record<string, XpEntry>;
  /** The newest test entry and the best XP so far, per test id. */
  tests: Record<string, { latest: XpEntry; best: number }>;
}

// ---------------------------------------------------------------- dates

const pad = (n: number) => String(n).padStart(2, "0");

/** The browser's local date for a time, "YYYY-MM-DD". */
export function localDay(at: number): string {
  const d = new Date(at);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** The day `n` days after `day` (calendar arithmetic on the date itself, no time zones). */
export function addDays(day: string, n: number): string {
  const [y, m, d] = day.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + n));
  return `${t.getUTCFullYear()}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}`;
}

const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;
export const isDay = (s: unknown): s is string => typeof s === "string" && DAY_RE.test(s);

// ---------------------------------------------------------------- scoring

const byTime = (a: Activity, b: Activity) =>
  a.at - b.at || (a.uid < b.uid ? -1 : a.uid > b.uid ? 1 : 0);

function solveEntry(
  e: Activity,
  data: SolveData,
  history: { solvedDays: Set<string | null>; revealedDays: Set<string> },
): Pick<XpEntry, "xp" | "parts" | "note"> {
  const base = baseXp(data.difficulty);
  if (e.day === null) {
    return { xp: base, parts: [{ label: "Solved before XP existed", xp: base }], note: null };
  }
  if (history.revealedDays.has(e.day)) {
    return { xp: 0, parts: [], note: "No XP: you opened the worked solution today." };
  }
  if (history.solvedDays.has(e.day)) {
    return { xp: 0, parts: [], note: "No XP: you already earned XP for this problem today." };
  }
  const label = data.difficulty === 1 ? "Easy" : data.difficulty === 3 ? "Hard" : "Medium";
  const parts: XpPart[] = [{ label: data.difficulty ? label : "Solved", xp: base }];
  if (data.checks === 1) parts.push({ label: "first try", xp: FIRST_TRY_BONUS });
  if (data.hints > 0) {
    parts.push({
      label: data.hints === 1 ? "1 extra hint" : `${data.hints} extra hints`,
      xp: -HINT_COST * data.hints,
    });
  }
  const sum = parts.reduce((s, p) => s + p.xp, 0);
  // Never below 5: say so in the breakdown, so the parts always add up to what was paid.
  if (sum < MIN_SOLVE_XP) parts.push({ label: "minimum", xp: MIN_SOLVE_XP - sum });
  let xp = Math.max(MIN_SOLVE_XP, sum);
  let note: string | null = null;
  if (history.solvedDays.size > 0) {
    xp = Math.ceil(xp / 2);
    note = "Half XP: you solved this one on an earlier day (a review).";
  }
  return { xp, parts, note };
}

/** XP a submitted test is worth on its own (before the "beat your best" rule). */
export function testWorth(data: TestData): { xp: number; parts: XpPart[]; points: number } {
  let questionXp = 0;
  let points = 0;
  let answered = 0;
  for (const q of data.questions) {
    if (q.blank) continue;
    answered += 1;
    const score = q.status === "correct" ? 1 : q.status === "partial" ? 0.5 : 0;
    points += score;
    questionXp += q.format === "choice" ? (score === 1 ? CHOICE_XP : 0) : baseXp(q.difficulty) * score;
  }
  const total = data.questions.length;
  const parts: XpPart[] = [{ label: "Questions", xp: Math.round(questionXp) }];
  const finished = total > 0 && answered * 2 >= total;
  if (finished) {
    const name = data.kind === "quiz" ? "a quiz" : data.kind === "final" ? "a final" : "a midterm";
    parts.push({ label: `finished ${name}`, xp: FINISH_BONUS[data.kind] });
    if (points / total >= PASS_SHARE) parts.push({ label: "70% or more", xp: PASS_BONUS });
  }
  return { xp: parts.reduce((s, p) => s + p.xp, 0), parts, points };
}

/** Replay the activity log into XP. Same log, same XP, on every device. */
export function scoreActivity(activity: Activity[]): XpSummary {
  const entries: XpEntry[] = [];
  const byUid: Record<string, XpEntry> = {};
  const byDay: Record<string, number> = {};
  const bySource: Record<Source, number> = { practice: 0, tests: 0, cards: 0 };
  const tests: XpSummary["tests"] = {};
  const solved = new Map<string, Set<string | null>>();
  const revealed = new Map<string, Set<string>>();
  const cardDays = new Map<string, Set<string>>();
  let total = 0;

  for (const e of [...activity].sort(byTime)) {
    let result: Pick<XpEntry, "xp" | "parts" | "note"> | null = null;
    if (e.type === "reveal") {
      if (e.day) {
        const days = revealed.get(e.item) ?? new Set<string>();
        days.add(e.day);
        revealed.set(e.item, days);
      }
      continue;
    }
    if (e.type === "solve" && e.data && "checks" in e.data) {
      const days = solved.get(e.item) ?? new Set<string | null>();
      result = solveEntry(e, e.data, {
        solvedDays: days,
        revealedDays: revealed.get(e.item) ?? new Set<string>(),
      });
      days.add(e.day);
      solved.set(e.item, days);
      bySource.practice += result.xp;
    } else if (e.type === "test" && e.data && "questions" in e.data) {
      const worth = testWorth(e.data);
      const best = tests[e.item]?.best ?? 0;
      const xp = Math.max(0, worth.xp - best);
      result = {
        xp,
        parts: worth.parts,
        note:
          best === 0
            ? null
            : xp > 0
              ? `Retake: only the ${xp} XP above your best (${best} XP) counts.`
              : `No XP: a retake only pays what beats your best on this test (${best} XP).`,
      };
      bySource.tests += xp;
    } else if (e.type === "card") {
      const day = e.day ?? "";
      const days = cardDays.get(e.item) ?? new Set<string>();
      const xp = days.has(day) ? 0 : CARD_XP;
      days.add(day);
      cardDays.set(e.item, days);
      result = { xp, parts: [{ label: "card", xp: CARD_XP }], note: xp ? null : "Already counted today." };
      bySource.cards += xp;
    }
    if (!result) continue;
    const entry: XpEntry = {
      uid: e.uid,
      type: e.type,
      item: e.item,
      course: e.course,
      topic: e.topic,
      day: e.day,
      at: e.at,
      ...result,
    };
    entries.push(entry);
    byUid[e.uid] = entry;
    total += entry.xp;
    if (e.day && entry.xp) byDay[e.day] = (byDay[e.day] ?? 0) + entry.xp;
    if (e.type === "test" && e.data && "questions" in e.data) {
      const worth = testWorth(e.data).xp;
      tests[e.item] = { latest: entry, best: Math.max(tests[e.item]?.best ?? 0, worth) };
    }
  }
  return { total, byDay, bySource, entries, byUid, tests };
}

// ---------------------------------------------------------------- streaks

export interface Streak {
  /** Days in a row with XP, counting today only once it has XP. */
  current: number;
  best: number;
  /** Freezes held now (earned one per 7 days in a row, up to 2). */
  freezes: number;
  /** Past days a freeze covered. */
  frozen: string[];
  /** True when today has XP already. */
  today: boolean;
  /** The first day a streak reached 7 and 30 days. */
  reached: { 7?: string; 30?: string };
}

/** Walk every day from the first one with XP up to today. */
export function streakFor(byDay: Record<string, number>, today: string): Streak {
  const days = Object.keys(byDay).filter((d) => byDay[d] > 0 && d <= today).sort();
  const none: Streak = { current: 0, best: 0, freezes: 0, frozen: [], today: false, reached: {} };
  if (days.length === 0) return none;
  let current = 0;
  let best = 0;
  let freezes = 0;
  let sinceEarned = 0;
  const frozen: string[] = [];
  const reached: Streak["reached"] = {};
  for (let d = days[0]; d <= today; d = addDays(d, 1)) {
    if ((byDay[d] ?? 0) > 0) {
      current += 1;
      if (current === 7 && !reached[7]) reached[7] = d;
      if (current === 30 && !reached[30]) reached[30] = d;
      sinceEarned += 1;
      if (sinceEarned === FREEZE_EVERY) {
        freezes = Math.min(MAX_FREEZES, freezes + 1);
        sinceEarned = 0;
      }
      best = Math.max(best, current);
    } else if (d === today) {
      // The day isn't over: the streak is still alive, it just hasn't grown yet.
    } else if (current > 0 && freezes > 0) {
      freezes -= 1;
      frozen.push(d);
    } else {
      current = 0;
      sinceEarned = 0;
    }
  }
  return { current, best, freezes, frozen, today: (byDay[today] ?? 0) > 0, reached };
}

// ---------------------------------------------------------------- levels

/** Level n starts at 50 × n × (n − 1) XP: 0, 100, 300, 600, 1,000, … */
export const levelStart = (n: number) => 50 * n * (n - 1);

export function levelFor(total: number): { level: number; start: number; next: number } {
  let level = Math.max(1, Math.floor((1 + Math.sqrt(1 + (4 * Math.max(0, total)) / 50)) / 2));
  while (levelStart(level + 1) <= total) level += 1;
  while (level > 1 && levelStart(level) > total) level -= 1;
  return { level, start: levelStart(level), next: levelStart(level + 1) };
}

// ---------------------------------------------------------------- milestones

export interface Milestone {
  id: string;
  title: string;
  detail: string;
  /** The day it was earned, "" if earned on undated earlier work, null if not yet. */
  earned: string | null;
  /** Earned, but the log can't say when (e.g. a chapter finished partly through tests). */
  dateUnknown?: boolean;
}

/** Milestones from the student's real history only. Chapter ones are added by the caller. */
export function milestones(
  activity: Activity[],
  summary: XpSummary,
  streak: Streak,
): Milestone[] {
  const sorted = [...activity].sort(byTime);
  const firstDay = (pred: (e: Activity) => boolean) => {
    const hit = sorted.find(pred);
    return hit ? (hit.day ?? "") : null;
  };
  // "On your own": no extra hint, and the worked solution never opened before the solve (on any
  // day). Opening it afterwards to compare doesn't take the milestone back.
  const revealedBefore = new Set<string>();
  let clean = 0;
  let cleanDay: string | null = null;
  const cleanSeen = new Set<string>();
  for (const e of sorted) {
    if (e.type === "reveal") {
      revealedBefore.add(e.item);
      continue;
    }
    if (e.type !== "solve" || !e.data || !("hints" in e.data) || e.day === null) continue;
    if (e.data.hints > 0 || revealedBefore.has(e.item) || cleanSeen.has(e.item)) continue;
    cleanSeen.add(e.item);
    clean += 1;
    if (clean === 10) cleanDay = e.day;
  }
  const testShare = (kind: TestKind, share: number) =>
    firstDay((e) => {
      if (e.type !== "test" || !e.data || !("questions" in e.data) || e.data.kind !== kind) return false;
      const n = e.data.questions.length;
      return n > 0 && testWorth(e.data).points / n >= share;
    });
  let running = 0;
  let thousand: string | null = null;
  for (const entry of summary.entries) {
    running += entry.xp;
    if (running >= 1000) {
      thousand = entry.day ?? "";
      break;
    }
  }
  return [
    {
      id: "first-solve",
      title: "First problem solved",
      detail: "Checked a problem until it said Correct.",
      earned: firstDay((e) => e.type === "solve"),
    },
    {
      id: "first-induction",
      title: "First induction proof",
      detail: "Solved a Chapter 10 induction problem.",
      earned: firstDay((e) => e.type === "solve" && e.topic === "induction"),
    },
    {
      id: "ten-clean",
      title: "Ten on your own",
      detail: "Solved 10 different problems without asking for a hint or opening the solution.",
      earned: cleanDay,
    },
    {
      id: "perfect-quiz",
      title: "Perfect quiz",
      detail: "Got every question of a quick quiz right.",
      earned: testShare("quiz", 1),
    },
    {
      id: "strong-final",
      title: "Strong final",
      detail: "Scored 80% or more on a practice final.",
      earned: testShare("final", 0.8),
    },
    {
      id: "streak-7",
      title: "7-day streak",
      detail: "Earned XP 7 days in a row.",
      earned: streak.reached[7] ?? null,
    },
    {
      id: "streak-30",
      title: "30-day streak",
      detail: "Earned XP 30 days in a row.",
      earned: streak.reached[30] ?? null,
    },
    {
      id: "xp-1000",
      title: "1,000 XP",
      detail: "Reached 1,000 XP in total.",
      earned: thousand,
    },
  ];
}

// ---------------------------------------------------------------- earlier work (backfill)

/** A ProofLab-made version's id is "<base id>-v<seed>"; XP files it under the base problem. */
export const baseProblemId = (id: string) => id.replace(/-v\d+$/, "");

export interface BackfillInput {
  /** Best verdict per problem id (practice may have stored version ids). */
  progress: Record<string, string>;
  tests: Record<
    string,
    {
      href?: string;
      submittedAt?: number;
      results?: Record<
        string,
        { verdict: { status: string }; steps: unknown[]; answer: string; choice?: unknown }
      >;
    }
  >;
  reviews: { uid: string; item: string; kind: string; course: string; topic: string; at: number }[];
  /** Courses the site shows (hidden ones are skipped); notes decks always count. */
  isLiveCourse: (course: string) => boolean;
  /** The browser's local date for a time. */
  dayOf: (at: number) => string;
  /** The activity log as merged after the first sync: anything with a live event is skipped. */
  existing: Activity[];
  /** A recorded "Reset XP" (from the database): nothing from before it comes back. */
  resetAt?: number | null;
}

/**
 * Activity events for work done before XP existed, with fixed uids so two devices that both
 * backfill never count anything twice. Run once per browser, after its first sync has merged
 * other devices' live events (or once it knows there is no database).
 *
 * "Before XP existed" is read from the merged log itself: the earliest live (non-backfill) event
 * on any device is when XP started for this student. With no live events yet (a fresh browser,
 * the Vercel site), everything is earlier work. Only work from before that point is backfilled:
 * - problems already Correct: one undated solve per book problem (ProofLab-made versions folded
 *   in). Skipped when the log has a live solve for it, when it was first worked on after XP
 *   started, or when a test taken after XP started covers it: its XP is already counted live,
 *   and a backfilled solve would sort first and turn a live solve into a half-XP review;
 * - submitted tests from before XP started, dated, skipped if the log has an event for them;
 * - concept and notes flashcard grades from before XP started (quiz answers included, right or
 *   wrong), dated. Problem flashcards are stored like practice checks, so they're skipped.
 * Nothing from before a recorded reset comes back.
 */
export function backfillEvents(input: BackfillInput): Activity[] {
  const events: Activity[] = [];
  const live = input.existing.filter((e) => !e.uid.startsWith("backfill-"));
  const xpStart = live.reduce((min, e) => Math.min(min, e.at), Infinity);
  const resetAt = input.resetAt ?? -Infinity;
  const liveSolved = new Set(live.filter((e) => e.type === "solve").map((e) => baseProblemId(e.item)));
  const testsSeen = new Set(input.existing.filter((e) => e.type === "test").map((e) => e.item));
  const firstWorked = new Map<string, number>();
  for (const r of input.reviews) {
    if (r.kind !== "problem") continue;
    const base = baseProblemId(r.item);
    firstWorked.set(base, Math.min(firstWorked.get(base) ?? Infinity, r.at));
  }
  const coveredByLaterTests = new Set<string>();
  for (const record of Object.values(input.tests)) {
    if (!record.submittedAt || record.submittedAt < xpStart || !record.results) continue;
    for (const id of Object.keys(record.results)) coveredByLaterTests.add(baseProblemId(id));
  }
  // Live test events name their book problems too, and they survive a retake that cleared the
  // record's results.
  for (const e of live) {
    if (e.type !== "test" || !e.data || !("questions" in e.data)) continue;
    for (const q of e.data.questions) if (q.item) coveredByLaterTests.add(baseProblemId(q.item));
  }
  const solved = new Set<string>();
  for (const [id, status] of Object.entries(input.progress)) {
    const base = baseProblemId(id);
    const [course = "", topic = ""] = base.split(".");
    if (status !== "correct" || !input.isLiveCourse(course) || solved.has(base)) continue;
    if (resetAt > 0) continue; // undated solves sit at time 0, before any reset
    if (liveSolved.has(base) || coveredByLaterTests.has(base)) continue;
    if ((firstWorked.get(base) ?? -Infinity) >= xpStart) continue;
    solved.add(base);
    events.push({
      uid: `backfill-solve-${base}`,
      type: "solve",
      day: null,
      at: 0,
      item: base,
      course,
      topic,
      // Only a ProofLab-made version was Correct: XP files it under the book problem, but the
      // book problem itself wasn't solved, so chapter dates must ignore it.
      data: {
        difficulty: 0,
        checks: 0,
        hints: 0,
        ...(input.progress[base] === "correct" ? {} : { variant: true }),
      },
    });
  }
  for (const [id, record] of Object.entries(input.tests)) {
    const match = /^\/tests\/([^/?#]+)\/(quiz|midterm|final)/.exec(record.href ?? "");
    if (!record.submittedAt || !record.results || !match || testsSeen.has(id)) continue;
    if (record.submittedAt >= xpStart || record.submittedAt <= resetAt) continue;
    if (!input.isLiveCourse(match[1])) continue;
    events.push({
      uid: `backfill-test-${id}`,
      type: "test",
      day: input.dayOf(record.submittedAt),
      at: record.submittedAt,
      item: id,
      course: match[1],
      topic: "",
      data: {
        kind: match[2] as TestKind,
        questions: Object.values(record.results).map((r) => ({
          difficulty: 0,
          format: r.choice ? ("choice" as const) : ("written" as const),
          status: (["correct", "partial", "incorrect", "invalid"].includes(r.verdict.status)
            ? r.verdict.status
            : "incorrect") as TestQuestionFact["status"],
          blank: r.steps.length === 0 && r.answer === "",
        })),
      },
    });
  }
  for (const r of input.reviews) {
    if (r.kind !== "card" && r.kind !== "note") continue;
    if (!(r.course === "notes" || input.isLiveCourse(r.course))) continue;
    if (r.at >= xpStart || r.at <= resetAt) continue;
    events.push({
      uid: `backfill-card-${r.uid}`,
      type: "card",
      day: input.dayOf(r.at),
      at: r.at,
      item: r.item,
      course: r.course,
      topic: r.topic,
    });
  }
  return events;
}
