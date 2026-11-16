"use client";

import { useEffect, useRef, useState } from "react";

/** A command (or prompt) to copy, with its Copy button beside it. */
export function CommandRow({ text, label, what }: { text: string; label: string; what?: string }) {
  return (
    <div className="mt-2 flex items-start gap-2">
      <code className="cmd">{text}</code>
      <CopyButton text={text} label={label} what={what} />
    </div>
  );
}

const WORD ={ idle: "Copy", copied: "Copied", failed: "Select and copy" } as const;

/** Copies one command (or, with `what`, something else). Says "Copied" for a moment, and
 * tells screen readers through a status region beside the button. */
export function CopyButton({
  text,
  label,
  what = "the command",
}: {
  text: string;
  label: string;
  what?: string;
}) {
  const [state, setState] = useState<keyof typeof WORD>("idle");
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("failed");
    }
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setState("idle"), 2000);
  }

  return (
    <>
      <button
        type="button"
        onClick={copy}
        aria-label={`Copy ${what}: ${label}`}
        className="btn btn-secondary"
      >
        {WORD[state]}
      </button>
      <span role="status" className="sr-only">
        {state === "idle" ? "" : WORD[state]}
      </span>
    </>
  );
}
