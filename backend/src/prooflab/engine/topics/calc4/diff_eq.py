"""Ordinary differential equations (SPEC §5.6): the ``ode_solution`` kind.

Every candidate solution is checked by substitution, never by re-solving the equation:

- explicit ``y = g(x, C…)``: the residual of the ODE must vanish for all x and all constants;
- implicit ``F(x, y, C) = 0`` (first order): with dy/dx = −F_x/F_y and C solved from F = 0 at
  each point, the residual must vanish for all (x, y);
- general solutions need ``order`` independent constants (rank of the Jacobian of
  ``[y, y′, …, y^(n−1)]`` with respect to the constants);
- initial value problems must satisfy every initial condition.
"""

from __future__ import annotations

import random
import re
from collections.abc import Sequence
from dataclasses import dataclass

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
    match_values,
    normalize,
    numeric_value,
    parse_value_list,
    split_relation,
    to_latex,
    values_equal,
)
from prooflab.engine.checker import ContentError, TopicHandler, VerdictBuilder, register
from prooflab.engine.models import Problem, StepStatus, Submission, VerdictStatus
from prooflab.engine.topics.calc1.derivatives import curve_points, equal_on_points

hints.register_many(
    {
        "NOT_A_SOLUTION": "Substitute your y into the differential equation: it doesn't satisfy "
        "it.",
        "NOT_GENERAL": "A general solution of an order-{order} equation needs {order} arbitrary "
        "constant(s). Yours has {count}.",
        "DEPENDENT_SOLUTIONS": "Your constants aren't independent: the solution doesn't contain "
        "{order} genuinely different pieces. (For a repeated root r of the characteristic "
        "equation, the second solution is x·e^(rx).)",
        "IC_NOT_SATISFIED": "Your solution satisfies the equation but not the initial condition "
        "{condition}.",
        "CONSTANTS_LEFT": "This is an initial value problem: use the initial conditions to find "
        "the value of each constant.",
        "MISSING_PARTICULAR": "Your y solves the homogeneous equation, but the right-hand side "
        "isn't zero. Add a particular solution y_p.",
        "ROOT_SIGNS": "The signs in your exponents look flipped. Check the roots of the "
        "characteristic equation.",
        "HOMOGENEOUS_ONLY": "That solves the homogeneous equation (the right-hand side set to 0).",
        "CHARACTERISTIC_EQUATION": "That isn't the characteristic equation of this ODE. Replace "
        "y⁽ᵏ⁾ by rᵏ.",
        "CHARACTERISTIC_ROOTS": "Those aren't the roots of the characteristic equation.",
        "NO_CHARACTERISTIC": "This equation doesn't have constant coefficients, so there's no "
        "characteristic equation to check.",
        "IMPLICIT_ORDER": "For this equation, write the solution explicitly as y = ...",
        "NOTE_STEP": "Notes aren't checked.",
    }
)

CONSTANT_NAMES = ("C", "C1", "C2", "C3", "A", "B", "K")
_MAX_ORDER = 4


class ODEParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ode: str
    func: str = Field(default="y", pattern=r"^[a-z]$")
    var: str = Field(default="x", pattern=r"^[a-z]$")
    ics: dict[str, str] = Field(default_factory=dict)
    variables: dict[str, str] | None = None


def _deriv_name(func: str, k: int) -> str:
    return f"{func}d{k}"


def prepare_ode_text(text: str, func: str, var: str) -> str:
    """``y'' - 3y' + 2y = 0`` → ``yd2 - 3 yd1 + 2y = 0`` (internal derivative names)."""
    s = normalize(text)
    s = re.sub(
        rf"d\^?([1-4])\s*{func}\s*/\s*d\s*{var}\s*\^?\1", lambda m: f" {func}d{m.group(1)} ", s
    )
    s = re.sub(rf"d\s*{func}\s*/\s*d\s*{var}", f" {func}d1 ", s)
    s = re.sub(rf"{func}('{{1,4}})", lambda m: f" {_deriv_name(func, len(m.group(1)))} ", s)
    s = re.sub(rf"{func}\s*\(\s*{var}\s*\)", f" {func} ", s)
    return s


