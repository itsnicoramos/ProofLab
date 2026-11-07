"use server";

// Server Actions the workspace calls. They proxy to the backend, which does all the checking.
// Server Actions are reachable by direct POST, so validate shapes here too (the backend also
// validates everything it receives).

import {
  BackendUnavailableError,
  getCourses,
  getDeckCards,
  getProblems,
  getSolution,
  postCheck,
  postChoiceAnswer,
  postNotes,
} from "./api";
import { bookSection, COURSE_ORDER, COURSE_SHORT, kindLabel, topicLabel } from "./labels";
import type {
  CheckInput,
  ChoiceGrade,
  DeckCard,
  NoteCardDraft,
  Solution,
  Verdict,
} from "./types";

export type CheckResult = { ok: true; verdict: Verdict } | { ok: false; error: string };
export type SolutionResult = { ok: true; solution: Solution } | { ok: false; error: string };

const ID_RE = /^[a-z0-9]+\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9-]*$/;
const KIND_RE = /^[a-z_]{1,20}$/;

function isValid(input: CheckInput): boolean {
  return (
    typeof input === "object" &&
    input !== null &&
    typeof input.problemId === "string" &&
    ID_RE.test(input.problemId) &&
    Array.isArray(input.steps) &&
    input.steps.length <= 40 &&
    input.steps.every(
      (s) =>
        typeof s?.kind === "string" &&
        KIND_RE.test(s.kind) &&
        typeof s.content === "string" &&
        s.content.length <= 500,
    ) &&
    (input.answer === null || (typeof input.answer === "string" && input.answer.length <= 500)) &&
    Number.isInteger(input.hintsRevealed) &&
    input.hintsRevealed >= 0 &&
    input.hintsRevealed <= 20
  );
}

function unreachable(error: unknown): string {
  if (error instanceof BackendUnavailableError) {
    return "ProofLab's checker isn't running. Start the backend and try again.";
  }
  return "Something went wrong talking to the checker. Try again.";
}

export async function checkWork(input: CheckInput): Promise<CheckResult> {
  if (!isValid(input)) {
    return { ok: false, error: "That submission is too long or has too many steps (max 40)." };
  }
  try {
    const res = await postCheck(input);
    if (res.ok) return { ok: true, verdict: res.verdict };
    if (res.status === 503) return { ok: false, error: res.detail };
    if (res.status === 404) return { ok: false, error: "This problem no longer exists." };
    if (res.status >= 500) {
      return { ok: false, error: "The checker hit an internal error. Try again in a moment." };
    }
    return { ok: false, error: "The checker couldn't read that submission." };
  } catch (error) {
    return { ok: false, error: unreachable(error) };
  }
}

export type GradeResult = { ok: true; verdicts: Verdict[] } | { ok: false; error: string };

/** Grade a whole practice test in one round trip. Verdicts come back in the input order. */
export async function gradeTest(items: CheckInput[]): Promise<GradeResult> {
  if (!Array.isArray(items) || items.length === 0 || items.length > 30 || !items.every(isValid)) {
    return {
      ok: false,
      error: "That test submission isn't valid (1 to 30 questions, 40 steps each).",
    };
  }
  try {
    const responses = await Promise.all(items.map((item) => postCheck(item)));
    const verdicts: Verdict[] = [];
    for (const res of responses) {
      if (!res.ok) {
        return {
          ok: false,
          error:
            res.status === 503
              ? res.detail
              : "The checker couldn't grade one of the questions. Try submitting again.",
        };
      }
      verdicts.push(res.verdict);
    }
    return { ok: true, verdicts };
  } catch (error) {
    return { ok: false, error: unreachable(error) };
  }
}

export interface ChoiceInput {
  problemId: string;
  seed: number;
  format: "answer" | "spot";
  choice: string;
}

export type ChoiceGradeResult = { ok: true; grades: ChoiceGrade[] } | { ok: false; error: string };

/** Grade multiple-choice answers; the server rebuilds each question to know the right key. */
export async function gradeChoices(items: ChoiceInput[]): Promise<ChoiceGradeResult> {
  const valid =
    Array.isArray(items) &&
    items.length <= 30 &&
    items.every(
      (i) =>
        typeof i?.problemId === "string" &&
        ID_RE.test(i.problemId) &&
        Number.isInteger(i.seed) &&
        (i.format === "answer" || i.format === "spot") &&
        /^[a-e]$/.test(i.choice),
    );
  if (!valid) return { ok: false, error: "Those answers aren't valid." };
  try {
    const grades = await Promise.all(items.map((i) => postChoiceAnswer(i)));
    if (grades.some((g) => g === null)) {
      return { ok: false, error: "The checker couldn't grade one of the questions. Try again." };
    }
    return { ok: true, grades: grades as ChoiceGrade[] };
  } catch (error) {
    return { ok: false, error: unreachable(error) };
  }
}

const TOPIC_RE = /^[a-z0-9][a-z0-9_-]*$/;
const COURSE_RE = /^[a-z0-9]+$/;

export type DeckResult = { ok: true; cards: DeckCard[] } | { ok: false; error: string };

