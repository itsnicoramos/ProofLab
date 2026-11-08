// Unit tests for the XP rules (SPEC §19). Run with `npm test` (node --test; Node 24 runs
// TypeScript directly, so there is nothing to install).

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  type Activity,
  addDays,
  backfillEvents,
  baseProblemId,
  levelFor,
  milestones,
  scoreActivity,
  streakFor,
  type TestData,
  testWorth,
} from "./xpRules.ts";

let n = 0;
const at = (day: string, minutes = 0) => Date.parse(`${day}T12:00:00Z`) + minutes * 60_000;

function solve(day: string | null, extra: Partial<Activity["data"]> = {}, item = "proofs.direct.p1", minutes = 0): Activity {
  n += 1;
  return {
    uid: `s${n}`,
    type: "solve",
    day,
    at: day ? at(day, minutes) : 0,
    item,
    course: "proofs",
    topic: "direct",
    data: { difficulty: 2, checks: 2, hints: 0, ...extra } as Activity["data"],
  };
}

function reveal(day: string, item = "proofs.direct.p1", minutes = 0): Activity {
  n += 1;
  return { uid: `r${n}`, type: "reveal", day, at: at(day, minutes), item, course: "proofs", topic: "direct" };
}

function testEvent(day: string, data: TestData, item = "midterm-abc", minutes = 0): Activity {
  n += 1;
  return { uid: `t${n}`, type: "test", day, at: at(day, minutes), item, course: "proofs", topic: "", data };
}

function card(day: string, item = "proofs.sets.card1", minutes = 0): Activity {
  n += 1;
  return { uid: `c${n}`, type: "card", day, at: at(day, minutes), item, course: "proofs", topic: "sets" };
}

const D = "2026-11-08";

test("a solve pays by difficulty, with a first-try bonus and a hint cost", () => {
  assert.equal(scoreActivity([solve(D, { difficulty: 1 })]).total, 10);
  assert.equal(scoreActivity([solve(D, { difficulty: 2 })]).total, 15);
  assert.equal(scoreActivity([solve(D, { difficulty: 3 })]).total, 20);
  assert.equal(scoreActivity([solve(D, { difficulty: 2, checks: 1 })]).total, 20);
  assert.equal(scoreActivity([solve(D, { difficulty: 3, hints: 1 })]).total, 15);
  // Never below 5, however many hints.
  assert.equal(scoreActivity([solve(D, { difficulty: 1, hints: 4 })]).total, 5);
});

test("the breakdown names each part", () => {
  const s = scoreActivity([solve(D, { difficulty: 2, checks: 1, hints: 1 })]);
  assert.deepEqual(
    s.entries[0].parts.map((p) => [p.label, p.xp]),
    [["Medium", 15], ["first try", 5], ["1 extra hint", -5]],
  );
  assert.equal(s.entries[0].xp, 15);
});

test("a problem pays once a day, and half on a later day", () => {
  const s = scoreActivity([solve(D, {}, "p", 0), solve(D, {}, "p", 5), solve(addDays(D, 1), {}, "p")]);
  assert.deepEqual(s.entries.map((e) => e.xp), [15, 0, 8]);
  assert.match(s.entries[1].note ?? "", /already earned/);
  assert.match(s.entries[2].note ?? "", /Half XP/);
});

test("opening the solution first pays nothing that day, but not the next", () => {
  const s = scoreActivity([reveal(D, "p", 0), solve(D, {}, "p", 5), solve(addDays(D, 1), {}, "p")]);
  assert.deepEqual(s.entries.map((e) => e.xp), [0, 8]);
  assert.match(s.entries[0].note ?? "", /worked solution/);
  // A reveal after solving doesn't take the XP back.
  assert.equal(scoreActivity([solve(D, {}, "q", 0), reveal(D, "q", 5)]).total, 15);
});

test("undated earlier work counts toward the total, not toward a day", () => {
  const s = scoreActivity([solve(null, { difficulty: 0, checks: 0 }, "old")]);
  assert.equal(s.total, 10);
  assert.deepEqual(s.byDay, {});
  // Solving it again later is a review: half.
  const again = scoreActivity([solve(null, { difficulty: 0, checks: 0 }, "old"), solve(D, {}, "old")]);
  assert.equal(again.entries[1].xp, 8);
});

const midterm = (statuses: string[], format: "written" | "choice" = "written"): TestData => ({
  kind: "midterm",
  questions: statuses.map((s) => ({
    difficulty: 2,
    format,
    status: (s === "blank" ? "incorrect" : s) as "correct",
    blank: s === "blank",
  })),
});

