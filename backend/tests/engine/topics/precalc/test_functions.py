from __future__ import annotations

import pytest

from prooflab.engine.algebra import MathContext
from prooflab.engine.models import StepStatus, VerdictStatus
from prooflab.engine.topics.precalc.functions import (
    is_cancelled,
    is_factored,
    is_lowest_terms,
    is_single_fraction,
)


@pytest.fixture
def problem(make_problem):
    def build(kind, data, answer, **kw):
        return make_problem(kind, data, answer, course="precalc", topic="functions", **kw)

    return build


def test_form_predicates():
    ctx = MathContext.build({"x": "real", "h": "real"})
    p = ctx.parse
    assert is_factored(p("2x(x-2)(x+2)")) and not is_factored(p("2x(x^2 - 4)"))
    assert is_single_fraction(p("(x+1)/x")) and not is_single_fraction(p("1 + 1/x"))
    assert is_lowest_terms(p("(x-3)/(x+3)")) and not is_lowest_terms(p("(x^2-9)/(x^2+6x+9)"))
    assert is_cancelled(p("2x + h"), ctx["h"]) and not is_cancelled(
        p("((x+h)^2 - x^2)/h"), ctx["h"]
    )


def test_composition_order_and_form(problem, check_submission, verdict_codes):
    p = problem("expression", {"compose": ["x^2", "x + 1"], "form": "expanded"}, "x^2 + 2x + 1")
    assert check_submission(p, answer="x^2 + 2x + 1").status is VerdictStatus.CORRECT
    partial = check_submission(p, answer="(x+1)^2")
    assert partial.status is VerdictStatus.PARTIAL
    assert "FORM_NOT_EXPANDED" in verdict_codes(partial)
    assert check_submission(p, answer="x^2 + 1").status is VerdictStatus.INCORRECT


def test_exact_value_rejects_unevaluated_and_decimal(make_problem, check_submission, verdict_codes):
    p = make_problem(
        "expression",
        {"variables": {}, "expression": "cos(pi/4)", "form": "exact", "forbid": ["cos"]},
        "sqrt(2)/2",
        course="precalc",
        topic="trig",
    )
    assert check_submission(p, answer="1/sqrt(2)").status is VerdictStatus.CORRECT
    assert "FORM_NOT_EVALUATED" in verdict_codes(check_submission(p, answer="cos(pi/4)"))
    assert "INEXACT" in verdict_codes(check_submission(p, answer="0.7071"))


def test_inverse_function(problem, check_submission, verdict_codes):
    p = problem("inverse_function", {"function": "3x - 6"}, "(x + 6)/3")
    verdict = check_submission(p, "y = 3x - 6", "x = 3y - 6", answer="x/3 + 2")
    assert verdict.status is VerdictStatus.CORRECT
    assert [s.status for s in verdict.steps] == [StepStatus.OK, StepStatus.OK]
    assert "RECIPROCAL_NOT_INVERSE" in verdict_codes(check_submission(p, answer="1/(3x - 6)"))
    assert "INVERSE_NOT_SWAPPED" in verdict_codes(check_submission(p, answer="3x - 6"))


def test_inverse_respects_branch(problem, check_submission, verdict_codes):
    p = problem(
        "inverse_function",
        {"function": "x^2", "domain": "real[0, 3]", "range": "real[0, 9]"},
        "sqrt(x)",
    )
    assert check_submission(p, answer="sqrt(x)").status is VerdictStatus.CORRECT
    wrong = check_submission(p, answer="-sqrt(x)")
    assert wrong.status is VerdictStatus.INCORRECT
    assert "INVERSE_BRANCH" in verdict_codes(wrong)


def test_domain_hints(problem, check_submission, verdict_codes):
    p = problem("domain", {"function": "1/sqrt(x - 1)"}, "(1, oo)")
    assert check_submission(p, answer="x > 1").status is VerdictStatus.CORRECT
    assert "ENDPOINTS" in verdict_codes(check_submission(p, answer="[1, oo)"))
    assert "DOMAIN_TOO_LARGE" in verdict_codes(check_submission(p, answer="all real numbers"))
    assert "DOMAIN_TOO_SMALL" in verdict_codes(check_submission(p, answer="(2, oo)"))
    assert check_submission(p, answer="(1, oo").status is VerdictStatus.INVALID


def test_domain_key_verified_by_sympy(problem):
    from prooflab.engine.checker import get_handler

    good = problem("domain", {"function": "ln(x - 3)"}, "(3, oo)")
    bad = problem("domain", {"function": "ln(x - 3)"}, "[3, oo)")
    handler = get_handler("domain")
    assert handler.verify_key(good, handler.params(good)) is True
    assert handler.verify_key(bad, handler.params(bad)) is False


def test_expression_key_must_match_data(problem):
    from prooflab.engine.checker import get_handler

    handler = get_handler("expression")
    p = problem("expression", {"compose": ["x^2", "x + 1"]}, "x^2 + 1")
    assert handler.verify_key(p, handler.params(p)) is False
