"use client";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-lg space-y-4 py-16">
      <h1 className="text-2xl font-semibold">ProofLab&apos;s checker isn&apos;t reachable</h1>
      <p className="text-muted">
        The website couldn&apos;t load data from the backend. Make sure it&apos;s running:
      </p>
      <pre className="overflow-x-auto rounded-lg border border-line bg-surface px-4 py-3 font-mono text-sm">
        cd backend{"\n"}uv run uvicorn prooflab.main:create_app --factory --reload --reload-dir src --app-dir src
      </pre>
      <button
        type="button"
        onClick={reset}
        className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink"
      >
        Try again
      </button>
    </div>
  );
}
