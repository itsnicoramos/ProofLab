"""Functions (SPEC §5.2): ``expression``, ``inverse_function``, ``domain``.

``expression`` is the general "enter an equivalent expression" kind (compositions, difference
quotients, simplification, factoring, exact values) and can be used from any topic.
"""

from __future__ import annotations

import re
from typing import Literal

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field

from prooflab.engine import hints
from prooflab.engine.algebra import (
    MathContext,
    MathInputError,
    VarSpec,
    equivalent,
    has_infinity,
    normalize,
    parse_real_set,
    set_difference_is_finite,
    set_latex,
    sets_equal,
    split_relation,
    strip_label,
    to_latex,
)
from prooflab.engine.checker import (
    ContentError,
    Detector,
    TopicHandler,
    VerdictBuilder,
    register,
)
from prooflab.engine.models import Problem, StepStatus, Submission, VerdictStatus

hints.register_many(
    {
        "FORM_NOT_EXPANDED": "Your expression is equivalent, but not fully expanded. Multiply "
        "out every product and power of sums.",
        "FORM_NOT_FACTORED": "Your expression is equivalent, but not completely factored. Check "
        "whether any factor can be factored further.",
        "FORM_NOT_SINGLE_FRACTION": "Your expression is equivalent, but it should be a single "
        "fraction. Combine the terms over a common denominator.",
        "FORM_NOT_LOWEST_TERMS": "Your expression is equivalent, but not in lowest terms. Cancel "
        "the factors the numerator and denominator have in common.",
        "FORM_NOT_CANCELLED": "Your expression is equivalent, but you still need to cancel {var} "
        "so the expression is defined when {var} = 0.",
        "FORM_NOT_EVALUATED": "Evaluate it: the answer shouldn't contain {names}.",
        "RECIPROCAL_NOT_INVERSE": "The inverse function f⁻¹ undoes f; it isn't the reciprocal "
        "1/f. Swap x and y in y = f(x), then solve for y.",
        "INVERSE_NOT_SWAPPED": "That's f itself. To find the inverse, swap x and y in y = f(x), "
        "then solve for y.",
        "INVERSE_BRANCH": "f(g(x)) and g(f(x)) don't both simplify to x on the given domain. "
        "Check signs and which square-root branch you need.",
        "INVERSE_STEP_WRONG": "This equation doesn't describe f or its inverse.",
        "ENDPOINTS": "Close: your set differs from the domain only at single points. Check which "
        "endpoints are included and which points must be left out.",
        "DOMAIN_TOO_LARGE": "Your set includes x-values where f is undefined. Look for zero "
        "denominators, negatives under even roots, and logs of non-positive numbers.",
        "DOMAIN_TOO_SMALL": "Your set leaves out x-values where f is defined.",
        "DOMAIN_CONDITION_WRONG": "This condition rules out x-values where f is defined.",
    }
)


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- forms

Form = Literal["any", "expanded", "factored", "single_fraction", "lowest_terms", "exact", "cancel"]


def is_expanded(expr: sp.Expr) -> bool:
    return sp.expand(expr) == expr


def is_factored(expr: sp.Expr) -> bool:
    """Every non-constant factor is irreducible over ℚ (and appears as factor**n)."""
    for arg in sp.Mul.make_args(expr):
        base = arg.base if arg.is_Pow and arg.exp.is_Integer and arg.exp > 0 else arg
        if not base.free_symbols:
            continue
        try:
            _, factors = sp.factor_list(base)
        except Exception:  # noqa: BLE001
            return False
        if len(factors) != 1 or factors[0][1] != 1:
            return False
    return True


def is_single_fraction(expr: sp.Expr) -> bool:
    if not expr.is_Add:
        return True
    return not any(sp.fraction(term)[1].free_symbols for term in expr.args)


def is_lowest_terms(expr: sp.Expr) -> bool:
    if not is_single_fraction(expr):
        return False
    num, den = sp.fraction(sp.together(expr))
    try:
        return not sp.gcd(num, den).free_symbols
    except Exception:  # noqa: BLE001
        return False


def is_cancelled(expr: sp.Expr, var: sp.Symbol) -> bool:
    try:
        return not has_infinity(expr.subs(var, 0))
    except Exception:  # noqa: BLE001
        return False


def forbidden_names(text: str, names: list[str]) -> list[str]:
    t = normalize(text).lower()
    return [n for n in names if re.search(re.escape(n.lower()), t)]


# --------------------------------------------------------------------------- expression


class ExpressionParams(_Params):
    variables: dict[str, str] = Field(default_factory=lambda: {"x": "real"})
    var: str = "x"
    expression: str | None = None
    compose: list[str] | None = Field(default=None, min_length=2, max_length=2)
    difference_quotient: str | None = None
    cancel_var: str = "h"
    form: Form = "any"
    forbid: list[str] = Field(default_factory=list)


