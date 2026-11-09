"""Shared fixtures: build throwaway problems and run checks without touching content files."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest

# Tests never touch the student's real progress database (SPEC §17).
os.environ["PROOFLAB_DB"] = str(Path(tempfile.mkdtemp(prefix="prooflab-test-")) / "test.sqlite3")
# Nor the learner's tutor memory (SPEC §20): by default it points at a port nothing listens
# on. tests/test_tutor_memory.py opts in to a throwaway Postgres schema explicitly.
os.environ["PROOFLAB_TUTOR_DATABASE_URL"] = "postgresql://nobody:none@127.0.0.1:9/none"
os.environ["PROOFLAB_TUTOR_DB_SCHEMA"] = "never_used"

from prooflab.engine.checker import check
from prooflab.engine.models import Problem, Submission, Verdict

StepSpec = str | tuple[str, str]


def build_problem(
    kind: str,
    data: dict[str, Any],
    answer: str = "",
    *,
    course: str = "calc1",
    topic: str = "derivatives",
    mistakes: Iterable[tuple[str, str]] = (),
    hints: Iterable[str] = ("Try again.",),
) -> Problem:
    return Problem.model_validate(
        {
            "id": f"{course}.{topic}.test",
            "course": course,
            "topic": topic,
            "kind": kind,
            "title": "Test problem",
            "prompt": "Test prompt",
            "answer_format": "anything",
            "difficulty": 1,
            "data": data,
            "answer": answer,
            "mistakes": [{"answer": a, "hint": h} for a, h in mistakes],
            "hints": list(hints),
            "solution": ["Test solution."],
            "reference": {"book": "openstax-calc1", "section": "1.1"},
            "review": {"status": "draft"},
            "examples": [
                {"name": "a", "submission": {}, "expect": {"status": "correct"}},
                {"name": "b", "submission": {}, "expect": {"status": "incorrect"}},
            ],
        }
    )


def submission(*steps: StepSpec, answer: str | None = None) -> Submission:
    return Submission.model_validate(
        {
            "steps": [
                {"kind": s[0], "content": s[1]} if isinstance(s, tuple) else {"content": s}
                for s in steps
            ],
            "answer": answer,
        }
    )


def run(
    problem: Problem, *steps: StepSpec, answer: str | None = None, hints_revealed: int = 0
) -> Verdict:
    return check(problem, submission(*steps, answer=answer), hints_revealed=hints_revealed)


def codes(verdict: Verdict) -> set[str]:
    """Every hint/step/answer code in a verdict."""
    out = {h.code for h in verdict.hints} | {s.code for s in verdict.steps if s.code}
    if verdict.answer is not None and verdict.answer.code:
        out.add(verdict.answer.code)
    return out


@pytest.fixture
def make_problem() -> Callable[..., Problem]:
    return build_problem


@pytest.fixture
def check_submission() -> Callable[..., Verdict]:
    return run


@pytest.fixture
def verdict_codes() -> Callable[[Verdict], set[str]]:
    return codes