@dataclass
class ODESetup:
    ctx: MathContext  # x, y and the allowed constants (answers)
    x: sp.Symbol
    y: sp.Symbol
    dsym: list[sp.Symbol]  # [y, y', y'', ...] as symbols
    E: sp.Expr  # residual lhs - rhs in terms of dsym and x
    order: int
    ics: list[tuple[int, sp.Expr, sp.Expr, str]]  # (derivative order, x0, value, label)
    constants: list[sp.Symbol]
    key: tuple[str, sp.Expr]

    @property
    def general(self) -> bool:
        return not self.ics

    @property
    def forcing(self) -> sp.Expr:
        return self.E.subs({s: 0 for s in self.dsym}, simultaneous=True)

    @property
    def linear(self) -> bool:
        return all(sp.diff(self.E, a, b) == 0 for a in self.dsym for b in self.dsym)

    def characteristic(self, r: sp.Symbol) -> sp.Expr | None:
        if not self.linear:
            return None
        coeffs = [sp.diff(self.E, s) for s in self.dsym]
        if any(c.has(self.x) for c in coeffs):
            return None
        return sp.expand(sp.Add(*(c * r**k for k, c in enumerate(coeffs))))


# --------------------------------------------------------------------------- parsing


_FUNC_ABS_RE = re.compile(r"\b(ln|log|sqrt|exp)\s*\|([^|]+)\|")


def wrap_abs_arguments(text: str) -> str:
    """``ln|y|`` → ``ln(|y|)`` (the shared parser needs parentheses around bars)."""
    return _FUNC_ABS_RE.sub(r"\1(|\2|)", text)


def parse_solution(text: str, s: ODESetup) -> tuple[str, sp.Expr]:
    """``("explicit", g)`` for ``y = g`` or ``("implicit", F)`` for ``F(x, y) = 0``."""
    func, var = str(s.y), str(s.x)
    t = wrap_abs_arguments(normalize(text))
    t = re.sub(rf"{func}\s*\(\s*{var}\s*\)", func, t)
    label = re.match(rf"^\s*{func}(?:_[a-z])?\s*=(?!=)(.*)$", t)
    if label:
        rhs = s.ctx.parse(label.group(1))
        if not rhs.has(s.y):
            return ("explicit", rhs)
        F = s.y - rhs
    else:
        parts, ops = split_relation(t)
        if not ops:
            expr = s.ctx.parse(t)
            if expr.has(s.y):
                raise MathInputError(f"Write your answer as {func} = ...", "NOT_AN_EQUATION")
            return ("explicit", expr)
        if ops != ["="]:
            raise MathInputError(
                "Write the solution as an equation with one '='.", "NOT_AN_EQUATION"
            )
        F = s.ctx.parse(parts[0]) - s.ctx.parse(parts[1])
        if not F.has(s.y):
            raise MathInputError(f"Your equation needs to involve {func}.", "NOT_AN_EQUATION")
    if s.order > 1:
        raise MathInputError(hints.message("IMPLICIT_ORDER"), "IMPLICIT_ORDER")
    return ("implicit", F)


def _parse_ics(
    raw: dict[str, str], func: str, ctx: MathContext
) -> list[tuple[int, sp.Expr, sp.Expr, str]]:
    out = []
    for cond, value in raw.items():
        m = re.fullmatch(rf"\s*{func}('*)\s*\((.+)\)\s*", normalize(cond))
        if not m:
            raise ContentError(f"bad initial condition {cond!r}")
        x0, v = ctx.parse(m.group(2)), ctx.parse(value)
        if x0.free_symbols or v.free_symbols:
            raise ContentError(f"initial condition {cond!r} must use numbers")
        out.append((len(m.group(1)), x0, v, f"{cond.strip()} = {value.strip()}"))
    return out


# --------------------------------------------------------------------------- checks


def constants_in(expr: sp.Expr, s: ODESetup) -> list[sp.Symbol]:
    return sorted(expr.free_symbols & set(s.constants), key=str)


def explicit_residual(g: sp.Expr, s: ODESetup, E: sp.Expr | None = None) -> sp.Expr:
    E = s.E if E is None else E
    derivs = [g] + [sp.diff(g, s.x, k) for k in range(1, len(s.dsym))]
    return E.subs(dict(zip(s.dsym, derivs, strict=True)), simultaneous=True)


def explicit_solves(g: sp.Expr, s: ODESetup, E: sp.Expr | None = None) -> bool | None:
    return equivalent(explicit_residual(g, s, E), 0, s.ctx)


