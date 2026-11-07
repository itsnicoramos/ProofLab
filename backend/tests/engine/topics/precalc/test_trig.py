from __future__ import annotations

import pytest

from prooflab.engine.algebra import MathContext
from prooflab.engine.models import StepStatus, VerdictStatus
from prooflab.engine.topics.precalc.trig import reaches


@pytest.fixture
def problem(make_problem):
    def build(kind, data, answer="", **kw):
        return make_problem(kind, data, answer, course="precalc", topic="trig", **kw)

    return build


def test_reaches_allows_definitions_but_not_identities():
    ctx = MathContext.build(["x"])
    p = ctx.parse
    assert reaches(p("sin(x)/cos(x)"), p("tan(x)"))
    assert reaches(p("1/cos(x)^2"), p("sec(x)^2"))
    assert not reaches(p("sin(x)^2 + cos(x)^2"), p("1"))
    assert not reaches(p("2 sin(x) cos(x)"), p("sin(2x)"))


def test_identity_statuses(problem, check_submission, verdict_codes):
    p = problem("trig_identity", {"lhs": "sec(x)^2 - tan(x)^2", "rhs": "1"})
    good = check_submission(
        p, "1/cos(x)^2 - sin(x)^2/cos(x)^2", "(1 - sin(x)^2)/cos(x)^2", "cos(x)^2/cos(x)^2", "1"
    )
    assert good.status is VerdictStatus.CORRECT
    bad = check_submission(p, "1/cos(x)^2 + sin(x)^2/cos(x)^2", "1")
    assert bad.status is VerdictStatus.INCORRECT and bad.steps[0].status is StepStatus.ERROR
    unfinished = check_submission(p, "1/cos(x)^2 - sin(x)^2/cos(x)^2")
    assert unfinished.status is VerdictStatus.PARTIAL
    assert "IDENTITY_INCOMPLETE" in verdict_codes(unfinished)
    assert check_submission(p).status is VerdictStatus.INCORRECT


def test_identity_can_run_right_to_left(problem, check_submission):
    p = problem("trig_identity", {"lhs": "sin(2x)", "rhs": "2 sin(x) cos(x)"})
    verdict = check_submission(p, "2 sin(x) cos(x)", "sin(2x)")
    assert verdict.status is VerdictStatus.CORRECT


def test_trig_equation(problem, check_submission, verdict_codes):
    p = problem("trig_equation", {"equation": "tan(x) = 1"}, "pi/4, 5pi/4")
    assert check_submission(p, answer="x = pi/4 or x = 5pi/4").status is VerdictStatus.CORRECT
    assert "MISSING_SOLUTIONS" in verdict_codes(check_submission(p, answer="pi/4"))
    assert "DEGREES_NOT_RADIANS" in verdict_codes(check_submission(p, answer="45, 225"))
    assert "OUTSIDE_INTERVAL" in verdict_codes(check_submission(p, answer="pi/4, 5pi/4, 9pi/4"))


def test_trig_equation_custom_interval(problem, check_submission):
    p = problem(
        "trig_equation", {"equation": "2cos(x)^2 = 1", "interval": "[0, pi]"}, "pi/4, 3pi/4"
    )
    assert check_submission(p, answer="pi/4, 3pi/4").status is VerdictStatus.CORRECT
    assert check_submission(p, answer="pi/4, 3pi/4, 5pi/4").status is VerdictStatus.INCORRECT


def test_trig_key_verification_finds_all_roots(problem):
    from prooflab.engine.checker import get_handler

    handler = get_handler("trig_equation")
    p = problem("trig_equation", {"equation": "2sin(x)^2 - sin(x) - 1 = 0"}, "pi/2, 7pi/6, 11pi/6")
    assert handler.verify_key(p, handler.params(p)) is True
    q = problem("trig_equation", {"equation": "2sin(x)^2 - sin(x) - 1 = 0"}, "pi/2")
    assert handler.verify_key(q, handler.params(q)) is False
