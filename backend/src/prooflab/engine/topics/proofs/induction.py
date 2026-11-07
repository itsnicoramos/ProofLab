"""Mathematical induction (SPEC §5.1, Book of Proof Chapter 10): ``induction``.

Two kinds of statement, both "for every integer n ≥ base":

- a sum formula, Σ_{i=start}^{n} term(i) = rhs(n) (``sum``), and
- a divisibility statement, d | f(n) (``divides``).

A proof is a list of steps:

- ``base``    the base case with numbers only: ``1 = 1(1 + 1)/2``, ``5^0 - 1 = 0 = 24·0``
- ``assume``  the inductive hypothesis for n = k: ``1 + 2 + ⋯ + k = k(k + 1)/2`` (only the right
              side is read, so the sum may use dots), or ``k^3 + 5k + 6 = 3m`` (m is new)
- ``expr``    the inductive step, a chain of expressions each equal to the n = k + 1 case.
              For a sum, one of them must *use* the hypothesis: the sum up to k replaced by
              rhs(k), plus the next term, like ``k(k + 1)/2 + (k + 1)``. For divisibility, they
              may use m (it stands for f(k)/d).
- ``witness`` (divisibility) the integer w with f(k + 1) = d·w, like ``25m + 1``
- ``note``    free text, never checked

Every check is exact algebra on the student's own expressions; nothing is guessed.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field, model_validator

from prooflab.engine import hints
from prooflab.engine.algebra import (
    MathContext,
    MathInputError,
    equivalent,
    is_integer_valued_polynomial,
    normalize,
    split_relation,
    to_latex,
)
from prooflab.engine.checker import ContentError, TopicHandler, VerdictBuilder, register
from prooflab.engine.models import Problem, StepStatus, Submission, VerdictStatus

hints.register_many(
    {
        "IND_BASE_OK": "Base case: for $n = {base}$, {detail}.",
        "IND_BASE_NUMBERS": "The base case is about one number: put $n = {base}$ in and write "
        "only numbers, like ${example}$.",
        "IND_BASE_UNEQUAL": "The parts of this line aren't equal: they work out to {values}.",
        "IND_BASE_WRONG": "For $n = {base}$ the statement is about ${value}$, but this line works "
        "out to ${got}$.",
        "IND_ASSUME_OK": "Inductive hypothesis: the statement holds for $n = k$.",
        "IND_ASSUME_FORMAT": "Write the hypothesis for n = k as an equation, like ${example}$.",
        "IND_ASSUME_WRONG": "The hypothesis is the statement with n replaced by k: its right side "
        "is ${rhs}$.",
        "IND_ASSUME_USE_K": "Write the hypothesis with k (the statement for n = k), not n.",
        "IND_ASSUME_DIVIDES": "Write it as ${target} = {d}m$: m is a new integer.",
        "IND_STEP_OK": "Equal to the n = k + 1 case.",
        "IND_STEP_USES_HYPOTHESIS": "Uses the hypothesis: the sum up to $k$ is ${rhs}$, plus the "
        "next term ${term}$.",
        "IND_STEP_WRONG": "This isn't equal to the n = k + 1 case. Check your algebra.",
        "IND_NO_HYPOTHESIS_YET": "Write the inductive hypothesis (an assume step) before using m.",
        "IND_WITNESS_OK": "${target} = {form}$ with ${w}$ an integer, so it is divisible by ${d}$.",
        "IND_WITNESS_WRONG": "With this witness, ${d}$ times it isn't ${target}$. Check your "
        "algebra.",
        "IND_WITNESS_NOT_INTEGER": "ProofLab can't confirm this witness is always an integer. "
        "Write it as a polynomial in k and m that is an integer for every integer k and m.",
        "IND_NEED_BASE": "Add the base case: check the statement for $n = {base}$.",
        "IND_NEED_HYPOTHESIS": "Add the inductive hypothesis: assume the statement for $n = k$.",
        "IND_USE_HYPOTHESIS": "In the inductive step, use the hypothesis: write the sum up to "
        "k + 1 "
        "as ${rhs}$ plus the next term ${term}$.",
        "IND_FINISH_SUM": "Now simplify until you reach the formula for n = k + 1: ${rhs}$.",
        "IND_FINISH_DIVIDES": "Finish with a witness step: the integer w with ${target} = {d}w$.",
        "IND_PROVED_SUM": "Proof complete: the formula holds for $n = {base}$, and whenever it "
        "holds for $k$ it holds for $k + 1$. By induction it holds for every $n \\ge {base}$. ∎",
        "IND_PROVED_DIVIDES": "Proof complete: ${d}$ divides ${target}$ for $n = {base}$, and "
        "whenever it does for $k$ it does for $k + 1$. By induction it holds for every "
        "$n \\ge {base}$. ∎",
        "IND_NOTE": "Notes aren't checked.",
    }
)


class SumGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: str = "i"
    term: str  # in the index
    start: int = 1
    rhs: str  # in n


class DividesGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    divisor: int = Field(ge=2)
    expr: str  # in n


class InductionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base: int = Field(ge=0)
    sum: SumGoal | None = None
    divides: DividesGoal | None = None

    @model_validator(mode="after")
    def _one_goal(self) -> InductionParams:
        if (self.sum is None) == (self.divides is None):
            raise ValueError("give exactly one of 'sum' or 'divides'")
        return self


@dataclass(frozen=True)
class _Spec:
    ctx: MathContext
    n: sp.Symbol
    k: sp.Symbol
    i: sp.Symbol | None
    term: sp.Expr | None  # sum term in the index
    start: int
    rhs: sp.Expr | None  # sum formula in n
    divisor: int | None
    target: sp.Expr | None  # divisibility expression in n
    base: int

    def at(self, expr: sp.Expr, value: sp.Expr | int) -> sp.Expr:
        return expr.subs(self.n, value)


_PREFIX = re.compile(r"^\s*(?:n\s*=\s*\d+|base(?:\s+case)?|for\s+n\s*=\s*\d+)\s*[:,]?\s*", re.I)
_SUFFIX = re.compile(
    r"(?:,?\s*(?:for\s+some|where|with|when)\b.*|,\s*k\s*(?:≥|>=|>)\s*\d+\s*)$", re.I
)
_DOTS = re.compile(r"\.\.\.|…|⋯|\\cdots|\\ldots|∑|Σ|\\sum")


def _sum_value(spec: _Spec, upto: int) -> sp.Expr:
    assert spec.term is not None and spec.i is not None
    return sp.Add(*[spec.term.subs(spec.i, j) for j in range(spec.start, upto + 1)])


def _top_terms(expr: sp.Expr) -> list[sp.Expr]:
    if isinstance(expr, sp.Add):
        out: list[sp.Expr] = []
        for a in expr.args:
            out.extend(_top_terms(a))
        return out
    return [expr]


def _fingerprint(expr: sp.Expr, k: sp.Symbol) -> tuple[sp.Expr, ...] | None:
    try:
        vals = tuple(sp.nsimplify(sp.simplify(expr.subs(k, v))) for v in (3, 5, 8))
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return vals if all(v.is_Rational for v in vals) else None


@register
class InductionHandler(TopicHandler):
    kind = "induction"
    Params = InductionParams
    step_kinds = frozenset({"base", "assume", "expr", "witness", "note"})
    syntax_help = (
        "'base': the base case with numbers, like 1 = 1(1 + 1)/2. 'assume': the hypothesis for "
        "n = k, like 1 + 2 + ... + k = k(k + 1)/2 (or k^3 + 5k + 6 = 3m). 'expr': the inductive "
        "step, each line equal to the n = k + 1 case; for a sum, start with the hypothesis plus "
        "the next term, like k(k + 1)/2 + (k + 1). 'witness': for divisibility, the integer w "
        "with f(k + 1) = d·w. Write factorials as (k + 1)!."
    )

    def has_answer(self, problem: Problem, params: InductionParams) -> bool:
        return False

    def spec(self, problem: Problem, params: InductionParams) -> _Spec:
        try:
            names = {"n": "integer", "k": "integer", "m": "integer"}
            if params.sum is not None:
                names[params.sum.index] = "integer"
            ctx = MathContext.build(names)
            n, k = ctx["n"], ctx["k"]
            if params.sum is not None:
                i = ctx[params.sum.index]
                return _Spec(
                    ctx,
                    n,
                    k,
                    i,
                    ctx.parse(params.sum.term),
                    params.sum.start,
                    ctx.parse(params.sum.rhs),
                    None,
                    None,
                    params.base,
                )
            assert params.divides is not None
            return _Spec(
                ctx,
                n,
                k,
                None,
                None,
                0,
                None,
                params.divides.divisor,
                ctx.parse(params.divides.expr),
                params.base,
            )
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def validate(self, problem: Problem, params: InductionParams) -> None:
        if not self.verify_key(problem, params):
            raise ContentError(f"{problem.id}: the statement isn't true for n = base … base + 15")

    def verify_key(self, problem: Problem, params: InductionParams) -> bool | None:
        spec = self.spec(problem, params)
        if spec.rhs is not None:
            assert spec.term is not None and spec.i is not None
            closed = sp.summation(spec.term, (spec.i, spec.start, spec.n))
            if sp.simplify(closed - spec.rhs) == 0:
                return True
            return all(
                sp.simplify(_sum_value(spec, v) - spec.at(spec.rhs, v)) == 0
                for v in range(spec.base, spec.base + 16)
            )
        assert spec.target is not None and spec.divisor is not None
        return all(
            int(spec.at(spec.target, v)) % spec.divisor == 0
            for v in range(spec.base, spec.base + 16)
        )

    # ------------------------------------------------------------------ steps

    def _base_step(self, i: int, text: str, spec: _Spec, vb: VerdictBuilder) -> bool:
        body = _PREFIX.sub("", normalize(text))
        numbers = MathContext.build()
        example = self._base_example(spec)
        divides = "|" in body and "=" not in body
        try:
            if divides:
                left, right = (part.strip() for part in body.split("|", 1))
                d_val, value = numbers.parse(left), numbers.parse(right)
                parts = [value]
                if spec.divisor is None or sp.simplify(d_val - spec.divisor) != 0:
                    vb.error(i, "base", "IND_BASE_NUMBERS", base=spec.base, example=example)
                    return False
            else:
                pieces, ops = split_relation(body)
                if any(op != "=" for op in ops):
                    raise MathInputError("", "IND_BASE_NUMBERS")
                parts = [numbers.parse(p) for p in pieces]
        except MathInputError:
            vb.error(i, "base", "IND_BASE_NUMBERS", base=spec.base, example=example)
            return False
        values = [sp.nsimplify(sp.simplify(p)) for p in parts]
        latex = " = ".join(to_latex(p) for p in parts)
        if any(not v.is_number for v in values):
            vb.error(i, "base", "IND_BASE_NUMBERS", latex=latex, base=spec.base, example=example)
            return False
        if len(set(values)) > 1:
            shown = ", ".join(f"${to_latex(v)}$" for v in values)
            vb.error(i, "base", "IND_BASE_UNEQUAL", latex=latex, values=shown)
            return False
        want = (
            _sum_value(spec, spec.base) if spec.rhs is not None else spec.at(spec.target, spec.base)  # type: ignore[arg-type]
        )
        if sp.simplify(values[0] - want) != 0:
            vb.error(
                i,
                "base",
                "IND_BASE_WRONG",
                latex=latex,
                base=spec.base,
                value=to_latex(want),
                got=to_latex(values[0]),
            )
            return False
        if spec.rhs is not None:
            detail = f"both sides equal ${to_latex(want)}$"
        else:
            detail = f"the expression is ${to_latex(want)}$, which is divisible by ${spec.divisor}$"
        vb.ok(i, "base", hints.message("IND_BASE_OK", base=spec.base, detail=detail), latex=latex)
        return True

    def _base_example(self, spec: _Spec) -> str:
        if spec.rhs is not None:
            left = to_latex(_sum_value(spec, spec.base))
            return f"{left} = {to_latex(spec.at(spec.rhs, spec.base))}"
        assert spec.target is not None
        value = spec.at(spec.target, spec.base)
        value = sp.simplify(value)
        return f"{to_latex(value)} = {spec.divisor} \\cdot {to_latex(value / spec.divisor)}"

    def _assume_step(
        self, i: int, text: str, spec: _Spec, vb: VerdictBuilder
    ) -> sp.Symbol | None | bool:
        """True (sum) / the new symbol m (divides) when valid, otherwise None."""
        body = _SUFFIX.sub("", normalize(text)).strip()
        pieces, ops = split_relation(body)
        if len(pieces) < 2 or ops[-1] != "=":
            example = self._assume_example(spec)
            vb.error(i, "assume", "IND_ASSUME_FORMAT", example=example)
            return None
        right_text, left_text = pieces[-1], pieces[-2]
        try:
            right = spec.ctx.parse(right_text)
        except MathInputError as exc:
            vb.step(i, "assume", StepStatus.ERROR, exc.message, code=exc.code)
            return None
        if spec.rhs is not None:
            rhs_k = spec.at(spec.rhs, spec.k)
            latex = f"\\cdots = {to_latex(right)}"
            if right.has(spec.n):
                vb.error(i, "assume", "IND_ASSUME_USE_K", latex=latex)
                return None
            if not equivalent(right, rhs_k, spec.ctx):
                vb.error(i, "assume", "IND_ASSUME_WRONG", latex=latex, rhs=to_latex(rhs_k))
                return None
            vb.ok(i, "assume", hints.message("IND_ASSUME_OK"), latex=latex)
            return True
        assert spec.target is not None and spec.divisor is not None
        target_k = spec.at(spec.target, spec.k)
        want = dict(target=to_latex(target_k), d=spec.divisor)
        try:
            left = spec.ctx.parse(left_text)
        except MathInputError:
            vb.error(i, "assume", "IND_ASSUME_DIVIDES", **want)
            return None
        latex = f"{to_latex(left)} = {to_latex(right)}"
        if left.has(spec.n) or right.has(spec.n):
            vb.error(i, "assume", "IND_ASSUME_USE_K", latex=latex)
            return None
        fresh = right.free_symbols - {spec.k}
        m = next(iter(fresh)) if len(fresh) == 1 else None
        if (
            m is None
            or sp.expand(right - spec.divisor * m) != 0
            or not equivalent(left, target_k, spec.ctx)
        ):
            vb.error(i, "assume", "IND_ASSUME_DIVIDES", latex=latex, **want)
            return None
        vb.ok(i, "assume", hints.message("IND_ASSUME_OK"), latex=latex)
        return m

    def _uses_hypothesis(self, text: str, spec: _Spec) -> bool:
        """Is this line rhs(k) + term(k + 1), possibly with the terms in any order?"""
        assert spec.rhs is not None and spec.term is not None and spec.i is not None
        try:
            with sp.evaluate(False):
                raw = spec.ctx.parse(text)
        except Exception:  # noqa: BLE001 - unevaluated parsing is best effort
            return False
        terms = _top_terms(raw)
        if len(terms) > 12:
            return False
        rhs_k = spec.at(spec.rhs, spec.k)
        nxt = spec.term.subs(spec.i, spec.k + 1)
        want = _fingerprint(rhs_k, spec.k)
        prints = [_fingerprint(t, spec.k) for t in terms]
        if want is None or any(p is None for p in prints):
            return False
        for size in range(1, len(terms)):
            for combo in itertools.combinations(range(len(terms)), size):
                total = tuple(sum(prints[j][q] for j in combo) for q in range(3))  # type: ignore[index]
                if total != want:
                    continue
                part = sp.Add(*[terms[j] for j in combo])
                rest = sp.Add(*[terms[j] for j in range(len(terms)) if j not in combo])
                if equivalent(part, rhs_k, spec.ctx) and equivalent(rest, nxt, spec.ctx):
                    return True
        return False

    # ------------------------------------------------------------------ check

    def check(
        self,
        problem: Problem,
        params: InductionParams,
        submission: Submission,
        vb: VerdictBuilder,
    ) -> None:
        spec = self.spec(problem, params)
        k = spec.k
        base_ok = False
        hypothesis: sp.Symbol | None | bool = None
        used = False
        simplified = False
        witness_ok = False
        if spec.rhs is not None:
            goal = spec.at(spec.rhs, k + 1)
        else:
            goal = spec.at(spec.target, k + 1)  # type: ignore[arg-type]

        for i, step in enumerate(submission.steps):
            kind = step.kind
            if kind == "note":
                vb.step(i, kind, StepStatus.UNCHECKED, code="IND_NOTE")
                continue
            if kind == "base":
                base_ok = self._base_step(i, step.content, spec, vb) or base_ok
                continue
            if kind == "assume":
                result = self._assume_step(i, step.content, spec, vb)
                if result is not None:
                    hypothesis = result
                continue
            m = hypothesis if isinstance(hypothesis, sp.Symbol) else None
            ctx = spec.ctx
            try:
                expr = ctx.parse(
                    re.sub(r"^\s*[A-Za-z]\w*\s*=(?!=)", "", step.content)
                    if kind == "witness"
                    else step.content
                )
            except MathInputError as exc:
                vb.step(i, kind, StepStatus.ERROR, exc.message, code=exc.code)
                continue
            latex = to_latex(expr)
            if expr.has(ctx["m"]) and m is None and spec.target is not None:
                vb.error(i, kind, "IND_NO_HYPOTHESIS_YET", latex=latex)
                continue
            subs = {m: spec.at(spec.target, k) / spec.divisor} if m is not None else {}  # type: ignore[arg-type,operator]
            if kind == "witness":
                if spec.target is None:
                    vb.error(i, kind, "IND_STEP_WRONG", latex=latex)
                    continue
                d = spec.divisor
                if not is_integer_valued_polynomial(expr, {k} | ({m} if m is not None else set())):
                    vb.error(i, kind, "IND_WITNESS_NOT_INTEGER", latex=latex)
                elif not equivalent(sp.expand(d * expr.xreplace(subs)), goal, ctx):  # type: ignore[operator]
                    vb.error(i, kind, "IND_WITNESS_WRONG", latex=latex, d=d, target=to_latex(goal))
                else:
                    witness_ok = True
                    form = f"{d}\\left({latex}\\right)"
                    vb.ok(
                        i,
                        kind,
                        hints.message(
                            "IND_WITNESS_OK", target=to_latex(goal), form=form, w=latex, d=d
                        ),
                        latex=latex,
                    )
                continue
            # expr: the inductive step chain
            if not equivalent(expr.xreplace(subs), goal, ctx):
                vb.error(i, kind, "IND_STEP_WRONG", latex=latex)
                continue
            if (
                spec.rhs is not None
                and hypothesis is not None
                and not used
                and self._uses_hypothesis(step.content, spec)
            ):
                used = True
                assert spec.term is not None and spec.i is not None
                vb.ok(
                    i,
                    kind,
                    hints.message(
                        "IND_STEP_USES_HYPOTHESIS",
                        rhs=to_latex(spec.at(spec.rhs, k)),
                        term=to_latex(spec.term.subs(spec.i, k + 1)),
                    ),
                    latex=latex,
                )
                continue
            if used:
                simplified = True
            vb.ok(i, kind, hints.message("IND_STEP_OK"), latex=latex)

        self._finish(spec, submission, vb, base_ok, hypothesis, used, simplified, witness_ok, goal)

    def _finish(
        self,
        spec: _Spec,
        submission: Submission,
        vb: VerdictBuilder,
        base_ok: bool,
        hypothesis: sp.Symbol | None | bool,
        used: bool,
        simplified: bool,
        witness_ok: bool,
        goal: sp.Expr,
    ) -> None:
        if not submission.steps:
            vb.hint("EMPTY_SUBMISSION")
            vb.set_status(VerdictStatus.INCORRECT)
            return
        first_error = vb.first_error
        if first_error is not None:
            vb.answer(VerdictStatus.INCORRECT, code="PROOF_HAS_ERRORS", step_number=first_error + 1)
            vb.set_status(VerdictStatus.INCORRECT)
            return
        missing: tuple[str, dict[str, object]] | None = None
        if not base_ok:
            missing = ("IND_NEED_BASE", {"base": spec.base})
        elif hypothesis is None:
            missing = ("IND_NEED_HYPOTHESIS", {})
        elif spec.rhs is not None:
            assert spec.term is not None and spec.i is not None
            if not used:
                missing = (
                    "IND_USE_HYPOTHESIS",
                    {
                        "rhs": to_latex(spec.at(spec.rhs, spec.k)),
                        "term": to_latex(spec.term.subs(spec.i, spec.k + 1)),
                    },
                )
            elif not simplified:
                missing = ("IND_FINISH_SUM", {"rhs": to_latex(goal)})
        elif not witness_ok:
            missing = ("IND_FINISH_DIVIDES", {"target": to_latex(goal), "d": spec.divisor})

        if missing is None:
            if spec.rhs is not None:
                vb.answer(VerdictStatus.CORRECT, code="IND_PROVED_SUM", base=spec.base)
            else:
                vb.answer(
                    VerdictStatus.CORRECT,
                    code="IND_PROVED_DIVIDES",
                    base=spec.base,
                    d=spec.divisor,
                    target=to_latex(spec.target),  # type: ignore[arg-type]
                )
            vb.set_status(VerdictStatus.CORRECT)
            return
        code, params = missing
        vb.answer(VerdictStatus.PARTIAL, code=code, **params)
        vb.hint(code, **params)
        vb.set_status(VerdictStatus.PARTIAL)

    def _assume_example(self, spec: _Spec) -> str:
        if spec.rhs is not None:
            return f"\\cdots = {to_latex(spec.at(spec.rhs, spec.k))}"
        return f"{to_latex(spec.at(spec.target, spec.k))} = {spec.divisor}m"  # type: ignore[arg-type]
