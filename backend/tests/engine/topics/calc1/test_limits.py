from __future__ import annotations

import sympy as sp

from prooflab.engine.algebra import MathContext
from prooflab.engine.models import StepStatus, VerdictStatus
from prooflab.engine.topics.calc1.limits import DNE, compute_limit, split_fraction


def test_compute_limit():
    ctx = MathContext.build(["x"])
    x = ctx["x"]
    assert compute_limit(sp.sin(x) / x, x, sp.Integer(0), "both") == 1
    assert compute_limit(sp.Abs(x) / x, x, sp.Integer(0), "both") == DNE
    assert compute_limit(1 / x, x, sp.Integer(0), "+") == sp.oo


def test_split_fraction_keeps_written_form():
    ctx = MathContext.build({"x": "positive"})
    num, den = split_fraction("ln(x)/(1/x)", ctx, ctx.parse("ln(x)/(1/x)"))
    assert num == sp.log(ctx["x"]) and den == 1 / ctx["x"]


def test_lhopital_on_rewritten_quotient(make_problem, check_submission):
    p = make_problem(
        "limit",
        {"expression": "x ln(x)", "point": "0", "direction": "+", "variables": {"x": "positive"}},
        "0",
        topic="limits",
    )
    verdict = check_submission(
        p, "ln(x)/(1/x)", ("lhopital", "(1/x)/(-1/x^2)"), "-x", "0", answer="0"
    )
    assert [s.status for s in verdict.steps] == [StepStatus.OK] * 4
    assert verdict.status is VerdictStatus.CORRECT


def test_lhopital_requires_indeterminate_form(make_problem, check_submission, verdict_codes):
    p = make_problem(
        "limit", {"expression": "(x^2 + 1)/(x + 1)", "point": "1"}, "1", topic="limits"
    )
    verdict = check_submission(p, ("lhopital", "2x/1"), answer="2")
    assert verdict.steps[0].status is StepStatus.ERROR
    assert "LHOPITAL_NOT_INDETERMINATE" in verdict_codes(verdict)


def test_step_that_changes_the_limit_is_an_error(make_problem, check_submission):
    p = make_problem(
        "limit", {"expression": "(x^2 - 4)/(x - 2)", "point": "2"}, "4", topic="limits"
    )
    verdict = check_submission(p, "x - 2", answer="0")
    assert verdict.steps[0].status is StepStatus.ERROR


def test_squeeze_style_step_is_a_warning(make_problem, check_submission):
    p = make_problem("limit", {"expression": "x^2 sin(1/x)", "point": "0"}, "0", topic="limits")
    verdict = check_submission(p, "x^2", answer="0")
    assert verdict.steps[0].status is StepStatus.WARNING
    assert verdict.status is VerdictStatus.CORRECT


def test_answer_words(make_problem, check_submission):
    p = make_problem("limit", {"expression": "1/x^2", "point": "0"}, "oo", topic="limits")
    assert check_submission(p, answer="infinity").status is VerdictStatus.CORRECT
    assert check_submission(p, answer="∞").status is VerdictStatus.CORRECT
    assert check_submission(p, answer="does not exist").status is VerdictStatus.PARTIAL
