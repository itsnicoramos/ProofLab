"use client";

// A chapter shelf's progress (SPEC §19): "3 of 12 solved", or "Chapter complete" once every
// problem in it has been checked Correct. Nothing until one is solved.

import { useProgress } from "@/lib/storage";

export function ChapterSolved({ problemIds }: { problemIds: string[] }) {
  const progress = useProgress();
  const solved = problemIds.filter((id) => progress[id] === "correct").length;
  if (solved === 0) return null;
  const done = solved === problemIds.length;
  return (
    <span className="text-sm text-ok">
      {done ? "Chapter complete" : `${solved} of ${problemIds.length} solved`}
    </span>
  );
}
