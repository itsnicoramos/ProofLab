import Link from "next/link";
import { Suspense } from "react";

import { ContinueShelf, type ProblemIndexEntry } from "@/components/ContinueShelf";
import { ProblemCard, SeeAllCard } from "@/components/ProblemCard";
import { Shelf } from "@/components/Shelf";
import { getCourses, getProblems } from "@/lib/api";
import { COURSE_ORDER, topicLabel } from "@/lib/labels";
import type { ProblemSummary } from "@/lib/types";

// Home shelves show the first cards of each topic; the course page shows every problem.
const HOME_SHELF_LIMIT = 12;

export default function HomePage() {
  return (
    <div className="space-y-10">
      <header className="max-w-2xl space-y-2">
        <h1 className="text-3xl sm:text-4xl">Practice</h1>
        <p className="text-muted">
          Pick a problem and write it out one step at a time. ProofLab points at the first step
          that goes wrong and says why.
        </p>
      </header>
      <Suspense fallback={<ShelvesSkeleton />}>
        <Shelves />
      </Suspense>
    </div>
  );
}

async function Shelves() {
  const [courses, problems] = await Promise.all([getCourses(), getProblems()]);

  if (problems.length === 0) {
    return (
      <p className="text-muted">
        The checker is running but has no problems to show. Add problem files under
        <code className="mx-1 font-mono">backend/src/prooflab/content/problems</code>and restart it.
      </p>
    );
  }

  const index: Record<string, ProblemIndexEntry> = {};
  const byTopic = new Map<string, ProblemSummary[]>();
  for (const p of problems) {
    index[p.id] = { title: p.title, course: p.course, topic: p.topic };
    const key = `${p.course}/${p.topic}`;
    byTopic.set(key, [...(byTopic.get(key) ?? []), p]);
  }
  const byId = new Map(courses.map((c) => [c.id, c]));

  return (
    <div className="space-y-12">
      <ContinueShelf problems={index} />
      {COURSE_ORDER.map((courseId) => {
        const course = byId.get(courseId);
        if (!course || course.problems === 0) return null;
        const topics = course.topics.filter((t) => t.problems > 0);
        return (
          <section key={courseId} aria-labelledby={`${courseId}-heading`} className="space-y-6">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-line pb-2">
              <h2 id={`${courseId}-heading`} className="text-2xl">
                {course.title}
              </h2>
              <Link
                href={`/courses/${courseId}`}
                className="flex h-11 items-center text-sm text-accent hover:underline"
              >
                Open {course.problems} problems
              </Link>
            </div>
            {topics.map((t) => {
              const list = byTopic.get(`${courseId}/${t.topic}`) ?? [];
              const label = topicLabel(t.topic, courseId);
              return (
                <Shelf
                  key={t.topic}
                  id={`${courseId}-${t.topic}`}
                  title={label}
                  meta={`${list.length} problems`}
                >
                  {list.slice(0, HOME_SHELF_LIMIT).map((p) => (
                    <ProblemCard key={p.id} problem={p} />
                  ))}
                  {list.length > HOME_SHELF_LIMIT && (
                    <SeeAllCard
                      href={`/courses/${courseId}#${t.topic}`}
                      count={list.length}
                      label={label}
                    />
                  )}
                </Shelf>
              );
            })}
          </section>
        );
      })}
    </div>
  );
}

function ShelvesSkeleton() {
  return (
    <div className="space-y-8" aria-busy aria-label="Loading problems">
      {[0, 1, 2].map((row) => (
        <div key={row} className="space-y-3">
          <div className="h-6 w-56 animate-pulse rounded bg-line motion-reduce:animate-none" />
          <div className="flex gap-3 overflow-hidden">
            {[0, 1, 2, 3].map((card) => (
              <div key={card} className="h-48 w-[17rem] shrink-0 animate-pulse rounded-lg border border-line bg-surface motion-reduce:animate-none" />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
