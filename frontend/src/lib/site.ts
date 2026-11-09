// Words and links the explainer page shows. The rules restate .claude/skills/tutor/SKILL.md
// in short; keep them in step with it. Keep this file free of imports so `npm test` can load it.

import type { Piece } from "./replay.ts";

export const GITHUB_URL = "https://github.com/itsnicoramos/ProofLab";
export const BOOK_URL = "https://richardhammack.github.io/BookOfProof/";

export type Rule = { n: number; title: string; text: string; step: number };

/** `step` is the 0-based replay step that shows the rule at work. */
export const RULES: Rule[] = [
  {
    n: 1,
    title: "The checker is the only judge",
    text: "The tutor says correct only after ProofLab's checker returned correct, and it says who decided. Chapters 11 to 14 have no checker yet, so there it gives feedback, never a verdict.",
    step: 16,
  },
  {
    n: 2,
    title: "Translate, never fix",
    text: "It turns the learner's own words into ProofLab steps and shows them before checking. A slip goes in exactly as written, so the verdict is about the learner's work.",
    step: 8,
  },
  {
    n: 3,
    title: "Hints before answers",
    text: "First a question about the flagged step, then the authored hints in order, then one hint of its own. The solution only when the learner says they give up.",
    step: 11,
  },
  {
    n: 4,
    title: "Try again, don't move on",
    text: "On a wrong verdict it points at the first flagged step, explains it in plain words and asks for another attempt. It doesn't rewrite the step.",
    step: 11,
  },
  {
    n: 5,
    title: "Exercises only through the CLI",
    text: "The problem files hold solutions, so the agent never opens them. It reads exercises through prooflab-tutor, which leaves solutions and quiz answers out.",
    step: 5,
  },
  {
    n: 6,
    title: "No book text, nothing invented",
    text: "It cites Book of Proof by section and page and links the free PDF. Practice comes from ProofLab's exercise bank or a labelled new-number version.",
    step: 6,
  },
  {
    n: 7,
    title: "Stay local",
    text: "Memory changes go through prooflab-tutor memory into a Postgres on the learner's machine. The agent never starts a server, never runs SQL and never opens ProofLab's progress database.",
    step: 18,
  },
];

export type PieceInfo = { id: Piece; name: string; where?: string; text: string };

export const PIECES: Record<Piece, PieceInfo> = {
  learner: {
    id: "learner",
    name: "Learner",
    text: "Types /tutor, answers questions and writes proofs in their own words.",
  },
  agent: {
    id: "agent",
    name: "Coding agent",
    where: "Claude Code, Codex, Cursor",
    text: "Teaches, asks questions and turns the learner's work into ProofLab steps. It never grades.",
  },
  skill: {
    id: "skill",
    name: "Tutor skill",
    where: ".claude/skills/tutor/",
    text: "SKILL.md, six modes and the rules. Agents other than Claude Code reach it through AGENTS.md.",
  },
  cli: {
    id: "cli",
    name: "prooflab-tutor",
    where: "backend/src/prooflab/tutor.py",
    text: "The only way the agent touches ProofLab. Every command prints JSON, and none needs a server.",
  },
  content: {
    id: "content",
    name: "Content",
    where: "backend/src/prooflab/content/",
    text: "Book of Proof exercises restated in ProofLab's words, 14 lesson notes and concept cards. Solutions stay behind the CLI.",
  },
  checker: {
    id: "checker",
    name: "Checker",
    where: "backend/src/prooflab/engine/",
    text: "Written rules and SymPy, no AI. The same input always gets the same verdict, and only it decides right and wrong.",
  },
  memory: {
    id: "memory",
    name: "Memory",
    where: "Postgres on 127.0.0.1:5433",
    text: "The plan, sessions, checked attempts and notes, in a local Postgres. A readable copy goes to LEARNING.md.",
  },
};

export const PIECE_ORDER: Piece[] = ["learner", "agent", "skill", "cli", "content", "checker", "memory"];

export type SetupStep = { title: string; command: string; note?: string };

export const SETUP: SetupStep[] = [
  {
    title: "Clone the repo",
    command: "git clone https://github.com/itsnicoramos/ProofLab.git && cd ProofLab",
  },
  {
    title: "Start the tutor's memory",
    command: "docker compose up -d tutor-db",
    note: "Without it the tutor still teaches and checks. It just can't save your progress.",
  },
  {
    title: "Install the tools",
    command: "cd backend && uv sync --extra tutor && uv run prooflab-tutor memory init && cd ..",
  },
  {
    title: "Open your agent in the ProofLab folder and start",
    command: "/tutor",
  },
];

export type AgentRow = { agent: string; start: string; practise: string; how: string };

export const AGENTS: AgentRow[] = [
  {
    agent: "Claude Code",
    start: "/tutor",
    practise: "/tutor practice 4",
    how: "Loads .claude/skills/tutor as the /tutor skill.",
  },
  {
    agent: "Codex",
    start: "use the tutor skill to start",
    practise: "practise chapter 4",
    how: "Reads AGENTS.md, which points it to the skill.",
  },
  {
    agent: "Other agents",
    start: "Read AGENTS.md and be my tutor",
    practise: "practise chapter 4",
    how: "Follow AGENTS.md, then the skill file, in plain words.",
  },
];
