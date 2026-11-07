"""Multiple-choice questions (SPEC §13.2) and the self-tuning test options (§13.1)."""

from __future__ import annotations

import random

import pytest
from fastapi.testclient import TestClient

from prooflab.content import load_registry
from prooflab.engine.checker import check
from prooflab.engine.models import Course, Submission, VerdictStatus
from prooflab.main import Settings, create_app
from prooflab.practice import allocate, build_practice_test
from prooflab.quiz import build_question, candidates, grade

REGISTRY = load_registry(courses=["proofs", "calc1", "calc2"])
SERVED = REGISTRY.served()


def run(problem, sub):
    return check(problem, sub)


def by_kind(kind: str):
    return next(p for p in SERVED if p.kind == kind)


@pytest.mark.parametrize(
    "kind", ["count", "finite_set", "truth_table", "derivative", "antiderivative", "limit"]
)
def test_answer_questions_have_one_right_choice(kind):
    problem = by_kind(kind)
    q = build_question(problem, 3, run, SERVED, "answer")
    assert q is not None and q.format == "answer"
    assert 3 <= len(q.choices) <= 4
    assert len({c.latex or c.text for c in q.choices}) == len(q.choices)
    assert grade(q, q.correct)[0]
    # Every wrong choice really is wrong: the checker marks it incorrect.
    for c in q.choices:
        if c.key == q.correct:
            continue
        assert not grade(q, c.key)[0]


def test_distractors_are_verified_by_the_checker():
    """Each wrong choice comes from a candidate the checker marked incorrect, never correct."""
    problem = by_kind("count")
    rng = random.Random(1)
    verdicts = [run(problem, Submission(answer=c)) for c in candidates(problem, rng, SERVED)]
    assert any(v.answer.status is VerdictStatus.INCORRECT for v in verdicts if v.answer)
    q = build_question(problem, 1, run, SERVED, "answer")
    assert q is not None
    shown_wrong = {c.latex for c in q.choices if c.key != q.correct}
    right = run(problem, Submission(answer=problem.answer)).answer.latex
    assert right not in shown_wrong


def test_spot_question_points_at_the_first_error():
    problem = by_kind("parity_proof")
    for seed in range(1, 8):
        q = build_question(problem, seed, run, SERVED, "spot")
        assert q is not None and q.format == "spot" and q.steps
        assert q.choices[-1].text and q.choices[-1].text.startswith("No mistake")
        ok, explanation = grade(q, q.correct)
        assert ok and explanation


def test_same_seed_same_question():
    problem = by_kind("finite_set")
    a = build_question(problem, 5, run, SERVED)
    b = build_question(problem, 5, run, SERVED)
    assert a == b


def test_most_problems_get_a_question():
    made = sum(build_question(p, 1, run, SERVED) is not None for p in SERVED)
    assert made >= 0.9 * len(SERVED)


def test_weights_move_questions_to_weak_topics():
    even = allocate(10, [10, 10, 10])
    weak_first = allocate(10, [10, 10, 10], [3.0, 1.0, 1.0])
    assert sum(even) == sum(weak_first) == 10
    assert weak_first[0] > even[0]
    assert all(n >= 1 for n in weak_first)


def test_prefer_puts_due_problems_in_the_test():
    due = [p.id for p in SERVED if p.course is Course.PROOFS and p.topic == "logic"][:2]
    test = build_practice_test(REGISTRY, Course.PROOFS, "quiz", seed=4, prefer=due, length=12)
    assert set(due) <= {p.id for p in test.problems}


def test_plain_tests_keep_their_ids():
    """Adding styles must not reshuffle the tests students already took."""
    a = build_practice_test(REGISTRY, Course.PROOFS, "final", seed=7)
    b = build_practice_test(REGISTRY, Course.PROOFS, "final", seed=7, style="written")
    assert a.id == b.id and a.problems == b.problems
    mixed = build_practice_test(REGISTRY, Course.PROOFS, "final", seed=7, style="mixed")
    assert mixed.id != a.id
    assert {q.format for q in mixed.questions} == {"written", "choice"}


def test_quiz_endpoint_round_trip():
    client = TestClient(create_app(Settings(isolate=False), REGISTRY))
    r = client.get(
        "/practice-tests",
        params={"course": "proofs", "kind": "quiz", "seed": 9, "style": "choice", "length": 6},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["style"] == "choice" and len(body["questions"]) == 6
    choice_qs = [q for q in body["questions"] if q["format"] == "choice"]
    assert choice_qs
    for q in choice_qs:
        assert "correct" not in q["choice"] and all(
            "explanation" not in c for c in q["choice"]["choices"]
        )
    q = choice_qs[0]
    results = {
        c["key"]: client.post(
            "/quiz/answer",
            json={
                "problem_id": q["problem"]["id"],
                "seed": q["choice"]["seed"],
                "format": q["choice"]["format"],
                "choice": c["key"],
            },
        ).json()
        for c in q["choice"]["choices"]
    }
    assert sum(r["correct"] for r in results.values()) == 1
    assert len({r["correct_choice"] for r in results.values()}) == 1
    assert all(r["solution"] for r in results.values())


def test_weights_and_prefer_params():
    client = TestClient(create_app(Settings(isolate=False), REGISTRY))
    params = {"course": "proofs", "kind": "quiz", "seed": 2, "weights": "logic:3,sets:0.5"}
    assert client.get("/practice-tests", params=params).status_code == 200
    bad = {**params, "weights": "logic:lots"}
    assert client.get("/practice-tests", params=bad).status_code == 422


def test_variants_flow_through_the_api():
    """ProofLab-made versions are served, labelled, checkable and quizzable by their id."""
    client = TestClient(create_app(Settings(isolate=False), REGISTRY))
    body = client.get(
        "/practice-tests",
        params={"course": "proofs", "kind": "final", "seed": 3, "variants": "true", "length": 20},
    ).json()
    made = [q for q in body["questions"] if q["problem"]["variant_of"]]
    assert made, "about half the supported questions should become new versions"
    for q in made:
        p = q["problem"]
        assert p["id"].startswith(p["variant_of"] + "-v")
        assert "prooflab-variant" in p["tags"] and "book-of-proof" not in p["tags"]
        detail = client.get(f"/problems/{p['id']}").json()
        assert "not an exercise in the book" in (detail["reference"]["note"] or "")
    from prooflab.variants import make_variant, parse_variant_id

    base_id, seed = parse_variant_id(made[0]["problem"]["id"])
    problem = make_variant(REGISTRY.get(base_id), seed)
    good = next(e for e in problem.examples if e.expect.status.value == "correct")
    verdict = client.post(
        "/check",
        json={
            "problem_id": problem.id,
            "steps": [s.model_dump() for s in good.submission.steps],
            "answer": good.submission.answer,
        },
    ).json()
    assert verdict["status"] == "correct"
