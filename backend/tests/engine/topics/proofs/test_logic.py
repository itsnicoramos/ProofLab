from __future__ import annotations

import pytest

from prooflab.engine.checker import ContentError, get_handler
from prooflab.engine.models import StepStatus, VerdictStatus


def _logic(make_problem, kind, data, answer=""):
    return make_problem(kind, data, answer, course="proofs", topic="logic")


@pytest.fixture
def table(make_problem):
    return _logic(make_problem, "truth_table", {"formula": "P ∨ (Q ⇒ R)"}, "T T T T T F T T")


@pytest.fixture
def values(make_problem):
    data = {
        "ask": "values",
        "constraints": [{"formula": "((P ∧ Q) ∨ R) ⇒ (R ∨ S)", "value": False}],
    }
    return _logic(make_problem, "truth_table", data, "P = T, Q = T, R = F, S = F")


@pytest.fixture
def demorgan(make_problem):
    return _logic(make_problem, "logical_equivalence", {"left": "~(P ∨ Q)", "right": "(~P) ∧ (~Q)"})


@pytest.fixture
def decide(make_problem):
    data = {"left": "P ∨ (Q ∧ R)", "right": "(P ∨ Q) ∧ R", "decide": True}
    return _logic(make_problem, "logical_equivalence", data, "not equivalent")


# --------------------------------------------------------------------------- truth_table


def test_column_answer(check_submission, verdict_codes, table):
    for answer in ["TTTTTFTT", "T T T T T F T T", "1 1 1 1 1 0 1 1"]:
        assert check_submission(table, answer=answer).status is VerdictStatus.CORRECT
    v = check_submission(table, answer="T T T T F F T T")
    assert v.status is VerdictStatus.INCORRECT and "TT_ROWS_WRONG" in verdict_codes(v)
    v = check_submission(table, answer="T T T T")
    assert v.status is VerdictStatus.INVALID and v.answer.code == "TT_WRONG_LENGTH"


def test_helper_columns(check_submission, verdict_codes, table):
    v = check_submission(table, ("column", "Q ⇒ R : T F T T T F T T"), answer="TTTTTFTT")
    assert v.status is VerdictStatus.CORRECT and v.steps[0].status is StepStatus.OK
    v = check_submission(table, ("column", "Q ⇒ R : T F F F T F F F"), answer="TTTTTFTT")
    assert v.status is VerdictStatus.PARTIAL
    assert {"TT_COLUMN_WRONG", "IMPLIES_AS_AND"} <= verdict_codes(v)
    v = check_submission(table, ("column", "Q ⇒ R"), ("column", "S : TTTTTTTT"))
    assert [s.status for s in v.steps] == [StepStatus.ERROR, StepStatus.ERROR]
    assert "TT_STEP_FORMAT" in verdict_codes(v)


def test_column_diagnostics(check_submission, verdict_codes, make_problem):
    p = _logic(make_problem, "truth_table", {"formula": "~(P ⇒ Q)"}, "F T F F")
    assert "TT_ALL_FLIPPED" in verdict_codes(check_submission(p, answer="T F T T"))
    assert "TT_ROW_ORDER" in verdict_codes(check_submission(p, answer="F F T F"))
    q = _logic(make_problem, "truth_table", {"formula": "P ⇒ Q"}, "T F T T")
    assert "IMPLIES_AS_AND" in verdict_codes(check_submission(q, answer="T F F F"))


def test_values_answer(check_submission, verdict_codes, values):
    v = check_submission(values, answer="P = T, Q = T, R = F, S = F")
    assert v.status is VerdictStatus.CORRECT
    assert check_submission(values, answer="P=T Q=T R=F S=F").status is VerdictStatus.CORRECT
    v = check_submission(values, answer="P = F, Q = T, R = F, S = F")
    assert v.status is VerdictStatus.INCORRECT and "LOGIC_VALUES_WRONG" in verdict_codes(v)
    v = check_submission(values, answer="P = T, Q = T")
    assert v.status is VerdictStatus.INVALID and v.answer.code == "LOGIC_VALUES_MISSING"


def test_values_with_a_given_fact(check_submission, make_problem):
    data = {
        "ask": "values",
        "constraints": [
            {"formula": "P", "value": False},
            {"formula": "(R ⇒ S) ⇔ (P ∧ Q)", "value": True},
        ],
        "solve_for": ["R", "S"],
    }
    p = _logic(make_problem, "truth_table", data, "R = T, S = F")
    assert check_submission(p, answer="R = T, S = F").status is VerdictStatus.CORRECT
    assert check_submission(p, answer="R = F, S = F").status is VerdictStatus.INCORRECT


