import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { Rich } from "@/components/Rich";
import { TestRunner, type TestQuestion } from "@/components/TestRunner";
import { getPracticeTest, getProblem } from "@/lib/api";
import { COURSE_SHORT, isCourseId, kindLabel, topicLabel } from "@/lib/labels";
import { DEFAULT_LENGTH } from "@/lib/testDefaults";
import type { TestKind, TestStyle } from "@/lib/types";

const isKind = (kind: string): kind is TestKind =>
  kind === "midterm" || kind === "final" || kind === "quiz";
const TOPICS_RE = /^[a-z0-9_-]+(,[a-z0-9_-]+)*$/;
const WEIGHTS_RE = /^[a-z0-9_-]+:\d{1,2}(\.\d{1,3})?(,[a-z0-9_-]+:\d{1,2}(\.\d{1,3})?)*$/;
const PREFER_RE = /^[a-z0-9._-]+(,[a-z0-9._-]+)*$/;
const STYLES: TestStyle[] = ["written", "mixed", "choice"];
const MAX_SEED = 2 ** 31 - 1;
const KIND_TITLE: Record<TestKind, string> = {
  midterm: "Practice midterm",
  final: "Practice final",
  quiz: "Quick quiz",
};

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/** Read the test's settings from the URL; anything malformed falls back to the default. */
function settings(search: Record<string, string | string[] | undefined>) {
  const seedRaw = Number(first(search.seed));
  const lengthRaw = Number(first(search.length));
  const topicsRaw = first(search.topics);
  const styleRaw = first(search.style) as TestStyle | undefined;
  const weightsRaw = first(search.weights);
  const preferRaw = first(search.prefer);
  return {
    seed: Number.isInteger(seedRaw) && seedRaw >= 0 && seedRaw <= MAX_SEED ? seedRaw : 1,
    length: Number.isInteger(lengthRaw) && lengthRaw >= 1 && lengthRaw <= 30 ? lengthRaw : null,
    topics: topicsRaw && TOPICS_RE.test(topicsRaw) ? topicsRaw : null,
    style: styleRaw && STYLES.includes(styleRaw) ? styleRaw : null,
    variants: first(search.variants) === "1",
    focus: first(search.focus) === "1",
    weights: weightsRaw && weightsRaw.length <= 1000 && WEIGHTS_RE.test(weightsRaw) ? weightsRaw : null,
    prefer: preferRaw && preferRaw.length <= 4000 && PREFER_RE.test(preferRaw) ? preferRaw : null,
  };
}

export async function generateMetadata(
  props: PageProps<"/tests/[course]/[kind]">,
): Promise<Metadata> {
  const { course, kind } = await props.params;
  if (!isCourseId(course) || !isKind(kind)) return { title: "Practice test" };
  return { title: `${KIND_TITLE[kind]} · ${COURSE_SHORT[course]}` };
}

export default function PracticeTestPage(props: PageProps<"/tests/[course]/[kind]">) {
  return (
    <Suspense fallback={<TestSkeleton />}>
      <TestContent params={props.params} searchParams={props.searchParams} />
    </Suspense>
  );
}

