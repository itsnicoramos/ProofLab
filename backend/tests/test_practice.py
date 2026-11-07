from __future__ import annotations

from collections import Counter

import pytest
from fastapi.testclient import TestClient

from prooflab.content import load_registry
from prooflab.engine.models import Course
from prooflab.main import Settings, create_app
from prooflab.practice import (
    MAX_LENGTH,
    PracticeTestError,
    allocate,
    available_topics,
    build_practice_test,
    default_topics,
)

REGISTRY = load_registry(courses=["proofs", "calc1", "calc2"])


def test_same_inputs_give_the_same_test():
    a = build_practice_test(REGISTRY, Course.PROOFS, "final", seed=7)
    b = build_practice_test(REGISTRY, Course.PROOFS, "final", seed=7)
    assert a.id == b.id and [p.id for p in a.problems] == [p.id for p in b.problems]
    c = build_practice_test(REGISTRY, Course.PROOFS, "final", seed=8)
    assert c.id != a.id
    assert [p.id for p in c.problems] != [p.id for p in a.problems]


def test_midterm_covers_the_first_half_and_final_covers_everything():
    topics = available_topics(REGISTRY, Course.PROOFS)
    assert default_topics(REGISTRY, Course.PROOFS, "final") == topics
    assert default_topics(REGISTRY, Course.PROOFS, "midterm") == topics[: (len(topics) + 1) // 2]
    midterm = build_practice_test(REGISTRY, Course.PROOFS, "midterm", seed=1)
    assert {p.topic for p in midterm.problems} <= set(midterm.topics)


def test_every_topic_in_scope_gets_a_question_and_order_follows_the_course():
    test = build_practice_test(REGISTRY, Course.PROOFS, "final", seed=3)
    assert {p.topic for p in test.problems} == set(test.topics)
    order = [test.topics.index(p.topic) for p in test.problems]
    assert order == sorted(order)
    assert len({p.id for p in test.problems}) == len(test.problems), "no repeated questions"


def test_length_is_capped_by_what_exists():
    small = build_practice_test(REGISTRY, Course.CALC1, "final", seed=1, length=MAX_LENGTH)
    assert len(small.problems) == len([p for p in REGISTRY.served() if p.course is Course.CALC1])
    one = build_practice_test(REGISTRY, Course.PROOFS, "midterm", seed=1, length=1)
    assert len(one.problems) == 1


def test_explicit_topics_and_unknown_topics():
    test = build_practice_test(REGISTRY, Course.PROOFS, "midterm", seed=2, topics=["direct"])
    assert {p.topic for p in test.problems} == {"direct"}
    with pytest.raises(PracticeTestError):
        build_practice_test(REGISTRY, Course.PROOFS, "midterm", seed=2, topics=["astrology"])


def test_difficulty_mix_and_kind_variety():
    test = build_practice_test(REGISTRY, Course.CALC2, "final", seed=5, length=12)
    difficulties = Counter(p.difficulty for p in test.problems)
    assert difficulties[2] >= difficulties[3], "medium questions should outnumber hard ones"
    assert len({p.kind for p in test.problems}) >= 3


def test_suggested_minutes_follow_the_stated_rule():
    test = build_practice_test(REGISTRY, Course.PROOFS, "midterm", seed=4)
    raw = sum({1: 5, 2: 8, 3: 12}[p.difficulty] for p in test.problems)
    assert test.suggested_minutes >= raw and test.suggested_minutes - raw < 5


@pytest.mark.parametrize(
    ("length", "sizes", "expected"),
    [
        (8, [65, 12], [6, 2]),
        (4, [10, 10, 10, 10], [1, 1, 1, 1]),
        (2, [5, 5, 5, 5], [1, 0, 0, 1]),
        (6, [1, 10], [1, 5]),
    ],
)
def test_allocate(length, sizes, expected):
    result = allocate(length, sizes)
    assert result == expected
    assert sum(result) == length
    assert all(r <= s for r, s in zip(result, sizes, strict=True))


def test_practice_test_endpoint():
    client = TestClient(create_app(Settings(isolate=False), REGISTRY))
    r = client.get("/practice-tests", params={"course": "proofs", "kind": "final", "seed": 11})
    assert r.status_code == 200
    body = r.json()
    assert body["title"].endswith("Practice final") and body["minutes_rule"]
    assert body["problems"]
    assert all("answer" not in p and "solution" not in p for p in body["problems"])
    again = client.get("/practice-tests", params={"course": "proofs", "kind": "final", "seed": 11})
    assert again.json()["id"] == body["id"]

    def status(**params: object) -> int:
        return client.get("/practice-tests", params={"course": "proofs", **params}).status_code

    assert status(topics="astrology") == 404
    assert status(kind="weekly") == 422
    assert status(length=99) == 422
