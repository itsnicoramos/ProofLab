"use client";

import Link from "next/link";

import { useTestHistory } from "@/lib/storage";

const DATE = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });

function formatScore(score: number, questions: number): string {
  const points = Number.isInteger(score) ? String(score) : score.toFixed(1);
  const percent = questions ? Math.round((score / questions) * 100) : 0;
  return `${points} / ${questions} · ${percent}%`;
}

/** Practice tests opened on any device (synced through the progress database), newest first. */
export function TestHistory() {
  const history = useTestHistory();
  if (history === null) return null; // before hydration: nothing to read yet

  return (
    <section aria-labelledby="history-heading" className="space-y-3">
      <h2 id="history-heading" className="text-xl">
        Your tests
      </h2>
      {history.length === 0 ? (
        <p className="text-sm text-muted">
          Tests you start show up here, with your score once you submit. They&apos;re saved in
          ProofLab&apos;s database on your Mac, so every device sees them.
        </p>
      ) : (
        <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
          {history.slice(0, 12).map((t) => (
            <li key={t.id}>
              <Link
                href={t.href}
                className="flex min-h-14 flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2 hover:bg-surface-2"
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">{t.title}</span>
                  <span className="text-xs text-muted">
                    {DATE.format(t.startedAt)} · {t.questions} questions
                  </span>
                </span>
                <span className="text-sm">
                  {t.submittedAt !== null && t.score !== null ? (
                    <span className="font-mono">{formatScore(t.score, t.questions)}</span>
                  ) : (
                    <span className="text-muted">In progress</span>
                  )}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
