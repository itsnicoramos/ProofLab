from __future__ import annotations

import pytest

from prooflab.engine.models import StepStatus, VerdictStatus


@pytest.fixture
def never_zero(make_problem):
    # Book of Proof 6.6: a² − 4b − 2 is never 0 (it is never divisible by 4).
    return make_problem(
        "impossibility_proof",
        {
            "variables": ["a", "b"],
            "target": "a^2 - 4b - 2",
            "divisor": 4,
            "forbidden": 0,
            "conclusion": "it is never 0. ∎",
        },
        course="proofs",
        topic="contradiction",
    )


@pytest.fixture
def odd_square(make_problem):
    # Book of Proof 6.1, by contradiction: n odd, so n² can't be even.
    return make_problem(
        "impossibility_proof",
        {
            "variables": ["n"],
            "hypotheses": [{"var": "n", "is": "odd"}],
            "target": "n^2",
            "divisor": 2,
            "forbidden": 0,
            "conclusion": "n² is odd, a contradiction. ∎",
        },
        course="proofs",
        topic="contradiction",
    )


def test_cases_cover_everything(never_zero, check_submission):
    verdict = check_submission(
        never_zero,
        ("case", "a = 2k"),
        "4k^2 - 4b - 2",
        ("form", "4(k^2 - b - 1) + 2"),
        ("case", "a = 2k + 1"),
        ("form", "4(k^2 + k - b) - 1"),
    )
    assert verdict.status is VerdictStatus.CORRECT
    assert "never 0" in verdict.answer.message


def test_missing_case_is_partial(never_zero, check_submission, verdict_codes):
    verdict = check_submission(never_zero, ("case", "a = 2k"), ("form", "4(k^2 - b - 1) + 2"))
    assert verdict.status is VerdictStatus.PARTIAL
    assert "CASES_NOT_EXHAUSTIVE" in verdict_codes(verdict)


def test_form_must_equal_and_be_shaped(never_zero, check_submission, verdict_codes):
    wrong = check_submission(never_zero, ("case", "a = 2k"), ("form", "4(k^2 - b) + 2"))
    assert "FORM_NOT_EQUAL" in verdict_codes(wrong)
    shapeless = check_submission(never_zero, ("form", "a^2 - 4b - 2"))
    assert "FORM_SHAPE" in verdict_codes(shapeless)
    # Equal to the expression but not factored: the student has to show d·(…) + r.
    unfactored = check_submission(never_zero, ("case", "a = 2k"), ("form", "4k^2 - 4b - 2"))
    assert "FORM_SHAPE" in verdict_codes(unfactored)


def test_restating_the_target_is_not_a_proof(make_problem, check_submission, verdict_codes):
    # Book of Proof 6.10: 21a + 30b = 1 has no integer solutions.
    problem = make_problem(
        "impossibility_proof",
        {
            "variables": ["a", "b"],
            "target": "21a + 30b",
            "divisor": 3,
            "forbidden": 1,
            "conclusion": "never 1. ∎",
        },
        course="proofs",
        topic="contradiction",
    )
    assert "FORM_SHAPE" in verdict_codes(check_submission(problem, ("form", "21a + 30b")))
    assert check_submission(problem, ("form", "3(7a + 10b)")).status is VerdictStatus.CORRECT


def test_unfinished_part_names_the_form_step(odd_square, check_submission, verdict_codes):
    verdict = check_submission(odd_square, ("let", "n = 2k + 1"), "4k^2 + 4k + 1")
    assert verdict.status is VerdictStatus.PARTIAL
    assert "FORM_INCOMPLETE" in verdict_codes(verdict)


def test_forbidden_remainder_is_an_error(make_problem, check_submission, verdict_codes):
    problem = make_problem(
        "impossibility_proof",
        {"variables": ["n"], "target": "2n", "divisor": 2, "forbidden": 0, "conclusion": "x"},
        course="proofs",
        topic="contradiction",
    )
    verdict = check_submission(problem, ("form", "2(n) + 0"))
    assert "FORM_ALLOWED_REMAINDER" in verdict_codes(verdict)


def test_let_then_form(odd_square, check_submission):
    verdict = check_submission(
        odd_square, ("let", "n = 2k + 1"), ("form", "n^2 = 2(2k^2 + 2k) + 1")
    )
    assert verdict.status is VerdictStatus.CORRECT
    assert verdict.steps[1].status is StepStatus.OK


@pytest.fixture
def mersenne(make_problem):
    # Book of Proof 7.20: some n ∈ ℕ has 11 | 2ⁿ − 1.
    return make_problem(
        "existence",
        {"variables": {"n": "positive"}, "statement": {"op": "divides", "args": [11, "2^n - 1"]}},
        "n = 10",
        course="proofs",
        topic="nonconditional",
    )


def test_existence(mersenne, check_submission, verdict_codes):
    assert check_submission(mersenne, answer="n = 10").status is VerdictStatus.CORRECT
    assert check_submission(mersenne, answer="n = 20").status is VerdictStatus.CORRECT
    assert "EXISTS_FAILS" in verdict_codes(check_submission(mersenne, answer="n = 3"))
    assert "COUNTEREXAMPLE_DOMAIN" in verdict_codes(check_submission(mersenne, answer="n = 0"))
    assert check_submission(mersenne, answer="10").status is VerdictStatus.INVALID