def test_truth_table_validation(make_problem, table):
    handler = get_handler("truth_table")
    assert handler.verify_key(table, handler.params(table)) is True
    wrong = _logic(make_problem, "truth_table", table.data, "T T T T T T T T")
    assert handler.verify_key(wrong, handler.params(wrong)) is False
    for data, answer in [
        ({"formula": "P ∨ Q ∧ R"}, "TTTT"),  # ambiguous
        ({"formula": "P ∨ Q"}, "maybe"),  # bad key
        ({"ask": "values", "constraints": [{"formula": "P ∨ Q", "value": True}]}, "P = T, Q = T"),
        ({"ask": "values"}, "P = T"),
    ]:
        bad = _logic(make_problem, "truth_table", data, answer)
        with pytest.raises(ContentError):
            handler.validate(bad, handler.params(bad))


# --------------------------------------------------------------------------- equivalence


def test_rewrite_chain(check_submission, verdict_codes, make_problem):
    p = _logic(make_problem, "logical_equivalence", {"left": "P ⇒ Q", "right": "(~P) ∨ Q"})
    v = check_submission(p, "P ⇒ Q", "~~P ⇒ Q", "~P ∨ Q")
    assert v.status is VerdictStatus.CORRECT, v
    assert v.answer.code == "LOGIC_EQUIVALENCE_SHOWN"
    # starting from the other side works too
    v = check_submission(p, "~P ∨ Q", "~P ∨ ~~Q", "P ⇒ Q")
    assert v.status is VerdictStatus.CORRECT


def test_chain_errors_and_hints(check_submission, verdict_codes, demorgan):
    v = check_submission(demorgan, "~(P ∨ Q)", "~P ∨ ~Q", "(~P) ∧ (~Q)")
    assert v.status is VerdictStatus.INCORRECT
    assert v.steps[1].status is StepStatus.ERROR
    assert {"LOGIC_STEP_NOT_EQUIVALENT", "DEMORGAN_CONNECTIVE"} <= verdict_codes(v)
    assert "P = T, Q = F" in v.steps[1].message


def test_chain_without_work_or_unfinished(check_submission, verdict_codes, demorgan):
    v = check_submission(demorgan, "~(P ∨ Q)", "~P ∧ ~Q")
    assert v.status is VerdictStatus.PARTIAL and "LOGIC_NO_WORK" in verdict_codes(v)
    v = check_submission(demorgan, "~(P ∨ Q)", "~(Q ∨ P)")
    assert v.status is VerdictStatus.PARTIAL and "LOGIC_INCOMPLETE" in verdict_codes(v)
    v = check_submission(demorgan)
    assert v.status is VerdictStatus.INCORRECT


def test_truth_table_method(check_submission, verdict_codes, demorgan):
    v = check_submission(
        demorgan, ("column", "~(P ∨ Q) : F F F T"), ("column", "(~P) ∧ (~Q) : FFFT")
    )
    assert v.status is VerdictStatus.CORRECT
    v = check_submission(demorgan, ("column", "~(P ∨ Q) : F F F T"))
    assert v.status is VerdictStatus.PARTIAL and "LOGIC_INCOMPLETE" in verdict_codes(v)
    v = check_submission(
        demorgan, ("column", "~(P ∨ Q) : F F F T"), ("column", "(~P) ∧ (~Q) : FFTT")
    )
    assert v.status is VerdictStatus.INCORRECT


def test_decide(check_submission, verdict_codes, decide):
    v = check_submission(decide, ("row", "P = T, Q = F, R = F"), answer="not equivalent")
    assert v.status is VerdictStatus.CORRECT
    assert check_submission(decide, answer="No, they aren't").status is VerdictStatus.CORRECT
    v = check_submission(decide, answer="equivalent")
    assert v.status is VerdictStatus.INCORRECT and "LOGIC_LOOK_FOR_ROW" in verdict_codes(v)
    v = check_submission(decide, ("row", "P = T, Q = T, R = T"), answer="not equivalent")
    assert v.status is VerdictStatus.PARTIAL and "LOGIC_ROW_SAME" in verdict_codes(v)
    assert check_submission(decide, answer="dunno").status is VerdictStatus.INVALID


def test_decide_equivalent(check_submission, verdict_codes, make_problem):
    data = {"left": "P ∧ Q", "right": "~(~P ∨ ~Q)", "decide": True}
    p = _logic(make_problem, "logical_equivalence", data, "equivalent")
    assert check_submission(p, answer="yes, equivalent").status is VerdictStatus.CORRECT
    v = check_submission(p, answer="not equivalent")
    assert "LOGIC_TRY_LAWS" in verdict_codes(v)


def test_equivalence_validation(make_problem, demorgan, decide):
    handler = get_handler("logical_equivalence")
    assert handler.verify_key(demorgan, handler.params(demorgan)) is True
    assert handler.verify_key(decide, handler.params(decide)) is True
    assert not handler.has_answer(demorgan, handler.params(demorgan))
    assert handler.has_answer(decide, handler.params(decide))
    false_claim = _logic(make_problem, "logical_equivalence", {"left": "P", "right": "~P"})
    assert handler.verify_key(false_claim, handler.params(false_claim)) is False
    with_key = _logic(make_problem, "logical_equivalence", demorgan.data, "equivalent")
    with pytest.raises(ContentError):
        handler.validate(with_key, handler.params(with_key))
