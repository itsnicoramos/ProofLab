// Server-side client for the ProofLab backend. Only import this from Server Components and
// Server Actions: the backend URL stays on the server, so the browser never needs CORS.
import { cache } from "react";

import { isCourseId } from "./labels";
import type {
  CheckInput,
  ChoiceGrade,
  CourseSummary,
  DeckCard,
  NoteCardDraft,
  PracticeTest,
  ProblemDetail,
  ProblemSummary,
  Solution,
  Verdict,
} from "./types";

export const BACKEND_URL = (process.env.PROOFLAB_API_URL ?? "http://localhost:8000").replace(
  /\/+$/,
  "",
);

export class BackendUnavailableError extends Error {
  constructor() {
    super(`Can't reach the ProofLab backend at ${BACKEND_URL}.`);
    this.name = "BackendUnavailableError";
  }
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${BACKEND_URL}${path}`, {
      ...init,
      headers: {
        accept: "application/json",
        ...(init?.body ? { "content-type": "application/json" } : {}),
      },
    });
  } catch {
    throw new BackendUnavailableError();
  }
}

async function getJson<T>(path: string): Promise<T | null> {
  const res = await request(path);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`ProofLab backend returned ${res.status} for ${path}`);
  return (await res.json()) as T;
}

// Only the courses the site shows (COURSE_ORDER in lib/labels.ts) get past these three, so a
// hidden course never appears in a list and its pages answer 404.

export const getCourses = cache(async (): Promise<CourseSummary[]> => {
  const courses = (await getJson<CourseSummary[]>("/courses")) ?? [];
  return courses.filter((c) => isCourseId(c.id));
});

export const getProblems = cache(
  async (course?: string, topic?: string): Promise<ProblemSummary[]> => {
    const params = new URLSearchParams();
    if (course) params.set("course", course);
    if (topic) params.set("topic", topic);
    const query = params.size ? `?${params}` : "";
    const problems = (await getJson<ProblemSummary[]>(`/problems${query}`)) ?? [];
    return problems.filter((p) => isCourseId(p.course));
  },
);

export const getProblem = cache(async (id: string): Promise<ProblemDetail | null> => {
  const problem = await getJson<ProblemDetail>(`/problems/${encodeURIComponent(id)}`);
  return problem && isCourseId(problem.course) ? problem : null;
});

export interface TestOptions {
  topics: string | null;
  length: number | null;
  style?: string | null;
  variants?: boolean;
  weights?: string | null;
  prefer?: string | null;
}

/** A practice test, or null when the course/topics can't produce one (404/422). */
export const getPracticeTest = cache(
  async (
    course: string,
    kind: string,
    seed: number,
    options: TestOptions,
  ): Promise<PracticeTest | null> => {
    const params = new URLSearchParams({ course, kind, seed: String(seed) });
    if (options.topics) params.set("topics", options.topics);
    if (options.length !== null) params.set("length", String(options.length));
    if (options.style) params.set("style", options.style);
    if (options.variants) params.set("variants", "true");
    if (options.weights) params.set("weights", options.weights);
    if (options.prefer) params.set("prefer", options.prefer);
    const res = await request(`/practice-tests?${params}`);
    if (res.status === 404 || res.status === 422) return null;
    if (!res.ok) throw new Error(`ProofLab backend returned ${res.status} for /practice-tests`);
    return (await res.json()) as PracticeTest;
  },
);

export async function getDeckCards(
  course: string,
  topics: string | null,
  parts: string,
): Promise<DeckCard[]> {
  const params = new URLSearchParams({ course, parts });
  if (topics) params.set("topics", topics);
  return (await getJson<DeckCard[]>(`/cards?${params}`)) ?? [];
}

export async function postChoiceAnswer(input: {
  problemId: string;
  seed: number;
  format: string;
  choice: string;
}): Promise<ChoiceGrade | null> {
  const res = await request("/quiz/answer", {
    method: "POST",
    body: JSON.stringify({
      problem_id: input.problemId,
      seed: input.seed,
      format: input.format,
      choice: input.choice,
    }),
  });
  if (!res.ok) return null;
  return (await res.json()) as ChoiceGrade;
}

export async function postNotes(text: string): Promise<NoteCardDraft[] | null> {
  const res = await request("/cards/from-notes", { method: "POST", body: JSON.stringify({ text }) });
  if (!res.ok) return null;
  return ((await res.json()) as { cards: NoteCardDraft[] }).cards;
}

export async function getSolution(id: string): Promise<Solution | null> {
  return getJson<Solution>(`/problems/${encodeURIComponent(id)}/solution`);
}

export type CheckResponse =
  | { ok: true; verdict: Verdict }
  | { ok: false; status: number; detail: string };

export async function postCheck(input: CheckInput): Promise<CheckResponse> {
  const res = await request("/check", {
    method: "POST",
    body: JSON.stringify({
      problem_id: input.problemId,
      steps: input.steps,
      answer: input.answer,
      hints_revealed: input.hintsRevealed,
    }),
  });
  if (res.ok) return { ok: true, verdict: (await res.json()) as Verdict };
  let detail = `The checker returned ${res.status}.`;
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    // keep the generic message
  }
  return { ok: false, status: res.status, detail };
}
