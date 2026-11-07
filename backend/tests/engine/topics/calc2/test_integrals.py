from __future__ import annotations

import pytest
import sympy as sp

from prooflab.engine.algebra import MathContext
from prooflab.engine.models import StepStatus, VerdictStatus
from prooflab.engine.topics.calc2.integrals import Frame, derivative, make_sub_frame


@pytest.fixture
def anti(make_problem):
    def build(integrand, answer, **data):
        return make_problem(
            "antiderivative",
            {"integrand": integrand, **data},
            answer,
            course="calc2",
            topic="integrals",
        )

    return build


@pytest.fixture
def definite(make_problem):
    def build(integrand, lower, upper, answer):
        data = {"integrand": integrand, "lower": lower, "upper": upper}
        return make_problem("definite_integral", data, answer, course="calc2", topic="integrals")

    return build


def _frame(integrand: str = "x e^x") -> Frame:
    ctx = MathContext.build(["x"], constants=["C"], allow_integral=True)
    return Frame(ctx, ctx["x"], ctx["x"], ctx.parse(integrand))


def test_derivative_handles_unevaluated_integrals():
    frame = _frame()
    step = frame.ctx.parse("x e^x - int(e^x, x)")
    assert sp.simplify(derivative(step, frame) - frame.integrand) == 0


def test_forward_substitution_frame():
    base = _frame("2x (x^2 + 1)^3")
    frame = make_sub_frame("u = x^2 + 1", base)
    step = frame.ctx.parse("int(u^3, u)")
    assert sp.simplify(derivative(step, frame) - base.integrand) == 0


def test_inverse_substitution_compares_in_the_new_variable():
    base = _frame("1/(x^2 + 4)")
    frame = make_sub_frame("x = 2 tan(t)", base)
    assert frame.inverse and str(frame.base) == "t"
    step = frame.ctx.parse("t/2")
    assert sp.simplify(derivative(step, frame) - frame.integrand) == 0


def test_any_antiderivative_form_is_accepted(anti, check_submission):
    p = anti("sin(x) cos(x)", "sin(x)^2/2 + C")
    for answer in ("sin(x)^2/2 + C", "-cos(x)^2/2 + C", "-cos(2x)/4 + K"):
        assert check_submission(p, answer=answer).status is VerdictStatus.CORRECT, answer


def test_missing_constant_and_log_abs(anti, check_submission, verdict_codes):
    p = anti("1/x", "ln(|x|) + C")
    assert "MISSING_C" in verdict_codes(check_submission(p, answer="ln(|x|)"))
    assert "LOG_ABS" in verdict_codes(check_submission(p, answer="ln(x) + C"))
    positive = anti("1/x", "ln(|x|) + C", variables={"x": "positive"})
    assert check_submission(positive, answer="ln(x) + C").status is VerdictStatus.CORRECT


def test_factor_and_sign_hints(anti, check_submission, verdict_codes):
    p = anti("cos(3x)", "sin(3x)/3 + C")
    assert "INTEGRAL_FACTOR" in verdict_codes(check_submission(p, answer="sin(3x) + C"))
    assert "INTEGRAL_SIGN" in verdict_codes(check_submission(p, answer="-sin(3x)/3 + C"))
    assert "DIFFERENTIATED_INSTEAD" in verdict_codes(check_submission(p, answer="-3 sin(3x)"))


def test_substitution_steps(anti, check_submission, verdict_codes):
    p = anti("2x e^(x^2)", "e^(x^2) + C")
    v = check_submission(
        p, ("sub", "u = x^2"), ("sub", "du = 2x dx"), "int(e^u, u)", answer="e^(x^2) + C"
    )
    assert [s.status for s in v.steps] == [StepStatus.OK] * 3
    v = check_submission(p, ("sub", "u = x^2"), ("sub", "du = x dx"), answer="e^(x^2) + C")
    assert v.steps[1].status is StepStatus.ERROR
    v = check_submission(p, ("sub", "u = x^2"), answer="e^u + C")
    assert "BACK_SUBSTITUTE" in verdict_codes(v)
    v = check_submission(p, ("sub", "u = x^2"), ("sub", "w = x"), answer="e^(x^2) + C")
    assert "INTEGRAL_ONE_SUB" in verdict_codes(v)


def test_bad_substitution_is_reported(anti, check_submission, verdict_codes):
    p = anti("2x e^(x^2)", "e^(x^2) + C")
    v = check_submission(p, ("sub", "u = 5"), answer="e^(x^2) + C")
    assert v.steps[0].status is StepStatus.ERROR
    assert "INTEGRAL_BAD_SUB" in verdict_codes(v)


def test_definite_integral_values_and_bounds(definite, check_submission, verdict_codes):
    p = definite("x sqrt(x^2 + 9)", "0", "4", "98/3")
    good = check_submission(p, ("sub", "u = x^2 + 9"), "int(sqrt(u)/2, u, 9, 25)", answer="98/3")
    assert good.status is VerdictStatus.CORRECT
    stale = check_submission(p, ("sub", "u = x^2 + 9"), "int(sqrt(u)/2, u, 0, 4)", answer="8/3")
    assert "BOUNDS_NOT_CHANGED" in verdict_codes(stale)
    assert check_submission(p, answer="32.667").status is VerdictStatus.PARTIAL


def test_improper_integrals(definite, check_submission):
    conv = definite("e^(-x)", "0", "oo", "1")
    assert (
        check_submission(conv, "int(e^(-x), x, 0, oo)", answer="1").status is VerdictStatus.CORRECT
    )
    div = definite("1/sqrt(x)", "1", "oo", "diverges")
    assert check_submission(div, answer="divergent").status is VerdictStatus.CORRECT
    assert check_submission(div, answer="oo").status is VerdictStatus.CORRECT
    assert check_submission(div, answer="2").status is VerdictStatus.INCORRECT


def test_answer_key_must_have_constant(anti):
    from prooflab.engine.checker import ContentError, get_handler

    p = anti("2x", "x^2")
    handler = get_handler("antiderivative")
    with pytest.raises(ContentError):
        handler.validate(p, handler.params(p))
