"""The repo tutor's lesson notes (SPEC §20): one per chapter, fixed shape, real ids and codes."""

from __future__ import annotations

import re

import pytest

from prooflab.content import load_registry
from prooflab.engine import hints
from prooflab.engine.checker import load_topics
from prooflab.lessons import SECTIONS, load_lessons

LESSONS = load_lessons("proofs")
REGISTRY = load_registry(courses=["proofs"])
TOPICS = REGISTRY.topics["proofs"]
SERVED = {p.id: p for p in REGISTRY.served()}
CITATION = re.compile(r"\(Section (\d+)\.(\d+), p\. (\d+)\)")
SECTION = re.compile(r"^(\d+)\.(\d+) .+ \(p\. (\d+)\)$")
CODE = re.compile(r"`([A-Z][A-Z0-9_]+)`")
PROBLEM_ID = re.compile(r"`(proofs\.[a-z0-9-]+\.[a-z0-9-]+)`")

load_topics()


def test_one_note_per_chapter() -> None:
    assert sorted(LESSONS) == list(range(1, 15))
    for n, lesson in LESSONS.items():
        assert lesson.topic == TOPICS[n - 1]
        assert lesson.path.name == f"ch{n:02d}-{lesson.topic}.md"
        assert lesson.book == "hammack-bop3"


@pytest.mark.parametrize("n", range(1, 15))
def test_note_shape(n: int) -> None:
    lesson = LESSONS[n]
    assert list(lesson.parts) == list(SECTIONS), "the seven sections, in order"
    assert all(lesson.parts[s].strip() for s in SECTIONS)
    assert lesson.body.startswith(f"# Chapter {n}: {lesson.title}\n")
    assert 30 <= lesson.minutes <= 240
    assert all(1 <= c < n for c in lesson.prerequisites)
    for name in ("—", "–"):
        assert name not in lesson.body, "no em or en dashes"


@pytest.mark.parametrize("n", range(1, 15))
def test_citations_match_the_book_sections(n: int) -> None:
    lesson = LESSONS[n]
    pages = {}
    for s in lesson.sections:
        m = SECTION.match(s)
        assert m and int(m[1]) == n, s
        pages[(int(m[1]), int(m[2]))] = int(m[3])
    cited = CITATION.findall(lesson.parts["Core ideas"])
    assert cited, "every core idea cites its section"
    for chapter, section, page in cited:
        assert pages.get((int(chapter), int(section))) == int(page), (chapter, section, page)


@pytest.mark.parametrize("n", range(1, 15))
def test_practice_and_mistakes_point_at_real_things(n: int) -> None:
    lesson = LESSONS[n]
    has_problems = any(p.topic == lesson.topic for p in SERVED.values())
    assert (lesson.checkable == "no") == (not has_problems)
    route = PROBLEM_ID.findall(lesson.parts["Practice route"])
    codes = CODE.findall(lesson.parts["Common mistakes"])
    if has_problems:
        assert len(route) >= 3
        for pid in route:
            assert pid in SERVED and SERVED[pid].topic == lesson.topic, pid
        assert codes, "mistakes name the checker's hint codes"
        for code in codes:
            assert hints.is_registered(code), code
    else:
        assert not route and not codes  # nothing to check against yet
        assert "Chapter" in lesson.parts["Practice route"]