/** A course's flashcards (concepts and/or problems) for the chosen chapters. */
export async function loadDeck(
  course: string,
  topics: string[],
  parts: ("concepts" | "problems")[],
): Promise<DeckResult> {
  if (
    !COURSE_RE.test(course) ||
    !Array.isArray(topics) ||
    !topics.every((t) => TOPIC_RE.test(t)) ||
    !Array.isArray(parts) ||
    parts.length === 0 ||
    !parts.every((p) => p === "concepts" || p === "problems")
  ) {
    return { ok: false, error: "Pick a course and at least one kind of card." };
  }
  try {
    return { ok: true, cards: await getDeckCards(course, topics.join(",") || null, parts.join(",")) };
  } catch (error) {
    return { ok: false, error: unreachable(error) };
  }
}

export type NotesResult = { ok: true; cards: NoteCardDraft[] } | { ok: false; error: string };

/** Find flashcards in the student's notes with ProofLab's written rules (no AI). */
export async function cardsFromNotes(text: string): Promise<NotesResult> {
  if (typeof text !== "string" || !text.trim()) {
    return { ok: false, error: "Paste or scan some notes first." };
  }
  if (text.length > 200_000) return { ok: false, error: "That's too much text (200,000 characters at most)." };
  try {
    const cards = await postNotes(text);
    return cards ? { ok: true, cards } : { ok: false, error: "ProofLab couldn't read those notes." };
  } catch (error) {
    return { ok: false, error: unreachable(error) };
  }
}

export interface SearchEntry {
  type: "topic" | "problem" | "test" | "page";
  label: string;
  detail: string;
  href: string;
  /** Extra lowercase words to match on (course names, chapter numbers, tags). */
  keywords: string;
  /** A topic with no problems yet: findable, but not suggested. */
  soon?: boolean;
}

export type SearchIndexResult = { ok: true; entries: SearchEntry[] } | { ok: false; error: string };

/** Everything the navbar search can find: topics, problems, practice tests and help pages. */
export async function getSearchIndex(): Promise<SearchIndexResult> {
  try {
    const [courses, problems] = await Promise.all([getCourses(), getProblems()]);
    const order = (id: string) => COURSE_ORDER.indexOf(id as (typeof COURSE_ORDER)[number]);
    const sorted = [...courses].sort((a, b) => order(a.id) - order(b.id));
    const entries: SearchEntry[] = [];
    const chapterWords = (label: string) => {
      const n = /^Chapter (\d+)/.exec(label)?.[1];
      return n ? ` chapter ${n} ch ${n} ch${n}` : "";
    };

    for (const course of sorted) {
      const name = COURSE_SHORT[course.id];
      for (const t of course.topics) {
        const label = topicLabel(t.topic, course.id);
        const has = t.problems > 0;
        entries.push({
          type: "topic",
          label,
          detail: has ? `${name} · ${t.problems} problems` : `${name} · not in ProofLab yet`,
          href: has ? `/courses/${course.id}#${t.topic}` : `/courses/${course.id}#later-heading`,
          keywords: `${course.id} ${name} ${t.topic}${chapterWords(label)}`.toLowerCase(),
          ...(has ? {} : { soon: true }),
        });
      }
      if (course.problems > 0) {
        for (const kind of ["midterm", "final", "quiz"] as const) {
          const quiz = kind === "quiz";
          entries.push({
            type: "test",
            label: quiz ? "Quick quiz" : `Practice ${kind}`,
            detail: quiz ? `${name} · multiple choice` : name,
            href: quiz ? `/tests/${course.id}/quiz?style=choice` : `/tests/${course.id}/${kind}`,
            keywords: `${course.id} ${name} test exam practice ${kind}${quiz ? " multiple choice mcq" : ""}`.toLowerCase(),
          });
        }
      }
    }

    for (const p of problems) {
      const topic = topicLabel(p.topic, p.course);
      const section = bookSection(p.title);
      entries.push({
        type: "problem",
        label: p.title,
        detail: `${COURSE_SHORT[p.course]} · ${section ? `${topic} · ${section}` : topic}`,
        href: `/problems/${p.id}`,
        keywords:
          `${p.course} ${COURSE_SHORT[p.course]} ${topic} ${kindLabel(p.kind)} ${p.tags.join(" ")}${chapterWords(topic)}${section ? ` section ${section}` : ""}`.toLowerCase(),
      });
    }

    entries.push(
      {
        type: "page",
        label: "Practice tests",
        detail: "Build a midterm, final or quick quiz",
        href: "/tests",
        keywords: "tests exams midterm final practice builder",
      },
      {
        type: "page",
        label: "Flashcards",
        detail: "Study cards that schedule themselves",
        href: "/cards",
        keywords: "flashcards cards review study spaced repetition memorize definitions notes",
      },
      {
        type: "page",
        label: "Make cards from your notes",
        detail: "Paste, scan or upload notes",
        href: "/cards/notes",
        keywords: "notes import flashcards scan pdf photo document upload",
      },
      {
        type: "page",
        label: "Typing math",
        detail: "How to enter steps and answers",
        href: "/help",
        keywords: "help syntax typing input notation guide",
      },
    );
    return { ok: true, entries };
  } catch (error) {
    return { ok: false, error: unreachable(error) };
  }
}

export async function revealSolution(problemId: string): Promise<SolutionResult> {
  if (typeof problemId !== "string" || !ID_RE.test(problemId)) {
    return { ok: false, error: "Unknown problem." };
  }
  try {
    const solution = await getSolution(problemId);
    return solution ? { ok: true, solution } : { ok: false, error: "No solution found." };
  } catch (error) {
    return { ok: false, error: unreachable(error) };
  }
}
