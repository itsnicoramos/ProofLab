"""Finite sets (SPEC §5.1): a safe parser and evaluator for set literals and set expressions.

Values are plain Python objects so they hash and compare as sets:

- numbers: canonical SymPy expressions (``2``, ``-1/2``, ``sqrt(3)``, ``pi``)
- atoms: letters or names a problem declares as elements (``a``, ``b``, ``R``): :class:`Atom`
- ordered tuples: ``tuple``
- sets: ``frozenset``

Set expressions (steps and problem data)::

    expr    := chain of ∪, or of ∩, or of − (mixing them needs parentheses)
    operand := factor (× factor)*                 A × B × C gives triples
    factor  := primary ( ' | ^c | ^n )*           complement, Cartesian power
    primary := ( expr ) | literal | NAME | P(expr) | comp(expr)
    literal := { element, element, ... } | ∅

Elements inside braces are literals, tuples ``(e1, e2, ...)``, ``...`` (a run of integers, as in
``{1, 2, ..., 9}``), declared atoms, or numbers in ProofLab's math syntax. Student input never
reaches ``eval``/``sympify``: numbers go through :func:`prooflab.engine.algebra.parse_math`.
Set-builder notation (:class:`Builder`) is only accepted in problem data, never from students.
"""

from __future__ import annotations

import itertools
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field

from prooflab.engine.algebra import (
    MAX_INPUT_CHARS,
    MathContext,
    MathInputError,
    has_infinity,
    normalize,
    split_relation,
    split_top,
)

MAX_ELEMENTS = 5000  # largest set ProofLab builds
MAX_POWER_SET_BASE = 12  # P(S) only for |S| ≤ 12 (4096 subsets)
MAX_DEPTH = 12  # nesting of sets/tuples/parentheses


@dataclass(frozen=True, order=True)
class Atom:
    """A named element such as ``a`` or ``R`` (the set of reals, used as an element)."""

    name: str


SetValue = frozenset
Value = object  # sp.Expr | Atom | tuple | frozenset

_ATOM_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_NAME_RE = re.compile(r"^[A-Z](?:_?[0-9]+)?$")
_BLACKBOARD = {"R", "Q", "N", "Z", "C"}


def _error(detail: str, code: str = "SET_SYNTAX") -> MathInputError:
    return MathInputError(detail, code)


# --------------------------------------------------------------------------- normalize

_UNICODE = (
    ("\\{", "{"),
    ("\\}", "}"),
    ("\\left", ""),
    ("\\right", ""),
    ("\\cup", "∪"),
    ("\\cap", "∩"),
    ("\\setminus", "−"),
    ("\\times", "×"),
    ("\\emptyset", "∅"),
    ("\\varnothing", "∅"),
    ("\\mathscr{P}", "P"),
    ("\\mathcal{P}", "P"),
    ("\\ldots", "..."),
    ("\\dots", "..."),
    ("\\cdots", "..."),
    ("…", "..."),
    ("𝒫", "P"),
    ("℘", "P"),
    ("Ø", "∅"),
    ("ø", "∅"),
    ("⌀", "∅"),
    ("∖", "−"),
    ("ℝ", "R"),
    ("ℚ", "Q"),
    ("ℕ", "N"),
    ("ℤ", "Z"),
    ("\u0305", "'"),  # combining overline: A̅ is the complement of A
    ("\u0304", "'"),
    ("’", "'"),
    ("′", "'"),
)
_LATEX_GROUP_RE = re.compile(r"\\(?:overline|bar)\{([^{}]*)\}")
_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_SUPERSCRIPT_RE = re.compile("[⁰¹²³⁴⁵⁶⁷⁸⁹]+")
_MATHBB_RE = re.compile(r"\\mathbb\{([A-Z])\}")


def normalize_sets(text: str) -> str:
    s = _SUPERSCRIPT_RE.sub(lambda m: "^" + m.group().translate(_SUPERSCRIPTS), text)
    s = _LATEX_GROUP_RE.sub(r"comp(\1)", s)
    s = _MATHBB_RE.sub(r"\1", s)
    for old, new in _UNICODE:
        s = s.replace(old, new)
    return s.strip()


# --------------------------------------------------------------------------- canonical values


def canon_number(expr: sp.Expr) -> sp.Expr:
    """A canonical form, so equal numbers written differently hash the same."""
    if expr.has(sp.Float):
        expr = sp.nsimplify(expr, rational=True)
    if expr.is_Rational:
        return expr
    return sp.radsimp(sp.expand(expr))


