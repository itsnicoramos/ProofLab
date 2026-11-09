"""Validated inputs for the tutor memory. Everything an agent sends goes through these."""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Chapter = Annotated[int, Field(ge=1, le=14)]
ChapterStatus = Literal["skip", "review", "do", "done"]
Mode = Literal["start", "level", "learn", "practice", "quiz", "guide"]
NoteKind = Literal["struggle", "misconception", "preference", "goal"]
QuizKind = Literal["placement", "chapter", "quiz", "midterm", "final"]
ItemId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{0,119}$")]
LearnerName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")]

MAX_PLACEMENT_BYTES = 5000


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanIn(_Strict):
    """``memory plan set``: the study plan (fields left out keep their current value)."""

    mission: Annotated[str, StringConstraints(min_length=1, max_length=2000)] | None = None
    goal: Annotated[str, StringConstraints(max_length=500)] | None = None
    pace: Annotated[str, StringConstraints(max_length=200)] | None = None
    exam_date: date | None = None
    entry_chapter: Chapter | None = None
    placement: dict[str, Any] | None = None
    chapters: dict[Chapter, ChapterStatus] | None = None

    @field_validator("placement")
    @classmethod
    def _small(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and len(json.dumps(value)) > MAX_PLACEMENT_BYTES:
            raise ValueError(f"placement is larger than {MAX_PLACEMENT_BYTES} bytes")
        return value


class NoteIn(_Strict):
    kind: NoteKind
    text: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    chapter: Chapter | None = None


class ReviewIn(_Strict):
    chapter: Chapter
    idea: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    problem_ids: list[ItemId] = Field(default_factory=list, max_length=20)


class QuizIn(_Strict):
    kind: QuizKind
    chapters: list[Chapter] = Field(default_factory=list, max_length=14)
    seed: Annotated[int, Field(ge=0, le=2**31 - 1)]
    total: Annotated[int, Field(ge=1, le=60)]
    session_id: int | None = None
