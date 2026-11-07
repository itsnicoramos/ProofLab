from __future__ import annotations

import pytest
import sympy as sp

from prooflab.engine.algebra import MathContext
from prooflab.engine.models import StepStatus, VerdictStatus
from prooflab.engine.topics.precalc.exp_log import (
    is_log_condensed,
    is_log_expanded,
    solve_in,
    step_solutions,
)


@pytest.fixture
def problem(make_problem):
    def build(kind, data, answer, **kw):
        return make_problem(kind, data, answer, course="precalc", topic="exp_log", **kw)

    return build


def test_step_solutions_handles_or_and_lists():
    ctx = MathContext.build(["x"])
    x = ctx["x"]
    values, _ = step_solutions("x = 2 or x = -3", ctx, x, sp.S.Reals)
    assert sorted(values) == [-3, 2]
    values, _ = step_solutions("(x - 1)(x + 4) = 0", ctx, x, sp.S.Reals)
    assert sorted(values) == [-4, 1]


def test_solve_in_finds_roots_solveset_misses_on_intervals():
    ctx = MathContext.build(["x"])
    x = ctx["x"]
    lhs = ctx.parse("2sin(x)^2 - sin(x) - 1")
    roots = solve_in(lhs, sp.Integer(0), x, sp.Interval.Ropen(0, 2 * sp.pi))
    assert len(roots) == 3


def test_log_forms():
    ctx = MathContext.build({"x": "positive", "y": "positive"})
    p = ctx.parse
    assert is_log_expanded(p("2 ln x - ln y")) and not is_log_expanded(p("ln(x^2) - ln y"))
    assert is_log_condensed(p("ln(x^2/y)")) and not is_log_condensed(p("2 ln(x/y)"))
    assert is_log_condensed(p("log(x y)"))  # base 10 is a single log too


def test_lost_and_extraneous_steps(problem, check_submission, verdict_codes):
    p = problem("equation", {"equation": "sqrt(x + 2) = x"}, "x = 2")
    verdict = check_submission(
        p, "x + 2 = x^2", "x^2 - x - 2 = 0", "(x - 2)(x + 1) = 0", answer="x = 2"
    )
    assert [s.status for s in verdict.steps] == [StepStatus.WARNING, StepStatus.OK, StepStatus.OK]
    assert verdict.status is VerdictStatus.CORRECT
    kept = check_submission(p, "x + 2 = x^2", answer="x = 2 or x = -1")
    assert kept.status is VerdictStatus.INCORRECT
    assert "EXTRA_SOLUTIONS" in verdict_codes(kept)

    q = problem("equation", {"equation": "x^2 = 5x"}, "x = 0 or x = 5")
    lost = check_submission(q, "x = 5", answer="5")
    assert lost.steps[0].status is StepStatus.ERROR
    assert {"LOST_SOLUTION", "MISSING_SOLUTIONS"} <= verdict_codes(lost)


def test_answer_formats(problem, check_submission):
    p = problem("equation", {"equation": "x^2 = 4"}, "x = 2 or x = -2")
    for answer in ("x = 2 or x = -2", "x = -2, x = 2", "{2, -2}", "2, -2"):
        assert check_submission(p, answer=answer).status is VerdictStatus.CORRECT, answer
    none = problem("equation", {"equation": "e^x = -1"}, "no solution")
    assert check_submission(none, answer="no solution").status is VerdictStatus.CORRECT
    assert check_submission(none, answer="x = 0").status is VerdictStatus.INCORRECT
    assert check_submission(p, answer="x = y").status is VerdictStatus.INVALID


def test_log_rewrite(problem, check_submission, verdict_codes):
    p = problem(
        "log_rewrite",
        {
            "expression": "ln(x y^3)",
            "form": "expanded",
            "variables": {"x": "positive", "y": "positive"},
        },
        "ln(x) + 3 ln(y)",
    )
    assert check_submission(p, answer="ln x + 3 ln y").status is VerdictStatus.CORRECT
    assert "LOG_NOT_EXPANDED" in verdict_codes(check_submission(p, answer="ln x + ln(y^3)"))
    assert check_submission(p, answer="3 ln x + ln y").status is VerdictStatus.INCORRECT
