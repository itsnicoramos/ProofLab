"use client";

import Link from "next/link";

import { Shelf } from "@/components/Shelf";
import { COURSE_NAV, topicLabel } from "@/lib/labels";
import { useStartedProblems } from "@/lib/storage";
import type { CourseId, VerdictStatus } from "@/lib/types";

export interface ProblemIndexEntry {
  title: string;
  course: CourseId;
  topic: string;
}

const STATUS_TEXT: Record<VerdictStatus | "draft", string> = {
  partial: "Partly there",
  incorrect: "Not solved yet",
  invalid: "Not solved yet",
  correct: "Solved",
  draft: "Started, not checked",
};

/** Problems this browser started but hasn't solved, newest first. Only real local progress. */
export function ContinueShelf({ problems }: { problems: Record<string, ProblemIndexEntry> }) {
  const started = useStartedProblems();
  if (started === null) return null; // server render and hydration: nothing to show yet

  const items = started.filter((s) => problems[s.id]);
  if (items.length === 0) {
    return (
      <p className="rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
        Problems you start show up here, so you can pick up where you left off. Choose any
        problem below to begin.
      </p>
    );
  }

  return (
    <Shelf id="continue" title="Continue" meta={`${items.length} in progress`} heading="h2">
      {items.map(({ id, status }) => {
        const p = problems[id];
        return (
          <Link
            key={id}
            href={`/problems/${id}`}
            className="flex w-[15rem] shrink-0 snap-start flex-col rounded-lg border border-line bg-surface p-4 transition-colors hover:border-accent"
          >
            <span className="text-xs text-muted">
              {COURSE_NAV[p.course]} · {topicLabel(p.topic, p.course)}
            </span>
            <span className="mt-1 line-clamp-2 font-serif text-[17px] leading-snug">{p.title}</span>
            <span className="mt-auto pt-3 text-sm text-accent">{STATUS_TEXT[status ?? "draft"]}</span>
          </Link>
        );
      })}
    </Shelf>
  );
}
