from __future__ import annotations

import pytest
import sympy as sp

from prooflab.engine.algebra import MathInputError
from prooflab.engine.finite_sets import (
    Atom,
    Builder,
    ElementContext,
    build_set,
    evaluate,
    flatten_tuples,
    latex,
    node_latex,
    parse_expression,
    parse_literal,
    text,
)

E = ElementContext.build(["a", "b", "c", "R", "Q", "N"])
NUMS = ElementContext.build()


def lit(t: str, ectx: ElementContext = E) -> frozenset:
    return parse_literal(t, ectx)


def ev(t: str, env=None, universe=None, ectx: ElementContext = E) -> frozenset:
    return evaluate(parse_expression(t, ectx), env or {}, universe)


# --------------------------------------------------------------------------- literals


def test_literals_compare_as_sets():
    assert lit("{1, 2, 3}") == lit("{3, 1, 2, 2}")
    assert lit("{}") == lit("∅") == lit("emptyset") == frozenset()
    assert lit("{0.5, 1/2, 2/4}") == frozenset({sp.Rational(1, 2)})
    assert lit("{sqrt(3), -√3}") == frozenset({sp.sqrt(3), -sp.sqrt(3)})
    assert lit("{(1+sqrt(3))^2}") == frozenset({4 + 2 * sp.sqrt(3)})


def test_nested_sets_tuples_and_atoms():
    s = lit("{{1}, {2, {3, 4}}, ∅}")
    assert len(s) == 3 and frozenset() in s
    pairs = lit("{(1, a), (2, b)}")
    assert (sp.Integer(1), Atom("a")) in pairs
    assert lit("{R, {Q, N}}") == frozenset({Atom("R"), frozenset({Atom("Q"), Atom("N")})})
    assert lit("{ℝ, ℚ}") == lit("{R, Q}")
    assert lit("{(1)}") == lit("{1}")  # parentheses around one thing aren't a tuple


def test_letters_that_are_not_atoms_are_numbers_or_errors():
    assert lit("{pi, e, 0}", NUMS) == frozenset({sp.pi, sp.E, sp.Integer(0)})
    e_atom = ElementContext.build(["e"])
    assert lit("{e}", e_atom) == frozenset({Atom("e")})
    with pytest.raises(MathInputError, match="can't read 'q'"):
        lit("{q}")


def test_ellipsis_runs():
    assert lit("{-9, -8, ..., 9}") == frozenset(sp.Integer(k) for k in range(-9, 10))
    assert lit("{-20, -15, …, 20}") == frozenset(sp.Integer(k) for k in range(-20, 21, 5))
    assert lit("{0, 1, 2, ..., 10}") == frozenset(sp.Integer(k) for k in range(11))
    assert lit("{5, ..., 1}") == frozenset(sp.Integer(k) for k in range(1, 6))
    for bad, code in [
        ("{1, 2, ...}", "SET_INFINITE"),
        ("{..., 1}", "SET_INFINITE"),
        ("{1, 3, ..., 6}", "SET_SYNTAX"),
        ("{a, ..., c}", "SET_SYNTAX"),
        ("{(1, ...)}", "SET_SYNTAX"),
    ]:
        with pytest.raises(MathInputError) as info:
            lit(bad)
        assert info.value.code == code, bad


@pytest.mark.parametrize(
    ("bad", "code"),
    [
        ("1, 2, 3", "SET_NOT_A_LIST"),
        ("{1, 2", "SET_NOT_A_LIST"),
        ("{1,,2}", "EMPTY"),
        ("{x ∈ Z : x > 0}", "SET_BUILDER"),
        ("{oo}", "SET_SYNTAX"),
        ("{sqrt(-1)}", "SET_SYNTAX"),
        ("{__import__('os')}", "PARSE_ERROR"),
    ],
)
def test_bad_literals(bad, code):
    with pytest.raises(MathInputError) as info:
        lit(bad)
    assert info.value.code == code


def test_display_is_sorted_and_round_trips():
    s = lit("{c, (2, a), 3, {1}, -1}")
    assert text(s) == "{-1, 3, c, (2, a), {1}}"
    assert lit(text(s)) == s
    assert latex(lit("{R}")) == r"\{\mathbb{R}\}"
    assert latex(frozenset()) == r"\emptyset"
    assert text(lit("{pi, e, 1/2}", NUMS)) == "{1/2, e, pi}"


# --------------------------------------------------------------------------- expressions

ENV = {"A": lit("{1, 2, 3, 4}"), "B": lit("{a, c}"), "A1": lit("{1}"), "U": lit("{0, 1, ..., 6}")}


def test_operations():
    assert ev("A ∪ B", ENV) == ev("A cup B", ENV) == ev("A u B", ENV) == ev(r"A \cup B", ENV)
    assert ev("A ∩ {2, 9}", ENV) == ev("A cap {2, 9}", ENV) == lit("{2}")
    assert ev("A − {1}", ENV) == ev("A - {1}", ENV) == ev(r"A \ {1}", ENV) == lit("{2, 3, 4}")
    assert ev("A - {1} - {2}", ENV) == lit("{3, 4}")
    assert ev("A_1 ∪ A1", ENV) == lit("{1}")