@register
class ExpressionHandler(TopicHandler):
    kind = "expression"
    Params = ExpressionParams
    syntax_help = (
        "Enter an expression, e.g. 4x^2 + 4x + 4 or -sqrt(3)/2. Each step should be equal to "
        "the answer (successive rewrites)."
    )

    def setup(self, problem: Problem, p: ExpressionParams):
        ctx = MathContext.build(p.variables)
        return ctx, ctx.parse(strip_label(problem.answer))

    def target(self, ctx: MathContext, p: ExpressionParams) -> sp.Expr | None:
        """The value the answer must equal, computed from the data (independent of the key)."""
        given = [p.expression, p.compose, p.difference_quotient]
        if sum(g is not None for g in given) > 1:
            raise ContentError("give at most one of expression / compose / difference_quotient")
        if p.expression is not None:
            return ctx.parse(p.expression)
        x = ctx[p.var] if (p.compose or p.difference_quotient) else None
        if p.compose is not None:
            outer, inner = (ctx.parse(t) for t in p.compose)
            return outer.subs(x, inner)
        if p.difference_quotient is not None:
            f = ctx.parse(p.difference_quotient)
            h = ctx[p.cancel_var]
            return (f.subs(x, x + h) - f) / h
        return None

    def validate(self, problem: Problem, params: ExpressionParams) -> None:
        try:
            ctx, key = self.setup(problem, params)
            self.target(ctx, params)
            if params.form == "cancel":
                ctx[params.cancel_var]
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc
        if not self.form_ok(key, params, ctx):
            raise ContentError(f"{problem.id}: the answer key isn't in the required form")

    def form_ok(self, expr: sp.Expr, p: ExpressionParams, ctx: MathContext) -> bool:
        checks = {
            "any": lambda e: True,
            "exact": lambda e: True,
            "expanded": is_expanded,
            "factored": is_factored,
            "single_fraction": is_single_fraction,
            "lowest_terms": is_lowest_terms,
            "cancel": lambda e: is_cancelled(e, ctx[p.cancel_var]),
        }
        return checks[p.form](expr)

    def verify_key(self, problem: Problem, params: ExpressionParams) -> bool | None:
        ctx, key = self.setup(problem, params)
        target = self.target(ctx, params)
        if target is None:
            return None
        return equivalent(target, key, ctx)

    def check(
        self, problem: Problem, params: ExpressionParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, key = self.setup(problem, params)
        self.check_steps_against(vb, submission.steps, ctx, key, problem=problem)
        student = self.grade_expression(
            vb, problem, ctx, submission.answer, key, require_exact=params.form == "exact"
        )
        answer = vb.answer_result
        if student is None or answer is None or answer.status is not VerdictStatus.CORRECT:
            return
        assert submission.answer is not None
        banned = forbidden_names(submission.answer, params.forbid)
        if banned:
            vb.answer(VerdictStatus.PARTIAL, latex=answer.latex, code="FORM_NOT_EVALUATED")
            vb.hint("FORM_NOT_EVALUATED", names=", ".join(banned))
            return
        if not self.form_ok(student, params, ctx):
            code = {
                "expanded": "FORM_NOT_EXPANDED",
                "factored": "FORM_NOT_FACTORED",
                "single_fraction": "FORM_NOT_SINGLE_FRACTION",
                "lowest_terms": "FORM_NOT_LOWEST_TERMS",
                "cancel": "FORM_NOT_CANCELLED",
            }[params.form]
            vb.answer(VerdictStatus.PARTIAL, latex=answer.latex, code=code, var=params.cancel_var)
            vb.hint(code, var=params.cancel_var)


# --------------------------------------------------------------------------- inverse


class InverseParams(_Params):
    function: str
    var: str = "x"
    domain: str = "real"
    range: str = "real"


@register
class InverseFunctionHandler(TopicHandler):
    kind = "inverse_function"
    Params = InverseParams
    syntax_help = (
        "Enter f⁻¹(x) as an expression in x. Steps can be equations in x and y "
        "(y = f(x), then swap x and y and solve for y)."
    )

    def setup(self, problem: Problem, p: InverseParams):
        for spec in (p.domain, p.range):
            if VarSpec.coerce(spec).domain != "real":
                raise ContentError(f"{problem.id}: domain/range must be 'real' or 'real[a, b]'")
        on_f = MathContext.build({p.var: p.domain, "y": "real"})
        on_g = MathContext.build({p.var: p.range, "y": "real"})
        answers = MathContext.build({p.var: p.range})
        f = on_f.parse(p.function)
        key = answers.parse(strip_label(problem.answer))
        return on_f, on_g, answers, on_f[p.var], f, key

    def validate(self, problem: Problem, params: InverseParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    @staticmethod
    def inverts(g: sp.Expr, f: sp.Expr, x: sp.Symbol, on_f: MathContext, on_g: MathContext):
        fg = equivalent(f.subs(x, g), x, on_g)
        gf = equivalent(g.subs(x, f), x, on_f)
        return fg, gf

    def verify_key(self, problem: Problem, params: InverseParams) -> bool | None:
        on_f, on_g, _, x, f, key = self.setup(problem, params)
        y = on_f["y"]
        try:
            candidates = sp.solve(sp.Eq(x, f.subs(x, y)), y)
        except Exception:  # noqa: BLE001
            candidates = []
        solved = any(equivalent(c.subs(y, x), key, on_g) for c in candidates)
        fg, gf = self.inverts(key, f, x, on_f, on_g)
        return bool(fg and gf and (solved or not candidates))

    def _check_step(self, vb: VerdictBuilder, i: int, step, on_f, on_g, x, f, key) -> None:
        y = on_f["y"]
        parts, ops = split_relation(normalize(step.content))
        try:
            lhs = None
            if ops == ["="]:
                try:
                    lhs = on_f.parse(parts[0])
                except MathInputError:
                    lhs = None  # a label such as f^-1(x) = ...
            if lhs is not None:
                rhs = on_f.parse(parts[1])
                latex = f"{to_latex(lhs)} = {to_latex(rhs)}"
                try:
                    sols = sp.solve(sp.Eq(lhs, rhs), y)
                except Exception:  # noqa: BLE001
                    sols = None
                if not sols:
                    vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
                    return
            else:
                expr = on_f.parse(parts[-1] if ops == ["="] else step.content)
                latex, sols = to_latex(expr), [expr]
        except MathInputError as exc:
            vb.step(i, step.kind, StepStatus.ERROR, exc.message, code=exc.code)
            return
        if any(equivalent(s, key, on_g) for s in sols):
            vb.ok(i, step.kind, "This describes the inverse.", latex=latex)
        elif any(equivalent(s, f, on_f) for s in sols):
            vb.ok(i, step.kind, "This is y = f(x).", latex=latex)
        else:
            vb.error(i, step.kind, "INVERSE_STEP_WRONG", latex=latex)

    def check(
        self, problem: Problem, params: InverseParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        on_f, on_g, answers, x, f, key = self.setup(problem, params)
        for i, step in enumerate(submission.steps):
            self._check_step(vb, i, step, on_f, on_g, x, f, key)

        def same(g: sp.Expr, _key: sp.Expr) -> bool | None:
            fg, gf = self.inverts(g, f, x, on_f, on_g)
            if fg and gf:
                return True
            if fg is None or gf is None:
                return None
            return False

        def detect(code: str, wrong: sp.Expr) -> Detector:
            return lambda s: (code, {}) if equivalent(s, wrong, on_g) else None

        detectors = [detect("RECIPROCAL_NOT_INVERSE", 1 / f), detect("INVERSE_NOT_SWAPPED", f)]

        def branch(s: sp.Expr) -> tuple[str, dict[str, object]] | None:
            fg, gf = self.inverts(s, f, x, on_f, on_g)
            return ("INVERSE_BRANCH", {}) if bool(fg) != bool(gf) else None

        detectors.append(branch)
        self.grade_expression(
            vb, problem, answers, submission.answer, key, equal=same, detectors=detectors
        )


# --------------------------------------------------------------------------- domain


class DomainParams(_Params):
    function: str
    var: str = "x"


@register
class DomainHandler(TopicHandler):
    kind = "domain"
    Params = DomainParams
    syntax_help = (
        "Enter the domain in interval notation, e.g. [2, 5) U (5, oo), or as inequalities, "
        "e.g. x >= 2 and x != 5. Steps can be conditions such as x - 2 >= 0."
    )

    def setup(self, problem: Problem, p: DomainParams):
        ctx = MathContext.build({p.var: "real"})
        x = ctx[p.var]
        return ctx, x, ctx.parse(p.function), parse_real_set(problem.answer, ctx, x)

    def validate(self, problem: Problem, params: DomainParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def verify_key(self, problem: Problem, params: DomainParams) -> bool | None:
        _, x, f, key = self.setup(problem, params)
        try:
            actual = sp.calculus.util.continuous_domain(f, x, sp.S.Reals)
        except Exception:  # noqa: BLE001
            return None
        return sets_equal(actual, key)

    def check(
        self, problem: Problem, params: DomainParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, x, f, key = self.setup(problem, params)
        for i, step in enumerate(submission.steps):
            cond = self.parse_step(vb, i, step, lambda t: parse_real_set(t, ctx, x))
            if cond is None:
                continue
            latex = set_latex(cond)
            if sp.Complement(key, cond) == sp.S.EmptySet:
                vb.ok(i, step.kind, latex=latex)
            else:
                vb.error(i, step.kind, "DOMAIN_CONDITION_WRONG", latex=latex)

        text = submission.answer
        if text is None or not text.strip():
            return
        try:
            student = parse_real_set(text, ctx, x)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        latex = set_latex(student)
        if sets_equal(student, key):
            vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
        mistake = self.match_mistake(
            problem, student, lambda t: parse_real_set(t, ctx, x), sets_equal
        )
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
        elif set_difference_is_finite(student, key):
            vb.hint("ENDPOINTS")
        elif sp.Complement(key, student) == sp.S.EmptySet:
            vb.hint("DOMAIN_TOO_LARGE")
        elif sp.Complement(student, key) == sp.S.EmptySet:
            vb.hint("DOMAIN_TOO_SMALL")
