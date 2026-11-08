"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  type ReactNode,
  type RefObject,
  useEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
} from "react";

import { DifficultyDots, StatusIcon } from "@/components/Badges";
import { ChoiceView } from "@/components/ChoiceView";
import { Workspace, type WorkspaceProblem } from "@/components/Workspace";
import { partsText, XpNote } from "@/components/XpNote";
import { gradeChoices, gradeTest } from "@/lib/actions";
import { gradeFromVerdict, recordProblem, useLearn } from "@/lib/learn";
import { firstStepKind, usesAnswer, VERDICT_LABEL } from "@/lib/labels";
import {
  clearAttempt,
  ensureTestStarted,
  type ExamResult,
  getAttempt,
  parseTestRecord,
  recordProgress,
  saveTestRecord,
  testDraftKey,
  updateAttempt,
  useAttempt,
  useClock,
  useTestRecordRaw,
  useTypedFlags,
} from "@/lib/storage";
import { randomSeed, testHref, type TestSettings } from "@/lib/testUrl";
import { recordTest, useXp } from "@/lib/xp";
import type { ChoiceQuestion, Verdict, VerdictStatus } from "@/lib/types";

export interface TestQuestion {
  id: string;
  title: string;
  /** Display label, e.g. "Chapter 4: Direct proof". */
  topic: string;
  topicId: string;
  course: string;
  kind: string;
  difficulty: number;
  /** The book problem a ProofLab-made version is based on. */
  variantOf: string | null;
  format: "written" | "choice";
  choice: ChoiceQuestion | null;
  problem: WorkspaceProblem;
  /** The statement, already rendered on the server. */
  prompt: ReactNode;
}

interface TestRunnerProps {
  testId: string;
  title: string;
  href: string;
  suggestedMinutes: number;
  settings: TestSettings;
  allTopics: string[];
  questions: TestQuestion[];
}

const isChoice = (q: TestQuestion): q is TestQuestion & { choice: ChoiceQuestion } =>
  q.format === "choice" && q.choice !== null;

function choiceVerdict(problemId: string, correct: boolean, picked: string): Verdict {
  return {
    problem_id: problemId,
    status: correct ? "correct" : "incorrect",
    score: correct ? 1 : 0,
    steps: [],
    answer: picked ? { status: correct ? "correct" : "incorrect", message: "", latex: null, code: null } : null,
    hints: [],
  };
}

function formatMinutes(ms: number): string {
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 1) return "under a minute";
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

const isBlankResult = (r: ExamResult | undefined) =>
  !r || (r.steps.length === 0 && r.answer === "");

/** A quiet dash for a question left blank, so it doesn't look like a wrong answer. */
function BlankMark() {
  return (
    <span
      aria-hidden
      className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-idle-soft text-xs font-bold text-idle"
    >
      –
    </span>
  );
}

const formatPoints = (points: number) =>
  Number.isInteger(points) ? String(points) : points.toFixed(1);

