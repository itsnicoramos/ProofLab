"""Shared SymPy helpers.

Two jobs:

1. **Safe parsing.** Student input never reaches ``eval``, ``sympify`` or ``parse_expr``. A
   small tokenizer and recursive-descent parser build SymPy objects directly from an allowlist
   of functions, constants and the problem's declared variables (SPEC §3).
2. **Robust comparison.** Equivalence is decided numerically at seeded-random points, with a
   symbolic fallback (SPEC §6), plus helpers for equations, solution sets, intervals, tuples
   and integer polynomials.
"""

from __future__ import annotations

import itertools
import random
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction

import mpmath
import sympy as sp

# --------------------------------------------------------------------------- limits

MAX_INPUT_CHARS = 500
MAX_TOKENS = 300
MAX_DEPTH = 60
MAX_EXPONENT = 1000
MAX_INT_DIGITS = 15
MAX_FACTORIAL = 500
MAX_RESULT_BITS = 20_000

SEED = 20_261_106
DEFAULT_TOL = 1e-9


class MathInputError(ValueError):
    """Input we refuse to parse. ``message`` is written for students."""

    def __init__(self, message: str, code: str = "PARSE_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


# --------------------------------------------------------------------------- vocabulary


def _log(x: sp.Expr, base: sp.Expr | None = None) -> sp.Expr:
    # Calculator convention: log(x) is base 10, ln(x) is natural.
    return sp.log(x, sp.Integer(10) if base is None else base)


_FUNCTIONS: dict[str, tuple[tuple[int, ...], Callable[..., sp.Expr]]] = {
    "sin": ((1,), sp.sin),
    "cos": ((1,), sp.cos),
    "tan": ((1,), sp.tan),
    "sec": ((1,), sp.sec),
    "csc": ((1,), sp.csc),
    "cot": ((1,), sp.cot),
    "asin": ((1,), sp.asin),
    "acos": ((1,), sp.acos),
    "atan": ((1,), sp.atan),
    "asec": ((1,), sp.asec),
    "acsc": ((1,), sp.acsc),
    "acot": ((1,), sp.acot),
    "arcsin": ((1,), sp.asin),
    "arccos": ((1,), sp.acos),
    "arctan": ((1,), sp.atan),
    "arcsec": ((1,), sp.asec),
    "arccsc": ((1,), sp.acsc),
    "arccot": ((1,), sp.acot),
    "sinh": ((1,), sp.sinh),
    "cosh": ((1,), sp.cosh),
    "tanh": ((1,), sp.tanh),
    "asinh": ((1,), sp.asinh),
    "acosh": ((1,), sp.acosh),
    "atanh": ((1,), sp.atanh),
    "exp": ((1,), sp.exp),
    "ln": ((1,), sp.log),
    "log": ((1, 2), _log),
    "sqrt": ((1,), sp.sqrt),
    "cbrt": ((1,), sp.cbrt),
    "root": ((2,), sp.root),
    "abs": ((1,), sp.Abs),
    "binom": ((2,), lambda n, k: _safe_binomial(n, k)),
}

_INVERSE = {
    "sin": sp.asin,
    "cos": sp.acos,
    "tan": sp.atan,
    "sec": sp.asec,
    "csc": sp.acsc,
    "cot": sp.acot,
    "sinh": sp.asinh,
    "cosh": sp.acosh,
    "tanh": sp.atanh,
}

_INTEGRAL_NAMES = frozenset({"int", "integral"})

CONSTANTS: dict[str, sp.Expr] = {
    "pi": sp.pi,
    "e": sp.E,
    "oo": sp.oo,
    "inf": sp.oo,
    "infty": sp.oo,
    "infinity": sp.oo,
}

GREEK = (
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "theta",
    "lambda",
    "mu",
    "rho",
    "sigma",
    "tau",
    "phi",
    "psi",
    "omega",
)

RESERVED_NAMES = frozenset(_FUNCTIONS) | frozenset(CONSTANTS) | _INTEGRAL_NAMES

_NAME_RE = re.compile(r"[A-Za-z]+[0-9]*")
_LOG_BASE_RE = re.compile(r"log([0-9]+)")


# --------------------------------------------------------------------------- variables


@dataclass(frozen=True)
class VarSpec:
    """A variable's domain: decides SymPy assumptions and where we sample it."""

    domain: str = "real"
    lo: float | None = None
    hi: float | None = None

    DOMAINS = ("real", "positive", "nonnegative", "integer")

    def __post_init__(self) -> None:
        if self.domain not in self.DOMAINS:
            raise ValueError(f"unknown variable domain {self.domain!r}")

    @classmethod
    def coerce(cls, value: object) -> VarSpec:
        """Accept ``"real"``, ``"positive"``, ``"real[-1, 1]"``, a mapping, or a VarSpec."""
        if isinstance(value, VarSpec):
            return value
        if value is None:
            return cls()
        if isinstance(value, str):
            m = re.fullmatch(
                r"\s*([a-z]+)\s*(?:\[\s*([-+0-9.e]+)\s*,\s*([-+0-9.e]+)\s*\])?\s*", value
            )
            if not m:
                raise ValueError(f"bad variable spec {value!r}")
            lo = float(m.group(2)) if m.group(2) else None
            hi = float(m.group(3)) if m.group(3) else None
            return cls(m.group(1), lo, hi)
        if isinstance(value, Mapping):
            sample = value.get("sample") or (None, None)
            return cls(str(value.get("domain", "real")), sample[0], sample[1])
        raise ValueError(f"bad variable spec {value!r}")

    def assumptions(self) -> dict[str, bool]:
        return {self.domain: True}

    def bounds(self) -> tuple[float, float]:
        defaults = {
            "real": (-3.5, 3.5),
            "positive": (0.05, 4.0),
            "nonnegative": (0.0, 4.0),
            "integer": (-25, 25),
        }[self.domain]
        return (
            self.lo if self.lo is not None else defaults[0],
            self.hi if self.hi is not None else defaults[1],
        )

    def sample(self, rng: random.Random) -> mpmath.mpf:
        lo, hi = self.bounds()
        if self.domain == "integer":
            return mpmath.mpf(rng.randint(int(lo), int(hi)))
        return mpmath.mpf(rng.uniform(lo, hi))


def _spec_for_symbol(sym: sp.Symbol) -> VarSpec:
    if sym.is_integer:
        return VarSpec("integer")
    if sym.is_positive:
        return VarSpec("positive")
    if sym.is_nonnegative:
        return VarSpec("nonnegative")
    return VarSpec("real")


@dataclass(frozen=True)
class MathContext:
    """The names a problem allows, their SymPy symbols, and their sampling domains."""

    symbols: Mapping[str, sp.Symbol] = field(default_factory=dict)
    specs: Mapping[sp.Symbol, VarSpec] = field(default_factory=dict)
    constants: frozenset[str] = frozenset()
    allow_integral: bool = False

    @classmethod
    def build(
        cls,
        variables: Mapping[str, object] | Iterable[str] | None = None,
        *,
        constants: Iterable[str] = (),
        allow_integral: bool = False,
    ) -> MathContext:
        return cls().extend(variables, constants=constants, allow_integral=allow_integral)

    def extend(
        self,
        variables: Mapping[str, object] | Iterable[str] | None = None,
        *,
        constants: Iterable[str] = (),
        allow_integral: bool | None = None,
    ) -> MathContext:
        symbols = dict(self.symbols)
        specs = dict(self.specs)
        if variables is None:
            items: list[tuple[str, object]] = []
        elif isinstance(variables, Mapping):
            items = list(variables.items())
        else:
            items = [(name, "real") for name in variables]
        const_names = list(constants)
        items += [(name, "real") for name in const_names]
        for name, raw_spec in items:
            if not _NAME_RE.fullmatch(name) or name in RESERVED_NAMES:
                raise ValueError(f"invalid variable name {name!r}")
            spec = VarSpec.coerce(raw_spec)
            sym = sp.Symbol(name, **spec.assumptions())
            symbols[name] = sym
            specs[sym] = spec
        return MathContext(
            symbols=symbols,
            specs=specs,
            constants=self.constants | frozenset(const_names),
            allow_integral=self.allow_integral if allow_integral is None else allow_integral,
        )

    def __getitem__(self, name: str) -> sp.Symbol:
        return self.symbols[name]

    def spec(self, sym: sp.Symbol) -> VarSpec:
        return self.specs.get(sym) or _spec_for_symbol(sym)

    @property
    def variable_names(self) -> list[str]:
        return sorted(n for n in self.symbols if n not in self.constants)

    def parse(self, text: str) -> sp.Expr:
        return parse_math(text, self)


# --------------------------------------------------------------------------- normalize

_SUPERSCRIPT_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_SUPERSCRIPT_RE = re.compile("[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+")
_REPLACEMENTS = (
    ("−", "-"),
    ("–", "-"),
    ("—", "-"),
    ("×", "*"),
    ("·", "*"),
    ("⋅", "*"),
    ("∙", "*"),
    ("÷", "/"),
    ("π", " pi "),
    ("∞", " oo "),
    ("√", " sqrt "),
    ("∛", " cbrt "),
    ("θ", " theta "),
    ("φ", " phi "),
    ("ϕ", " phi "),
    ("α", " alpha "),
    ("β", " beta "),
    ("γ", " gamma "),
    ("δ", " delta "),
    ("ε", " epsilon "),
    ("λ", " lambda "),
    ("μ", " mu "),
    ("ρ", " rho "),
    ("σ", " sigma "),
    ("τ", " tau "),
    ("ψ", " psi "),
    ("ω", " omega "),
    ("≤", "<="),
    ("≥", ">="),
    ("≠", "!="),
    ("⟨", "<"),
    ("⟩", ">"),
    ("’", "'"),
    ("′", "'"),
    ("″", "''"),
    ("**", "^"),
)


def normalize(text: str) -> str:
    """Map common Unicode math characters to the ASCII syntax the parser understands."""
    s = _SUPERSCRIPT_RE.sub(lambda m: "^(" + m.group().translate(_SUPERSCRIPT_MAP) + ")", text)
    for old, new in _REPLACEMENTS:
        s = s.replace(old, new)
    s = re.sub(r"\blog_\{?\s*([0-9]+)\s*\}?", r"log\1", s)
    return s.strip()


# --------------------------------------------------------------------------- tokenizer

_TOKEN_RE = re.compile(r"\s*(?:(\d+\.\d*|\.\d+|\d+)|([A-Za-z]+[0-9]*)|([-+*/^(),!|]))")

Token = tuple[str, object, int]  # (type, value, position); type in {num, sym, func, op}


def _tokenize(text: str, ctx: MathContext) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    n = len(text)
    while pos < n:
        if text[pos:].strip() == "":
            break
        m = _TOKEN_RE.match(text, pos)
        if not m:
            ch = text[pos + len(text[pos:]) - len(text[pos:].lstrip())]
            if ch in "=<>":
                raise MathInputError(
                    "Enter an expression here, not an equation or inequality.", "NOT_AN_EXPRESSION"
                )
            raise MathInputError(f"ProofLab doesn't understand the character '{ch}'.")
        start = m.start(m.lastindex or 0)
        num, name, op = m.groups()
        if num is not None:
            tokens.append(("num", _number(num), start))
        elif name is not None:
            tokens.extend(_resolve_name(name, ctx, start))
        else:
            tokens.append(("op", op, start))
        pos = m.end()
        if len(tokens) > MAX_TOKENS:
            raise MathInputError("That input is too long for ProofLab to check.", "TOO_LONG")
    return tokens


def _number(text: str) -> sp.Expr:
    if "." in text:
        if len(text.replace(".", "")) > MAX_INT_DIGITS + 5:
            raise MathInputError("That number has too many digits.", "TOO_LONG")
        return sp.Float(text)
    if len(text) > MAX_INT_DIGITS:
        raise MathInputError("That number has too many digits.", "TOO_LONG")
    return sp.Integer(int(text))


def _known_names(ctx: MathContext) -> list[str]:
    names = set(_FUNCTIONS) | set(CONSTANTS) | set(GREEK)
    names |= {n for n in ctx.symbols if n.isalpha()}
    if ctx.allow_integral:
        names |= _INTEGRAL_NAMES
    return sorted(names, key=len, reverse=True)


def _unknown_name_error(name: str, ctx: MathContext) -> MathInputError:
    allowed = ", ".join(ctx.variable_names) or "no variables"
    return MathInputError(
        f"'{name}' isn't a variable or function ProofLab knows here. This problem uses: {allowed}.",
        "UNKNOWN_NAME",
    )


def _name_token(name: str, ctx: MathContext, pos: int) -> Token:
    if name in ctx.symbols:
        return ("sym", ctx.symbols[name], pos)
    if name in _FUNCTIONS or _LOG_BASE_RE.fullmatch(name):
        return ("func", name, pos)
    if name in _INTEGRAL_NAMES:
        if not ctx.allow_integral:
            raise MathInputError("Integrals can't be entered in this problem.", "UNKNOWN_NAME")
        return ("func", name, pos)
    if name in CONSTANTS:
        return ("sym", CONSTANTS[name], pos)
    raise _unknown_name_error(name, ctx)


def _resolve_name(raw: str, ctx: MathContext, pos: int) -> list[Token]:
    """Turn an identifier run like ``xsinx`` or ``C1`` into tokens."""
    if raw in ctx.symbols or raw in _FUNCTIONS or raw in CONSTANTS or _LOG_BASE_RE.fullmatch(raw):
        return [_name_token(raw, ctx, pos)]
    if raw in _INTEGRAL_NAMES:
        return [_name_token(raw, ctx, pos)]
    lower = raw.lower()
    if len(raw) > 1 and (lower in _FUNCTIONS or lower in CONSTANTS):
        return [_name_token(lower, ctx, pos)]

    m = re.fullmatch(r"([A-Za-z]+)([0-9]*)", raw)
    assert m is not None
    alpha, digits = m.groups()
    out: list[Token] = []
    names = _known_names(ctx)
    i = 0
    while i < len(alpha):
        for cand in names:
            if alpha.startswith(cand, i):
                break
        else:
            raise _unknown_name_error(alpha[i], ctx)
        if cand in GREEK and cand not in ctx.symbols:
            raise _unknown_name_error(cand, ctx)
        out.append(_name_token(cand, ctx, pos + i))
        i += len(cand)
    if digits:
        out.append(("num", _number(digits), pos + len(alpha)))
    return out


# --------------------------------------------------------------------------- parser


def _safe_pow(base: sp.Expr, exp: sp.Expr) -> sp.Expr:
    if exp.is_Number:
        if abs(exp) > MAX_EXPONENT:
            raise MathInputError("That exponent is too large to check.", "TOO_LARGE")
        if base.is_zero and exp.is_negative:
            raise MathInputError("Division by zero.", "DIVISION_BY_ZERO")
        if base.is_Integer and exp.is_Integer and exp > 0:
            bits = max(int(abs(base)).bit_length(), 1) * int(exp)
            if bits > MAX_RESULT_BITS:
                raise MathInputError("That number is too large to check.", "TOO_LARGE")
    return sp.Pow(base, exp)


def _safe_binomial(n: sp.Expr, k: sp.Expr) -> sp.Expr:
    """binom(n, k), "n choose k" (Book of Proof Section 3.4)."""
    if n.is_Integer and k.is_Integer:
        if n > MAX_FACTORIAL:
            raise MathInputError("That binomial coefficient is too large to check.", "TOO_LARGE")
        if n < 0:
            raise MathInputError("binom(n, k) needs n ≥ 0.")
    return sp.binomial(n, k)


def _safe_factorial(arg: sp.Expr) -> sp.Expr:
    if arg.is_Integer:
        if arg > MAX_FACTORIAL:
            raise MathInputError("That factorial is too large to check.", "TOO_LARGE")
        if arg < 0:
            raise MathInputError("Factorials of negative integers are undefined.")
    return sp.factorial(arg)


class _Parser:
    def __init__(self, tokens: list[Token], ctx: MathContext) -> None:
        self.toks = tokens
        self.i = 0
        self.ctx = ctx
        self.depth = 0
        self.abs_depth = 0

    # -- token helpers
    def peek(self) -> Token | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def advance(self) -> Token:
        tok = self.peek()
        if tok is None:
            raise MathInputError("The input ends too early. Is something missing?")
        self.i += 1
        return tok

    def at_op(self, ch: str) -> bool:
        tok = self.peek()
        return tok is not None and tok[0] == "op" and tok[1] == ch

    def expect_op(self, ch: str) -> None:
        if not self.at_op(ch):
            tok = self.peek()
            found = "the end of the input" if tok is None else f"'{_describe(tok)}'"
            raise MathInputError(f"Expected '{ch}' but found {found}.")
        self.i += 1

    def starts_atom(self, tok: Token | None) -> bool:
        if tok is None:
            return False
        kind, value, _ = tok
        if kind in ("num", "sym", "func"):
            return True
        return kind == "op" and (value == "(" or (value == "|" and self.abs_depth == 0))

    def enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise MathInputError("That input is nested too deeply to check.", "TOO_LONG")

    # -- grammar
    def parse(self) -> sp.Expr:
        if not self.toks:
            raise MathInputError("This is empty.", "EMPTY")
        expr = self.sum()
        tok = self.peek()
        if tok is not None:
            raise MathInputError(f"Unexpected '{_describe(tok)}'.")
        return expr

    def sum(self) -> sp.Expr:
        left = self.product()
        while self.at_op("+") or self.at_op("-"):
            op = self.advance()[1]
            right = self.product()
            left = left + right if op == "+" else left - right
        return left

    def product(self) -> sp.Expr:
        left = self.unary()
        while True:
            tok = self.peek()
            if self.at_op("*"):
                self.advance()
                left = left * self.unary()
            elif self.at_op("/"):
                self.advance()
                right = self.unary()
                if right.is_zero:
                    raise MathInputError("Division by zero.", "DIVISION_BY_ZERO")
                left = left / right
            elif self.starts_atom(tok):
                assert tok is not None
                prev = self.toks[self.i - 1]
                if tok[0] == "num" and prev[0] == "num":
                    raise MathInputError(
                        "Two numbers are next to each other. Use * to multiply them."
                    )
                left = left * self.power()
            else:
                return left

    def unary(self) -> sp.Expr:
        self.enter()
        try:
            if self.at_op("-"):
                self.advance()
                return -self.unary()
            if self.at_op("+"):
                self.advance()
                return self.unary()
            return self.power()
        finally:
            self.depth -= 1

    def power(self) -> sp.Expr:
        base = self.postfix()
        if self.at_op("^"):
            self.advance()
            return _safe_pow(base, self.unary())
        return base

    def postfix(self) -> sp.Expr:
        value = self.atom()
        while self.at_op("!"):
            self.advance()
            value = _safe_factorial(value)
        return value

    def atom(self) -> sp.Expr:
        self.enter()
        try:
            kind, value, _ = self.advance()
            if kind in ("num", "sym"):
                return value  # type: ignore[return-value]
            if kind == "func":
                return self.call(str(value))
            if value == "(":
                inner = self.sum()
                self.expect_op(")")
                return inner
            if value == "|":
                self.abs_depth += 1
                inner = self.sum()
                self.expect_op("|")
                self.abs_depth -= 1
                return sp.Abs(inner)
            raise MathInputError(f"Unexpected '{value}'.")
        finally:
            self.depth -= 1

    def call(self, name: str) -> sp.Expr:
        power: sp.Expr | None = None
        if self.at_op("^"):
            self.advance()
            power = self.unary()
        if self.at_op("("):
            self.advance()
            args = [self.sum()]
            while self.at_op(","):
                self.advance()
                args.append(self.sum())
            self.expect_op(")")
        else:
            args = [self.implicit_argument(name)]
        return self.apply(name, args, power)

    def implicit_argument(self, name: str) -> sp.Expr:
        # "sin x", "sin 2x", "ln x^2", "sqrt x" — a number and/or variables, no operators.
        tok = self.peek()
        if tok is not None and tok[0] == "op" and tok[1] == "|" and self.abs_depth == 0:
            return self.atom()  # ln|x|
        if tok is None or tok[0] not in ("num", "sym"):
            raise MathInputError(f"Put the input of {name} in parentheses, like {name}(x).")
        factors = []
        if tok[0] == "num":
            factors.append(self.power())
        while (tok := self.peek()) is not None and tok[0] == "sym":
            factors.append(self.power())
        return sp.Mul(*factors)

    def apply(self, name: str, args: list[sp.Expr], power: sp.Expr | None) -> sp.Expr:
        if name in _INTEGRAL_NAMES:
            value = self.integral(args)
        elif m := _LOG_BASE_RE.fullmatch(name):
            if len(args) != 1:
                raise MathInputError(f"{name} takes one input.")
            value = sp.log(args[0], int(m.group(1)))
        else:
            arities, fn = _FUNCTIONS[name]
            if len(args) not in arities:
                want = " or ".join(str(a) for a in arities)
                raise MathInputError(f"{name} takes {want} input(s), not {len(args)}.")
            if power is not None and power == -1 and name in _INVERSE:
                return _INVERSE[name](*args)
            value = fn(*args)
        if power is not None:
            value = _safe_pow(value, power)
        return value

    def integral(self, args: list[sp.Expr]) -> sp.Expr:
        if len(args) not in (2, 4) or not isinstance(args[1], sp.Symbol):
            raise MathInputError("Write integrals as int(f, x) or int(f, x, a, b).")
        if len(args) == 2:
            return sp.Integral(args[0], args[1])
        return sp.Integral(args[0], (args[1], args[2], args[3]))


def _describe(tok: Token) -> str:
    kind, value, _ = tok
    if kind == "func":
        return str(value)
    if kind == "sym":
        return str(value)
    return str(value)


def parse_math(text: str, ctx: MathContext) -> sp.Expr:
    """Parse one expression typed by a student (or a content author)."""
    if not isinstance(text, str):
        raise TypeError("parse_math expects a string")
    if len(text) > MAX_INPUT_CHARS:
        raise MathInputError("That input is too long for ProofLab to check.", "TOO_LONG")
    s = normalize(text)
    if not s:
        raise MathInputError("This is empty.", "EMPTY")
    return _Parser(_tokenize(s, ctx), ctx).parse()


# --------------------------------------------------------------------------- labels, latex

_LABEL_RE = re.compile(
    r"""^\s*(?:
        [A-Za-z][A-Za-z0-9]*'*\s*(?:\(\s*[A-Za-z0-9,\s]*\))?   # f(x), f'(x), y', g''(t), F(x, y)
      | [d∂]\^?\d*\s*[A-Za-z]*\s*/\s*[d∂]\s*[A-Za-z]\^?\d*       # dy/dx, d/dx, d^2y/dx^2, ∂f/∂x
      | [A-Za-z]_[A-Za-z]+\s*(?:\([^()=]*\))?                   # f_x, f_xy, f_x(1, 2)
    )\s*=(?!=)""",
    re.X,
)


def strip_label(text: str) -> str:
    """``f'(x) = 2x`` → ``2x``. Leaves anything without a recognisable label alone."""
    m = _LABEL_RE.match(text)
    if m and "=" not in text[m.end() :]:
        return text[m.end() :]
    return text


def to_latex(expr: sp.Basic) -> str:
    return sp.latex(expr, ln_notation=True)


# --------------------------------------------------------------------------- numerics


def _as_basic(value: object) -> sp.Basic:
    if isinstance(value, str):
        raise TypeError("use parse_math for strings")
    if isinstance(value, bool):
        raise TypeError("booleans are not expressions")
    if isinstance(value, int):
        return sp.Integer(value)
    if isinstance(value, Fraction):
        return sp.Rational(value.numerator, value.denominator)
    if isinstance(value, float):
        return sp.Float(value)
    if isinstance(value, sp.Basic):
        return value
    raise TypeError(f"not an expression: {type(value).__name__}")


def _finite_mpc(value: object) -> mpmath.mpc | None:
    try:
        c = mpmath.mpc(value)
    except (TypeError, ValueError):
        return None
    if not (mpmath.isfinite(c.real) and mpmath.isfinite(c.imag)):
        return None
    return c


def _is_real(c: mpmath.mpc, tol: float) -> bool:
    return abs(c.imag) <= tol * max(1, abs(c.real))


def _close(a: mpmath.mpc, b: mpmath.mpc, tol: float) -> bool:
    return abs(a - b) <= tol * max(1, abs(a), abs(b))


def has_infinity(expr: sp.Basic) -> bool:
    return any(expr.has(v) for v in (sp.oo, -sp.oo, sp.zoo, sp.nan))


def contains_float(expr: sp.Basic) -> bool:
    return any(isinstance(node, sp.Float) for node in sp.preorder_traversal(expr))


def compile_numeric(expr: sp.Basic, symbols: Sequence[sp.Symbol]) -> Callable[..., object]:
    """Compile a SymPy expression (built by our parser or by SymPy) for mpmath evaluation."""
    return sp.lambdify(list(symbols), expr, modules=["mpmath"])


def _call(fn: Callable[..., object], point: Sequence[object]) -> mpmath.mpc | None:
    try:
        return _finite_mpc(fn(*point))
    except Exception:  # noqa: BLE001 — any evaluation failure just means "skip this point"
        return None


def numeric_value(expr: object, *, dps: int = 30) -> mpmath.mpc | None:
    """Evaluate a closed-form constant expression; ``None`` if undefined or not finite."""
    e = _as_basic(expr)
    if e.free_symbols or has_infinity(e):
        return None
    with mpmath.workdps(dps):
        try:
            return _call(compile_numeric(e, []), [])
        except Exception:  # noqa: BLE001
            return None


def real_value(expr: object, *, tol: float = DEFAULT_TOL) -> float | None:
    """Like :func:`numeric_value` but only for real results; returns a float."""
    v = numeric_value(expr)
    if v is None or not _is_real(v, tol):
        return None
    return float(v.real)


def _sample_points(
    symbols: Sequence[sp.Symbol], ctx: MathContext | None, tries: int, seed: int
) -> Iterable[list[mpmath.mpf]]:
    rng = random.Random(seed)
    specs = [ctx.spec(s) if ctx else _spec_for_symbol(s) for s in symbols]
    for _ in range(tries):
        yield [spec.sample(rng) for spec in specs]


def equivalent(
    a: object,
    b: object,
    ctx: MathContext | None = None,
    *,
    tol: float = DEFAULT_TOL,
    want: int = 8,
    min_points: int = 4,
    tries: int = 60,
    symbolic_fallback: bool = True,
) -> bool | None:
    """Are ``a`` and ``b`` equal on their common real domain?

    ``True``/``False`` when decided, ``None`` when ProofLab can't tell (SPEC §6).
    """
    ea, eb = _as_basic(a), _as_basic(b)
    if ea == eb:
        return True
    if has_infinity(ea) or has_infinity(eb):
        return False
    symbols = sorted(ea.free_symbols | eb.free_symbols, key=str)
    if not symbols:
        va, vb = numeric_value(ea), numeric_value(eb)
        if va is None or vb is None:
            return None
        return _close(va, vb, tol)

    agree = domain_mismatch = 0
    with mpmath.workdps(30):
        fa, fb = compile_numeric(ea, symbols), compile_numeric(eb, symbols)
        for point in _sample_points(symbols, ctx, tries, SEED):
            va, vb = _call(fa, point), _call(fb, point)
            if va is None or vb is None:
                continue
            ra, rb = _is_real(va, tol), _is_real(vb, tol)
            if not (ra and rb):
                domain_mismatch += ra != rb
                continue
            if not _close(va, vb, tol):
                return False
            agree += 1
            if agree >= want:
                return True
    if agree >= min_points:
        return True
    if agree == 0 and domain_mismatch >= min_points:
        return False
    if symbolic_fallback:
        try:
            diff = sp.simplify(ea - eb)
        except Exception:  # noqa: BLE001
            return None
        if diff == 0:
            return True
        if diff.is_number and diff.is_zero is False:
            return False
    return None


def approximately_equal(
    a: object, b: object, ctx: MathContext | None = None, rel: float = 1e-3
) -> bool:
    return bool(equivalent(a, b, ctx, tol=rel, symbolic_fallback=False))


def nice_number(value: mpmath.mpc | float) -> sp.Expr:
    """Best-effort exact form for a float (small rationals, multiples of pi)."""
    x = float(mpmath.mpf(value.real) if isinstance(value, mpmath.mpc) else value)
    guess = sp.nsimplify(x, [sp.pi], tolerance=1e-9, rational=False)
    if sp.count_ops(guess) <= 6 and abs(float(guess) - x) <= 1e-9 * max(1.0, abs(x)):
        return guess
    return sp.Float(x, 6)


def relation(
    student: object, key: object, ctx: MathContext | None = None, *, tol: float = 1e-8
) -> tuple[str, sp.Expr | None] | None:
    """How a wrong answer relates to the key.

    Returns ``("negated", None)``, ``("scaled", k)``, ``("shifted", c)`` or ``None``.
    """
    es, ek = _as_basic(student), _as_basic(key)
    if has_infinity(es) or has_infinity(ek):
        return None
    symbols = sorted(es.free_symbols | ek.free_symbols, key=str)
    ratios: list[mpmath.mpc] = []
    diffs: list[mpmath.mpc] = []
    with mpmath.workdps(30):
        fs, fk = compile_numeric(es, symbols), compile_numeric(ek, symbols)
        points = _sample_points(symbols, ctx, 40, SEED + 1) if symbols else [[]]
        for point in points:
            vs, vk = _call(fs, point), _call(fk, point)
            if vs is None or vk is None or not (_is_real(vs, tol) and _is_real(vk, tol)):
                continue
            diffs.append(vs - vk)
            if abs(vk) > tol:
                ratios.append(vs / vk)
            if len(diffs) >= 8:
                break
    if not diffs:
        return None

    def constant(values: list[mpmath.mpc]) -> mpmath.mpc | None:
        if len(values) < (1 if not symbols else 4):
            return None
        if all(_close(v, values[0], tol) for v in values):
            return values[0]
        return None

    k = constant(ratios)
    if k is not None and not _close(k, mpmath.mpc(1), tol) and abs(k) > tol:
        if _close(k, mpmath.mpc(-1), tol):
            return ("negated", None)
        return ("scaled", nice_number(k))
    c = constant(diffs)
    if c is not None and abs(c) > tol:
        return ("shifted", nice_number(c))
    return None


# --------------------------------------------------------------------------- structure


def split_top(text: str, sep: str = ",") -> list[str]:
    """Split on ``sep`` outside of (), [], {}."""
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts]


