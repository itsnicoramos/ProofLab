"""Vector calculus (SPEC §5.6): divergence, curl, potential_function, line_integral."""

from __future__ import annotations

from collections.abc import Sequence

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field, model_validator

from prooflab.engine import hints
from prooflab.engine.algebra import (
    MathContext,
    MathInputError,
    equivalent,
    normalize,
    numeric_value,
    parse_tuple,
    split_top,
    strip_label,
    strip_outer,
    to_latex,
    values_equal,
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
        "CURL_NOT_DIV": "That's the curl of F (a vector). The divergence is a scalar: "
        "∂P/∂x + ∂Q/∂y + ∂R/∂z.",
        "DIV_NOT_CURL": "That's the divergence of F (a scalar). The curl is a vector: "
        "⟨R_y − Q_z, P_z − R_x, Q_x − P_y⟩.",
        "DIV_IS_SCALAR": "The divergence is a single scalar expression, not a vector.",
        "CURL_IS_VECTOR": "The curl is a vector. Enter it as <a, b, c>.",
        "DIV_MIXED_PARTIALS": "Divergence pairs each component with its own variable: "
        "∂P/∂x + ∂Q/∂y + ∂R/∂z. It looks like the pairing got mixed up.",
        "CURL_SIGN": "Check the sign of the {component}. Each curl component is a difference of "
        "two partial derivatives, and the order matters.",
        "CURL_COMPONENT": "Check the {component}.",
        "POTENTIAL_PARTIAL": "So far F agrees with {good}, but not with {bad}. Add the terms the "
        "other components need.",
        "POTENTIAL_COMPONENT": "Compare {bad} with the matching component(s) of F: they don't "
        "agree yet.",
        "POTENTIAL_DOUBLE_COUNT": "It looks like you integrated each component and added all the "
        "results. Terms shared between components then get counted more than once.",
        "NOT_CONSERVATIVE": "Check whether F is conservative before looking for f: compare the "
        "cross-partials (e.g. ∂P/∂y and ∂Q/∂x).",
        "FIELD_IS_CONSERVATIVE": "Compare the cross-partials again: they agree, so F is "
        "conservative and a potential function exists.",
        "MISSING_DERIVATIVE": "Don't forget the factor from the parametrization: dr = r′(t) dt for "
        "a vector field, ds = |r′(t)| dt for a scalar one.",
        "LINE_INTEGRAL_STEP_WRONG": "This step doesn't match the integrand in t, an antiderivative "
        "of it, or the value of the integral.",
        "LINE_INTEGRAL_BOUNDS": "The integrand is right, but integrate over the parameter "
        "interval given in the problem.",
    }
)

_NOT_CONSERVATIVE_WORDS = {
    "not conservative",
    "none",
    "no potential",
    "no potential function",
    "no such function",
    "dne",
    "does not exist",
    "f is not conservative",
    "the field is not conservative",
}
_COMPONENT_NAMES = ("first (i) component", "second (j) component", "third (k) component")
_DEFAULT_VARS = ("x", "y", "z")


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _input_code(exc: MathInputError) -> str:
    return exc.code if hints.is_registered(exc.code) else "PARSE_ERROR"


def _tuple(text: str, ctx: MathContext, n: int | None = None) -> list[sp.Expr]:
    try:
        return parse_tuple(text, ctx, n)
    except MathInputError as exc:
        raise MathInputError(exc.message, _input_code(exc)) from exc


def _partials(names: Sequence[str]) -> str:
    return _join([f"∂f/∂{n}" for n in names])


def _join(words: Sequence[str]) -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def _looks_like_vector(text: str) -> bool:
    return len(split_top(strip_outer(normalize(text)), ",")) > 1


def _vector_latex(vec: Sequence[sp.Expr]) -> str:
    return r"\left\langle " + ", ".join(to_latex(v) for v in vec) + r" \right\rangle"


def divergence(field: Sequence[sp.Expr], syms: Sequence[sp.Symbol]) -> sp.Expr:
    return sp.Add(*(sp.diff(f, s) for f, s in zip(field, syms, strict=True)))


def curl(field: Sequence[sp.Expr], syms: Sequence[sp.Symbol]) -> list[sp.Expr]:
    P, Q, R = field
    x, y, z = syms
    d = sp.diff
    return [d(R, y) - d(Q, z), d(P, z) - d(R, x), d(Q, x) - d(P, y)]


def is_conservative(field: Sequence[sp.Expr], syms: Sequence[sp.Symbol], ctx: MathContext) -> bool:
    if len(field) == 2:
        checks = [sp.diff(field[1], syms[0]) - sp.diff(field[0], syms[1])]
    else:
        checks = curl(field, syms)
    return all(equivalent(c, 0, ctx) for c in checks)


