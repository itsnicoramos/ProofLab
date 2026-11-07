from __future__ import annotations

import pytest
import sympy as sp

from prooflab.engine.algebra import MathContext
from prooflab.engine.checker import ContentError, get_handler
from prooflab.engine.models import StepStatus, VerdictStatus
from prooflab.engine.topics.proofs.divisibility import (
    Predicate,
    evaluate_predicate,
    form_latex,
    parse_assignment,
    substitute,
)


def _proof(make_problem, data):
    return make_problem("divisibility_proof", data, course="proofs", topic="divisibility")


@pytest.fixture
def transitive(make_problem):
    return _proof(
        make_problem,
        {
            "variables": ["a", "b", "c"],
            "hypotheses": [{"var": "b", "divisor": "a"}, {"var": "c", "divisor": "b"}],
            "target": "c",
            "goal": {"divisor": "a"},
        },
    )


def test_substitute_reaches_a_fixpoint():
    ctx = MathContext.build(
        {"a": "integer", "b": "integer", "c": "integer", "j": "integer", "k": "integer"}
    )
    a, b, c, j, k = (ctx[n] for n in "abcjk")
    assert substitute(c, {c: b * k, b: a * j}) == a * j * k


def test_form_latex_keeps_the_factor():
    k = sp.Symbol("k")
    assert form_latex(sp.Integer(2), 2 * k**2 + 2 * k, sp.Integer(1)).startswith("2 \\left(")


def test_symbolic_divisor_proof(transitive, check_submission):
    verdict = check_submission(
        transitive, ("let", "b = aj"), ("let", "c = bk"), "(aj)k", "a(jk)", ("witness", "jk")
    )
    assert verdict.status is VerdictStatus.CORRECT


def test_symbolic_divisor_representation_errors(transitive, check_submission, verdict_codes):
    verdict = check_submission(transitive, ("let", "b = j/a"))
    assert "BAD_REPRESENTATION" in verdict_codes(verdict)
    verdict = check_submission(transitive, ("let", "b = a + j"))
    assert "BAD_REPRESENTATION" in verdict_codes(verdict)


def test_witness_mismatch(transitive, check_submission, verdict_codes):
    verdict = check_submission(transitive, ("let", "b = aj"), ("let", "c = bk"), ("witness", "k"))
    assert verdict.steps[-1].status is StepStatus.ERROR
    assert "WITNESS_MISMATCH" in verdict_codes(verdict)


def test_congruence_hypothesis(make_problem, check_submission, verdict_codes):
    p = _proof(
        make_problem,
        {
            "variables": ["n"],
            "hypotheses": [{"var": "n", "divisor": 3, "remainder": 1}],
            "target": "n^2",
            "goal": {"divisor": 3, "remainder": 1},
        },
    )
    ok = check_submission(p, ("let", "n = 3k + 4"), ("witness", "3k^2 + 8k + 5"))
    assert ok.status is VerdictStatus.CORRECT
    assert "BAD_REPRESENTATION" in verdict_codes(check_submission(p, ("let", "n = 3k + 2")))


def test_case_split_mod_3(make_problem, check_submission, verdict_codes):
    p = _proof(make_problem, {"variables": ["n"], "target": "n^3 - n", "goal": {"divisor": 3}})
    cases = [
        ("case", "n = 3k"), ("witness", "9k^3 - k"),
        ("case", "n = 3k + 1"), ("witness", "9k^3 + 9k^2 + 2k"),
        ("case", "n = 3k - 1"), ("witness", "9k^3 - 9k^2 + 2k"),
    ]  # fmt: skip
    assert check_submission(p, *cases).status is VerdictStatus.CORRECT
    mixed = check_submission(p, ("case", "n = 3k"), ("case", "n = 6k + 1"))
    assert "CASE_MISMATCH" in verdict_codes(mixed)


def test_try_cases_hint(make_problem, check_submission, verdict_codes):
    p = _proof(make_problem, {"variables": ["n"], "target": "n^3 - n", "goal": {"divisor": 3}})
    assert "TRY_CASES" in verdict_codes(check_submission(p, ("witness", "(n^3 - n)/3")))


def test_bad_content_is_rejected(make_problem):
    p = _proof(make_problem, {"variables": ["n"], "target": "n", "goal": {"divisor": 1}})
    handler = get_handler("divisibility_proof")
    with pytest.raises(Exception, match="divisor"):
        handler.validate(p, handler.params(p))


# --------------------------------------------------------------------------- counterexample


