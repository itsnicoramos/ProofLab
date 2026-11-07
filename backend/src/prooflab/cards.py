"""Flashcards (SPEC §15): decks built from ProofLab's own content, no AI.

Two sources, both already in the content folder:

- **Concept cards** in ``content/cards/<course>.json``: the book's definitions, notation and
  theorems, restated in ProofLab's words and cited (the same "invent nothing" rule as problems).
- **Problem cards**: every served problem, with its statement on the front and its worked
  solution on the back.

Cards from the student's own notes are made by :mod:`prooflab.notes` and live in their browser.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field, ValidationError, field_validator

from prooflab.engine.models import Citation, Course, Problem, _Strict

if TYPE_CHECKING:
    from prooflab.engine.models import CourseOutline, Reference

CardType = Literal["definition", "notation", "theorem", "fact"]
_CARD_ID = re.compile(r"^[a-z0-9]+\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9-]*$")


class Card(_Strict):
    """One concept card: a term (or a theorem's name) and what it means."""

    id: str
    topic: str
    type: CardType
    front: str = Field(min_length=1, max_length=120)
    back: str = Field(min_length=1, max_length=400)
    reference: Citation

    @field_validator("id")
    @classmethod
    def _id_format(cls, value: str) -> str:
        if not _CARD_ID.fullmatch(value):
            raise ValueError("card id must look like '<course>.<topic>.<slug>'")
        return value


class CardFile(_Strict):
    course: Course
    cards: list[Card]


def load_cards(
    root: Path,
    outline: dict[str, CourseOutline],
    references: dict[str, Reference],
    *,
    only: set[str] | None = None,
) -> tuple[dict[str, list[Card]], list[str]]:
    """Read ``cards/*.json``; returns the cards by course and a list of problems found."""
    out: dict[str, list[Card]] = {}
    errors: list[str] = []
    folder = root / "cards"
    if not folder.is_dir():
        return out, errors
    for path in sorted(folder.glob("*.json")):
        label = f"cards/{path.name}"
        try:
            deck = CardFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValidationError, json.JSONDecodeError) as exc:
            errors.append(f"{label}: {exc}")
            continue
        course = deck.course.value
        if only is not None and course not in only:
            continue
        if path.stem != course:
            errors.append(f"{label}: course {course!r} but the file is named {path.name}")
        topics = outline[course].topics
        seen_ids: set[str] = set()
        fronts: set[tuple[str, str]] = set()
        for card in deck.cards:
            where = f"{label}: {card.id}"
            prefix = f"{course}.{card.topic}."
            if not card.id.startswith(prefix):
                errors.append(f"{where}: id must start with {prefix!r}")
            if card.topic not in topics:
                errors.append(f"{where}: unknown topic {card.topic!r} for {course}")
            if card.id in seen_ids:
                errors.append(f"{where}: duplicate id")
            seen_ids.add(card.id)
            key = (card.topic, card.front.strip().lower())
            if key in fronts:
                errors.append(f"{where}: two cards in {card.topic} share the front {card.front!r}")
            fronts.add(key)
            if card.reference.book not in references:
                errors.append(f"{where}: unknown reference book {card.reference.book!r}")
            if "—" in card.front or "—" in card.back:
                errors.append(f"{where}: use a comma or colon instead of an em dash")
        out.setdefault(course, []).extend(deck.cards)
    return out, errors


# --------------------------------------------------------------------------- decks


DeckPart = Literal["concepts", "problems"]


class DeckCard(_Strict):
    """A card as the API serves it: concept cards and problem cards share this shape."""

    id: str
    course: Course
    topic: str
    type: Literal["definition", "notation", "theorem", "fact", "problem"]
    front: str
    back: list[str]
    title: str | None = None
    difficulty: int | None = None
    citation: str


def concept_card(card: Card, course: Course, book_title: str) -> DeckCard:
    return DeckCard(
        id=card.id,
        course=course,
        topic=card.topic,
        type=card.type,
        front=card.front,
        back=[card.back],
        citation=f"{book_title}, {card.reference.section}",
    )


def problem_card(problem: Problem, book_title: str) -> DeckCard:
    return DeckCard(
        id=problem.id,
        course=problem.course,
        topic=problem.topic,
        type="problem",
        front=problem.prompt,
        back=list(problem.solution),
        title=problem.title,
        difficulty=problem.difficulty,
        citation=f"{book_title}, {problem.reference.section}",
    )


def build_deck(
    cards: dict[str, list[Card]],
    problems: Sequence[Problem],
    book_titles: dict[str, str],
    course: Course,
    *,
    topics: Iterable[str] | None = None,
    parts: Iterable[DeckPart] = ("concepts", "problems"),
    topic_order: Sequence[str] = (),
) -> list[DeckCard]:
    """A course's deck, filtered by topic, in course order (concepts before problems)."""
    wanted = set(topics) if topics else None
    parts = set(parts)
    order = {t: i for i, t in enumerate(topic_order)}
    out: list[DeckCard] = []
    if "concepts" in parts:
        for card in cards.get(course.value, []):
            if wanted is None or card.topic in wanted:
                title = book_titles.get(card.reference.book, card.reference.book)
                out.append(concept_card(card, course, title))
    if "problems" in parts:
        for p in problems:
            if p.course is course and (wanted is None or p.topic in wanted):
                out.append(problem_card(p, book_titles.get(p.reference.book, p.reference.book)))
    # Stable sort keeps concepts ahead of problems inside each topic.
    return sorted(out, key=lambda c: order.get(c.topic, len(order)))
