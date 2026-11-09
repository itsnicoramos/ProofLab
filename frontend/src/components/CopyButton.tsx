"use client";

import { useState } from "react";

/** Copies one command. Says "Copied" for a moment, and tells screen readers too. */
export function CopyButton({ text, label }: { text: string; label: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("failed");
    }
    window.setTimeout(() => setState("idle"), 2000);
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={`Copy the command: ${label}`}
      className="h-11 shrink-0 rounded-lg border border-line bg-surface px-3 text-sm font-semibold"
    >
      <span aria-live="polite">
        {state === "copied" ? "Copied" : state === "failed" ? "Select and copy" : "Copy"}
      </span>
    </button>
  );
}
