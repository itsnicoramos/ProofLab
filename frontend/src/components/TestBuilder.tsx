"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { useLearn } from "@/lib/learn";
import { COURSE_SHORT } from "@/lib/labels";
import { DEFAULT_LENGTH, DEFAULT_STYLE, randomSeed, testHref } from "@/lib/testUrl";
import type { CourseId, TestKind, TestStyle } from "@/lib/types";

export interface BuilderCourse {
  id: CourseId;
  /** Topics with problems, in course order, with display labels. */
  topics: { topic: string; label: string; problems: number }[];
}

const MAX_LENGTH = 30;

const KINDS: { id: TestKind; label: string; help: string }[] = [
  { id: "midterm", label: "Midterm", help: "First half of the chapters, 8 questions." },
  { id: "final", label: "Final", help: "Every chapter, 12 questions." },
  { id: "quiz", label: "Quick quiz", help: "Every chapter, 10 quick questions." },
];

const STYLES: { id: TestStyle; label: string; help: string }[] = [
  { id: "written", label: "Written", help: "Write out the work; every step is checked." },
  { id: "mixed", label: "Mixed", help: "About half multiple choice, half written." },
  { id: "choice", label: "Multiple choice", help: "Pick the answer, or spot the wrong step." },
];

/** Same rule as the backend: a midterm covers the first half of the chapters (rounded up). */
function defaultTopics(course: BuilderCourse, kind: TestKind): string[] {
  const all = course.topics.map((t) => t.topic);
  return kind !== "midterm" ? all : all.slice(0, Math.max(1, Math.ceil(all.length / 2)));
}