async function TestContent({
  params,
  searchParams,
}: {
  params: Promise<{ course: string; kind: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ course, kind }, search] = await Promise.all([params, searchParams]);
  if (!isCourseId(course) || !isKind(kind)) notFound();
  const opts = settings(search);
  const { seed, length, topics } = opts;
  const test = await getPracticeTest(course, kind, seed, {
    topics,
    length,
    style: opts.style,
    variants: opts.variants,
    weights: opts.weights,
    prefer: opts.prefer,
  });

  if (!test) {
    return (
      <div className="mx-auto max-w-2xl space-y-3">
        <h1 className="text-3xl">Can&apos;t build this test</h1>
        <p className="text-muted">
          {COURSE_SHORT[course]} has no problems in the chapters this link asks for.
        </p>
        <Link href="/tests" className="inline-flex h-11 items-center text-accent hover:underline">
          Build a different test
        </Link>
      </div>
    );
  }

  const details = await Promise.all(test.questions.map((q) => getProblem(q.problem.id)));
  const questions: TestQuestion[] = test.questions.flatMap((tq, i) => {
    const detail = details[i];
    const summary = tq.problem;
    if (!detail) return [];
    return [
      {
        id: summary.id,
        title: summary.title,
        topic: topicLabel(summary.topic, course),
        topicId: summary.topic,
        course,
        kind: kindLabel(summary.kind),
        difficulty: summary.difficulty,
        variantOf: summary.variant_of ?? null,
        format: tq.format,
        choice: tq.choice,
        problem: {
          id: detail.id,
          kind: detail.kind,
          step_kinds: detail.step_kinds,
          answer_format: detail.answer_format,
          hint_count: detail.hint_count,
        },
        prompt: (
          <Rich
            text={detail.prompt}
            className="rounded-xl border border-line bg-surface px-5 py-5 text-[17px] leading-relaxed"
          />
        ),
      },
    ];
  });

  const query = new URLSearchParams({ seed: String(test.seed) });
  if (topics) query.set("topics", test.topics.join(","));
  if (length !== null) query.set("length", String(length));
  if (opts.style && opts.style !== "written") query.set("style", opts.style);
  if (opts.variants) query.set("variants", "1");
  if (opts.focus) query.set("focus", "1");
  if (opts.weights) query.set("weights", opts.weights);
  if (opts.prefer) query.set("prefer", opts.prefer);
  const href = `/tests/${course}/${kind}?${String(query).replaceAll("%2C", ",").replaceAll("%3A", ":")}`;
  const chapters = test.topics.map((t) => topicLabel(t, course));
  const choiceCount = questions.filter((q) => q.format === "choice" && q.choice).length;
  const madeCount = questions.filter((q) => q.variantOf).length;

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header className="space-y-3">
        <nav aria-label="Breadcrumb" className="text-sm text-muted">
          <Link href="/tests" className="inline-flex min-h-11 items-center hover:text-ink">
            Practice tests
          </Link>
          <span aria-hidden> / </span>
          <Link href={`/courses/${course}`} className="inline-flex min-h-11 items-center hover:text-ink">
            {COURSE_SHORT[course]}
          </Link>
        </nav>
        <h1 className="text-3xl sm:text-4xl">{test.title}</h1>
        <p className="text-muted">
          {questions.length} questions · about {test.suggested_minutes} minutes · test #{test.seed}
        </p>
        <p className="text-sm text-muted">
          Covers {chapters.join(", ")}.{" "}
          {madeCount > 0
            ? `${madeCount} question${madeCount === 1 ? " is a version" : "s are versions"} ProofLab made with new numbers (marked, not from the book); the rest are problems already in ProofLab.`
            : "Every question is a problem already in ProofLab, so you can practise any of them again afterwards."}{" "}
          {choiceCount > 0 &&
            `${choiceCount === questions.length ? "Every question is" : `${choiceCount} questions are`} multiple choice: the wrong choices are common mistakes, each checked to be wrong. `}
          Timing is {test.minutes_rule}.
        </p>
        {opts.focus && (
          <p className="text-sm text-muted">
            Adapted to you: chapters you find harder get more questions, and problems due for
            review come first.
          </p>
        )}
        <p className="text-sm text-muted">
          Nothing is checked until you submit the whole test: no hints and no solutions until then.
          Your answers save in this browser as you type; your result is saved to ProofLab&apos;s
          database when you submit.
        </p>
      </header>

      <TestRunner
        testId={test.id}
        title={test.title}
        href={href}
        suggestedMinutes={test.suggested_minutes}
        settings={{
          course,
          kind,
          topics: topics ? test.topics : null,
          length: length ?? DEFAULT_LENGTH[kind],
          style: test.style,
          variants: test.variants,
          focus: opts.focus,
        }}
        allTopics={test.topics}
        questions={questions}
      />
    </div>
  );
}

function TestSkeleton() {
  return (
    <div className="mx-auto max-w-3xl space-y-6" aria-busy aria-label="Building your test">
      <div className="h-9 w-80 animate-pulse rounded bg-line motion-reduce:animate-none" />
      <div className="h-5 w-56 animate-pulse rounded bg-line motion-reduce:animate-none" />
      {[0, 1].map((q) => (
        <div
          key={q}
          className="h-48 animate-pulse rounded-xl border border-line bg-surface motion-reduce:animate-none"
        />
      ))}
    </div>
  );
}
