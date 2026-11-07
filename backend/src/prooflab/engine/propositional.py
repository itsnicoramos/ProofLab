"""Propositional logic (SPEC §5.1, Book of Proof Chapter 2): a safe formula parser and evaluator.

Formulas are built from statement letters (``P``, ``Q``, ...), the constants ``T``/``F``, and::

    ~  ¬  not            negation
    ∧  &  ^  and  /\\     and
    ∨  |  v  or   \\/     or
    ⇒  →  =>  ->  implies
    ⇔  ↔  <=> <-> iff

``~`` binds tightest (``~P ∨ Q`` is ``(~P) ∨ Q``, as in the book), then ∧/∨, then ⇒, then ⇔.
Mixing ∧ and ∨, or chaining ⇒ or ⇔, needs parentheses. A hand-written tokenizer and
recursive-descent parser build :class:`Formula` trees; student input never reaches ``eval``.

Truth tables list rows in the book's order: the first variable is T in the top half and F in
the bottom half, and the last variable alternates T, F, T, F.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from prooflab.engine.algebra import MAX_INPUT_CHARS, MathInputError

MAX_VARIABLES = 6  # 64 rows
MAX_DEPTH = 40
MAX_TOKENS = 200

Row = tuple[bool, ...]


@dataclass(frozen=True)
class Formula:
    op: str  # var, const, not, and, or, implies, iff
    args: tuple[Formula, ...] = ()
    name: str = ""  # variable name, or "T"/"F" for constants

    # -- evaluation
    def value(self, env: Mapping[str, bool]) -> bool:
        op = self.op
        if op == "var":
            return env[self.name]
        if op == "const":
            return self.name == "T"
        if op == "not":
            return not self.args[0].value(env)
        vals = [a.value(env) for a in self.args]
        if op == "and":
            return all(vals)
        if op == "or":
            return any(vals)
        if op == "implies":
            return (not vals[0]) or vals[1]
        if op == "iff":
            return vals[0] == vals[1]
        raise ValueError(op)

    def variables(self) -> set[str]:
        if self.op == "var":
            return {self.name}
        out: set[str] = set()
        for a in self.args:
            out |= a.variables()
        return out


def _error(detail: str, code: str = "LOGIC_SYNTAX") -> MathInputError:
    return MathInputError(detail, code)


# --------------------------------------------------------------------------- tokenizer

_REPLACEMENTS = (
    ("\\Leftrightarrow", "⇔"),
    ("\\leftrightarrow", "⇔"),
    ("\\iff", "⇔"),
    ("\\Rightarrow", "⇒"),
    ("\\rightarrow", "⇒"),
    ("\\implies", "⇒"),
    ("\\to", "⇒"),
    ("\\wedge", "∧"),
    ("\\land", "∧"),
    ("\\vee", "∨"),
    ("\\lor", "∨"),
    ("\\neg", "~"),
    ("\\lnot", "~"),
    ("\\sim", "~"),
    ("\\left", ""),
    ("\\right", ""),
    ("<=>", "⇔"),
    ("<->", "⇔"),
    ("↔", "⇔"),
    ("⟺", "⇔"),
    ("=>", "⇒"),
    ("->", "⇒"),
    ("→", "⇒"),
    ("⟹", "⇒"),
    ("/\\", "∧"),
    ("\\/", "∨"),
    ("&&", "∧"),
    ("||", "∨"),
    ("&", "∧"),
    ("|", "∨"),
    ("^", "∧"),
    ("¬", "~"),
    ("!", "~"),
    ("∼", "~"),
    ("˜", "~"),
)
_WORDS = {
    "not": "~",
    "and": "∧",
    "or": "∨",
    "v": "∨",
    "implies": "⇒",
    "iff": "⇔",
    "true": "T",
    "false": "F",
}


def normalize_logic(text: str) -> str:
    s = text
    for old, new in _REPLACEMENTS:
        s = s.replace(old, new)
    return s.strip()


@dataclass(frozen=True)
class LogicContext:
    """The statement letters a problem uses."""

    variables: tuple[str, ...]

    @classmethod
    def build(cls, names: Iterable[str]) -> LogicContext:
        out = tuple(names)
        if len(out) > MAX_VARIABLES:
            raise ValueError(f"at most {MAX_VARIABLES} statement letters")
        for n in out:
            if not re.fullmatch(r"[A-Z]", n):
                raise ValueError(f"statement letters are single capitals, not {n!r}")
        if len(set(out)) != len(out):
            raise ValueError("duplicate statement letters")
        return cls(out)

    def describe(self) -> str:
        return ", ".join(self.variables)

    @property
    def rows(self) -> list[Row]:
        return rows(len(self.variables))

    def parse(self, text: str) -> Formula:
        return parse_formula(text, self)


def rows(n: int) -> list[Row]:
    """All assignments in the book's order (T before F, first variable slowest)."""
    return list(itertools.product((True, False), repeat=n))


