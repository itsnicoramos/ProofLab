from __future__ import annotations

import pytest

from prooflab.engine.checker import ContentError, get_handler
from prooflab.engine.models import StepStatus, VerdictStatus

PRODUCT_KEY = "{(1, a), (1, c), (2, a), (2, c), (3, a), (3, c), (4, a), (4, c)}"


def _set_problem(make_problem, data, answer, **kw):
    return make_problem("finite_set", data, answer, course="proofs", topic="sets", **kw)


@pytest.fixture
def product(make_problem):
    data = {"sets": {"A": "{1, 2, 3, 4}", "B": "{a, c}"}, "atoms": ["a", "c"], "compute": "A × B"}
    return _set_problem(make_problem, data, PRODUCT_KEY)


@pytest.fixture
def complement(make_problem):
    data = {
        "sets": {"A": "{4, 3, 6, 7, 1, 9}", "B": "{5, 6, 8, 4}", "U": "{0, 1, ..., 10}"},
        "universe": "U",
        "compute": "A' ∩ B",
    }
    return _set_problem(make_problem, data, "{5, 8}")


def test_correct_set_in_any_order(check_submission, product):
    shuffled = "{(4, c), (1, a), (2, c), (1, c), (3, a), (2, a), (3, c), (4, a), (1, a)}"
    v = check_submission(product, answer=shuffled)
    assert v.status is VerdictStatus.CORRECT and v.score == 1.0


def test_reversed_pairs(check_submission, verdict_codes, product):
    v = check_submission(product, answer=PRODUCT_KEY.replace("(1, a)", "(a, 1)"))
    assert v.status is VerdictStatus.INCORRECT
    reversed_all = "{(a, 1), (c, 1), (a, 2), (c, 2), (a, 3), (c, 3), (a, 4), (c, 4)}"
    v = check_submission(product, answer=reversed_all)
    assert "SET_PAIRS_REVERSED" in verdict_codes(v)


def test_missing_and_extra_elements(check_submission, verdict_codes, product):
    v = check_submission(product, answer="{(1, a), (1, c), (5, a)}")
    codes = verdict_codes(v)
    assert {"SET_MISSING", "SET_EXTRA"} <= codes
    extra = next(h for h in v.hints if h.code == "SET_EXTRA")
    assert "(5, a)" in extra.message and "(2, a)" not in extra.message
    missing = next(h for h in v.hints if h.code == "SET_MISSING")
    assert "6" in missing.message


def test_wrong_shape(check_submission, verdict_codes, product):
    assert "SET_TUPLE_LENGTH" in verdict_codes(check_submission(product, answer="{1, 2, a}"))
    v = check_submission(product, answer="(1, a), (1, c)")
    assert v.status is VerdictStatus.INVALID and v.answer.code == "SET_NOT_A_LIST"


def test_steps_are_equations_between_sets(check_submission, verdict_codes, complement):
    v = check_submission(
        complement,
        "A' = {0, 2, 5, 8, 10}",
        "A' ∩ B = {0, 2, 5, 8, 10} ∩ {5, 6, 8, 4} = {5, 8}",
        answer="{5, 8}",
    )
    assert v.status is VerdictStatus.CORRECT, v
    assert [s.status for s in v.steps] == [StepStatus.OK, StepStatus.OK]

    v = check_submission(complement, "A' = {0, 2, 5, 8}", answer="{5, 8}")
    assert v.status is VerdictStatus.PARTIAL and v.steps[0].status is StepStatus.ERROR
    assert {"SET_STEP_NOT_EQUAL", "SET_MISSING", "STEP_ERRORS"} <= verdict_codes(v)


def test_unlabeled_and_note_steps_are_not_counted(check_submission, complement):
    v = check_submission(complement, "{5, 8}", ("note", "complement first"), answer="{5, 8}")
    assert v.status is VerdictStatus.CORRECT
    assert [s.status for s in v.steps] == [StepStatus.UNCHECKED, StepStatus.UNCHECKED]


def test_step_errors(check_submission, verdict_codes, complement):
    v = check_submission(complement, "A' ∪ B ∩ A = {1}", "|A| = {1}", "C = {1}")
    assert [s.status for s in v.steps] == [StepStatus.ERROR] * 3
    assert {"SET_MIXED_OPERATORS", "SET_STEP_MIXED", "SET_UNKNOWN_NAME"} <= verdict_codes(v)