_REL_OPS = ("<=", ">=", "!=", "==", "=", "<", ">")


def split_relation(text: str) -> tuple[list[str], list[str]]:
    """Split ``a < x <= b`` into ``(["a", "x", "b"], ["<", "<="])`` at the top level."""
    parts: list[str] = []
    ops: list[str] = []
    depth, start, i = 0, 0, 0
    while i < len(text):
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 0:
            for op in _REL_OPS:
                if text.startswith(op, i):
                    parts.append(text[start:i].strip())
                    ops.append("=" if op == "==" else op)
                    i += len(op)
                    start = i
                    break
            else:
                i += 1
                continue
            continue
        i += 1
    parts.append(text[start:].strip())
    return parts, ops


def parse_equation(text: str, ctx: MathContext) -> tuple[sp.Expr, sp.Expr]:
    """``lhs = rhs`` → ``(lhs, rhs)``."""
    parts, ops = split_relation(normalize(text))
    if ops != ["="]:
        raise MathInputError("Write an equation with exactly one '='.", "NOT_AN_EQUATION")
    return ctx.parse(parts[0]), ctx.parse(parts[1])


def strip_outer(text: str, pairs: str = "()[]{}<>") -> str:
    t = text.strip()
    for open_, close in zip(pairs[::2], pairs[1::2], strict=True):
        if len(t) >= 2 and t[0] == open_ and t[-1] == close:
            depth = 0
            for idx, ch in enumerate(t):
                depth += ch == open_
                depth -= ch == close
                if depth == 0 and idx != len(t) - 1:
                    break
            else:
                return t[1:-1].strip()
    return t


