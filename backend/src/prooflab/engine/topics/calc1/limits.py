"""Limits (SPEC §5.3): the ``limit`` kind.

Steps are algebraic rewrites of the previous step (``expr``) or L'Hôpital steps
(``lhopital``). A constant step is read as "the limit equals this value".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import sympy as sp
from pydantic import BaseModel, ConfigDict

from prooflab.engine import hints
from prooflab.engine.algebra import (
    MathContext,
    MathInputError,
    contains_float,
    equivalent,
    normalize,
    strip_label,
    to_latex,
    values_equal,
)
from prooflab.engine.checker import ContentError, TopicHandler, VerdictBuilder, register
from prooflab.engine.models import Problem, StepStatus, Submission, VerdictStatus

hints.register_many(
    {
        "LHOPITAL_NOT_INDETERMINATE": "L'Hôpital's rule only applies to 0/0 or ∞/∞ forms. "
        "This expression isn't one, so evaluate it directly.",
        "LHOPITAL_NOT_A_QUOTIENT": "L'Hôpital's rule needs a quotient f/g. Rewrite the expression "
        "as a fraction first.",
        "LHOPITAL_WRONG_DERIVATIVE": "For L'Hôpital's rule, differentiate the numerator and the "
        "denominator separately: f′/g′.",
        "LHOPITAL_QUOTIENT_RULE": "L'Hôpital's rule is f′/g′, not the derivative of f/g "
        "(no quotient rule here).",
        "LIMIT_PRESERVED_ONLY": "This has the same limit, but it isn't an algebraic rewrite of the "
        "previous step. Justify it (for example with the squeeze theorem) or rewrite it.",
        "LIMIT_STEP_WRONG": "This step changes the limit, so it can't follow from the previous "
        "one.",
        "LIMIT_VALUE_WRONG": "That isn't the value of the limit.",
        "INDETERMINATE_IS_NOT_DNE": "The function may be undefined at the point, but the limit can "
        "still exist. Simplify (factor, rationalize, or use an identity) and try again.",
        "INDETERMINATE_FORM": "0/0 is an indeterminate form, not a value. It means more work is "
        "needed: simplify the expression first.",
        "ONE_SIDED_ONLY": "That's the limit from one side only. Check the other side: if the two "
        "one-sided limits differ, the limit does not exist.",
        "INFINITE_LIMIT": "The function grows without bound here. Say how: write oo or -oo.",
        "LIMIT_SIGN": "Check the sign: does the expression head to +∞ or to −∞?",
    }
)

DNE = "DNE"
_DNE_WORDS = {"dne", "does not exist", "doesn't exist", "doesnt exist", "no limit"}
_UNDEFINED_WORDS = {"undefined", "undef"}
_INDETERMINATE_RE = re.compile(r"^\s*0\s*/\s*0\s*$")


class LimitParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expression: str
    var: str = "x"
    point: str
    direction: Literal["both", "+", "-"] = "both"
    variables: dict[str, str] | None = None


LimitValue = sp.Expr | str  # a SymPy value (possibly ±oo) or DNE


@dataclass
class _Setup:
    ctx: MathContext
    x: sp.Symbol
    f: sp.Expr
    a: sp.Expr
    direction: str
    key: LimitValue


def parse_limit_value(text: str, ctx: MathContext) -> LimitValue:
    t = text.strip().lower().rstrip(".")
    if t in _DNE_WORDS or t in _UNDEFINED_WORDS:
        return DNE
    if _INDETERMINATE_RE.match(text):
        raise MathInputError(hints.message("INDETERMINATE_FORM"), "INDETERMINATE_FORM")
    value = ctx.parse(strip_label(text))
    if value.free_symbols:
        raise MathInputError(
            "A limit is a number (or oo, -oo, DNE), so it can't contain variables."
        )
    return value


def compute_limit(f: sp.Expr, x: sp.Symbol, a: sp.Expr, direction: str) -> LimitValue | None:
    """The limit, ``DNE``, or ``None`` if SymPy can't decide."""
    try:
        if a in (sp.oo, -sp.oo) or direction != "both":
            value = sp.limit(f, x, a, dir=direction if direction != "both" else "+")
        else:
            value = sp.limit(f, x, a, dir="+-")
    except ValueError:
        return DNE
    except Exception:  # noqa: BLE001
        return None
    if isinstance(value, sp.AccumBounds) or value is sp.nan:
        return DNE
    if value is sp.zoo:
        return DNE
    if isinstance(value, sp.Limit):
        return None
    return value


