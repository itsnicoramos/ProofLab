from __future__ import annotations

import pytest

from prooflab.engine.models import StepStatus, VerdictStatus


@pytest.fixture
def odd_square(make_problem):
    data = {
        "variables": ["n"],
        "hypotheses": [{"var": "n", "is": "odd"}],
        "target": "n^2",
        "goal": "odd",
    }
    return make_problem("parity_proof", data, course="proofs", topic="parity")


@pytest.fixture
def two_evens(make_problem):
    data = {
        "variables": ["m", "n"],
        "hypotheses": [{"var": "m", "is": "even"}, {"var": "n", "is": "even"}],
        "target": "m + n",
        "goal": "even",
    }
    return make_problem("parity_proof", data, course="proofs", topic="parity")


def test_complete_direct_proof(odd_square, check_submission):
    verdict = check_submission(
        odd_square,
        ("let", "n = 2k + 1"),
        "(2k + 1)^2",
        "4k^2 + 4k + 1",
        "2(2k^2 + 2k) + 1",
        ("witness", "m = 2k^2 + 2k"),
    )
    assert verdict.status is VerdictStatus.CORRECT
    assert all(s.status is StepStatus.OK for s in verdict.steps)
    assert verdict.answer is not None and "∎" in verdict.answer.message


@pytest.mark.parametrize("rep", ["n = 2k - 1", "n = 2j + 3", "n = -2k + 1", "n=2*k+1"])
def test_any_valid_odd_representation(odd_square, check_submission, rep):
    verdict = check_submission(odd_square, ("let", rep))
    assert verdict.steps[0].status is StepStatus.OK, rep


@pytest.mark.parametrize(
    ("rep", "code"),
    [
        ("n = k + 1", "ODD_FORM"),
        ("n = 2k", "ODD_FORM"),
        ("n = 4k + 1", "ODD_FORM"),
        ("n = 3", "BAD_REPRESENTATION"),
        ("n = 2n + 1", "FRESH_NOT_NEW"),
        ("n = 2j + 2k + 1", "BAD_REPRESENTATION"),
    ],
)
def test_bad_representations(odd_square, check_submission, verdict_codes, rep, code):
    verdict = check_submission(odd_square, ("let", rep))
    assert verdict.steps[0].status is StepStatus.ERROR
    assert code in verdict_codes(verdict)


def test_let_needs_a_problem_variable(odd_square, check_submission, verdict_codes):
    verdict = check_submission(odd_square, ("let", "2k + 1"))
    assert "LET_FORMAT" in verdict_codes(verdict)


def test_same_fresh_variable_is_rejected(two_evens, check_submission, verdict_codes):
    verdict = check_submission(two_evens, ("let", "m = 2k"), ("let", "n = 2k"))
    assert verdict.status is VerdictStatus.INCORRECT
    assert "SAME_FRESH_VARIABLE" in verdict_codes(verdict)


def test_chain_step_must_equal_target(two_evens, check_submission):
    verdict = check_submission(
        two_evens, ("let", "m = 2j"), ("let", "n = 2k"), "2j + 2k", "2(j + 2k)"
    )
    assert [s.status for s in verdict.steps][-2:] == [StepStatus.OK, StepStatus.ERROR]


def test_unknown_letter_in_chain_step(two_evens, check_submission):
    verdict = check_submission(two_evens, ("let", "m = 2j"), "2q + n")
    assert verdict.steps[1].status is StepStatus.ERROR
    assert verdict.steps[1].code == "UNKNOWN_NAME"


def test_incomplete_proof_is_partial(two_evens, check_submission, verdict_codes):
    verdict = check_submission(two_evens, ("let", "m = 2j"), ("let", "n = 2k"), "2(j + k)")
    assert verdict.status is VerdictStatus.PARTIAL
    assert "PROOF_INCOMPLETE" in verdict_codes(verdict)


def test_missing_let_hint(odd_square, check_submission, verdict_codes):
    verdict = check_submission(odd_square, ("witness", "(n^2 - 1)/2"))
    assert verdict.status is VerdictStatus.INCORRECT
    assert {"WITNESS_NOT_INTEGER", "MISSING_LET"} <= verdict_codes(verdict)


def test_notes_are_unchecked(odd_square, check_submission):
    verdict = check_submission(odd_square, ("note", "n is odd so write it as 2k+1"))
    assert verdict.steps[0].status is StepStatus.UNCHECKED
    assert verdict.status is VerdictStatus.PARTIAL


def test_empty_proof(odd_square, check_submission, verdict_codes):
    verdict = check_submission(odd_square)
    assert verdict.status is VerdictStatus.INCORRECT
    assert "EMPTY_SUBMISSION" in verdict_codes(verdict)


def test_cases_must_be_exhaustive(make_problem, check_submission, verdict_codes):
    p = make_problem(
        "parity_proof",
        {"variables": ["n"], "target": "n^2 + n", "goal": "even"},
        course="proofs",
        topic="parity",
    )
    even = [("case", "n = 2k"), ("witness", "2k^2 + k")]
    odd = [("case", "n = 2k + 1"), ("witness", "2k^2 + 3k + 1")]
    assert check_submission(p, *even, *odd).status is VerdictStatus.CORRECT
    partial = check_submission(p, *even)
    assert partial.status is VerdictStatus.PARTIAL
    assert "CASES_NOT_EXHAUSTIVE" in verdict_codes(partial)
    # mod-4 cases also work when all four remainders are covered
    mod4 = [
        ("case", "n = 4k"), ("witness", "8k^2 + 2k"),
        ("case", "n = 4k + 1"), ("witness", "8k^2 + 6k + 1"),
        ("case", "n = 4k + 2"), ("witness", "8k^2 + 10k + 3"),
        ("case", "n = 4k + 3"), ("witness", "8k^2 + 14k + 6"),
    ]  # fmt: skip
    assert check_submission(p, *mod4).status is VerdictStatus.CORRECT


def test_cases_relative_to_hypothesis(odd_square, check_submission, verdict_codes):
    # n odd: the cases n = 4k + 1 and n = 4k + 3 cover every odd n.
    verdict = check_submission(
        odd_square,
        ("case", "n = 4k + 1"),
        ("witness", "8k^2 + 4k"),
        ("case", "n = 4k + 3"),
        ("witness", "8k^2 + 12k + 4"),
    )
    assert verdict.status is VerdictStatus.CORRECT
    bad = check_submission(odd_square, ("case", "n = 4k + 2"))
    assert "CASE_CONTRADICTS_HYPOTHESIS" in verdict_codes(bad)
