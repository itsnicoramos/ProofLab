"""Partial derivatives (SPEC §5.5): ``partial_derivative``, ``gradient``,
``directional_derivative``, ``tangent_plane``."""

from __future__ import annotations

import itertools
import re
from collections.abc import Sequence

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field, model_validator

from prooflab.engine import hints
from prooflab.engine.algebra import (
    MathContext,
    MathInputError,
    contains_float,
    equivalent,
    normalize,
    parse_tuple,
    split_relation,
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
        "WRONG_VARIABLE": "That's a partial derivative with respect to the wrong variable. "
        "Differentiate with respect to {var} and treat the other variables as constants.",
        "NOT_CONSTANT": "While differentiating with respect to {var}, treat every other variable "
        "as a constant.",
        "PARTIAL_INCOMPLETE": "You've differentiated {got} time(s); this problem asks for {want} "
        "partial derivatives in a row.",
        "COMPONENTS_SWAPPED": "The right components are there, but in the wrong order. "
        "The gradient lists ∂f/∂x first, then ∂f/∂y (then ∂f/∂z).",
        "VECTOR_COMPONENT": "Component {component} isn't right; the other components are.",
        "VECTOR_LENGTH": "The answer should be a vector with {n} components.",
        "NOT_EVALUATED_AT_POINT": "That's the general formula. Now evaluate it at the given point "
        "to get a number.",
        "NOT_UNIT_VECTOR": "The directional derivative uses a unit vector. Divide the direction "
        "vector by its length first.",
        "MAX_RATE_INSTEAD": "That's |∇f|, the maximum rate of change, not the rate of change in "
        "the given direction.",
        "PARTIAL_STEP_WRONG": "This isn't one of the partial derivatives of the function.",
        "VALUE_STEP_WRONG": "This value doesn't match the function or its partial derivatives at "
        "the point.",
        "NOT_A_PLANE": "A tangent plane is linear in x, y and z. Evaluate the partial derivatives "
        "at the point to get numbers.",
        "PLANE_WRONG_POINT": "Your plane is tilted correctly but doesn't pass through the point "
        "of tangency.",
        "PLANE_WRONG_NORMAL": "Your plane passes through the point, but its tilt is off. Check the "
        "partial derivatives at the point.",
    }
)

Variables = list[str] | dict[str, str]


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


_SUBSCRIPT_LABEL_RE = re.compile(r"^\s*[A-Za-z]_[A-Za-z]+\s*\(\s*[^()=]*\)\s*=(?!=)")


def strip_partial_label(text: str) -> str:
    """Like :func:`strip_label`, plus subscripted labels with arguments: ``f_x(1, 2) = 4``."""
    stripped = strip_label(text)
    if stripped != text:
        return stripped
    m = _SUBSCRIPT_LABEL_RE.match(text)
    if m and "=" not in text[m.end() :]:
        return text[m.end() :]
    return text


def _names(variables: Variables) -> list[str]:
    return list(variables)


def _detector(ctx: MathContext, candidate: sp.Expr, code: str, **params: object) -> Detector:
    def detect(student: sp.Expr) -> tuple[str, dict[str, object]] | None:
        try:
            same = equivalent(student, candidate, ctx, symbolic_fallback=False)
        except Exception:  # noqa: BLE001
            return None
        return (code, params) if same else None

    return detect


def _content_error(problem: Problem, exc: Exception) -> ContentError:
    return ContentError(f"{problem.id}: {exc}")


# --------------------------------------------------------------------------- vectors


def vector_text(text: str) -> str:
    """Drop a label such as ``∇f =`` or ``grad f =`` in front of a vector."""
    if text.count("=") == 1:
        right = text.split("=", 1)[1]
        if right.strip()[:1] in "<([⟨":
            return right
    return text


def is_vector_text(text: str) -> bool:
    inner = strip_outer(normalize(vector_text(text)))
    return len(split_top(inner, ",")) > 1


def parse_vector(text: str, ctx: MathContext) -> list[sp.Expr]:
    return parse_tuple(vector_text(text), ctx)


def vector_latex(v: Sequence[sp.Expr]) -> str:
    return r"\left\langle " + ", ".join(to_latex(c) for c in v) + r" \right\rangle"


