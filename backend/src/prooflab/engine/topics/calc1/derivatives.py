"""Derivatives (SPEC §5.3): ``derivative``, ``tangent_line``, ``implicit_derivative``."""

from __future__ import annotations

import random

import mpmath
import sympy as sp
from pydantic import BaseModel, ConfigDict, Field

from prooflab.engine import hints
from prooflab.engine.algebra import (
    SEED,
    MathContext,
    MathInputError,
    compile_numeric,
    equivalent,
    normalize,
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
        "PRODUCT_RULE": "Check the product rule: (uv)′ = u′v + uv′, not u′v′.",
        "QUOTIENT_RULE": "Check the quotient rule: (u/v)′ = (u′v − uv′)/v². The order of the "
        "numerator terms matters.",
        "CHAIN_RULE": "Don't forget the chain rule: multiply by the derivative of the inside "
        "function.",
        "POWER_RULE": "Power rule: d/dx xⁿ = n·xⁿ⁻¹. Remember to lower the exponent by one.",
        "INTEGRATED_INSTEAD": "That's an antiderivative of f, not its derivative.",
        "WRONG_ORDER": "That's derivative number {got}; this problem asks for derivative number "
        "{want}.",
        "NOT_A_LINE": "A tangent line is a line: y = mx + b with numbers m and b. Plug x = a into "
        "f′(x) to get a number for the slope.",
        "SLOPE_ONLY": "That's the slope. The answer should be the whole line, y = mx + b.",
        "WRONG_SLOPE": "Your line passes through the right point, but its slope isn't f′(a).",
        "WRONG_POINT": "Your slope is right, but the line doesn't pass through (a, f(a)).",
        "WRONG_VALUE": "This value isn't f′(a) or f(a) for this problem.",
        "INVERTED_RATIO": "It looks like you computed dx/dy instead of dy/dx. Solve for dy/dx.",
    }
)


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- detectors


def _matches(student: sp.Expr, candidate: sp.Expr, ctx: MathContext) -> bool:
    try:
        return bool(equivalent(student, candidate, ctx, symbolic_fallback=False))
    except Exception:  # noqa: BLE001
        return False


def _detector(ctx: MathContext, candidate: sp.Expr, code: str, **params: object) -> Detector:
    def detect(student: sp.Expr) -> tuple[str, dict[str, object]] | None:
        return (code, params) if _matches(student, candidate, ctx) else None

    return detect


def rule_detectors(f: sp.Expr, x: sp.Symbol, ctx: MathContext) -> list[Detector]:
    """Wrong answers produced by misapplying the product, quotient, chain and power rules."""
    out: list[Detector] = []
    d = sp.diff
    coeff, body = f.as_independent(x, as_Add=False)
    num, den = sp.fraction(body)

    if den.has(x) and num != 1:
        n1, d1 = d(num, x), d(den, x)
        for wrong in ((n1 * den + num * d1) / den**2, (num * d1 - n1 * den) / den**2, n1 / d1):
            out.append(_detector(ctx, coeff * wrong, "QUOTIENT_RULE"))
    elif body.is_Mul:
        factors = [a for a in body.args if a.has(x)]
        if len(factors) >= 2:
            u, v = factors[0], sp.Mul(*factors[1:])
            for wrong in (d(u, x) * d(v, x), d(u, x) * v, u * d(v, x)):
                out.append(_detector(ctx, coeff * wrong, "PRODUCT_RULE"))

    inner = None
    if isinstance(body, sp.Function) and len(body.args) == 1 and body.args[0] != x:
        inner = body.args[0]
        u = sp.Dummy("u")
        no_chain = d(body.func(u), u).subs(u, inner)
    elif body.is_Pow and body.base != x and body.base.has(x) and not body.exp.has(x):
        inner = body.base
        no_chain = body.exp * inner ** (body.exp - 1)
    if inner is not None and inner.has(x):
        out.append(_detector(ctx, coeff * no_chain, "CHAIN_RULE"))

    if body.is_Pow and body.base == x and not body.exp.has(x):
        n = body.exp
        out.append(_detector(ctx, coeff * n * x**n, "POWER_RULE"))
        if n != -1:
            out.append(_detector(ctx, coeff * x ** (n + 1) / (n + 1), "INTEGRATED_INSTEAD"))
    return out


# --------------------------------------------------------------------------- derivative


def derivative_name(k: int) -> str:
    return {1: "f′(x)", 2: "f″(x)", 3: "f‴(x)"}.get(k, f"f⁽{k}⁾(x)")