def one_sided(f: sp.Expr, x: sp.Symbol, a: sp.Expr) -> tuple[LimitValue | None, LimitValue | None]:
    if a in (sp.oo, -sp.oo):
        return (None, None)
    return compute_limit(f, x, a, "-"), compute_limit(f, x, a, "+")


def limit_values_equal(u: LimitValue | None, v: LimitValue | None) -> bool:
    if u is None or v is None:
        return False
    if isinstance(u, str) or isinstance(v, str):
        return u == v
    if u.is_infinite or v.is_infinite:
        return bool(u == v)
    return values_equal(u, v)


def split_fraction(text: str, ctx: MathContext, expr: sp.Expr) -> tuple[sp.Expr, sp.Expr] | None:
    """The numerator and denominator as the student *wrote* them.

    SymPy would silently rewrite ``ln x / (1/x)`` as ``x ln x``, hiding the quotient.
    """
    s = normalize(strip_label(text))
    depth, cut = 0, -1
    for i, ch in enumerate(s):
        if ch in "([{":
            depth += 1
        if ch in ")]}":
            depth -= 1
        if ch == "/" and depth == 0:
            cut = i
    if cut > 0:
        try:
            num, den = ctx.parse(s[:cut]), ctx.parse(s[cut + 1 :])
            if equivalent(num / den, expr, ctx):
                return num, den
        except MathInputError:
            pass
    num, den = sp.fraction(sp.together(expr))
    if den == 1:
        return None
    return num, den


