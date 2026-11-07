import type { ReviewStatus, VerdictStatus } from "@/lib/types";

export function DifficultyDots({ level }: { level: number }) {
  return (
    <span
      className="inline-flex items-center gap-0.5"
      title={`Difficulty ${level} of 3`}
      aria-label={`Difficulty ${level} of 3`}
    >
      {[1, 2, 3].map((n) => (
        <span
          key={n}
          className={`h-1.5 w-1.5 rounded-full ${n <= level ? "bg-ink" : "bg-line"}`}
        />
      ))}
    </span>
  );
}

export function ReviewBadge({ status, className = "" }: { status: ReviewStatus; className?: string }) {
  if (status !== "draft") return null;
  return (
    <span
      className={`rounded border border-line px-1.5 py-0.5 text-xs text-muted ${className}`}
      title="The answer key is machine-verified, but a person hasn't reviewed this problem yet."
    >
      Draft
    </span>
  );
}

const STATUS_STYLE: Record<VerdictStatus, string> = {
  correct: "bg-ok-soft text-ok",
  partial: "bg-warn-soft text-warn",
  incorrect: "bg-bad-soft text-bad",
  invalid: "bg-idle-soft text-idle",
};

const STATUS_ICON: Record<VerdictStatus, string> = {
  correct: "✓",
  partial: "◐",
  incorrect: "✗",
  invalid: "?",
};

export function StatusIcon({ status, className = "" }: { status: VerdictStatus; className?: string }) {
  return (
    <span
      className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold ${STATUS_STYLE[status]} ${className}`}
      aria-hidden
    >
      {STATUS_ICON[status]}
    </span>
  );
}

export { STATUS_STYLE };
