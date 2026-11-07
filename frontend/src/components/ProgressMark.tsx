"use client";

import { StatusIcon } from "@/components/Badges";
import { useProgress } from "@/lib/storage";

const TITLE = {
  correct: "You've solved this",
  partial: "Partly solved",
  incorrect: "Attempted",
  invalid: "Attempted",
} as const;

/** Shows this browser's best result for a problem (nothing if never attempted). */
export function ProgressMark({ problemId }: { problemId: string }) {
  const status = useProgress()[problemId];
  if (!status) return <span className="h-5 w-5" aria-hidden />;
  return (
    <span title={TITLE[status]}>
      <StatusIcon status={status === "invalid" ? "incorrect" : status} />
      <span className="sr-only">{TITLE[status]}</span>
    </span>
  );
}

/** "3 of 7 solved" for a list of problems. */
export function SolvedCount({ problemIds }: { problemIds: string[] }) {
  const progress = useProgress();
  const solved = problemIds.filter((id) => progress[id] === "correct").length;
  if (solved === 0) return null;
  return (
    <span className="text-xs text-ok">
      {solved} of {problemIds.length} solved
    </span>
  );
}