class DerivativeParams(_Params):
    function: str
    var: str = "x"
    order: int = Field(default=1, ge=1, le=4)
    variables: dict[str, str] | None = None


@register
class DerivativeHandler(TopicHandler):
    kind = "derivative"
    Params = DerivativeParams
    syntax_help = (
        "Enter the derivative as an expression, e.g. 2x sin(x) + x^2 cos(x). "
        "Labels like f'(x) = ... are fine. Each step should be a rewrite of the derivative."
    )

    def setup(self, problem: Problem, p: DerivativeParams):
        ctx = MathContext.build(p.variables or {p.var: "real"})
        return ctx, ctx.parse(p.function), ctx[p.var], ctx.parse(strip_label(problem.answer))

    def validate(self, problem: Problem, params: DerivativeParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def verify_key(self, problem: Problem, params: DerivativeParams) -> bool | None:
        ctx, f, x, key = self.setup(problem, params)
        return equivalent(sp.diff(f, x, params.order), key, ctx)

    def check(
        self, problem: Problem, params: DerivativeParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, f, x, key = self.setup(problem, params)
        detectors = rule_detectors(f, x, ctx) if params.order == 1 else []
        for k in range(1, params.order):
            detectors.append(
                _detector(ctx, sp.diff(f, x, k), "WRONG_ORDER", got=k, want=params.order)
            )
        if params.order == 1:
            self.check_steps_against(
                vb,
                submission.steps,
                ctx,
                key,
                problem=problem,
                detectors=detectors,
                target_name=derivative_name(1),
            )
        else:
            self._check_staged_steps(vb, problem, ctx, f, x, key, params.order, submission)
        self.grade_expression(vb, problem, ctx, submission.answer, key, detectors=detectors)

    def _check_staged_steps(self, vb, problem, ctx, f, x, key, order, submission) -> None:
        """For f″ and higher, steps may pass through f′, f″, … in order."""
        stages = [sp.diff(f, x, k) for k in range(1, order)] + [key]
        stage = 0
        for i, step in enumerate(submission.steps):
            expr = self.parse_step(vb, i, step, lambda t: ctx.parse(strip_label(t)))
            if expr is None:
                continue
            latex = to_latex(expr)
            match = next((k for k in range(stage, order) if equivalent(expr, stages[k], ctx)), None)
            if match is not None:
                stage = match
                vb.ok(i, step.kind, f"That's {derivative_name(match + 1)}.", latex=latex)
                continue
            vb.error(
                i,
                step.kind,
                "STEP_NOT_EQUAL_TO_TARGET",
                f"This step isn't equal to {derivative_name(stage + 1)}"
                + (" or a later derivative." if stage + 1 < order else "."),
                latex=latex,
            )
            if vb.first_error == i:
                detectors = rule_detectors(f, x, ctx) if stage == 0 else []
                self.diagnose_expression(
                    vb, problem, ctx, expr, stages[stage], detectors=detectors, step=i
                )


# --------------------------------------------------------------------------- tangent line


class TangentLineParams(_Params):
    function: str
    var: str = "x"
    at: str


def _parse_line(text: str, ctx: MathContext, x: sp.Symbol, y: sp.Symbol) -> sp.Expr:
    """Parse ``y = mx + b`` (or any equation linear in y) and return the right-hand side."""
    parts, ops = split_relation(normalize(text))
    if ops != ["="]:
        raise MathInputError("Write the line as an equation, like y = 3x - 2.", "NOT_AN_EQUATION")
    lhs, rhs = ctx.parse(parts[0]), ctx.parse(parts[1])
    eq = sp.expand(lhs - rhs)
    a = sp.diff(eq, y)
    if a == 0 or a.has(y) or a.has(x):
        raise MathInputError("Write the line in terms of x and y, like y = 3x - 2.", "NOT_A_LINE")
    return sp.expand(sp.solve(eq, y)[0])


@register
class TangentLineHandler(TopicHandler):
    kind = "tangent_line"
    Params = TangentLineParams
    syntax_help = (
        "Enter the line as an equation, e.g. y = 4x - 3. Steps can be the derivative "
        "(f'(x) = ...), the slope or point value, or the line in another form."
    )

    def setup(self, problem: Problem, p: TangentLineParams):
        ctx = MathContext.build({p.var: "real", "y": "real"})
        x, y = ctx[p.var], ctx["y"]
        f = ctx.parse(p.function)
        a = ctx.parse(p.at)
        fprime = sp.diff(f, x)
        m, fa = fprime.subs(x, a), f.subs(x, a)
        line = sp.expand(fa + m * (x - a))
        key = _parse_line(problem.answer, ctx, x, y)
        return ctx, x, y, f, a, fprime, m, fa, line, key

    def validate(self, problem: Problem, params: TangentLineParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError, IndexError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def verify_key(self, problem: Problem, params: TangentLineParams) -> bool | None:
        ctx, x, y, f, a, fprime, m, fa, line, key = self.setup(problem, params)
        return equivalent(line, key, ctx)

    def check(
        self,
        problem: Problem,
        params: TangentLineParams,
        submission: Submission,
        vb: VerdictBuilder,
    ) -> None:
        ctx, x, y, f, a, fprime, m, fa, line, key = self.setup(problem, params)

        for i, step in enumerate(submission.steps):
            text = step.content
            stripped = strip_label(text)
            lhs = text.split("=")[0].strip() if "=" in text else ""
            is_derivative_label = stripped != text and any(c in lhs for c in "'d∂")
            # "y = x - 2" is a line, not a label: only f(1) = …, f'(x) = …, dy/dx = … are labels.
            if "=" in text and (stripped == text or lhs == str(y)):
                parsed = self.parse_step(vb, i, step, lambda t: _parse_line(t, ctx, x, y))
                if parsed is None:
                    continue
                latex = f"y = {to_latex(parsed)}"
                if equivalent(parsed, line, ctx):
                    vb.ok(i, step.kind, latex=latex)
                else:
                    vb.error(i, step.kind, "STEP_NOT_EQUAL_TO_TARGET", latex=latex)
                continue
            expr = self.parse_step(vb, i, step, lambda t: ctx.parse(strip_label(t)))
            if expr is None:
                continue
            latex = to_latex(expr)
            if expr.has(x):
                if equivalent(expr, fprime, ctx):
                    vb.ok(i, step.kind, "That's f′(x).", latex=latex)
                else:
                    vb.error(
                        i, step.kind, "STEP_NOT_EQUAL_TO_TARGET", "This isn't f′(x).", latex=latex
                    )
                    self.diagnose_expression(
                        vb, problem, ctx, expr, fprime, detectors=rule_detectors(f, x, ctx), step=i
                    )
            elif equivalent(expr, m, ctx):
                vb.ok(i, step.kind, "That's the slope f′(a).", latex=latex)
            elif not is_derivative_label and equivalent(expr, fa, ctx):
                vb.ok(i, step.kind, "That's f(a), the y-coordinate of the point.", latex=latex)
            else:
                vb.error(i, step.kind, "WRONG_VALUE", latex=latex)

        if submission.answer is None or not submission.answer.strip():
            return
        text = submission.answer
        if "=" not in text:
            try:
                value = ctx.parse(text)
            except MathInputError as exc:
                vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
                return
            vb.answer(VerdictStatus.INCORRECT, latex=to_latex(value), code="WRONG")
            if not value.has(x) and equivalent(value, m, ctx):
                vb.hint("SLOPE_ONLY")
            else:
                vb.hint("NOT_A_LINE")
            return
        try:
            student = _parse_line(text, ctx, x, y)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        latex = f"y = {to_latex(student)}"
        if equivalent(student, key, ctx):
            vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
        mistake = self.match_mistake(
            problem,
            student,
            lambda t: _parse_line(t, ctx, x, y),
            lambda s, c: equivalent(s, c, ctx),
        )
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
            return
        slope = sp.diff(student, x)
        if slope.has(x):
            vb.hint("NOT_A_LINE")
            return
        right_slope = bool(equivalent(slope, m, ctx))
        right_point = bool(equivalent(student.subs(x, a), fa, ctx))
        if right_point and not right_slope:
            vb.hint("WRONG_SLOPE")
        elif right_slope and not right_point:
            vb.hint("WRONG_POINT")


# --------------------------------------------------------------------------- implicit


class ImplicitParams(_Params):
    equation: str
    x: str = "x"
    y: str = "y"


def curve_points(
    F: sp.Expr, x: sp.Symbol, y: sp.Symbol, count: int = 12
) -> list[tuple[mpmath.mpf, mpmath.mpf]]:
    """Real points on ``F(x, y) = 0`` (for comparing implicit derivatives on the curve)."""
    rng = random.Random(SEED + 7)
    points: list[tuple[mpmath.mpf, mpmath.mpf]] = []
    for _ in range(60):
        x0 = sp.Float(rng.uniform(-3.5, 3.5), 30)
        g = sp.expand(F.subs(x, x0))
        roots: list[sp.Expr] = []
        try:
            poly = sp.Poly(g, y)
            if poly.degree() >= 1:
                roots = [r for r in poly.nroots(n=30) if abs(sp.im(r)) < 1e-20]
        except (sp.PolynomialError, sp.polys.polyerrors.PolynomialError, Exception):  # noqa: BLE001
            roots = []
            for guess in (-2.0, 0.5, 2.0):
                try:
                    roots.append(sp.nsolve(g, y, guess, prec=30))
                except Exception:  # noqa: BLE001
                    continue
        for r in roots:
            points.append((mpmath.mpf(str(x0)), mpmath.mpf(str(sp.re(r)))))
        if len(points) >= count:
            break
    return points


def equal_on_points(
    a: sp.Expr, b: sp.Expr, syms: list[sp.Symbol], points, tol: float = 1e-8
) -> bool | None:
    fa, fb = compile_numeric(a, syms), compile_numeric(b, syms)
    agree = 0
    with mpmath.workdps(30):
        for pt in points:
            try:
                va, vb_ = mpmath.mpc(fa(*pt)), mpmath.mpc(fb(*pt))
            except Exception:  # noqa: BLE001
                continue
            if not (mpmath.isfinite(va.real) and mpmath.isfinite(vb_.real)):
                continue
            if abs(va - vb_) > tol * max(1, abs(va), abs(vb_)):
                return False
            agree += 1
    return True if agree >= 4 else None


@register
class ImplicitDerivativeHandler(TopicHandler):
    kind = "implicit_derivative"
    Params = ImplicitParams
    syntax_help = "Enter dy/dx as an expression in x and y, e.g. -x/y."

    def setup(self, problem: Problem, p: ImplicitParams):
        ctx = MathContext.build({p.x: "real", p.y: "real"})
        x, y = ctx[p.x], ctx[p.y]
        parts, ops = split_relation(normalize(p.equation))
        if ops != ["="]:
            raise ContentError(f"{problem.id}: equation needs one '='")
        F = ctx.parse(parts[0]) - ctx.parse(parts[1])
        dydx = -sp.diff(F, x) / sp.diff(F, y)
        key = ctx.parse(strip_label(problem.answer))
        return ctx, x, y, F, dydx, key

    def validate(self, problem: Problem, params: ImplicitParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def _same(self, a: sp.Expr, b: sp.Expr, ctx: MathContext, x, y, points) -> bool | None:
        on_curve = equal_on_points(a, b, [x, y], points) if points else None
        if on_curve is not None:
            return on_curve
        return equivalent(a, b, ctx)

    def verify_key(self, problem: Problem, params: ImplicitParams) -> bool | None:
        ctx, x, y, F, dydx, key = self.setup(problem, params)
        return self._same(key, dydx, ctx, x, y, curve_points(F, x, y))

    def check(
        self, problem: Problem, params: ImplicitParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, x, y, F, dydx, key = self.setup(problem, params)
        points = curve_points(F, x, y)

        def same(a: sp.Expr, b: sp.Expr) -> bool | None:
            return self._same(a, b, ctx, x, y, points)

        for i, step in enumerate(submission.steps):
            expr = self.parse_step(vb, i, step, lambda t: ctx.parse(strip_label(t)))
            if expr is None:
                continue
            verdict = same(expr, dydx)
            if verdict:
                vb.ok(i, step.kind, latex=to_latex(expr))
            elif verdict is None:
                vb.step(
                    i, step.kind, StepStatus.UNCHECKED, latex=to_latex(expr), code="UNVERIFIED_STEP"
                )
            else:
                vb.error(i, step.kind, "STEP_NOT_EQUAL_TO_TARGET", latex=to_latex(expr))

        Fx, Fy = sp.diff(F, x), sp.diff(F, y)
        detectors: list[Detector] = []
        for wrong, code in ((-Fy / Fx, "INVERTED_RATIO"), (Fx / Fy, "SIGN_ERROR")):
            detectors.append(
                lambda s, w=wrong, c=code: (c, {}) if same(s, w) else None  # type: ignore[misc]
            )
        self.grade_expression(
            vb, problem, ctx, submission.answer, key, equal=same, detectors=detectors
        )
