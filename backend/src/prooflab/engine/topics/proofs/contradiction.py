"""Contradiction and non-conditional statements (SPEC §5.1, Book of Proof Chapters 6–7).

``impossibility_proof`` — "this can never happen" statements about integers, the core of most
proofs by contradiction in Chapter 6 (and several in Chapter 7): a² − 4b − 2 ≠ 0, 4 ∤ (n² + 2),
"if a² + b² = c², then a or b is even", "there are no integers with 21a + 30b = 1". The proof
shows that an integer expression always leaves the wrong remainder:

- ``let``/``case``/``expr``/``note`` steps work exactly as in ``divisibility_proof``.
- ``form`` ``4(k^2 - b) + 2``: the expression written as d·w + r with w an integer polynomial.
  It must equal the expression, and r must not be the remainder the claim rules out. Every case
  (or the whole proof, without cases) needs one.

``existence`` — "there exists" statements (Chapter 7) proved by giving an example: values that
make the statement true, checked with the same predicates as ``counterexample``.
"""

from __future__ import annotations

import dataclasses

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field, model_validator

from prooflab.engine import hints
from prooflab.engine.algebra import (
    MathInputError,
    equivalent,
    is_integer_polynomial,
    normalize,
    split_relation,
    to_latex,
)
from prooflab.engine.checker import ContentError, VerdictBuilder, register
from prooflab.engine.models import Problem, StepStatus, Submission, VerdictStatus
from prooflab.engine.topics.proofs.divisibility import (
    _DOMAIN_WORDS,
    CounterexampleHandler,
    DomainName,
    ModularProofHandler,
    Predicate,
    ProofSpec,
    _Block,
    _leaves,
    evaluate_predicate,
    form_latex,
    parse_assignment,
    substitute,
)

hints.register_many(
    {
        "FORM_NOT_EQUAL": "This isn't equal to ${target}$ here. Check your algebra.",
        "FORM_SHAPE": "Write it factored, as ${d}$ times an integer plus a number, like "
        "${example}$: that factoring is the step that shows the remainder.",
        "FORM_INCOMPLETE": "Everything so far checks out, but the proof isn't finished. Each part "
        "should end with a form step: the expression as ${d}$ times an integer plus a remainder.",
        "FORM_ALLOWED_REMAINDER": "This leaves remainder {r} when divided by ${d}$, which is the "
        "remainder the statement rules out. Check the algebra, or split into cases.",
        "FORM_OK": "${target} = {form}$ leaves remainder {r} when divided by ${d}$, "
        "never {forbidden}.",
        "EXISTS_VALID": "These values make the statement true, so such values exist.",
        "EXISTS_FAILS": "With these values the statement is false. Find values that make it true.",
        "EXISTS_FORMAT": "Write the values like n = 10: one 'name = number' for each of {names}.",
    }
)


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Hypothesis(_Params):
    """``{"var": "n", "is": "odd"}`` or ``{"var": "a", "divisor": 3, "remainder": 1}``."""

    var: str
    is_: str | None = Field(default=None, alias="is", pattern=r"^(even|odd)$")
    divisor: int | None = None
    remainder: int | None = None

    @model_validator(mode="after")
    def _one_form(self) -> Hypothesis:
        if (self.is_ is None) == (self.divisor is None):
            raise ValueError("give either 'is' (even/odd) or 'divisor' + 'remainder'")
        return self

    def condition(self) -> tuple[str, int, int]:
        if self.is_ is not None:
            return (self.var, 2, 0 if self.is_ == "even" else 1)
        return (self.var, int(self.divisor or 0), int(self.remainder or 0))


class ImpossibilityParams(_Params):
    variables: list[str] = Field(min_length=1)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    target: str
    divisor: int = Field(ge=2)
    #: the remainder ``target`` can never leave when divided by ``divisor``
    forbidden: int = Field(ge=0)
    #: shown when the proof is complete, e.g. "so $a^2 - 4b - 2$ is never 0. ∎"
    conclusion: str