def implicit_solves(F: sp.Expr, s: ODESetup, E: sp.Expr | None = None) -> bool | None:
    E = s.E if E is None else E
    x, y = s.x, s.y
    Fy = sp.diff(F, y)
    if Fy == 0:
        return False
    R = E.subs({s.dsym[0]: y, s.dsym[1]: -sp.diff(F, x) / Fy}, simultaneous=True)
    consts = constants_in(F, s)
    for c in consts:
        a = sp.diff(F, c)
        if a.has(c) or a == 0:
            continue
        c_value = -sp.expand(F - a * c) / a
        return equivalent(R.subs(c, c_value), 0, s.ctx)
    if consts:
        return None
    points = curve_points(F, x, y)
    if not points:
        return None
    return equal_on_points(R, sp.Integer(0), [x, y], points)


def solves(kind: str, expr: sp.Expr, s: ODESetup, E: sp.Expr | None = None) -> bool | None:
    return explicit_solves(expr, s, E) if kind == "explicit" else implicit_solves(expr, s, E)


def independent_rank(g: sp.Expr, s: ODESetup, consts: Sequence[sp.Symbol]) -> int:
    """Rank of ∂(y, y′, …, y^(n−1))/∂(C1, …, Cm) at a few sample points (max over points)."""
    if not consts:
        return 0
    rows = [[sp.diff(sp.diff(g, s.x, i), c) for c in consts] for i in range(s.order)]
    syms = [s.x, *consts]
    fns = [[compile_numeric(e, syms) for e in row] for row in rows]
    rng = random.Random(SEED + 11)
    best = 0
    with mpmath.workdps(30):
        for _ in range(8):
            point = [s.ctx.spec(sym).sample(rng) for sym in syms]
            try:
                M = mpmath.matrix([[mpmath.mpf(mpmath.re(f(*point))) for f in row] for row in fns])
                sv = mpmath.svd_r(M, compute_uv=False)
            except Exception:  # noqa: BLE001
                continue
            values = [abs(v) for v in sv]
            top = max(values) if values else 0
            if top == 0:
                continue
            best = max(best, sum(1 for v in values if v > top * mpmath.mpf("1e-12")))
            if best >= s.order:
                break
    return best


def failing_ics(kind: str, expr: sp.Expr, s: ODESetup) -> list[str] | None:
    """Labels of the initial conditions the solution misses (``None`` = can't evaluate)."""
    failing = []
    for k, x0, value, label in s.ics:
        if kind == "explicit":
            at_x0 = sp.diff(expr, s.x, k).subs(s.x, x0)
            if numeric_value(at_x0) is None:
                return None
            if not values_equal(at_x0, value, tol=1e-9):
                failing.append(label)
        else:
            if k != 0:
                continue
            residual = numeric_value(expr.subs({s.x: x0, s.y: value}, simultaneous=True))
            if residual is None:
                return None
            if abs(residual) > 1e-9:
                failing.append(label)
    return failing


def solution_latex(kind: str, expr: sp.Expr, s: ODESetup) -> str:
    if kind == "explicit":
        return f"{s.y} = {to_latex(expr)}"
    return f"{to_latex(expr)} = 0"


def reflected(E: sp.Expr, dsym: Sequence[sp.Symbol]) -> sp.Expr:
    """The equation with odd derivatives negated (characteristic roots r → −r)."""
    return E.subs({d: (-1) ** k * d for k, d in enumerate(dsym)}, simultaneous=True)


# --------------------------------------------------------------------------- handler


@dataclass
class _Outcome:
    status: VerdictStatus
    code: str
    params: dict[str, object]


