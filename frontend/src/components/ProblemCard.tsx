import Link from "next/link";

import { DifficultyDots } from "@/components/Badges";
import { MathPreview } from "@/components/MathPreview";
import { ProgressMark } from "@/components/ProgressMark";
import { kindLabel } from "@/lib/labels";
import type { ProblemSummary } from "@/lib/types";

/** A shelf card. Its "artwork" is the problem's own statement, typeset (DESIGN.md motif). */
export function ProblemCard({ problem }: { problem: ProblemSummary }) {
  return (
    <Link
      href={`/problems/${problem.id}`}
      className="flex w-[17rem] shrink-0 snap-start flex-col rounded-lg border border-line bg-surface p-4 transition-colors hover:border-accent"
    >
      <span className="text-xs text-muted">{kindLabel(problem.kind)}</span>
      <span className="mt-1 line-clamp-2 font-serif text-[17px] leading-snug text-ink">
        {problem.title}
      </span>
      <MathPreview
        text={problem.prompt}
        className="mt-3 line-clamp-4 text-sm leading-relaxed text-ink/85 [&_.katex-display]:my-1"
      />
      <span className="mt-auto flex items-center justify-between pt-4">
        <DifficultyDots level={problem.difficulty} />
        <ProgressMark problemId={problem.id} />
      </span>
    </Link>
  );
}

/** The last card in a capped home shelf: a real link to the full topic on its course page. */
export function SeeAllCard({ href, count, label }: { href: string; count: number; label: string }) {
  return (
    <Link
      href={href}
      className="flex w-[12rem] shrink-0 snap-start flex-col justify-center rounded-lg border border-dashed border-line p-4 text-sm text-muted transition-colors hover:border-accent hover:text-ink"
    >
      <span className="font-medium text-ink">See all {count}</span>
      <span className="mt-1">{label}</span>
    </Link>
  );
}
