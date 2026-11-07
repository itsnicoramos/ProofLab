from __future__ import annotations

import pytest

from prooflab.engine.checker import ContentError, get_handler
from prooflab.engine.models import StepStatus, VerdictStatus


@pytest.fixture
def plates(make_problem):
    return make_problem(
        "count",
        {},
        "26^4",
        course="proofs",
        topic="counting",
        mistakes=[("binom(26, 4)", "Order matters for a list.")],
    )


@pytest.mark.parametrize("answer", ["456976", "26^4", "26*26*26*26", "binom(26,1)^4"])
def test_any_expression_for_the_right_count(plates, check_submission, answer):
    assert check_submission(plates, answer=answer).status is VerdictStatus.CORRECT


def test_authored_mistake_gets_its_hint(plates, check_submission, verdict_codes):
    verdict = check_submission(plates, answer="binom(26, 4)")
    assert verdict.status is VerdictStatus.INCORRECT
    assert "KNOWN_MISTAKE" in verdict_codes(verdict)


def test_fractions_and_symbols(plates, check_submission, verdict_codes):
    assert "COUNT_NOT_INTEGER" in verdict_codes(check_submission(plates, answer="1/2"))
    assert check_submission(plates, answer="x + 1").status is VerdictStatus.INVALID


def test_working_steps_are_shown_not_judged(plates, check_submission):
    verdict = check_submission(plates, "26^2", answer="26^4")
    assert verdict.steps[0].status is StepStatus.UNCHECKED and "676" in verdict.steps[0].message
    assert verdict.status is VerdictStatus.CORRECT


def test_bad_key_is_a_content_error(make_problem):
    problem = make_problem("count", {}, "1/3", course="proofs", topic="counting")
    handler = get_handler("count")
    with pytest.raises(ContentError):
        handler.validate(problem, handler.params(problem))


def test_binomial_function():
    from prooflab.engine.algebra import MathContext

    assert MathContext.build().parse("binom(10, 3)") == 120


@pytest.mark.parametrize(("text", "value"), [("P(15, 4)", 32760), ("C(10, 3)", 120)])
def test_book_notation(make_problem, check_submission, text, value):
    problem = make_problem("count", {}, str(value), course="proofs", topic="counting")
    assert check_submission(problem, answer=text).status is VerdictStatus.CORRECT
