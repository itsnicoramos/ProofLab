import { CopyButton } from "@/components/CopyButton";
import { Diagram } from "@/components/Diagram";
import { Replay, type ReplayItem } from "@/components/Replay";
import { StepView } from "@/components/StepView";
import { announce, piecesFor, type Replay as ReplayData } from "@/lib/replay";
import { AGENTS, BOOK_URL, GITHUB_URL, RULES, SETUP } from "@/lib/site";
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
          What your agent does when you type <code className="font-mono text-[0.85em]">/tutor</code>
        </h1>
        <p className="text-lg text-muted">
          ProofLab checks university math one step at a time, starting with <em>Book of Proof</em>,
          the MATH 123 textbook. Its repo ships a tutor that runs inside your own coding agent. The
          agent teaches, asks and hints. ProofLab&apos;s checker, written rules and SymPy with no AI,
          decides what&apos;s right.
        </p>
        <div className="flex flex-wrap gap-3">
          <a
            href="#setup"
            className="inline-flex h-11 items-center rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink"
          >
            Set it up
          </a>
          <a
            href="#session"
            className="inline-flex h-11 items-center rounded-lg border border-line bg-surface px-5 text-sm font-semibold"
          >
            Watch a session
          </a>
        </div>
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
            {replay.captured_on} with a throwaway memory. The page shortens{" "}
            <code className="font-mono text-xs">{replay.cli}</code> to{" "}
            <code className="font-mono text-xs">prooflab-tutor</code>.
          </p>
        </div>
        <div className="mt-6">
          <Replay items={items} />
        </div>
      </Section>

      <Section id="rules" title="Seven rules it keeps">
        <p className="max-w-3xl text-muted">
          They&apos;re written in the skill,{" "}
          <code className="font-mono text-sm">.claude/skills/tutor/SKILL.md</code>, and repeated in{" "}
          <code className="font-mono text-sm">AGENTS.md</code>, so every agent keeps the same ones.
        </p>
        <ol className="mt-6 grid gap-4 md:grid-cols-2">
          {RULES.map((rule) => (
            <li
              key={rule.n}
              id={`rule-${rule.n}`}
              className="scroll-mt-20 rounded-lg border border-line bg-surface px-5 py-4"
            >
              <div className="flex items-baseline gap-3">
                <span className="font-serif text-2xl font-semibold tabular-nums">{rule.n}</span>
                <h3 className="text-lg">{rule.title}</h3>
              </div>
              <p className="mt-2 text-muted">{rule.text}</p>
              <a
                href={`#step-${rule.step + 1}`}
                className="mt-1 inline-flex min-h-11 items-center text-sm text-accent hover:underline"
              >
                See it in step {rule.step + 1}
              </a>
            </li>
          ))}
        </ol>
      </Section>

      <Section id="setup" title="Set it up">
        <p className="max-w-3xl text-muted">
          You need uv, Docker (Docker Desktop, or Colima on a Mac) and a coding agent. Run these from
          a terminal.
        </p>
        <a
          href="https://docs.astral.sh/uv/getting-started/installation/"
          className="inline-flex min-h-11 items-center text-sm text-accent hover:underline"
        >
          How to install uv
        </a>
        <ol className="mt-4 max-w-4xl space-y-4">
          {SETUP.map((s, i) => (
            <li key={s.title} className="rounded-lg border border-line bg-surface px-4 py-3">
              <p className="font-semibold">
                <span className="mr-2 text-muted tabular-nums">{i + 1}.</span>
                {s.title}
              </p>
              <div className="mt-2 flex items-start gap-2">
                <code className="min-w-0 flex-1 rounded-md bg-idle-soft px-3 py-2.5 font-mono text-[13px] break-words">
                  {s.command}
                </code>
                <CopyButton text={s.command} label={s.title} />
              </div>
              {s.note && <p className="mt-2 text-sm text-muted">{s.note}</p>}
            </li>
          ))}
        </ol>

        <h3 className="mt-10 text-xl">Which agents work</h3>
        <p className="mt-2 max-w-3xl text-muted">
          Any agent that can run commands in the repo. These are the words to start with.
        </p>
        <ul className="mt-4 grid gap-4 md:grid-cols-3">
          {AGENTS.map((a) => (
            <li key={a.agent} className="rounded-lg border border-line bg-surface px-4 py-3">
              <p className="font-semibold">{a.agent}</p>
              <dl className="mt-2 space-y-2 text-sm">
                <div>
                  <dt className="text-muted">Start</dt>
                  <dd className="font-mono text-[13px] break-words">{a.start}</dd>
                </div>
                <div>
                  <dt className="text-muted">Practise a chapter</dt>
                  <dd className="font-mono text-[13px] break-words">{a.practise}</dd>
                </div>
                <div>
                  <dt className="text-muted">How it finds the tutor</dt>
                  <dd>{a.how}</dd>
                </div>
              </dl>
            </li>
          ))}
        </ul>

        <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-2">
          <a
            href={GITHUB_URL}
            className="inline-flex h-11 items-center rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink"
          >
            Get the code on GitHub
          </a>
          <a href={BOOK_URL} className="inline-flex min-h-11 items-center text-sm text-accent hover:underline">
            Book of Proof, free PDF from the author
          </a>
        </div>
      </Section>
    </div>
  );
}

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
