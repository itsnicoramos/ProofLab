"use client";

import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useTransition,
  type KeyboardEvent,
} from "react";

import { StatusIcon } from "@/components/Badges";
import { Rich, Tex } from "@/components/Rich";
import { ScanDialog, type ScanApply } from "@/components/ScanDialog";
import { XpNote } from "@/components/XpNote";
import { checkWork, revealSolution } from "@/lib/actions";
import { gradeFromVerdict, recordProblem } from "@/lib/learn";
import { linesToSteps } from "@/lib/scan";
import {
  firstStepKind,
  STEP_STATUS_LABEL,
  stepKindLabel,
  stepPlaceholder,
  usesAnswer,
  VERDICT_LABEL,
} from "@/lib/labels";
import {
  type DraftStep,
  type ExamResult,
  newStepId,
  recordProgress,
  resetAttempt,
  updateAttempt,
  useAttempt,
} from "@/lib/storage";
import { recordReveal, recordSolve, useXpToday } from "@/lib/xp";
import type { ProblemDetail, Solution, StepResult, StepStatus, Verdict } from "@/lib/types";

export type WorkspaceProblem = Pick<
  ProblemDetail,
  "id" | "kind" | "step_kinds" | "answer_format" | "hint_count"
> &
  Partial<Pick<ProblemDetail, "course" | "topic" | "difficulty" | "variant_of">>;

interface CheckedStep {
  content: string;
  kind: string;
  result: StepResult;
}

interface Checked {
  verdict: Verdict;
  steps: Map<string, CheckedStep>;
  answer: string;
}

const STEP_STYLE: Record<StepStatus, { chip: string; ring: string; icon: string }> = {
  ok: { chip: "bg-ok-soft text-ok", ring: "border-ok/40", icon: "✓" },
  warning: {
    chip: "bg-warn-soft text-warn",
    ring: "border-warn/50",
    icon: "!",
  },
  error: { chip: "bg-bad-soft text-bad", ring: "border-bad/60", icon: "✗" },
  unchecked: { chip: "bg-idle-soft text-idle", ring: "border-line", icon: "·" },
};

const BANNER_STYLE = {
  correct: "border-ok/40 bg-ok-soft",
  partial: "border-warn/40 bg-warn-soft",
  incorrect: "border-bad/40 bg-bad-soft",
  invalid: "border-line bg-idle-soft",
} as const;

function toChecked(result: ExamResult): Checked {
  const steps = new Map<string, CheckedStep>();
  for (const r of result.verdict.steps) {
    const step = result.steps[r.index];
    if (step) steps.set(step.id, { content: step.content, kind: step.kind, result: r });
  }
  return { verdict: result.verdict, steps, answer: result.answer };
}

interface WorkspaceProps {
  problem: WorkspaceProblem;
  /** Where the draft is saved; defaults to the problem id. Tests use their own keys. */
  draftKey?: string;
  /** "exam": no checking, hints or solution until the whole test is submitted. */
  mode?: "practice" | "exam";
  /** Exam mode after submitting: what was graded. Shows the results and locks the inputs. */
  result?: ExamResult | null;
  label?: string;
}

