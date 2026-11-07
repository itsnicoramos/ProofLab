"""Multiple integrals (SPEC §5.5): ``iterated_integral`` and ``integral_setup``.

Student integrals are evaluated numerically with a fixed Gauss–Legendre rule on a cosine-mapped
interval (which smooths the square-root endpoints of circular regions), never with symbolic
``integrate`` on student input. Regions are compared by *moments*: two descriptions describe the
same region exactly when ∫∫ h dA agrees for a family of test functions h.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from functools import lru_cache
from typing import Literal

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field, field_validator

from prooflab.engine import hints
from prooflab.engine.algebra import (
    MathContext,
    MathInputError,
    equivalent,
    real_value,
    strip_label,
    to_latex,
)
from prooflab.engine.checker import ContentError, TopicHandler, VerdictBuilder, register
from prooflab.engine.models import Problem, StepStatus, Submission, VerdictStatus

hints.register_many(
    {
        "ITERATED_STEP_WRONG": "This doesn't match the integral after integrating the inner "
        "variable(s). Check the antiderivative and the limits you plugged in.",
        "ANSWER_HAS_INTEGRAL": "Evaluate the integral all the way to a number.",
        "SETUP_NOT_ITERATED": "Write the setup as one iterated integral with two integral signs "
        "and nothing outside, like int(int(f, y, a, b), x, c, d).",
        "WRONG_COORDINATES": "Use {coordinates} coordinates: integrate with respect to "
        "{variables}.",
        "INTEGRATION_ORDER": "This problem asks you to integrate with respect to {inner} first "
        "(inside), then {outer} (outside).",
        "SETUP_BOUNDS": "The inner limits may depend only on the outer variable, and the outer "
        "limits must be numbers.",
        "REGION_MISMATCH": "These limits describe a different region from the original. Sketch "
        "the region and read the new limits off the sketch.",
        "REVERSED_LIMITS_ONLY": "Reversing the order isn't just swapping dx and dy: the limits "
        "have to describe the same region from the other direction. Sketch it first.",
        "LIMITS_BACKWARDS": "Your limits run backwards (lower limit above the upper one), which "
        "flips the sign of the integral.",
        "MISSING_JACOBIAN": "In polar coordinates dA = r dr dθ. Don't forget the extra factor r.",
        "INTEGRAND_NOT_CONVERTED": "Rewrite the integrand in polar coordinates: x = r cos θ, "
        "y = r sin θ.",
        "INTEGRAND_CHANGED": "Changing the order of integration doesn't change the integrand.",
        "SETUP_VALUE_STEP": "This doesn't have the same value as the original integral.",
    }
)

Limit = tuple[sp.Symbol, sp.Expr, sp.Expr]


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- quadrature


def _gauss_legendre(n: int) -> list[tuple[float, float]]:
    """Nodes and weights on [0, 1]."""
    out = []
    for i in range(1, n + 1):
        x = math.cos(math.pi * (i - 0.25) / (n + 0.5))
        for _ in range(100):
            p0, p1 = 1.0, x
            for k in range(2, n + 1):
                p0, p1 = p1, ((2 * k - 1) * x * p1 - (k - 1) * p0) / k
            dp = n * (x * p1 - p0) / (x * x - 1)
            dx = p1 / dp
            x -= dx
            if abs(dx) < 1e-16:
                break
        out.append(((1 - x) / 2, 1 / ((1 - x * x) * dp * dp)))
    return out


_NODES = [(t, w, math.cos(math.pi * t), math.sin(math.pi * t)) for t, w in _gauss_legendre(48)]


def _expr(value: object) -> sp.Expr:
    if isinstance(value, sp.Basic):
        return value  # type: ignore[return-value]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"not a number or expression: {value!r}")
    return sp.Integer(value) if isinstance(value, int) else sp.Float(value)


def iterated_quad(integrand: sp.Expr, limits: Sequence[Limit]) -> float | None:
    """∫…∫ integrand over nested ``limits`` (innermost first); ``None`` if it can't be done."""
    integrand = _expr(integrand)
    limits = [(var, _expr(lo), _expr(hi)) for var, lo, hi in limits]
    syms = list(dict.fromkeys(var for var, _, _ in limits))
    extra = integrand.free_symbols | {
        s for _, lo, hi in limits for s in (lo.free_symbols | hi.free_symbols)
    }
    if not extra <= set(syms):
        return None
    try:
        f = sp.lambdify(syms, integrand, modules="math")
        bounds = [
            (
                syms.index(var),
                sp.lambdify(syms, lo, modules="math"),
                sp.lambdify(syms, hi, modules="math"),
            )
            for var, lo, hi in limits
        ]
    except Exception:  # noqa: BLE001
        return None
    values = [0.0] * len(syms)

    def level(k: int) -> float:
        idx, lo, hi = bounds[k]
        a, b = float(lo(*values)), float(hi(*values))
        half = (b - a) / 2
        total = 0.0
        for _, w, c, s in _NODES:
            values[idx] = a + half * (1 - c)
            inner = level(k - 1) if k > 0 else float(f(*values))
            total += w * half * math.pi * s * inner
        return total

    try:
        result = level(len(bounds) - 1)
    except (ValueError, ZeroDivisionError, OverflowError, TypeError):
        return None
    return result if math.isfinite(result) else None


