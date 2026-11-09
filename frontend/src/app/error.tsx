"use client";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-lg space-y-4 py-16">
      <h1 className="text-2xl">This page didn&apos;t load</h1>
      <p className="text-muted">Something went wrong while showing it. Try again.</p>
      <button
        type="button"
        onClick={reset}
        className="h-11 rounded-lg bg-accent px-4 text-sm font-semibold text-accent-ink"
      >
        Try again
      </button>
    </div>
  );
}
