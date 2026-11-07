from __future__ import annotations

import pytest
import sympy as sp

from prooflab.engine.models import StepStatus, VerdictStatus
from prooflab.engine.topics.calc2.series import (
    ABSOLUTELY,
    CONVERGES,
    DIVERGES,
    NOT_ABSOLUTELY,
    geometric_ratio,
    normalize_test,
    p_value,
    parse_convergence,
    run_test,
    series_context,
    taylor,
)


@pytest.fixture
def conv(make_problem):
    def build(term, answer, start=1):
        data = {"term": term, "start": start}
        return make_problem("series_convergence", data, answer, course="calc2", topic="series")

    return build


def _term(text: str, start: int = 1):
    ctx = series_context("n", start)
    return ctx.parse(text), ctx["n"]


def test_test_name_aliases():
    assert normalize_test("Ratio Test") == "ratio"
    assert normalize_test("p-series") == "p_series"
    assert normalize_test("the nth term test") == "divergence"
    assert normalize_test("LCT") == "limit_comparison"
    assert normalize_test("alternating series test") == "alternating"
    assert normalize_test("magic") is None


def test_parse_convergence_words():
    assert parse_convergence("Converges absolutely") == (CONVERGES, ABSOLUTELY)
    assert parse_convergence("conditionally convergent") == (CONVERGES, "conditionally")
    assert parse_convergence("does not converge") == (DIVERGES, None)


def test_recognisers():
    a, n = _term("4/n^3")
    assert p_value(a, n) == 3
    b, n = _term("3 (2/5)^n")
    assert geometric_ratio(b, n) == sp.Rational(2, 5)
    c, n = _term("1/(n^2 + 1)")
    assert p_value(c, n) is None


def test_run_test_results():
    a, n = _term("n!/10^n")
    assert run_test("ratio", a, n, 1).facts == {DIVERGES}
    b, n = _term("1/n^2")
    assert run_test("ratio", b, n, 1).inconclusive == "RATIO_TEST_INCONCLUSIVE"
    assert run_test("divergence", b, n, 1).inconclusive == "DIVERGENCE_TEST_INCONCLUSIVE"
    c, n = _term("(-1)^n/sqrt(n)")
    assert run_test("alternating", c, n, 1).facts == {CONVERGES}
    assert run_test("p_series", c, n, 1).facts == {NOT_ABSOLUTELY}
    assert not run_test("alternating", b, n, 1).applies


def test_comparison_needs_right_direction(conv, check_submission, verdict_codes):
    p = conv("1/(n + 2^n)", "converges")
    good = check_submission(p, ("compare", "1/2^n"), ("test", "comparison"), answer="converges")
    assert good.status is VerdictStatus.CORRECT
    weak = check_submission(p, ("compare", "1/n"), ("test", "comparison"), answer="converges")
    assert "COMPARISON_WRONG_DIRECTION" in verdict_codes(weak)
    wobbly = conv("(2 + (-1)^n)/n^2", "converges")
    bad = check_submission(wobbly, ("compare", "2/n^2"), ("test", "comparison"), answer="converges")
    assert "SERIES_COMPARISON_INEQUALITY" in verdict_codes(bad)


def test_limit_step_checks_the_test_limit(conv, check_submission, verdict_codes):
    p = conv("n/3^n", "converges")
    v = check_submission(p, ("test", "ratio"), ("limit", "L = 1/3"), answer="converges")
    assert v.status is VerdictStatus.CORRECT
    v = check_submission(p, ("test", "ratio"), ("limit", "L = 3"), answer="converges")
    assert v.steps[1].status is StepStatus.ERROR
    v = check_submission(p, ("limit", "1/3"), answer="converges")
    assert "SERIES_LIMIT_WITHOUT_TEST" in verdict_codes(v)


def test_unknown_test_is_an_error(conv, check_submission, verdict_codes):
    p = conv("1/n^2", "converges")
    v = check_submission(p, ("test", "vibes"), answer="converges")
    assert "SERIES_UNKNOWN_TEST" in verdict_codes(v)


def test_series_sum_partial_sums(make_problem, check_submission):
    p = make_problem(
        "series_sum",
        {"term": "1/((n + 1)(n + 2))", "start": 0},
        "1",
        course="calc2",
        topic="series",
    )
    v = check_submission(p, "1 - 1/(N + 2)", answer="1")
    assert v.status is VerdictStatus.CORRECT
    v = check_submission(p, "1/n", answer="1")
    assert v.steps[0].status is StepStatus.ERROR


def test_taylor_helper_and_hints(make_problem, check_submission, verdict_codes):
    ctx = series_context("n", 1).extend({"x": "real"})
    x = ctx["x"]
    assert taylor(sp.exp(x), x, sp.Integer(0), 2) == sp.expand(1 + x + x**2 / 2)
    p = make_problem(
        "taylor_polynomial",
        {"function": "e^x", "center": "1", "degree": 2},
        "e + e(x-1) + e(x-1)^2/2",
        course="calc2",
        topic="series",
    )
    assert check_submission(p, answer="e(1 + (x-1) + (x-1)^2/2)").status is VerdictStatus.CORRECT
    assert "WRONG_CENTER" in verdict_codes(check_submission(p, answer="1 + x + x^2/2"))
    assert "MISSING_FACTORIALS" in verdict_codes(
        check_submission(p, answer="e + e(x-1) + e(x-1)^2")
    )