@register
class LimitHandler(TopicHandler):
    kind = "limit"
    Params = LimitParams
    step_kinds = frozenset({"expr", "lhopital"})
    syntax_help = (
        "Enter the limit's value: a number, oo, -oo, or DNE. Each step is either an algebraic "
        "rewrite of the previous step ('expr') or a L'Hôpital step f'/g' ('lhopital'). "
        "A step that's just a number means 'the limit equals this'."
    )

    def setup(self, problem: Problem, p: LimitParams) -> _Setup:
        ctx = MathContext.build(p.variables or {p.var: "real"})
        return _Setup(
            ctx=ctx,
            x=ctx[p.var],
            f=ctx.parse(p.expression),
            a=ctx.parse(p.point),
            direction=p.direction,
            key=parse_limit_value(problem.answer, ctx),
        )

    def validate(self, problem: Problem, params: LimitParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def verify_key(self, problem: Problem, params: LimitParams) -> bool | None:
        s = self.setup(problem, params)
        actual = compute_limit(s.f, s.x, s.a, s.direction)
        if actual is None:
            return None
        return limit_values_equal(actual, s.key)

    # -- steps
    def _check_steps(
        self, s: _Setup, params: LimitParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        prev_expr, prev_text = s.f, params.expression
        for i, step in enumerate(submission.steps):
            expr = self.parse_step(vb, i, step, lambda t: s.ctx.parse(strip_label(t)))
            if expr is None:
                prev_expr = None
                continue
            latex = to_latex(expr)
            if prev_expr is None:
                vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
            elif step.kind == "lhopital":
                self._check_lhopital(i, step.kind, s, prev_expr, prev_text, expr, latex, vb)
            elif not expr.has(s.x):
                if limit_values_equal(expr, s.key) and s.key != DNE:
                    vb.ok(i, step.kind, "That's the value of the limit.", latex=latex)
                else:
                    vb.error(i, step.kind, "LIMIT_VALUE_WRONG", latex=latex)
            else:
                same = equivalent(expr, prev_expr, s.ctx)
                if same:
                    vb.ok(i, step.kind, latex=latex)
                else:
                    before = compute_limit(prev_expr, s.x, s.a, s.direction)
                    after = compute_limit(expr, s.x, s.a, s.direction)
                    if before is not None and limit_values_equal(before, after):
                        vb.step(
                            i,
                            step.kind,
                            StepStatus.WARNING,
                            latex=latex,
                            code="LIMIT_PRESERVED_ONLY",
                        )
                    elif same is None or before is None or after is None:
                        vb.step(
                            i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP"
                        )
                    else:
                        vb.error(i, step.kind, "LIMIT_STEP_WRONG", latex=latex)
            prev_expr, prev_text = expr, step.content

    def _check_lhopital(
        self, i, kind, s: _Setup, prev, prev_text, expr, latex, vb: VerdictBuilder
    ) -> None:
        frac = split_fraction(prev_text, s.ctx, prev)
        if frac is None:
            vb.error(i, kind, "LHOPITAL_NOT_A_QUOTIENT", latex=latex)
            return
        num, den = frac
        ln = compute_limit(num, s.x, s.a, s.direction)
        ld = compute_limit(den, s.x, s.a, s.direction)
        zero_zero = ln == 0 and ld == 0
        inf_inf = (
            not isinstance(ln, str)
            and not isinstance(ld, str)
            and ln is not None
            and ld is not None
            and ln.is_infinite
            and ld.is_infinite
        )
        if ln is None or ld is None:
            vb.step(i, kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
            return
        if not (zero_zero or inf_inf):
            vb.error(i, kind, "LHOPITAL_NOT_INDETERMINATE", latex=latex)
            return
        target = sp.diff(num, s.x) / sp.diff(den, s.x)
        if equivalent(expr, target, s.ctx):
            form = "0/0" if zero_zero else "∞/∞"
            vb.ok(i, kind, f"Valid L'Hôpital step ({form} form).", latex=latex)
        elif equivalent(expr, sp.diff(num / den, s.x), s.ctx):
            vb.error(i, kind, "LHOPITAL_QUOTIENT_RULE", latex=latex)
        else:
            vb.error(i, kind, "LHOPITAL_WRONG_DERIVATIVE", latex=latex)

    # -- answer
    def check(
        self, problem: Problem, params: LimitParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        s = self.setup(problem, params)
        self._check_steps(s, params, submission, vb)
        text = submission.answer
        if text is None or not text.strip():
            return
        try:
            student = parse_limit_value(text, s.ctx)
        except MathInputError as exc:
            if exc.code == "INDETERMINATE_FORM":
                vb.answer(VerdictStatus.INCORRECT, exc.message, code="INDETERMINATE_FORM")
                vb.hint("INDETERMINATE_FORM")
            else:
                vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        latex = r"\text{DNE}" if student == DNE else to_latex(student)
        key = s.key

        if limit_values_equal(student, key):
            if not isinstance(student, str) and contains_float(student) and not contains_float(key):
                vb.answer(VerdictStatus.PARTIAL, latex=latex, code="INEXACT")
                vb.hint("INEXACT")
            else:
                vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
            return
        if not isinstance(student, str) and contains_float(student) and not isinstance(key, str):
            if not key.is_infinite and values_equal(student, key, tol=1e-3):
                vb.answer(VerdictStatus.PARTIAL, latex=latex, code="INEXACT")
                vb.hint("INEXACT")
                return

        key_infinite = not isinstance(key, str) and key.is_infinite
        if student == DNE and key_infinite:
            vb.answer(VerdictStatus.PARTIAL, latex=latex, code="INFINITE_LIMIT")
            vb.hint("INFINITE_LIMIT")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
        mistake = self.match_mistake(
            problem, student, lambda t: parse_limit_value(t, s.ctx), limit_values_equal
        )
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
        elif student == DNE:
            vb.hint("INDETERMINATE_IS_NOT_DNE")
        elif key == DNE:
            left, right = one_sided(s.f, s.x, s.a)
            if limit_values_equal(student, left) or limit_values_equal(student, right):
                vb.hint("ONE_SIDED_ONLY")
        elif key_infinite and not isinstance(student, str) and student.is_infinite:
            vb.hint("LIMIT_SIGN")
        elif not isinstance(student, str) and not student.is_infinite and not key_infinite:
            self.diagnose_expression(vb, problem, s.ctx, student, key)