def parse_tuple(text: str, ctx: MathContext, n: int | None = None) -> list[sp.Expr]:
    """``<a, b, c>``, ``(a, b, c)`` or ``[a, b, c]`` → list of expressions."""
    t = strip_outer(normalize(text))
    parts = split_top(t, ",")
    if any(not p for p in parts):
        raise MathInputError("One of the components is empty.", "EMPTY")
    if n is not None and len(parts) != n:
        raise MathInputError(f"Expected {n} components, got {len(parts)}.", "WRONG_DIMENSION")
    return [ctx.parse(p) for p in parts]


# --------------------------------------------------------------------------- value sets

_EMPTY_WORDS = {
    "no solution",
    "no solutions",
    "no real solution",
    "no real solutions",
    "none",
    "empty",
    "empty set",
    "{}",
    "∅",
}


def parse_value_list(text: str, ctx: MathContext, var: sp.Symbol | None = None) -> list[sp.Expr]:
    """``x = 2 or x = -3`` / ``{2, -3}`` / ``2, -3`` / ``no solution`` → values."""
    raw = text.strip()
    if raw.lower() in _EMPTY_WORDS:
        return []
    t = strip_outer(normalize(raw), "{}")
    if not t:
        return []
    t = re.sub(r"\b(or|and)\b", ",", t)
    values: list[sp.Expr] = []
    for part in split_top(t, ","):
        if not part:
            continue
        pieces, ops = split_relation(part)
        if ops:
            if ops != ["="] or (var is not None and pieces[0].strip() != str(var)):
                raise MathInputError(
                    f"Write each solution as {var or 'x'} = value, separated by 'or' or commas.",
                    "BAD_SOLUTION_LIST",
                )
            part = pieces[1]
        values.append(ctx.parse(part))
    return dedupe_values(values)


