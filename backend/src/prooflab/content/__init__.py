"""Load and validate problem content (SPEC §4, §8).

``content/references.json`` is the book registry; ``content/courses.json`` is the course outline
(each course's topics, in display order); ``content/problems/<course>/**/*.json`` holds one problem
per file, and ``content/cards/<course>.json`` holds concept flashcards (SPEC §15). Loading
validates everything and raises :class:`ContentLoadError` listing every problem found, so a bad
file stops the server from starting.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from prooflab.cards import Card, load_cards
from prooflab.engine.checker import ContentError, get_handler, handlers
from prooflab.engine.models import Course, CourseOutline, Problem, Reference

CONTENT_DIR = Path(__file__).resolve().parent
COURSE_ORDER = [c.value for c in Course]
RETIRED_FOLDER = "retired"  # problems/<course>/retired/ keeps retired problems (any topic)


class ContentLoadError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("invalid content:\n  " + "\n  ".join(errors))
        self.errors = errors


def load_outline(root: Path = CONTENT_DIR) -> dict[str, CourseOutline]:
    """``courses.json``: one outline per course, keyed by course id."""
    raw = json.loads((root / "courses.json").read_text(encoding="utf-8"))
    try:
        outlines = [CourseOutline.model_validate(item) for item in raw["courses"]]
    except ValidationError as exc:
        raise ContentLoadError([f"courses.json: {exc}"]) from exc
    out: dict[str, CourseOutline] = {}
    for outline in outlines:
        if outline.id.value in out:
            raise ContentLoadError([f"courses.json: course {outline.id.value!r} listed twice"])
        out[outline.id.value] = outline
    missing = [c for c in COURSE_ORDER if c not in out]
    if missing:
        raise ContentLoadError([f"courses.json: no outline for {missing}"])
    return out


@lru_cache(maxsize=1)
def course_topics() -> dict[str, list[str]]:
    """Each course's (active) topics, in display order."""
    return {course: list(o.topics) for course, o in load_outline().items()}


@dataclass
class Registry:
    references: dict[str, Reference]
    problems: dict[str, Problem]
    sources: dict[str, Path] = field(default_factory=dict)
    topics: dict[str, list[str]] = field(default_factory=course_topics)
    cards: dict[str, list[Card]] = field(default_factory=dict)

    def _topic_index(self, p: Problem) -> int:
        order = self.topics.get(p.course.value, [])
        return order.index(p.topic) if p.topic in order else len(order)

    def served(self) -> list[Problem]:
        """Problems the API serves (not retired), in course/topic/id order."""

        def key(p: Problem) -> tuple[object, ...]:
            # Book-mapped problems (ids like ch4-ex01) follow the book's order; others go by
            # difficulty.
            in_book_order = "book-of-proof" in p.tags
            return (
                COURSE_ORDER.index(p.course.value),
                self._topic_index(p),
                0 if in_book_order else 1,
                p.id if in_book_order else "",
                p.difficulty,
                p.id,
            )

        return sorted((p for p in self.problems.values() if p.served), key=key)

    def get(self, problem_id: str) -> Problem | None:
        problem = self.problems.get(problem_id)
        return problem if problem is not None and problem.served else None


def load_references(root: Path = CONTENT_DIR) -> dict[str, Reference]:
    raw = json.loads((root / "references.json").read_text(encoding="utf-8"))
    refs = [Reference.model_validate(item) for item in raw["books"]]
    out: dict[str, Reference] = {}
    for ref in refs:
        if ref.id in out:
            raise ContentLoadError([f"references.json: duplicate book id {ref.id!r}"])
        out[ref.id] = ref
    return out


def load_registry(root: Path = CONTENT_DIR, *, courses: Iterable[str] | None = None) -> Registry:
    """Load and validate content. ``courses`` limits loading to some course folders (tests)."""
    only = set(courses) if courses is not None else None
    errors: list[str] = []
    references = load_references(root)
    outline = load_outline(root)
    kinds = handlers()
    problems: dict[str, Problem] = {}
    sources: dict[str, Path] = {}
    problems_dir = root / "problems"

    for path in sorted(problems_dir.rglob("*.json")):
        rel = path.relative_to(problems_dir)
        if only is not None and rel.parts[0] not in only:
            continue
        label = str(rel)
        try:
            problem = Problem.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as exc:
            errors.append(f"{label}: {exc}")
            continue
        folder = rel.parts[0]
        if folder != problem.course.value:
            errors.append(f"{label}: course {problem.course.value!r} but file is under {folder}/")
        if len(rel.parts) > 2:
            subfolder = rel.parts[1]
            if subfolder == RETIRED_FOLDER:
                if problem.served:
                    errors.append(f"{label}: only retired problems belong in {subfolder}/")
            elif subfolder != problem.topic:
                errors.append(f"{label}: topic {problem.topic!r} but file is under {subfolder}/")
        course_outline = outline[problem.course.value]
        if problem.topic not in course_outline.topics:
            retired_topic = problem.topic in course_outline.retired_topics
            if not retired_topic:
                errors.append(
                    f"{label}: unknown topic {problem.topic!r} for {problem.course.value}"
                )
            elif problem.served:
                errors.append(
                    f"{label}: topic {problem.topic!r} is retired; only retired problems may use it"
                )
        if problem.id in problems:
            errors.append(f"{label}: duplicate id {problem.id!r} (also {sources[problem.id]})")
        if problem.reference.book not in references:
            errors.append(f"{label}: unknown reference book {problem.reference.book!r}")
        if problem.kind not in kinds:
            errors.append(f"{label}: unknown kind {problem.kind!r}")
        else:
            handler = get_handler(problem.kind)
            try:
                params = handler.params(problem)
                handler.validate(problem, params)
            except ContentError as exc:
                errors.append(f"{label}: {exc}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{label}: answer key/data failed to load: {exc!r}")
            bad_steps = {
                s.kind
                for e in problem.examples
                for s in e.submission.steps
                if s.kind not in handler.step_kinds
            }
            if bad_steps:
                errors.append(f"{label}: examples use step kinds {sorted(bad_steps)}")
        problems[problem.id] = problem
        sources[problem.id] = path

    cards, card_errors = load_cards(root, outline, references, only=only)
    errors.extend(card_errors)
    if errors:
        raise ContentLoadError(errors)
    topics = {course: list(o.topics) for course, o in outline.items()}
    return Registry(
        references=references, problems=problems, sources=sources, topics=topics, cards=cards
    )


@lru_cache(maxsize=1)
def get_registry() -> Registry:
    return load_registry()