def test_predicates():
    ctx = MathContext.build({"a": "integer", "b": "integer"})
    values = {ctx["a"]: sp.Integer(4), ctx["b"]: sp.Integer(6)}

    def ev(raw):
        return evaluate_predicate(Predicate.model_validate(raw), ctx, values)

    assert not ev({"op": "divides", "args": ["a", "b"]})
    assert ev({"op": "divides", "args": ["a", "a b"]})
    assert ev({"op": "even", "args": ["a + b"]})
    assert not ev({"op": "prime", "args": ["a + b"]})
    assert ev(
        {"op": "or", "args": [{"op": "lt", "args": ["a", "b"]}, {"op": "odd", "args": ["a"]}]}
    )
    assert ev({"op": "not", "args": [{"op": "eq", "args": ["a", 5]}]})
    assert ev({"op": "divides", "args": [0, 0]}) and not ev({"op": "divides", "args": [0, "a"]})


def test_predicate_arity_is_validated():
    with pytest.raises(ValueError):
        Predicate.model_validate({"op": "divides", "args": ["a"]})
    with pytest.raises(ValueError):
        Predicate.model_validate({"op": "and", "args": ["a"]})


def test_parse_assignment():
    assert parse_assignment("a = 4, b = -2", ["a", "b"]) == {"a": 4, "b": -2}
    assert parse_assignment("a=4 and b=2", ["a", "b"]) == {"a": 4, "b": 2}


@pytest.fixture
def converse(make_problem):
    data = {
        "variables": {"a": "positive", "b": "integer", "c": "integer"},
        "hypothesis": {"op": "divides", "args": ["a", "b c"]},
        "conclusion": {
            "op": "or",
            "args": [{"op": "divides", "args": ["a", "b"]}, {"op": "divides", "args": ["a", "c"]}],
        },
    }
    return make_problem(
        "counterexample", data, "a = 4, b = 2, c = 2", course="proofs", topic="divisibility"
    )


@pytest.mark.parametrize(
    ("answer", "status", "code"),
    [
        ("a = 6, b = 2, c = 3", VerdictStatus.CORRECT, "COUNTEREXAMPLE_VALID"),
        ("a = 2, b = 4, c = 3", VerdictStatus.INCORRECT, "CONCLUSION_HOLDS"),
        ("a = 5, b = 2, c = 3", VerdictStatus.INCORRECT, "HYPOTHESIS_NOT_MET"),
        ("a = -4, b = 2, c = 2", VerdictStatus.INCORRECT, "COUNTEREXAMPLE_DOMAIN"),
        ("a = 1/2, b = 2, c = 2", VerdictStatus.INCORRECT, "COUNTEREXAMPLE_NOT_INTEGER"),
        ("a = 4", VerdictStatus.INVALID, "COUNTEREXAMPLE_MISSING_VALUE"),
        ("4, 2, 2", VerdictStatus.INVALID, "COUNTEREXAMPLE_FORMAT"),
    ],
)
def test_counterexample_verdicts(converse, check_submission, verdict_codes, answer, status, code):
    verdict = check_submission(converse, answer=answer)
    assert verdict.status is status
    assert code in verdict_codes(verdict)


def test_counterexample_key_is_verified(converse):
    handler = get_handler("counterexample")
    assert handler.verify_key(converse, handler.params(converse)) is True
    wrong = converse.model_copy(update={"answer": "a = 2, b = 2, c = 2"})
    assert handler.verify_key(wrong, handler.params(wrong)) is False


def test_congruence_with_a_symbolic_modulus(make_problem, check_submission, verdict_codes):
    """Book of Proof Definition 5.1: a ≡ b (mod n) means a = nk + b."""
    p = make_problem(
        "divisibility_proof",
        {
            "variables": ["a", "b", "n"],
            "hypotheses": [{"var": "a", "divisor": "n", "remainder": "b"}],
            "target": "a^3 - b^3",
            "goal": {"divisor": "n"},
        },
        course="proofs",
        topic="divisibility",
    )
    good = check_submission(p, ("let", "a = nk + b"), ("witness", "n^2 k^3 + 3n k^2 b + 3k b^2"))
    assert good.status is VerdictStatus.CORRECT
    lost_b = check_submission(p, ("let", "a = nk"))
    assert lost_b.steps[0].status is StepStatus.ERROR
    assert "BAD_REPRESENTATION" in verdict_codes(lost_b)


def test_symbolic_modulus_rejects_a_numeric_remainder(make_problem):
    problem = make_problem(
        "divisibility_proof",
        {
            "variables": ["a", "n"],
            "hypotheses": [{"var": "a", "divisor": "n", "remainder": 2}],
            "target": "a",
            "goal": {"divisor": "n"},
        },
        course="proofs",
        topic="divisibility",
    )
    handler = get_handler("divisibility_proof")
    with pytest.raises(ContentError, match="remainder"):
        handler.validate(problem, handler.params(problem))
