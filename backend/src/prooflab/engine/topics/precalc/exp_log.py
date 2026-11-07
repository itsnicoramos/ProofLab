"""Exponentials and logarithms (SPEC §5.2): ``equation`` and ``log_rewrite``.

Also home of the shared *solve chain* used by ``trig_equation``: each step is an equation (or
``a = b or c = d``, or a list of values) and must keep every true solution of the original
equation. Losing one is an error; introducing extraneous ones is only a warning, because
combining logs or squaring is legitimate as long as the final answer is checked.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field

from prooflab.engine import hints
from prooflab.engine.algebra import (
    MathContext,
    MathInputError,
    contains_float,
    dedupe_values,
    equivalent,
    match_values,
    normalize,
    parse_equation,
    parse_real_set,
    parse_value_list,
    real_solutions,
    real_value,
    satisfies,
    split_relation,
    split_top,
    to_latex,
    values_equal,
)
from prooflab.engine.checker import (
    ContentError,
    TopicHandler,
    VerdictBuilder,
    register,
)
from prooflab.engine.models import Problem, Step, StepStatus, Submission, VerdictStatus

hints.register_many(
    {
        "LOST_SOLUTION": "This step loses a solution. Did you divide by something that could be "
        "zero, or keep only one square root?",
        "EXTRANEOUS_SOLUTION": "This step can introduce extraneous solutions (for example by "
        "combining logarithms or squaring both sides). Check your final answers in the original "
        "equation.",
        "MISSING_SOLUTIONS": "At least one solution is missing.",
        "EXTRA_SOLUTIONS": "At least one of your values doesn't satisfy the original equation. "
        "Plug each one back in (remember that logarithms need positive inputs).",
        "OUTSIDE_INTERVAL": "At least one of your values is outside the interval the problem asks "
        "about.",
        "SOLUTION_NOT_A_NUMBER": "Each solution should be a number, not an expression with "
        "variables.",
        "LOG_NOT_EXPANDED": "Your expression is equivalent, but not fully expanded: no logarithm "
        "should still contain a product, quotient or power.",
        "LOG_NOT_CONDENSED": "Your expression is equivalent, but it should be a single logarithm "
        "with no coefficient in front.",
    }
)


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- solve chain


def in_domain(value: sp.Expr, domain: sp.Set) -> bool:
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


def solve_in(lhs: sp.Expr, rhs: sp.Expr, var: sp.Symbol, domain: sp.Set) -> list[sp.Expr] | None:
    """Real solutions of ``lhs = rhs`` in ``domain`` (bounded intervals handled by algebra)."""
    return real_solutions(lhs, rhs, var, domain)


def _piece(
    text: str, ctx: MathContext, var: sp.Symbol, domain: sp.Set
) -> tuple[list[sp.Expr] | None, str]:
    parts, ops = split_relation(normalize(text))
    if ops == ["="]:
        lhs, rhs = ctx.parse(parts[0]), ctx.parse(parts[1])
        return solve_in(lhs, rhs, var, domain), f"{to_latex(lhs)} = {to_latex(rhs)}"
    if not ops:
        value = ctx.parse(text)
        if value.free_symbols:
            raise MathInputError(
                "Each step should be an equation, like 2x + 1 = 5, or a list of values.",
                "NOT_AN_EQUATION",
            )
        return ([value] if in_domain(value, domain) else []), to_latex(value)
    raise MathInputError("Each step should be an equation with one '='.", "NOT_AN_EQUATION")


def step_solutions(
    text: str, ctx: MathContext, var: sp.Symbol, domain: sp.Set
) -> tuple[list[sp.Expr] | None, str]:
    """Solutions of a step like ``(x-2)(x+1) = 0`` or ``x = 2 or x = -1``; ``None`` = unknown."""
    t = re.sub(r"\bor\b", ",", text)
    values: list[sp.Expr] = []
    latex: list[str] = []
    unknown = False
    for piece in split_top(t, ","):
        if not piece:
            continue
        vals, tex = _piece(piece, ctx, var, domain)
        latex.append(tex)
        if vals is None:
            unknown = True
        else:
            values.extend(vals)
    if not latex:
        raise MathInputError("This step is empty.", "EMPTY")
    return (None if unknown else dedupe_values(values)), r" \text{ or } ".join(latex)


def _contains(values: Sequence[sp.Expr], v: sp.Expr) -> bool:
    return any(values_equal(v, w) for w in values)


def check_solution_steps(
    vb: VerdictBuilder,
    steps: Sequence[Step],
    ctx: MathContext,
    var: sp.Symbol,
    domain: sp.Set,
    truth: Sequence[sp.Expr],
) -> None:
    prev: list[sp.Expr] = list(truth)
    for i, step in enumerate(steps):
        try:
            current, latex = step_solutions(step.content, ctx, var, domain)
        except MathInputError as exc:
            vb.step(i, step.kind, StepStatus.ERROR, exc.message, code=exc.code)
            continue
        if current is None:
            vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
            continue
        lost = [v for v in truth if _contains(prev, v) and not _contains(current, v)]
        new_extra = [v for v in current if not _contains(truth, v) and not _contains(prev, v)]
        if lost:
            vb.error(i, step.kind, "LOST_SOLUTION", latex=latex)
        elif new_extra:
            vb.step(i, step.kind, StepStatus.WARNING, latex=latex, code="EXTRANEOUS_SOLUTION")
        else:
            vb.ok(i, step.kind, latex=latex)
        prev = current


def values_latex(values: Sequence[sp.Expr]) -> str:
    if not values:
        return r"\varnothing"
    return r"\left\{" + ", ".join(to_latex(v) for v in values) + r"\right\}"


def same_values(a: Sequence[sp.Expr], b: Sequence[sp.Expr]) -> bool:
    missing, extra = match_values(a, b)
    return not missing and not extra


def grade_solutions(
    handler: TopicHandler,
    vb: VerdictBuilder,
    problem: Problem,
    ctx: MathContext,
    lhs: sp.Expr,
    rhs: sp.Expr,
    var: sp.Symbol,
    domain: sp.Set,
    truth: Sequence[sp.Expr],
    text: str | None,
    *,
    check_degrees: bool = False,
) -> None:
    """Grade a final solution list against the key and the original equation."""
    if text is None or not text.strip():
        return
    try:
        student = parse_value_list(text, ctx, var)
    except MathInputError as exc:
        vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
        return
    if any(v.free_symbols for v in student):
        vb.answer(VerdictStatus.INVALID, code="SOLUTION_NOT_A_NUMBER")
        return
    latex = values_latex(student)
    if same_values(student, truth):
        if any(contains_float(v) for v in student) and not any(contains_float(v) for v in truth):
            vb.answer(VerdictStatus.PARTIAL, latex=latex, code="INEXACT")
            vb.hint("INEXACT")
        else:
            vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
        return
    if any(contains_float(v) for v in student):
        missing, extra = match_values(student, truth, tol=1e-3)
        if not missing and not extra:
            vb.answer(VerdictStatus.PARTIAL, latex=latex, code="INEXACT")
            vb.hint("INEXACT")
            return

    vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
    mistake = handler.match_mistake(
        problem, student, lambda t: parse_value_list(t, ctx, var), same_values
    )
    if mistake is not None:
        vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
        return
    if check_degrees and student:
        as_radians = [v * sp.pi / 180 for v in student]
        if same_values(as_radians, truth) or all(
            satisfies(lhs, rhs, var, r) and in_domain(r, domain) for r in as_radians
        ):
            vb.hint("DEGREES_NOT_RADIANS")
            return
    missing, extra = match_values(student, truth)
    outside = [v for v in extra if satisfies(lhs, rhs, var, v) and not in_domain(v, domain)]
    if outside:
        vb.hint("OUTSIDE_INTERVAL")
    if len(outside) < len(extra):
        vb.hint("EXTRA_SOLUTIONS")
    if missing:
        vb.hint("MISSING_SOLUTIONS")


# --------------------------------------------------------------------------- equation


class EquationParams(_Params):
    equation: str
    var: str = "x"
    interval: str | None = None
    variables: dict[str, str] | None = None


class SolveHandler(TopicHandler):
    """Shared implementation for equation-solving kinds."""

    default_interval: str | None = None
    check_degrees = False

    def setup(self, problem: Problem, p: EquationParams):
        ctx = MathContext.build(p.variables or {p.var: "real"})
        var = ctx[p.var]
        lhs, rhs = parse_equation(p.equation, ctx)
        interval = p.interval or self.default_interval
        domain = parse_real_set(interval, ctx, var) if interval else sp.S.Reals
        truth = parse_value_list(problem.answer, ctx, var)
        return ctx, var, lhs, rhs, domain, truth

    def validate(self, problem: Problem, params: EquationParams) -> None:
        try:
            _, _, _, _, _, truth = self.setup(problem, params)
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc
        if any(v.free_symbols for v in truth):
            raise ContentError(f"{problem.id}: solutions must be numbers")

    def verify_key(self, problem: Problem, params: EquationParams) -> bool | None:
        ctx, var, lhs, rhs, domain, truth = self.setup(problem, params)
        if not all(satisfies(lhs, rhs, var, v) and in_domain(v, domain) for v in truth):
            return False
        solved = solve_in(lhs, rhs, var, domain)
        if solved is None:
            return None
        return same_values(solved, truth)

    def check(
        self, problem: Problem, params: EquationParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, var, lhs, rhs, domain, truth = self.setup(problem, params)
        check_solution_steps(vb, submission.steps, ctx, var, domain, truth)
        grade_solutions(
            self,
            vb,
            problem,
            ctx,
            lhs,
            rhs,
            var,
            domain,
            truth,
            submission.answer,
            check_degrees=self.check_degrees,
        )


@register
class EquationHandler(SolveHandler):
    kind = "equation"
    Params = EquationParams
    syntax_help = (
        "Enter all real solutions, like x = 2 or x = -3 (or {2, -3}, or 'no solution'). "
        "Each step is an equation, e.g. (x - 2)(x + 3) = 0 or x = 2 or x = -3."
    )


# --------------------------------------------------------------------------- log rewrite


class LogRewriteParams(_Params):
    expression: str
    form: Literal["expanded", "condensed"]
    variables: dict[str, str] = Field(
        default_factory=lambda: {"x": "positive", "y": "positive", "z": "positive"}
    )


def _logs(expr: sp.Expr) -> list[sp.Expr]:
    return [n for n in sp.preorder_traversal(expr) if isinstance(n, sp.log)]


def is_log_expanded(expr: sp.Expr) -> bool:
    """No log of a product, quotient or power of variables."""
    for node in _logs(expr):
        arg = node.args[0]
        if not arg.free_symbols:
            continue
        if arg.is_Mul or arg.is_Pow:
            return False
    return True


def is_log_condensed(expr: sp.Expr) -> bool:
    """A single logarithm (any base), with no coefficient in front."""
    logs = [n for n in _logs(expr) if n.args[0].free_symbols]
    if len(logs) != 1:
        return False
    coeff = sp.simplify(expr / logs[0])
    if coeff.free_symbols:
        return False
    if coeff == 1:
        return True
    inv = sp.simplify(1 / coeff)
    return isinstance(inv, sp.log) and not inv.args[0].free_symbols


@register
class LogRewriteHandler(TopicHandler):
    kind = "log_rewrite"
    Params = LogRewriteParams
    syntax_help = (
        "Enter the rewritten expression. ln is the natural log, log is base 10, log_2(x) is "
        "base 2. Each step should be equal to the original expression."
    )

    def setup(self, problem: Problem, p: LogRewriteParams):
        ctx = MathContext.build(p.variables)
        return ctx, ctx.parse(p.expression), ctx.parse(problem.answer)

    def form_ok(self, expr: sp.Expr, form: str) -> bool:
        return is_log_expanded(expr) if form == "expanded" else is_log_condensed(expr)

    def validate(self, problem: Problem, params: LogRewriteParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def verify_key(self, problem: Problem, params: LogRewriteParams) -> bool | None:
        ctx, expr, key = self.setup(problem, params)
        if not self.form_ok(key, params.form):
            return False
        same = equivalent(expr, key, ctx)
        if same is None:
            return None
        return bool(same) and sp.simplify(sp.expand_log(expr - key, force=True)) == 0

    def check(
        self, problem: Problem, params: LogRewriteParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, expr, key = self.setup(problem, params)
        self.check_steps_against(vb, submission.steps, ctx, expr, problem=problem)
        student = self.grade_expression(vb, problem, ctx, submission.answer, key)
        answer = vb.answer_result
        if student is None or answer is None or answer.status is not VerdictStatus.CORRECT:
            return
        if not self.form_ok(student, params.form):
            code = "LOG_NOT_EXPANDED" if params.form == "expanded" else "LOG_NOT_CONDENSED"
            vb.answer(VerdictStatus.PARTIAL, latex=answer.latex, code=code)
            vb.hint(code)