def dedupe_values(values: Iterable[sp.Expr], tol: float = DEFAULT_TOL) -> list[sp.Expr]:
    out: list[sp.Expr] = []
    for v in values:
        if not any(values_equal(v, w, tol) for w in out):
            out.append(v)
    return out


def values_equal(a: object, b: object, tol: float = DEFAULT_TOL) -> bool:
    ea, eb = _as_basic(a), _as_basic(b)
    if ea == eb:
        return True
    va, vb = numeric_value(ea), numeric_value(eb)
    return va is not None and vb is not None and _close(va, vb, tol)


def match_values(
    student: Sequence[sp.Expr], key: Sequence[sp.Expr], tol: float = DEFAULT_TOL
) -> tuple[list[sp.Expr], list[sp.Expr]]:
    """``(missing, extra)``: key values the student lacks, student values not in the key."""
    missing = [k for k in key if not any(values_equal(k, s, tol) for s in student)]
    extra = [s for s in student if not any(values_equal(s, k, tol) for k in key)]
    return missing, extra


def satisfies(
    lhs: sp.Expr, rhs: sp.Expr, var: sp.Symbol, value: sp.Expr, tol: float = 1e-9
) -> bool:
    """Does ``var = value`` make both sides real, finite and equal?"""
    try:
        left = numeric_value(lhs.subs(var, value))
        right = numeric_value(rhs.subs(var, value))
    except Exception:  # noqa: BLE001
        return False
    if left is None or right is None:
        return False
    if not (_is_real(left, tol) and _is_real(right, tol)):
        return False
    return _close(left, right, tol)