def vectors_equal(u: Sequence[sp.Expr], w: Sequence[sp.Expr], ctx: MathContext) -> bool | None:
    if len(u) != len(w):
        return False
    results = [equivalent(a, b, ctx) for a, b in zip(u, w, strict=True)]
    if any(r is False for r in results):
        return False
    if any(r is None for r in results):
        return None
    return True


class _VectorGrading:
    """Grading for vector answers, shared by gradient-style kinds."""

    def grade_vector(
        self: TopicHandler,
        vb: VerdictBuilder,
        problem: Problem,
        ctx: MathContext,
        text: str | None,
        key: Sequence[sp.Expr],
        *,
        symbolic: Sequence[sp.Expr] | None = None,
        component_detectors: Sequence[Sequence[Detector]] | None = None,
    ) -> None:
        if text is None or not text.strip():
            return
        try:
            v = parse_vector(text, ctx)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        latex = vector_latex(v)
        if len(v) != len(key):
            vb.answer(VerdictStatus.INCORRECT, latex=latex, code="VECTOR_LENGTH", n=len(key))
            vb.hint("VECTOR_LENGTH", n=len(key))
            return
        results = [equivalent(a, b, ctx) for a, b in zip(v, key, strict=True)]
        if all(results):
            if any(contains_float(c) for c in v) and not any(contains_float(c) for c in key):
                vb.answer(VerdictStatus.PARTIAL, latex=latex, code="INEXACT")
                vb.hint("INEXACT")
            else:
                vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
            return
        if not any(r is False for r in results):
            vb.answer(VerdictStatus.INVALID, latex=latex, code="UNVERIFIED")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
        mistake = self.match_mistake(
            problem,
            v,
            lambda t: parse_vector(t, ctx),
            lambda a, b: vectors_equal(a, b, ctx),
        )
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
            return
        if (
            symbolic is not None
            and any(c.free_symbols for c in v)
            and vectors_equal(v, symbolic, ctx)
        ):
            vb.hint("NOT_EVALUATED_AT_POINT")
            return
        n = len(key)
        for perm in itertools.permutations(range(n)):
            if perm == tuple(range(n)):
                continue
            if all(equivalent(v[i], key[perm[i]], ctx) for i in range(n)):
                vb.hint("COMPONENTS_SWAPPED")
                return
        wrong = [i for i, r in enumerate(results) if r is False]
        if len(wrong) < n:
            vb.hint("VECTOR_COMPONENT", component=wrong[0] + 1)
        i = wrong[0]
        detectors = component_detectors[i] if component_detectors else ()
        self.diagnose_expression(vb, problem, ctx, v[i], key[i], detectors=detectors)


def _point(ctx: MathContext, names: Sequence[str], at: Sequence[str]) -> dict[sp.Symbol, sp.Expr]:
    if len(at) != len(names):
        raise ValueError(f"'at' needs {len(names)} coordinates")
    return {ctx[n]: ctx.parse(a) for n, a in zip(names, at, strict=True)}


# --------------------------------------------------------------------------- partials


class PartialParams(_Params):
    function: str
    variables: Variables = ["x", "y"]
    respect: list[str] = Field(min_length=1, max_length=3)


