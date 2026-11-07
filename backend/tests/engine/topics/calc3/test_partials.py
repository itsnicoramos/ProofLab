from __future__ import annotations

import pytest
import sympy as sp

from prooflab.engine.algebra import MathContext
from prooflab.engine.checker import ContentError, get_handler
from prooflab.engine.models import StepStatus, VerdictStatus
from prooflab.engine.topics.calc3.partials import (
    _plane_coeffs,
    _proportional,
    is_vector_text,
    strip_partial_label,
)

COURSE = {"course": "calc3", "topic": "partials"}


def test_strip_partial_label():
    assert strip_partial_label("f_x(1, 2) = 4") == " 4"
    assert strip_partial_label("∂f/∂x = 2x").strip() == "2x"
    assert strip_partial_label("2x + y") == "2x + y"


def test_is_vector_text():
    assert is_vector_text("<2x, 3y>")
    assert is_vector_text("∇f = (1, 2)")
    assert not is_vector_text("(x + 1)")


def test_partial_derivative(make_problem, check_submission, verdict_codes):
    p = make_problem(
        "partial_derivative",
        {"function": "x^2 y + y^3", "respect": ["x"]},
        "2x y",
        **COURSE,
    )
    assert check_submission(p, "∂f/∂x = 2xy", answer="f_x = 2xy").status is VerdictStatus.CORRECT
    assert "WRONG_VARIABLE" in verdict_codes(check_submission(p, answer="x^2 + 3y^2"))
    assert "NOT_CONSTANT" in verdict_codes(check_submission(p, answer="2xy + x^2 + 3y^2"))


def test_mixed_partial_steps_pass_through_intermediates(
    make_problem, check_submission, verdict_codes
):
    p = make_problem(
        "partial_derivative",
        {"function": "x^3 y^2", "respect": ["x", "y"]},
        "6x^2 y",
        **COURSE,
    )
    verdict = check_submission(p, "f_x = 3x^2 y^2", "f_xy = 6x^2 y", answer="6x^2 y")
    assert [s.status for s in verdict.steps] == [StepStatus.OK, StepStatus.OK]
    assert verdict.status is VerdictStatus.CORRECT
    assert "PARTIAL_INCOMPLETE" in verdict_codes(check_submission(p, answer="3x^2 y^2"))


def test_gradient(make_problem, check_submission, verdict_codes):
    p = make_problem("gradient", {"function": "x^2 + x y^3"}, "<2x + y^3, 3x y^2>", **COURSE)
    assert check_submission(p, answer="∇f = (2x + y^3, 3xy^2)").status is VerdictStatus.CORRECT
    assert "COMPONENTS_SWAPPED" in verdict_codes(check_submission(p, answer="<3xy^2, 2x + y^3>"))
    assert "VECTOR_LENGTH" in verdict_codes(check_submission(p, answer="<2x + y^3, 3xy^2, 0>"))
    wrong_second = check_submission(p, answer="<2x + y^3, y^3>")
    assert "VECTOR_COMPONENT" in verdict_codes(wrong_second)


def test_gradient_at_a_point(make_problem, check_submission, verdict_codes):
    p = make_problem("gradient", {"function": "x y^2", "at": ["1", "3"]}, "<9, 6>", **COURSE)
    verdict = check_submission(p, "<y^2, 2xy>", "<9, 6>", answer="<9, 6>")
    assert verdict.status is VerdictStatus.CORRECT
    assert "NOT_EVALUATED_AT_POINT" in verdict_codes(check_submission(p, answer="<y^2, 2xy>"))


def test_directional_derivative(make_problem, check_submission, verdict_codes):
    p = make_problem(
        "directional_derivative",
        {"function": "x y", "at": ["1", "2"], "direction": ["1", "1"]},
        "3/sqrt(2)",
        **COURSE,
    )
    assert check_submission(p, answer="3sqrt(2)/2").status is VerdictStatus.CORRECT
    assert "NOT_UNIT_VECTOR" in verdict_codes(check_submission(p, answer="3"))
    assert check_submission(p, answer="2.1213").status is VerdictStatus.PARTIAL


def test_plane_helpers():
    ctx = MathContext.build(["x", "y", "z"])
    X = [ctx["x"], ctx["y"], ctx["z"]]
    plane = _plane_coeffs(ctx.parse("2x + 4y - z - 3"), X)
    assert plane == [2, 4, -1, -3]
    assert _plane_coeffs(ctx.parse("x^2 + z"), X) is None
    assert _proportional([sp.Integer(-4), -8, 2, 6], plane)
    assert not _proportional([sp.Integer(2), 4, -1, 0], plane)


def test_tangent_plane(make_problem, check_submission, verdict_codes):
    p = make_problem(
        "tangent_plane", {"function": "x y", "at": ["2", "3"]}, "z = 3x + 2y - 6", **COURSE
    )
    assert check_submission(p, answer="6x + 4y - 2z = 12").status is VerdictStatus.CORRECT
    assert "PLANE_WRONG_POINT" in verdict_codes(check_submission(p, answer="z = 3x + 2y"))
    assert "PLANE_WRONG_NORMAL" in verdict_codes(
        check_submission(p, answer="z - 6 = 2(x - 2) + 3(y - 3)")
    )
    assert "NOT_A_PLANE" in verdict_codes(check_submission(p, answer="z = xy"))
    steps = check_submission(
        p, "f_x = y", "f_x(2, 3) = 3", "z - 6 = 3(x - 2) + 2(y - 3)", answer="z = 3x + 2y - 6"
    )
    assert [s.status for s in steps.steps] == [StepStatus.OK] * 3


def test_tangent_plane_surface_validation(make_problem):
    handler = get_handler("tangent_plane")
    good = make_problem(
        "tangent_plane",
        {"surface": "x^2 + y^2 + z^2 = 3", "at": ["1", "1", "1"]},
        "x + y + z = 3",
        **COURSE,
    )
    assert handler.verify_key(good, handler.params(good)) is True
    off_surface = make_problem(
        "tangent_plane",
        {"surface": "x^2 + y^2 + z^2 = 3", "at": ["1", "1", "2"]},
        "x + y + z = 3",
        **COURSE,
    )
    with pytest.raises(ContentError):
        handler.validate(off_surface, handler.params(off_surface))


def test_verify_key_catches_a_wrong_key(make_problem):
    handler = get_handler("partial_derivative")
    p = make_problem("partial_derivative", {"function": "x^2 y", "respect": ["y"]}, "2xy", **COURSE)
    assert handler.verify_key(p, handler.params(p)) is False