@register
class ODESolutionHandler(TopicHandler):
    kind = "ode_solution"
    Params = ODEParams
    step_kinds = frozenset({"expr", "characteristic", "roots", "note"})
    syntax_help = (
        "Enter y = ... (for first-order equations an implicit relation like y^2 = x^2 + C also "
        "works). Use C, C1, C2, A, B or K for arbitrary constants. Steps: 'expr' for a candidate "
        "solution (y_h = ..., y_p = ... are fine), 'characteristic' for r^2 - 3r + 2 = 0, "
        "'roots' for r = 1, 2 (complex: r = -1 ± 2i), 'note' for anything else."
    )

    def setup(self, problem: Problem, p: ODEParams) -> ODESetup:
        spec = (p.variables or {}).get(p.var, "real")
        names = {p.var: spec, p.func: "real"}
        deriv_names = {_deriv_name(p.func, k): "real" for k in range(1, _MAX_ORDER + 1)}
        try:
            ode_ctx = MathContext.build({**names, **deriv_names})
            parts, ops = split_relation(prepare_ode_text(p.ode, p.func, p.var))
            if ops != ["="]:
                raise ContentError(f"{problem.id}: the ODE needs exactly one '='")
            E = ode_ctx.parse(parts[0]) - ode_ctx.parse(parts[1])
            dsym = [ode_ctx[p.func]] + [
                ode_ctx[_deriv_name(p.func, k)] for k in range(1, _MAX_ORDER + 1)
            ]
            order = max((k for k in range(1, _MAX_ORDER + 1) if E.has(dsym[k])), default=0)
            if order == 0:
                raise ContentError(f"{problem.id}: the ODE has no derivative of {p.func}")
            ctx = MathContext.build(names, constants=CONSTANT_NAMES)
            ics = _parse_ics(p.ics, p.func, ctx)
        except MathInputError as exc:
            raise ContentError(f"{problem.id}: {exc.message}") from exc
        if ics and len(ics) != order:
            raise ContentError(
                f"{problem.id}: an order-{order} IVP needs {order} initial conditions"
            )
        s = ODESetup(
            ctx=ctx,
            x=ctx[p.var],
            y=ctx[p.func],
            dsym=dsym[: order + 1],
            E=E,
            order=order,
            ics=ics,
            constants=[ctx[c] for c in CONSTANT_NAMES],
            key=("explicit", sp.Integer(0)),
        )
        try:
            s.key = parse_solution(problem.answer, s)
        except MathInputError as exc:
            raise ContentError(f"{problem.id}: bad answer key: {exc.message}") from exc
        return s

    def validate(self, problem: Problem, params: ODEParams) -> None:
        self.setup(problem, params)

    # -- grading core (shared by answers and verify_key)
    def evaluate(self, kind: str, expr: sp.Expr, s: ODESetup) -> _Outcome:
        ok = solves(kind, expr, s)
        if ok is None:
            return _Outcome(VerdictStatus.INVALID, "UNVERIFIED", {})
        if not ok:
            return _Outcome(VerdictStatus.INCORRECT, "NOT_A_SOLUTION", {})
        consts = constants_in(expr, s)
        if s.general:
            if len(consts) < s.order:
                return _Outcome(
                    VerdictStatus.PARTIAL, "NOT_GENERAL", {"order": s.order, "count": len(consts)}
                )
            if kind == "explicit" and independent_rank(expr, s, consts) < s.order:
                return _Outcome(VerdictStatus.PARTIAL, "DEPENDENT_SOLUTIONS", {"order": s.order})
            return _Outcome(VerdictStatus.CORRECT, "CORRECT", {})
        if consts:
            return _Outcome(VerdictStatus.PARTIAL, "CONSTANTS_LEFT", {})
        failing = failing_ics(kind, expr, s)
        if failing is None:
            return _Outcome(VerdictStatus.INVALID, "UNVERIFIED", {})
        if failing:
            return _Outcome(VerdictStatus.INCORRECT, "IC_NOT_SATISFIED", {"condition": failing[0]})
        return _Outcome(VerdictStatus.CORRECT, "CORRECT", {})

    def verify_key(self, problem: Problem, params: ODEParams) -> bool | None:
        s = self.setup(problem, params)
        kind, expr = s.key
        outcome = self.evaluate(kind, expr, s)
        if outcome.code == "UNVERIFIED":
            return None
        return outcome.status is VerdictStatus.CORRECT

    # -- steps
    def _check_steps(self, s: ODESetup, submission: Submission, vb: VerdictBuilder) -> None:
        r = sp.Symbol("r")
        rctx = MathContext.build(["r", "i"])
        imag = rctx["i"]
        char_key = s.characteristic(r)
        for i, step in enumerate(submission.steps):
            if step.kind == "note":
                vb.step(i, step.kind, StepStatus.UNCHECKED, code="NOTE_STEP")
                continue
            if step.kind in ("characteristic", "roots"):
                if char_key is None:
                    vb.step(i, step.kind, StepStatus.UNCHECKED, code="NO_CHARACTERISTIC")
                    continue
                if step.kind == "characteristic":
                    self._check_characteristic(i, step, rctx, char_key, vb)
                else:
                    self._check_roots(i, step, rctx, imag, char_key, vb)
                continue
            parsed = self.parse_step(vb, i, step, lambda t: parse_solution(t, s))
            if parsed is None:
                continue
            kind, expr = parsed
            latex = solution_latex(kind, expr, s)
            full = solves(kind, expr, s)
            if full:
                vb.ok(i, step.kind, "This satisfies the differential equation.", latex=latex)
                continue
            forcing = s.forcing
            if s.linear and forcing != 0 and solves(kind, expr, s, s.E - forcing):
                vb.ok(i, step.kind, latex=latex, code="HOMOGENEOUS_ONLY")
            elif full is None:
                vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
            else:
                vb.error(i, step.kind, "NOT_A_SOLUTION", latex=latex)

    def _check_characteristic(
        self, i, step, rctx: MathContext, key: sp.Expr, vb: VerdictBuilder
    ) -> None:
        r = sp.Symbol("r")
        try:
            parts, ops = split_relation(normalize(step.content))
            if ops == ["="]:
                expr = rctx.parse(parts[0]) - rctx.parse(parts[1])
            elif not ops:
                expr = rctx.parse(step.content)
            else:
                raise MathInputError("Write the characteristic equation with one '='.")
        except MathInputError as exc:
            vb.step(i, step.kind, StepStatus.ERROR, exc.message, code="PARSE_ERROR")
            return
        expr = sp.expand(expr.subs(rctx["r"], r))
        latex = to_latex(expr) + " = 0"
        try:
            ps, pk = sp.Poly(expr, r), sp.Poly(key, r)
            same = (
                ps.degree() == pk.degree()
                and sp.expand(ps.as_expr() * pk.LC() - pk.as_expr() * ps.LC()) == 0
            )
        except sp.PolynomialError:
            same = False
        if same:
            vb.ok(i, step.kind, "That's the characteristic equation.", latex=latex)
        else:
            vb.error(i, step.kind, "CHARACTERISTIC_EQUATION", latex=latex)

    def _check_roots(
        self, i, step, rctx: MathContext, imag, key: sp.Expr, vb: VerdictBuilder
    ) -> None:
        r = sp.Symbol("r")
        text = normalize(step.content).replace("+/-", "±").replace("+-", "±")
        pieces = []
        for part in re.split(r",|\bor\b|\band\b", text):
            if "±" in part:
                pieces += [part.replace("±", "+", 1), part.replace("±", "-", 1)]
            elif part.strip():
                pieces.append(part)
        try:
            values = parse_value_list(", ".join(pieces), rctx, rctx["r"])
        except MathInputError as exc:
            vb.step(i, step.kind, StepStatus.ERROR, exc.message, code="PARSE_ERROR")
            return
        values = [v.subs(imag, sp.I) for v in values]
        roots = list(sp.roots(sp.Poly(key, r)).keys())
        latex = r",\ ".join(to_latex(v) for v in values)
        missing, extra = match_values(values, roots)
        if not missing and not extra:
            vb.ok(i, step.kind, "Those are the roots of the characteristic equation.", latex=latex)
        else:
            vb.error(i, step.kind, "CHARACTERISTIC_ROOTS", latex=latex)

    # -- answer
    def check(
        self, problem: Problem, params: ODEParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        s = self.setup(problem, params)
        self._check_steps(s, submission, vb)
        text = submission.answer
        if text is None or not text.strip():
            return
        try:
            kind, expr = parse_solution(text, s)
        except MathInputError as exc:
            code = exc.code if hints.is_registered(exc.code) else "PARSE_ERROR"
            vb.answer(VerdictStatus.INVALID, exc.message, code=code)
            return
        latex = solution_latex(kind, expr, s)
        outcome = self.evaluate(kind, expr, s)
        vb.answer(outcome.status, latex=latex, code=outcome.code, **outcome.params)
        if outcome.status is VerdictStatus.CORRECT:
            return
        if outcome.code != "NOT_A_SOLUTION":
            vb.hint(outcome.code, **outcome.params)
            return
        if kind == "explicit":
            mistake = self.match_mistake(
                problem,
                expr,
                lambda t: parse_solution(t, s)[1],
                lambda a, b: equivalent(a, b, s.ctx),
            )
            if mistake is not None:
                vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
                return
        forcing = s.forcing
        if s.linear and forcing != 0 and solves(kind, expr, s, s.E - forcing):
            vb.hint("MISSING_PARTICULAR")
            return
        if kind == "explicit" and s.order >= 2 and s.characteristic(sp.Symbol("r")) is not None:
            if explicit_solves(expr, s, reflected(s.E, s.dsym)):
                vb.hint("ROOT_SIGNS")
                return
        vb.hint("NOT_A_SOLUTION")
