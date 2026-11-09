import { Rich, Tex } from "@/components/Rich";
import {
  ACTOR,
  command,
  isCheck,
  pageOutputs,
  type CheckOutput,
  type ReplayStep,
  type RunStep,
  type StepVerdict,
} from "@/lib/replay";
import { RULES } from "@/lib/site";

const TOUCHES: Record<RunStep["touches"], string> = {
  content: "Content",
  checker: "Checker",
  memory: "Memory",
};

/** One replay step: who acts, then what they said or ran. Rendered on the server. */
export function StepView({ step, n }: { step: ReplayStep; n: number }) {
  return (
    <div className="grid gap-2 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-4">
      <p className="flex items-baseline gap-2 text-sm sm:flex-col sm:gap-0 sm:pt-3">
        <span className="text-muted tabular-nums">Step {n}</span>
        <span className="font-semibold">{ACTOR[step.kind]}</span>
      </p>
      <div className="min-w-0 space-y-2">
        <Body step={step} />
        {step.rules && step.rules.length > 0 && <RuleLinks rules={step.rules} />}
      </div>
    </div>
  );
}

function Body({ step }: { step: ReplayStep }) {
  switch (step.kind) {
    case "learner":
      return (
        <p className="rounded-lg border border-line bg-surface px-4 py-3 font-mono text-sm whitespace-pre-wrap break-words">
          {step.text}
        </p>
      );
    case "tutor":
      return (
        <div className="space-y-3 rounded-lg border border-line bg-surface px-4 py-3">
          <Rich text={step.text} />
          {step.proposal && (
            <ol className="space-y-1 rounded-md border border-line bg-surface-2 p-2">
              {step.proposal.map((p, i) => (
                <li key={i} className="flex items-baseline gap-3 px-1 py-0.5 text-sm">
                  <span className="w-4 shrink-0 text-right text-muted tabular-nums">{i + 1}</span>
                  <span className="w-16 shrink-0 font-mono text-xs text-muted">{p.kind}</span>
                  <code className="min-w-0 break-words font-mono">{p.content}</code>
                </li>
              ))}
            </ol>
          )}
          {step.after && <p>{step.after}</p>}
          {step.aside && <p className="border-t border-line pt-3 text-sm text-muted">{step.aside}</p>}
        </div>
      );
    case "read":
      return (
        <div className="space-y-2 rounded-lg bg-idle-soft px-4 py-3 text-sm">
          <ul className="space-y-0.5 font-mono text-[13px] break-words">
            {step.files.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          <p className="text-muted">{step.summary}</p>
        </div>
      );
    case "run":
      return <RunBody step={step} />;
  }
}

function RunBody({ step }: { step: RunStep }) {
  return (
    <div className="space-y-3 rounded-lg bg-idle-soft px-4 py-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <code className="min-w-0 flex-1 font-mono text-[13px] break-words">
          <span aria-hidden className="text-muted">
            ${" "}
          </span>
          {command(step)}
        </code>
        <span className="shrink-0 rounded border border-line bg-surface px-2 py-0.5 text-xs text-muted">
          {TOUCHES[step.touches]}
        </span>
      </div>
      <p className="text-muted">{step.summary}</p>
      {isCheck(step) && <VerdictView output={step.output} />}
      {pageOutputs(step).map((o) => (
        <Output key={o.label} label={o.label} text={o.text} />
      ))}
    </div>
  );
}

function Output({ label, text }: { label: string; text: string }) {
  return (
    <details className="group rounded-md border border-line bg-surface">
      <summary className="flex min-h-11 items-center px-3 text-sm text-ink">{label}</summary>
      <pre className="max-h-80 overflow-auto border-t border-line px-3 py-2 font-mono text-xs whitespace-pre-wrap break-words">
        {text}
      </pre>
    </details>
  );
}

const STATUS: Record<StepVerdict["status"], { word: string; tone: string }> = {
  ok: { word: "Checks out", tone: "text-ok" },
  error: { word: "Flagged", tone: "text-bad" },
  warning: { word: "Warning", tone: "text-warn" },
  unchecked: { word: "Not checked", tone: "text-muted" },
};

const OVERALL: Record<CheckOutput["verdict"]["status"], { word: string; tone: string }> = {
  correct: { word: "Correct", tone: "bg-ok-soft text-ok" },
  incorrect: { word: "Incorrect", tone: "bg-bad-soft text-bad" },
  partial: { word: "Partly right", tone: "bg-warn-soft text-warn" },
  invalid: { word: "Couldn't read it", tone: "bg-idle-soft text-idle" },
};

const PLAIN_OK = "This step checks out.";

/** The checker's verdict, the way ProofLab read each step (typeset with KaTeX). */
function VerdictView({ output }: { output: CheckOutput }) {
  const { verdict } = output;
  const overall = OVERALL[verdict.status];
  const held = verdict.hints.find((h) => h.code === "AUTHORED_HINT");
  return (
    <div className="rounded-lg border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2">
        <p className="font-semibold">ProofLab&apos;s checker</p>
        <p className={`rounded px-2 py-0.5 text-sm font-semibold ${overall.tone}`}>{overall.word}</p>
      </div>
      <ol className="divide-y divide-line">
        {verdict.steps.map((s) => {
          const status = STATUS[s.status];
          const note = s.message && s.message !== PLAIN_OK ? s.message : null;
          return (
            <li key={s.index} className="px-4 py-2">
              <div className="grid grid-cols-[1.25rem_4rem_minmax(0,1fr)] items-baseline gap-2 sm:grid-cols-[1.25rem_4.5rem_minmax(0,1fr)_auto]">
                <span className="text-right text-muted tabular-nums">{s.index + 1}</span>
                <span className="font-mono text-xs text-muted">{s.kind}</span>
                <span className="min-w-0 overflow-x-auto">
                  {s.latex ? <Tex latex={s.latex} /> : <span className="text-muted">none</span>}
                </span>
                <span className={`col-start-3 text-sm font-semibold sm:col-start-auto ${status.tone}`}>
                  {status.word}
                </span>
              </div>
              {note && (
                <p className={`mt-1 text-sm sm:pl-[6.75rem] ${s.status === "error" ? "text-bad" : "text-muted"}`}>
                  <Rich text={note} inline />
                  {s.code && <code className="ml-2 font-mono text-xs">{s.code}</code>}
                </p>
              )}
            </li>
          );
        })}
      </ol>
      {verdict.answer && (
        <p className="border-t border-line px-4 py-2 text-sm">
          <Rich text={verdict.answer.message} inline />
        </p>
      )}
      {held && (
        <p className="border-t border-line px-4 py-2 text-sm text-muted">
          The verdict also carries the first authored hint. The tutor keeps it for when the learner
          asks for help and asks a question first.
        </p>
      )}
      {output.recorded && (
        <p className="border-t border-line px-4 py-2 text-sm text-muted">
          Saved to memory as attempt {output.attempt_id}
          {output.counted === false ? ", not counted (a typing slip)" : ""}. Checked by {output.checked_by}.
        </p>
      )}
    </div>
  );
}

function RuleLinks({ rules }: { rules: number[] }) {
  return (
    <p className="flex flex-wrap gap-x-4 text-sm">
      {rules.map((n) => {
        const rule = RULES.find((r) => r.n === n);
        return (
          <a key={n} href={`#rule-${n}`} className="inline-flex min-h-11 items-center text-accent hover:underline">
            Rule {n}{rule ? `: ${rule.title}` : ""}
          </a>
        );
      })}
    </p>
  );
}