@register
class ImpossibilityProofHandler(ModularProofHandler):
    kind = "impossibility_proof"
    Params = ImpossibilityParams
    step_kinds = frozenset({"let", "case", "expr", "form", "note"})
    syntax_help = (
        "Show the expression can never have the remainder the statement rules out. 'let': "
        "rewrite a hypothesis (n = 2k + 1). 'case': split into cases (a = 2k, then a = 2k + 1). "
        "'expr': algebra, each step equal to the expression. 'form': the expression as d times "
        "an integer plus a remainder, like 4(k^2 - b) + 2. 'note': not checked."
    )

    def spec(self, problem: Problem, params: ImpossibilityParams) -> ProofSpec:
        if params.forbidden >= params.divisor:
            raise ContentError(f"{problem.id}: need 0 ≤ forbidden < divisor")
        spec = self.build_spec(
            problem,
            params.variables,
            [h.condition() for h in params.hypotheses],
            params.target,
            params.divisor,
            params.forbidden,
        )
        return dataclasses.replace(spec, conclusion=f"Proof complete: {params.conclusion}")

    def describe(self, divisor: sp.Expr, remainder: sp.Expr) -> str:
        if divisor == 2:
            return "even" if remainder == 0 else "odd"
        return super().describe(divisor, remainder)

    def _witness_step(
        self, i: int, text: str, spec: ProofSpec, block: _Block, vb: VerdictBuilder
    ) -> None:
        parts, ops = split_relation(normalize(text))
        body = parts[-1] if ops and all(op == "=" for op in ops) else text
        try:
            expr = block.ctx.parse(body)
        except MathInputError as exc:
            vb.step(i, "form", StepStatus.ERROR, exc.message, code=exc.code)
            return
        latex = to_latex(expr)
        d = int(spec.divisor)
        forbidden = int(spec.remainder)
        target = substitute(spec.target, block.subs)
        value = substitute(expr, block.subs)
        target_latex = to_latex(spec.target)
        if not equivalent(value, target, block.ctx):
            vb.error(i, "form", "FORM_NOT_EQUAL", latex=latex, target=target_latex)
            for v in spec.hypotheses:
                if v not in block.subs and spec.target.has(v):
                    vb.hint("MISSING_LET", step=i, var=f"${to_latex(v)}$")
            return
        integers = set(spec.variables) | block.fresh
        written = self._written_form(body, block, d, integers)
        if written is None:
            self._shape_error(i, latex, d, vb)
            return
        multiple, const = written
        # The student's own factoring: expression = multiple·(integer) + const, with d | multiple.
        r = int(const) % d
        w = sp.expand((sp.expand(value) - r) / d)
        if not is_integer_polynomial(w, integers):
            self._shape_error(i, latex, d, vb)
            return
        form = form_latex(spec.divisor, w, sp.Integer(r))
        if r == forbidden:
            vb.error(i, "form", "FORM_ALLOWED_REMAINDER", latex=latex, r=r, d=d)
            return
        block.witness = sp.Add(sp.Mul(spec.divisor, w, evaluate=False), r, evaluate=False)
        vb.ok(
            i,
            "form",
            hints.message("FORM_OK", target=target_latex, form=form, r=r, d=d, forbidden=forbidden),
            latex=latex,
        )

    @staticmethod
    def _written_form(
        text: str, block: _Block, d: int, integers: set[sp.Symbol]
    ) -> tuple[int, sp.Integer] | None:
        """Read the line as the student wrote it: (multiple of d)·(integer) + constant.

        Returns (multiple, constant), or None when the line isn't in that shape (so the student
        has to show the factoring; ProofLab doesn't do it for them).
        """
        try:
            with sp.evaluate(False):
                raw = block.ctx.parse(text)
        except Exception:  # noqa: BLE001 - unevaluated parsing is best effort
            return None

        def terms(e: sp.Expr) -> list[sp.Expr]:
            return [t for a in e.args for t in terms(a)] if isinstance(e, sp.Add) else [e]

        const = sp.Integer(0)
        product: sp.Expr | None = None
        for term in terms(raw):
            value = sp.simplify(term)
            if value.is_number:
                if not value.is_Integer:
                    return None
                const += value
                continue
            if product is not None:
                return None  # more than one non-constant part: not factored yet
            product = term
        if product is None:
            return None
        factors = list(product.args) if isinstance(product, sp.Mul) else [product]
        numbers = [f for f in factors if sp.simplify(f).is_number]
        rest = [f for f in factors if not sp.simplify(f).is_number]
        multiple = sp.simplify(sp.Mul(*numbers)) if numbers else sp.Integer(1)
        if not multiple.is_Integer or int(multiple) % d != 0 or not rest:
            return None
        inner = sp.expand(sp.simplify(sp.Mul(*rest)))  # evaluate the unevaluated tree
        if not is_integer_polynomial(inner, integers):
            return None
        return int(multiple), sp.Integer(const)

    @staticmethod
    def _shape_error(i: int, latex: str, d: int, vb: VerdictBuilder) -> None:
        k = sp.Symbol("k")
        vb.error(
            i,
            "form",
            "FORM_SHAPE",
            latex=latex,
            d=d,
            top=d - 1,
            example=form_latex(sp.Integer(d), k**2 + k, sp.Integer(1)),
        )

    def incomplete_hint(self, spec: ProofSpec) -> tuple[str, dict[str, object]]:
        return "FORM_INCOMPLETE", {"d": int(spec.divisor)}

    def single_conclusion(self, spec: ProofSpec, witness: sp.Expr) -> str:
        return spec.conclusion or super().single_conclusion(spec, witness)

    def cases_conclusion(self, spec: ProofSpec) -> str:
        return spec.conclusion or super().cases_conclusion(spec)