function Segmented<T extends string>({
  name,
  options,
  value,
  onChange,
}: {
  name: string;
  options: { id: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex gap-2">
      {options.map((o) => (
        <label
          key={o.id}
          className={`flex min-h-11 flex-1 cursor-pointer items-center justify-center rounded-lg border px-2 text-center text-sm transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-accent ${
            value === o.id ? "border-ink bg-ink font-medium text-bg" : "border-line hover:border-accent"
          }`}
        >
          <input
            type="radio"
            name={name}
            value={o.id}
            checked={value === o.id}
            onChange={() => onChange(o.id)}
            className="sr-only"
          />
          {o.label}
        </label>
      ))}
    </div>
  );
}

export function TestBuilder({ courses }: { courses: BuilderCourse[] }) {
  const router = useRouter();
  const ids = useId();
  const learn = useLearn();
  const [courseId, setCourseId] = useState<CourseId>(courses[0].id);
  const [kind, setKind] = useState<TestKind>("midterm");
  const [style, setStyle] = useState<TestStyle | null>(null); // null = the kind's default
  const [chosen, setChosen] = useState<string[] | null>(null); // null = the default for the kind
  const [lengthText, setLengthText] = useState<string | null>(null); // null = the default
  const [focus, setFocus] = useState(false);
  const [variants, setVariants] = useState(false);
  const [pending, setPending] = useState(false);

  const course = courses.find((c) => c.id === courseId) ?? courses[0];
  const defaults = defaultTopics(course, kind);
  const topics = chosen ?? defaults;
  const pickedStyle = style ?? DEFAULT_STYLE[kind];
  const available = course.topics
    .filter((t) => topics.includes(t.topic))
    .reduce((sum, t) => sum + t.problems, 0);
  const cap = Math.min(available, MAX_LENGTH);
  const length = lengthText === null ? Math.min(DEFAULT_LENGTH[kind], cap) : Number(lengthText);
  const lengthValid = Number.isInteger(length) && length >= 1 && length <= cap;
  const canStart = topics.length > 0 && lengthValid && !pending;
  const tried = Object.keys(learn.ability).filter((k) => k.startsWith(`${course.id}/`)).length;

  function toggle(topic: string) {
    const next = topics.includes(topic) ? topics.filter((t) => t !== topic) : [...topics, topic];
    setChosen(course.topics.map((t) => t.topic).filter((t) => next.includes(t)));
  }

  function start() {
    if (!canStart) return;
    const isDefaultScope =
      topics.length === defaults.length && topics.every((t) => defaults.includes(t));
    setPending(true);
    router.push(
      testHref(
        {
          course: course.id,
          kind,
          topics: isDefaultScope ? null : topics,
          length,
          style: pickedStyle,
          variants,
          focus,
        },
        randomSeed(),
        learn,
        course.topics.map((t) => t.topic),
      ),
    );
  }

  return (
    <form
      className="space-y-6 rounded-xl border border-line bg-surface p-4 sm:p-6"
      onSubmit={(e) => {
        e.preventDefault();
        start();
      }}
    >
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <label htmlFor={`${ids}-course`} className="mb-1.5 block text-sm font-medium">
            Course
          </label>
          <select
            id={`${ids}-course`}
            value={course.id}
            onChange={(e) => {
              setCourseId(e.target.value as CourseId);
              setChosen(null);
              setLengthText(null);
            }}
            className="h-11 w-full rounded-lg border border-line bg-bg px-3 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent"
          >
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {COURSE_SHORT[c.id]}
              </option>
            ))}
          </select>
        </div>

        <fieldset>
          <legend className="mb-1.5 text-sm font-medium">Kind</legend>
          <Segmented
            name={`${ids}-kind`}
            options={KINDS}
            value={kind}
            onChange={(k) => {
              setKind(k);
              setChosen(null);
              setLengthText(null);
              setStyle(null);
            }}
          />
          <p className="mt-1.5 text-xs text-muted">{KINDS.find((k) => k.id === kind)?.help}</p>
        </fieldset>
      </div>

      <fieldset>
        <legend className="mb-1.5 text-sm font-medium">Questions are</legend>
        <Segmented name={`${ids}-style`} options={STYLES} value={pickedStyle} onChange={setStyle} />
        <p className="mt-1.5 text-xs text-muted">
          {STYLES.find((s) => s.id === pickedStyle)?.help} The wrong choices come from common
          mistakes, and each one is checked to be wrong.
        </p>
      </fieldset>

      <fieldset>
        <legend className="mb-1.5 text-sm font-medium">Chapters</legend>
        <div className="grid gap-1 md:grid-cols-2">
          {course.topics.map((t) => (
            <label
              key={t.topic}
              className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md px-2 hover:bg-surface-2"
            >
              <input
                type="checkbox"
                checked={topics.includes(t.topic)}
                onChange={() => toggle(t.topic)}
                className="h-5 w-5 accent-accent"
              />
              <span className="flex-1 text-sm">{t.label}</span>
              <span className="text-xs text-muted">{t.problems}</span>
            </label>
          ))}
        </div>
        {chosen !== null && (
          <button
            type="button"
            onClick={() => setChosen(null)}
            className="mt-1 h-11 px-2 text-sm text-muted underline-offset-4 hover:text-ink hover:underline"
          >
            Use the usual chapters
          </button>
        )}
      </fieldset>

      <div>
        <label htmlFor={`${ids}-length`} className="mb-1.5 block text-sm font-medium">
          Number of questions
        </label>
        <input
          id={`${ids}-length`}
          type="number"
          inputMode="numeric"
          min={1}
          max={Math.max(cap, 1)}
          value={lengthText ?? String(length)}
          onChange={(e) => setLengthText(e.target.value)}
          aria-describedby={`${ids}-length-help`}
          aria-invalid={!lengthValid || undefined}
          className="h-11 w-28 rounded-lg border border-line bg-bg px-3 font-mono text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent aria-[invalid]:border-bad"
        />
        <p id={`${ids}-length-help`} className="mt-1.5 text-xs text-muted">
          {topics.length === 0
            ? "Pick at least one chapter."
            : lengthValid
              ? `Up to ${cap} from the chapters you picked.`
              : `Enter a whole number from 1 to ${cap}.`}
        </p>
      </div>

      <fieldset className="space-y-1">
        <legend className="mb-1.5 text-sm font-medium">Let ProofLab adapt the test</legend>
        <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-md px-2 py-2 hover:bg-surface-2">
          <input
            type="checkbox"
            checked={focus}
            onChange={(e) => setFocus(e.target.checked)}
            className="mt-0.5 h-5 w-5 shrink-0 accent-accent"
          />
          <span className="text-sm">
            Focus on my weak spots
            <span className="block text-xs text-muted">
              {tried
                ? `Uses your saved results (${tried} chapter${tried === 1 ? "" : "s"} tried): weaker chapters get more questions, and problems due for review come first.`
                : "Uses your saved results once you've answered some questions. Until then, untried chapters get a little extra weight."}
            </span>
          </span>
        </label>
        <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-md px-2 py-2 hover:bg-surface-2">
          <input
            type="checkbox"
            checked={variants}
            onChange={(e) => setVariants(e.target.checked)}
            className="mt-0.5 h-5 w-5 shrink-0 accent-accent"
          />
          <span className="text-sm">
            Include new versions with different numbers
            <span className="block text-xs text-muted">
              Problems ProofLab can remake (51 so far: parity and direct proofs, truth tables, sets,
              induction sums) usually come as a version with new numbers, checked the same way and
              marked as not from the book.
            </span>
          </span>
        </label>
      </fieldset>

      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">
        <button
          type="submit"
          disabled={!canStart}
          className="h-11 rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {pending ? "Building…" : "Start test"}
        </button>
        <span className="text-xs text-muted">Each start picks a fresh set of questions.</span>
      </div>
    </form>
  );
}