def _in_set(value: sp.Expr, domain: sp.Set) -> bool:
    try:
        contained = domain.contains(value)
        if contained in (sp.true, sp.false):
            return bool(contained)
    except Exception:  # noqa: BLE001
        pass
    v = real_value(value)
    if v is None:
        return False
    try:
        return bool(domain.contains(sp.Float(v, 30)))
    except Exception:  # noqa: BLE001
        return False


def _finite_elements(s: object) -> list[sp.Expr] | None:
    if s is None:
        return None
    if s == sp.S.EmptySet:
        return []
    if isinstance(s, sp.FiniteSet):
        return list(s)
    return None


def real_solutions(
    lhs: sp.Expr, rhs: sp.Expr, var: sp.Symbol, domain: sp.Set = sp.S.Reals
) -> list[sp.Expr] | None:
    """Real solutions of ``lhs = rhs`` in ``domain``, each verified by substitution.

    ``None`` if SymPy can't produce a finite list (e.g. infinitely many solutions).
    """
    expr = lhs - rhs
    values: list[sp.Expr] | None
    try:
        values = _finite_elements(sp.solveset(expr, var, domain))
    except Exception:  # noqa: BLE001
        values = None
    if domain != sp.S.Reals:
        # solveset on a bounded interval can miss roots (2sin²x − sin x − 1 = 0 on [0, 2π)
        # returns only π/2); solving over ℝ and intersecting finds them. Candidates are all
        # verified by substitution below, so the union is safe.
        try:
            via_reals = _finite_elements(sp.solveset(expr, var, sp.S.Reals).intersect(domain))
        except Exception:  # noqa: BLE001
            via_reals = None
        if via_reals is not None:
            values = [*(values or []), *via_reals]
    if values is None:
        try:
            candidates = sp.solve(sp.Eq(lhs, rhs), var, dict=False)
            if isinstance(candidates, list) and all(isinstance(c, sp.Expr) for c in candidates):
                values = [c for c in candidates if _in_set(c, domain)]
        except Exception:  # noqa: BLE001
            values = None
    if values is None:
        return None
    return dedupe_values(v for v in values if satisfies(lhs, rhs, var, v))