# =========================================================================== existence


class ExistenceParams(_Params):
    variables: dict[str, DomainName] = Field(min_length=1)
    statement: Predicate


@register
class ExistenceHandler(CounterexampleHandler):
    kind = "existence"
    Params = ExistenceParams  # type: ignore[assignment]
    syntax_help = (
        "Prove it exists by giving an example: a value for each variable, like n = 10, that "
        "makes the statement true. Steps are notes for your own working and aren't checked."
    )

    def validate(self, problem: Problem, params: ExistenceParams) -> None:  # type: ignore[override]
        try:
            ctx = self.setup(params)  # type: ignore[arg-type]
            for leaf in _leaves(params.statement):
                if isinstance(leaf, str):
                    ctx.parse(leaf)
            parse_assignment(problem.answer, list(params.variables))
        except (MathInputError, ValueError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def evaluate(  # type: ignore[override]
        self, params: ExistenceParams, text: str
    ) -> tuple[str, dict[str, object], dict[str, sp.Expr]]:
        ctx = self.setup(params)  # type: ignore[arg-type]
        try:
            raw = parse_assignment(text, list(params.variables))
        except MathInputError as exc:
            raise MathInputError(
                hints.message("EXISTS_FORMAT", names=", ".join(params.variables)), exc.code
            ) from exc
        for name, value in raw.items():
            if not value.is_Integer:
                return "COUNTEREXAMPLE_NOT_INTEGER", {"var": name}, raw
            domain = params.variables[name]
            if (domain == "positive" and value <= 0) or (domain == "nonnegative" and value < 0):
                return "COUNTEREXAMPLE_DOMAIN", {"var": name, "domain": _DOMAIN_WORDS[domain]}, raw
        values = {ctx[n]: sp.Integer(v) for n, v in raw.items()}
        if not evaluate_predicate(params.statement, ctx, values):
            return "EXISTS_FAILS", {}, raw
        return "EXISTS_VALID", {}, raw

    def verify_key(self, problem: Problem, params: ExistenceParams) -> bool | None:  # type: ignore[override]
        code, _, _ = self.evaluate(params, problem.answer)
        return code == "EXISTS_VALID"

    def check(  # type: ignore[override]
        self, problem: Problem, params: ExistenceParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        for i, step in enumerate(submission.steps):
            vb.step(i, step.kind, StepStatus.UNCHECKED, code="PROOF_NOTE")
        text = submission.answer
        if text is None or not text.strip():
            return
        try:
            code, extra, raw = self.evaluate(params, text)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        latex = ",\\ ".join(f"{n} = {to_latex(v)}" for n, v in raw.items())
        if code == "EXISTS_VALID":
            vb.answer(VerdictStatus.CORRECT, latex=latex, code=code)
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code=code, **extra)
        vb.hint(code, **extra)
