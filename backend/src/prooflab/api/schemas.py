"""HTTP request/response shapes (SPEC §7). Answer keys never appear in these models."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from prooflab.engine.models import Course, ReviewStatus, Step


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Health(_Out):
    status: str
    version: str
    problems: int


class TopicSummary(_Out):
    topic: str
    problems: int


class CourseSummary(_Out):
    id: Course
    title: str
    problems: int
    topics: list[TopicSummary]


class ProblemSummary(_Out):
    id: str
    course: Course
    topic: str
    kind: str
    title: str
    prompt: str
    difficulty: int
    tags: list[str]
    review_status: ReviewStatus
    variant_of: str | None = None  # set on ProofLab-made versions (not from the book)


class CitationOut(_Out):
    book_id: str
    title: str
    authors: list[str]
    edition: str | None
    section: str
    note: str | None
    url: str
    license: str
    license_url: str | None


class ReviewOut(_Out):
    status: ReviewStatus
    reviewed_on: date | None


class ProblemDetail(ProblemSummary):
    answer_format: str
    syntax_help: str
    step_kinds: list[str]
    has_answer: bool
    reference: CitationOut
    review: ReviewOut
    hint_count: int


class SolutionOut(_Out):
    problem_id: str
    answer: str
    solution: list[str]


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_id: str = Field(max_length=120)
    steps: list[Step] = Field(default_factory=list, max_length=40)
    answer: str | None = Field(default=None, max_length=500)
    hints_revealed: int = Field(default=0, ge=0, le=20)


class ChoiceOptionOut(_Out):
    key: str
    latex: str | None
    text: str | None


class SpotStepOut(_Out):
    kind: str
    content: str
    latex: str | None


class ChoiceOut(_Out):
    """A multiple-choice question (SPEC §13.2). The right key is not included."""

    format: str  # "answer" or "spot"
    seed: int
    stem: str
    choices: list[ChoiceOptionOut]
    steps: list[SpotStepOut] = Field(default_factory=list)
    attempt_answer: str | None = None


class QuestionOut(_Out):
    problem: ProblemSummary
    format: str  # "written" or "choice"
    choice: ChoiceOut | None = None


class PracticeTestOut(_Out):
    """A practice midterm, final or quiz assembled from existing problems (SPEC §13)."""

    id: str
    course: Course
    kind: str
    title: str
    seed: int
    topics: list[str]
    style: str
    variants: bool
    suggested_minutes: int
    minutes_rule: str
    problems: list[ProblemSummary]
    questions: list[QuestionOut]


class ChoiceAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_id: str = Field(max_length=160)
    seed: int = Field(ge=0, le=2**31 - 1)
    format: str = Field(pattern="^(answer|spot)$")
    choice: str = Field(pattern="^[a-e]$")


class ChoiceAnswerOut(_Out):
    problem_id: str
    correct: bool
    choice: str
    correct_choice: str
    explanation: str | None
    solution: list[str]


class DeckCardOut(_Out):
    id: str
    course: Course
    topic: str
    type: str
    front: str
    back: list[str]
    title: str | None
    difficulty: int | None
    citation: str


class NotesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=200_000)


class NoteCardOut(_Out):
    front: str
    back: str
    type: str
    rule: str
    rule_label: str
    line: int


class NotesOut(_Out):
    cards: list[NoteCardOut]
    lines: int


class ReadLineOut(_Out):
    text: str
    confidence: float | None
    page: int


class ReadOut(_Out):
    """A photo, PDF or document turned into lines of text (SPEC §14). Transcription only."""

    kind: str
    engine: str
    pages: int
    lines: list[ReadLineOut]
    text: str


class ReaderCapabilities(_Out):
    images: bool
    pdf: bool
    documents: bool
    text: bool
