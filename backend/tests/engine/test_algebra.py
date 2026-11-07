from __future__ import annotations

import pytest
import sympy as sp

from prooflab.engine.algebra import (
    MathContext,
    MathInputError,
    VarSpec,
    equivalent,
    is_integer_polynomial,
    linear_in,
    match_values,
    normalize,
    parse_equation,
    parse_real_set,
    parse_tuple,
    parse_value_list,
    real_solutions,
    relation,
    satisfies,
    set_difference_is_finite,
    sets_equal,
    strip_label,
)

CTX = MathContext.build({"x": "real", "y": "real", "theta": "real"}, constants=["C"])
x, y, theta = CTX["x"], CTX["y"], CTX["theta"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2x", 2 * x),
        ("3(x+1)", 3 * x + 3),
        ("(x+1)(x-1)", (x + 1) * (x - 1)),
        ("x sin x", x * sp.sin(x)),
        ("xsinx", x * sp.sin(x)),
        ("x^2", x**2),
        ("x**2", x**2),
        ("x²", x**2),
        ("√(x+1)", sp.sqrt(x + 1)),
        ("sin 2x", sp.sin(2 * x)),
        ("sin^2(x)", sp.sin(x) ** 2),
        ("sin^-1(x)", sp.asin(x)),
        ("arctan x", sp.atan(x)),
        ("ln(x)", sp.log(x)),
        ("log(100)", sp.Integer(2)),
        ("log_2(8)", sp.Integer(3)),
        ("log(8, 2)", sp.Integer(3)),
        ("e^x", sp.exp(x)),
        ("e^-x^2", sp.exp(-(x**2))),
        ("2πx", 2 * sp.pi * x),
        ("|x - 1|", sp.Abs(x - 1)),
        ("5!", sp.Integer(120)),
        ("1/2x", x / 2),
        ("-x^2", -(x**2)),
        ("2^-1", sp.Rational(1, 2)),
        ("x + C", x + CTX["C"]),
        ("Sin(θ)", sp.sin(theta)),
        ("x⁻¹", 1 / x),
        ("−x · y", -x * y),
        ("∞", sp.oo),
    ],
)
def test_parser(text, expected):
    assert CTX.parse(text) == expected


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("", "EMPTY"),
        ("x = 2", "NOT_AN_EXPRESSION"),
        ("q", "UNKNOWN_NAME"),
        ("f(x)", "UNKNOWN_NAME"),
        ("__import__('os')", "PARSE_ERROR"),
        ("x.__class__", "PARSE_ERROR"),
        ("().__class__.__bases__", "PARSE_ERROR"),
        ("x;y", "PARSE_ERROR"),
        ("2^10000", "TOO_LARGE"),
        ("2^2^2^2^2", "TOO_LARGE"),
        ("9999!", "TOO_LARGE"),
        ("1/0", "DIVISION_BY_ZERO"),
        ("0^-1", "DIVISION_BY_ZERO"),
        ("1234567890123456789", "TOO_LONG"),
        ("(" * 80 + "x" + ")" * 80, "TOO_LONG"),
        ("x" * 501, "TOO_LONG"),
        ("int(x, x)", "UNKNOWN_NAME"),
        ("2 3", "PARSE_ERROR"),
        ("sin", "PARSE_ERROR"),
    ],
)
def test_parser_rejects(text, code):
    with pytest.raises(MathInputError) as err:
        CTX.parse(text)
    assert err.value.code == code
    assert err.value.message


def test_integrals_only_when_allowed():
    ctx = CTX.extend(allow_integral=True)
    assert ctx.parse("int(x^2, x)") == sp.Integral(x**2, x)
    assert ctx.parse("int(x, x, 0, 1)") == sp.Integral(x, (x, 0, 1))
    with pytest.raises(MathInputError):
        ctx.parse("int(x, 2)")


def test_variable_domains_set_assumptions():
    ctx = MathContext.build({"n": "integer", "t": "positive", "s": "real[-1, 1]"})
    assert ctx["n"].is_integer and ctx["t"].is_positive
    assert ctx.spec(ctx["s"]).bounds() == (-1.0, 1.0)
    with pytest.raises(ValueError):
        VarSpec.coerce("complex")
    with pytest.raises(ValueError):
        MathContext.build(["sin"])


def test_normalize_unicode():
    assert normalize("x² − 2·x ≤ π") == "x^(2) - 2*x <=  pi"


def test_equivalence():
    p = CTX.parse
    assert equivalent(p("(x^2-1)/(x-1)"), p("x+1"), CTX)
    assert equivalent(p("sin(x)^2 + cos(x)^2"), 1, CTX)
    assert equivalent(p("sin(2x)"), p("2 sin x cos x"), CTX)
    assert equivalent(p("sqrt(x^2)"), x, CTX) is False
    assert equivalent(p("sqrt(x^2)"), p("|x|"), CTX)
    assert equivalent(p("x + 1"), p("x + 1.0000001"), CTX) is False
    assert equivalent(p("sqrt(x)"), p("sqrt(-x)"), CTX) is False
    assert equivalent(sp.oo, sp.oo, CTX) and equivalent(sp.oo, -sp.oo, CTX) is False
    assert equivalent(p("sqrt(2)/2"), p("sin(pi/4)"), CTX)