export function Workspace({
  problem,
  draftKey = problem.id,
  mode = "practice",
  result = null,
  label = "Your work",
}: WorkspaceProps) {
  const exam = mode === "exam";
  const scheduled = useRef(false);
  // XP (SPEC §19): checks on this visit, and the solve recorded when one first said Correct.
  const checks = useRef(0);
  const solved = useRef<string | null>(null);
  // The XP note shows under the check that earned it; a later check on this visit clears it.
  const [solveUid, setSolveUid] = useState<string | null>(null);
  // Solved already today (this visit, an earlier one, or Start over): more solves pay nothing
  // today, so the XP wording changes. Read from the activity log, the source of truth.
  const xpItem = problem.variant_of ?? problem.id;
  const xp = useXpToday();
  const solvedToday =
    !exam &&
    xp.today !== null &&
    xp.activity.some((e) => e.type === "solve" && e.item === xpItem && e.day === xp.today);
  // Start over bumps this, so a check still in flight from before is dropped when it lands.
  const attemptEpoch = useRef(0);
  const locked = exam && result !== null;
  const firstKind = firstStepKind(problem.kind, problem.step_kinds);
  const newKind = problem.step_kinds.includes("expr") ? "expr" : firstKind;
  const draft = useAttempt(draftKey, firstKind);
  const graded = useMemo(() => (result ? toChecked(result) : null), [result]);
  const attempt = useMemo(
    () =>
      locked && result
        ? {
            ...draft,
            steps: result.steps.length
              ? result.steps
              : [{ id: "none", kind: firstKind, content: "" }],
            answer: result.answer,
          }
        : draft,
    [locked, result, draft, firstKind],
  );
  const [practiceChecked, setChecked] = useState<Checked | null>(null);
  const checked = exam ? graded : practiceChecked;
  const answerId = useId();
  const [error, setError] = useState<string | null>(null);
  const [solution, setSolution] = useState<Solution | null>(null);
  const [confirmingSolution, setConfirmingSolution] = useState(false);
  const [pending, startTransition] = useTransition();
  const inputs = useRef(new Map<string, HTMLInputElement>());
  const focusNext = useRef<string | null>(null);

  const hasAnswer = usesAnswer(problem.kind);
  const pickKind = problem.step_kinds.length > 1;
  const edit = (change: Parameters<typeof updateAttempt>[2]) => {
    if (!locked) updateAttempt(draftKey, firstKind, change);
  };

  useEffect(() => {
    const id = focusNext.current;
    if (id) {
      inputs.current.get(id)?.focus();
      focusNext.current = null;
    }
  });

  // ------------------------------------------------------------- editing

  function setStep(id: string, patch: Partial<DraftStep>) {
    edit((a) => ({
      ...a,
      steps: a.steps.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    }));
  }

  function insertAfter(id: string) {
    const step: DraftStep = { id: newStepId(), kind: newKind, content: "" };
    focusNext.current = step.id;
    edit((a) => {
      const steps = [...a.steps];
      steps.splice(steps.findIndex((s) => s.id === id) + 1, 0, step);
      return { ...a, steps };
    });
  }

  function removeStep(id: string) {
    edit((a) => {
      if (a.steps.length === 1) return { ...a, steps: [{ ...a.steps[0], content: "" }] };
      const index = a.steps.findIndex((s) => s.id === id);
      const steps = a.steps.filter((s) => s.id !== id);
      focusNext.current = steps[Math.max(0, index - 1)].id;
      return { ...a, steps };
    });
  }

  function onStepKey(event: KeyboardEvent<HTMLInputElement>, step: DraftStep) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      return; // handled by the section-wide shortcut below
    } else if (event.key === "Enter") {
      event.preventDefault();
      insertAfter(step.id);
    } else if (event.key === "Backspace" && step.content === "" && attempt.steps.length > 1) {
      event.preventDefault();
      removeStep(step.id);
    }
  }

  function applyScan({ lines, asAnswer }: ScanApply) {
    const stepLines = asAnswer ? lines.slice(0, -1) : lines;
    const answer = asAnswer
      ? lines[lines.length - 1].replace(/^(final\s+)?answer\s*[:=]?\s*/i, "")
      : null;
    const scanned = linesToSteps(stepLines, problem.step_kinds, newKind, problem.kind).map(
      (step) => ({
        ...step,
        id: newStepId(),
      }),
    );
    edit((a) => {
      const blank = a.steps.every((st) => st.content.trim() === "");
      const steps = scanned.length === 0 ? a.steps : blank ? scanned : [...a.steps, ...scanned];
      return { ...a, steps: steps.slice(0, 40), answer: answer ?? a.answer };
    });
  }

  function startOver() {
    resetAttempt(draftKey, firstKind);
    setChecked(null);
    setError(null);
    checks.current = 0;
    solved.current = null;
    setSolveUid(null);
    attemptEpoch.current += 1;
  }

  /** "Try again": put the cursor on the first step marked wrong (or the answer). */
  function tryAgain() {
    const wrong = attempt.steps.find((s) => resultFor(s)?.status === "error");
    // The answer box needs work unless it was checked correct (an empty one has no result).
    const answerNeedsWork = hasAnswer && answerResult?.status !== "correct";
    const target =
      (wrong && inputs.current.get(wrong.id)) ||
      (answerNeedsWork && document.getElementById(answerId)) ||
      inputs.current.get(attempt.steps[attempt.steps.length - 1].id);
    if (target instanceof HTMLInputElement) {
      target.focus();
      if (target.value) target.select();
    }
  }

  // ------------------------------------------------------------- checking

  function submit(options: { anotherHint?: boolean } = {}) {
    if (exam) return; // tests are graded all at once by the test page
    const submitted = attempt.steps.filter((s) => s.content.trim() !== "");
    const answer = hasAnswer ? attempt.answer.trim() : "";
    const seen = attempt.hints.length;
    // Normal checks re-request the latest hint already shown; "another hint" asks for the next.
    const hintsRevealed = options.anotherHint ? seen : Math.max(seen - 1, 0);
    const epoch = attemptEpoch.current;
    startTransition(async () => {
      const res = await checkWork({
        problemId: problem.id,
        steps: submitted.map(({ kind, content }) => ({ kind, content })),
        answer: answer || null,
        hintsRevealed,
      });
      if (epoch !== attemptEpoch.current) return; // "Start over" was pressed while it ran
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setError(null);
      const steps = new Map<string, CheckedStep>();
      for (const result of res.verdict.steps) {
        const step = submitted[result.index];
        if (step)
          steps.set(step.id, {
            content: step.content,
            kind: step.kind,
            result,
          });
      }
      setChecked({ verdict: res.verdict, steps, answer });
      const authored = res.verdict.hints.find((h) => h.code === "AUTHORED_HINT");
      if (authored) {
        edit((a) =>
          a.hints.includes(authored.message) ? a : { ...a, hints: [...a.hints, authored.message] },
        );
      }
      recordProgress(problem.id, res.verdict.status);
      checks.current += 1;
      // The XP note belongs under the check that earned it; a later check on this visit pays
      // nothing, so it shows none.
      if (solved.current) setSolveUid(null);
      // Correct pays XP once a visit; anything else is "try again" and costs nothing.
      if (res.verdict.status === "correct" && !solved.current && problem.course && problem.topic) {
        solved.current = recordSolve(
          { item: xpItem, course: problem.course, topic: problem.topic },
          // The first hint appears by itself after a wrong check, so only the ones asked for
          // with "Show another hint" count: a wrong answer never costs XP.
          {
            difficulty: problem.difficulty ?? 0,
            checks: checks.current,
            hints: Math.max(0, seen - 1),
            ...(problem.variant_of ? { variant: true } : {}),
          },
        );
        setSolveUid(solved.current);
      }
      // The first check on this visit is what you could do from memory; later checks are you
      // fixing it with feedback, so only the first one schedules the next review.
      const grade = gradeFromVerdict(res.verdict.status, seen);
      if (!scheduled.current && grade && problem.course && problem.topic && problem.difficulty) {
        scheduled.current = true;
        recordProblem(
          {
            id: problem.id,
            course: problem.course,
            topic: problem.topic,
            difficulty: problem.difficulty,
          },
          grade,
        );
      }
    });
  }

  function showSolution() {
    startTransition(async () => {
      const res = await revealSolution(problem.id);
      if (res.ok) {
        setSolution(res.solution);
        setConfirmingSolution(false);
        if (!exam && problem.course && problem.topic) {
          recordReveal({
            item: problem.variant_of ?? problem.id,
            course: problem.course,
            topic: problem.topic,
          });
        }
      } else {
        setError(res.error);
      }
    });
  }

  // ------------------------------------------------------------- derived view state

  const verdict = checked?.verdict ?? null;
  const resultFor = (step: DraftStep): StepResult | null => {
    const c = checked?.steps.get(step.id);
    return c && c.content === step.content && c.kind === step.kind ? c.result : null;
  };
  const stale =
    !exam &&
    checked !== null &&
    (attempt.answer.trim() !== checked.answer ||
      attempt.steps.some((s) => s.content.trim() !== "" && resultFor(s) === null));
  const answerResult =
    verdict?.answer && hasAnswer && attempt.answer.trim() === checked?.answer
      ? verdict.answer
      : null;
  const blank = locked && result !== null && result.steps.length === 0 && result.answer === "";
  const feedback = (verdict?.hints ?? []).filter(
    (h) => h.code !== "AUTHORED_HINT" && !(blank && h.code === "EMPTY_SUBMISSION"),
  );
  const canAskHint =
    !exam &&
    verdict !== null &&
    verdict.status !== "correct" &&
    attempt.hints.length < problem.hint_count;
  const canShowSolution = exam ? locked : verdict !== null;
  const nothingToCheck =
    attempt.steps.every((s) => s.content.trim() === "") && (!hasAnswer || !attempt.answer.trim());

  return (
    <section
      aria-label={label}
      className="space-y-5"
      onKeyDown={(e) => {
        // ⌘/Ctrl + Enter checks from any field, including the step-kind menus.
        if (!exam && e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
          e.preventDefault();
          if (!pending && !nothingToCheck) submit();
        }
      }}
    >
      <ol className="space-y-3">
        {attempt.steps.map((step, i) => {
          const result = resultFor(step);
          const style = result ? STEP_STYLE[result.status] : null;
          return (
            <li key={step.id} className="group">
              <div
                className={`flex items-stretch overflow-hidden rounded-lg border bg-surface transition-colors focus-within:border-accent focus-within:ring-2 focus-within:ring-accent ${style ? style.ring : "border-line"}`}
              >
                <span className="flex w-9 shrink-0 items-center justify-center border-r border-line bg-surface-2 font-mono text-xs text-muted">
                  {i + 1}
                </span>
                {pickKind && (
                  <select
                    aria-label={`Step ${i + 1} kind`}
                    value={step.kind}
                    disabled={locked}
                    onChange={(e) => setStep(step.id, { kind: e.target.value })}
                    className="shrink-0 border-r border-line bg-surface-2 px-2 text-xs font-medium text-muted outline-none"
                  >
                    {problem.step_kinds.map((k) => (
                      <option key={k} value={k}>
                        {stepKindLabel(k)}
                      </option>
                    ))}
                  </select>
                )}
                <input
                  ref={(el) => {
                    if (el) inputs.current.set(step.id, el);
                    else inputs.current.delete(step.id);
                  }}
                  aria-label={`Step ${i + 1}`}
                  value={step.content}
                  readOnly={locked}
                  onChange={(e) => setStep(step.id, { content: e.target.value })}
                  onKeyDown={(e) => {
                    if (!locked) onStepKey(e, step);
                  }}
                  placeholder={
                    locked ? "No work written" : stepPlaceholder(step.kind, problem.kind)
                  }
                  maxLength={500}
                  spellCheck={false}
                  autoComplete="off"
                  autoCapitalize="off"
                  className="min-w-0 flex-1 bg-transparent px-3 py-2.5 font-mono text-[15px] outline-none placeholder:text-muted/60"
                />
                {!locked && (
                  <button
                    type="button"
                    onClick={() => removeStep(step.id)}
                    aria-label={`Remove step ${i + 1}`}
                    className="flex w-11 shrink-0 items-center justify-center text-muted opacity-60 transition hover:text-bad hover:opacity-100 pointer-fine:sm:opacity-0 pointer-fine:sm:group-hover:opacity-60 pointer-fine:sm:focus:opacity-100"
                  >
                    ×
                  </button>
                )}
              </div>
              {result && style && (
                <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1 pl-11 text-sm">
                  <span
                    className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium ${style.chip}`}
                  >
                    <span aria-hidden>{style.icon}</span>
                    {STEP_STATUS_LABEL[result.status]}
                  </span>
                  {result.message && <Rich text={result.message} inline className="text-ink/90" />}
                  {result.latex && (
                    <span className="text-muted">
                      read as <Tex latex={result.latex} className="text-ink" />
                    </span>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>

      {!locked && (
        <div className="flex flex-wrap gap-2 text-sm">
          <button
            type="button"
            onClick={() => insertAfter(attempt.steps[attempt.steps.length - 1].id)}
            className="min-h-11 rounded-md border border-dashed border-line px-3 py-1.5 text-muted transition hover:border-accent hover:text-accent"
          >
            + Add step
          </button>
          <ScanDialog problemKind={problem.kind} hasAnswer={hasAnswer} onApply={applyScan} />
          <span className="self-center text-xs text-muted pointer-coarse:hidden">
            {exam ? "Enter adds a step" : "Enter adds a step · ⌘/Ctrl + Enter checks"}
          </span>
        </div>
      )}

      {hasAnswer && (
        <div>
          <label htmlFor={answerId} className="mb-1.5 block text-sm font-medium">
            Final answer
          </label>
          <input
            id={answerId}
            value={attempt.answer}
            readOnly={locked}
            onChange={(e) => edit((a) => ({ ...a, answer: e.target.value }))}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.metaKey && !e.ctrlKey) {
                e.preventDefault();
                if (!pending && !nothingToCheck) submit();
              }
            }}
            placeholder={locked ? "No answer given" : "Your answer"}
            maxLength={500}
            spellCheck={false}
            autoComplete="off"
            autoCapitalize="off"
            className={`w-full rounded-lg border bg-surface px-3 py-2.5 font-mono text-[15px] outline-none transition-colors focus:border-accent focus:ring-2 focus:ring-accent ${answerResult ? STEP_STYLE[answerResult.status === "correct" ? "ok" : answerResult.status === "partial" ? "warning" : "error"].ring : "border-line"}`}
          />
          <p className="mt-1.5 text-xs text-muted">{problem.answer_format}</p>
          {answerResult && (
            <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
              <StatusIcon status={answerResult.status} />
              <Rich text={answerResult.message} inline />
              {answerResult.latex && (
                <span className="text-muted">
                  read as <Tex latex={answerResult.latex} className="text-ink" />
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {!locked && (
        <div className="flex flex-wrap items-center gap-3">
          {!exam && (
            <button
              type="button"
              onClick={() => submit()}
              disabled={pending || nothingToCheck}
              className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-accent-ink shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {pending ? "Checking…" : "Check my work"}
            </button>
          )}
          <button
            type="button"
            onClick={startOver}
            disabled={exam && nothingToCheck}
            className="min-h-11 px-1 text-sm text-muted underline-offset-4 hover:text-ink hover:underline disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:no-underline"
          >
            {exam ? "Clear this question" : "Start over"}
          </button>
        </div>
      )}

      <div aria-live="polite" className="space-y-4">
        {error && (
          <p className="rounded-lg border border-bad/40 bg-bad-soft px-4 py-3 text-sm text-bad">
            {error}
          </p>
        )}

        {verdict && (
          <div
            className={`rounded-xl border px-4 py-3.5 ${BANNER_STYLE[verdict.status]} ${stale ? "opacity-60" : ""}`}
          >
            <div className="flex items-center gap-2.5">
              <StatusIcon status={verdict.status} />
              <span className="font-semibold">
                {blank ? "Left blank, no credit" : VERDICT_LABEL[verdict.status]}
              </span>
              {stale && (
                <span className="text-xs text-muted">You&apos;ve edited since this check.</span>
              )}
            </div>
            {!hasAnswer && verdict.answer?.message && (
              <Rich text={verdict.answer.message} className="mt-1.5 text-sm" />
            )}
            {!exam && !stale && verdict.status === "correct" && solveUid && (
              <XpNote uids={[solveUid]} className="mt-1.5" />
            )}
            {feedback.length > 0 && (
              <ul className="mt-2.5 space-y-1.5 text-sm">
                {feedback.map((h, i) => (
                  <li key={`${h.code}-${i}`}>
                    <span>
                      {h.step !== null && <span className="font-medium">Step {h.step + 1}: </span>}
                      <Rich text={h.message} inline />
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {!exam && !stale && verdict.status !== "correct" && (
              <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1">
                <button
                  type="button"
                  onClick={tryAgain}
                  className="h-11 rounded-lg border border-line bg-surface px-4 text-sm font-medium hover:border-accent"
                >
                  Try again
                </button>
                <span className="text-sm text-muted">
                  {solvedToday
                    ? "You already solved this one today, so it pays no more XP until tomorrow. "
                    : "No XP yet. "}
                  {attempt.steps.some((st) => resultFor(st)?.status === "error")
                    ? "Fix the marked step and check again"
                    : hasAnswer && answerResult?.status !== "correct"
                      ? attempt.answer.trim()
                        ? "Fix your final answer and check again"
                        : "Enter a final answer and check again"
                      : "Use the feedback above and check again"}
                  {solvedToday ? "." : "; trying again costs nothing."}
                </span>
              </div>
            )}
          </div>
        )}

        {!exam && attempt.hints.length > 0 && (
          <div className="rounded-xl border border-accent/30 bg-accent-soft px-4 py-3.5">
            <p className="text-sm font-semibold text-accent">Hints</p>
            <ul className="mt-1.5 space-y-1.5 text-sm">
              {attempt.hints.map((h) => (
                <li key={h}>
                  <Rich text={h} inline />
                </li>
              ))}
            </ul>
          </div>
        )}

        {(canAskHint || canShowSolution) && (
          <div className="flex flex-wrap items-center gap-3 text-sm">
            {canAskHint && (
              <button
                type="button"
                disabled={pending}
                onClick={() => submit({ anotherHint: true })}
                className="rounded-md border border-accent/40 px-3 py-1.5 font-medium text-accent transition hover:bg-accent-soft disabled:opacity-40"
              >
                Show another hint
              </button>
            )}
            {canShowSolution && !solution && !confirmingSolution && (
              <button
                type="button"
                onClick={() => setConfirmingSolution(true)}
                className="text-muted underline-offset-4 hover:text-ink hover:underline"
              >
                Show solution
              </button>
            )}
            {confirmingSolution && (
              <span className="flex flex-wrap items-center gap-2">
                <span className="text-muted">
                  Reveal the full solution? Trying a hint first usually teaches more.
                  {!exam && !solvedToday && " Seeing it means no XP for this problem today."}
                </span>
                <button
                  type="button"
                  disabled={pending}
                  onClick={showSolution}
                  className="rounded-md bg-ink px-3 py-1 font-medium text-bg disabled:opacity-40"
                >
                  Reveal
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmingSolution(false)}
                  className="text-muted hover:text-ink"
                >
                  Cancel
                </button>
              </span>
            )}
          </div>
        )}

        {solution && (
          <div className="rounded-xl border border-line bg-surface px-4 py-4">
            <p className="text-sm font-semibold">Worked solution</p>
            <ol className="mt-2 list-decimal space-y-2 pl-5 text-[15px]">
              {solution.solution.map((line, i) => (
                <li key={i}>
                  <Rich text={line} />
                </li>
              ))}
            </ol>
            {solution.answer && (
              <p className="mt-3 text-sm">
                <span className="text-muted">Answer key: </span>
                <code className="rounded bg-idle-soft px-1.5 py-0.5 font-mono">
                  {solution.answer}
                </code>
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
