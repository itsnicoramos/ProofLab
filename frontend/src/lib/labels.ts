// Human-readable names for the backend's ids. Unknown ids fall back to a tidied version.

import type { CourseId, StepStatus, VerdictStatus } from "./types";

export const COURSE_ORDER: CourseId[] = ["proofs", "precalc", "calc1", "calc2", "calc3", "calc4"];

export const COURSE_SHORT: Record<CourseId, string> = {
  proofs: "Proof",
  precalc: "Precalculus",
  calc1: "Calculus 1",
  calc2: "Calculus 2",
  calc3: "Calculus 3",
  calc4: "Calculus 4",
};

/** Compact names for the navbar, where every course must fit. */
export const COURSE_NAV: Record<CourseId, string> = {
  proofs: "Proof",
  precalc: "Precalc",
  calc1: "Calc 1",
  calc2: "Calc 2",
  calc3: "Calc 3",
  calc4: "Calc 4",
};

/** MATH 123 topics are Book of Proof chapters, named and numbered as in the book. */
const BOOK_CHAPTERS: Record<string, [number, string]> = {
  sets: [1, "Sets"],
  logic: [2, "Logic"],
  counting: [3, "Counting"],
  direct: [4, "Direct proof"],
  contrapositive: [5, "Contrapositive proof"],
  contradiction: [6, "Proof by contradiction"],
  nonconditional: [7, "Proving non-conditional statements"],
  "set-proofs": [8, "Proofs involving sets"],
  disproof: [9, "Disproof"],
  induction: [10, "Mathematical induction"],
  relations: [11, "Relations"],
  functions: [12, "Functions"],
  "calculus-proofs": [13, "Proofs in calculus"],
  cardinality: [14, "Cardinality of sets"],
};

/**
 * Book of Proof section titles (from the book's table of contents) for chapters whose exercises
 * are numbered by section. Problem titles start "Ex 1.4 #8", so the section can be named.
 */
const BOOK_SECTIONS: Record<string, string> = {
  "1.1": "Introduction to sets",
  "1.2": "The Cartesian product",
  "1.3": "Subsets",
  "1.4": "Power sets",
  "1.5": "Union, intersection, difference",
  "1.6": "Complement",
  "1.7": "Venn diagrams",
  "1.8": "Indexed sets",
  "1.9": "Sets that are number systems",
  "1.10": "Russell's paradox",
};

/** "Ex 1.4 #8 · …" gives "1.4 Power sets"; null for titles without a known section. */
export function bookSection(title: string): string | null {
  const n = /^Ex (\d+\.\d+) #/.exec(title)?.[1];
  return n && BOOK_SECTIONS[n] ? `${n} ${BOOK_SECTIONS[n]}` : null;
}

const TOPICS: Record<string, string> = {
  parity: "Parity",
  divisibility: "Divisibility",
  functions: "Functions",
  trig: "Trigonometry",
  exp_log: "Exponentials & logarithms",
  limits: "Limits",
  derivatives: "Derivatives",
  integrals: "Integrals",
  series: "Series",
  partials: "Partial derivatives",
  multiple_integrals: "Multiple integrals",
  vector_calc: "Vector calculus",
  diff_eq: "Differential equations",
};

const KINDS: Record<string, string> = {
  parity_proof: "Parity proof",
  divisibility_proof: "Divisibility proof",
  counterexample: "Counterexample",
  finite_set: "Sets",
  truth_table: "Truth table",
  logical_equivalence: "Logical equivalence",
  count: "Counting",
  impossibility_proof: "Proof by contradiction",
  existence: "Existence proof",
  set_identity: "Set equality proof",
  induction: "Induction proof",
  expression: "Simplify or evaluate",
  inverse_function: "Inverse function",
  domain: "Domain",
  trig_identity: "Prove an identity",
  trig_equation: "Trig equation",
  log_rewrite: "Log rules",
  equation: "Solve an equation",
  limit: "Limit",
  derivative: "Derivative",
  tangent_line: "Tangent line",
  implicit_derivative: "Implicit differentiation",
  antiderivative: "Antiderivative",
  definite_integral: "Definite integral",
  series_convergence: "Convergence",
  series_sum: "Sum of a series",
  taylor_polynomial: "Taylor polynomial",
  partial_derivative: "Partial derivative",
  gradient: "Gradient",
  directional_derivative: "Directional derivative",
  tangent_plane: "Tangent plane",
  iterated_integral: "Iterated integral",
  integral_setup: "Set up an integral",
  divergence: "Divergence",
  curl: "Curl",
  potential_function: "Potential function",
  line_integral: "Line integral",
  ode_solution: "Differential equation",
};

