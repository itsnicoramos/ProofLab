import { AgentFlow } from "@/components/AgentFlow";
import { CommandRow } from "@/components/CopyButton";
import { Diagram } from "@/components/Diagram";
import { Replay, type ReplayItem } from "@/components/Replay";
import { StepView } from "@/components/StepView";
import { announce, piecesFor, type Replay as ReplayData } from "@/lib/replay";
import {
  AGENT_COMMAND,
  AGENT_PARTS,
  AGENTS,
  DOCTOR_COMMAND,
  GITHUB_URL,
  HELP_PROMPT,
  MILESTONES,
  RULES,
  SECTIONS,
  SESSION_SHAPE,
  SETUP,
} from "@/lib/site";
import captured from "@/replay/practice-4.json";

const replay = captured as unknown as ReplayData;

export default function HomePage() {
  const items: ReplayItem[] = replay.steps.map((step, i) => ({
    pieces: piecesFor(step),
    label: announce(step, i + 1, replay.steps.length),
    node: <StepView step={step} n={i + 1} />,
  }));

  return (
    <div className="space-y-16 sm:space-y-20">
      <header className="max-w-3xl space-y-5">
        <h1 className="text-3xl leading-tight sm:text-5xl">
          What your agent does when you type <code className="code-inline">/tutor</code>
        </h1>
        <p className="text-lg text-muted">
          ProofLab checks university math one step at a time, starting with the proofs in MATH 123.
          Its repo ships a tutor that runs inside your own coding agent. The
          agent teaches, asks and hints. ProofLab&apos;s checker, written rules and SymPy with no AI,
          decides what&apos;s right.
        </p>
        <div className="flex flex-wrap gap-3">
          <a href="#setup" className="btn btn-primary px-5">
            Set it up
          </a>
          <a href="#session" className="btn btn-secondary px-5">
            Watch a session
          </a>
        </div>
        {/* Below md the header has no section links, so the page lists them here. */}
        <nav aria-label="Sections" className="md:hidden">
          <p className="text-sm text-muted">On this page</p>
          <ul className="mt-1 flex flex-wrap gap-x-5">
            {SECTIONS.map((s) => (
              <li key={s.href}>
                <a href={s.href} className="link inline-flex min-h-11 items-center text-sm">
                  {s.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <Section id="how" title="How the pieces fit">
        <p className="max-w-3xl text-muted">
          Everything the tutor uses is in the repo or on your machine. It covers all 14 chapters
          with lesson notes, and the checker grades 192 exercises from Chapters 1 to 10.
        </p>
        <div className="mt-6 max-w-4xl">
          <Diagram />
        </div>
      </Section>

      <Section id="session" title="One session, step by step">
        <div className="max-w-3xl space-y-3">
          <p className="text-muted">
            A learner practises Chapter 4 in Claude Code. Press Next to follow each turn: what they
            type, what the agent runs, what ProofLab&apos;s checker says back.
          </p>
          <p className="text-sm text-muted">
            {replay.setup_note} The learner&apos;s and tutor&apos;s words were written for this page,
            following the tutor skill. Every command and its output is real, captured from the CLI on{" "}
            {replay.captured_on} with a throwaway memory. For exercises and lessons the page shows the
            fields the tutor uses. The page shortens{" "}
            <code className="code-inline">{replay.cli}</code> to{" "}
            <code className="code-inline">prooflab-tutor</code>.
          </p>
        </div>
        <div className="mt-6">
          <Replay items={items} />
        </div>
      </Section>

      <Section id="rules" title="Seven rules it keeps">
        <p className="max-w-3xl text-muted">
          They&apos;re written in the skill,{" "}
          <code className="code-inline">.claude/skills/tutor/SKILL.md</code>, and repeated in{" "}
          <code className="code-inline">AGENTS.md</code>, so every agent keeps the same ones.
        </p>
        <ol className="mt-6 grid gap-4 md:grid-cols-2">
          {RULES.map((rule) => (
            <li key={rule.n} id={`rule-${rule.n}`} className="card scroll-mt-20">
              <div className="flex items-baseline gap-3">
                <span className="font-serif text-2xl font-semibold tabular-nums">{rule.n}</span>
                <h3 className="text-lg">{rule.title}</h3>
              </div>
              <p className="mt-2 text-muted">{rule.text}</p>
              <a href={`#step-${rule.step + 1}`} className="link mt-1 inline-flex min-h-11 items-center text-sm">
                See it in step {rule.step + 1}
              </a>
            </li>
          ))}
        </ol>
      </Section>

      <Section id="setup" title="Set it up">
        <p className="max-w-3xl text-muted">
          You need uv and a coding agent. Docker (Docker Desktop, or Colima on a Mac) is optional:
          it lets the tutor save your progress. Run these from a terminal.
        </p>
        <a
          href="https://docs.astral.sh/uv/getting-started/installation/"
          className="link inline-flex min-h-11 items-center text-sm"
        >
          How to install uv
        </a>

        <div className="card mt-2 max-w-4xl">
          <h3 className="text-lg">Never used a terminal?</h3>
          <p className="mt-1 text-muted">
            You don&apos;t have to work this out alone. Ask any AI assistant you like to walk you
            through the setup, one step at a time. Paste this to start.
          </p>
          <CommandRow text={HELP_PROMPT} label="ask for help with the setup" what="the prompt" />
        </div>

        <ol className="mt-4 max-w-4xl space-y-4">
          {SETUP.map((s, i) => (
            <li key={s.title} className="card">
              <p className="font-semibold">
                <span className="mr-2 text-muted tabular-nums">{i + 1}.</span>
                {s.title}
              </p>
              <CommandRow text={s.command} label={s.title} />
              {s.note && <p className="mt-2 text-sm text-muted">{s.note}</p>}
            </li>
          ))}
        </ol>

        <p className="mt-4 max-w-3xl text-muted">
          Then open your agent in the ProofLab folder and see{" "}
          <a href="#use" className="link inline-flex min-h-11 items-center">
            how to use the skill
          </a>
          .
        </p>
      </Section>

      <Section id="use" title="How to use the skill">
        <p className="max-w-3xl text-muted">
          The tutor is a skill: plain instructions in{" "}
          <code className="code-inline">.claude/skills/tutor/</code> that any agent able to
          run commands in the repo can follow. Say these words to it.
        </p>
        <ul className="mt-6 grid gap-4 md:grid-cols-3">
          {AGENTS.map((a) => (
            <li key={a.agent} className="card">
              <p className="font-semibold">{a.agent}</p>
              <dl className="mt-2 space-y-2 text-sm">
                {(
                  [
                    ["Start", a.start],
                    ["Next lesson", a.next],
                    ["Practise a chapter", a.practise],
                    ["Quiz or mock test", a.quiz],
                  ] as const
                ).map(([label, words]) => (
                  <div key={label}>
                    <dt className="text-muted">{label}</dt>
                    <dd className="font-mono text-code break-words">{words}</dd>
                  </div>
                ))}
                <div>
                  <dt className="text-muted">How it finds the tutor</dt>
                  <dd>{a.how}</dd>
                </div>
              </dl>
            </li>
          ))}
        </ul>

        <div className="mt-8 grid max-w-4xl gap-x-8 gap-y-6 md:grid-cols-2">
          <div className="border-t border-line pt-3">
            <h3 className="text-lg">What a session looks like</h3>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-muted">
              {SESSION_SHAPE.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
          </div>
          <div className="border-t border-line pt-3">
            <h3 className="text-lg">Check your setup</h3>
            <p className="mt-1 text-muted">
              It says what is missing and how to fix it. Chapters 11 to 14 have lessons but no
              checker yet, so there the tutor gives feedback, never a verdict.
            </p>
            <CommandRow text={DOCTOR_COMMAND} label="check your setup" />
          </div>
        </div>
      </Section>

      <Section id="building" title="Now building">
        <p className="max-w-3xl text-muted">
          Separate from the tutor above: ProofLab&apos;s own agent, with no coding agent needed. A
          model, its tools, a bounded loop and the controls around them. The runtime works and is
          still experimental. The model translates and teaches. Code judges. Postgres remembers.
          The shell is the only door between them.
        </p>
        <div className="mt-6 max-w-4xl">
          <AgentFlow />
        </div>

        <h3 className="mt-10 text-xl">Four parts, one module each</h3>
        <ul className="mt-4 grid gap-x-6 gap-y-6 md:grid-cols-2 lg:grid-cols-4">
          {AGENT_PARTS.map((p) => (
            <li key={p.name} className="border-t border-line pt-3">
              <p className="font-semibold">{p.name}</p>
              <p className="mt-0.5 font-mono text-xs text-muted">{p.where}</p>
              <ul className="mt-2 space-y-1.5 text-sm text-muted">
                {p.points.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            </li>
          ))}
        </ul>

        <div className="card mt-8 max-w-4xl">
          <h3 className="text-lg">Run it</h3>
          <p className="mt-1 text-muted">
            After the setup above, add the agent&apos;s extra with{" "}
            <code className="code-inline">uv sync --extra tutor --extra agent</code> in{" "}
            <code className="code-inline">backend</code>. It needs a paid Anthropic API key in{" "}
            <code className="code-inline">ANTHROPIC_API_KEY</code>, so every turn costs money.
            Each run writes a JSON log to <code className="code-inline">logs/</code>.
          </p>
          <CommandRow text={AGENT_COMMAND} label="run the agent" />
        </div>

        <h3 className="mt-10 text-xl">Milestones</h3>
        <ol className="mt-4 max-w-4xl space-y-3">
          {MILESTONES.map((m) => (
            <li key={m.n} className={`card ${m.status === "next" ? "border-accent ring-1 ring-accent outline-2 outline-transparent" : ""}`}>
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="font-serif text-xl font-semibold tabular-nums">{m.n}</span>
                <p className="font-semibold">{m.title}</p>
                <span
                  className={`ml-auto text-sm ${m.status === "next" ? "font-semibold text-ink" : "text-muted"}`}
                >
                  {STATUS_LABEL[m.status]}
                </span>
              </div>
              <p className="mt-1 text-sm text-muted">{m.text}</p>
            </li>
          ))}
        </ol>

        <a href={GITHUB_URL} className="btn btn-secondary mt-10 px-5">
          Get the code on GitHub
        </a>
      </Section>
    </div>
  );
}

const STATUS_LABEL = { done: "Done", next: "Building next", planned: "Planned" } as const;

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="scroll-mt-20">
      <h2 id={`${id}-heading`} className="mb-4 border-b border-line pb-2 text-2xl sm:text-3xl">
        {title}
      </h2>
      {children}
    </section>
  );
}
