import { FlowArrow as Arrow, FlowCard } from "@/components/Flow";
import type { Piece } from "@/lib/replay";
import { PIECE_ORDER, PIECES } from "@/lib/site";

/** One piece of the tutor. */
function Node({ piece }: { piece: Piece }) {
  const info = PIECES[piece];
  return (
    <FlowCard title={info.name} where={info.where} judge={piece === "checker"}>
      {info.text}
    </FlowCard>
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
    <div className="card">
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
