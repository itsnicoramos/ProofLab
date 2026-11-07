"""Trigonometry (SPEC §5.2): ``trig_identity`` and ``trig_equation``.

Exact trig values use the ``expression`` kind (functions.py) with ``form: exact`` and
``forbid: ["sin", "cos", ...]``.
"""

from __future__ import annotations

import sympy as sp
from pydantic import BaseModel, ConfigDict

from prooflab.engine import hints
from prooflab.engine.algebra import (
    MathContext,
    MathInputError,
    equivalent,
    relation,
    strip_label,
    to_latex,
)
from prooflab.engine.checker import ContentError, TopicHandler, VerdictBuilder, register
from prooflab.engine.models import Problem, StepStatus, Submission, VerdictStatus
from prooflab.engine.topics.precalc.exp_log import EquationParams, SolveHandler

hints.register_many(
    {
        "IDENTITY_INCOMPLETE": "Every step is valid, but you haven't reached the other side yet. "
        "Keep going until a step is the right-hand side.",
        "IDENTITY_NO_WORK": "Show the intermediate steps: which identities take you from one side "
        "to the other?",
        "IDENTITY_UNVERIFIED": "ProofLab couldn't verify every step, so it can't confirm the "
        "proof.",
        "DEGREES_NOT_RADIANS": "Those look like degrees. Give the solutions in radians.",
    }
)


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- identity


class IdentityParams(_Params):
    lhs: str
    rhs: str
    var: str = "x"


def _in_sin_cos(expr: sp.Expr) -> sp.Expr:
    """Rewrite tan, cot, sec, csc by their definitions (no other identities)."""
    return (
        expr.replace(sp.tan, lambda a: sp.sin(a) / sp.cos(a))
        .replace(sp.cot, lambda a: sp.cos(a) / sp.sin(a))
        .replace(sp.sec, lambda a: 1 / sp.cos(a))
        .replace(sp.csc, lambda a: 1 / sp.sin(a))
    )


def reaches(step: sp.Expr, side: sp.Expr) -> bool:
    """Is ``step`` the target side, up to rational algebra and the definitions of tan/sec/…?

    sin(x), cos(x), cos(2x), … are treated as independent symbols here, so the student still
    has to apply the real identities (Pythagorean, double-angle, …) to get there.
    """
    if step == side:
        return True
    try:
        diff = sp.together(_in_sin_cos(step) - _in_sin_cos(side))
        return sp.cancel(diff) == 0 or sp.expand(diff) == 0
    except Exception:  # noqa: BLE001
        return False


@register
class TrigIdentityHandler(TopicHandler):
    kind = "trig_identity"
    Params = IdentityParams
    syntax_help = (
        "Prove the identity with steps only (no final answer). Start from one side; each step "
        "must equal the previous one; the last step must be the other side."
    )

    def has_answer(self, problem: Problem, params: IdentityParams) -> bool:
        return False

    def setup(self, problem: Problem, p: IdentityParams):
        ctx = MathContext.build({p.var: "real"})
        return ctx, ctx.parse(p.lhs), ctx.parse(p.rhs)

    def validate(self, problem: Problem, params: IdentityParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def verify_key(self, problem: Problem, params: IdentityParams) -> bool | None:
        ctx, lhs, rhs = self.setup(problem, params)
        if reaches(lhs, rhs):
            return False  # nothing to prove
        numeric = equivalent(lhs, rhs, ctx, symbolic_fallback=False)
        if numeric is False:
            return False
        symbolic = sp.simplify(sp.trigsimp(lhs - rhs)) == 0
        return True if numeric and symbolic else (numeric or None)

    def check(
        self, problem: Problem, params: IdentityParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, lhs, rhs = self.setup(problem, params)
        if not submission.steps:
            vb.hint("EMPTY_SUBMISSION")
            vb.set_status(VerdictStatus.INCORRECT)
            return
        parsed: list[sp.Expr] = []
        prev = lhs
        unchecked = False
        for i, step in enumerate(submission.steps):
            expr = self.parse_step(vb, i, step, lambda t: ctx.parse(strip_label(t)))
            if expr is None:
                continue
            latex = to_latex(expr)
            same = equivalent(expr, prev, ctx)
            if same:
                vb.ok(i, step.kind, latex=latex)
            elif same is None:
                unchecked = True
                vb.step(i, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
            else:
                vb.error(i, step.kind, "NOT_EQUIVALENT", latex=latex)
                if relation(expr, prev, ctx) == ("negated", None):
                    vb.hint("SIGN_ERROR", step=i)
            parsed.append(expr)
            prev = expr

        if vb.first_error is not None:
            vb.set_status(VerdictStatus.INCORRECT)
            return
        if unchecked:
            vb.hint("IDENTITY_UNVERIFIED")
            vb.set_status(VerdictStatus.PARTIAL)
            return
        last = parsed[-1]
        forwards = reaches(last, rhs)
        backwards = reaches(parsed[0], rhs) and reaches(last, lhs) and len(parsed) > 1
        if not (forwards or backwards):
            vb.hint("IDENTITY_INCOMPLETE")
            vb.set_status(VerdictStatus.PARTIAL)
        elif len(parsed) < 2:
            vb.hint("IDENTITY_NO_WORK")
            vb.set_status(VerdictStatus.PARTIAL)
        else:
            vb.set_status(VerdictStatus.CORRECT)


# --------------------------------------------------------------------------- equation


class TrigEquationParams(EquationParams):
    interval: str | None = "[0, 2pi)"


@register
class TrigEquationHandler(SolveHandler):
    kind = "trig_equation"
    Params = TrigEquationParams
    default_interval = "[0, 2pi)"
    check_degrees = True
    syntax_help = (
        "Enter every solution in the interval, in radians, like x = pi/6 or x = 5pi/6 "
        "(or {pi/6, 5pi/6}). Each step is an equation, e.g. (2sin x - 1)(sin x + 1) = 0."
    )
