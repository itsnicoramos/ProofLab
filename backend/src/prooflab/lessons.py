"""Lesson notes for the repo tutor (SPEC §20): one original Markdown note per chapter.

A note is ``content/lessons/<course>/chNN-<topic>.md``: a small frontmatter block (one
``key: value`` per line, list values as one-line JSON arrays) followed by a fixed set of
``##`` sections. The notes are ProofLab's own words; they cite *Book of Proof* sections and
never reproduce its text.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from prooflab.content import CONTENT_DIR

LESSONS_DIR = CONTENT_DIR / "lessons"

SECTIONS = (
    "Why it matters",
    "Core ideas",
    "Worked example",
    "Typing it into ProofLab",
    "Common mistakes",
    "Pause questions",
    "Practice route",
)
CHECKABLE = ("yes", "partly", "no")
REVIEW = ("draft", "reviewed")
_FIELDS = (
    "chapter",
    "title",
    "topic",
    "book",
    "sections",
    "prerequisites",
    "minutes",
    "checkable",
    "review",
)


class LessonError(ValueError):
    """A lesson note that doesn't follow the format."""


@dataclass(frozen=True)
class Lesson:
    chapter: int
    title: str
    topic: str
    book: str
    sections: list[str]
    prerequisites: list[int]
    minutes: int
    checkable: str
    review: str
    path: Path
    body: str
    parts: dict[str, str] = field(default_factory=dict)  # "## heading" -> its text

    def summary(self) -> dict[str, object]:
        return {
            "chapter": self.chapter,
            "title": self.title,
            "topic": self.topic,
            "sections": self.sections,
            "prerequisites": self.prerequisites,
            "minutes": self.minutes,
            "checkable": self.checkable,
            "review": self.review,
            "path": self.repo_path,
        }

    @property
    def repo_path(self) -> str:
        """The note's path from the repository root, for showing to learners."""
        parts = self.path.parts
        return "/".join(parts[parts.index("backend") :]) if "backend" in parts else str(self.path)


def _value(raw: str) -> object:
    raw = raw.strip()
    if raw[:1] in '["' or re.fullmatch(r"-?\d+", raw):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LessonError(f"bad value {raw!r}: {exc}") from None
    return raw


def parse_lesson(path: Path) -> Lesson:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise LessonError(f"{path.name}: must start with a --- frontmatter block")
    head, sep, body = text[4:].partition("\n---\n")
    if not sep:
        raise LessonError(f"{path.name}: the frontmatter block is never closed with ---")
    meta: dict[str, object] = {}
    for line in head.splitlines():
        if not line.strip():
            continue
        key, colon, raw = line.partition(":")
        if not colon:
            raise LessonError(f"{path.name}: frontmatter line {line!r} isn't key: value")
        try:
            meta[key.strip()] = _value(raw)
        except LessonError as exc:
            raise LessonError(f"{path.name}: {key.strip()}: {exc}") from None
    missing = [k for k in _FIELDS if k not in meta]
    if missing:
        raise LessonError(f"{path.name}: frontmatter is missing {', '.join(missing)}")
    parts: dict[str, str] = {}
    current = None
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            parts[current] = ""
        elif current is not None:
            parts[current] += line + "\n"
    try:
        lesson = Lesson(
            chapter=int(meta["chapter"]),  # type: ignore[arg-type]
            title=str(meta["title"]),
            topic=str(meta["topic"]),
            book=str(meta["book"]),
            sections=[str(s) for s in meta["sections"]],  # type: ignore[union-attr]
            prerequisites=[int(c) for c in meta["prerequisites"]],  # type: ignore[union-attr]
            minutes=int(meta["minutes"]),  # type: ignore[arg-type]
            checkable=str(meta["checkable"]),
            review=str(meta["review"]),
            path=path,
            body=body.strip() + "\n",
            parts={k: v.strip() for k, v in parts.items()},
        )
    except (TypeError, ValueError) as exc:
        raise LessonError(f"{path.name}: {exc}") from None
    if lesson.checkable not in CHECKABLE:
        raise LessonError(f"{path.name}: checkable must be one of {', '.join(CHECKABLE)}")
    if lesson.review not in REVIEW:
        raise LessonError(f"{path.name}: review must be one of {', '.join(REVIEW)}")
    return lesson


def load_lessons(course: str = "proofs", root: Path = LESSONS_DIR) -> dict[int, Lesson]:
    """The course's notes by chapter number (missing chapters are simply absent)."""
    folder = root / course
    if not folder.is_dir():
        return {}
    out: dict[int, Lesson] = {}
    for path in sorted(folder.glob("ch*.md")):
        lesson = parse_lesson(path)
        if lesson.chapter in out:
            raise LessonError(f"{path.name}: chapter {lesson.chapter} has two notes")
        out[lesson.chapter] = lesson
    return out
