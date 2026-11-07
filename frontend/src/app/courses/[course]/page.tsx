import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ProblemCard } from "@/components/ProblemCard";
import { SolvedCount } from "@/components/ProgressMark";
import { Shelf } from "@/components/Shelf";
import { getCourses, getProblems } from "@/lib/api";
import { COURSE_SHORT, isCourseId, topicLabel } from "@/lib/labels";
import type { ProblemSummary } from "@/lib/types";

export async function generateMetadata(props: PageProps<"/courses/[course]">): Promise<Metadata> {
  const { course } = await props.params;
  return { title: isCourseId(course) ? COURSE_SHORT[course] : "Course" };
}

export default function CoursePage(props: PageProps<"/courses/[course]">) {
  return (
    <Suspense fallback={<CourseSkeleton />}>
      <CourseContent params={props.params} />
    </Suspense>
  );
}

async function CourseContent({ params }: { params: Promise<{ course: string }> }) {
  const { course } = await params;
  if (!isCourseId(course)) notFound();
  const [courses, problems] = await Promise.all([getCourses(), getProblems(course)]);
  const summary = courses.find((c) => c.id === course);
  if (!summary) notFound();

  const byTopic = new Map<string, ProblemSummary[]>();
  for (const p of problems) byTopic.set(p.topic, [...(byTopic.get(p.topic) ?? []), p]);
  const filled = summary.topics.filter((t) => (byTopic.get(t.topic)?.length ?? 0) > 0);
  const empty = summary.topics.filter((t) => (byTopic.get(t.topic)?.length ?? 0) === 0);

  return (
    <div className="space-y-10">
      <header className="space-y-3">
        <h1 className="text-3xl sm:text-4xl">{summary.title}</h1>
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
          <span>{summary.problems} problems</span>
          <SolvedCount problemIds={problems.map((p) => p.id)} />
        </div>
        {filled.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <Link
              href={`/tests/${course}/midterm`}
              className="flex h-11 items-center rounded-lg bg-accent px-4 text-sm font-semibold text-accent-ink transition hover:opacity-90"
            >
              Practice midterm
            </Link>
            <Link
              href={`/tests/${course}/final`}
              className="flex h-11 items-center rounded-lg border border-line px-4 text-sm font-medium hover:border-accent"
            >
              Practice final
            </Link>
          </div>
        )}
        {filled.length > 1 && (
          <nav aria-label="Jump to a topic" className="flex flex-wrap gap-2 pt-1">
            {filled.map((t) => (
              <a
                key={t.topic}
                href={`#${t.topic}`}
                className="flex h-11 items-center rounded-md border border-line bg-surface px-3 text-sm hover:border-accent"
              >
                {topicLabel(t.topic, course)}
              </a>
            ))}
          </nav>
        )}
      </header>

      {filled.length === 0 && <p className="text-muted">This course has no problems yet.</p>}

      {filled.map((t) => {
        const list = byTopic.get(t.topic) ?? [];
        return (
          <Shelf
            key={t.topic}
            id={t.topic}
            title={topicLabel(t.topic, course)}
            meta={`${list.length} problems`}
            heading="h2"
            expandable
          >
            {list.map((p) => (
              <ProblemCard key={p.id} problem={p} />
            ))}
          </Shelf>
        );
      })}

      {empty.length > 0 && (
        <section aria-labelledby="later-heading" className="border-t border-line pt-6">
          <h2 id="later-heading" className="text-lg">
            Not in ProofLab yet
          </h2>
          <p className="mt-1 text-sm text-muted">
            These topics have no checkable problems yet:{" "}
            {empty.map((t) => topicLabel(t.topic, course)).join(", ")}.
          </p>
        </section>
      )}
    </div>
  );
}

function CourseSkeleton() {
  return (
    <div className="space-y-6" aria-busy aria-label="Loading course">
      <div className="h-9 w-72 animate-pulse rounded bg-line motion-reduce:animate-none" />
      <div className="flex gap-3 overflow-hidden">
        {[0, 1, 2, 3].map((card) => (
          <div
            key={card}
            className="h-48 w-[17rem] shrink-0 animate-pulse rounded-lg border border-line bg-surface motion-reduce:animate-none"
          />
        ))}
      </div>
    </div>
  );
}