test("a test pays per question plus finishing and passing bonuses", () => {
  // 3 right (45) + 1 partly right (7.5) of 4 = 3.5 / 4 = 87.5%: 53 + 20 + 10.
  const worth = testWorth(midterm(["correct", "correct", "correct", "partial"]));
  assert.equal(worth.points, 3.5);
  assert.deepEqual(worth.parts.map((p) => p.xp), [53, 20, 10]);
  // Multiple choice pays 5 a right answer.
  assert.equal(testWorth(midterm(["correct", "incorrect"], "choice")).parts[0].xp, 5);
  // Under half answered: no finishing bonus.
  assert.deepEqual(testWorth(midterm(["correct", "blank", "blank", "blank"])).parts.map((p) => p.label), ["Questions"]);
  // Half answered but under 70%: finishing bonus only.
  assert.equal(testWorth({ ...midterm(["correct", "incorrect", "blank", "blank"]), kind: "final" }).xp, 15 + 30);
});

test("a retake pays only what beats your best on that test", () => {
  const good = midterm(["correct", "correct", "correct", "correct"]); // 60 + 20 + 10 = 90
  const worse = midterm(["correct", "incorrect", "incorrect", "incorrect"]); // 15 + 20 = 35
  const s = scoreActivity([
    testEvent(D, worse, "m", 0),
    testEvent(D, good, "m", 10),
    testEvent(D, worse, "m", 20),
    testEvent(D, good, "other", 30),
  ]);
  assert.deepEqual(s.entries.map((e) => e.xp), [35, 55, 0, 90]);
  assert.equal(s.tests.m.best, 90);
  assert.match(s.entries[2].note ?? "", /beats your best/);
});

test("flashcards pay 1 XP per card per day", () => {
  const s = scoreActivity([card(D, "a", 0), card(D, "a", 1), card(D, "b", 2), card(addDays(D, 1), "a")]);
  assert.deepEqual(s.entries.map((e) => e.xp), [1, 0, 1, 1]);
  assert.equal(s.bySource.cards, 3);
  assert.deepEqual(s.byDay, { [D]: 2, [addDays(D, 1)]: 1 });
});

test("dates step over month and year ends", () => {
  assert.equal(addDays("2026-12-31", 1), "2027-01-01");
  assert.equal(addDays("2028-02-28", 1), "2028-02-29");
  assert.equal(addDays("2026-03-01", -1), "2026-02-28");
});

const days = (start: string, count: number, skip: number[] = []) =>
  Object.fromEntries(
    Array.from({ length: count }, (_, i) => i)
      .filter((i) => !skip.includes(i))
      .map((i) => [addDays(start, i), 10]),
  );

test("a streak counts days in a row and survives today until it ends", () => {
  const byDay = days(D, 3);
  assert.equal(streakFor(byDay, addDays(D, 2)).current, 3);
  // Today has no XP yet: the streak is still 3, not broken.
  const s = streakFor(byDay, addDays(D, 3));
  assert.equal(s.current, 3);
  assert.equal(s.today, false);
  // A missed day with no freeze breaks it.
  assert.equal(streakFor(byDay, addDays(D, 4)).current, 0);
  assert.equal(streakFor(byDay, addDays(D, 4)).best, 3);
  assert.equal(streakFor({}, D).current, 0);
});

test("seven days in a row earn a freeze that covers one missed day", () => {
  // Days 0..6 active (earns a freeze), day 7 missed, days 8..9 active.
  const byDay = days(D, 10, [7]);
  const s = streakFor(byDay, addDays(D, 9));
  assert.equal(s.current, 9);
  assert.deepEqual(s.frozen, [addDays(D, 7)]);
  assert.equal(s.freezes, 0);
  // Without the seventh day there is no freeze, so the miss breaks it.
  const short = streakFor(days(D, 9, [6]), addDays(D, 8));
  assert.equal(short.current, 2);
  // Freezes cap at 2.
  assert.equal(streakFor(days(D, 28), addDays(D, 27)).freezes, 2);
  assert.equal(streakFor(days(D, 7), addDays(D, 6)).reached[7], addDays(D, 6));
});

test("levels start at 0, 100, 300, 600, 1000", () => {
  assert.deepEqual(levelFor(0), { level: 1, start: 0, next: 100 });
  assert.equal(levelFor(99).level, 1);
  assert.equal(levelFor(100).level, 2);
  assert.equal(levelFor(299).level, 2);
  assert.equal(levelFor(300).level, 3);
  assert.deepEqual(levelFor(600), { level: 4, start: 600, next: 1000 });
  assert.equal(levelFor(1000).level, 5);
});