def closed_value(expr: sp.Expr) -> float | None:
    """Numeric value of a closed expression that may contain definite integrals."""
    if isinstance(expr, sp.Integral):
        if expr.function.has(sp.Integral) or any(len(lim) != 3 for lim in expr.limits):
            return None
        return iterated_quad(expr.function, [(lim[0], lim[1], lim[2]) for lim in expr.limits])
    if not expr.has(sp.Integral):
        return real_value(expr)
    args = []
    for arg in expr.args:
        if arg.has(sp.Integral):
            v = closed_value(arg)
            if v is None:
                return None
            args.append(sp.Float(v, 17))
        else:
            args.append(arg)
    return real_value(expr.func(*args))


def _close(a: float, b: float, tol: float = 1e-7) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def _parse_limits(ctx: MathContext, bounds: Sequence[Sequence[str]]) -> list[Limit]:
    limits = []
    for var, lo, hi in bounds:
        limits.append((ctx[var], ctx.parse(lo), ctx.parse(hi)))
    return limits


def bounds_problem(limits: Sequence[Limit]) -> bool:
    """True when some limit depends on its own variable or on a variable further in."""
    for k, (_, lo, hi) in enumerate(limits):
        allowed = {var for var, _, _ in limits[k + 1 :]}
        if not (_expr(lo).free_symbols | _expr(hi).free_symbols) <= allowed:
            return True
    return False


def _bounds_field(value: list[list[str]]) -> list[list[str]]:
    for b in value:
        if len(b) != 3:
            raise ValueError("each bound is [variable, lower, upper]")
    return value


# --------------------------------------------------------------------------- iterated


class IteratedParams(_Params):
    integrand: str
    bounds: list[list[str]] = Field(min_length=1, max_length=3)
    variables: dict[str, str] | None = None

    _check_bounds = field_validator("bounds")(_bounds_field)


@lru_cache(maxsize=256)
def _stages(integrand: str, bounds: tuple[tuple[str, str, str], ...], variables: tuple) -> tuple:
    ctx = _iterated_ctx(bounds, dict(variables) if variables else None)
    cur = ctx.parse(integrand)
    out = [cur]
    for var, lo, hi in _parse_limits(ctx, bounds):
        if cur is None:
            out.append(None)
            continue
        try:
            nxt = sp.integrate(cur, (var, lo, hi))
        except Exception:  # noqa: BLE001
            nxt = None
        cur = None if nxt is None or nxt.has(sp.Integral) else sp.simplify(nxt)
        out.append(cur)
    return tuple(out)


def _iterated_ctx(bounds, variables: dict[str, str] | None) -> MathContext:
    names = [b[0] for b in bounds]
    spec: dict[str, str] = {n: "real" for n in names}
    spec.update(variables or {})
    return MathContext.build(spec, allow_integral=True)