# --------------------------------------------------------------------------- real sets

_REALS_WORDS = {"r", "ℝ", "reals", "all reals", "all real numbers", "real numbers", "(-oo,oo)"}


def parse_real_set(text: str, ctx: MathContext, var: sp.Symbol) -> sp.Set:
    """Interval notation, finite sets or inequalities in ``var`` → a SymPy set.

    ``(-oo, 2) U (2, oo)``, ``[0, oo)``, ``{1, 2}``, ``x >= 2``, ``-1 < x <= 3``,
    ``x < 0 or x > 1``, ``x != 2``, ``all real numbers``, ``∅``.
    """
    raw = text.strip()
    low = re.sub(r"\s+", "", normalize(raw).lower())
    if raw.lower() in _EMPTY_WORDS:
        return sp.S.EmptySet
    if raw.lower() in _REALS_WORDS or low in _REALS_WORDS:
        return sp.S.Reals
    t = normalize(raw).replace("∪", " U ")
    pieces = _split_union(t)
    result: sp.Set = sp.S.EmptySet
    for piece in pieces:
        result = sp.Union(result, _parse_set_piece(piece, ctx, var))
    return result


def _split_union(text: str) -> list[str]:
    out, depth, cur, i = [], 0, [], 0
    while i < len(text):
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if depth == 0:
            m = re.match(r"\s+(U|u|or)\s+", text[i:])
            if m:
                out.append("".join(cur))
                cur = []
                i += m.end()
                continue
        cur.append(ch)
        i += 1
    out.append("".join(cur))
    return [p.strip() for p in out if p.strip()]


