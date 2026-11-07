import type { Metadata } from "next";
import { Suspense } from "react";

import { type BuilderCourse, TestBuilder } from "@/components/TestBuilder";
import { TestHistory } from "@/components/TestHistory";
import { getCourses } from "@/lib/api";
import { COURSE_ORDER, topicLabel } from "@/lib/labels";

export const metadata: Metadata = { title: "Practice tests" };

export default function TestsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <header className="space-y-3">
        <h1 className="text-3xl sm:text-4xl">Practice tests</h1>
        <p className="text-muted">
          A midterm, final or quick quiz built from the problems in ProofLab, written out step by
          step or as multiple choice. Nothing is checked until you submit. Then each question gets
          the same rule-based verdict as practice mode, and your results shape the next test.
        </p>
      </header>

      <Suspense fallback={<BuilderSkeleton />}>
        <Builder />
      </Suspense>

      <TestHistory />

      <section
        aria-labelledby="how-heading"
        className="space-y-2 border-t border-line pt-6 text-sm"
      >
        <h2 id="how-heading" className="text-lg">
          How a test is put together
        </h2>
        <ul className="list-disc space-y-1.5 pl-5 text-muted">
          <li>
            Questions are picked from the problem bank. With &ldquo;new versions&rdquo; on, most
            problems ProofLab can remake become a version with different numbers, built from the
            same problem, checked the same way, and marked as not from the book.
          </li>
          <li>Every chapter you pick gets at least one question, and bigger chapters get more.</li>
          <li>The mix aims for 3 easy : 5 medium : 2 hard, with different question types.</li>
          <li>
            Multiple choice: the wrong choices come from common mistakes and small slips (a sign, a
            number, one truth value). Each one is run through the checker and kept only if it is
            wrong. &ldquo;Spot the wrong step&rdquo; questions use worked attempts from the bank.
          </li>
          <li>
            &ldquo;Focus on my weak spots&rdquo; uses your saved results: chapters where
            you miss more get more questions, and problems due for review come first.
          </li>
          <li>
            The same link always gives the same test, so you can retake it or send it to a friend.
          </li>
        </ul>
      </section>
    </div>
  );
}

async function Builder() {
  const courses = await getCourses();
  const order = (id: string) => COURSE_ORDER.indexOf(id as (typeof COURSE_ORDER)[number]);
  const usable: BuilderCourse[] = courses
    .filter((c) => c.problems > 0)
    .sort((a, b) => order(a.id) - order(b.id))
    .map((c) => ({
      id: c.id,
      topics: c.topics
        .filter((t) => t.problems > 0)
        .map((t) => ({ topic: t.topic, label: topicLabel(t.topic, c.id), problems: t.problems })),
    }));

  if (usable.length === 0) {
    return <p className="text-muted">There are no problems to build a test from yet.</p>;
  }
  return <TestBuilder courses={usable} />;
}

function BuilderSkeleton() {
  return (
    <div
      aria-busy
      aria-label="Loading courses"
      className="h-96 animate-pulse rounded-xl border border-line bg-surface motion-reduce:animate-none"
    />
  );
}