def _tokenize(src: str, ctx: LogicContext) -> list[tuple[str, str]]:
    toks: list[tuple[str, str]] = []
    i = 0
    while i < len(src):
        ch = src[i]
        if ch.isspace():
            i += 1
        elif ch in "~∧∨⇒⇔()[]":
            toks.append(("op", {"[": "(", "]": ")"}.get(ch, ch)))
            i += 1
        elif ch.isalpha():
            m = re.match(r"[A-Za-z]+", src[i:])
            assert m
            word = m.group()
            i += len(word)
            low = word.lower()
            if word in ctx.variables:
                toks.append(("var", word))
            elif low in _WORDS and not (len(word) == 1 and word.isupper()):
                mapped = _WORDS[low]
                toks.append(("const" if mapped in "TF" else "op", mapped))
            elif word in ("T", "F"):
                toks.append(("const", word))
            elif len(word) > 1 and all(c in ctx.variables for c in word):
                raise _error(
                    f"Put a connective between the letters in '{word}' (for example P ∧ Q)."
                )
            else:
                raise _error(
                    f"'{word}' isn't a statement letter here. This problem uses {ctx.describe()}."
                )
        else:
            raise _error(f"ProofLab doesn't know the symbol '{ch}' in a logical statement.")
        if len(toks) > MAX_TOKENS:
            raise _error("That statement is too long for ProofLab to check.", "TOO_LONG")
    return toks


def parse_formula(text: str, ctx: LogicContext) -> Formula:
    if len(text) > MAX_INPUT_CHARS:
        raise _error("That statement is too long for ProofLab to check.", "TOO_LONG")
    src = normalize_logic(text)
    if not src:
        raise _error("This is empty.", "EMPTY")
    parser = _Parser(_tokenize(src, ctx))
    formula = parser.iff(0)
    if parser.pos != len(parser.toks):
        raise _error(f"ProofLab couldn't read the part starting at '{parser.toks[parser.pos][1]}'.")
    return formula


class _Parser:
    def __init__(self, toks: list[tuple[str, str]]) -> None:
        self.toks = toks
        self.pos = 0

    def peek(self) -> tuple[str, str] | None:
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def at(self, val: str) -> bool:
        tok = self.peek()
        return tok is not None and tok[0] == "op" and tok[1] == val

    def iff(self, depth: int) -> Formula:
        left = self.implies(depth)
        if self.at("⇔"):
            self.pos += 1
            right = self.implies(depth)
            if self.at("⇔"):
                raise _error("Add parentheses: P ⇔ Q ⇔ R is ambiguous.", "LOGIC_AMBIGUOUS")
            return Formula("iff", (left, right))
        return left

    def implies(self, depth: int) -> Formula:
        left = self.junction(depth)
        if self.at("⇒"):
            self.pos += 1
            right = self.junction(depth)
            if self.at("⇒"):
                raise _error(
                    "Add parentheses: P ⇒ Q ⇒ R could mean (P ⇒ Q) ⇒ R or P ⇒ (Q ⇒ R).",
                    "LOGIC_AMBIGUOUS",
                )
            return Formula("implies", (left, right))
        return left

    def junction(self, depth: int) -> Formula:
        args = [self.unary(depth)]
        op: str | None = None
        while self.at("∧") or self.at("∨"):
            this = "and" if self.peek()[1] == "∧" else "or"  # type: ignore[index]
            if op is not None and this != op:
                raise _error(
                    "Add parentheses: P ∨ Q ∧ R could mean (P ∨ Q) ∧ R or P ∨ (Q ∧ R).",
                    "LOGIC_AMBIGUOUS",
                )
            op = this
            self.pos += 1
            args.append(self.unary(depth))
        if op is None:
            return args[0]
        node = args[0]
        for arg in args[1:]:  # left-associative binary nodes
            node = Formula(op, (node, arg))
        return node

    def unary(self, depth: int) -> Formula:
        if depth > MAX_DEPTH:
            raise _error("That statement is nested too deeply for ProofLab.", "TOO_LONG")
        if self.at("~"):
            self.pos += 1
            return Formula("not", (self.unary(depth + 1),))
        tok = self.peek()
        if tok is None:
            raise _error("This statement ends too early.")
        self.pos += 1
        kind, val = tok
        if kind == "var":
            return Formula("var", name=val)
        if kind == "const":
            return Formula("const", name=val)
        if val == "(":
            inner = self.iff(depth + 1)
            if not self.at(")"):
                raise _error("A '(' is never closed.")
            self.pos += 1
            return inner
        raise _error(f"ProofLab didn't expect '{val}' here.")


