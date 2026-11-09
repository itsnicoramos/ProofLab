"""Course packs: what the repo tutor needs to know about one course (SPEC §22).

A pack is ``content/packs/<id>.json``. It names the course the way a learner does ("MATH 123"),
the ProofLab content track it draws on (that track's problems, concept cards and lesson notes),
its textbook, and its placement areas. The tutor's rules, tools and memory are the same for
every pack; only this data changes, so adding a course is adding a file.

A pack with no track is an empty slot. The tutor can still plan, coach from the learner's own
course materials and remember, but nothing in that course gets a verdict yet.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from prooflab.content import CONTENT_DIR, course_topics, load_references
from prooflab.engine.models import Course

PACKS_DIR = CONTENT_DIR / "packs"
DEFAULT_PACK = "math123"
COURSE_ENV = "PROOFLAB_TUTOR_COURSE"

Line = Annotated[str, StringConstraints(min_length=1, max_length=120)]


class PackError(ValueError):
    """A pack file that doesn't hold together, or a course name no pack answers to."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlacementArea(_Strict):
    """One area of the placement quiz, and the track topics its questions come from (one
    question per entry, so a topic listed twice gives two)."""

    area: Line
    topics: list[str] = Field(min_length=1, max_length=4)


class CoursePack(_Strict):
    id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9]{1,23}$")]
    code: Line  # what the university calls it: "MATH 123"
    title: Line
    summary: Annotated[str, StringConstraints(min_length=1, max_length=400)]
    aliases: list[Line] = Field(default_factory=list, max_length=8)
    track: Course | None = None  # the content course it uses; None for an empty slot
    book: str | None = None  # an id in content/references.json
    book_name: Line | None = None  # how citations name the book: "Book of Proof"
    free_pdf: Annotated[str, StringConstraints(pattern=r"^https://\S+$")] | None = None
    placement: list[PlacementArea] = Field(default_factory=list, max_length=8)

    @property
    def status(self) -> Literal["ready", "empty"]:
        return "ready" if self.track is not None else "empty"

    @property
    def topics(self) -> list[str]:
        """The pack's chapters, as the track's topics in order (none for an empty slot)."""
        return list(course_topics()[self.track.value]) if self.track is not None else []

    @property
    def names(self) -> set[str]:
        return {_key(n) for n in (self.id, self.code, *self.aliases)}

    def describe(self) -> dict[str, object]:
        return {
            "course": self.id,
            "code": self.code,
            "title": self.title,
            "status": self.status,
            "summary": self.summary,
            "track": self.track.value if self.track else None,
            "chapters": len(self.topics),
        }


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _check(pack: CoursePack, books: set[str]) -> list[str]:
    errors = []
    if pack.book is not None and pack.book not in books:
        errors.append(f"book {pack.book!r} isn't in references.json")
    if pack.track is None:
        if pack.placement:
            errors.append("an empty slot (no track) can't have placement areas")
    else:
        topics = set(pack.topics)
        for area in pack.placement:
            unknown = [t for t in area.topics if t not in topics]
            if unknown:
                errors.append(f"placement area {area.area!r} names unknown topics {unknown}")
        if pack.book is None or pack.book_name is None:
            errors.append("a pack with a track needs its book and book_name, for citations")
    return errors


@lru_cache(maxsize=4)
def load_packs(root: Path = PACKS_DIR) -> dict[str, CoursePack]:
    """Every pack, keyed by id, in file-name order. Raises :class:`PackError` listing every
    problem found, so a bad pack stops the tutor before it teaches from it."""
    books = set(load_references())
    packs: dict[str, CoursePack] = {}
    errors: list[str] = []
    taken: dict[str, str] = {}
    for path in sorted(root.glob("*.json")):
        try:
            pack = CoursePack.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        if pack.id != path.stem:
            errors.append(f"{path.name}: id {pack.id!r} must match the file name")
        errors += [f"{path.name}: {e}" for e in _check(pack, books)]
        for name in sorted(pack.names):
            if name in taken:
                errors.append(f"{path.name}: the name {name!r} is already used by {taken[name]}")
            taken[name] = pack.id
        packs[pack.id] = pack
    if not packs:
        errors.append(f"no course packs in {root}")
    if errors:
        raise PackError("invalid course packs:\n  " + "\n  ".join(errors))
    return packs


def find_pack(name: str | None = None) -> CoursePack:
    """The pack a course name means: an id, a course code or an alias, written any way
    ("MATH 223", "math-223", "223"). No name means ``PROOFLAB_TUTOR_COURSE``, then MATH 123."""
    packs = load_packs()
    wanted = name or os.environ.get(COURSE_ENV) or DEFAULT_PACK
    key = _key(wanted)
    for pack in packs.values():
        if key and key in pack.names:
            return pack
    known = ", ".join(f"{p.id} ({p.code})" for p in packs.values())
    raise PackError(f"No course called {wanted[:40]!r}. The courses are: {known}.")
