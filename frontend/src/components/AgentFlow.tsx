// The README's flowchart of ProofLab's own agent, drawn like the tutor diagram above it.
import { FlowArrow as Arrow, FlowCard as Card } from "@/components/Flow";

/** The loop inside the runtime, one step: the three things that happen, in order. */
function LoopStrip() {
  const stages = ["ask the model", "run its tool calls", "check, approve, log"];
  return (
    <ol aria-label="One step of the loop" className="mt-3 flex flex-wrap items-center gap-1.5">
      {stages.map((s, i) => (
        <li key={s} className="flex items-center gap-1.5">
          <span className="rounded-md bg-idle-soft px-2 py-1 font-mono text-xs text-ink">
            {i + 1}. {s}
          </span>
          {i < stages.length - 1 && (
            <span aria-hidden className="text-ink">
              →
            </span>
          )}
        </li>
      ))}
      <li className="font-mono text-xs text-muted">repeat, at most 12 times</li>
    </ol>
  );
}

export function AgentFlow() {
  return (
    <div>
      <Card title="Learner" where="a terminal">
        Types what they want to learn, writes proofs in their own words and answers the [y/N]
        prompts.
      </Card>
      <Arrow text="The learner talks to prooflab-agent, which runs in their terminal." />
      <div className="grid gap-3 sm:grid-cols-2">
        <Card title="Agent runtime" where="prooflab-agent run">
          Owns the loop, so the harness decides what happens next, not the model. A tool error
          goes back to the model as a message instead of crashing it.
          <LoopStrip />
        </Card>
        <Card title="Model" where="Claude by default, set with --model">
          Teaches, asks questions and turns the learner&apos;s words into ProofLab steps. Swappable
          behind one method. It never grades.
        </Card>
      </div>
      <Arrow
        both
        text="The runtime sends the conversation to the model, and the model answers with words or tool calls."
      />
      <Card title="Guard" where="backend/src/prooflab/tutor_guard.py">
        An allowlist that judges every command before it runs. A deny is final, and the
        learner&apos;s yes can&apos;t override it. Claude Code, Codex and Cursor reach the same
        guard through AGENTS.md.
      </Card>
      <Arrow text="An allowed call runs as one prooflab-tutor command, with the learner's text on stdin." />
      <Card title="prooflab-tutor" where="backend/src/prooflab/tutor.py">
        The shell contract: one JSON object out and an exit code the agent can act on (0 done, 1
        bad request, 3 memory down).
      </Card>
      <Arrow text="prooflab-tutor asks the checker for verdicts and reads and writes memory." />
      <div className="grid gap-3 md:grid-cols-2">
        <Card title="Checker" where="backend/src/prooflab/engine/" judge>
          SymPy and written rules, in an isolated worker with a time limit. The same input always
          gets the same verdict, and only it decides right and wrong.
        </Card>
        <Card title="Postgres memory" where="127.0.0.1:5433">
          The plan, attempts, notes and reviews. If it is down, the verdict still comes back.
        </Card>
      </div>
    </div>
  );
}