def test_products_and_powers():
    assert len(ev("A × B", ENV)) == len(ev("A x B", ENV)) == len(ev("A * B", ENV)) == 8
    assert ev("B × A", ENV) != ev("A × B", ENV)
    assert ev("∅ × B", ENV) == frozenset()
    triples = ev("B^3", ENV)
    assert len(triples) == 8 and all(len(t) == 3 for t in triples)
    assert ev("B³", ENV) == triples == ev("B × B × B", ENV)
    nested = ev("(A × B) × B", ENV)
    assert ((sp.Integer(1), Atom("a")), Atom("c")) in nested
    assert ev("A × (B × B)", ENV) != nested
    assert flatten_tuples(ev("A × (B × B)", ENV)) == flatten_tuples(nested)


def test_complements_and_power_sets():
    u = ENV["U"]
    assert ev("A'", ENV, u) == ev("A^c", ENV, u) == ev("comp(A)", ENV, u) == lit("{0, 5, 6}")
    assert ev(r"\overline{A}", ENV, u) == ev("A̅", ENV, u) == lit("{0, 5, 6}")
    assert ev("(A ∩ {1, 2})'", ENV, u) == lit("{0, 3, 4, 5, 6}")
    assert ev("P({1, 2})", ENV) == lit("{∅, {1}, {2}, {1, 2}}")
    assert ev("𝒫(𝒫({2}))", ENV) == lit("{∅, {∅}, {{2}}, {∅, {2}}}")
    assert ev("℘(∅)", ENV) == lit("{∅}")
    with pytest.raises(MathInputError) as info:
        ev("A'", ENV)
    assert info.value.code == "SET_NO_UNIVERSE"


def test_latex_of_expressions():
    assert node_latex(parse_expression("(A × B) ∩ B'", E)) == (
        r"\left(A \times B\right) \cap \overline{B}"
    )
    assert node_latex(parse_expression("P(A1)", E)) == r"\mathscr{P}\left(A_{1}\right)"


@pytest.mark.parametrize(
    ("bad", "code"),
    [
        ("A ∪ B ∩ A", "SET_MIXED_OPERATORS"),
        ("A ∪ B − A", "SET_MIXED_OPERATORS"),
        ("C", "SET_UNKNOWN_NAME"),
        ("(A ∪ B", "SET_SYNTAX"),
        ("A ∪", "SET_SYNTAX"),
        ("A ? B", "SET_SYNTAX"),
        ("P(P(P(P({1, 2, 3, 4}))))", "SET_TOO_LARGE"),
        ("A^9", "SET_TOO_LARGE"),
        ("{1, 2, ..., 100}^3", "SET_TOO_LARGE"),
    ],
)
def test_bad_expressions(bad, code):
    with pytest.raises(MathInputError) as info:
        ev(bad, ENV)
    assert info.value.code == code


def test_mixing_is_fine_with_parentheses():
    assert ev("(A ∪ B) ∩ A", ENV) == ENV["A"]
    assert ev("A ∪ (B ∩ A)", ENV) == ENV["A"]


# --------------------------------------------------------------------------- set-builder (data)


def build(**kw) -> frozenset:
    return build_set(Builder.model_validate(kw), {}, E)


def test_builders_over_numbers():
    assert build(var="x", domain="Z", where=["-2 <= x < 7"]) == lit("{-2, -1, ..., 6}")
    assert build(var="x", domain="N", where=["-2 < x <= 7"]) == lit("{1, 2, ..., 7}")
    assert build(var="x", domain="R", where=["x^3 + 5x^2 = -6x"]) == lit("{0, -2, -3}")
    assert build(var="x", domain="R", where=["x^2 = 3"]) == lit("{sqrt(3), -sqrt(3)}")
    assert build(var="x", domain="Z", element="5x", where=["|2x| <= 8"]) == lit(
        "{-20, -15, ..., 20}"
    )
    assert build(var="x", domain="N", where=["x^2 < 0"]) == frozenset()
    assert len(build(var="x", domain="Z", where=["|x| < 10"])) == 19


def test_naturals_variant_includes_zero():
    b = Builder(var="x", domain="N", where=["|x| < 10"])
    assert len(build_set(b, {}, E)) == 9
    assert len(build_set(b, {}, E, naturals_from=0)) == 10


def test_builders_over_sets():
    singletons = build(var="X", **{"in": "P(P({1, 2, 3}))"}, where=["|X| <= 1"])
    assert len(singletons) == 9 and frozenset() in singletons
    assert build(var="X", **{"in": "P({1, 2, 3})"}, where=["2 ∈ X"]) == lit(
        "{{2}, {1, 2}, {2, 3}, {1, 2, 3}}"
    )
    assert build(var="X", **{"in": "P({3, 2, a})"}, where=["|X| = 4"]) == frozenset()


@pytest.mark.parametrize(
    "spec",
    [
        {"var": "x", "domain": "Z", "where": ["x > 0"]},  # unbounded
        {"var": "x", "domain": "R", "where": ["x > 0"]},  # an interval, not finite
        {"var": "x", "where": ["x > 0"]},  # no domain
        {"var": "X", "in": "P({1})", "where": ["X is big"]},
    ],
)
def test_bad_builders(spec):
    with pytest.raises(ValueError):
        build(**spec)