def _parse_set_piece(piece: str, ctx: MathContext, var: sp.Symbol) -> sp.Set:
    if piece.lower() in _EMPTY_WORDS:
        return sp.S.EmptySet
    if piece[0] in "([" and piece[-1] in ")]":
        inner = piece[1:-1]
        bounds = split_top(inner, ",")
        if len(bounds) == 2:
            lo, hi = ctx.parse(bounds[0]), ctx.parse(bounds[1])
            if lo.free_symbols or hi.free_symbols:
                raise MathInputError("Interval endpoints must be numbers.", "BAD_INTERVAL")
            return sp.Interval(lo, hi, left_open=piece[0] == "(", right_open=piece[-1] == ")")
    if piece[0] == "{" and piece[-1] == "}":
        return sp.FiniteSet(*parse_value_list(piece, ctx, var))
    conjuncts = re.split(r"\s+and\s+", piece)
    result: sp.Set = sp.S.Reals
    for c in conjuncts:
        result = sp.Intersection(result, _inequality_set(c, ctx, var))
    return result


def _inequality_set(text: str, ctx: MathContext, var: sp.Symbol) -> sp.Set:
    parts, ops = split_relation(text)
    if not ops or "=" in ops:
        raise MathInputError(
            "Write the set in interval notation, like (-oo, 2) U (2, oo), or as an inequality.",
            "BAD_SET",
        )
    exprs = [ctx.parse(p) for p in parts]
    builders = {"<": sp.Lt, "<=": sp.Le, ">": sp.Gt, ">=": sp.Ge, "!=": sp.Ne}
    result: sp.Set = sp.S.Reals
    for left, op, right in zip(exprs, ops, exprs[1:], strict=False):
        rel = builders[op](left, right)
        if rel.free_symbols - {var}:
            raise MathInputError(f"Use only {var} in the inequality.", "BAD_SET")
        try:
            result = sp.Intersection(result, rel.as_set())
        except Exception as exc:  # noqa: BLE001
            raise MathInputError("ProofLab couldn't read that inequality.", "BAD_SET") from exc
    return result