export function TestRunner({
  testId,
  title,
  href,
  suggestedMinutes,
  settings,
  allTopics,
  questions,
}: TestRunnerProps) {
  const router = useRouter();
  const learn = useLearn();
  const record = parseTestRecord(useTestRecordRaw(testId));
  const graded = record?.submittedAt && record.results ? record : null;
  const drafts = useMemo(
    () =>
      questions.map((q) => ({
        key: testDraftKey(testId, q.id),
        firstKind: firstStepKind(q.problem.kind, q.problem.step_kinds),
      })),
    [questions, testId],
  );
  const typed = useTypedFlags(drafts);
  const now = useClock();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [confirmingBlank, setConfirmingBlank] = useState(false);
  const resultsHeading = useRef<HTMLHeadingElement>(null);
  const focusResults = useRef(false);

  const meta = useMemo(
    () => ({ title, href, questions: questions.length }),
    [title, href, questions.length],
  );

  useEffect(() => {
    ensureTestStarted(testId, meta);
  }, [testId, meta]);

  useEffect(() => {
    if (graded && focusResults.current) {
      focusResults.current = false;
      resultsHeading.current?.focus();
    }
  });

  const answered = typed === null ? null : [...typed].filter((c) => c === "1").length;
  const blanks = answered === null ? 0 : questions.length - answered;
  const end = graded?.submittedAt ?? now;
  const elapsed = record && end !== null ? Math.max(0, end - record.startedAt) : null;

  // ------------------------------------------------------------- actions

  function submit() {
    if (blanks > 0 && !confirmingBlank) {
      setConfirmingBlank(true);
      return;
    }
    setConfirmingBlank(false);
    const submitted = questions.map((q, i) => {
      const attempt = getAttempt(drafts[i].key, drafts[i].firstKind);
      if (isChoice(q)) return { steps: [], answer: attempt.answer.trim() };
      return {
        steps: attempt.steps.filter((s) => s.content.trim() !== ""),
        answer: usesAnswer(q.problem.kind) ? attempt.answer.trim() : "",
      };
    });
    const written = questions.flatMap((q, i) => (isChoice(q) ? [] : [i]));
    // Blank choice questions are graded too (as a wrong pick), so the results can still show
    // the right choice, its explanation and the worked solution.
    const picked = questions.flatMap((q, i) => (isChoice(q) ? [i] : []));
    startTransition(async () => {
      const [checks, choices] = await Promise.all([
        written.length
          ? gradeTest(
              written.map((i) => ({
                problemId: questions[i].id,
                steps: submitted[i].steps.map(({ kind: k, content }) => ({ kind: k, content })),
                answer: submitted[i].answer || null,
                hintsRevealed: 0,
              })),
            )
          : Promise.resolve({ ok: true as const, verdicts: [] }),
        picked.length
          ? gradeChoices(
              picked.map((i) => {
                const q = questions[i] as TestQuestion & { choice: ChoiceQuestion };
                return {
                  problemId: q.id,
                  seed: q.choice.seed,
                  format: q.choice.format,
                  choice: submitted[i].answer || "a",
                };
              }),
            )
          : Promise.resolve({ ok: true as const, grades: [] }),
      ]);
      if (!checks.ok || !choices.ok) {
        setError(!checks.ok ? checks.error : !choices.ok ? choices.error : null);
        return;
      }
      setError(null);
      const results: Record<string, ExamResult> = {};
      let score = 0;
      written.forEach((qi, j) => {
        const verdict = checks.verdicts[j];
        results[questions[qi].id] = { verdict, ...submitted[qi] };
      });
      questions.forEach((q, qi) => {
        if (!isChoice(q)) return;
        const j = picked.indexOf(qi);
        const g = j >= 0 ? choices.grades[j] : null;
        const blank = !submitted[qi].answer;
        results[q.id] = {
          verdict: choiceVerdict(q.id, !blank && !!g?.correct, submitted[qi].answer),
          steps: [],
          answer: submitted[qi].answer,
          choice: {
            picked: submitted[qi].answer,
            correct: g?.correct_choice ?? "",
            explanation: blank ? null : (g?.explanation ?? null),
            solution: g?.solution ?? [],
          },
        };
      });
      for (const q of questions) {
        const r = results[q.id];
        if (!r) continue;
        score += r.verdict.score;
        // Practice progress marks are for book problems; ProofLab-made versions feed only the
        // study model, under the problem they're based on.
        if (!q.variantOf) recordProgress(q.id, r.verdict.status);
        const grade = isBlankResult(r) ? 1 : gradeFromVerdict(r.verdict.status);
        if (grade) {
          recordProblem(
            { id: q.variantOf ?? q.id, course: q.course, topic: q.topicId, difficulty: q.difficulty },
            grade,
          );
        }
      }
      // XP (SPEC §19): the facts of this submission; the XP is worked out from them.
      recordTest(testId, settings.course, {
        kind: settings.kind,
        questions: questions.map((q) => ({
          item: q.variantOf ? null : q.id,
          difficulty: q.difficulty,
          format: isChoice(q) ? "choice" : "written",
          status: results[q.id]?.verdict.status ?? "incorrect",
          blank: isBlankResult(results[q.id]),
        })),
      });
      focusResults.current = true;
      saveTestRecord(testId, {
        ...meta,
        startedAt: record?.startedAt ?? Date.now(),
        submittedAt: Date.now(),
        score,
        results,
      });
      window.scrollTo({ top: 0 });
    });
  }

  function retake() {
    for (const d of drafts) clearAttempt(d.key);
    saveTestRecord(testId, null);
    ensureTestStarted(testId, meta);
    setError(null);
    window.scrollTo({ top: 0 });
  }

  function newTest() {
    // With "focus", the weights come from the results just recorded, so the next test adapts.
    router.push(testHref(settings, randomSeed(), learn, allTopics));
  }

  // ------------------------------------------------------------- view

  return (
    <div className="space-y-8">
      {graded ? (
        <Results
          testId={testId}
          questions={questions}
          results={graded.results ?? {}}
          score={graded.score ?? 0}
          elapsed={elapsed}
          suggestedMinutes={suggestedMinutes}
          headingRef={resultsHeading}
          onRetake={retake}
          onNewTest={newTest}
        />
      ) : (
        <>
          <nav aria-label="Questions" className="flex flex-wrap gap-2">
            {questions.map((q, i) => {
              const done = typed?.[i] === "1";
              return (
                <a
                  key={q.id}
                  href={`#q-${i + 1}`}
                  className={`flex h-11 w-11 items-center justify-center rounded-md border font-mono text-sm transition-colors hover:border-accent ${
                    done ? "border-ink bg-ink text-bg" : "border-line bg-surface text-muted"
                  }`}
                >
                  {i + 1}
                  <span className="sr-only">{done ? ", answered" : ", blank"}</span>
                </a>
              );
            })}
          </nav>

          <div className="sticky top-14 z-20 -mx-4 flex items-center justify-between gap-3 border-b border-line bg-bg px-4 py-2 sm:mx-0 sm:rounded-lg sm:border sm:px-4">
            <p className="text-sm text-muted" aria-live="off">
              {answered === null ? (
                `${questions.length} questions`
              ) : (
                <>
                  <span className="font-medium text-ink">{answered}</span> of {questions.length}{" "}
                  answered
                </>
              )}
              {elapsed !== null && <> · {formatMinutes(elapsed)} so far</>}
              <span className="hidden sm:inline"> · aim for {suggestedMinutes} min</span>
            </p>
            <a
              href="#submit-test"
              className="flex h-11 shrink-0 items-center rounded-lg border border-line px-3 text-sm font-medium hover:border-accent"
            >
              Finish
            </a>
          </div>
        </>
      )}

      <ol className="space-y-12">
        {questions.map((q, i) => {
          const result = graded?.results?.[q.id] ?? null;
          return (
            <li key={q.id}>
              <section
                id={`q-${i + 1}`}
                aria-labelledby={`q-${i + 1}-title`}
                className="scroll-mt-32 space-y-4"
              >
                <div className="flex items-center justify-between gap-3 border-t border-line pt-6">
                  <p className="text-sm text-muted">
                    Question {i + 1} of {questions.length}
                  </p>
                  {result && (
                    <span className="flex items-center gap-2 text-sm">
                      {isBlankResult(result) ? (
                        <BlankMark />
                      ) : (
                        <StatusIcon status={result.verdict.status} />
                      )}
                      {formatPoints(result.verdict.score)} / 1
                    </span>
                  )}
                </div>
                <h2 id={`q-${i + 1}-title`} className="text-xl sm:text-2xl">
                  {q.title}
                </h2>
                <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
                  <span>{q.topic}</span>
                  <span>{q.kind}</span>
                  <DifficultyDots level={q.difficulty} />
                  {q.variantOf && (
                    <span className="rounded border border-line px-1.5 py-0.5 text-xs">
                      Made by ProofLab, not from the book
                    </span>
                  )}
                  {isChoice(q) && <span>Multiple choice</span>}
                </p>
                {q.prompt}
                {isChoice(q) ? (
                  <ChoiceAnswer
                    question={q.choice}
                    draftKey={drafts[i].key}
                    firstKind={drafts[i].firstKind}
                    result={result}
                    label={`Question ${i + 1}`}
                  />
                ) : (
                  <Workspace
                    problem={q.problem}
                    draftKey={drafts[i].key}
                    mode="exam"
                    result={result}
                    label={`Your work for question ${i + 1}`}
                  />
                )}
                {result && (
                  <Link
                    href={`/problems/${q.id}`}
                    className="inline-flex h-11 items-center text-sm text-accent hover:underline"
                  >
                    Practise this problem with hints
                  </Link>
                )}
              </section>
            </li>
          );
        })}
      </ol>

      {!graded && (
        <div id="submit-test" className="scroll-mt-32 space-y-3 border-t border-line pt-6">
          <div aria-live="polite" className="space-y-3">
            {error && (
              <p className="rounded-lg border border-bad/40 bg-bad-soft px-4 py-3 text-sm text-bad">
                {error}
              </p>
            )}
            {confirmingBlank && (
              <p className="text-sm">
                {blanks === 1 ? "1 question is" : `${blanks} questions are`} blank and will score 0.
                Submit anyway?
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={submit}
              disabled={pending || answered === null}
              className="h-11 rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {pending ? "Grading…" : confirmingBlank ? "Submit anyway" : "Submit test"}
            </button>
            {confirmingBlank && !pending && (
              <button
                type="button"
                onClick={() => setConfirmingBlank(false)}
                className="h-11 px-2 text-sm text-muted hover:text-ink"
              >
                Keep working
              </button>
            )}
            <span className="text-xs text-muted">
              Every question is checked by the same rules as practice mode, and your results
              tune what ProofLab asks you next.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/** A multiple-choice answer, saved as the draft's answer so it survives a reload. */
function ChoiceAnswer({
  question,
  draftKey,
  firstKind,
  result,
  label,
}: {
  question: ChoiceQuestion;
  draftKey: string;
  firstKind: string;
  result: ExamResult | null;
  label: string;
}) {
  const attempt = useAttempt(draftKey, firstKind);
  const picked = result ? (result.choice?.picked ?? "") : attempt.answer;
  return (
    <ChoiceView
      question={question}
      label={label}
      picked={picked || null}
      onPick={
        result ? undefined : (key) => updateAttempt(draftKey, firstKind, (a) => ({ ...a, answer: key }))
      }
      graded={
        result?.choice
          ? {
              correct: result.choice.correct,
              explanation: result.choice.explanation,
              solution: result.choice.solution,
            }
          : null
      }
    />
  );
}

// ---------------------------------------------------------------- results

const STATUS_ORDER: VerdictStatus[] = ["correct", "partial", "incorrect", "invalid"];

function Results({
  testId,
  questions,
  results,
  score,
  elapsed,
  suggestedMinutes,
  headingRef,
  onRetake,
  onNewTest,
}: {
  testId: string;
  questions: TestQuestion[];
  results: Record<string, ExamResult>;
  score: number;
  elapsed: number | null;
  suggestedMinutes: number;
  headingRef: RefObject<HTMLHeadingElement | null>;
  onRetake: () => void;
  onNewTest: () => void;
}) {
  const total = questions.length;
  const percent = total ? Math.round((score / total) * 100) : 0;
  const xpTest = useXp().summary.tests[testId] ?? null;
  const isBlank = isBlankResult;
  const blank = questions.filter((q) => isBlank(results[q.id])).length;
  const counts = STATUS_ORDER.map((status) => ({
    status,
    n: questions.filter((q) => !isBlank(results[q.id]) && results[q.id]?.verdict.status === status)
      .length,
  })).filter((c) => c.n > 0);

  const chapters: { topic: string; points: number; questions: number }[] = [];
  for (const q of questions) {
    let row = chapters.find((c) => c.topic === q.topic);
    if (!row) {
      row = { topic: q.topic, points: 0, questions: 0 };
      chapters.push(row);
    }
    row.points += results[q.id]?.verdict.score ?? 0;
    row.questions += 1;
  }

  return (
    <section
      aria-labelledby="results-heading"
      className="space-y-6 rounded-xl border border-line bg-surface p-5 sm:p-6"
    >
      <div className="space-y-2">
        <h2 id="results-heading" ref={headingRef} tabIndex={-1} className="text-lg outline-none">
          Your result
        </h2>
        <p className="font-serif text-4xl">
          {formatPoints(score)} <span className="text-2xl text-muted">/ {total}</span>
          <span className="sr-only"> points, </span>
          <span className="ml-3 text-2xl">{percent}%</span>
        </p>
        <p className="text-sm text-muted">
          {[
            ...counts.map((c) => `${c.n} ${VERDICT_LABEL[c.status].toLowerCase()}`),
            ...(blank ? [`${blank} blank`] : []),
          ].join(" · ")}
        </p>
        {elapsed !== null && (
          <p className="text-sm text-muted">
            Took {formatMinutes(elapsed)}, against about {suggestedMinutes} min suggested.
          </p>
        )}
        {xpTest && (
          <div className="pt-1">
            <XpNote uids={[xpTest.latest.uid]} breakdown={false} />
            {xpTest.latest.xp > 0 && xpTest.latest.parts.length > 0 && (
              <p className="text-sm text-muted">{partsText(xpTest.latest.parts)}</p>
            )}
          </div>
        )}
      </div>

      {chapters.length > 1 && (
        <table className="w-full text-sm">
          <caption className="mb-2 text-left font-medium">By chapter</caption>
          <thead className="sr-only">
            <tr>
              <th scope="col">Chapter</th>
              <th scope="col">Points</th>
            </tr>
          </thead>
          <tbody>
            {chapters.map((c) => (
              <tr key={c.topic} className="border-t border-line">
                <th scope="row" className="py-2 text-left font-normal">
                  {c.topic}
                </th>
                <td className="py-2 text-right font-mono">
                  {formatPoints(c.points)} / {c.questions}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <ol className="grid grid-cols-1 gap-1 text-sm sm:grid-cols-2">
        {questions.map((q, i) => {
          const r = results[q.id];
          return (
            <li key={q.id}>
              <a
                href={`#q-${i + 1}`}
                className="flex min-h-11 items-center gap-2 rounded-md px-2 hover:bg-surface-2"
              >
                {isBlank(r) ? <BlankMark /> : r ? <StatusIcon status={r.verdict.status} /> : null}
                <span className="font-mono text-muted">{i + 1}.</span>
                <span className="min-w-0 flex-1 truncate">{q.title}</span>
                <span className="sr-only">
                  {isBlank(r) ? "left blank" : r ? VERDICT_LABEL[r.verdict.status] : ""}
                </span>
              </a>
            </li>
          );
        })}
      </ol>

      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
        <button
          type="button"
          onClick={onNewTest}
          className="h-11 rounded-lg bg-accent px-4 text-sm font-semibold text-accent-ink transition hover:opacity-90"
        >
          New test, same settings
        </button>
        <button
          type="button"
          onClick={onRetake}
          className="h-11 rounded-lg border border-line px-4 text-sm font-medium hover:border-accent"
        >
          Retake these questions
        </button>
        <Link
          href="/tests"
          className="flex h-11 items-center px-1 text-sm text-muted hover:text-ink"
        >
          Build a different test
        </Link>
        {xpTest && xpTest.best > 0 && (
          <p className="w-full text-xs text-muted">
            A retake pays only the XP above your best on this test ({xpTest.best} XP). A new
            test pays in full.
          </p>
        )}
      </div>
    </section>
  );
}
