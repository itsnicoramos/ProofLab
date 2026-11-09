import type { Piece } from "@/lib/replay";
import { PIECE_ORDER, PIECES } from "@/lib/site";

/** One piece of the tutor. The checker gets the ink border: it is the only judge. */
function Node({ piece }: { piece: Piece }) {
  const info = PIECES[piece];
  const judge = piece === "checker";
  return (
    <div
      className={`h-full rounded-lg border bg-surface px-4 py-3 ${judge ? "border-ink" : "border-line"}`}
    >
      <p className="font-semibold">{info.name}</p>
      {info.where && <p className="mt-0.5 break-words font-mono text-xs text-muted">{info.where}</p>}
      <p className="mt-2 text-sm text-muted">{info.text}</p>
    </div>
  );
}

/** A labelled arrow between rows. The label names both ends, so it reads right at any width. */
function Arrow({ text }: { text: string }) {
  return (
    <p className="flex items-center gap-2 py-2 pl-4 text-sm text-muted">
      <span aria-hidden className="text-base text-ink">
        ↓
      </span>
      {text}
    </p>
  );
}

/** The whole tutor, top to bottom: who talks to whom, and what each piece is for. */
export function Diagram() {
  return (
    <div>
      <Node piece="learner" />
      <Arrow text="The learner types /tutor and their work into their agent." />
      <Node piece="agent" />
      <div className="grid sm:grid-cols-2 sm:gap-x-4">
        <div className="flex flex-col">
          <Arrow text="The agent reads its rules and steps in the skill." />
          <div className="flex-1">
            <Node piece="skill" />
          </div>
        </div>
        <div className="flex flex-col">
          <Arrow text="The agent runs every command through prooflab-tutor." />
          <div className="flex-1">
            <Node piece="cli" />
          </div>
        </div>
      </div>
      <Arrow text="prooflab-tutor loads the exercise, asks the checker and saves to memory." />
      <div className="grid gap-3 md:grid-cols-3">
        <Node piece="content" />
        <Node piece="checker" />
        <Node piece="memory" />
      </div>
    </div>
  );
}

/** The replay's side panel: which pieces the current step uses ("you are here"). */
export function PieceTrail({ active }: { active: Piece[] }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <p className="text-sm font-semibold">Working in this step</p>
      <ol className="mt-3 space-y-1.5">
        {PIECE_ORDER.map((id) => {
          const on = active.includes(id);
          return (
            <li
              key={id}
              className={`rounded-md border px-3 py-1.5 text-sm ${
                on ? "border-accent bg-accent-soft font-semibold text-ink" : "border-line text-muted"
              }`}
            >
              {PIECES[id].name}
              {on && <span className="sr-only"> (in use)</span>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
