from __future__ import annotations

import pytest

from prooflab.engine.checker import ContentError, get_handler
from prooflab.engine.models import VerdictStatus


def _induction(make_problem, **data):
    return make_problem("induction", data, course="proofs", topic="induction")


@pytest.fixture
def gauss(make_problem):
    return _induction(make_problem, base=1, sum={"term": "i", "rhs": "(n^2 + n)/2"})


@pytest.fixture
def cubes(make_problem):
    return _induction(make_problem, base=0, divides={"divisor": 3, "expr": "n^3 + 5n + 6"})


def test_sum_proof(gauss, check_submission):
    verdict = check_submission(
        gauss,
        ("base", "1 = (1^2 + 1)/2"),
        ("assume", "1 + 2 + ... + k = (k^2 + k)/2"),
        "(k^2 + k)/2 + (k + 1)",
        "((k + 1)^2 + (k + 1))/2",
    )
    assert verdict.status is VerdictStatus.CORRECT


def test_sum_needs_the_hypothesis(gauss, check_submission, verdict_codes):
    verdict = check_submission(
        gauss, ("base", "1 = 1"), ("assume", "... = (k^2 + k)/2"), "((k + 1)^2 + (k + 1))/2"
    )
    assert verdict.status is VerdictStatus.PARTIAL
    assert "IND_USE_HYPOTHESIS" in verdict_codes(verdict)


def test_sum_needs_simplifying(gauss, check_submission, verdict_codes):
    verdict = check_submission(
        gauss, ("base", "1 = 1"), ("assume", "... = (k^2 + k)/2"), "(k^2 + k)/2 + k + 1"
    )
    assert "IND_FINISH_SUM" in verdict_codes(verdict)


def test_base_case_errors(gauss, check_submission, verdict_codes):
    assert "IND_BASE_UNEQUAL" in verdict_codes(check_submission(gauss, ("base", "1 = 2")))
    assert "IND_BASE_NUMBERS" in verdict_codes(check_submission(gauss, ("base", "n = n")))
    assert "IND_NEED_BASE" in verdict_codes(
        check_submission(gauss, ("assume", "... = (k^2 + k)/2"))
    )


def test_hypothesis_must_use_k(gauss, check_submission, verdict_codes):
    verdict = check_submission(gauss, ("assume", "1 + ... + n = (n^2 + n)/2"))
    assert "IND_ASSUME_USE_K" in verdict_codes(verdict)


def test_exponential_sum(make_problem, check_submission):
    problem = _induction(make_problem, base=1, sum={"term": "2^i", "rhs": "2^(n+1) - 2"})
    verdict = check_submission(
        problem,
        ("base", "2 = 2^2 - 2"),
        ("assume", "2 + 4 + ... + 2^k = 2^(k+1) - 2"),
        "2^(k+1) - 2 + 2^(k+1)",
        "2^(k+2) - 2",
    )
    assert verdict.status is VerdictStatus.CORRECT


def test_divisibility_proof(cubes, check_submission):
    verdict = check_submission(
        cubes,
        ("base", "0^3 + 5*0 + 6 = 6 = 3*2"),
        ("assume", "k^3 + 5k + 6 = 3m"),
        "3m + 3k^2 + 3k + 6",
        ("witness", "m + k^2 + k + 2"),
    )
    assert verdict.status is VerdictStatus.CORRECT


def test_divisibility_wrong_witness(cubes, check_submission, verdict_codes):
    verdict = check_submission(
        cubes, ("base", "3 | 6"), ("assume", "k^3 + 5k + 6 = 3m"), ("witness", "m + k^2 + k + 1")
    )
    assert "IND_WITNESS_WRONG" in verdict_codes(verdict)


def test_exponential_divisibility(make_problem, check_submission):
    problem = _induction(make_problem, base=0, divides={"divisor": 24, "expr": "5^(2n) - 1"})
    verdict = check_submission(
        problem,
        ("base", "5^0 - 1 = 0"),
        ("assume", "5^(2k) - 1 = 24m"),
        "25(5^(2k) - 1) + 24",
        ("witness", "25m + 1"),
    )
    assert verdict.status is VerdictStatus.CORRECT


def test_false_statement_is_a_content_error(make_problem):
    problem = _induction(make_problem, base=1, sum={"term": "i", "rhs": "n^2"})
    handler = get_handler("induction")
    with pytest.raises(ContentError):
        handler.validate(problem, handler.params(problem))


def test_integer_valued_witness(make_problem, check_submission):
    # Book of Proof 10.13: 6 | n³ − n, where k(k + 1)/2 is an integer.
    problem = _induction(make_problem, base=0, divides={"divisor": 6, "expr": "n^3 - n"})
    verdict = check_submission(
        problem,
        ("base", "0^3 - 0 = 0"),
        ("assume", "k^3 - k = 6m"),
        "6m + 3k(k + 1)",
        ("witness", "m + k(k + 1)/2"),
    )
    assert verdict.status is VerdictStatus.CORRECT
    not_integer = check_submission(
        problem, ("base", "0 = 0"), ("assume", "k^3 - k = 6m"), ("witness", "m + k/2")
    )
    assert not_integer.status is VerdictStatus.INCORRECT


def test_no_hypothesis_credit_without_assume(gauss, check_submission):
    verdict = check_submission(gauss, ("base", "1 = 1"), "(k^2 + k)/2 + (k + 1)")
    assert "hypothesis" not in verdict.steps[1].message.lower()