# --------------------------------------------------------------------------- tables


def column(f: Formula, variables: Sequence[str], order: Sequence[Row] | None = None) -> list[bool]:
    table = order if order is not None else rows(len(variables))
    return [f.value(dict(zip(variables, row, strict=True))) for row in table]


def equivalent(a: Formula, b: Formula, variables: Sequence[str]) -> bool:
    return column(a, variables) == column(b, variables)


def first_difference(a: Formula, b: Formula, variables: Sequence[str]) -> dict[str, bool] | None:
    for row in rows(len(variables)):
        env = dict(zip(variables, row, strict=True))
        if a.value(env) != b.value(env):
            return env
    return None


def column_text(values: Sequence[bool]) -> str:
    return " ".join("T" if v else "F" for v in values)


_COLUMN_TOKEN_RE = re.compile(r"TRUE|FALSE|T|F|1|0")
_COLUMN_SEPARATORS_RE = re.compile(r"[\s,;|/]+")


def parse_column(text: str) -> list[bool]:
    """``T T F T`` / ``TTFT`` / ``1, 1, 0, 1`` → [True, True, False, True]."""
    s = text.strip().upper()
    if not s:
        raise _error("This column is empty.", "EMPTY")
    tokens = _COLUMN_TOKEN_RE.findall(s)
    leftover = _COLUMN_SEPARATORS_RE.sub("", _COLUMN_TOKEN_RE.sub("", s))
    if leftover or not tokens:
        raise _error("Write a column as T/F values, one per row, like T T F T.", "TT_BAD_COLUMN")
    return [t in ("T", "TRUE", "1") for t in tokens]


_ASSIGN_RE = re.compile(
    r"([A-Z])\s*(?:=|:|is|is\s+)?\s*(true|false|T|F|1|0)(?![A-Za-z])", re.IGNORECASE
)


def parse_assignment(text: str, variables: Sequence[str]) -> dict[str, bool]:
    """``P = T, Q = F`` / ``P is true and Q is false`` → {"P": True, "Q": False}."""
    s = text.strip()
    found: dict[str, bool] = {}
    for m in _ASSIGN_RE.finditer(s):
        name = m.group(1)
        if not name.isupper():
            continue
        if name not in variables:
            raise _error(
                f"'{name}' isn't a statement letter here. This problem uses "
                f"{', '.join(variables)}.",
                "LOGIC_BAD_ROW",
            )
        if name in found:
            raise _error(f"{name} is given a value twice.", "LOGIC_BAD_ROW")
        found[name] = m.group(2).upper() in ("T", "TRUE", "1")
    leftover = re.sub(r"(?i)\b(and)\b|[\s,;]+", "", _ASSIGN_RE.sub("", s))
    if leftover or not found:
        raise _error("Write truth values like P = T, Q = F (one for each letter).", "LOGIC_BAD_ROW")
    return found


def row_text(env: Mapping[str, bool], variables: Sequence[str]) -> str:
    return ", ".join(f"{v} = {'T' if env[v] else 'F'}" for v in variables if v in env)


# --------------------------------------------------------------------------- structure


def canonical(f: Formula) -> Formula:
    """Flatten chains of the same associative connective: (P ∧ Q) ∧ R ≡ P ∧ (Q ∧ R)."""
    if f.op in ("and", "or"):
        flat: list[Formula] = []
        for a in f.args:
            ca = canonical(a)
            flat.extend(ca.args if ca.op == f.op else (ca,))
        return Formula(f.op, tuple(flat))
    if f.args:
        return Formula(f.op, tuple(canonical(a) for a in f.args), f.name)
    return f