function tidy(id: string): string {
  const words = id.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function topicLabel(topic: string, course?: string): string {
  const chapter = course === "proofs" ? BOOK_CHAPTERS[topic] : undefined;
  if (chapter) return `Chapter ${chapter[0]}: ${chapter[1]}`;
  return TOPICS[topic] ?? tidy(topic);
}

/** The course a problem id belongs to (ids look like "calc1.limits.factor-cancel"). */
export function courseOfProblemId(id: string): CourseId | null {
  const course = id.split(".")[0];
  return isCourseId(course) ? course : null;
}
export const kindLabel = (kind: string) => KINDS[kind] ?? tidy(kind);

export const isCourseId = (value: string): value is CourseId =>
  (COURSE_ORDER as string[]).includes(value);

// Step kinds: label shown in the picker, and an example placeholder.
const STEP_KINDS: Record<string, { label: string; placeholder: string }> = {
  expr: { label: "Step", placeholder: "e.g. 2x sin(x) + x^2 cos(x)" },
  lhopital: { label: "L'Hôpital", placeholder: "f′/g′, e.g. sin(x)/(2x)" },
  let: { label: "Let", placeholder: "e.g. n = 2k + 1" },
  case: { label: "Case", placeholder: "e.g. n = 3k + 1" },
  witness: { label: "Witness", placeholder: "e.g. 2k^2 + 2k" },
  form: { label: "Form", placeholder: "e.g. 4(k^2 - b) + 2" },
  base: { label: "Base case", placeholder: "e.g. 1 = 1(1 + 1)/2" },
  assume: { label: "Assume", placeholder: "e.g. 1 + 2 + ... + k = k(k + 1)/2" },
  column: { label: "Column", placeholder: "e.g. ~P ∨ Q : T F T T" },
  row: { label: "Row", placeholder: "e.g. P = T, Q = F" },
  note: { label: "Note", placeholder: "Words for yourself (not checked)" },
  sub: { label: "Substitute", placeholder: "e.g. u = x^2 + 1" },
  test: { label: "Test", placeholder: "e.g. ratio, root, comparison, p-series" },
  limit: { label: "Test limit", placeholder: "e.g. 1/2" },
  compare: { label: "Compare with", placeholder: "e.g. 1/n^2" },
  characteristic: { label: "Characteristic eq.", placeholder: "e.g. r^2 - 3r + 2 = 0" },
  roots: { label: "Roots", placeholder: "e.g. r = 1, 2" },
};

export const stepKindLabel = (kind: string) => STEP_KINDS[kind]?.label ?? tidy(kind);
/** Example text for a plain "Step" line, by problem kind (the generic one is calculus). */
const EXPR_PLACEHOLDER: Record<string, string> = {
  parity_proof: "e.g. 4k^2 + 4k + 1",
  divisibility_proof: "e.g. a(jk)",
  impossibility_proof: "e.g. 4k^2 - 4b - 2",
  counterexample: "Working for yourself (not checked)",
  existence: "Working for yourself (not checked)",
  finite_set: "e.g. {1, 2, 3}",
  truth_table: "e.g. ~P ∨ Q",
  logical_equivalence: "e.g. ~P ∨ Q",
  count: "e.g. 26^4 or binom(10, 3)",
  set_identity: "e.g. x ∈ A or (x ∈ B and x ∈ C)",
  induction: "e.g. k(k + 1)/2 + (k + 1)",
};

export const stepPlaceholder = (kind: string, problemKind?: string) =>
  (kind === "expr" && problemKind ? EXPR_PLACEHOLDER[problemKind] : undefined) ??
  STEP_KINDS[kind]?.placeholder ??
  "";

const PROOF_KINDS = new Set([
  "parity_proof",
  "divisibility_proof",
  "impossibility_proof",
  "set_identity",
  "induction",
]);

/** Kinds whose verdict comes from the steps alone (no final-answer box). */
export const usesAnswer = (kind: string) => !PROOF_KINDS.has(kind) && kind !== "trig_identity";

export const isProofKind = (kind: string) => PROOF_KINDS.has(kind);

/** The step kind a brand-new attempt starts with. */
export function firstStepKind(problemKind: string, stepKinds: string[]): string {
  if (stepKinds.includes("base")) return "base";
  if (stepKinds.includes("let")) return "let";
  if (problemKind === "series_convergence" && stepKinds.includes("test")) return "test";
  return stepKinds.includes("expr") ? "expr" : (stepKinds[0] ?? "expr");
}

export const VERDICT_LABEL: Record<VerdictStatus, string> = {
  correct: "Correct",
  partial: "Partly there",
  incorrect: "Not yet",
  invalid: "Couldn't check that",
};

export const STEP_STATUS_LABEL: Record<StepStatus, string> = {
  ok: "Checks out",
  warning: "Careful",
  error: "Problem here",
  unchecked: "Not checked",
};
