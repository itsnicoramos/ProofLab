"use client";

// The top bar's link to the Progress page: today's XP against the daily goal, plus the streak
// from tablet width up (SPEC §19). Before the browser's copy is read it just says "Progress".

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useXpToday } from "@/lib/xp";

export function XpLink({ active }: { active: boolean }) {
  const { ready, todayXp, goal, streak } = useXpToday();
  const done = ready && todayXp >= goal;
  const days = streak?.current ?? 0;
  return (
    <Link
      href="/progress"
      aria-current={active ? "page" : undefined}
      className={`flex h-11 shrink-0 items-center gap-2 border-b-2 px-2.5 text-sm tabular-nums transition-colors ${
        active
          ? "border-accent font-medium text-ink"
          : "border-transparent text-muted hover:border-line hover:text-ink"
      }`}
    >
      {ready ? (
        <>
          {/* The spoken name starts with the visible XP (WCAG 2.5.3): "35 / 50 XP earned today,
              3-day streak. Progress". */}
          <span className={done ? "text-ok" : undefined}>
            {todayXp} / {goal} XP
          </span>
          <span className="sr-only"> earned today</span>
          {days > 0 && (
            <span className="hidden text-muted md:inline">
              <span className="sr-only">, </span>
              {days}-day streak
            </span>
          )}
          <span className="sr-only">. Progress</span>
        </>
      ) : (
        "Progress"
      )}
    </Link>
  );
}

/** The link with "you are here" marking. Wrap in <Suspense> (usePathname suspends). */
export function ActiveXpLink() {
  return <XpLink active={usePathname().startsWith("/progress")} />;
}
