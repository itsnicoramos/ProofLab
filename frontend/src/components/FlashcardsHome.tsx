"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { deleteDeck, noteItemId, useDecks } from "@/lib/decks";
import { formatInterval, resetLearning, summarize, useHydrated, useLearn } from "@/lib/learn";
import { COURSE_SHORT } from "@/lib/labels";
import { useClock } from "@/lib/storage";
import { useSyncStatus } from "@/lib/sync";
import { randomSeed, testHref } from "@/lib/testUrl";

/** Where the student's reviews are kept, and whether the latest ones have been saved there. */
function SyncNote() {
  const { status } = useSyncStatus();
  return (
    <p className="text-muted" aria-live="polite">
      Your reviews, decks and test results are saved in ProofLab&apos;s database (SQLite) on your
      Mac, so your phone and laptop share one schedule.{" "}
      {status === "offline"
        ? "The database isn't reachable right now: changes are kept in this browser and sent when it's back."
        : status === "saved"
          ? "Everything is saved."
          : status === "syncing"
            ? "Saving…"
            : ""}
    </p>
  );
}
import type { CourseId } from "@/lib/types";

export interface CardCourse {
  id: CourseId;
  topics: { topic: string; label: string; problems: number; concepts: number }[];
}

type Part = "concepts" | "problems";

function studyHref(course: string, topics: string[], parts: Part[], mode: "study" | "quiz") {
  const q = new URLSearchParams({ course, parts: parts.join(",") });
  if (topics.length) q.set("topics", topics.join(","));
  if (mode === "quiz") q.set("mode", "quiz");
  return `/cards/study?${String(q).replaceAll("%2C", ",")}`;
}

