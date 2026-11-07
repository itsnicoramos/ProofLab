from __future__ import annotations

import pytest

from prooflab.engine.models import StepStatus, VerdictStatus


@pytest.fixture
def product(make_problem):
    return make_problem("derivative", {"function": "x^2 sin(x)"}, "2x sin(x) + x^2 cos(x)")


def test_equivalent_forms_are_accepted(product, check_submission):
    for answer in ("2x sin(x) + x^2 cos(x)", "x(2sin x + x cos x)", "f'(x) = x^2cos(x)+2xsin(x)"):
        assert check_submission(product, answer=answer).status is VerdictStatus.CORRECT, answer


def test_product_rule_detector(product, check_submission, verdict_codes):
    verdict = check_submission(product, answer="2x cos(x)")
    assert verdict.status is VerdictStatus.INCORRECT
    assert "PRODUCT_RULE" in verdict_codes(verdict)


def test_first_wrong_step_is_flagged(product, check_submission):
    verdict = check_submission(
        product, "2x sin(x) + x^2 cos(x)", "2x sin(x) - x^2 cos(x)", answer="2x sin(x) + x^2 cos(x)"
    )
    assert [s.status for s in verdict.steps] == [StepStatus.OK, StepStatus.ERROR]
    assert verdict.status is VerdictStatus.PARTIAL


def test_parsed_input_is_echoed_as_latex(product, check_submission):
    verdict = check_submission(product, answer="2x sin x + x^2 cos x")
    assert verdict.answer is not None and "sin" in (verdict.answer.latex or "")


def test_unknown_variable_is_invalid(product, check_submission):
    verdict = check_submission(product, answer="2t sin(t)")
    assert verdict.status is VerdictStatus.INVALID
    assert verdict.answer is not None and "This problem uses: x" in verdict.answer.message


def test_chain_and_quotient_detectors(make_problem, check_submission, verdict_codes):
    chain = make_problem("derivative", {"function": "e^(x^2)"}, "2x e^(x^2)")
    assert "CHAIN_RULE" in verdict_codes(check_submission(chain, answer="e^(x^2)"))
    quotient = make_problem("derivative", {"function": "sin(x)/x"}, "(x cos(x) - sin(x))/x^2")
    assert "QUOTIENT_RULE" in verdict_codes(
        check_submission(quotient, answer="(sin(x) - x cos(x))/x^2")
    )


def test_authored_hint_is_appended_when_wrong(make_problem, check_submission):
    p = make_problem("derivative", {"function": "x^3"}, "3x^2", hints=["first", "second"])
    verdict = check_submission(p, answer="x^2", hints_revealed=1)
    assert any(h.code == "AUTHORED_HINT" and "second" in h.message for h in verdict.hints)


def test_tangent_line(make_problem, check_submission, verdict_codes):
    p = make_problem("tangent_line", {"function": "x^2", "at": "3"}, "y = 6x - 9")
    assert check_submission(p, answer="y - 9 = 6(x - 3)").status is VerdictStatus.CORRECT
    assert "WRONG_POINT" in verdict_codes(check_submission(p, answer="y = 6x"))
    assert "WRONG_SLOPE" in verdict_codes(check_submission(p, answer="y = 2x + 3"))
    assert "SLOPE_ONLY" in verdict_codes(check_submission(p, answer="6"))


def test_implicit_derivative_is_compared_on_the_curve(make_problem, check_submission):
    p = make_problem("implicit_derivative", {"equation": "x^2 + y^2 = 25"}, "-x/y")
    assert check_submission(p, answer="-x/y").status is VerdictStatus.CORRECT
    assert check_submission(p, answer="x/y").status is VerdictStatus.INCORRECT


def test_tangent_line_step_written_as_y_equals(make_problem, check_submission):
    p = make_problem("tangent_line", {"function": "x^3 - 2x", "at": "1"}, "y = x - 2")
    verdict = check_submission(p, "f'(x) = 3x^2 - 2", "f(1) = -1", "y = x - 2", answer="y = x - 2")
    assert [s.status for s in verdict.steps] == [StepStatus.OK] * 3
    assert verdict.status is VerdictStatus.CORRECT


def test_higher_derivative_steps_may_pass_through_lower_ones(make_problem, check_submission):
    p = make_problem("derivative", {"function": "x^4", "order": 2}, "12x^2")
    verdict = check_submission(p, "f'(x) = 4x^3", "f''(x) = 12x^2", answer="12x^2")
    assert [s.status for s in verdict.steps] == [StepStatus.OK, StepStatus.OK]
    assert "f″(x)" in verdict.steps[1].message
    backwards = check_submission(p, "12x^2", "4x^3", answer="12x^2")
    assert backwards.steps[1].status is StepStatus.ERROR
