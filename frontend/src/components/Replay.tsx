"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { PieceTrail } from "@/components/Diagram";
import type { Piece } from "@/lib/replay";

export type ReplayItem = { pieces: Piece[]; label: string; node: ReactNode };

const STEP_HASH = /^#step-(\d+)$/;

/**
 * The /tutor session, one step at a time. The steps are rendered on the server; this only
 * decides how many are visible. A link to #step-N (from the rules) shows the session up to N.
 */
export function Replay({ items }: { items: ReplayItem[] }) {
  const total = items.length;
  const [current, setCurrent] = useState(1);
  const [said, setSaid] = useState("");
  const scrollTarget = useRef<{ n: number; block: ScrollLogicalPosition } | null>(null);

  const go = useCallback(
    (n: number, block: ScrollLogicalPosition = "nearest") => {
      const next = Math.min(Math.max(n, 1), total);
      setCurrent(next);
      setSaid(items[next - 1].label);
      scrollTarget.current = { n: next, block };
    },
    [items, total],
  );

  useEffect(() => {
    const target = scrollTarget.current;
    if (!target) return;
    scrollTarget.current = null;
    document.getElementById(`step-${target.n}`)?.scrollIntoView({ block: target.block });
  }, [current]);

  useEffect(() => {
    const fromHash = () => {
      const match = STEP_HASH.exec(window.location.hash);
      if (!match) return;
      go(Number(match[1]), "start");
      // Drop the hash so the same rule link works again on a second click.
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    return () => window.removeEventListener("hashchange", fromHash);
  }, [go]);

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_15rem]">
      <div>
        <div className="sticky top-14 z-20 -mx-4 border-b border-line bg-bg px-4 py-2 sm:mx-0 sm:px-0">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => go(current - 1)}
              disabled={current === 1}
              className="h-11 rounded-lg border border-line bg-surface px-4 text-sm font-semibold disabled:opacity-50"
            >
              Back
            </button>
            <button
              type="button"
              onClick={() => go(current + 1)}
              disabled={current === total}
              className="h-11 rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink disabled:opacity-50"
            >
              Next
            </button>
            <p className="px-1 text-sm text-muted tabular-nums">
              Step {current} of {total}
            </p>
            <button
              type="button"
              onClick={() => (current === total ? go(1, "start") : go(total))}
              className="ml-auto h-11 px-2 text-sm text-accent hover:underline"
            >
              {current === total ? "Start over" : "Show all"}
            </button>
          </div>
        </div>
        <p aria-live="polite" className="sr-only">
          {said}
        </p>
        <ol className="mt-6 space-y-5">
          {items.slice(0, current).map((item, i) => {
            const here = i + 1 === current;
            return (
              <li
                key={i}
                id={`step-${i + 1}`}
                aria-current={here ? "step" : undefined}
                className={`scroll-mt-32 rounded-xl p-2 sm:p-3 ${here ? "ring-2 ring-accent" : ""}`}
              >
                {item.node}
              </li>
            );
          })}
        </ol>
        {current < total && (
          <p className="mt-6 text-sm text-muted">
            {total - current} more {total - current === 1 ? "step" : "steps"}. Press Next.
          </p>
        )}
      </div>
      <aside aria-label="Which pieces this step uses" className="hidden lg:block">
        <div className="sticky top-32">
          <PieceTrail active={items[current - 1].pieces} />
        </div>
      </aside>
    </div>
  );
}