def _check_size(n: int) -> None:
    if n > MAX_ELEMENTS:
        raise _error("That set is too large for ProofLab to work with.", "SET_TOO_LARGE")


def power_set(s: frozenset) -> frozenset:
    if len(s) > MAX_POWER_SET_BASE:
        raise _error("That power set is too large for ProofLab to list.", "SET_TOO_LARGE")
    items = list(s)
    return frozenset(
        frozenset(c) for r in range(len(items) + 1) for c in itertools.combinations(items, r)
    )


def product(sets: list[frozenset]) -> frozenset:
    size = math.prod(len(s) for s in sets)
    _check_size(size)
    return frozenset(itertools.product(*sets))


# --------------------------------------------------------------------------- display


def sort_key(v: Value) -> tuple:
    if isinstance(v, frozenset):
        return (3, len(v), tuple(sorted(sort_key(x) for x in v)))
    if isinstance(v, tuple):
        return (2, len(v), tuple(sort_key(x) for x in v))
    if isinstance(v, Atom):
        return (1, 0.0, v.name)
    try:
        num = float(sp.N(v))
    except (TypeError, ValueError):
        num = 0.0
    return (0, num, str(v))


def latex(v: Value) -> str:
    if isinstance(v, frozenset):
        if not v:
            return r"\emptyset"
        return r"\{" + ", ".join(latex(x) for x in sorted(v, key=sort_key)) + r"\}"
    if isinstance(v, tuple):
        return "(" + ", ".join(latex(x) for x in v) + ")"
    if isinstance(v, Atom):
        if v.name in _BLACKBOARD:
            return rf"\mathbb{{{v.name}}}"
        return v.name if len(v.name) == 1 else rf"\mathrm{{{v.name}}}"
    return sp.latex(v)


def text(v: Value) -> str:
    """Plain-text form in ProofLab's input syntax (used for answer keys)."""
    if isinstance(v, frozenset):
        if not v:
            return "∅"
        return "{" + ", ".join(text(x) for x in sorted(v, key=sort_key)) + "}"
    if isinstance(v, tuple):
        return "(" + ", ".join(text(x) for x in v) + ")"
    if isinstance(v, Atom):
        return v.name
    return re.sub(r"\bE\b", "e", sp.sstr(v).replace("**", "^"))


# --------------------------------------------------------------------------- elements


@dataclass(frozen=True)
class ElementContext:
    """What may appear as an element: declared atom names, plus numbers."""

    atoms: frozenset[str] = frozenset()

    @classmethod
    def build(cls, atoms: Iterable[str] = ()) -> ElementContext:
        names = frozenset(atoms)
        for name in names:
            if not _ATOM_RE.fullmatch(name):
                raise ValueError(f"bad atom name {name!r}")
        return cls(names)

    def describe(self) -> str:
        if not self.atoms:
            return "Elements here are numbers (and sets or ordered pairs of numbers)."
        names = ", ".join(sorted(self.atoms))
        return f"Elements here are numbers and the letters/names {names}."


_ELLIPSIS = object()
_EMPTY_WORDS = {"∅", "{}", "emptyset", "empty", "varnothing"}


def _matching(textval: str, start: int) -> int:
    """Index of the bracket closing the one at ``start`` (or -1)."""
    pairs = {"{": "}", "(": ")", "[": "]"}
    stack: list[str] = []
    for i in range(start, len(textval)):
        ch = textval[i]
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in ")]}":
            if not stack or stack.pop() != ch:
                return -1
            if not stack:
                return i
    return -1


def parse_literal(raw: str, ectx: ElementContext, depth: int = 0) -> frozenset:
    """``{1, 2, (a, b), {3}}`` or ``∅`` → frozenset. Nothing else is accepted."""
    if depth == 0:
        if len(raw) > MAX_INPUT_CHARS:
            raise _error("That input is too long for ProofLab to check.", "TOO_LONG")
        raw = normalize_sets(raw)
    t = raw.strip()
    if t.lower() in _EMPTY_WORDS:
        return frozenset()
    if not t.startswith("{") or _matching(t, 0) != len(t) - 1:
        raise _error(
            "Write the set by listing its elements between braces, like {1, 2, 3} "
            "(∅ for the empty set).",
            "SET_NOT_A_LIST",
        )
    if depth > MAX_DEPTH:
        raise _error("That set is nested too deeply for ProofLab to check.", "TOO_LONG")
    inner = t[1:-1].strip()
    if not inner:
        return frozenset()
    if ":" in _top_level(inner) or "∈" in _top_level(inner):
        raise _error(
            "ProofLab can't evaluate set-builder notation here. List the elements instead.",
            "SET_BUILDER",
        )
    items = [parse_element(part, ectx, depth + 1) for part in split_top(inner, ",")]
    values = _expand_ellipses(items)
    _check_size(len(values))
    return frozenset(values)


