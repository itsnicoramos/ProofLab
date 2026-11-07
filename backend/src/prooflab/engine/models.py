"""Core data model (SPEC §4): problems, submissions, verdicts, references, reviews."""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Course(StrEnum):
    PROOFS = "proofs"
    PRECALC = "precalc"
    CALC1 = "calc1"
    CALC2 = "calc2"
    CALC3 = "calc3"
    CALC4 = "calc4"


COURSE_TITLES: dict[Course, str] = {
    Course.PROOFS: "Proof",
    Course.PRECALC: "Precalculus",
    Course.CALC1: "Calculus 1: Limits & Derivatives",
    Course.CALC2: "Calculus 2: Integrals & Series",
    Course.CALC3: "Calculus 3: Multivariable Calculus",
    Course.CALC4: "Calculus 4: Vector Calculus & Differential Equations",
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- references


class Reference(_Strict):
    """A book in ``content/references.json``."""

    id: str
    title: str
    authors: list[str]
    edition: str | None = None
    publisher: str | None = None
    year: int | None = None
    url: str
    license: str
    license_url: str | None = None


_TOPIC_RE = r"^[a-z0-9][a-z0-9_-]*$"


class CourseOutline(_Strict):
    """One course in ``content/courses.json``: its content topics, in display order.

    Topics are content groupings (for MATH 123, the book's chapters). They are independent of
    the engine modules that implement problem kinds: one module can serve several topics.
    """

    id: Course
    note: str | None = None
    topics: list[str] = Field(min_length=1)
    retired_topics: list[str] = Field(default_factory=list)

    @field_validator("topics", "retired_topics")
    @classmethod
    def _topic_names(cls, value: list[str]) -> list[str]:
        for topic in value:
            if not re.fullmatch(_TOPIC_RE, topic):
                raise ValueError(f"bad topic name {topic!r}")
        if len(set(value)) != len(value):
            raise ValueError("topics must be unique")
        return value

    @model_validator(mode="after")
    def _retired_are_separate(self) -> CourseOutline:
        both = set(self.topics) & set(self.retired_topics)
        if both:
            raise ValueError(f"topics both active and retired: {sorted(both)}")
        return self


class Citation(_Strict):
    """Where a problem comes from (proofs course) or where its topic is taught (SPEC §4.4)."""

    book: str
    section: str
    note: str | None = None


# --------------------------------------------------------------------------- review


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    RETIRED = "retired"


class Review(_Strict):
    status: ReviewStatus
    reviewer: str | None = None
    reviewed_on: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _reviewed_needs_reviewer(self) -> Review:
        if self.status is ReviewStatus.REVIEWED and not (self.reviewer and self.reviewed_on):
            raise ValueError("a reviewed problem needs 'reviewer' and 'reviewed_on'")
        return self


# --------------------------------------------------------------------------- submissions


class Step(_Strict):
    kind: str = Field(default="expr", pattern=r"^[a-z_]{1,20}$")
    content: str = Field(max_length=500)


class Submission(_Strict):
    steps: list[Step] = Field(default_factory=list, max_length=40)
    answer: str | None = Field(default=None, max_length=500)


# --------------------------------------------------------------------------- verdicts


class VerdictStatus(StrEnum):
    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"
    INVALID = "invalid"


class StepStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    UNCHECKED = "unchecked"


class Feedback(_Strict):
    code: str
    message: str
    step: int | None = None


class StepResult(_Strict):
    index: int
    kind: str
    status: StepStatus
    message: str
    latex: str | None = None
    code: str | None = None


class AnswerResult(_Strict):
    status: VerdictStatus
    message: str
    latex: str | None = None
    code: str | None = None


class Verdict(_Strict):
    problem_id: str
    status: VerdictStatus
    score: float
    steps: list[StepResult] = Field(default_factory=list)
    answer: AnswerResult | None = None
    hints: list[Feedback] = Field(default_factory=list)


SCORES = {VerdictStatus.CORRECT: 1.0, VerdictStatus.PARTIAL: 0.5}


# --------------------------------------------------------------------------- problems


class Mistake(_Strict):
    answer: str
    hint: str


class Expectation(_Strict):
    status: VerdictStatus
    first_error: int | None = None
    hint_codes: list[str] = Field(default_factory=list)


class Example(_Strict):
    name: str
    submission: Submission
    expect: Expectation


_ID_RE = re.compile(r"^[a-z0-9]+\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9-]*$")


class Problem(_Strict):
    id: str
    course: Course
    topic: str
    kind: str
    title: str
    prompt: str
    answer_format: str
    difficulty: int = Field(ge=1, le=3)
    tags: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    answer: str = ""
    mistakes: list[Mistake] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)
    solution: list[str] = Field(min_length=1)
    reference: Citation
    review: Review
    examples: list[Example] = Field(min_length=2)

    @field_validator("id")
    @classmethod
    def _id_format(cls, value: str) -> str:
        if not _ID_RE.fullmatch(value):
            raise ValueError("id must look like '<course>.<topic>.<slug>'")
        return value

    @model_validator(mode="after")
    def _id_matches_course_topic(self) -> Problem:
        course, topic, _ = self.id.split(".", 2)
        if course != self.course.value or topic != self.topic:
            raise ValueError(f"id {self.id!r} must start with '{self.course.value}.{self.topic}.'")
        statuses = {e.expect.status for e in self.examples}
        if VerdictStatus.CORRECT not in statuses:
            raise ValueError("needs at least one example that is 'correct'")
        if statuses == {VerdictStatus.CORRECT}:
            raise ValueError("needs at least one example that is not 'correct'")
        return self

    @property
    def served(self) -> bool:
        return self.review.status is not ReviewStatus.RETIRED
