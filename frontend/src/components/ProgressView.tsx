"use client";

// The Progress page (SPEC §19): today's goal, the streak, a 12-week calendar, the level, every
// chapter's progress, milestones and recent XP. Everything is computed from this browser's
// copy of the activity log, best verdicts and study model; nothing here is invented.

import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { partsText } from "@/components/XpNote";
import { mastery, useLearn } from "@/lib/learn";
import { useProgress } from "@/lib/storage";
import { useSyncStatus } from "@/lib/sync";
import { resetXp, setGoal, useXpToday } from "@/lib/xp";
import {
  addDays,
  FREEZE_EVERY,
  GOALS,
  levelFor,
  MAX_FREEZES,
  type Milestone,
  milestones,
  type XpEntry,
} from "@/lib/xpRules";

export interface ProgressChapter {
  course: string;
  courseName: string;
  topic: string;
  label: string;
  ids: string[];
}

const GOAL_HINT: Record<number, string> = {
  20: "about 1 problem",
  50: "about 3 problems",
  100: "about 6 problems",
};

const WEEKS = 12;

function formatDay(day: string): string {
  return new Date(`${day}T12:00:00`).toLocaleDateString("en-CA", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Monday = 0 … Sunday = 6, from the date itself. */
function weekday(day: string): number {
  const [y, m, d] = day.split("-").map(Number);
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
}

function Bar({ value, max, label }: { value: number; max: number; label: string }) {
  const share = max > 0 ? Math.min(1, value / max) : 0;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={Math.min(value, max)}
      className="h-2 w-full overflow-hidden rounded-full bg-line"
    >
      <div className="h-full rounded-full bg-ink" style={{ width: `${share * 100}%` }} />
    </div>
  );
}

function Section({
  title,
  children,
  id,
}: {
  title: string;
  children: React.ReactNode;
  id: string;
}) {
  return (
    <section aria-labelledby={id} className="space-y-4 rounded-xl border border-line bg-surface p-5 sm:p-6">
      <h2 id={id} className="text-xl">
        {title}
      </h2>
      {children}
    </section>
  );
}

export function ProgressView({
  chapters,
  titles,
}: {
  chapters: ProgressChapter[];
  titles: Record<string, string>;
}) {
  const { activity, summary, ready, today, todayXp, goal, streak } = useXpToday();
  const progress = useProgress();
  const learn = useLearn();
  const sync = useSyncStatus();
  // A settled answer to "is there a database?": each 30 s sync briefly says "syncing", which
  // must not flip the wording back and forth.
  const db =
    sync.status === "local"
      ? "none"
      : sync.status === "saved" || (sync.status === "syncing" && sync.lastSaved !== null)
        ? "yes"
        : "unknown";
  const ids = useId();
  const [confirmReset, setConfirmReset] = useState(false);
  const resetTrigger = useRef<HTMLButtonElement>(null);
  const resetCancel = useRef<HTMLButtonElement>(null);
  const resetWasOpen = useRef(false);
  // Keep keyboard focus: on Cancel when the confirmation opens, back on the trigger when it closes.
  useEffect(() => {
    if (confirmReset) resetCancel.current?.focus();
    else if (resetWasOpen.current) resetTrigger.current?.focus();
    resetWasOpen.current = confirmReset;
  }, [confirmReset]);

  const level = levelFor(summary.total);
  const allMilestones = useMemo<Milestone[]>(() => {
    if (!streak) return [];
    // A chapter is complete on the day its last problem first became Correct: its first practice
    // solve of the book problem itself (not a ProofLab-made version), or its first right answer
    // in a practice test, whichever came first. Undated (pre-XP) solves came before all of that.
    // A problem with neither (made Correct before tests recorded their problems) can't be
    // dated, so the date is left off.
    const firstCorrect = new Map<string, { day: string | null; at: number }>();
    const note = (id: string, day: string | null, at: number) => {
      const prev = firstCorrect.get(id);
      if (!prev || at < prev.at) firstCorrect.set(id, { day, at });
    };
    for (const e of activity) {
      if (e.type === "solve" && e.data && "checks" in e.data && !e.data.variant) note(e.item, e.day, e.at);
      if (e.type === "test" && e.data && "questions" in e.data) {
        for (const q of e.data.questions) if (q.item && q.status === "correct") note(q.item, e.day, e.at);
      }
    }
    const done = chapters
      .filter((c) => c.ids.every((id) => progress[id] === "correct"))
      .map((c): Milestone => {
        const firsts = c.ids.map((id) => firstCorrect.get(id));
        const known = firsts.every((f) => f !== undefined);
        const dated = firsts
          .map((f) => f?.day)
          .filter((d): d is string => typeof d === "string")
          .sort();
        return {
          id: `chapter-${c.course}-${c.topic}`,
          title: `${c.label} complete`,
          detail: `Solved every ${c.courseName} problem in this chapter.`,
          earned: known && dated.length ? dated[dated.length - 1] : "",
          dateUnknown: !known,
        };
      });
    return [...milestones(activity, summary, streak), ...done];
  }, [activity, summary, streak, chapters, progress]);

  if (!ready || !today || !streak) {
    return (
      <div
        aria-busy
        aria-label="Loading progress"
        className="h-96 animate-pulse rounded-xl border border-line bg-surface motion-reduce:animate-none"
      />
    );
  }

  const toGo = Math.max(0, goal - todayXp);
  const earned = allMilestones.filter((m) => m.earned !== null);
  const notYet = allMilestones.filter((m) => m.earned === null);

  return (
    <div className="space-y-6">
      <Section title="Today" id={`${ids}-today`}>
        <div className="space-y-2">
          <p className="font-serif text-4xl tabular-nums">
            {todayXp} <span className="text-2xl text-muted">/ {goal} XP</span>
          </p>
          <Bar value={todayXp} max={goal} label="Today's XP toward the daily goal" />
          <p className="text-sm text-muted">
            {toGo === 0 ? "Daily goal done." : `${toGo} XP to go today.`}{" "}
            {todayXp === 0 && (
              <Link href="/" className="text-accent hover:underline">
                Pick a problem
              </Link>
            )}
          </p>
        </div>
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium">Daily goal</legend>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {GOALS.map((g) => (
              <label
                key={g}
                className={`flex min-h-11 cursor-pointer flex-col justify-center rounded-lg border px-3 py-1.5 text-sm transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-accent ${
                  goal === g ? "border-ink bg-ink text-bg" : "border-line hover:border-accent"
                }`}
              >
                <input
                  type="radio"
                  name={`${ids}-goal`}
                  value={g}
                  checked={goal === g}
                  onChange={() => setGoal(g)}
                  className="sr-only"
                />
                <span className="font-medium">{g} XP a day</span>
                <span className={`text-xs ${goal === g ? "text-bg/75" : "text-muted"}`}>
                  {GOAL_HINT[g]}
                </span>
              </label>
            ))}
          </div>
          <p className="mt-1.5 text-xs text-muted">The goal is kept in this browser.</p>
        </fieldset>
      </Section>

      <Section title="Streak" id={`${ids}-streak`}>
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
          <p className="font-serif text-4xl tabular-nums">
            {streak.current} <span className="text-2xl text-muted">{streak.current === 1 ? "day" : "days"}</span>
          </p>
          <p className="text-sm text-muted">Best: {streak.best} {streak.best === 1 ? "day" : "days"}</p>
        </div>
        <p className="text-sm">
          {streak.current === 0
            ? "Earn any XP today to start a streak."
            : streak.today
              ? "Today counts. Come back tomorrow to keep it going."
              : `Earn any XP today to keep your ${streak.current}-day streak.`}
        </p>
        <p className="text-sm text-muted">
          {streak.freezes === 0
            ? "No streak freezes yet."
            : streak.freezes === 1
              ? "1 streak freeze ready."
              : `${streak.freezes} streak freezes ready.`}{" "}
          You earn one for every {FREEZE_EVERY} days in a row (up to {MAX_FREEZES}). A missed day
          uses one automatically.
        </p>
        <Calendar byDay={summary.byDay} frozen={streak.frozen} today={today} goal={goal} />
      </Section>

      <Section title={`Level ${level.level}`} id={`${ids}-level`}>
        <div className="space-y-2">
          <p className="text-sm">
            <span className="font-semibold tabular-nums">{summary.total.toLocaleString("en-CA")} XP</span>{" "}
            <span className="text-muted">
              in total. {level.next - summary.total} XP to level {level.level + 1}.
            </span>
          </p>
          <Bar
            value={summary.total - level.start}
            max={level.next - level.start}
            label={`Progress to level ${level.level + 1}`}
          />
        </div>
        <dl className="grid grid-cols-3 gap-2 text-sm">
          {(
            [
              ["Practice", summary.bySource.practice],
              ["Tests", summary.bySource.tests],
              ["Flashcards", summary.bySource.cards],
            ] as const
          ).map(([label, xp]) => (
            <div key={label} className="rounded-lg border border-line px-3 py-2">
              <dt className="text-xs text-muted">{label}</dt>
              <dd className="font-medium tabular-nums">{xp} XP</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="Chapters" id={`${ids}-chapters`}>
        <ul className="divide-y divide-line">
          {chapters.map((c) => {
            const solved = c.ids.filter((id) => progress[id] === "correct").length;
            const skill = mastery(learn, c.course, c.topic);
            return (
              <li key={`${c.course}/${c.topic}`} className="space-y-1.5 py-3">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <Link
                    href={`/courses/${c.course}#${c.topic}`}
                    className="min-h-11 py-2 font-medium hover:text-accent sm:min-h-0 sm:py-0"
                  >
                    {c.label}
                  </Link>
                  <span className={`text-sm tabular-nums ${solved === c.ids.length ? "text-ok" : "text-muted"}`}>
                    {solved === c.ids.length ? "Complete" : `${solved} of ${c.ids.length} solved`}
                  </span>
                </div>
                <Bar value={solved} max={c.ids.length} label={`${c.label}: problems solved`} />
                <p className="text-xs text-muted">
                  {skill === null
                    ? "Skill: not tried yet"
                    : `Skill: about ${Math.round(skill * 100)}% chance on a medium problem`}
                </p>
              </li>
            );
          })}
        </ul>
      </Section>

      <Section title="Milestones" id={`${ids}-milestones`}>
        {earned.length === 0 && <p className="text-sm text-muted">None yet. Solve a problem to earn the first one.</p>}
        {earned.length > 0 && (
          <ul className="space-y-2">
            {earned.map((m) => (
              <li key={m.id} className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
                <span>
                  <span className="font-medium">{m.title}</span>
                  <span className="text-muted"> · {m.detail}</span>
                </span>
                {!m.dateUnknown && (
                  <span className="text-xs text-muted">{m.earned ? formatDay(m.earned) : "Earlier"}</span>
                )}
              </li>
            ))}
          </ul>
        )}
        {notYet.length > 0 && (
          <details className="text-sm">
            <summary className="flex min-h-11 cursor-pointer items-center text-muted hover:text-ink">
              Not earned yet ({notYet.length})
            </summary>
            <ul className="space-y-1.5 pb-1 text-muted">
              {notYet.map((m) => (
                <li key={m.id}>
                  {m.title} · {m.detail}
                </li>
              ))}
            </ul>
          </details>
        )}
      </Section>

      <Section title="Recent XP" id={`${ids}-recent`}>
        <Recent entries={summary.entries} titles={titles} />
      </Section>

      <div className="space-y-2 border-t border-line pt-6 text-sm">
        <p className="text-muted">
          {db === "none"
            ? "XP is saved in this browser only: this server keeps no progress database."
            : db === "yes"
              ? "XP is saved in this browser and in the progress database, so your devices share it."
              : "XP is saved in this browser, and in the progress database whenever it can be reached."}
        </p>
        {confirmReset ? (
          <div
            role="group"
            aria-labelledby={`${ids}-reset-question`}
            onKeyDown={(e) => {
              if (e.key === "Escape") setConfirmReset(false);
            }}
            className="flex flex-wrap items-center gap-3"
          >
            <span id={`${ids}-reset-question`}>
              {db === "none"
                ? "Forget all XP, streaks and milestones in this browser?"
                : db === "yes"
                  ? "Forget all XP, streaks and milestones on every device?"
                  : "Forget all XP, streaks and milestones?"}{" "}
              Your answers, test results and flashcard schedule stay, and so do chapter completions,
              which come from your answers.
            </span>
            <button
              type="button"
              onClick={() => {
                resetXp();
                setConfirmReset(false);
              }}
              className="h-11 rounded-lg bg-bad px-4 font-medium text-bg"
            >
              Reset XP
            </button>
            <button
              ref={resetCancel}
              type="button"
              onClick={() => setConfirmReset(false)}
              className="h-11 px-2 text-muted hover:text-ink"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            ref={resetTrigger}
            type="button"
            onClick={() => setConfirmReset(true)}
            className="h-11 px-1 text-muted underline-offset-4 hover:text-ink hover:underline"
          >
            Reset XP and streak
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- the calendar

function Calendar({
  byDay,
  frozen,
  today,
  goal,
}: {
  byDay: Record<string, number>;
  frozen: string[];
  today: string;
  goal: number;
}) {
  const start = addDays(today, -((WEEKS - 1) * 7 + weekday(today)));
  const frozenSet = new Set(frozen);
  const columns = Array.from({ length: WEEKS }, (_, w) =>
    Array.from({ length: 7 }, (_, d) => addDays(start, w * 7 + d)),
  );
  const shown = columns.flat().filter((d) => d <= today);
  const active = shown.filter((d) => (byDay[d] ?? 0) > 0).length;
  const met = shown.filter((d) => (byDay[d] ?? 0) >= goal).length;
  const cell = (d: string) => {
    if (d > today) return "bg-transparent";
    const xp = byDay[d] ?? 0;
    if (xp >= goal) return "bg-ink";
    if (xp > 0) return "bg-ink/35";
    if (frozenSet.has(d)) return "border border-dashed border-ink/60";
    return "bg-line";
  };
  return (
    <figure className="space-y-2">
      <div aria-hidden className="flex gap-1">
        {columns.map((col, w) => (
          <div key={w} className="grid grid-rows-7 gap-1">
            {col.map((d) => (
              <span
                key={d}
                title={d > today ? undefined : `${formatDay(d)}: ${byDay[d] ?? 0} XP${frozenSet.has(d) ? " (freeze used)" : ""}`}
                className={`h-4 w-4 rounded-sm ${cell(d)} ${d === today ? "ring-2 ring-accent ring-offset-1 ring-offset-surface" : ""}`}
              />
            ))}
          </div>
        ))}
      </div>
      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
        <span>
          Last {WEEKS} weeks: XP on {active} {active === 1 ? "day" : "days"}, goal met on {met}.
        </span>
        <span aria-hidden className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-sm bg-line" /> none
          <span className="ml-2 h-3 w-3 rounded-sm bg-ink/35" /> some
          <span className="ml-2 h-3 w-3 rounded-sm bg-ink" /> goal
          <span className="ml-2 h-3 w-3 rounded-sm border border-dashed border-ink/60" /> freeze
        </span>
      </figcaption>
    </figure>
  );
}

// ---------------------------------------------------------------- recent XP

interface Row {
  key: string;
  day: string | null;
  label: string;
  detail: string | null;
  xp: number;
  /** Flashcards on one day are one row. */
  cards?: number;
}

const TEST_NAME: Record<string, string> = {
  quiz: "Quick quiz",
  midterm: "Practice midterm",
  final: "Practice final",
};

const MAX_ROWS = 15;

function rows(entries: XpEntry[], titles: Record<string, string>): Row[] {
  const out: Row[] = [];
  for (const e of [...entries].reverse()) {
    const last = out[out.length - 1];
    if (e.type === "card" && last?.cards && last.day === e.day) {
      last.cards += 1;
      last.xp += e.xp;
      last.label = `${last.cards} flashcards`;
      continue;
    }
    if (out.length >= MAX_ROWS) break;
    if (e.type === "card") {
      out.push({ key: `cards-${e.uid}`, day: e.day, label: "1 flashcard", detail: null, xp: e.xp, cards: 1 });
      continue;
    }
    const label =
      e.type === "test"
        ? (TEST_NAME[e.item.split("-")[0]] ?? "Practice test")
        : (titles[e.item] ?? e.item);
    out.push({
      key: e.uid,
      day: e.day,
      label,
      detail: e.note ?? (e.parts.length > 1 ? partsText(e.parts) : null),
      xp: e.xp,
    });
  }
  return out;
}

function Recent({ entries, titles }: { entries: XpEntry[]; titles: Record<string, string> }) {
  const list = rows(entries, titles);
  if (list.length === 0) {
    return <p className="text-sm text-muted">Nothing yet. Every right answer shows up here.</p>;
  }
  return (
    <ul className="divide-y divide-line text-sm">
      {list.map((r) => (
        <li key={r.key} className="flex items-baseline gap-3 py-2.5">
          <span className="w-24 shrink-0 text-xs text-muted">{r.day ? formatDay(r.day) : "Earlier"}</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate">{r.label}</span>
            {r.detail && <span className="block text-xs text-muted">{r.detail}</span>}
          </span>
          <span className={`shrink-0 tabular-nums ${r.xp > 0 ? "font-medium" : "text-muted"}`}>
            {r.xp > 0 ? `+${r.xp}` : "0"} XP
          </span>
        </li>
      ))}
    </ul>
  );
}
