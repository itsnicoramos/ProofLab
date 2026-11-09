// The /tutor replay on the home page. The turns live in src/replay/practice-4.script.json;
// frontend/scripts/capture_replay.py runs every command for real and writes practice-4.json,
// which is what the page shows. Keep this file free of imports so `npm test` can load it.

export type Piece = "learner" | "agent" | "skill" | "cli" | "content" | "checker" | "memory";
export type Touches = "content" | "checker" | "memory";

export type ProposedStep = { kind: string; content: string };

type Base = { rules?: number[] };
export type LearnerStep = Base & { kind: "learner"; text: string };
export type TutorStep = Base & {
  kind: "tutor";
  text: string;
  proposal?: ProposedStep[];
  after?: string;
  aside?: string;
};
export type ReadStep = Base & { kind: "read"; files: string[]; summary: string };
export type RunStep = Base & {
  kind: "run";
  touches: Touches;
  args: string[];
  summary: string;
  exit: number;
  output: unknown;
  stdin?: unknown;
  file?: string;
  file_text?: string;
};
export type ReplayStep = LearnerStep | TutorStep | ReadStep | RunStep;

export type Replay = {
  title: string;
  about: string;
  setup_note: string;
  captured_on: string;
  cli: string;
  setup: unknown[];
  steps: ReplayStep[];
};

export type StepVerdict = {
  index: number;
  kind: string;
  status: "ok" | "error" | "warning" | "unchecked";
  message: string;
  latex: string | null;
  code: string | null;
};
export type CheckOutput = {
  checked_by: string;
  problem_id: string;
  verdict: {
    status: "correct" | "incorrect" | "partial" | "invalid";
    steps: StepVerdict[];
    answer: { status: string; message: string; code: string | null } | null;
    hints: { code: string; message: string; step: number | null }[];
  };
  recorded?: boolean;
  attempt_id?: number;
  first_try?: boolean;
  counted?: boolean;
};

export const isCheck = (step: ReplayStep): step is RunStep & { output: CheckOutput } =>
  step.kind === "run" && step.args[0] === "check";

/** The pieces of the diagram a step uses, in flow order. */
export function piecesFor(step: ReplayStep): Piece[] {
  switch (step.kind) {
    case "learner":
      return ["learner"];
    case "tutor":
      return ["agent"];
    case "read":
      return ["agent", "skill"];
    case "run": {
      const pieces: Piece[] = ["agent", "cli", step.touches];
      // `check --record` asks the checker, then saves its verdict to memory.
      if (step.args.includes("--record") && step.touches !== "memory") pieces.push("memory");
      return pieces;
    }
  }
}

const quote = (arg: string) => (/^[\w./:@-]+$/.test(arg) ? arg : `"${arg.replace(/"/g, '\\"')}"`);

/** The command as the agent runs it, shortened to the CLI's name. */
export const command = (step: RunStep) => ["prooflab-tutor", ...step.args.map(quote)].join(" ");

export const ACTOR: Record<ReplayStep["kind"], string> = {
  learner: "Learner types",
  tutor: "Tutor says",
  read: "Agent reads",
  run: "Agent runs",
};

/** One line for screen readers when a step appears. */
export function announce(step: ReplayStep, n: number, total: number): string {
  const what =
    step.kind === "run"
      ? command(step)
      : step.kind === "read"
        ? step.files.join(", ")
        : step.text.split("\n")[0];
  return `Step ${n} of ${total}. ${ACTOR[step.kind]}: ${what}`;
}