# --------------------------------------------------------------------------- fields


class FieldParams(_Params):
    field: list[str] = Field(min_length=2, max_length=3)
    vars: list[str] | None = None
    variables: dict[str, str] | None = None


class _FieldHandler(TopicHandler):
    dims: tuple[int, ...] = (2, 3)
    constants: tuple[str, ...] = ()

    def field_setup(self, problem: Problem, p: FieldParams):
        names = p.vars or list(_DEFAULT_VARS[: len(p.field)])
        if len(names) != len(p.field) or len(p.field) not in self.dims:
            raise ContentError(
                f"{problem.id}: field and vars must have the same length {self.dims}"
            )
        ctx = MathContext.build(
            p.variables or dict.fromkeys(names, "real"), constants=self.constants
        )
        syms = [ctx[n] for n in names]
        try:
            field = [ctx.parse(c) for c in p.field]
        except MathInputError as exc:
            raise ContentError(f"{problem.id}: bad field component: {exc.message}") from exc
        return ctx, syms, field

    def validate(self, problem: Problem, params: FieldParams) -> None:
        self.setup(problem, params)

    def setup(self, problem: Problem, params: FieldParams):  # pragma: no cover - overridden
        raise NotImplementedError


@register
class DivergenceHandler(_FieldHandler):
    kind = "divergence"
    Params = FieldParams
    syntax_help = (
        "Enter div F as one expression, e.g. 2x + z. Steps can be rewrites of the divergence."
    )

    def setup(self, problem: Problem, p: FieldParams):
        ctx, syms, field = self.field_setup(problem, p)
        try:
            key = ctx.parse(strip_label(problem.answer))
        except MathInputError as exc:
            raise ContentError(f"{problem.id}: bad answer key: {exc.message}") from exc
        return ctx, syms, field, key

    def verify_key(self, problem: Problem, params: FieldParams) -> bool | None:
        ctx, syms, field, key = self.setup(problem, params)
        return equivalent(divergence(field, syms), key, ctx)

    def _detectors(self, ctx: MathContext, syms, field) -> list[Detector]:
        from itertools import permutations

        out: list[Detector] = []
        seen: list[sp.Expr] = [divergence(field, syms)]
        for perm in permutations(range(len(syms))):
            if list(perm) == list(range(len(syms))):
                continue
            wrong = sp.Add(*(sp.diff(f, syms[j]) for f, j in zip(field, perm, strict=True)))
            if any(equivalent(wrong, s, ctx) for s in seen):
                continue
            seen.append(wrong)
            out.append(
                lambda s, w=wrong: (
                    ("DIV_MIXED_PARTIALS", {})  # type: ignore[misc]
                    if equivalent(s, w, ctx, symbolic_fallback=False)
                    else None
                )
            )
        return out

    def check(
        self, problem: Problem, params: FieldParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, syms, field, key = self.setup(problem, params)
        self.check_steps_against(vb, submission.steps, ctx, key, problem=problem)
        text = submission.answer
        if text is not None and text.strip() and _looks_like_vector(text):
            try:
                vec = _tuple(text, ctx)
            except MathInputError as exc:
                vb.answer(VerdictStatus.INVALID, exc.message, code=_input_code(exc))
                return
            vb.answer(VerdictStatus.INCORRECT, latex=_vector_latex(vec), code="WRONG")
            if len(vec) == 3 == len(field) and all(
                equivalent(a, b, ctx) for a, b in zip(vec, curl(field, syms), strict=True)
            ):
                vb.hint("CURL_NOT_DIV")
            else:
                vb.hint("DIV_IS_SCALAR")
            return
        self.grade_expression(
            vb, problem, ctx, text, key, detectors=self._detectors(ctx, syms, field)
        )


def _vector_check(
    vec: Sequence[sp.Expr], key: Sequence[sp.Expr], ctx: MathContext
) -> list[bool | None]:
    return [equivalent(a, b, ctx) for a, b in zip(vec, key, strict=True)]


@register
class CurlHandler(_FieldHandler):
    kind = "curl"
    Params = FieldParams
    dims = (3,)
    syntax_help = (
        "Enter curl F as a vector, e.g. <0, -x, 2y>. Steps can be the curl in other forms."
    )

    def setup(self, problem: Problem, p: FieldParams):
        ctx, syms, field = self.field_setup(problem, p)
        try:
            key = parse_tuple(problem.answer, ctx, 3)
        except MathInputError as exc:
            raise ContentError(f"{problem.id}: bad answer key: {exc.message}") from exc
        return ctx, syms, field, key

    def verify_key(self, problem: Problem, params: FieldParams) -> bool | None:
        ctx, syms, field, key = self.setup(problem, params)
        results = _vector_check(curl(field, syms), key, ctx)
        if any(r is False for r in results):
            return False
        return None if any(r is None for r in results) else True

    def check(
        self, problem: Problem, params: FieldParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, syms, field, key = self.setup(problem, params)

        for i, step in enumerate(submission.steps):
            vec = self.parse_step(vb, i, step, lambda t: _tuple(strip_label(t), ctx, 3))
            if vec is None:
                continue
            results = _vector_check(vec, key, ctx)
            latex = _vector_latex(vec)
            if all(results):
                vb.ok(i, step.kind, latex=latex)
            elif any(r is False for r in results):
                bad = [_COMPONENT_NAMES[j] for j, r in enumerate(results) if r is False]
                vb.error(i, step.kind, "CURL_COMPONENT", latex=latex, component=_join(bad))
            else:
                vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")

        text = submission.answer
        if text is None or not text.strip():
            return
        if not _looks_like_vector(text):
            try:
                scalar = ctx.parse(strip_label(text))
            except MathInputError as exc:
                vb.answer(VerdictStatus.INVALID, exc.message, code=_input_code(exc))
                return
            vb.answer(VerdictStatus.INCORRECT, latex=to_latex(scalar), code="WRONG")
            if equivalent(scalar, divergence(field, syms), ctx):
                vb.hint("DIV_NOT_CURL")
            else:
                vb.hint("CURL_IS_VECTOR")
            return
        try:
            vec = _tuple(strip_label(text), ctx, 3)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=_input_code(exc))
            return
        latex = _vector_latex(vec)
        results = _vector_check(vec, key, ctx)
        if all(results):
            vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
            return
        if not any(r is False for r in results):
            vb.answer(VerdictStatus.INVALID, latex=latex, code="UNVERIFIED")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
        mistake = self.match_mistake(
            problem,
            vec,
            lambda t: _tuple(t, ctx, 3),
            lambda a, b: all(_vector_check(a, b, ctx)),
        )
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
            return
        for j, ok in enumerate(results):
            if ok is not False:
                continue
            if not equivalent(key[j], 0, ctx) and equivalent(vec[j], -key[j], ctx):
                vb.hint("CURL_SIGN", component=_COMPONENT_NAMES[j])
            else:
                vb.hint("CURL_COMPONENT", component=_COMPONENT_NAMES[j])


# --------------------------------------------------------------------------- potential


@register
class PotentialFunctionHandler(_FieldHandler):
    kind = "potential_function"
    Params = FieldParams
    constants = ("C", "K")
    syntax_help = (
        "Enter a potential function f with ∇f = F, e.g. x^2 y + z (adding + C is fine), "
        "or 'not conservative' if no such f exists. Steps can be partial results, like "
        "the integral of P with respect to x."
    )

    def setup(self, problem: Problem, p: FieldParams):
        ctx, syms, field = self.field_setup(problem, p)
        if problem.answer.strip().lower() in _NOT_CONSERVATIVE_WORDS:
            return ctx, syms, field, None
        try:
            key = ctx.parse(strip_label(problem.answer))
        except MathInputError as exc:
            raise ContentError(f"{problem.id}: bad answer key: {exc.message}") from exc
        return ctx, syms, field, key

    @staticmethod
    def _matches(f: sp.Expr, field, syms, ctx: MathContext) -> list[bool | None]:
        return [equivalent(sp.diff(f, s), comp, ctx) for comp, s in zip(field, syms, strict=True)]

    def verify_key(self, problem: Problem, params: FieldParams) -> bool | None:
        ctx, syms, field, key = self.setup(problem, params)
        conservative = is_conservative(field, syms, ctx)
        if key is None:
            return not conservative
        return conservative and all(self._matches(key, field, syms, ctx))

    def check(
        self, problem: Problem, params: FieldParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, syms, field, key = self.setup(problem, params)
        names = [str(s) for s in syms]

        for i, step in enumerate(submission.steps):
            expr = self.parse_step(vb, i, step, lambda t: ctx.parse(strip_label(t)))
            if expr is None:
                continue
            latex = to_latex(expr)
            matches = self._matches(expr, field, syms, ctx)
            good = [n for n, m in zip(names, matches, strict=True) if m]
            bad = [n for n, m in zip(names, matches, strict=True) if m is False]
            if not bad and len(good) == len(names):
                vb.ok(i, step.kind, "∇f matches F.", latex=latex)
            elif good and bad:
                vb.step(
                    i,
                    step.kind,
                    StepStatus.WARNING,
                    latex=latex,
                    code="POTENTIAL_PARTIAL",
                    good=_partials(good),
                    bad=_partials(bad),
                )
            elif bad:
                vb.error(i, step.kind, "POTENTIAL_COMPONENT", latex=latex, bad=_partials(bad))
            else:
                vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")

        text = submission.answer
        if text is None or not text.strip():
            return
        if text.strip().lower().rstrip(".") in _NOT_CONSERVATIVE_WORDS:
            latex = r"\text{not conservative}"
            if key is None:
                vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
            else:
                vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
                vb.hint("FIELD_IS_CONSERVATIVE")
            return
        try:
            student = ctx.parse(strip_label(text))
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=_input_code(exc))
            return
        latex = to_latex(student)
        matches = self._matches(student, field, syms, ctx)
        bad = [n for n, m in zip(names, matches, strict=True) if m is False]
        if key is None:
            vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
            vb.hint("NOT_CONSERVATIVE")
            return
        if all(matches):
            vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
            return
        if not bad:
            vb.answer(VerdictStatus.INVALID, latex=latex, code="UNVERIFIED")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
        mistake = self.match_mistake(
            problem, student, ctx.parse, lambda a, b: equivalent(a, b, ctx)
        )
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
            return
        try:
            double = sp.Add(*(sp.integrate(c, s) for c, s in zip(field, syms, strict=True)))
            doubled = bool(equivalent(sp.diff(student - double, syms[0]), 0, ctx)) and all(
                equivalent(sp.diff(student - double, s), 0, ctx) for s in syms
            )
        except Exception:  # noqa: BLE001
            doubled = False
        if doubled:
            vb.hint("POTENTIAL_DOUBLE_COUNT")
        else:
            vb.hint("POTENTIAL_COMPONENT", bad=_partials(bad))


# --------------------------------------------------------------------------- line integrals


class LineIntegralParams(_Params):
    curve: list[str] = Field(min_length=2, max_length=3)
    param: str = "t"
    bounds: list[str] = Field(min_length=2, max_length=2)
    field: list[str] | None = None
    scalar: str | None = None
    vars: list[str] | None = None

    @model_validator(mode="after")
    def _one_integrand(self) -> LineIntegralParams:
        if (self.field is None) == (self.scalar is None):
            raise ValueError("give exactly one of 'field' (F · dr) or 'scalar' (f ds)")
        if self.field is not None and len(self.field) != len(self.curve):
            raise ValueError("field and curve must have the same number of components")
        return self


class _LineSetup:
    def __init__(self, ctx, t, a, b, integrand, dropped, key) -> None:
        self.ctx: MathContext = ctx
        self.t: sp.Symbol = t
        self.a: sp.Expr = a
        self.b: sp.Expr = b
        self.integrand: sp.Expr = integrand
        self.dropped: list[sp.Expr] = dropped
        self.key: sp.Expr = key


def definite_value(integrand: sp.Expr, t: sp.Symbol, a: sp.Expr, b: sp.Expr) -> sp.Expr:
    """Exact value if SymPy finds one, else a 30-digit numeric value."""
    try:
        value = sp.integrate(integrand, (t, a, b))
        if not value.has(sp.Integral):
            return value
    except Exception:  # noqa: BLE001
        pass
    return sp.Integral(integrand, (t, a, b)).evalf(30)


@register
class LineIntegralHandler(TopicHandler):
    kind = "line_integral"
    Params = LineIntegralParams
    syntax_help = (
        "Enter the exact value of the integral. Steps can be the integrand in t "
        "(F(r(t))·r'(t) or f(r(t))|r'(t)|), an antiderivative of it, an integral written as "
        "int(g, t, a, b), or a value."
    )

    def setup(self, problem: Problem, p: LineIntegralParams) -> _LineSetup:
        names = p.vars or list(_DEFAULT_VARS[: len(p.curve)])
        if len(names) != len(p.curve):
            raise ContentError(f"{problem.id}: vars and curve must have the same length")
        try:
            base = MathContext.build([p.param])
            a, b = base.parse(p.bounds[0]), base.parse(p.bounds[1])
            lo, hi = sorted((float(a), float(b)))
            ctx = MathContext.build(
                {p.param: {"domain": "real", "sample": [lo, hi]}}, allow_integral=True
            )
            t = ctx[p.param]
            fctx = MathContext.build(names)
            r = [ctx.parse(c) for c in p.curve]
            rp = [sp.diff(c, t) for c in r]
            subs = {fctx[n]: c for n, c in zip(names, r, strict=True)}
            if p.field is not None:
                Fr = [fctx.parse(c).subs(subs) for c in p.field]
                integrand = sp.Add(*(f * d for f, d in zip(Fr, rp, strict=True)))
                dropped = [sp.Add(*Fr), sp.Add(*(f * c for f, c in zip(Fr, r, strict=True)))]
            else:
                assert p.scalar is not None
                fr = fctx.parse(p.scalar).subs(subs)
                integrand = fr * sp.sqrt(sp.Add(*(d**2 for d in rp)))
                dropped = [fr]
            key = ctx.parse(problem.answer)
        except (MathInputError, TypeError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc
        if key.free_symbols:
            raise ContentError(f"{problem.id}: the answer key must be a number")
        return _LineSetup(ctx, t, a, b, integrand, dropped, key)

    def validate(self, problem: Problem, params: LineIntegralParams) -> None:
        self.setup(problem, params)

    def verify_key(self, problem: Problem, params: LineIntegralParams) -> bool | None:
        s = self.setup(problem, params)
        return values_equal(definite_value(s.integrand, s.t, s.a, s.b), s.key, tol=1e-12)

    def _is_dropped(self, s: _LineSetup, g: sp.Expr) -> bool:
        return any(
            equivalent(g, d, s.ctx, symbolic_fallback=False)
            and not equivalent(d, s.integrand, s.ctx)
            for d in s.dropped
        )

    def _check_integral_step(self, i, kind, s: _LineSetup, expr: sp.Expr, latex, vb) -> bool:
        """Handle a step written with int(...). Returns True if it was decided here."""
        integrals = list(expr.atoms(sp.Integral))
        if len(integrals) != 1:
            return False
        integral = integrals[0]
        if list(integral.variables) != [s.t] or len(integral.limits[0]) != 3:
            return False
        g = integral.function
        _, lo, hi = integral.limits[0]
        if equivalent(g, s.integrand, s.ctx):
            if values_equal(lo, s.a) and values_equal(hi, s.b):
                vb.ok(i, kind, "That's the line integral as an integral in t.", latex=latex)
            else:
                vb.error(i, kind, "LINE_INTEGRAL_BOUNDS", latex=latex)
            return True
        if self._is_dropped(s, g):
            vb.error(i, kind, "MISSING_DERIVATIVE", latex=latex)
            return True
        return False

    def check(
        self,
        problem: Problem,
        params: LineIntegralParams,
        submission: Submission,
        vb: VerdictBuilder,
    ) -> None:
        s = self.setup(problem, params)
        t = s.t

        for i, step in enumerate(submission.steps):
            expr = self.parse_step(vb, i, step, lambda text: s.ctx.parse(strip_label(text)))
            if expr is None:
                continue
            latex = to_latex(expr)
            if expr.has(sp.Integral):
                if self._check_integral_step(i, step.kind, s, expr, latex, vb):
                    continue
                if not expr.free_symbols:
                    value = numeric_value(expr)
                    if value is not None and values_equal(expr, s.key, tol=1e-12):
                        vb.ok(i, step.kind, latex=latex)
                    elif value is None:
                        vb.step(
                            i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP"
                        )
                    else:
                        vb.error(i, step.kind, "LINE_INTEGRAL_STEP_WRONG", latex=latex)
                    continue
                vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
            elif expr.has(t):
                if equivalent(expr, s.integrand, s.ctx):
                    vb.ok(i, step.kind, "That's the integrand in t.", latex=latex)
                elif equivalent(sp.diff(expr, t), s.integrand, s.ctx):
                    vb.ok(i, step.kind, "That's an antiderivative of the integrand.", latex=latex)
                elif self._is_dropped(s, expr):
                    vb.error(i, step.kind, "MISSING_DERIVATIVE", latex=latex)
                else:
                    vb.error(i, step.kind, "LINE_INTEGRAL_STEP_WRONG", latex=latex)
            elif values_equal(expr, s.key):
                vb.ok(i, step.kind, "That's the value of the integral.", latex=latex)
            else:
                vb.error(i, step.kind, "LINE_INTEGRAL_STEP_WRONG", latex=latex)

        def dropped_detector(d: sp.Expr) -> Detector:
            def detect(student: sp.Expr):
                if equivalent(d, s.integrand, s.ctx):
                    return None
                value = definite_value(d, t, s.a, s.b)
                return ("MISSING_DERIVATIVE", {}) if values_equal(student, value) else None

            return detect

        self.grade_expression(
            vb,
            problem,
            s.ctx,
            submission.answer,
            s.key,
            require_exact=True,
            detectors=[dropped_detector(d) for d in s.dropped],
        )