def _top_level(s: str) -> str:
    """The characters of ``s`` outside any brackets."""
    out, depth = [], 0
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def parse_element(raw: str, ectx: ElementContext, depth: int = 0) -> Value:
    t = raw.strip()
    if not t:
        raise _error("One of the elements is empty (check for a doubled comma).", "EMPTY")
    if depth > MAX_DEPTH:
        raise _error("That set is nested too deeply for ProofLab to check.", "TOO_LONG")
    if t in ("...", ". . .", ".."):
        return _ELLIPSIS
    if t.lower() in _EMPTY_WORDS or t.startswith("{"):
        return parse_literal(t, ectx, depth)
    if t.startswith("(") and _matching(t, 0) == len(t) - 1:
        parts = split_top(t[1:-1], ",")
        if len(parts) == 1:
            return parse_element(parts[0], ectx, depth + 1)
        entries = tuple(parse_element(p, ectx, depth + 1) for p in parts)
        if any(e is _ELLIPSIS for e in entries):
            raise _error("'...' can only stand for elements of a set, not entries of a tuple.")
        return entries
    if t in ectx.atoms:
        return Atom(t)
    try:
        expr = MathContext.build().parse(t)
    except MathInputError as exc:
        if exc.code == "UNKNOWN_NAME":
            raise _error(f"ProofLab can't read '{t}' as an element. {ectx.describe()}") from exc
        raise
    if has_infinity(expr) or expr.free_symbols or not expr.is_real:
        raise _error(f"'{t}' isn't a real number. {ectx.describe()}")
    return canon_number(expr)


def _is_int(v: object) -> bool:
    return isinstance(v, sp.Integer)


