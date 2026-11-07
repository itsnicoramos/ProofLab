// Shapes returned by the ProofLab backend (see SPEC.md §4.1 and §7).

export type CourseId = "proofs" | "precalc" | "calc1" | "calc2" | "calc3" | "calc4";
export type ReviewStatus = "draft" | "reviewed" | "retired";
export type VerdictStatus = "correct" | "partial" | "incorrect" | "invalid";
export type StepStatus = "ok" | "warning" | "error" | "unchecked";

export interface TopicSummary {
  topic: string;
  problems: number;
}

export interface CourseSummary {
  id: CourseId;
  title: string;
  problems: number;
  topics: TopicSummary[];
}

export interface ProblemSummary {
  id: string;
  course: CourseId;
  topic: string;
  kind: string;
  title: string;
  prompt: string;
  difficulty: number;
  tags: string[];
  review_status: ReviewStatus;
  /** Set on ProofLab-made versions with new numbers: the book problem it's based on. */
  variant_of?: string | null;
}

export interface Citation {
  book_id: string;
  title: string;
  authors: string[];
  edition: string | null;
  section: string;
  note: string | null;
  url: string;
  license: string;
  license_url: string | null;
}

export interface ProblemDetail extends ProblemSummary {
  answer_format: string;
  syntax_help: string;
  step_kinds: string[];
  reference: Citation;
  review: { status: ReviewStatus; reviewed_on: string | null };
  hint_count: number;
}

export interface Solution {
  problem_id: string;
  answer: string;
  solution: string[];
}

export interface StepResult {
  index: number;
  kind: string;
  status: StepStatus;
  message: string;
  latex: string | null;
  code: string | null;
}

export interface AnswerResult {
  status: VerdictStatus;
  message: string;
  latex: string | null;
  code: string | null;
}

export interface Feedback {
  code: string;
  message: string;
  step: number | null;
}

export interface Verdict {
  problem_id: string;
  status: VerdictStatus;
  score: number;
  steps: StepResult[];
  answer: AnswerResult | null;
  hints: Feedback[];
}

export interface StepInput {
  kind: string;
  content: string;
}

export interface CheckInput {
  problemId: string;
  steps: StepInput[];
  answer: string | null;
  hintsRevealed: number;
}

export type TestKind = "midterm" | "final" | "quiz";
export type TestStyle = "written" | "mixed" | "choice";

export interface ChoiceOption {
  key: string;
  latex: string | null;
  text: string | null;
}

/** A multiple-choice question (SPEC.md §13.2). The right key stays on the server. */
export interface ChoiceQuestion {
  format: "answer" | "spot";
  seed: number;
  stem: string;
  choices: ChoiceOption[];
  steps: { kind: string; content: string; latex: string | null }[];
  attempt_answer: string | null;
}

export interface TestQuestion {
  problem: ProblemSummary;
  format: "written" | "choice";
  choice: ChoiceQuestion | null;
}

/** A practice midterm, final or quiz assembled by the backend (SPEC.md §13). */
export interface PracticeTest {
  id: string;
  course: CourseId;
  kind: TestKind;
  title: string;
  seed: number;
  topics: string[];
  style: TestStyle;
  variants: boolean;
  suggested_minutes: number;
  minutes_rule: string;
  problems: ProblemSummary[];
  questions: TestQuestion[];
}

export interface ChoiceGrade {
  problem_id: string;
  correct: boolean;
  choice: string;
  correct_choice: string;
  explanation: string | null;
  solution: string[];
}

/** A flashcard from the backend: a cited concept, or a problem with its worked solution. */
export interface DeckCard {
  id: string;
  course: CourseId;
  topic: string;
  type: "definition" | "notation" | "theorem" | "fact" | "problem";
  front: string;
  back: string[];
  title: string | null;
  difficulty: number | null;
  citation: string;
}

/** A card the notes rules found, before the student edits and saves it. */
export interface NoteCardDraft {
  front: string;
  back: string;
  type: string;
  rule: string;
  rule_label: string;
  line: number;
}
