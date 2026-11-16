// The diagrams' two parts, shared by the tutor diagram and the agent flowchart: bordered
// cards joined by labelled arrows that name both ends, so they read right at any width.

/** One piece. The checker gets the ink border instead of the hairline: it is the only judge. */
export function FlowCard({
  title,
  where,
  children,
  judge = false,
}: {
  title: string;
  where?: string;
  children: React.ReactNode;
  judge?: boolean;
}) {
  return (
    <div className={`card h-full ${judge ? "border-ink" : ""}`}>
      <p className="font-semibold">{title}</p>
      {where && <p className="mt-0.5 break-words font-mono text-xs text-muted">{where}</p>}
      <div className="mt-2 text-sm text-muted">{children}</div>
    </div>
  );
}

export function FlowArrow({ text, both = false }: { text: string; both?: boolean }) {
  return (
    <p className="flex items-center gap-2 py-2 pl-4 text-sm text-muted">
      <span aria-hidden className="text-base text-ink">
        {both ? "↕" : "↓"}
      </span>
      {text}
    </p>
  );
}