def test_relation_diagnostics():
    p = CTX.parse
    assert relation(p("-2x"), p("2x"), CTX) == ("negated", None)
    assert relation(p("6x"), p("2x"), CTX) == ("scaled", 3)
    assert relation(p("x^2 + 3"), p("x^2"), CTX) == ("shifted", 3)
    assert relation(p("pi/2"), p("pi"), CTX) == ("scaled", sp.Rational(1, 2))
    assert relation(p("x^3"), p("x^2"), CTX) is None


def test_equations_and_solution_sets():
    lhs, rhs = parse_equation("x^2 - 5x + 6 = 0", CTX)
    sols = real_solutions(lhs, rhs, x)
    assert sorted(sols) == [2, 3]
    assert satisfies(lhs, rhs, x, sp.Integer(2)) and not satisfies(lhs, rhs, x, sp.Integer(4))
    ctx = MathContext.build(["x"])
    log_l, log_r = parse_equation("ln(x) + ln(x - 3) = ln(10)", ctx)
    assert real_solutions(log_l, log_r, ctx["x"]) == [5]
    assert not satisfies(log_l, log_r, ctx["x"], sp.Integer(-2))
    with pytest.raises(MathInputError):
        parse_equation("x^2", CTX)


@pytest.mark.parametrize(
    ("text", "values"),
    [
        ("x = 2 or x = -3", [2, -3]),
        ("x=2, x=-3", [2, -3]),
        ("{2, -3}", [2, -3]),
        ("2, -3, 2", [2, -3]),
        ("no solution", []),
        ("∅", []),
    ],
)
def test_value_lists(text, values):
    assert parse_value_list(text, CTX, x) == values


def test_match_values():
    missing, extra = match_values([sp.Integer(2), sp.Integer(7)], [sp.Integer(2), sp.Integer(3)])
    assert (missing, extra) == ([3], [7])
    assert match_values([sp.sqrt(2) / 2], [1 / sp.sqrt(2)]) == ([], [])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(-oo, 2) U (2, oo)", sp.Union(sp.Interval.open(-sp.oo, 2), sp.Interval.open(2, sp.oo))),
        ("x != 2", sp.Union(sp.Interval.open(-sp.oo, 2), sp.Interval.open(2, sp.oo))),
        ("[0, oo)", sp.Interval(0, sp.oo)),
        ("x >= 0", sp.Interval(0, sp.oo)),
        ("-1 < x <= 3", sp.Interval.Lopen(-1, 3)),
        ("x < 0 or x > 1", sp.Union(sp.Interval.open(-sp.oo, 0), sp.Interval.open(1, sp.oo))),
        ("all real numbers", sp.S.Reals),
        ("{1, 2}", sp.FiniteSet(1, 2)),
        ("∅", sp.S.EmptySet),
    ],
)
def test_real_sets(text, expected):
    assert sets_equal(parse_real_set(text, CTX, x), expected)


def test_set_difference_only_at_endpoints():
    assert set_difference_is_finite(sp.Interval(0, 1), sp.Interval.open(0, 1))
    assert not set_difference_is_finite(sp.Interval(0, 1), sp.Interval(0, 2))


def test_tuples():
    assert parse_tuple("<2x, 3y^2>", CTX, 2) == [2 * x, 3 * y**2]
    assert parse_tuple("(1, 2, 3)", CTX) == [1, 2, 3]
    assert parse_tuple("⟨x, y⟩", CTX) == [x, y]
    with pytest.raises(MathInputError):
        parse_tuple("<1, 2>", CTX, 3)


def test_integer_polynomials_and_linear_forms():
    ctx = MathContext.build({"k": "integer", "j": "integer"})
    k, j = ctx["k"], ctx["j"]
    assert is_integer_polynomial(2 * k**2 + 2 * k, [k])
    assert is_integer_polynomial(k * j - 3, [k, j])
    assert not is_integer_polynomial((k**2 + k) / 2, [k])
    assert not is_integer_polynomial(k + x, [k])
    assert linear_in(2 * k + 1, k) == (2, 1)
    assert linear_in(k**2, k) is None


def test_strip_label():
    assert strip_label("f'(x) = 2x") == " 2x"
    assert strip_label("dy/dx = 3x^2") == " 3x^2"
    assert strip_label("f_x = 2y") == " 2y"
    assert strip_label("x^2 + 1") == "x^2 + 1"


def test_abs_bars_as_an_implicit_function_argument():
    assert CTX.parse("ln|x|") == sp.log(sp.Abs(x))
    assert CTX.parse("ln|x| + 1") == sp.log(sp.Abs(x)) + 1


def test_subscript_labels_with_arguments():
    assert strip_label("f_x(1, 2) = 4").strip() == "4"


def test_solving_on_a_bounded_interval_finds_every_root():
    lhs, rhs = parse_equation("2sin(x)^2 - sin(x) - 1 = 0", CTX)
    sols = real_solutions(lhs, rhs, x, sp.Interval.Ropen(0, 2 * sp.pi))
    assert sorted(sols, key=float) == [sp.pi / 2, 7 * sp.pi / 6, 11 * sp.pi / 6]


def test_integer_valued_polynomials():
    import sympy as sp

    from prooflab.engine.algebra import is_integer_valued_polynomial

    k, m = sp.symbols("k m")
    assert is_integer_valued_polynomial(k * (k + 1) / 2, {k})
    assert is_integer_valued_polynomial(m + k * (k + 1) * (k + 2) / 6, {k, m})
    assert not is_integer_valued_polynomial(k / 2, {k})
    assert not is_integer_valued_polynomial(k**2 / 2, {k})
    assert not is_integer_valued_polynomial(sp.sqrt(k), {k})