test("milestones come only from real history", () => {
  const activity = [
    ...Array.from({ length: 10 }, (_, i) => solve(D, { hints: 0 }, `p${i}`, i)),
    { ...solve(D, {}, "proofs.induction.x", 20), topic: "induction" },
  ];
  const summary = scoreActivity(activity);
  const m = milestones(activity, summary, streakFor(summary.byDay, D));
  const earned = Object.fromEntries(m.map((x) => [x.id, x.earned]));
  assert.equal(earned["first-solve"], D);
  assert.equal(earned["first-induction"], D);
  assert.equal(earned["ten-clean"], D);
  assert.equal(earned["perfect-quiz"], null);
  assert.equal(earned["streak-7"], null);
  // A hint or an opened solution doesn't count toward "on your own".
  const helped = [solve(D, { hints: 1 }, "h"), reveal(D, "r", 0), solve(D, {}, "r", 1)];
  const hs = scoreActivity(helped);
  assert.equal(milestones(helped, hs, streakFor(hs.byDay, D)).find((x) => x.id === "ten-clean")?.earned, null);
});

test("the 5 XP floor shows in the breakdown, so the parts add up", () => {
  const e = scoreActivity([solve(D, { difficulty: 1, hints: 2 })]).entries[0];
  assert.equal(e.xp, 5);
  assert.deepEqual(e.parts.map((p) => [p.label, p.xp]), [["Easy", 10], ["2 extra hints", -10], ["minimum", 5]]);
  assert.equal(e.parts.reduce((s, p) => s + p.xp, 0), e.xp);
});

test("'Ten on your own': opening a solution after solving keeps it, before solving (any day) blocks it", () => {
  const ten = Array.from({ length: 10 }, (_, i) => solve(D, { hints: 0 }, `q${i}`, i));
  const after = [...ten, reveal(D, "q3", 30)];
  const s1 = scoreActivity(after);
  assert.equal(milestones(after, s1, streakFor(s1.byDay, D)).find((m) => m.id === "ten-clean")?.earned, D);
  // The solution of q3 opened the day before it was solved: q3 doesn't count, so only 9.
  const before = [reveal(addDays(D, -1), "q3", 0), ...ten];
  const s2 = scoreActivity(before);
  assert.equal(milestones(before, s2, streakFor(s2.byDay, D)).find((m) => m.id === "ten-clean")?.earned, null);
});

const live = (c: string) => c === "proofs";
const dayOf = (t: number) => new Date(t).toISOString().slice(0, 10);
const earlier = Date.parse("2026-11-01T12:00:00Z");

test("backfill folds ProofLab-made versions into their base problem", () => {
  assert.equal(baseProblemId("proofs.direct.p2-v11"), "proofs.direct.p2");
  assert.equal(baseProblemId("proofs.direct.p2"), "proofs.direct.p2");
  const events = backfillEvents({
    progress: {
      "proofs.direct.p2": "correct",
      "proofs.direct.p2-v11": "correct",
      "proofs.direct.p2-v12": "correct",
      "proofs.direct.p3-v4": "correct",
      "proofs.direct.p5": "partial",
      "calc1.limits.x": "correct",
    },
    tests: {},
    reviews: [],
    isLiveCourse: live,
    dayOf,
    existing: [],
  });
  assert.deepEqual(events.map((e) => e.uid).sort(), ["backfill-solve-proofs.direct.p2", "backfill-solve-proofs.direct.p3"]);
  assert.equal(scoreActivity(events).total, 20);
});

test("backfill skips what already has a live event, so a live solve is never halved", () => {
  // p1 was tried before XP, then solved live on another device (merged in by the first sync).
  const liveSolve = { ...solve(D, { difficulty: 2, checks: 1 }, "proofs.sets.p1"), course: "proofs", topic: "sets" };
  const liveVersion = { ...solve(D, {}, "proofs.sets.p2"), course: "proofs", topic: "sets" };
  const liveTest = testEvent(D, midterm(["correct"]), "quiz-new");
  const events = backfillEvents({
    progress: { "proofs.sets.p1": "correct", "proofs.sets.p2-v9": "correct", "proofs.sets.old": "correct" },
    tests: {
      "quiz-old": { href: "/tests/proofs/quiz?seed=1", submittedAt: earlier, results: { a: { verdict: { status: "correct" }, steps: [], answer: "a", choice: {} } } },
      "quiz-new": { href: "/tests/proofs/quiz?seed=2", submittedAt: at(D), results: { a: { verdict: { status: "correct" }, steps: [], answer: "a", choice: {} } } },
      "midterm-unsubmitted": { href: "/tests/proofs/midterm?seed=3" },
    },
    reviews: [
      { uid: "r1", item: "proofs.sets.p1", kind: "problem", course: "proofs", topic: "sets", at: earlier },
      { uid: "r3", item: "proofs.sets.card-a", kind: "card", course: "proofs", topic: "sets", at: earlier },
      { uid: "r5", item: "note:deck1:c1", kind: "note", course: "notes", topic: "deck1", at: earlier },
      { uid: "r6", item: "calc1.d.card", kind: "card", course: "calc1", topic: "d", at: earlier },
    ],
    isLiveCourse: live,
    dayOf,
    existing: [liveSolve, liveVersion, liveTest],
  });
  assert.deepEqual(events.map((e) => e.uid).sort(), [
    "backfill-card-r3",
    "backfill-card-r5",
    "backfill-solve-proofs.sets.old",
    "backfill-test-quiz-old",
  ]);
  const test = events.find((e) => e.type === "test");
  assert.equal(test?.day, dayOf(earlier));
  assert.deepEqual(test?.data, { kind: "quiz", questions: [{ difficulty: 0, format: "choice", status: "correct", blank: false }] });
  // The live solve keeps its full XP next to the backfill.
  const s = scoreActivity([liveSolve, ...events]);
  assert.equal(s.byUid[liveSolve.uid].xp, 20);
});