def sets_equal(a: sp.Set, b: sp.Set) -> bool:
    try:
        return bool(sp.Complement(a, b) == sp.S.EmptySet and sp.Complement(b, a) == sp.S.EmptySet)
    except Exception:  # noqa: BLE001
        return False


def set_difference_is_finite(a: sp.Set, b: sp.Set) -> bool:
    """True when ``a`` and ``b`` differ only at isolated points (e.g. endpoints)."""
    try:
        d = sp.Union(sp.Complement(a, b), sp.Complement(b, a))
    except Exception:  # noqa: BLE001
        return False
    return isinstance(d, sp.FiniteSet) and len(d) > 0


def set_latex(s: sp.Set) -> str:
    return sp.latex(s)


# --------------------------------------------------------------------------- integers


def is_integer_polynomial(expr: sp.Expr, integer_symbols: Iterable[sp.Symbol]) -> bool:
    """Is ``expr`` a polynomial with integer coefficients in integer-valued symbols?

    If so it is an integer for every integer input (closure of ℤ under + and ×).
    """
    allowed = set(integer_symbols)
    e = sp.expand(expr)
    if not e.free_symbols <= allowed:
        return False
    if not e.free_symbols:
        return bool(e.is_Integer)
    try:
        poly = sp.Poly(e, *sorted(e.free_symbols, key=str))
    except sp.PolynomialError:
        return False
    return all(c.is_Integer for c in poly.coeffs())


def is_integer_valued_polynomial(
    expr: sp.Expr, integer_symbols: Iterable[sp.Symbol], max_points: int = 4096
) -> bool:
    """Is ``expr`` a polynomial (rational coefficients allowed) that is an integer at every
    integer point, like k(k + 1)/2?

    Exact: a polynomial of degree ≤ dᵢ in each xᵢ is integer-valued on ℤⁿ exactly when it is an
    integer combination of products of binomials C(xᵢ, j), and those coefficients are the finite
    differences of its values on the grid {0, …, d₁} × ⋯ × {0, …, dₙ}. So integer values on that
    grid prove integer values everywhere.
    """
    if is_integer_polynomial(expr, integer_symbols):
        return True
    allowed = set(integer_symbols)
    e = sp.expand(expr)
    if not e.free_symbols or not e.free_symbols <= allowed:
        return False
    syms = sorted(e.free_symbols, key=str)
    try:
        poly = sp.Poly(e, *syms)
    except sp.PolynomialError:
        return False
    if not all(c.is_Rational for c in poly.coeffs()):
        return False
    degrees = [poly.degree(s) for s in syms]
    total = 1
    for d in degrees:
        total *= d + 1
    if total > max_points:
        return False
    for point in itertools.product(*(range(d + 1) for d in degrees)):
        if not poly.eval(dict(zip(syms, point, strict=True))).is_Integer:
            return False
    return True


def linear_in(expr: sp.Expr, sym: sp.Symbol) -> tuple[sp.Expr, sp.Expr] | None:
    """``expr == a*sym + b`` with ``a``, ``b`` free of ``sym`` → ``(a, b)``; else ``None``."""
    e = sp.expand(expr)
    a = sp.diff(e, sym)
    if a.has(sym):
        return None
    b = sp.expand(e - a * sym)
    if b.has(sym):
        return None
    return a, b