@register
class IteratedIntegralHandler(TopicHandler):
    kind = "iterated_integral"
    Params = IteratedParams
    syntax_help = (
        "Enter the exact value of the integral, e.g. 3/8 or pi/4. Steps can be the result after "
        "the inner integral (an expression in the outer variable), an int(...) you rewrote, or "
        "numbers."
    )

    def setup(self, problem: Problem, p: IteratedParams):
        ctx = _iterated_ctx(p.bounds, p.variables)
        f = ctx.parse(p.integrand)
        limits = _parse_limits(ctx, p.bounds)
        if bounds_problem(limits):
            raise ValueError("inner limits may only depend on outer variables")
        key = ctx.parse(strip_label(problem.answer))
        if key.free_symbols or key.has(sp.Integral):
            raise ValueError("the answer key must be a number")
        stages = _stages(
            p.integrand,
            tuple(tuple(b) for b in p.bounds),
            tuple(sorted((p.variables or {}).items())),
        )
        return ctx, f, limits, key, stages

    def validate(self, problem: Problem, params: IteratedParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError, ValueError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def verify_key(self, problem: Problem, params: IteratedParams) -> bool | None:
        ctx, f, limits, key, stages = self.setup(problem, params)
        exact = stages[-1]
        if exact is not None:
            return equivalent(exact, key, ctx)
        numeric, target = iterated_quad(f, limits), real_value(key)
        if numeric is None or target is None:
            return None
        return _close(numeric, target, 1e-8)

    def _stage_message(self, k: int, limits: Sequence[Limit]) -> str:
        if k == 0:
            return "That's the integrand."
        done = ", then ".join(str(var) for var, _, _ in limits[:k])
        return f"That's the result after integrating with respect to {done}."

    def check(
        self, problem: Problem, params: IteratedParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, f, limits, key, stages = self.setup(problem, params)
        target = real_value(key)
        current = 0
        for i, step in enumerate(submission.steps):
            expr = self.parse_step(vb, i, step, lambda t: ctx.parse(strip_label(t)))
            if expr is None:
                continue
            latex = to_latex(expr)
            if not expr.free_symbols:
                value = closed_value(expr)
                if value is None or target is None:
                    vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
                elif _close(value, target):
                    vb.ok(i, step.kind, "That's the value of the integral.", latex=latex)
                else:
                    vb.error(i, step.kind, "ITERATED_STEP_WRONG", latex=latex)
                    if not expr.has(sp.Integral) and vb.first_error == i:
                        self.diagnose_expression(vb, problem, ctx, expr, key, step=i)
                continue
            matched = None
            undecided = False
            for k in range(current, len(stages) - 1):
                if stages[k] is None:
                    undecided = True
                    continue
                same = equivalent(expr, stages[k], ctx)
                if same:
                    matched = k
                    break
                undecided = undecided or same is None
            if matched is not None:
                vb.ok(i, step.kind, self._stage_message(matched, limits), latex=latex)
                current = matched
            elif undecided:
                vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
            else:
                vb.error(i, step.kind, "ITERATED_STEP_WRONG", latex=latex)
                if vb.first_error == i:
                    like = [
                        s
                        for s in stages[current:-1]
                        if s is not None and s.free_symbols == expr.free_symbols
                    ]
                    if like:
                        self.diagnose_expression(vb, problem, ctx, expr, like[0], step=i)

        text = submission.answer
        if text is None or not text.strip():
            return
        try:
            student = ctx.parse(strip_label(text))
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        if student.has(sp.Integral):
            vb.answer(VerdictStatus.INCORRECT, latex=to_latex(student), code="ANSWER_HAS_INTEGRAL")
            vb.hint("ANSWER_HAS_INTEGRAL")
            return
        self.grade_expression(vb, problem, ctx, text, key, require_exact=True)


# --------------------------------------------------------------------------- setup

_TEST_FUNCTIONS = (
    "1",
    "x",
    "y",
    "x^2",
    "x y",
    "y^2",
    "x^3",
    "x^2 y",
    "x y^2",
    "y^3",
    "e^(x/2 - y/3)",
    "sin(x/2 + y)",
)


class SetupParams(_Params):
    integrand: str
    region: list[list[str]] = Field(min_length=2, max_length=2)
    order: list[str] = Field(min_length=2, max_length=2)
    coordinates: Literal["cartesian", "polar"] = "cartesian"

    _check_region = field_validator("region")(_bounds_field)


def _setup_ctx(coordinates: str) -> MathContext:
    spec: dict[str, str] = {"x": "real", "y": "real"}
    if coordinates == "polar":
        spec.update({"r": "positive", "theta": "real[0, 6.28]"})
    return MathContext.build(spec, allow_integral=True)


def parse_setup(text: str, ctx: MathContext) -> tuple[sp.Expr, list[Limit]] | None:
    """``int(int(f, y, a, b), x, c, d)`` → ``(f, [(y, a, b), (x, c, d)])``.

    ``None`` if the input isn't a single iterated definite integral.
    """
    expr = ctx.parse(strip_label(text))
    if not isinstance(expr, sp.Integral) or expr.function.has(sp.Integral):
        return None
    if any(len(lim) != 3 for lim in expr.limits):
        return None
    return expr.function, [(lim[0], lim[1], lim[2]) for lim in expr.limits]


@lru_cache(maxsize=256)
def _region_moments(region: tuple[tuple[str, str, str], ...]) -> tuple[float | None, ...]:
    ctx = _setup_ctx("cartesian")
    limits = _parse_limits(ctx, region)
    return tuple(iterated_quad(ctx.parse(h), limits) for h in _TEST_FUNCTIONS)


def _student_moments(ctx: MathContext, limits: Sequence[Limit], polar: bool) -> list[float | None]:
    out = []
    for h in _TEST_FUNCTIONS:
        g = ctx.parse(h)
        if polar:
            r, t = ctx["r"], ctx["theta"]
            g = g.subs({ctx["x"]: r * sp.cos(t), ctx["y"]: r * sp.sin(t)}, simultaneous=True) * r
        out.append(iterated_quad(g, limits))
    return out


def _compare_moments(student: Sequence[float | None], original: Sequence[float | None]) -> str:
    """``"same"``, ``"negated"``, ``"different"`` or ``"unknown"``."""
    if any(v is None for v in student) or any(v is None for v in original):
        return "unknown"
    if all(_close(a, b) for a, b in zip(student, original, strict=True)):  # type: ignore[arg-type]
        return "same"
    if all(_close(a, -b) for a, b in zip(student, original, strict=True)):  # type: ignore[operator]
        return "negated"
    return "different"


@register
class IntegralSetupHandler(TopicHandler):
    kind = "integral_setup"
    Params = SetupParams
    step_kinds = frozenset({"expr", "note"})
    syntax_help = (
        "Enter the iterated integral without evaluating it, inner integral first: "
        "int(int(f, y, a, b), x, c, d) means ∫ from c to d ∫ from a to b f dy dx. In polar, "
        "use r and theta. 'note' steps are free text and aren't checked."
    )

    def setup(self, problem: Problem, p: SetupParams):
        ctx = _setup_ctx(p.coordinates)
        if {b[0] for b in p.region} != {"x", "y"}:
            raise ValueError("'region' must be iterated bounds in x and y")
        f = ctx.parse(p.integrand)
        original = _parse_limits(ctx, p.region)
        if bounds_problem(original):
            raise ValueError("region: inner limits may only depend on the outer variable")
        polar = p.coordinates == "polar"
        if polar:
            if set(p.order) != {"r", "theta"}:
                raise ValueError("polar setups integrate in r and theta")
            r, t = ctx["r"], ctx["theta"]
            expected = f.subs({ctx["x"]: r * sp.cos(t), ctx["y"]: r * sp.sin(t)}, simultaneous=True)
            jacobian = r
        else:
            if set(p.order) != {"x", "y"}:
                raise ValueError("cartesian setups integrate in x and y")
            expected, jacobian = f, sp.Integer(1)
        order = [ctx[v] for v in p.order]
        key = parse_setup(problem.answer, ctx)
        if key is None:
            raise ValueError("answer key must be an iterated integral")
        region_key = tuple(tuple(b) for b in p.region)
        return ctx, f, original, polar, expected, jacobian, order, key, region_key

    def validate(self, problem: Problem, params: SetupParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError, ValueError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def evaluate(
        self, s, integrand: sp.Expr, limits: list[Limit], params: SetupParams
    ) -> list[tuple[str, dict]]:
        """Problems with a setup, as ``(code, params)``; empty means correct."""
        ctx, f, original, polar, expected, jacobian, order, _key, region_key = s
        found: list[tuple[str, dict]] = []
        variables = [var for var, _, _ in limits]
        if len(limits) != 2:
            return [("SETUP_NOT_ITERATED", {})]
        if set(variables) != set(order):
            names = " and ".join("θ" if str(v) == "theta" else str(v) for v in order)
            return [("WRONG_COORDINATES", {"coordinates": params.coordinates, "variables": names})]
        if variables != order:
            found.append(
                ("INTEGRATION_ORDER", {"inner": _name(order[0]), "outer": _name(order[1])})
            )
        if bounds_problem(limits):
            return [*found, ("SETUP_BOUNDS", {})]

        same_integrand = equivalent(integrand, expected * jacobian, ctx)
        if not same_integrand:
            if polar and integrand.has(ctx["x"], ctx["y"]):
                found.append(("INTEGRAND_NOT_CONVERTED", {}))
            elif polar and equivalent(integrand, expected, ctx):
                found.append(("MISSING_JACOBIAN", {}))
            elif polar:
                found.append(("INTEGRAND_NOT_CONVERTED", {}))
            else:
                found.append(("INTEGRAND_CHANGED", {}))

        region = _compare_moments(_student_moments(ctx, limits, polar), _region_moments(region_key))
        if region == "negated":
            found.append(("LIMITS_BACKWARDS", {}))
        elif region == "different":
            found.append(
                (
                    "REVERSED_LIMITS_ONLY"
                    if _naive_swap(ctx, limits, original)
                    else "REGION_MISMATCH",
                    {},
                )
            )
        elif region == "unknown":
            found.append(("UNVERIFIED", {}))
        return found

    def verify_key(self, problem: Problem, params: SetupParams) -> bool | None:
        s = self.setup(problem, params)
        integrand, limits = s[7]
        problems = self.evaluate(s, integrand, limits, params)
        if problems == [("UNVERIFIED", {})]:
            return None
        return not problems

    def check(
        self, problem: Problem, params: SetupParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        s = self.setup(problem, params)
        ctx, f, original = s[0], s[1], s[2]
        target = iterated_quad(f, original)
        for i, step in enumerate(submission.steps):
            if step.kind == "note":
                vb.step(i, step.kind, StepStatus.UNCHECKED, "Notes aren't checked.")
                continue
            expr = self.parse_step(vb, i, step, lambda t: ctx.parse(strip_label(t)))
            if expr is None:
                continue
            latex = to_latex(expr)
            value = closed_value(expr) if not expr.free_symbols else None
            if value is None or target is None:
                vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
            elif _close(value, target):
                vb.ok(i, step.kind, "Same value as the original integral.", latex=latex)
            else:
                vb.error(i, step.kind, "SETUP_VALUE_STEP", latex=latex)

        text = submission.answer
        if text is None or not text.strip():
            return
        try:
            parsed = parse_setup(text, ctx)
            shown = ctx.parse(strip_label(text))
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        latex = to_latex(shown)
        if parsed is None:
            vb.answer(VerdictStatus.INCORRECT, latex=latex, code="SETUP_NOT_ITERATED")
            vb.hint("SETUP_NOT_ITERATED")
            return
        integrand, limits = parsed
        found = self.evaluate(s, integrand, limits, params)
        if not found:
            vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
            return
        if found == [("UNVERIFIED", {})]:
            vb.answer(VerdictStatus.INVALID, latex=latex, code="UNVERIFIED")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")

        def same_setup(a, b) -> bool:
            return b is not None and _setups_equal(ctx, a, b, s[3])

        mistake = self.match_mistake(problem, parsed, lambda t: parse_setup(t, ctx), same_setup)
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
            return
        for code, extra in found:
            if code != "UNVERIFIED":
                vb.hint(code, **extra)


def _naive_swap(ctx: MathContext, limits: Sequence[Limit], original: Sequence[Limit]) -> bool:
    """Did the student keep the original limits (as written, or with x and y renamed)?"""
    x, y = ctx["x"], ctx["y"]
    swap = {x: y, y: x}
    for rename in (False, True):
        ok = True
        for (_, lo, hi), (_, olo, ohi) in zip(limits, original, strict=True):
            if rename:
                olo, ohi = olo.subs(swap, simultaneous=True), ohi.subs(swap, simultaneous=True)
            if not (equivalent(lo, olo, ctx) and equivalent(hi, ohi, ctx)):
                ok = False
                break
        if ok:
            return True
    return False


def _name(sym: sp.Symbol) -> str:
    return "θ" if str(sym) == "theta" else str(sym)


def _setups_equal(ctx: MathContext, a, b, polar: bool) -> bool:
    (fa, la), (fb, lb) = a, b
    if [v for v, _, _ in la] != [v for v, _, _ in lb]:
        return False
    if not equivalent(fa, fb, ctx):
        return False
    return (
        _compare_moments(_student_moments(ctx, la, polar), _student_moments(ctx, lb, polar))
        == "same"
    )
