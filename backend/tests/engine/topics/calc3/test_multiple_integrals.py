from __future__ import annotations

import math

import pytest
import sympy as sp

from prooflab.engine.algebra import MathContext
from prooflab.engine.checker import get_handler
from prooflab.engine.models import StepStatus, VerdictStatus
from prooflab.engine.topics.calc3.multiple_integrals import (
    bounds_problem,
    closed_value,
    iterated_quad,
)

COURSE = {"course": "calc3", "topic": "multiple_integrals"}
CTX = MathContext.build(
    {"x": "real", "y": "real", "r": "positive", "theta": "real"}, allow_integral=True
)
X, Y, R, T = CTX["x"], CTX["y"], CTX["r"], CTX["theta"]


@pytest.mark.parametrize(
    ("integrand", "limits", "expected"),
    [
        (sp.Integer(1), [(Y, 0, sp.sqrt(1 - X**2)), (X, 0, 1)], math.pi / 4),
        (X * Y, [(Y, 0, X), (X, 0, 1)], 1 / 8),
        (sp.exp(X**2), [(X, Y, 1), (Y, 0, 1)], (math.e - 1) / 2),
        (R, [(R, 0, 2), (T, 0, 2 * sp.pi)], 4 * math.pi),
    ],
)
def test_iterated_quad(integrand, limits, expected):
    assert iterated_quad(integrand, limits) == pytest.approx(expected, rel=1e-10)


def test_iterated_quad_refuses_free_symbols():
    assert iterated_quad(X * Y, [(Y, 0, 1)]) is None


def test_closed_value_handles_arithmetic_around_integrals():
    assert closed_value(CTX.parse("2 int(int(x y, y, 0, x), x, 0, 1) + 1")) == pytest.approx(1.25)
    assert closed_value(CTX.parse("pi/4")) == pytest.approx(math.pi / 4)


def test_bounds_problem():
    assert not bounds_problem([(Y, 0, X), (X, 0, 1)])
    assert bounds_problem([(Y, 0, Y), (X, 0, 1)])
    assert bounds_problem([(Y, 0, 1), (X, 0, Y)])


@pytest.fixture
def triangle(make_problem):
    return make_problem(
        "iterated_integral",
        {"integrand": "x + y", "bounds": [["y", "0", "x"], ["x", "0", "1"]]},
        "1/2",
        **COURSE,
    )


def test_iterated_steps_follow_the_stages(triangle, check_submission):
    verdict = check_submission(triangle, "x + y", "3x^2/2", "int(3x^2/2, x, 0, 1)", answer="1/2")
    assert [s.status for s in verdict.steps] == [StepStatus.OK] * 3
    assert verdict.status is VerdictStatus.CORRECT


def test_iterated_wrong_inner_result(triangle, check_submission, verdict_codes):
    verdict = check_submission(triangle, "x^2/2", answer="1/6")
    assert verdict.steps[0].status is StepStatus.ERROR
    assert "ITERATED_STEP_WRONG" in verdict_codes(verdict)


def test_iterated_answer_must_be_a_number(triangle, check_submission, verdict_codes):
    verdict = check_submission(triangle, answer="int(3x^2/2, x, 0, 1)")
    assert "ANSWER_HAS_INTEGRAL" in verdict_codes(verdict)


@pytest.fixture
def reverse(make_problem):
    return make_problem(
        "integral_setup",
        {"integrand": "x y", "region": [["y", "0", "x"], ["x", "0", "2"]], "order": ["x", "y"]},
        "int(int(x y, x, y, 2), y, 0, 2)",
        **COURSE,
    )


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        ("int(int(x y, x, 0, y), y, 0, 2)", "REVERSED_LIMITS_ONLY"),
        ("int(int(x y, x, 2, y), y, 0, 2)", "LIMITS_BACKWARDS"),
        ("int(int(x y, x, y, 2), y, 0, 1)", "REGION_MISMATCH"),
        ("int(int(x y, y, 0, x), x, 0, 2)", "INTEGRATION_ORDER"),
        ("int(int(x y, x, x, 2), y, 0, 2)", "SETUP_BOUNDS"),
        ("int(int(x + y, x, y, 2), y, 0, 2)", "INTEGRAND_CHANGED"),
        ("2", "SETUP_NOT_ITERATED"),
    ],
)
def test_setup_diagnostics(reverse, check_submission, verdict_codes, answer, code):
    verdict = check_submission(reverse, answer=answer)
    assert verdict.status is VerdictStatus.INCORRECT
    assert code in verdict_codes(verdict)


def test_setup_correct_with_notes_and_value_step(reverse, check_submission):
    verdict = check_submission(
        reverse, ("note", "sketch: triangle"), "2", answer="int(int(x y, x, y, 2), y, 0, 2)"
    )
    assert [s.status for s in verdict.steps] == [StepStatus.UNCHECKED, StepStatus.OK]
    assert verdict.status is VerdictStatus.CORRECT


@pytest.fixture
def polar(make_problem):
    return make_problem(
        "integral_setup",
        {
            "integrand": "1",
            "region": [["y", "-sqrt(1 - x^2)", "sqrt(1 - x^2)"], ["x", "-1", "1"]],
            "order": ["r", "theta"],
            "coordinates": "polar",
        },
        "int(int(r, r, 0, 1), theta, 0, 2pi)",
        **COURSE,
    )


def test_polar_setup(polar, check_submission, verdict_codes):
    assert (
        check_submission(polar, answer="int(int(r, r, 0, 1), θ, 0, 2π)").status
        is VerdictStatus.CORRECT
    )
    assert "MISSING_JACOBIAN" in verdict_codes(
        check_submission(polar, answer="int(int(1, r, 0, 1), theta, 0, 2pi)")
    )
    cartesian = "int(int(1, y, -sqrt(1 - x^2), sqrt(1 - x^2)), x, -1, 1)"
    assert "WRONG_COORDINATES" in verdict_codes(check_submission(polar, answer=cartesian))


def test_setup_verify_key(polar, make_problem):
    handler = get_handler("integral_setup")
    assert handler.verify_key(polar, handler.params(polar)) is True
    bad = make_problem(
        "integral_setup",
        {**polar.data},
        "int(int(r, r, 0, 1), theta, 0, pi)",
        **COURSE,
    )
    assert handler.verify_key(bad, handler.params(bad)) is False
