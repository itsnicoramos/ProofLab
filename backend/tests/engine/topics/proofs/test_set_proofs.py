from __future__ import annotations

import pytest

from prooflab.engine.checker import ContentError, get_handler
from prooflab.engine.models import VerdictStatus
from prooflab.engine.topics.proofs.set_proofs import line_formula, parse_line


def _identity(make_problem, **data):
    return make_problem("set_identity", data, course="proofs", topic="set-proofs")


@pytest.fixture
def distributive(make_problem):
    return _identity(
        make_problem, sets=["A", "B", "C"], left="A ∪ (B ∩ C)", right="(A ∪ B) ∩ (A ∪ C)"
    )


def test_element_chasing_proof(distributive, check_submission):
    verdict = check_submission(
        distributive,
        "x in A union (B intersect C)",
        "x in A or (x in B and x in C)",
        "(x in A or x in B) and (x in A or x in C)",
        "x in (A union B) intersect (A union C)",
    )
    assert verdict.status is VerdictStatus.CORRECT


def test_straight_jump_is_not_a_proof(distributive, check_submission, verdict_codes):
    verdict = check_submission(distributive, "A ∪ (B ∩ C)", "(A ∪ B) ∩ (A ∪ C)")
    assert verdict.status is VerdictStatus.PARTIAL
    assert "SETID_NO_WORK" in verdict_codes(verdict)


def test_wrong_line_names_an_element(distributive, check_submission, verdict_codes):
    verdict = check_submission(distributive, "x ∈ A ∪ (B ∩ C)", "x ∈ A ∨ (x ∈ B ∨ x ∈ C)")
    assert verdict.status is VerdictStatus.INCORRECT
    assert "SETID_STEP_DIFFERS" in verdict_codes(verdict)
    assert "∉" in verdict.steps[1].message or "∈" in verdict.steps[1].message


def test_unfinished_chain(distributive, check_submission, verdict_codes):
    verdict = check_submission(distributive, "x ∈ A ∪ (B ∩ C)", "x ∈ A or (x ∈ B and x ∈ C)")
    assert "SETID_INCOMPLETE" in verdict_codes(verdict)


def test_de_morgan_with_complements(make_problem, check_submission):
    problem = _identity(
        make_problem, sets=["A", "B"], left="(A ∩ B)'", right="A' ∪ B'", universe=True
    )
    verdict = check_submission(
        problem, "x ∈ (A ∩ B)'", "not (x in A and x in B)", "x ∉ A or x ∉ B", "x ∈ Ā ∪ B̄"
    )
    assert verdict.status is VerdictStatus.CORRECT


def test_products_use_coordinates(make_problem, check_submission):
    problem = _identity(
        make_problem,
        sets=["A", "B", "C"],
        left="A × (B ∪ C)",
        right="(A × B) ∪ (A × C)",
        point=["x", "y"],
    )
    verdict = check_submission(
        problem,
        "(x, y) ∈ A × (B ∪ C)",
        "x ∈ A and (y ∈ B or y ∈ C)",
        "(x ∈ A and y ∈ B) or (x ∈ A and y ∈ C)",
        "(x,y) ∈ (A × B) ∪ (A × C)",
    )
    assert verdict.status is VerdictStatus.CORRECT


def test_mixed_operators_need_parentheses(distributive, check_submission, verdict_codes):
    assert "SETID_SYNTAX" in verdict_codes(check_submission(distributive, "A ∪ B ∩ C"))


def test_unequal_sides_are_a_content_error(make_problem):
    problem = _identity(make_problem, sets=["A", "B"], left="A − B", right="B − A")
    handler = get_handler("set_identity")
    with pytest.raises(ContentError):
        handler.validate(problem, handler.params(problem))


def test_parse_aliases():
    f = line_formula(parse_line("x element of A \\cup B", ["A", "B"], False), ["x"])
    assert f.op == "or"
