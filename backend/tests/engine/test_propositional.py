from __future__ import annotations

import pytest

from prooflab.engine.algebra import MathInputError
from prooflab.engine.propositional import (
    LogicContext,
    column,
    column_text,
    diagnose_column,
    diagnose_rewrite,
    equivalent,
    first_difference,
    parse_assignment,
    parse_column,
    rows,
    same_statement,
    to_latex,
    to_text,
)

PQ = LogicContext.build(["P", "Q"])
PQR = LogicContext.build(["P", "Q", "R"])


def col(text: str, ctx: LogicContext = PQ) -> str:
    return column_text(column(ctx.parse(text), ctx.variables))


def test_rows_are_in_the_books_order():
    assert rows(2) == [(True, True), (True, False), (False, True), (False, False)]
    assert col("P", PQR) == "T T T T F F F F"
    assert col("R", PQR) == "T F T F T F T F"


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("P ∧ Q", "T F F F"),
        ("P & Q", "T F F F"),
        ("P and Q", "T F F F"),
        ("P ^ Q", "T F F F"),
        (r"P \wedge Q", "T F F F"),
        ("P ∨ Q", "T T T F"),
        ("P | Q", "T T T F"),
        ("P v Q", "T T T F"),
        ("P or Q", "T T T F"),
        ("P ⇒ Q", "T F T T"),
        ("P => Q", "T F T T"),
        ("P -> Q", "T F T T"),
        ("P → Q", "T F T T"),
        ("P implies Q", "T F T T"),
        ("P ⇔ Q", "T F F T"),
        ("P <=> Q", "T F F T"),
        ("P iff Q", "T F F T"),
        ("~P", "F F T T"),
        ("¬P", "F F T T"),
        ("not P", "F F T T"),
        ("~~P", "T T F F"),
        ("[P ∨ Q]", "T T T F"),
        ("P ∨ T", "T T T T"),
        ("Q ∧ false", "F F F F"),
    ],
)
def test_connectives(formula, expected):
    assert col(formula) == expected


def test_negation_binds_tightest():
    assert col("~P ∨ Q") == col("(~P) ∨ Q") != col("~(P ∨ Q)")
    assert col("~P ⇒ Q ∧ P") == col("(~P) ⇒ (Q ∧ P)")


@pytest.mark.parametrize(
    ("bad", "code"),
    [
        ("P ∨ Q ∧ R", "LOGIC_AMBIGUOUS"),
        ("P ⇒ Q ⇒ R", "LOGIC_AMBIGUOUS"),
        ("P ⇔ Q ⇔ R", "LOGIC_AMBIGUOUS"),
        ("P ∧", "LOGIC_SYNTAX"),
        ("(P ∧ Q", "LOGIC_SYNTAX"),
        ("PQ", "LOGIC_SYNTAX"),
        ("P ∧ S", "LOGIC_SYNTAX"),
        ("P + Q", "LOGIC_SYNTAX"),
        ("__import__('os')", "LOGIC_SYNTAX"),
        ("", "EMPTY"),
    ],
)
def test_bad_formulas(bad, code):
    with pytest.raises(MathInputError) as info:
        PQR.parse(bad)
    assert info.value.code == code


def test_depth_and_length_limits():
    with pytest.raises(MathInputError):
        PQ.parse("~" * 60 + "P")
    with pytest.raises(MathInputError):
        PQ.parse(" ∧ ".join(["P"] * 300))


def test_context_validation():
    with pytest.raises(ValueError):
        LogicContext.build(["P", "Q", "R", "S", "U", "V", "W"])
    with pytest.raises(ValueError):
        LogicContext.build(["p"])


def test_structural_comparison_flattens_associative_chains():
    assert same_statement(PQR.parse("(P ∧ Q) ∧ R"), PQR.parse("P ∧ (Q ∧ R)"))
    assert same_statement(PQR.parse("((P))"), PQR.parse("P"))
    assert not same_statement(PQ.parse("P ∧ Q"), PQ.parse("Q ∧ P"))


def test_equivalence_and_differences():
    a, b = PQ.parse("P ⇒ Q"), PQ.parse("~P ∨ Q")
    assert equivalent(a, b, PQ.variables)
    assert first_difference(a, b, PQ.variables) is None
    assert first_difference(a, PQ.parse("Q ⇒ P"), PQ.variables) == {"P": True, "Q": False}


def test_display():
    f = PQR.parse("~(P ∨ Q) ⇒ (R ∧ ~P)")
    assert to_text(f) == "~(P ∨ Q) ⇒ (R ∧ ~P)"
    assert to_latex(f) == r"\sim (P \vee Q) \Rightarrow (R \wedge \sim P)"


def test_parse_column():
    expected = [True, True, False, True]
    assert parse_column("T T F T") == parse_column("TTFT") == parse_column("1,1,0,1") == expected
    assert parse_column("t, t, f, t") == parse_column("true true false true") == expected
    with pytest.raises(MathInputError):
        parse_column("T T X T")
    with pytest.raises(MathInputError):
        parse_column("")


def test_parse_assignment():
    expected = {"P": True, "Q": False}
    for t in ["P = T, Q = F", "P=T Q=F", "P is true and Q is false", "P: 1; Q: 0"]:
        assert parse_assignment(t, ["P", "Q"]) == expected, t
    for bad in ["P = T, P = F", "S = T", "P = maybe", "hello"]:
        with pytest.raises(MathInputError):
            parse_assignment(bad, ["P", "Q"])


def test_typical_mistakes_are_recognised():
    implies = PQ.parse("P ⇒ Q")
    converse = column(PQ.parse("Q ⇒ P"), PQ.variables)
    assert diagnose_column(implies, converse, PQ.variables) == "IMPLIES_CONVERSE"
    assert diagnose_column(implies, column(PQ.parse("P ∧ Q"), PQ.variables), PQ.variables) == (
        "IMPLIES_AS_AND"
    )
    demorgan = PQ.parse("~(P ∧ Q)")
    assert diagnose_rewrite(demorgan, PQ.parse("~P ∧ ~Q"), PQ.variables) == ("DEMORGAN_CONNECTIVE")
    assert diagnose_rewrite(implies, PQ.parse("P ∨ Q"), PQ.variables) == "IMPLIES_AS_OR"