test("a card with both a backfilled and a live event the same day pays once", () => {
  const backfilled: Activity = { uid: "backfill-card-r9", type: "card", day: D, at: at(D, 1), item: "proofs.sets.card-z", course: "proofs", topic: "sets" };
  const liveCard = { ...card(D, "proofs.sets.card-z", 2) };
  assert.equal(scoreActivity([backfilled, liveCard]).bySource.cards, 1);
});

test("backfill takes only work from before XP started (the earliest live event)", () => {
  const xpStarted = card(D, "proofs.sets.first-live-card", 0); // XP started on D at 12:00
  const after = at(D, 60);
  const events = backfillEvents({
    progress: { "proofs.sets.from-test": "correct", "proofs.sets.old": "correct" },
    tests: {
      // Taken after XP started: it has its own live event, and it made from-test Correct.
      "quiz-later": { href: "/tests/proofs/quiz?seed=4", submittedAt: after, results: { "proofs.sets.from-test": { verdict: { status: "correct" }, steps: [], answer: "a" } } },
    },
    reviews: [
      // A wrong quiz answer after XP started paid nothing live; it must stay unpaid.
      { uid: "late", item: "proofs.sets.card-q", kind: "card", course: "proofs", topic: "sets", at: after },
      { uid: "early", item: "proofs.sets.card-q", kind: "card", course: "proofs", topic: "sets", at: earlier },
    ],
    isLiveCourse: live,
    dayOf,
    existing: [xpStarted],
  });
  assert.deepEqual(events.map((e) => e.uid).sort(), ["backfill-card-early", "backfill-solve-proofs.sets.old"]);
});

test("backfill brings back nothing a recorded reset forgot", () => {
  const resetAt = at(D);
  const events = backfillEvents({
    progress: { "proofs.sets.old": "correct" },
    tests: {
      "quiz-before": { href: "/tests/proofs/quiz?seed=5", submittedAt: earlier, results: { a: { verdict: { status: "correct" }, steps: [], answer: "a", choice: {} } } },
    },
    reviews: [
      { uid: "before", item: "proofs.sets.c", kind: "card", course: "proofs", topic: "sets", at: earlier },
      { uid: "after", item: "proofs.sets.c", kind: "card", course: "proofs", topic: "sets", at: resetAt + 1000 },
    ],
    isLiveCourse: live,
    dayOf,
    existing: [],
    resetAt,
  });
  assert.deepEqual(events.map((e) => e.uid), ["backfill-card-after"]);
});

test("a backfilled solve from a version only is marked as a version (chapter dates ignore it)", () => {
  const events = backfillEvents({
    progress: { "proofs.sets.b-v7": "correct", "proofs.sets.a": "correct", "proofs.sets.a-v2": "correct" },
    tests: {},
    reviews: [],
    isLiveCourse: live,
    dayOf,
    existing: [],
  });
  const byItem = Object.fromEntries(events.map((e) => [e.item, e.data]));
  assert.deepEqual(byItem["proofs.sets.b"], { difficulty: 0, checks: 0, hints: 0, variant: true });
  assert.deepEqual(byItem["proofs.sets.a"], { difficulty: 0, checks: 0, hints: 0 });
});

test("a live test event still covers its problems after an abandoned retake cleared the record", () => {
  const liveTest = testEvent(D, { kind: "midterm", questions: [{ item: "proofs.sets.p", difficulty: 2, format: "written", status: "correct", blank: false }] }, "midterm-m");
  const events = backfillEvents({
    progress: { "proofs.sets.p": "correct" },
    tests: { "midterm-m": { href: "/tests/proofs/midterm?seed=1" } }, // retake started, never submitted
    reviews: [{ uid: "r", item: "proofs.sets.p", kind: "problem", course: "proofs", topic: "sets", at: earlier }],
    isLiveCourse: live,
    dayOf,
    existing: [liveTest],
  });
  assert.deepEqual(events, []);
});
