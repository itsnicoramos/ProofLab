from __future__ import annotations

import pytest
import sympy as sp

from prooflab.engine.algebra import MathContext
from prooflab.engine.checker import get_handler
from prooflab.engine.models import StepStatus, VerdictStatus
from prooflab.engine.topics.calc4.vector_calc import curl, divergence, is_conservative

KW = {"course": "calc4", "topic": "vector_calc"}


def test_div_and_curl_helpers():
    ctx = MathContext.build(["x", "y", "z"])
    x, y, z = (ctx[n] for n in "xyz")
    F = [x * y, y * z, z * x]
    assert divergence(F, [x, y, z]) == x + y + z
    assert curl(F, [x, y, z]) == [-y, -z, -x]
    assert is_conservative([2 * x * y, x**2, sp.Integer(0)], [x, y, z], ctx)
    assert not is_conservative([-y, x], [x, y], ctx)


@pytest.fixture
def div_problem(make_problem):
    return make_problem("divergence", {"field": ["x^2 y", "y z", "x z^2"]}, "2xy + z + 2xz", **KW)


def test_divergence_answers(div_problem, check_submission, verdict_codes):
    assert check_submission(div_problem, answer="2x y + 2x z + z").status is VerdictStatus.CORRECT
    curl_given = check_submission(div_problem, answer="<-y, -z^2, -x^2>")
    assert curl_given.status is VerdictStatus.INCORRECT
    assert "CURL_NOT_DIV" in verdict_codes(curl_given)
    assert "DIV_IS_SCALAR" in verdict_codes(check_submission(div_problem, answer="<1, 2, 3>"))
    assert "DIV_MIXED_PARTIALS" in verdict_codes(
        check_submission(div_problem, answer="x^2 + y + z^2")
    )


def test_curl_component_feedback(make_problem, check_submission, verdict_codes):
    p = make_problem("curl", {"field": ["-y", "x", "z^2"]}, "<0, 0, 2>", **KW)
    verdict = check_submission(p, "<0, 0, 1 + 1>", answer="(0, 0, 2)")
    assert verdict.status is VerdictStatus.CORRECT and verdict.steps[0].status is StepStatus.OK
    flipped = check_submission(p, answer="<0, 0, -2>")
    assert "CURL_SIGN" in verdict_codes(flipped)
    assert "third" in next(h.message for h in flipped.hints if h.code == "CURL_SIGN")
    assert "CURL_IS_VECTOR" in verdict_codes(check_submission(p, answer="2"))
    wrong_size = check_submission(p, answer="<0, 2>")
    assert wrong_size.status is VerdictStatus.INVALID


def test_potential_function(make_problem, check_submission, verdict_codes):
    p = make_problem("potential_function", {"field": ["2xy + z", "x^2", "x"]}, "x^2 y + x z", **KW)
    verdict = check_submission(p, "x^2 y", "x^2 y + x z", answer="x^2 y + x z + 7")
    assert [s.status for s in verdict.steps] == [StepStatus.WARNING, StepStatus.OK]
    assert verdict.status is VerdictStatus.CORRECT
    wrong = check_submission(p, answer="x^2 y")
    assert "POTENTIAL_COMPONENT" in verdict_codes(wrong)
    # The hint names the failing derivative, not the missing term.
    message = next(h.message for h in wrong.hints if h.code == "POTENTIAL_COMPONENT")
    assert "∂f/∂x and ∂f/∂z" in message and "xz" not in message.replace(" ", "")


def test_not_conservative(make_problem, check_submission, verdict_codes):
    p = make_problem("potential_function", {"field": ["-y", "x"]}, "not conservative", **KW)
    assert check_submission(p, answer="Not conservative.").status is VerdictStatus.CORRECT
    assert "NOT_CONSERVATIVE" in verdict_codes(check_submission(p, answer="x y"))
    handler = get_handler("potential_function")
    assert handler.verify_key(p, handler.params(p)) is True


def test_vector_line_integral(make_problem, check_submission, verdict_codes):
    p = make_problem(
        "line_integral",
        {"curve": ["t", "t^2"], "bounds": ["0", "1"], "field": ["y", "x"]},
        "1",
        **KW,
    )
    good = check_submission(p, "t^2 + 2t^2", "t^3", "int(3t^2, t, 0, 1)", answer="1")
    assert [s.status for s in good.steps] == [StepStatus.OK] * 3
    dropped = check_submission(p, "t^2 + t", answer="5/6")
    assert dropped.steps[0].code == "MISSING_DERIVATIVE"
    assert "MISSING_DERIVATIVE" in verdict_codes(dropped)
    bounds = check_submission(p, "int(3t^2, t, 0, 2)", answer="1")
    assert bounds.steps[0].code == "LINE_INTEGRAL_BOUNDS"


def test_scalar_line_integral_needs_exact_value(make_problem, check_submission, verdict_codes):
    p = make_problem(
        "line_integral",
        {"curve": ["cos(t)", "sin(t)", "t"], "bounds": ["0", "2pi"], "scalar": "z"},
        "2sqrt(2) pi^2",
        **KW,
    )
    assert check_submission(p, "sqrt(2) t", answer="2√(2)π²").status is VerdictStatus.CORRECT
    decimal = check_submission(p, answer="27.92")
    assert decimal.status is VerdictStatus.PARTIAL and "INEXACT" in verdict_codes(decimal)
    assert "MISSING_DERIVATIVE" in verdict_codes(check_submission(p, answer="2pi^2"))


def test_line_integral_params_need_one_integrand(make_problem):
    from prooflab.engine.checker import ContentError

    p = make_problem(
        "line_integral",
        {"curve": ["t", "t"], "bounds": ["0", "1"], "field": ["y", "x"], "scalar": "x"},
        "1",
        **KW,
    )
    with pytest.raises(ContentError):
        get_handler("line_integral").params(p)


def test_verify_key_rejects_wrong_keys(make_problem):
    p = make_problem("curl", {"field": ["x y", "y z", "z x"]}, "<y, z, x>", **KW)
    handler = get_handler("curl")
    assert handler.verify_key(p, handler.params(p)) is False
