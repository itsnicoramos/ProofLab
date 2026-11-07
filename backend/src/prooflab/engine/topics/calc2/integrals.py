"""Integrals (SPEC §5.4): ``antiderivative`` and ``definite_integral``.

Every antiderivative-style step is checked by *differentiating* it and comparing with the
integrand — no ``integrate()`` on student input. Unevaluated integrals ``int(g, v)`` inside a
step count as "some antiderivative of g": we replace each by a placeholder ``I``, differentiate
the rest, and add ``∂Φ/∂I · g · dv/dbase``.

One ``sub`` step per attempt defines a substitution:

- forward ``u = g(x)``: later steps may use ``u``; everything is compared in ``x`` after
  ``u → g(x)`` (so ``int(h(u), u)`` contributes ``h(g(x))·g′(x)``);
- inverse ``x = g(t)`` (trig substitution): everything is compared in ``t``; the integrand
  becomes ``f(g(t))·g′(t)``.

A ``sub`` step may also be a differential, ``du = 2x dx``, which is checked against ``g′``.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

import mpmath
import sympy as sp
from pydantic import BaseModel, ConfigDict

from prooflab.engine import hints
from prooflab.engine.algebra import (
    GREEK,
    RESERVED_NAMES,
    SEED,
    MathContext,
    MathInputError,
    compile_numeric,
    contains_float,
    equivalent,
    normalize,
    relation,
    split_relation,
    strip_label,
    to_latex,
)
from prooflab.engine.checker import ContentError, TopicHandler, VerdictBuilder, register
from prooflab.engine.models import Problem, Step, StepStatus, Submission, VerdictStatus

CONSTANTS = ("C", "K", "c")
SUB_SAMPLE = "real[0.1, 1.2]"  # inside (0, π/2): where trig substitutions are invertible
DIVERGES = "diverges"
_DIVERGE_WORDS = {"diverges", "divergent", "diverge", "dne", "does not exist", "it diverges"}
_SUB_NAME_RE = re.compile(r"[A-Za-z]|" + "|".join(GREEK))

hints.register_many(
    {
        "MISSING_C": "Right antiderivative, but an indefinite integral is a whole family of "
        "functions: add + C.",
        "LOG_ABS": "Close: ln(x) is only defined for x > 0, but the integrand isn't. Use "
        "ln|…| so the answer works on the whole domain.",
        "INTEGRAL_STEP_NOT_ANTIDERIVATIVE": "Differentiating this step doesn't give back the "
        "integrand, so it isn't an antiderivative of it.",
        "INTEGRAL_FACTOR": "Differentiate your answer: you get {factor} times the integrand. Look "
        "for a missing constant factor (often from du).",
        "INTEGRAL_SIGN": "Differentiate your answer: you get the negative of the integrand. Check "
        "the signs of your antiderivatives.",
        "DIFFERENTIATED_INSTEAD": "That's the derivative of the integrand, not an antiderivative.",
        "UNFINISHED_INTEGRAL": "Your answer still contains an integral. Finish evaluating it.",
        "BACK_SUBSTITUTE": "Write your final answer in terms of {var}: substitute back for {sub}.",
        "INTEGRAL_MIXED_VARIABLES": "After substituting, the integral should involve only {sub}. "
        "Replace d{var} using d{sub} = g′({var}) d{var}.",
        "INTEGRAL_BAD_SUB": "Write a substitution as u = g(x), or x = g(t) for a trig "
        "substitution.",
        "INTEGRAL_ONE_SUB": "ProofLab checks one substitution per attempt.",
        "INTEGRAL_DIFFERENTIAL_WRONG": "That differential isn't right. Differentiate the "
        "substitution again.",
        "BOUNDS_NOT_CHANGED": "When you substitute in a definite integral, change the limits of "
        "integration too (or switch back to the original variable before plugging in).",
        "INTEGRAL_VALUE_STEP_WRONG": "This value isn't equal to the integral.",
        "INTEGRAL_NEEDS_VALUE": "A definite integral is a number. Evaluate your antiderivative at "
        "the limits: F(b) − F(a).",
    }
)


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AntiderivativeParams(_Params):
    integrand: str
    var: str = "x"
    variables: dict[str, str] | None = None


class DefiniteIntegralParams(AntiderivativeParams):
    lower: str
    upper: str


# --------------------------------------------------------------------------- frames


@dataclass(frozen=True)
class Frame:
    """How steps are compared: the variable we differentiate in and the integrand in it."""

    ctx: MathContext
    x: sp.Symbol
    base: sp.Symbol
    integrand: sp.Expr
    sub: sp.Symbol | None = None
    g: sp.Expr | None = None
    inverse: bool = False

    def to_base(self, expr: sp.Expr) -> sp.Expr:
        if self.sub is None:
            return expr
        if self.inverse:
            return expr.subs(self.x, self.g)
        return expr.subs(self.sub, self.g)

    def integral_rate(self, integral: sp.Integral) -> sp.Expr | None:
        """d/d(base) of an indefinite integral appearing in a step."""
        if len(integral.limits) != 1:
            return None
        limit = integral.limits[0]
        var = limit[0]
        if len(limit) == 3:
            bounds = sp.Tuple(*limit[1:])
            return None if bounds.free_symbols & {self.x, self.base} else sp.Integer(0)
        body = self.to_base(integral.function)
        if var == self.base:
            return body
        if self.sub is not None and not self.inverse and var == self.sub:
            return body * sp.diff(self.g, self.x)
        if self.sub is not None and self.inverse and var == self.x:
            return body * sp.diff(self.g, self.sub)
        return None

    def latex(self) -> str:
        if self.sub is None or self.g is None:
            return ""
        if self.inverse:
            d = sp.diff(self.g, self.sub)
            return rf"{self.x} = {to_latex(self.g)},\quad d{self.x} = {to_latex(d)}\,d{self.sub}"
        d = sp.diff(self.g, self.x)
        return rf"{self.sub} = {to_latex(self.g)},\quad d{self.sub} = {to_latex(d)}\,d{self.x}"


def derivative(expr: sp.Expr, frame: Frame) -> sp.Expr | None:
    """d/d(base) of a step that may contain unevaluated integrals; ``None`` if unsupported."""
    integrals = list(expr.atoms(sp.Integral))
    top = [i for i in integrals if not any(j != i and j.has(i) for j in integrals)]
    holders = {integral: sp.Dummy(f"I{k}") for k, integral in enumerate(top)}
    phi = frame.to_base(expr.xreplace(holders))
    total = sp.diff(phi, frame.base)
    for integral, holder in holders.items():
        coeff = sp.diff(phi, holder)
        if coeff == 0:
            continue
        rate = frame.integral_rate(integral)
        if rate is None:
            return None
        total += coeff * rate
    if any(total.has(h) for h in holders.values()):
        return None
    return total


def _new_names(text: str, ctx: MathContext) -> list[str]:
    names: list[str] = []
    for ident in re.findall(r"[A-Za-z]+", normalize(text)):
        if ident in RESERVED_NAMES or ident in ctx.symbols or ident in names:
            continue
        names.append(ident)
    return names


def make_sub_frame(text: str, base: Frame) -> Frame:
    parts, ops = split_relation(normalize(text))
    if ops != ["="]:
        raise MathInputError(hints.message("INTEGRAL_BAD_SUB"), "INTEGRAL_BAD_SUB")
    lhs, rhs = parts[0].strip(), parts[1].strip()
    x, ctx = base.x, base.ctx
    try:
        if lhs == str(x):
            new = _new_names(rhs, ctx)
            if len(new) != 1 or not _SUB_NAME_RE.fullmatch(new[0]):
                raise MathInputError(
                    "Write the substitution as x = g(t) with one new variable, e.g. x = 2 sin(t).",
                    "INTEGRAL_BAD_SUB",
                )
            sub_ctx = ctx.extend({new[0]: SUB_SAMPLE})
            t = sub_ctx[new[0]]
            g = sub_ctx.parse(rhs)
            if not g.has(t) or g.has(x) or sp.diff(g, t) == 0:
                raise MathInputError(hints.message("INTEGRAL_BAD_SUB"), "INTEGRAL_BAD_SUB")
            integrand = base.integrand.subs(x, g) * sp.diff(g, t)
            return Frame(sub_ctx, x, t, integrand, t, g, inverse=True)
        if not _SUB_NAME_RE.fullmatch(lhs) or lhs in ctx.symbols or lhs in RESERVED_NAMES:
            raise MathInputError(
                f"Use a new variable name for the substitution, like u = g({x}).",
                "INTEGRAL_BAD_SUB",
            )
        sub_ctx = ctx.extend({lhs: "real"})
        u = sub_ctx[lhs]
        g = sub_ctx.parse(rhs)
    except ValueError as exc:
        if isinstance(exc, MathInputError):
            raise
        raise MathInputError(hints.message("INTEGRAL_BAD_SUB"), "INTEGRAL_BAD_SUB") from exc
    if g.has(u) or not g.has(x) or sp.diff(g, x) == 0:
        raise MathInputError(hints.message("INTEGRAL_BAD_SUB"), "INTEGRAL_BAD_SUB")
    return Frame(sub_ctx, x, x, base.integrand, u, g, inverse=False)


def _differential(text: str, frame: Frame) -> tuple[sp.Expr, sp.Expr] | None:
    """``du = 2x dx`` / ``du/dx = 2x`` → (student value, correct value); ``None`` if not one."""
    if frame.sub is None:
        return None
    top, bottom = (frame.x, frame.sub) if frame.inverse else (frame.sub, frame.x)
    parts, ops = split_relation(normalize(text))
    if ops != ["="]:
        return None
    lhs = parts[0].replace(" ", "")
    rhs = parts[1].strip()
    if lhs == f"d{top}/d{bottom}":
        value_text = rhs
    elif lhs == f"d{top}":
        m = re.fullmatch(rf"(.*?)\*?\s*d{bottom}", rhs)
        if not m:
            return None
        value_text = m.group(1) or "1"
    else:
        return None
    correct = sp.diff(frame.g, bottom)
    return frame.ctx.parse(value_text), correct


def _constant_value(expr: sp.Expr) -> mpmath.mpc | None:
    """Numeric value of a closed expression, including definite ``Integral``s (mpmath.quad)."""
    if expr.free_symbols:
        return None
    if expr in (sp.oo, -sp.oo, sp.zoo, sp.nan):
        return None
    with mpmath.workdps(30):
        try:
            value = mpmath.mpc(compile_numeric(expr, [])())
        except Exception:  # noqa: BLE001
            return None
    if not (mpmath.isfinite(value.real) and mpmath.isfinite(value.imag)):
        return None
    return value


def _close(a: mpmath.mpc | None, b: mpmath.mpc | None, tol: float = 1e-8) -> bool:
    return a is not None and b is not None and abs(a - b) <= tol * max(1, abs(a), abs(b))


def _drop_constants(expr: sp.Expr, ctx: MathContext) -> sp.Expr:
    return expr.subs({ctx[c]: 0 for c in CONSTANTS if c in ctx.symbols})


def _loses_real_domain(student: sp.Expr, key: sp.Expr, ctx: MathContext, x: sp.Symbol) -> bool:
    """Is the key real somewhere the student's answer isn't (e.g. ln x vs ln|x| for x < 0)?"""
    s, k = _drop_constants(student, ctx), _drop_constants(key, ctx)
    syms = sorted(s.free_symbols | k.free_symbols | {x}, key=str)
    fs, fk = compile_numeric(s, syms), compile_numeric(k, syms)
    rng = random.Random(SEED + 11)
    with mpmath.workdps(30):
        for _ in range(40):
            point = [ctx.spec(sym).sample(rng) for sym in syms]
            try:
                vk = mpmath.mpc(fk(*point))
            except Exception:  # noqa: BLE001
                continue
            if not mpmath.isfinite(vk.real) or abs(vk.imag) > 1e-12 * max(1, abs(vk.real)):
                continue
            try:
                vs = mpmath.mpc(fs(*point))
            except Exception:  # noqa: BLE001
                return True
            if abs(vs.imag) > 1e-9 * max(1, abs(vs.real)):
                return True
    return False


def _has_log_abs(expr: sp.Expr) -> bool:
    return any(a.args and a.args[0].has(sp.Abs) for a in expr.atoms(sp.log))


# --------------------------------------------------------------------------- shared handler


class _IntegralHandler(TopicHandler):
    step_kinds = frozenset({"expr", "sub"})

    def context(self, p: AntiderivativeParams) -> MathContext:
        return MathContext.build(
            p.variables or {p.var: "real"}, constants=CONSTANTS, allow_integral=True
        )

    def base_frame(self, p: AntiderivativeParams) -> Frame:
        ctx = self.context(p)
        x = ctx[p.var]
        return Frame(ctx, x, x, ctx.parse(p.integrand))

    def _sub_step(self, i: int, step: Step, base: Frame, frame: Frame, vb: VerdictBuilder) -> Frame:
        if frame.sub is not None:
            try:
                diff = _differential(step.content, frame)
            except MathInputError as exc:
                vb.step(i, step.kind, StepStatus.ERROR, exc.message, code=exc.code)
                return frame
            if diff is not None:
                student, correct = diff
                if equivalent(student, correct, frame.ctx):
                    vb.ok(i, step.kind, latex=frame.latex())
                else:
                    vb.error(i, step.kind, "INTEGRAL_DIFFERENTIAL_WRONG", latex=to_latex(student))
                return frame
            vb.error(i, step.kind, "INTEGRAL_ONE_SUB")
            return frame
        try:
            new = make_sub_frame(step.content, base)
        except MathInputError as exc:
            vb.step(i, step.kind, StepStatus.ERROR, exc.message, code=exc.code)
            return frame
        vb.ok(i, step.kind, "Substitution noted.", latex=new.latex())
        return new

    def _antiderivative_step(
        self, i: int, step: Step, expr: sp.Expr, frame: Frame, vb: VerdictBuilder, problem: Problem
    ) -> bool | None:
        latex = to_latex(expr)
        d = derivative(expr, frame)
        same = None if d is None else equivalent(d, frame.integrand, frame.ctx)
        if same:
            vb.ok(i, step.kind, latex=latex)
            return True
        if same is None:
            vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
            return None
        vb.error(i, step.kind, "INTEGRAL_STEP_NOT_ANTIDERIVATIVE", latex=latex)
        if frame.sub is not None and not frame.inverse:
            for integral in expr.atoms(sp.Integral):
                if integral.limits[0][0] == frame.sub and integral.function.has(frame.x):
                    vb.hint("INTEGRAL_MIXED_VARIABLES", step=i, var=frame.x, sub=frame.sub)
                    return False
        if vb.first_error == i and d is not None:
            self._factor_hint(vb, d, frame, step=i)
        return False

    @staticmethod
    def _factor_hint(vb: VerdictBuilder, d: sp.Expr, frame: Frame, step: int | None = None) -> bool:
        rel = relation(d, frame.integrand, frame.ctx)
        if rel is None:
            return False
        name, value = rel
        if name == "negated":
            vb.hint("INTEGRAL_SIGN", step=step)
            return True
        if name == "scaled":
            vb.hint("INTEGRAL_FACTOR", step=step, factor=f"${to_latex(value)}$")
            return True
        return False


# --------------------------------------------------------------------------- antiderivative


@register
class AntiderivativeHandler(_IntegralHandler):
    kind = "antiderivative"
    Params = AntiderivativeParams
    syntax_help = (
        "Enter an antiderivative with + C, e.g. x^3/3 + C. Steps can use int(f, x) for integrals "
        "still to do. Add a 'sub' step like u = x^2 + 1 (or x = 2 sin(t)) to substitute; later "
        "steps may use u. Each step should be an antiderivative of the integrand."
    )

    def setup(self, problem: Problem, p: AntiderivativeParams) -> tuple[Frame, sp.Expr]:
        base = self.base_frame(p)
        key = base.ctx.parse(strip_label(problem.answer))
        return base, key

    def validate(self, problem: Problem, params: AntiderivativeParams) -> None:
        try:
            base, key = self.setup(problem, params)
        except (MathInputError, KeyError, ValueError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc
        if not key.free_symbols & {base.ctx[c] for c in CONSTANTS}:
            raise ContentError(f"{problem.id}: the answer key should include + C")

    def verify_key(self, problem: Problem, params: AntiderivativeParams) -> bool | None:
        base, key = self.setup(problem, params)
        return equivalent(sp.diff(key, base.x), base.integrand, base.ctx)

    def check(
        self,
        problem: Problem,
        params: AntiderivativeParams,
        submission: Submission,
        vb: VerdictBuilder,
    ) -> None:
        base, key = self.setup(problem, params)
        frame = base
        for i, step in enumerate(submission.steps):
            if step.kind == "sub":
                frame = self._sub_step(i, step, base, frame, vb)
                continue
            expr = self.parse_step(vb, i, step, lambda t, c=frame.ctx: c.parse(strip_label(t)))
            if expr is not None:
                self._antiderivative_step(i, step, expr, frame, vb, problem)
        self._grade(problem, base, frame, key, submission.answer, vb)

    def _grade(
        self,
        problem: Problem,
        base: Frame,
        frame: Frame,
        key: sp.Expr,
        text: str | None,
        vb: VerdictBuilder,
    ) -> None:
        if text is None or not text.strip():
            return
        ctx, x, f = base.ctx, base.x, base.integrand
        try:
            student = ctx.parse(strip_label(text))
        except MathInputError as exc:
            if frame.sub is not None:
                try:
                    in_sub = frame.ctx.parse(strip_label(text))
                except MathInputError:
                    in_sub = None
                if in_sub is not None and in_sub.has(frame.sub):
                    vb.answer(
                        VerdictStatus.INCORRECT,
                        latex=to_latex(in_sub),
                        code="BACK_SUBSTITUTE",
                        var=x,
                        sub=frame.sub,
                    )
                    vb.hint("BACK_SUBSTITUTE", var=x, sub=frame.sub)
                    return
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        latex = to_latex(student)
        if student.has(sp.Integral):
            vb.answer(VerdictStatus.INCORRECT, latex=latex, code="UNFINISHED_INTEGRAL")
            vb.hint("UNFINISHED_INTEGRAL")
            return
        d = sp.diff(student, x)
        same = equivalent(d, f, ctx)
        if same:
            constants = {ctx[c] for c in CONSTANTS}
            problems_found = []
            if (
                _has_log_abs(key)
                and not _has_log_abs(student)
                and _loses_real_domain(student, key, ctx, x)
            ):
                problems_found.append("LOG_ABS")
            if not student.free_symbols & constants:
                problems_found.append("MISSING_C")
            if problems_found:
                vb.answer(VerdictStatus.PARTIAL, latex=latex, code=problems_found[0])
                for code in problems_found:
                    vb.hint(code)
            else:
                vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
            return
        if same is None:
            vb.answer(VerdictStatus.INVALID, latex=latex, code="UNVERIFIED")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
        mistake = self.match_mistake(
            problem,
            student,
            lambda t: ctx.parse(strip_label(t)),
            lambda s, m: equivalent(sp.diff(s, x), sp.diff(m, x), ctx),
        )
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
            return
        if equivalent(_drop_constants(student, ctx), sp.diff(f, x), ctx):
            vb.hint("DIFFERENTIATED_INSTEAD")
            return
        self._factor_hint(vb, d, base)


# --------------------------------------------------------------------------- definite


@register
class DefiniteIntegralHandler(_IntegralHandler):
    kind = "definite_integral"
    Params = DefiniteIntegralParams
    syntax_help = (
        "Enter the exact value (fractions, sqrt, pi, ln ...), or 'diverges' for a divergent "
        "improper integral. Steps can be antiderivatives, int(f, x, a, b), a 'sub' step like "
        "u = x^2 + 1, or values such as 16/4 - 1/4."
    )

    def setup(self, problem: Problem, p: DefiniteIntegralParams):
        base = self.base_frame(p)
        a, b = base.ctx.parse(p.lower), base.ctx.parse(p.upper)
        if a.free_symbols or b.free_symbols:
            raise ContentError(f"{problem.id}: limits of integration must be numbers")
        key = self.parse_value(problem.answer, base.ctx)
        return base, a, b, key

    @staticmethod
    def parse_value(text: str, ctx: MathContext) -> sp.Expr | str:
        t = text.strip().lower().rstrip(".")
        if t in _DIVERGE_WORDS:
            return DIVERGES
        value = ctx.parse(strip_label(text))
        return value

    def validate(self, problem: Problem, params: DefiniteIntegralParams) -> None:
        try:
            base, a, b, key = self.setup(problem, params)
        except (MathInputError, KeyError, ValueError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc
        if not isinstance(key, str) and key.free_symbols:
            raise ContentError(f"{problem.id}: the answer key must be a number")

    def verify_key(self, problem: Problem, params: DefiniteIntegralParams) -> bool | None:
        base, a, b, key = self.setup(problem, params)
        try:
            value = sp.integrate(base.integrand, (base.x, a, b))
        except Exception:  # noqa: BLE001
            value = None
        if value is not None and not value.has(sp.Integral):
            if value in (sp.oo, -sp.oo) or value.has(sp.zoo, sp.nan):
                return key == DIVERGES
            if isinstance(key, str):
                return False
            return bool(equivalent(value, key, base.ctx))
        numeric = _constant_value(sp.Integral(base.integrand, (base.x, a, b)))
        if numeric is None or isinstance(key, str):
            return None
        return _close(numeric, _constant_value(key))

    def _key_value(self, key: sp.Expr | str) -> mpmath.mpc | None:
        return None if isinstance(key, str) else _constant_value(key)

    def check(
        self,
        problem: Problem,
        params: DefiniteIntegralParams,
        submission: Submission,
        vb: VerdictBuilder,
    ) -> None:
        base, a, b, key = self.setup(problem, params)
        key_value = self._key_value(key)
        frame = base
        old_bound_values: list[mpmath.mpc] = []  # what the student gets if bounds aren't changed

        for i, step in enumerate(submission.steps):
            if step.kind == "sub":
                frame = self._sub_step(i, step, base, frame, vb)
                continue
            expr = self.parse_step(vb, i, step, lambda t, c=frame.ctx: c.parse(strip_label(t)))
            if expr is None:
                continue
            variables = {frame.x, frame.base} | ({frame.sub} if frame.sub is not None else set())
            if expr.free_symbols & variables:
                ok = self._antiderivative_step(i, step, expr, frame, vb, problem)
                if ok and frame.sub is not None and not frame.inverse and not expr.has(frame.x):
                    stale = _constant_value(expr.subs(frame.sub, b) - expr.subs(frame.sub, a))
                    if stale is not None:
                        old_bound_values.append(stale)
                continue
            self._value_step(
                i, step, _drop_constants(expr, frame.ctx), frame, a, b, key, key_value, vb
            )

        self._grade(problem, base, key, key_value, old_bound_values, submission.answer, vb)

    def _value_step(
        self, i, step, expr, frame: Frame, a, b, key, key_value, vb: VerdictBuilder
    ) -> None:
        latex = to_latex(expr)
        if key == DIVERGES:
            if expr in (sp.oo, -sp.oo):
                vb.ok(i, step.kind, latex=latex)
            else:
                vb.error(i, step.kind, "INTEGRAL_VALUE_STEP_WRONG", latex=latex)
            return
        value = _constant_value(expr)
        if value is None:
            vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
            return
        if _close(value, key_value):
            vb.ok(i, step.kind, latex=latex)
            return
        vb.error(i, step.kind, "INTEGRAL_VALUE_STEP_WRONG", latex=latex)
        if frame.sub is not None and not frame.inverse:
            moved = (frame.g.subs(frame.x, a), frame.g.subs(frame.x, b))
            for integral in expr.atoms(sp.Integral):
                lim = integral.limits[0]
                if (
                    len(lim) == 3
                    and lim[0] == frame.sub
                    and sp.simplify(lim[1] - a) == 0
                    and sp.simplify(lim[2] - b) == 0
                    and (sp.simplify(moved[0] - a) != 0 or sp.simplify(moved[1] - b) != 0)
                ):
                    vb.hint("BOUNDS_NOT_CHANGED", step=i)
                    return

    def _grade(
        self, problem: Problem, base: Frame, key, key_value, stale_values, text, vb: VerdictBuilder
    ) -> None:
        if text is None or not text.strip():
            return
        ctx = base.ctx
        try:
            student = self.parse_value(text, ctx)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        if isinstance(student, str):
            if key == DIVERGES:
                vb.answer(VerdictStatus.CORRECT, latex=r"\text{diverges}", code="CORRECT")
            else:
                vb.answer(VerdictStatus.INCORRECT, latex=r"\text{diverges}", code="WRONG")
            return
        latex = to_latex(student)
        if student.free_symbols - {ctx[c] for c in CONSTANTS}:
            vb.answer(VerdictStatus.INCORRECT, latex=latex, code="INTEGRAL_NEEDS_VALUE")
            vb.hint("INTEGRAL_NEEDS_VALUE")
            return
        student = _drop_constants(student, ctx)
        if key == DIVERGES:
            if student in (sp.oo, -sp.oo):
                vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
                return
            vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
            mistake = self.match_mistake(
                problem,
                student,
                lambda t: ctx.parse(strip_label(t)),
                lambda s, m: equivalent(s, m, ctx),
            )
            if mistake is not None:
                vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
            return
        value = _constant_value(student)
        if _close(value, key_value):
            if contains_float(student) and not contains_float(key):
                vb.answer(VerdictStatus.PARTIAL, latex=latex, code="INEXACT")
                vb.hint("INEXACT")
            else:
                vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
            return
        if contains_float(student) and _close(value, key_value, tol=1e-3):
            vb.answer(VerdictStatus.PARTIAL, latex=latex, code="INEXACT")
            vb.hint("INEXACT")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
        if any(_close(value, s) for s in stale_values):
            vb.hint("BOUNDS_NOT_CHANGED")
            return
        if value is not None:
            self.diagnose_expression(vb, problem, ctx, student, key)
