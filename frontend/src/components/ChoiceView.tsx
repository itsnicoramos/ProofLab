"use client";

import { useId } from "react";

import { Rich, Tex } from "@/components/Rich";
import { stepKindLabel } from "@/lib/labels";

export interface ChoiceLike {
  stem: string;
  choices: { key: string; latex: string | null; text: string | null }[];
  steps?: { kind: string; content: string; latex: string | null }[];
  attempt_answer?: string | null;
}

export interface ChoiceGraded {
  correct: string;
  explanation: string | null;
  solution?: string[];
}

/**
 * A multiple-choice question: the stem, an optional attempt to inspect ("spot the wrong step"),
 * and the choices as large radio rows. After grading, the right choice is marked, the picked
 * one too if it was wrong, and the explanation and worked solution appear.
 */
export function ChoiceView({
  question,
  label,
  picked,
  onPick,
  graded,
}: {
  question: ChoiceLike;
  label: string;
  picked: string | null;
  onPick?: (key: string) => void;
  graded: ChoiceGraded | null;
}) {
  const name = useId();
  const locked = !onPick || graded !== null;

  return (
    <div className="space-y-4">
      {question.steps && question.steps.length > 0 && (
        <ol className="space-y-1.5 rounded-xl border border-line bg-surface-2 px-4 py-3">
          {question.steps.map((s, i) => (
            <li key={i} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[15px]">
              <span className="w-14 shrink-0 font-mono text-xs text-muted">Step {i + 1}</span>
              <span className="text-xs text-muted">{stepKindLabel(s.kind)}</span>
              {s.latex ? (
                <Tex latex={s.latex} className="min-w-0" />
              ) : (
                <code className="min-w-0 break-words font-mono text-sm">{s.content}</code>
              )}
            </li>
          ))}
          {question.attempt_answer && (
            <li className="flex flex-wrap items-baseline gap-x-3 text-[15px]">
              <span className="w-14 shrink-0 font-mono text-xs text-muted">Answer</span>
              <code className="font-mono text-sm">{question.attempt_answer}</code>
            </li>
          )}
        </ol>
      )}

      <fieldset className="min-w-0 space-y-2">
        <legend className="mb-2 font-medium">
          {question.stem}
          <span className="sr-only"> ({label})</span>
        </legend>
        {question.choices.map((c) => {
          const isPicked = picked === c.key;
          const isRight = graded?.correct === c.key;
          const state = graded
            ? isRight
              ? "border-ok bg-ok-soft"
              : isPicked
                ? "border-bad bg-bad-soft"
                : "border-line opacity-70"
            : isPicked
              ? "border-accent bg-accent-soft"
              : "border-line hover:border-accent";
          return (
            <label
              key={c.key}
              className={`flex min-h-12 items-center gap-3 rounded-lg border px-3 py-2 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-accent ${state} ${
                locked ? "cursor-default" : "cursor-pointer"
              }`}
            >
              <input
                type="radio"
                name={name}
                value={c.key}
                checked={isPicked}
                disabled={locked}
                onChange={() => onPick?.(c.key)}
                className="sr-only"
              />
              <span
                aria-hidden
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border font-mono text-xs ${
                  isPicked && !graded ? "border-accent bg-accent text-accent-ink" : "border-line"
                }`}
              >
                {graded && isRight ? "✓" : graded && isPicked ? "✗" : c.key.toUpperCase()}
              </span>
              <span className="min-w-0 flex-1 overflow-x-auto py-1">
                {c.latex ? <Tex latex={c.latex} /> : <span className="text-[15px]">{c.text}</span>}
              </span>
              {graded && (isRight || isPicked) && (
                <span className="shrink-0 text-xs font-medium">
                  {isRight ? (isPicked ? "Your answer, right" : "Right answer") : "Your answer"}
                </span>
              )}
            </label>
          );
        })}
      </fieldset>

      {graded && (
        <div className="space-y-3">
          {picked === null || picked === "" ? (
            <p className="text-sm text-muted">Left blank.</p>
          ) : null}
          {graded.explanation && (
            <Rich
              text={graded.explanation}
              className="rounded-lg border border-line bg-surface px-4 py-3 text-sm"
            />
          )}
          {graded.solution && graded.solution.length > 0 && (
            <details className="rounded-lg border border-line bg-surface px-4">
              <summary className="cursor-pointer py-3 text-sm font-medium">Worked solution</summary>
              <div className="space-y-2 pb-3 text-sm">
                {graded.solution.map((line, i) => (
                  <Rich key={i} text={line} />
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
