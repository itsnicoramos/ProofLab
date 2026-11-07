"""Every problem: schema, reference, review status, answer key and expected verdicts (SPEC §8)."""

from __future__ import annotations

import os

import pytest

from prooflab.content import load_registry
from prooflab.engine import hints
from prooflab.engine.checker import check, get_handler, handlers
from prooflab.engine.models import ReviewStatus, StepStatus, VerdictStatus

# PROOFLAB_TEST_COURSES=calc1,calc2 limits the run to some courses (handy while authoring).
_ONLY = os.environ.get("PROOFLAB_TEST_COURSES")
REGISTRY = load_registry(courses=_ONLY.split(",") if _ONLY else None)
PROBLEMS = sorted(REGISTRY.problems.values(), key=lambda p: p.id)
EXAMPLES = [(p, e) for p in PROBLEMS for e in p.examples]


def _pid(problem) -> str:
    return problem.id


def test_content_loads() -> None:
    assert PROBLEMS, "no problems found"


@pytest.mark.skipif(bool(_ONLY), reason="only meaningful for the full content set")
def test_every_kind_has_problems() -> None:
    used = {p.kind for p in PROBLEMS}
    missing = sorted(set(handlers()) - used)
    assert not missing, f"kinds with no content: {missing}"


@pytest.mark.parametrize("problem", PROBLEMS, ids=_pid)
def test_reference_is_valid(problem) -> None:
    book = REGISTRY.references.get(problem.reference.book)
    assert book is not None, f"unknown book {problem.reference.book!r}"
    assert problem.reference.section.strip(), "citation needs a section"
    assert book.license, "book needs a license"


@pytest.mark.parametrize("problem", PROBLEMS, ids=_pid)
def test_review_status(problem) -> None:
    review = problem.review
    assert review.status in ReviewStatus
    if review.status is ReviewStatus.REVIEWED:
        assert review.reviewer and review.reviewed_on


@pytest.mark.parametrize("problem", PROBLEMS, ids=_pid)
def test_answer_key_matches_sympy(problem) -> None:
    handler = get_handler(problem.kind)
    verified = handler.verify_key(problem, handler.params(problem))
    assert verified is not False, (
        f"{problem.id}: answer key {problem.answer!r} disagrees with SymPy"
    )


@pytest.mark.parametrize("problem", PROBLEMS, ids=_pid)
def test_problem_has_hints_and_solution(problem) -> None:
    assert problem.hints, "add at least one authored hint"
    assert all(line.strip() for line in problem.solution)


@pytest.mark.parametrize(
    ("problem", "example"), EXAMPLES, ids=[f"{p.id}::{e.name}" for p, e in EXAMPLES]
)
def test_example_verdict(problem, example) -> None:
    verdict = check(problem, example.submission)
    dump = verdict.model_dump_json(indent=2)
    assert verdict.status == example.expect.status, dump

    errors = [s.index for s in verdict.steps if s.status is StepStatus.ERROR]
    if example.expect.first_error is not None:
        assert errors and errors[0] == example.expect.first_error, dump
    if example.expect.status is VerdictStatus.CORRECT:
        assert not errors, dump

    codes = {h.code for h in verdict.hints} | {s.code for s in verdict.steps if s.code}
    if verdict.answer is not None and verdict.answer.code:
        codes.add(verdict.answer.code)
    for code in example.expect.hint_codes:
        assert code in codes, f"expected hint {code}; got {sorted(codes)}\n{dump}"
    for code in codes:
        assert hints.is_registered(code), f"unregistered hint code {code}"
    assert "ENGINE_ERROR" not in codes, dump