def test_answer_cannot_be_an_expression(check_submission, complement):
    v = check_submission(complement, answer="A' ∩ B")
    assert v.status is VerdictStatus.INVALID


def test_power_set_hints(check_submission, verdict_codes, make_problem):
    p = _set_problem(make_problem, {"compute": "P({1, 2})"}, "{∅, {1}, {2}, {1, 2}}")
    assert check_submission(p, answer="{{}, {2}, {1}, {2, 1}}").status is VerdictStatus.CORRECT
    v = check_submission(p, answer="{{1}, {2}, {1, 2}}")
    assert {"SET_EMPTY_MISSING", "SET_MISSING"} <= verdict_codes(v)
    v = check_submission(p, answer="{{∅, {1}, {2}, {1, 2}}}")
    assert "SET_BRACES" in verdict_codes(v)


def test_tuple_grouping_hint(check_submission, verdict_codes, make_problem):
    data = {"sets": {"A": "{1, 2}", "B": "{a}"}, "atoms": ["a"], "compute": "(A × B) × B"}
    p = _set_problem(make_problem, data, "{((1, a), a), ((2, a), a)}")
    v = check_submission(p, answer="{(1, a, a), (2, a, a)}")
    assert "SET_TUPLE_GROUPING" in verdict_codes(v)


def test_cardinality(check_submission, verdict_codes, make_problem):
    data = {"compute": "{{1}, {2, {3, 4}}, ∅}", "ask": "cardinality"}
    p = _set_problem(make_problem, data, "3")
    assert check_submission(p, answer="3").status is VerdictStatus.CORRECT
    v = check_submission(p, answer="4")
    assert v.status is VerdictStatus.INCORRECT and "SET_COUNT_INNER" in verdict_codes(v)
    assert check_submission(p, answer="three").status is VerdictStatus.INVALID
    v = check_submission(p, "|{{1}, {2, {3, 4}}, ∅}| = 3", answer="3")
    assert v.status is VerdictStatus.CORRECT and v.steps[0].status is StepStatus.OK


def test_naturals_start_at_one(check_submission, verdict_codes, make_problem):
    builder = {"var": "x", "domain": "N", "where": ["x^2 < 10"]}
    p = _set_problem(make_problem, {"compute": builder}, "{1, 2, 3}")
    v = check_submission(p, answer="{0, 1, 2, 3}")
    assert "SET_NATURALS_ZERO" in verdict_codes(v)
    q = _set_problem(make_problem, {"compute": builder, "ask": "cardinality"}, "3")
    assert "SET_NATURALS_ZERO" in verdict_codes(check_submission(q, answer="4"))


def test_known_mistakes(check_submission, verdict_codes, make_problem):
    p = _set_problem(
        make_problem,
        {"compute": "{1, 2} ∩ {2, 3}"},
        "{2}",
        mistakes=[("{1, 2, 3}", "That's the union.")],
    )
    v = check_submission(p, answer="{3, 2, 1}")
    assert "KNOWN_MISTAKE" in verdict_codes(v)


def test_verify_key_and_validation(make_problem, product):
    handler = get_handler("finite_set")
    assert handler.verify_key(product, handler.params(product)) is True
    wrong = _set_problem(make_problem, product.data, "{(1, a)}")
    assert handler.verify_key(wrong, handler.params(wrong)) is False
    no_compute = _set_problem(make_problem, {}, "{0}")
    assert handler.verify_key(no_compute, handler.params(no_compute)) is None
    for data, answer in [
        ({"compute": "A"}, "{1}"),  # unknown set
        ({"sets": {"A": "{1}"}, "universe": "U", "compute": "A"}, "{1}"),  # unknown universe
        ({"compute": "{1}"}, "1, 2"),  # key isn't a list
        ({"compute": "{1}", "ask": "cardinality"}, "{1}"),  # key isn't a count
    ]:
        bad = _set_problem(make_problem, data, answer)
        with pytest.raises(ContentError):
            handler.validate(bad, handler.params(bad))


def test_has_answer(product):
    handler = get_handler("finite_set")
    assert handler.has_answer(product, handler.params(product))