def same_statement(a: Formula, b: Formula) -> bool:
    return canonical(a) == canonical(b)


_LATEX_OP = {"and": r"\wedge", "or": r"\vee", "implies": r"\Rightarrow", "iff": r"\Leftrightarrow"}
_TEXT_OP = {"and": "∧", "or": "∨", "implies": "⇒", "iff": "⇔"}


def _render(f: Formula, ops: Mapping[str, str], neg: str, parent: str | None) -> str:
    if f.op == "var":
        return f.name
    if f.op == "const":
        return r"\mathrm{" + f.name + "}" if neg.startswith("\\") else f.name
    if f.op == "not":
        return neg + _render(f.args[0], ops, neg, "not")
    sep = f" {ops[f.op]} "
    body = sep.join(_render(a, ops, neg, f.op) for a in f.args)
    if parent is None or (parent == f.op and f.op in ("and", "or")):
        return body
    return f"({body})"


def to_latex(f: Formula) -> str:
    return _render(canonical(f), _LATEX_OP, r"\sim ", None)


def to_text(f: Formula) -> str:
    return _render(canonical(f), _TEXT_OP, "~", None)


# --------------------------------------------------------------------------- common mistakes


def _negate(f: Formula) -> Formula:
    return Formula("not", (f,))


def _local_mutations(f: Formula) -> list[tuple[str, Formula]]:
    out: list[tuple[str, Formula]] = []
    a = f.args
    if f.op == "implies":
        out += [
            ("IMPLIES_CONVERSE", Formula("implies", (a[1], a[0]))),
            ("IMPLIES_INVERSE", Formula("implies", (_negate(a[0]), _negate(a[1])))),
            ("IMPLIES_AS_OR", Formula("or", (a[0], a[1]))),
            ("IMPLIES_AS_AND", Formula("and", (a[0], a[1]))),
            ("IMPLIES_AS_IFF", Formula("iff", (a[0], a[1]))),
        ]
    elif f.op == "iff":
        out.append(("IFF_AS_IMPLIES", Formula("implies", (a[0], a[1]))))
    elif f.op in ("and", "or"):
        out.append(("AND_OR_SWAPPED", Formula("or" if f.op == "and" else "and", a)))
    elif f.op == "not":
        inner = a[0]
        out.append(("NEGATION_DROPPED", inner))
        if inner.op in ("and", "or"):
            x, y = inner.args
            out.append(("DEMORGAN_CONNECTIVE", Formula(inner.op, (_negate(x), _negate(y)))))
            out.append(("NEGATION_SCOPE", Formula(inner.op, (_negate(x), y))))
        elif inner.op in ("implies", "iff"):
            out.append(
                ("NEGATION_SCOPE", Formula(inner.op, (_negate(inner.args[0]), inner.args[1])))
            )
    return out


def mutations(f: Formula, limit: int = 400) -> list[tuple[str, Formula]]:
    """Formulas one typical mistake away from ``f``, labelled with a hint code."""
    out: list[tuple[str, Formula]] = list(_local_mutations(f))
    for i, child in enumerate(f.args):
        for code, mutated in mutations(child, limit):
            args = list(f.args)
            args[i] = mutated
            out.append((code, Formula(f.op, tuple(args), f.name)))
            if len(out) >= limit:
                return out
    return out


def diagnose_column(f: Formula, student: Sequence[bool], variables: Sequence[str]) -> str | None:
    """The hint code of a typical mistake that explains a wrong column, if any."""
    for code, mutated in mutations(f):
        if column(mutated, variables) == list(student):
            return code
    return None


def diagnose_rewrite(prev: Formula, step: Formula, variables: Sequence[str]) -> str | None:
    """The hint code of a typical mistake that turns ``prev`` into something like ``step``."""
    target = column(step, variables)
    for code, mutated in mutations(prev):
        if column(mutated, variables) == target:
            return code
    return None


def other_orders(variables: Sequence[str]) -> list[list[Row]]:
    """Row orders students commonly use instead of the book's (to spot order mix-ups)."""
    n = len(variables)
    f_first = list(itertools.product((False, True), repeat=n))
    reversed_vars = [tuple(reversed(r)) for r in rows(n)]
    reversed_f_first = [tuple(reversed(r)) for r in f_first]
    return [f_first, reversed_vars, reversed_f_first]