def _expand_ellipses(items: list[object]) -> list[Value]:
    out: list[Value] = []
    for i, item in enumerate(items):
        if item is not _ELLIPSIS:
            out.append(item)
            continue
        nxt = items[i + 1] if i + 1 < len(items) else None
        if not out or nxt is None or nxt is _ELLIPSIS:
            raise _error(
                "This set goes on forever. ProofLab only checks finite sets, so list every "
                "element (a run like 1, 2, ..., 9 is fine).",
                "SET_INFINITE",
            )
        prev = out[-1]
        if not (_is_int(prev) and _is_int(nxt)):
            raise _error("'...' only works between whole numbers, like 1, 2, ..., 9.")
        if len(out) >= 2 and _is_int(out[-2]):
            step = int(prev) - int(out[-2])
        else:
            step = 1 if int(nxt) >= int(prev) else -1
        span = int(nxt) - int(prev)
        if step == 0 or span * step <= 0 or span % step:
            raise _error(f"ProofLab can't tell how '...' gets from {prev} to {nxt}.")
        _check_size(len(out) + span // step)
        out.extend(sp.Integer(k) for k in range(int(prev) + step, int(nxt), step))
    return out


# --------------------------------------------------------------------------- expressions


@dataclass(frozen=True)
class Node:
    op: str  # lit, name, union, inter, diff, prod, pow, comp, powerset
    args: tuple = ()
    value: object = None


_OP_SYMBOL = {"union": r"\cup", "inter": r"\cap", "diff": "-", "prod": r"\times"}


def node_latex(node: Node, top: bool = True) -> str:
    if node.op == "lit":
        return latex(node.value)
    if node.op == "name":
        name = str(node.value)
        m = re.fullmatch(r"([A-Z])_?([0-9]+)", name)
        return f"{m.group(1)}_{{{m.group(2)}}}" if m else name
    if node.op in _OP_SYMBOL:
        body = f" {_OP_SYMBOL[node.op]} ".join(node_latex(a, False) for a in node.args)
        return body if top else rf"\left({body}\right)"
    if node.op == "pow":
        return f"{node_latex(node.args[0], False)}^{{{node.value}}}"
    if node.op == "comp":
        return rf"\overline{{{node_latex(node.args[0])}}}"
    if node.op == "powerset":
        return rf"\mathscr{{P}}\left({node_latex(node.args[0])}\right)"
    raise ValueError(node.op)


_WORD_OPS = {
    "cup": "∪",
    "union": "∪",
    "u": "∪",
    "cap": "∩",
    "intersect": "∩",
    "n": "∩",
    "minus": "−",
    "setminus": "−",
    "times": "×",
    "x": "×",
}
_POWER_SET_WORDS = {"P", "pow", "powerset"}
_COMP_WORDS = {"comp", "complement", "overline", "bar"}
_SYMBOL_OPS = {"∪": "union", "∩": "inter", "−": "diff", "-": "diff", "\\": "diff", "×": "prod"}


class _Tokens:
    """Scanner for the set-expression level. Braces are read whole, as literals."""

    def __init__(self, src: str) -> None:
        self.toks: list[tuple[str, str]] = []
        i = 0
        while i < len(src):
            ch = src[i]
            if ch.isspace():
                i += 1
            elif ch == "{":
                end = _matching(src, i)
                if end < 0:
                    raise _error("A '{' is never closed.")
                self.toks.append(("lit", src[i : end + 1]))
                i = end + 1
            elif ch == "∅":
                self.toks.append(("lit", "∅"))
                i += 1
            elif ch in "()'^*":
                self.toks.append(("punct", "×" if ch == "*" else ch))
                i += 1
            elif ch in _SYMBOL_OPS:
                self.toks.append(("op", ch if ch not in "-\\" else "−"))
                i += 1
            elif ch.isalpha():
                m = re.match(r"[A-Za-z]+(?:_?[0-9]+)?", src[i:])
                if not m:
                    raise _error(f"ProofLab couldn't read '{src[i:]}'.")
                word = m.group()
                i += len(word)
                if word in _WORD_OPS:
                    self.toks.append(("op", _WORD_OPS[word]))
                elif word in ("emptyset", "varnothing"):
                    self.toks.append(("lit", "∅"))
                else:
                    self.toks.append(("word", word))
            elif ch.isdigit():
                m = re.match(r"[0-9]+", src[i:])
                assert m
                self.toks.append(("int", m.group()))
                i += len(m.group())
            elif ch == "}":
                raise _error("There's a '}' without a matching '{'.")
            else:
                raise _error(f"ProofLab doesn't know the symbol '{ch}' here.")
        self.pos = 0

    def peek(self) -> tuple[str, str] | None:
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def take(self) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise _error("This ends too early.")
        self.pos += 1
        return tok

    def at(self, kind: str, val: str | None = None) -> bool:
        tok = self.peek()
        return tok is not None and tok[0] == kind and (val is None or tok[1] == val)


def parse_expression(raw: str, ectx: ElementContext) -> Node:
    """Parse a set expression into a :class:`Node` tree (no evaluation yet)."""
    if len(raw) > MAX_INPUT_CHARS:
        raise _error("That input is too long for ProofLab to check.", "TOO_LONG")
    src = normalize_sets(raw)
    if not src:
        raise _error("This is empty.", "EMPTY")
    toks = _Tokens(src)
    node = _Parser(toks, ectx).expr(0)
    if toks.peek() is not None:
        raise _error(f"ProofLab couldn't read the part starting at '{toks.peek()[1]}'.")
    return node


class _Parser:
    def __init__(self, toks: _Tokens, ectx: ElementContext) -> None:
        self.toks = toks
        self.ectx = ectx

    def expr(self, depth: int) -> Node:
        if depth > MAX_DEPTH:
            raise _error("That expression is nested too deeply for ProofLab.", "TOO_LONG")
        first = self.operand(depth)
        args = [first]
        op: str | None = None
        while self.toks.at("op") and self.toks.peek()[1] != "×":
            this = _SYMBOL_OPS[self.toks.take()[1]]
            if op is not None and this != op:
                raise _error(
                    "Add parentheses: ProofLab won't guess how ∪, ∩ and − group when they're "
                    "mixed, as in A ∪ B ∩ C.",
                    "SET_MIXED_OPERATORS",
                )
            op = this
            args.append(self.operand(depth))
        if op is None:
            return first
        if op == "diff":  # left to right: A − B − C = (A − B) − C
            node = args[0]
            for arg in args[1:]:
                node = Node("diff", (node, arg))
            return node
        return Node(op, tuple(args))

    def operand(self, depth: int) -> Node:
        factors = [self.factor(depth)]
        while self.toks.at("op", "×") or self.toks.at("punct", "×"):
            self.toks.take()
            factors.append(self.factor(depth))
        return factors[0] if len(factors) == 1 else Node("prod", tuple(factors))

    def factor(self, depth: int) -> Node:
        node = self.primary(depth)
        while True:
            if self.toks.at("punct", "'"):
                self.toks.take()
                node = Node("comp", (node,))
            elif self.toks.at("punct", "^"):
                self.toks.take()
                if self.toks.at("word", "c") or self.toks.at("word", "C"):
                    self.toks.take()
                    node = Node("comp", (node,))
                elif self.toks.at("punct", "("):
                    self.toks.take()
                    n = self.toks.take()
                    if n[0] != "int" or not self.toks.at("punct", ")"):
                        raise _error("A Cartesian power needs a whole number, like A^2.")
                    self.toks.take()
                    node = self._power(node, n[1])
                elif self.toks.at("int"):
                    node = self._power(node, self.toks.take()[1])
                else:
                    raise _error("After '^' write a whole number (A^2) or c (A^c, complement).")
            else:
                return node

    @staticmethod
    def _power(node: Node, digits: str) -> Node:
        n = int(digits)
        if not 1 <= n <= 8:
            raise _error("ProofLab handles Cartesian powers from A^1 to A^8.", "SET_TOO_LARGE")
        return Node("pow", (node,), n)

    def primary(self, depth: int) -> Node:
        tok = self.toks.take()
        kind, val = tok
        if kind == "lit":
            return Node("lit", value=parse_literal(val, self.ectx))
        if kind == "punct" and val == "(":
            inner = self.expr(depth + 1)
            if not self.toks.at("punct", ")"):
                raise _error("A '(' is never closed.")
            self.toks.take()
            return inner
        if kind == "word":
            if (val in _POWER_SET_WORDS or val in _COMP_WORDS) and self.toks.at("punct", "("):
                self.toks.take()
                inner = self.expr(depth + 1)
                if not self.toks.at("punct", ")"):
                    raise _error("A '(' is never closed.")
                self.toks.take()
                return Node("powerset" if val in _POWER_SET_WORDS else "comp", (inner,))
            if _NAME_RE.fullmatch(val):
                return Node("name", value=val.replace("_", ""))
            raise _error(f"ProofLab doesn't know '{val}' here.")
        raise _error(f"ProofLab didn't expect '{val}' here.")


def evaluate(
    node: Node, env: Mapping[str, frozenset], universe: frozenset | None = None
) -> frozenset:
    """Evaluate a set expression with named sets from ``env``."""
    op = node.op
    if op == "lit":
        return node.value  # type: ignore[return-value]
    if op == "name":
        name = str(node.value)
        if name not in env:
            known = ", ".join(sorted(env)) or "no named sets"
            raise _error(
                f"There's no set called {name} in this problem (it has {known}).",
                "SET_UNKNOWN_NAME",
            )
        return env[name]
    args = [evaluate(a, env, universe) for a in node.args]
    if op == "union":
        out = frozenset().union(*args)
        _check_size(len(out))
        return out
    if op == "inter":
        return frozenset.intersection(*args)
    if op == "diff":
        return args[0] - args[1]
    if op == "prod":
        return product(args)
    if op == "pow":
        return product([args[0]] * int(node.value))  # type: ignore[call-overload]
    if op == "comp":
        if universe is None:
            raise _error(
                "This problem has no universal set, so complements aren't defined.",
                "SET_NO_UNIVERSE",
            )
        return universe - args[0]
    if op == "powerset":
        return power_set(args[0])
    raise ValueError(op)


# --------------------------------------------------------------------------- set-builder (data)


class Builder(BaseModel):
    """Set-builder notation in problem data: ``{element : var ∈ domain, where...}``.

    Numeric domains (``Z``, ``N`` = {1, 2, 3, ...}, ``R``) solve the conditions with SymPy; ``in``
    takes a finite set expression and filters it with ``|X| <= 1`` / ``a ∈ X`` / ``a ∉ X``.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    var: str
    domain: Literal["Z", "N", "R"] | None = None
    in_: str | None = Field(default=None, alias="in")
    element: str | None = None
    where: list[str] = Field(default_factory=list)


_CARD_RE = re.compile(r"^\|\s*([A-Za-z])\s*\|\s*(<=|>=|!=|<|>|=)\s*([0-9]+)$")
_MEMBER_RE = re.compile(r"^(.+?)\s*(∈|∉|\bnotin\b|\bin\b)\s*([A-Za-z])$")
_CMP = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}
_REL = {"<": sp.Lt, "<=": sp.Le, ">": sp.Gt, ">=": sp.Ge, "=": sp.Eq, "!=": sp.Ne}


def build_set(
    b: Builder,
    env: Mapping[str, frozenset],
    ectx: ElementContext,
    universe: frozenset | None = None,
    *,
    naturals_from: int = 1,
) -> frozenset:
    """Evaluate a builder from problem data. ``naturals_from=0`` is the "ℕ includes 0" variant."""
    if (b.domain is None) == (b.in_ is None):
        raise ValueError("a builder needs exactly one of 'domain' and 'in'")
    if b.in_ is not None:
        candidates = evaluate(parse_expression(b.in_, ectx), env, universe)
        return frozenset(
            v for v in candidates if all(_set_condition(c, b.var, v, ectx) for c in b.where)
        )
    ctx = MathContext.build({b.var: "real"})
    var = ctx[b.var]
    solutions: sp.Set = sp.S.Reals
    for cond in b.where:
        parts, ops = split_relation(normalize(cond))
        if not ops:
            raise ValueError(f"condition {cond!r} has no relation")
        exprs = [ctx.parse(p) for p in parts]
        for left, op, right in zip(exprs, ops, exprs[1:], strict=False):
            solutions = sp.Intersection(solutions, _REL[op](left, right).as_set())
    if b.domain == "R":
        if not isinstance(solutions, sp.FiniteSet) and solutions != sp.S.EmptySet:
            raise ValueError(f"builder over R is not finite: {solutions}")
        values = list(solutions)
    else:
        lo = naturals_from if b.domain == "N" else None
        if solutions == sp.S.EmptySet:
            values = []
        else:
            inf, sup = solutions.inf, solutions.sup
            low = int(sp.ceiling(inf)) if inf.is_finite else lo
            if low is None or not sup.is_finite:
                raise ValueError(f"builder over {b.domain} is not bounded: {solutions}")
            if lo is not None:
                low = max(low, lo)
            values = [
                sp.Integer(k)
                for k in range(low, int(sp.floor(sup)) + 1)
                if bool(solutions.contains(sp.Integer(k)))
            ]
            _check_size(len(values))
    if b.element is not None:
        elem = ctx.parse(b.element)
        values = [elem.subs(var, v) for v in values]
    return frozenset(canon_number(sp.sympify(v)) for v in values)


def _set_condition(cond: str, var: str, value: Value, ectx: ElementContext) -> bool:
    c = normalize_sets(cond)
    m = _CARD_RE.fullmatch(c)
    if m and m.group(1) == var:
        if not isinstance(value, frozenset):
            raise ValueError(f"|{var}| needs {var} to be a set")
        return _CMP[m.group(2)](len(value), int(m.group(3)))
    m = _MEMBER_RE.fullmatch(c)
    if m and m.group(3) == var:
        if not isinstance(value, frozenset):
            raise ValueError(f"membership in {var} needs {var} to be a set")
        inside = parse_element(m.group(1), ectx) in value
        return inside if m.group(2) in ("∈", "in") else not inside
    raise ValueError(f"unsupported set condition {cond!r}")


# --------------------------------------------------------------------------- comparisons


def flatten_tuples(v: Value) -> Value:
    """((1, 2), 3) → (1, 2, 3), recursively inside sets too."""
    if isinstance(v, frozenset):
        return frozenset(flatten_tuples(x) for x in v)
    if isinstance(v, tuple):
        out: list[Value] = []
        for x in v:
            fx = flatten_tuples(x)
            out.extend(fx if isinstance(fx, tuple) else (fx,))
        return tuple(out)
    return v


def tuple_lengths(s: frozenset) -> set[int]:
    return {len(x) if isinstance(x, tuple) else 0 for x in s}


def count_leaves(v: Value) -> int:
    """Number of non-set things anywhere inside ``v`` (for "counted the inside" mistakes)."""
    if isinstance(v, frozenset):
        return sum(count_leaves(x) for x in v)
    return 1


def count_members_deep(v: Value) -> int:
    """Every element at every level of nesting."""
    if isinstance(v, frozenset):
        return sum(1 + count_members_deep(x) for x in v)
    return 0
