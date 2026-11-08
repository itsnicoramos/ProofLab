"use client";

// One line above the home shelves (SPEC §19): today's XP against the goal, the streak, and how
// many problems are due for review. Reserves its height until the browser's copy is read, so
// the page doesn't jump.

import Link from "next/link";

import { isCourseId } from "@/lib/labels";
import { useLearn } from "@/lib/learn";
import { useClock } from "@/lib/storage";
import { useXpToday } from "@/lib/xp";

export function TodayStrip() {
  const { ready, todayXp, goal, streak } = useXpToday();
  const learn = useLearn();
  const now = useClock();
  if (!ready || !streak || now === null) return <div className="min-h-11" aria-hidden />;
  const due = Object.values(learn.items).filter(
    (it) => it.kind === "problem" && isCourseId(it.course) && it.due <= now,
  ).length;
  const parts = [
    todayXp >= goal ? `Daily goal done: ${todayXp} XP today` : `${todayXp} of ${goal} XP today`,
    streak.current > 0
      ? streak.today
        ? `${streak.current}-day streak`
        : `earn XP today to keep your ${streak.current}-day streak`
      : null,
    due > 0 ? `${due} ${due === 1 ? "problem" : "problems"} due for review` : null,
  ].filter(Boolean);
  return (
    <p className="flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-line bg-surface px-4 py-2 text-sm">
      <span className="tabular-nums">{parts.join(" · ")}</span>
      <Link href="/progress" className="flex h-11 items-center text-accent hover:underline sm:ml-auto">
        Progress
      </Link>
    </p>
  );
}
