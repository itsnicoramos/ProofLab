// The home page's /tutor replay must keep the tutor's own rules (SKILL.md), and the page text
// must keep DESIGN.md's (no em or en dashes). Run with `npm test`.
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import {
  command,
  isCheck,
  pageOutputs,
  piecesFor,
  type Replay,
  type ReplayStep,
  type TutorStep,
} from "./replay.ts";
import { RULES } from "./site.ts";

const SRC = join(import.meta.dirname, "..");
const read = (path: string) => readFileSync(join(SRC, path), "utf8");
const replay: Replay = JSON.parse(read("replay/practice-4.json"));
const script = JSON.parse(read("replay/practice-4.script.json"));
const steps = replay.steps;

const lastCheckBefore = (i: number) => {
  for (let j = i - 1; j >= 0; j--) {
    const s = steps[j];
    if (isCheck(s)) return s;
  }
  return null;
};

test("the captured replay matches its script, turn for turn", () => {
  assert.equal(steps.length, script.steps.length);
  steps.forEach((step, i) => {
    assert.equal(step.kind, script.steps[i].kind, `step ${i + 1}`);
    if (step.kind !== "run") assert.deepEqual(step, script.steps[i], `step ${i + 1}`);
  });
});

test("every command ran and printed output", () => {
  for (const step of steps) {
    if (step.kind !== "run") continue;
    assert.equal(step.exit, 0, step.args.join(" "));
    assert.ok(step.output && typeof step.output === "object", step.args.join(" "));
    assert.ok(!step.args.includes("{session}"), "the session id was filled in");
  }
});

test("the tutor says correct only right after the checker said so (rule 1)", () => {
  steps.forEach((step, i) => {
    if (step.kind !== "tutor") return;
    const says = step.text.toLowerCase();
    const check = lastCheckBefore(i);
    if (/\bmarks (it|this) correct\b/.test(says)) {
      assert.equal(check?.output.verdict.status, "correct", `step ${i + 1}`);
    }
    if (/\bmarks (it|this) incorrect\b/.test(says)) {
      assert.equal(check?.output.verdict.status, "incorrect", `step ${i + 1}`);
    }
    if (/\bcorrect\b/.test(says.replace(/\bincorrect\b/g, ""))) {
      assert.match(says, /proofLab's checker marks/i, `step ${i + 1} names who decided`);
    }
  });
});

test("each check grades exactly the steps the learner agreed to (rule 2)", () => {
  steps.forEach((step, i) => {
    if (!isCheck(step)) return;
    const shown = steps
      .slice(0, i)
      .map((s, j) => [s, j] as const)
      .filter((pair): pair is readonly [TutorStep, number] => pair[0].kind === "tutor" && !!pair[0].proposal)
      .at(-1);
    assert.ok(shown, `check at step ${i + 1} has steps shown before it`);
    const [tutor, at] = shown;
    assert.deepEqual(step.stdin, { steps: tutor.proposal, answer: null }, `step ${i + 1}`);
    const between = steps.slice(at + 1, i);
    assert.ok(between.some((s) => s.kind === "learner"), `the learner answered before step ${i + 1}`);
  });
});

test("no solution is shown, because the learner never gave up (rule 3)", () => {
  for (const step of steps) {
    if (step.kind === "run") assert.notEqual(step.args[0], "solution");
  }
});

test("after a wrong verdict the tutor asks before anything else (rules 3 and 4)", () => {
  steps.forEach((step, i) => {
    if (!isCheck(step) || step.output.verdict.status === "correct") return;
    const reply = steps[i + 1];
    assert.equal(reply.kind, "tutor");
    assert.ok((reply as TutorStep).text.trim().endsWith("?"), "ends with a question");
    assert.equal((reply as TutorStep).proposal, undefined, "doesn't rewrite the steps");
  });
});

test("exercise output never carries a solution (rule 5)", () => {
  const keys = (v: unknown): string[] =>
    v && typeof v === "object"
      ? Object.entries(v).flatMap(([k, x]) => [k, ...keys(x)])
      : [];
  for (const step of steps) {
    if (step.kind !== "run" || step.args[0] !== "show") continue;
    for (const k of ["solution", "examples", "answer_key"]) assert.ok(!keys(step.output).includes(k), k);
  }
});

test("each rule links to a step that is tagged with it", () => {
  assert.deepEqual(RULES.map((r) => r.n), [1, 2, 3, 4, 5, 6, 7]);
  for (const rule of RULES) {
    const step: ReplayStep | undefined = steps[rule.step];
    assert.ok(step?.rules?.includes(rule.n), `rule ${rule.n} -> step ${rule.step + 1}`);
  }
});

test("every step lights up at least one piece of the diagram", () => {
  for (const step of steps) assert.ok(piecesFor(step).length > 0);
});

test("no absolute paths from the capture machine reach the page", () => {
  const text = read("replay/practice-4.json");
  assert.doesNotMatch(text, /\/Users\/|\/home\/|C:\\\\/);
});

const files = (dir: string): string[] =>
  readdirSync(join(SRC, dir)).flatMap((name) => {
    const path = join(dir, name);
    return statSync(join(SRC, path)).isDirectory() ? files(path) : [path];
  });

test("page text has no em or en dashes (DESIGN.md)", () => {
  for (const path of files(".").filter((p) => /\.(tsx|ts)$/.test(p))) {
    assert.doesNotMatch(read(path), /[\u2013\u2014]/, path);
  }
  for (const step of script.steps) {
    const words = [step.text, step.summary, step.after, step.aside].filter(Boolean).join(" ");
    assert.doesNotMatch(words, /[\u2013\u2014]/, JSON.stringify(step).slice(0, 60));
  }
  assert.doesNotMatch(`${script.about} ${script.setup_note}`, /[\u2013\u2014]/);
});

// The website names no textbook (decided 2026-11-08): not in its text, and not in anything the
// replay renders. The capture itself keeps the CLI's full output.
const BOOK = /book of proof|hammack|bookofproof|book-of-proof|\bp\. ?\d/i;

test("the page never names the book", () => {
  for (const path of files(".").filter((p) => /\.(tsx|ts)$/.test(p) && !p.endsWith(".test.ts"))) {
    assert.doesNotMatch(read(path), BOOK, path);
  }
  steps.forEach((step, i) => {
    const words =
      step.kind === "run"
        ? [command(step), step.summary, ...pageOutputs(step).flatMap((o) => [o.label, o.text])]
        : step.kind === "read"
          ? [...step.files, step.summary]
          : step.kind === "tutor"
            ? [step.text, step.after ?? "", step.aside ?? "", ...(step.proposal ?? []).map((p) => p.content)]
            : [step.text];
    for (const w of words) assert.doesNotMatch(w, BOOK, `step ${i + 1}`);
    if (isCheck(step)) {
      const v = step.output.verdict;
      const said = [...v.steps.map((s) => s.message), v.answer?.message ?? "", ...v.hints.map((h) => h.message)];
      for (const w of said) assert.doesNotMatch(w, BOOK, `verdict at step ${i + 1}`);
    }
  });
  assert.doesNotMatch(replay.setup_note, BOOK);
});