export function FlashcardsHome({ courses }: { courses: CardCourse[] }) {
  const ids = useId();
  const router = useRouter();
  const learn = useLearn();
  const hydrated = useHydrated();
  const decks = useDecks();
  const now = useClock();
  const [courseId, setCourseId] = useState<CourseId>(courses[0]?.id ?? "proofs");
  const [chosen, setChosen] = useState<string[] | null>(null);
  const [parts, setParts] = useState<Part[]>(["concepts", "problems"]);
  const [confirmReset, setConfirmReset] = useState(false);

  const course = courses.find((c) => c.id === courseId) ?? courses[0];
  if (!course) return <p className="text-muted">There are no cards yet.</p>;
  const topics = chosen ?? course.topics.map((t) => t.topic);
  const picked = course.topics.filter((t) => topics.includes(t.topic));
  const count =
    (parts.includes("concepts") ? picked.reduce((n, t) => n + t.concepts, 0) : 0) +
    (parts.includes("problems") ? picked.reduce((n, t) => n + t.problems, 0) : 0);
  const conceptCount = picked.reduce((n, t) => n + t.concepts, 0);
  const allTopics = topics.length === course.topics.length;
  const topicParam = allTopics ? [] : topics;

  const items = Object.values(learn.items);
  const due = now === null ? 0 : items.filter((it) => it.due <= now).length;
  const nextDue = now === null ? null : items.filter((it) => it.due > now).sort((a, b) => a.due - b.due)[0];
  const summary = summarize(learn);

  function toggleTopic(topic: string) {
    const next = topics.includes(topic) ? topics.filter((t) => t !== topic) : [...topics, topic];
    setChosen(course.topics.map((t) => t.topic).filter((t) => next.includes(t)));
  }

  function togglePart(part: Part) {
    setParts((p) => (p.includes(part) ? p.filter((x) => x !== part) : [...p, part]));
  }

  return (
    <div className="space-y-10">
      <section
        aria-labelledby="due-heading"
        className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-line bg-surface p-4 sm:p-5"
      >
        <div className="space-y-1">
          <h2 id="due-heading" className="text-lg">
            {!hydrated ? "Reviews" : due > 0 ? `${due} card${due === 1 ? "" : "s"} due` : "Nothing due"}
          </h2>
          <p className="text-sm text-muted">
            {!hydrated
              ? "Checking what's due…"
              : due > 0
                ? "Cards and problems you've seen before, scheduled for just before you'd forget them."
                : nextDue && now !== null
                  ? `The next review is due in ${formatInterval(nextDue.due - now)}. Study new cards below.`
                  : "Study a deck below. Every card you grade gets scheduled for review."}
          </p>
        </div>
        {hydrated && due > 0 && (
          <Link
            href="/cards/study?mode=due"
            className="flex h-11 items-center rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink transition hover:opacity-90"
          >
            Review {due} now
          </Link>
        )}
      </section>

      <section aria-labelledby="deck-heading" className="space-y-5">
        <h2 id="deck-heading" className="text-xl">
          Study a course
        </h2>
        <div className="space-y-6 rounded-xl border border-line bg-surface p-4 sm:p-6">
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
              <legend className="mb-1.5 text-sm font-medium">Cards</legend>
              <div className="flex flex-col gap-1">
                {(
                  [
                    ["concepts", "Definitions and theorems"],
                    ["problems", "Problems with worked solutions"],
                  ] as const
                ).map(([part, label]) => (
                  <label
                    key={part}
                    className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md px-2 hover:bg-surface-2"
                  >
                    <input
                      type="checkbox"
                      checked={parts.includes(part)}
                      onChange={() => togglePart(part)}
                      className="h-5 w-5 accent-accent"
                    />
                    <span className="text-sm">{label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          </div>

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
                    onChange={() => toggleTopic(t.topic)}
                    className="h-5 w-5 accent-accent"
                  />
                  <span className="flex-1 text-sm">{t.label}</span>
                  <span className="text-xs text-muted">
                    {(parts.includes("concepts") ? t.concepts : 0) +
                      (parts.includes("problems") ? t.problems : 0)}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">
            {count > 0 && topics.length > 0 && parts.length > 0 ? (
              <>
                <Link
                  href={studyHref(course.id, topicParam, parts, "study")}
                  className="flex h-11 items-center rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink transition hover:opacity-90"
                >
                  Study {count} cards
                </Link>
                {conceptCount >= 4 && parts.includes("concepts") ? (
                  <Link
                    href={studyHref(course.id, topicParam, ["concepts"], "quiz")}
                    className="flex h-11 items-center rounded-lg border border-line px-4 text-sm font-medium hover:border-accent"
                  >
                    Quiz me on the terms
                  </Link>
                ) : null}
                <button
                  type="button"
                  onClick={() =>
                    router.push(
                      testHref(
                        {
                          course: course.id,
                          kind: "quiz",
                          topics: topicParam.length ? topicParam : null,
                          length: null,
                          style: "mixed",
                          variants: false,
                          focus: true,
                        },
                        randomSeed(),
                        learn,
                        course.topics.map((t) => t.topic),
                      ),
                    )
                  }
                  className="flex h-11 items-center px-1 text-sm text-accent hover:underline"
                >
                  Quick quiz on the problems
                </button>
              </>
            ) : (
              <p className="text-sm text-muted">Pick at least one chapter and one kind of card.</p>
            )}
          </div>
        </div>
      </section>

      <section aria-labelledby="notes-heading" className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1">
            <h2 id="notes-heading" className="text-xl">
              Your notes
            </h2>
            <p className="text-sm text-muted">
              Paste, upload or photograph notes. ProofLab finds definitions, theorems and formulas
              with written rules, and you check every card before it&apos;s saved.
            </p>
          </div>
          <Link
            href="/cards/notes"
            className="flex h-11 items-center rounded-lg border border-line px-4 text-sm font-medium hover:border-accent"
          >
            Make cards from notes
          </Link>
        </div>
        {hydrated && decks.length > 0 && (
          <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
            {decks.map((d) => {
              const dueHere =
                now === null
                  ? 0
                  : d.cards.filter((c) => (learn.items[noteItemId(d.id, c.id)]?.due ?? Infinity) <= now)
                      .length;
              return (
                <li key={d.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{d.name}</p>
                    <p className="text-xs text-muted">
                      {d.cards.length} cards{dueHere ? ` · ${dueHere} due` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Link
                      href={`/cards/study?deck=${d.id}`}
                      className="flex h-11 items-center rounded-md px-3 text-sm text-accent hover:underline"
                    >
                      Study
                    </Link>
                    {d.cards.length >= 4 && (
                      <Link
                        href={`/cards/study?deck=${d.id}&mode=quiz`}
                        className="flex h-11 items-center rounded-md px-3 text-sm text-accent hover:underline"
                      >
                        Quiz
                      </Link>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(`Delete "${d.name}" and its ${d.cards.length} cards? This removes it on every device.`))
                          deleteDeck(d.id);
                      }}
                      className="flex h-11 items-center rounded-md px-3 text-sm text-muted hover:text-bad"
                    >
                      Delete
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section aria-labelledby="model-heading" className="space-y-3 border-t border-line pt-6 text-sm">
        <h2 id="model-heading" className="text-lg">
          How the schedule learns
        </h2>
        <p className="text-muted">
          Each card has a memory strength. Grading a card (or checking a problem) updates it with the
          FSRS spaced-repetition formulas, and the card comes back when you&apos;d be about 90% likely
          to still know it. On top of that, ProofLab fits one number to all your past reviews: how
          much longer or shorter your memory lasts than the formulas expect.
        </p>
        <p>
          {!hydrated
            ? "Loading your history…"
            : summary.fitted
              ? `Tuned to you from ${summary.reviews} reviews: your memory lasts about ${summary.k.toFixed(2)}× as long as the starting model expects, and its predictions fit your answers ${Math.round(summary.improvement * 100)}% better.`
              : summary.reviews === 0
                ? "No reviews yet. The schedule starts from the standard model."
                : `${summary.reviews} review${summary.reviews === 1 ? "" : "s"} so far. It starts tuning itself after ${summary.needed} more repeat review${summary.needed === 1 ? "" : "s"}.`}
        </p>
        <SyncNote />
        {hydrated && summary.reviews > 0 && (
          <div className="flex flex-wrap items-center gap-3">
            {confirmReset ? (
              <>
                <span>Forget every review and start the schedule over?</span>
                <button
                  type="button"
                  onClick={() => {
                    resetLearning();
                    setConfirmReset(false);
                  }}
                  className="h-11 rounded-lg border border-bad px-3 text-bad"
                >
                  Forget my reviews
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmReset(false)}
                  className="h-11 px-2 text-muted hover:text-ink"
                >
                  Keep them
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmReset(true)}
                className="h-11 px-1 text-muted underline-offset-4 hover:text-ink hover:underline"
              >
                Start the schedule over
              </button>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
