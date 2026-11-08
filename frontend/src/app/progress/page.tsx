import type { Metadata } from "next";
import { Suspense } from "react";

import { type ProgressChapter, ProgressView } from "@/components/ProgressView";
import { getCourses, getProblems } from "@/lib/api";
import { COURSE_ORDER, COURSE_SHORT, topicLabel } from "@/lib/labels";

export const metadata: Metadata = { title: "Progress" };

export default function ProgressPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <header className="space-y-3">
        <h1 className="text-3xl sm:text-4xl">Progress</h1>
        <p className="text-muted">
          XP comes only from answers the checker marks right, from practice tests, and from
          flashcards you grade. A wrong answer costs nothing: fix it and try again.
        </p>
      </header>
      <Suspense fallback={<ProgressSkeleton />}>
        <Content />
      </Suspense>
    </div>
  );
}

async function Content() {
  const [courses, problems] = await Promise.all([getCourses(), getProblems()]);
  const titles: Record<string, string> = {};
  const byTopic = new Map<string, string[]>();
  for (const p of problems) {
    titles[p.id] = p.title;
    const key = `${p.course}/${p.topic}`;
    byTopic.set(key, [...(byTopic.get(key) ?? []), p.id]);
  }
  const chapters: ProgressChapter[] = [];
  for (const courseId of COURSE_ORDER) {
    const course = courses.find((c) => c.id === courseId);
    if (!course) continue;
    for (const t of course.topics) {
      const ids = byTopic.get(`${courseId}/${t.topic}`) ?? [];
      if (ids.length === 0) continue;
      chapters.push({
        course: courseId,
        courseName: COURSE_SHORT[courseId],
        topic: t.topic,
        label: topicLabel(t.topic, courseId),
        ids,
      });
    }
  }
  return <ProgressView chapters={chapters} titles={titles} />;
}

function ProgressSkeleton() {
  return (
    <div
      aria-busy
      aria-label="Loading progress"
      className="h-96 animate-pulse rounded-xl border border-line bg-surface motion-reduce:animate-none"
    />
  );
}
