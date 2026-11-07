from __future__ import annotations

import pytest

from prooflab.engine.checker import ContentError, get_handler
from prooflab.engine.models import StepStatus, VerdictStatus
from prooflab.engine.topics.calc4.diff_eq import prepare_ode_text, wrap_abs_arguments

KW = {"course": "calc4", "topic": "diff_eq"}


def test_prepare_ode_text():
    text = prepare_ode_text("y'' - 3y' + 2y = 0", "y", "x")
    assert "yd2" in text and "yd1" in text and "'" not in text
    assert "yd1" in prepare_ode_text("dy/dx = x y(x)", "y", "x")
    assert "yd2" in prepare_ode_text("d^2y/dx^2 + y = 0", "y", "x")
    assert wrap_abs_arguments("ln|y| = x") == "ln(|y|) = x"


@pytest.fixture
def second_order(make_problem):
    return make_problem(
        "ode_solution", {"ode": "y'' - 3y' + 2y = 0"}, "y = C1 e^x + C2 e^(2x)", **KW
    )


def test_general_solution_any_constant_names(second_order, check_submission):
    for answer in ("y = Ae^x + Be^(2x)", "y(x) = C2 e^(2x) + C1 e^x", "C1 e^x + C2 e^(2x)"):
        assert check_submission(second_order, answer=answer).status is VerdictStatus.CORRECT, answer


def test_constants_must_be_enough_and_independent(second_order, check_submission, verdict_codes):
    one = check_submission(second_order, answer="y = C e^x")
    assert one.status is VerdictStatus.PARTIAL and "NOT_GENERAL" in verdict_codes(one)
    dependent = check_submission(second_order, answer="y = C1 e^x + C2 e^x")
    assert dependent.status is VerdictStatus.PARTIAL
    assert "DEPENDENT_SOLUTIONS" in verdict_codes(dependent)
    redundant = check_submission(second_order, answer="y = (A + B) e^x + C e^(2x)")
    assert redundant.status is VerdictStatus.CORRECT


def test_flipped_roots_and_step_kinds(second_order, check_submission, verdict_codes):
    verdict = check_submission(
        second_order,
        ("characteristic", "r^2 - 3r + 2"),
        ("roots", "r = 2 or r = 1"),
        ("note", "two distinct real roots"),
        answer="y = C1 e^(-x) + C2 e^(-2x)",
    )
    assert [s.status for s in verdict.steps] == [StepStatus.OK, StepStatus.OK, StepStatus.UNCHECKED]
    assert verdict.status is VerdictStatus.INCORRECT
    assert "ROOT_SIGNS" in verdict_codes(verdict)


def test_complex_roots_step(make_problem, check_submission):
    p = make_problem(
        "ode_solution", {"ode": "y'' + 2y' + 5y = 0"}, "y = e^(-x)(C1 cos(2x) + C2 sin(2x))", **KW
    )
    good = check_submission(
        p, ("roots", "r = -1 + 2i, r = -1 - 2i"), answer="y = e^(-x)(A cos 2x + B sin 2x)"
    )
    assert good.status is VerdictStatus.CORRECT
    bad = check_submission(p, ("roots", "r = 1 ± 2i"))
    assert bad.steps[0].code == "CHARACTERISTIC_ROOTS"


def test_implicit_general_solution(make_problem, check_submission, verdict_codes):
    p = make_problem("ode_solution", {"ode": "y' = 2x y"}, "y = C e^(x^2)", **KW)
    assert check_submission(p, answer="ln|y| = x^2 + C").status is VerdictStatus.CORRECT
    assert check_submission(p, answer="ln|y| - x^2 = K").status is VerdictStatus.CORRECT
    wrong = check_submission(p, answer="ln|y| = x^3 + C")
    assert wrong.status is VerdictStatus.INCORRECT and "NOT_A_SOLUTION" in verdict_codes(wrong)


def test_implicit_needs_first_order(second_order, check_submission):
    verdict = check_submission(second_order, answer="y^2 = e^x + C")
    assert verdict.status is VerdictStatus.INVALID


def test_initial_value_problem(make_problem, check_submission, verdict_codes):
    p = make_problem(
        "ode_solution", {"ode": "y' + 2y = 4", "ics": {"y(0)": "5"}}, "y = 2 + 3e^(-2x)", **KW
    )
    assert (
        check_submission(p, "y = 2 + C e^(-2x)", answer="y = 2 + 3e^(-2x)").status
        is VerdictStatus.CORRECT
    )
    left = check_submission(p, answer="y = 2 + C e^(-2x)")
    assert left.status is VerdictStatus.PARTIAL and "CONSTANTS_LEFT" in verdict_codes(left)
    ic = check_submission(p, answer="y = 2 + 5e^(-2x)")
    assert ic.status is VerdictStatus.INCORRECT
    assert any("y(0) = 5" in h.message for h in ic.hints if h.code == "IC_NOT_SATISFIED")
    homogeneous = check_submission(p, "y = 5e^(-2x)", answer="y = 5e^(-2x)")
    assert homogeneous.steps[0].code == "HOMOGENEOUS_ONLY"
    assert "MISSING_PARTICULAR" in verdict_codes(homogeneous)


def test_second_order_ivp(make_problem, check_submission, verdict_codes):
    p = make_problem(
        "ode_solution",
        {"ode": "y'' + y = 0", "ics": {"y(0)": "1", "y'(0)": "2"}},
        "y = cos(x) + 2 sin(x)",
        **KW,
    )
    assert check_submission(p, answer="y = cos x + 2 sin x").status is VerdictStatus.CORRECT
    wrong = check_submission(p, answer="y = cos x + sin x")
    assert any("y'(0) = 2" in h.message for h in wrong.hints if h.code == "IC_NOT_SATISFIED")


def test_content_errors(make_problem):
    handler = get_handler("ode_solution")
    bad_ics = make_problem(
        "ode_solution", {"ode": "y'' + y = 0", "ics": {"y(0)": "1"}}, "y = cos(x)", **KW
    )
    with pytest.raises(ContentError):
        handler.validate(bad_ics, handler.params(bad_ics))
    no_derivative = make_problem("ode_solution", {"ode": "y = x"}, "y = x", **KW)
    with pytest.raises(ContentError):
        handler.validate(no_derivative, handler.params(no_derivative))
    wrong_key = make_problem("ode_solution", {"ode": "y' = y"}, "y = C e^(2x)", **KW)
    assert handler.verify_key(wrong_key, handler.params(wrong_key)) is False
