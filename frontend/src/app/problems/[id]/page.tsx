import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { DifficultyDots, ReviewBadge } from "@/components/Badges";
import { Rich } from "@/components/Rich";
import { Workspace } from "@/components/Workspace";
import { getProblem, getProblems } from "@/lib/api";
import { COURSE_SHORT, kindLabel, topicLabel } from "@/lib/labels";

export async function generateMetadata(props: PageProps<"/problems/[id]">): Promise<Metadata> {
  const { id } = await props.params;
  const problem = await getProblem(id).catch(() => null);
  return { title: problem?.title ?? "Problem" };
}

export default function ProblemPage(props: PageProps<"/problems/[id]">) {
  return (
    <Suspense fallback={<ProblemSkeleton />}>
      <ProblemContent params={props.params} />
    </Suspense>
  );
}

async function ProblemContent({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const problem = await getProblem(id);
  if (!problem) notFound();
  const siblings = await getProblems(problem.course, problem.topic);
  const index = siblings.findIndex((p) => p.id === problem.id);
  const prev = index > 0 ? siblings[index - 1] : null;
  const next = index >= 0 && index < siblings.length - 1 ? siblings[index + 1] : null;
  const ref = problem.reference;

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header className="space-y-3">
        <nav aria-label="Breadcrumb" className="text-sm text-muted">
          <Link
            href={`/courses/${problem.course}`}
            className="inline-flex min-h-11 items-center hover:text-ink"
          >
            {COURSE_SHORT[problem.course]}
          </Link>
          <span aria-hidden> / </span>
          <Link
            href={`/courses/${problem.course}#${problem.topic}`}
            className="inline-flex min-h-11 items-center hover:text-ink"
          >
            {topicLabel(problem.topic, problem.course)}
          </Link>
        </nav>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{problem.title}</h1>
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
          <span>{kindLabel(problem.kind)}</span>
          <DifficultyDots level={problem.difficulty} />
          <ReviewBadge status={problem.review_status} />
          {problem.variant_of && (
            <span className="rounded border border-line px-1.5 py-0.5 text-xs">
              Made by ProofLab, not from the book
            </span>
          )}
        </div>
      </header>

      <Rich
        text={problem.prompt}
        className="rounded-xl border border-line bg-surface px-5 py-5 text-[17px] leading-relaxed"
      />

      <Workspace
        problem={{
          id: problem.id,
          kind: problem.kind,
          step_kinds: problem.step_kinds,
          answer_format: problem.answer_format,
          hint_count: problem.hint_count,
          course: problem.course,
          topic: problem.topic,
          difficulty: problem.difficulty,
          variant_of: problem.variant_of,
        }}
      />

      <div className="grid gap-4 border-t border-line pt-6 text-sm sm:grid-cols-2">
        <details className="rounded-lg border border-line bg-surface px-4">
          <summary className="cursor-pointer py-3 font-medium">How to type this</summary>
          <p className="text-muted">{problem.syntax_help}</p>
          <Link
            href="/help"
            className="mb-1 inline-flex min-h-11 items-center text-accent hover:underline"
          >
            Full typing guide
          </Link>
        </details>
        <div className="rounded-lg border border-line bg-surface px-4 py-3">
          <p className="font-medium">Read more</p>
          <p className="mt-1 text-muted">
            <a href={ref.url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
              {ref.title}
            </a>
            {ref.edition ? `, ${ref.edition}` : ""}: {ref.section}
          </p>
          <p className="mt-1 text-xs text-muted">
            {ref.authors.join(", ")} · {ref.license}
          </p>
        </div>
      </div>

      <nav aria-label="More problems" className="flex justify-between gap-4 text-sm">
        {prev ? (
          <Link
            href={`/problems/${prev.id}`}
            className="inline-flex min-h-11 items-center text-muted hover:text-ink"
          >
            ← {prev.title}
          </Link>
        ) : (
          <span />
        )}
        {next && (
          <Link
            href={`/problems/${next.id}`}
            className="inline-flex min-h-11 items-center justify-end text-right text-muted hover:text-ink"
          >
            {next.title} →
          </Link>
        )}
      </nav>
    </div>
  );
}

function ProblemSkeleton() {
  return (
    <div className="mx-auto max-w-3xl space-y-6" aria-busy>
      <div className="h-8 w-64 animate-pulse rounded bg-line motion-reduce:animate-none" />
      <div className="h-28 animate-pulse rounded-xl border border-line bg-surface motion-reduce:animate-none" />
      <div className="h-12 animate-pulse rounded-lg border border-line bg-surface motion-reduce:animate-none" />
    </div>
  );
}