@register
class PartialDerivativeHandler(TopicHandler):
    kind = "partial_derivative"
    Params = PartialParams
    syntax_help = (
        "Enter the partial derivative as an expression, e.g. 2xy + y^3. Labels like f_x = ... "
        "or ∂f/∂x = ... are fine. Each step should be a rewrite of the partial derivative."
    )

    def setup(self, problem: Problem, p: PartialParams):
        ctx = MathContext.build(p.variables)
        names = _names(p.variables)
        if not set(p.respect) <= set(names):
            raise ValueError(f"'respect' must use the problem's variables {names}")
        f = ctx.parse(p.function)
        key = ctx.parse(strip_partial_label(problem.answer))
        return ctx, names, f, key

    def validate(self, problem: Problem, params: PartialParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError, ValueError) as exc:
            raise _content_error(problem, exc) from exc

    def verify_key(self, problem: Problem, params: PartialParams) -> bool | None:
        ctx, names, f, key = self.setup(problem, params)
        return equivalent(sp.diff(f, *[ctx[v] for v in params.respect]), key, ctx)

    def detectors(
        self, ctx: MathContext, names: list[str], f: sp.Expr, respect: list[str]
    ) -> list[Detector]:
        syms = [ctx[n] for n in names]
        wanted = sorted(respect)
        out: list[Detector] = []
        label = ", then ".join(respect)
        for seq in itertools.product(names, repeat=len(respect)):
            if sorted(seq) != wanted:
                out.append(
                    _detector(ctx, sp.diff(f, *[ctx[s] for s in seq]), "WRONG_VARIABLE", var=label)
                )
        if len(respect) == 1:
            total = sp.Add(*[sp.diff(f, s) for s in syms])
            out.append(_detector(ctx, total, "NOT_CONSTANT", var=respect[0]))
        for k in range(1, len(respect)):
            out.append(
                _detector(
                    ctx,
                    sp.diff(f, *[ctx[s] for s in respect[:k]]),
                    "PARTIAL_INCOMPLETE",
                    got=k,
                    want=len(respect),
                )
            )
        return out

    def check(
        self, problem: Problem, params: PartialParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, names, f, key = self.setup(problem, params)
        detectors = self.detectors(ctx, names, f, params.respect)
        # Steps may pass through the intermediate partials in order: f_x, then f_xy, ...
        stages = [
            sp.diff(f, *[ctx[v] for v in params.respect[:k]]) for k in range(1, len(params.respect))
        ]
        stages.append(key)
        current = 0
        for i, step in enumerate(submission.steps):
            expr = self.parse_step(vb, i, step, lambda t: ctx.parse(strip_partial_label(t)))
            if expr is None:
                continue
            latex = to_latex(expr)
            results = [equivalent(expr, stages[k], ctx) for k in range(current, len(stages))]
            hit = next((k for k, r in enumerate(results, start=current) if r), None)
            if hit is not None:
                label = "".join(params.respect[: hit + 1])
                message = None if hit == len(stages) - 1 else f"That's f_{label}."
                vb.ok(i, step.kind, message, latex=latex)
                current = hit
            elif any(r is None for r in results):
                vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
            else:
                vb.error(i, step.kind, "STEP_NOT_EQUAL_TO_TARGET", latex=latex)
                if vb.first_error == i:
                    self.diagnose_expression(
                        vb, problem, ctx, expr, key, detectors=detectors, step=i
                    )
        answer = submission.answer
        if answer is not None:
            answer = strip_partial_label(answer)
        self.grade_expression(vb, problem, ctx, answer, key, detectors=detectors)


# --------------------------------------------------------------------------- gradient


class GradientParams(_Params):
    function: str
    variables: Variables = ["x", "y"]
    at: list[str] | None = None


@register
class GradientHandler(_VectorGrading, TopicHandler):
    kind = "gradient"
    Params = GradientParams
    syntax_help = (
        "Enter the gradient as a vector, e.g. <2x y, x^2> (or (2xy, x^2)). Steps can be "
        "individual partial derivatives (f_x = ...) or the whole vector."
    )

    def setup(self, problem: Problem, p: GradientParams):
        ctx = MathContext.build(p.variables)
        names = _names(p.variables)
        syms = [ctx[n] for n in names]
        f = ctx.parse(p.function)
        grad = [sp.diff(f, s) for s in syms]
        point = _point(ctx, names, p.at) if p.at is not None else None
        at_point = [g.subs(point) for g in grad] if point is not None else None
        key = parse_vector(problem.answer, ctx)
        return ctx, names, syms, f, grad, at_point, key

    def validate(self, problem: Problem, params: GradientParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError, ValueError) as exc:
            raise _content_error(problem, exc) from exc

    def verify_key(self, problem: Problem, params: GradientParams) -> bool | None:
        ctx, names, syms, f, grad, at_point, key = self.setup(problem, params)
        return vectors_equal(key, at_point if at_point is not None else grad, ctx)

    def check(
        self, problem: Problem, params: GradientParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, names, syms, f, grad, at_point, key = self.setup(problem, params)
        for i, step in enumerate(submission.steps):
            if is_vector_text(step.content):
                v = self.parse_step(vb, i, step, lambda t: parse_vector(t, ctx))
                if v is None:
                    continue
                latex = vector_latex(v)
                if vectors_equal(v, grad, ctx):
                    vb.ok(i, step.kind, "That's ∇f.", latex=latex)
                elif at_point is not None and vectors_equal(v, at_point, ctx):
                    vb.ok(i, step.kind, "That's ∇f at the point.", latex=latex)
                else:
                    vb.error(
                        i,
                        step.kind,
                        "STEP_NOT_EQUAL_TO_TARGET",
                        "This isn't the gradient.",
                        latex=latex,
                    )
                continue
            _check_scalar_step(vb, i, step, ctx, grad, at_point or [])
        component_detectors = [
            PartialDerivativeHandler().detectors(ctx, names, f, [n]) if at_point is None else []
            for n in names
        ]
        self.grade_vector(
            vb,
            problem,
            ctx,
            submission.answer,
            key,
            symbolic=grad if at_point is not None else None,
            component_detectors=component_detectors,
        )


def _check_scalar_step(
    vb: VerdictBuilder,
    index: int,
    step,
    ctx: MathContext,
    partials: Sequence[sp.Expr],
    values: Sequence[sp.Expr],
    *,
    extra_ok: Sequence[tuple[sp.Expr, str]] = (),
    lenient: bool = False,
) -> None:
    """A step that should be a partial derivative (formula) or one of its values."""
    expr = TopicHandler.parse_step(vb, index, step, lambda t: ctx.parse(strip_partial_label(t)))
    if expr is None:
        return
    latex = to_latex(expr)
    for candidate, message in extra_ok:
        if equivalent(expr, candidate, ctx):
            vb.ok(index, step.kind, message, latex=latex)
            return
    if expr.free_symbols:
        if any(equivalent(expr, p, ctx) for p in partials):
            vb.ok(index, step.kind, "That's one of the partial derivatives.", latex=latex)
        elif lenient:
            vb.step(index, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
        else:
            vb.error(index, step.kind, "PARTIAL_STEP_WRONG", latex=latex)
        return
    if any(values_equal(expr, v) for v in values):
        vb.ok(index, step.kind, "That value checks out.", latex=latex)
    elif lenient:
        vb.step(index, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
    else:
        vb.error(index, step.kind, "VALUE_STEP_WRONG", latex=latex)


# --------------------------------------------------------------------------- directional


class DirectionalParams(_Params):
    function: str
    variables: Variables = ["x", "y"]
    at: list[str]
    direction: list[str]


@register
class DirectionalDerivativeHandler(TopicHandler):
    kind = "directional_derivative"
    Params = DirectionalParams
    syntax_help = (
        "Enter the directional derivative as an exact number, e.g. 7/sqrt(5). Steps can be "
        "the gradient (a vector), the unit vector, partial derivatives, or numbers."
    )

    def setup(self, problem: Problem, p: DirectionalParams):
        ctx = MathContext.build(p.variables)
        names = _names(p.variables)
        syms = [ctx[n] for n in names]
        f = ctx.parse(p.function)
        point = _point(ctx, names, p.at)
        v = [ctx.parse(c) for c in p.direction]
        if len(v) != len(names):
            raise ValueError(f"'direction' needs {len(names)} components")
        norm = sp.sqrt(sp.Add(*[c**2 for c in v]))
        if norm == 0:
            raise ValueError("direction must be nonzero")
        u = [c / norm for c in v]
        grad = [sp.diff(f, s) for s in syms]
        grad_p = [g.subs(point) for g in grad]
        value = sp.Add(*[g * c for g, c in zip(grad_p, u, strict=True)])
        key = ctx.parse(strip_partial_label(problem.answer))
        return ctx, f, grad, grad_p, v, norm, u, value, key

    def validate(self, problem: Problem, params: DirectionalParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError, ValueError) as exc:
            raise _content_error(problem, exc) from exc

    def verify_key(self, problem: Problem, params: DirectionalParams) -> bool | None:
        ctx, f, grad, grad_p, v, norm, u, value, key = self.setup(problem, params)
        return equivalent(value, key, ctx)

    def check(
        self,
        problem: Problem,
        params: DirectionalParams,
        submission: Submission,
        vb: VerdictBuilder,
    ) -> None:
        ctx, f, grad, grad_p, v, norm, u, value, key = self.setup(problem, params)
        unnormalized = sp.Add(*[g * c for g, c in zip(grad_p, v, strict=True)])
        symbolic = sp.Add(*[g * c for g, c in zip(grad, u, strict=True)])
        vectors = [
            (grad, "That's ∇f."),
            (grad_p, "That's ∇f at the point."),
            (u, "That's the unit vector in the given direction."),
            (v, "That's the direction vector."),
        ]
        for i, step in enumerate(submission.steps):
            if is_vector_text(step.content):
                w = self.parse_step(vb, i, step, lambda t: parse_vector(t, ctx))
                if w is None:
                    continue
                latex = vector_latex(w)
                for candidate, message in vectors:
                    if vectors_equal(w, candidate, ctx):
                        vb.ok(i, step.kind, message, latex=latex)
                        break
                else:
                    vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
                continue
            expr = self.parse_step(vb, i, step, lambda t: ctx.parse(strip_partial_label(t)))
            if expr is None:
                continue
            if (
                not expr.free_symbols
                and values_equal(expr, unnormalized)
                and not values_equal(unnormalized, value)
            ):
                vb.error(i, step.kind, "NOT_UNIT_VECTOR", latex=to_latex(expr))
                continue
            _check_scalar_step(
                vb,
                i,
                step,
                ctx,
                grad,
                [*grad_p, *u, norm],
                extra_ok=[
                    (value, "That's the directional derivative."),
                    (symbolic, "That's ∇f · u."),
                ],
                lenient=True,
            )
        detectors: list[Detector] = []
        if not values_equal(unnormalized, value):
            detectors.append(_detector(ctx, unnormalized, "NOT_UNIT_VECTOR"))
        detectors.append(_detector(ctx, symbolic, "NOT_EVALUATED_AT_POINT"))
        max_rate = sp.sqrt(sp.Add(*[g**2 for g in grad_p]))
        if not values_equal(max_rate, value):
            detectors.append(_detector(ctx, max_rate, "MAX_RATE_INSTEAD"))
        self.grade_expression(
            vb, problem, ctx, submission.answer, key, require_exact=True, detectors=detectors
        )


# --------------------------------------------------------------------------- tangent plane


class TangentPlaneParams(_Params):
    function: str | None = None
    surface: str | None = None
    at: list[str]

    @model_validator(mode="after")
    def _one_kind(self) -> TangentPlaneParams:
        if (self.function is None) == (self.surface is None):
            raise ValueError("give exactly one of 'function' (z = f(x, y)) or 'surface'")
        want = 2 if self.function is not None else 3
        if len(self.at) != want:
            raise ValueError(f"'at' needs {want} coordinates")
        return self


def _plane_coeffs(G: sp.Expr, X: Sequence[sp.Symbol]) -> list[sp.Expr] | None:
    """Coefficients ``[a, b, c, d]`` of ``a x + b y + c z + d``, or ``None`` if not a plane."""
    G = sp.expand(G)
    try:
        poly = sp.Poly(G, *X)
    except sp.PolynomialError:
        return None
    if poly.total_degree() > 1:
        return None
    coeffs = [poly.coeff_monomial(s) for s in X] + [poly.coeff_monomial(1)]
    if any(c.free_symbols for c in coeffs) or all(c == 0 for c in coeffs[:3]):
        return None
    return coeffs


def _proportional(u: Sequence[sp.Expr], w: Sequence[sp.Expr]) -> bool:
    """Is ``u = λ w`` for some nonzero λ?"""
    pivot = next((j for j, c in enumerate(w) if not values_equal(c, 0)), None)
    if pivot is None or values_equal(u[pivot], 0):
        return False
    lam = u[pivot] / w[pivot]
    return all(values_equal(a, lam * b) for a, b in zip(u, w, strict=True))


@register
class TangentPlaneHandler(TopicHandler):
    kind = "tangent_plane"
    Params = TangentPlaneParams
    syntax_help = (
        "Enter the plane as an equation in x, y and z, e.g. z = 2x + 4y - 5. Any equivalent "
        "equation works. Steps can be partial derivatives, their values, or the plane in "
        "another form."
    )

    def setup(self, problem: Problem, p: TangentPlaneParams):
        ctx = MathContext.build(["x", "y", "z"])
        X = [ctx["x"], ctx["y"], ctx["z"]]
        if p.function is not None:
            f = ctx.parse(p.function)
            if f.has(X[2]):
                raise ValueError("'function' should be f(x, y), without z")
            a, b = (ctx.parse(c) for c in p.at)
            pt = {X[0]: a, X[1]: b}
            c = f.subs(pt)
            partials = [sp.diff(f, X[0]), sp.diff(f, X[1])]
            normal = [d.subs(pt) for d in partials] + [sp.Integer(-1)]
            P3 = [a, b, c]
            values = [*normal[:2], c]
        else:
            parts, ops = split_relation(normalize(p.surface or ""))
            if ops != ["="]:
                raise ValueError("'surface' must be an equation")
            F = ctx.parse(parts[0]) - ctx.parse(parts[1])
            P3 = [ctx.parse(c) for c in p.at]
            pt = dict(zip(X, P3, strict=True))
            if not values_equal(F.subs(pt), 0):
                raise ValueError("the point is not on the surface")
            partials = [sp.diff(F, s) for s in X]
            normal = [d.subs(pt) for d in partials]
            values = normal
        if all(values_equal(n, 0) for n in normal):
            raise ValueError("the surface has no tangent plane at that point")
        plane = [*normal, -sp.Add(*[n * q for n, q in zip(normal, P3, strict=True)])]
        key = self.parse_plane(problem.answer, ctx, X)
        if key is None:
            raise ValueError("answer key is not a plane")
        return ctx, X, P3, partials, values, plane, key

    @staticmethod
    def parse_plane(text: str, ctx: MathContext, X) -> list[sp.Expr] | None:
        parts, ops = split_relation(normalize(text))
        if ops != ["="]:
            raise MathInputError(
                "Write the plane as an equation, like z = 2x + 4y - 5.", "NOT_AN_EQUATION"
            )
        G = ctx.parse(parts[0]) - ctx.parse(parts[1])
        return _plane_coeffs(G, X)

    def validate(self, problem: Problem, params: TangentPlaneParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError, ValueError) as exc:
            raise _content_error(problem, exc) from exc

    def verify_key(self, problem: Problem, params: TangentPlaneParams) -> bool | None:
        ctx, X, P3, partials, values, plane, key = self.setup(problem, params)
        return _proportional(key, plane)

    def _plane_step(self, text: str, ctx: MathContext, X) -> bool:
        """Is this step an equation of a plane (rather than a labelled value like f_x = 2x)?"""
        parts, ops = split_relation(normalize(text))
        if ops != ["="]:
            return False
        try:
            G = ctx.parse(parts[0]) - ctx.parse(parts[1])
        except MathInputError:
            return False
        return G.has(X[2])

    def check(
        self,
        problem: Problem,
        params: TangentPlaneParams,
        submission: Submission,
        vb: VerdictBuilder,
    ) -> None:
        ctx, X, P3, partials, values, plane, key = self.setup(problem, params)
        for i, step in enumerate(submission.steps):
            if self._plane_step(step.content, ctx, X):
                coeffs = self.parse_step(vb, i, step, lambda t: self.parse_plane(t, ctx, X))
                if coeffs is None:
                    vb.error(i, step.kind, "NOT_A_PLANE")
                elif _proportional(coeffs, plane):
                    vb.ok(i, step.kind, "That's the tangent plane.")
                else:
                    vb.error(
                        i, step.kind, "STEP_NOT_EQUAL_TO_TARGET", "This isn't the tangent plane."
                    )
                continue
            _check_scalar_step(vb, i, step, ctx, partials, values)

        text = submission.answer
        if text is None or not text.strip():
            return
        try:
            parts, ops = split_relation(normalize(text))
            if ops != ["="]:
                raise MathInputError(
                    "Write the plane as an equation, like z = 2x + 4y - 5.", "NOT_AN_EQUATION"
                )
            G = ctx.parse(parts[0]) - ctx.parse(parts[1])
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        latex = f"{to_latex(ctx.parse(parts[0]))} = {to_latex(ctx.parse(parts[1]))}"
        coeffs = _plane_coeffs(G, X)
        if coeffs is None:
            vb.answer(VerdictStatus.INCORRECT, latex=latex, code="NOT_A_PLANE")
            vb.hint("NOT_A_PLANE")
            return
        if _proportional(coeffs, plane):
            vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
        mistake = self.match_mistake(
            problem,
            coeffs,
            lambda t: self.parse_plane(t, ctx, X),
            lambda a, b: b is not None and _proportional(a, b),
        )
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
            return
        through_point = values_equal(G.subs(dict(zip(X, P3, strict=True))), 0)
        if _proportional(coeffs[:3], plane[:3]):
            vb.hint("PLANE_WRONG_POINT")
        elif through_point:
            vb.hint("PLANE_WRONG_NORMAL")
