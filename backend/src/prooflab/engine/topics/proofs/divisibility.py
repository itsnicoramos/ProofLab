"""Divisibility proofs and counterexamples (SPEC §5.1): ``divisibility_proof``, ``counterexample``.

This module also holds the structured-proof engine that ``parity.py`` reuses (parity is
divisibility by 2). A proof is a list of steps:

- ``let``     ``n = 2k + 1``  rewrite a hypothesis with a new integer variable
- ``case``    ``n = 3k + 1``  start a case; the cases must cover every possibility
- ``expr``    a chain step; must equal the target expression under the substitutions
- ``witness`` ``w`` or ``m = w``: an integer polynomial with ``target = d·w + r``
- ``note``    free text, never checked
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field, model_validator

from prooflab.engine import hints
from prooflab.engine.algebra import (
    RESERVED_NAMES,
    MathContext,
    MathInputError,
    equivalent,
    is_integer_polynomial,
    linear_in,
    normalize,
    split_relation,
    split_top,
    to_latex,
)
from prooflab.engine.checker import ContentError, TopicHandler, VerdictBuilder, register
from prooflab.engine.models import Problem, StepStatus, Submission, VerdictStatus

hints.register_many(
    {
        "LET_FORMAT": "Write a let step like n = 2k + 1: one of the problem's variables, '=', and "
        "an expression in a new integer variable.",
        "ALREADY_INTRODUCED": "{var} was already rewritten earlier in this part of the proof.",
        "LET_WITHOUT_HYPOTHESIS": "Nothing in the problem says {var} has this form. To consider "
        "the possibilities for {var}, use case steps that cover every remainder.",
        "BAD_REPRESENTATION": 'This doesn\'t capture the hypothesis. "{condition}" means '
        "{var} = {form} for some integer k.",
        "FRESH_NOT_NEW": "Introduce a new letter here. {var} is already a variable in this "
        "problem, so it can't also be the new integer.",
        "SAME_FRESH_VARIABLE": "{fresh} is already used for another variable. Reusing it secretly "
        "assumes the two are related (for example m = n). Use a different new letter.",
        "CASE_MISMATCH": "Every case should split the same variable by the same number, like "
        "n = 3k, n = 3k + 1, n = 3k + 2.",
        "CASE_CONTRADICTS_HYPOTHESIS": "This case can't happen: it contradicts the hypothesis "
        "about {var}.",
        "CASES_NOT_EXHAUSTIVE": "Your cases don't cover every possibility for {var}. Missing: "
        "{missing}.",
        "WITNESS_NOT_INTEGER": "ProofLab can't confirm this witness is an integer. Write it as a "
        "polynomial with integer coefficients in your integer variables (sums and products of "
        "integers are integers).",
        "WITNESS_MISMATCH": "With this witness, {form} isn't equal to the expression you're "
        "working on. Check your algebra.",
        "MISSING_LET": "Start from the hypothesis about {var}: rewrite {var} with a let step using "
        "a new integer variable.",
        "TRY_CASES": "Nothing is known about {var}, so ProofLab can't see why this is an integer. "
        "Try splitting into cases by the remainder of {var}.",
        "PROOF_INCOMPLETE": "Everything so far checks out, but the proof isn't finished. Each part "
        "should end with a witness step: the integer w that puts the expression in the required "
        "form.",
        "PROOF_COMPLETE": "{conclusion}",
        "PROOF_HAS_ERRORS": "Step {step_number} doesn't check out, so the proof isn't valid yet.",
        "PROOF_NOTE": "Notes aren't checked.",
        "COUNTEREXAMPLE_FORMAT": "Write the values like a = 4, b = 2: one 'name = integer' for "
        "each variable, separated by commas.",
        "COUNTEREXAMPLE_MISSING_VALUE": "Give a value for every variable: {names}.",
        "COUNTEREXAMPLE_NOT_INTEGER": "{var} has to be an integer.",
        "COUNTEREXAMPLE_DOMAIN": "{var} has to be {domain} in this problem.",
        "HYPOTHESIS_NOT_MET": "These values don't satisfy the hypothesis, so they can't show the "
        "statement is false.",
        "CONCLUSION_HOLDS": "The conclusion is true for these values, so they don't disprove the "
        "statement. You need the hypothesis true and the conclusion false.",
        "COUNTEREXAMPLE_VALID": "The hypothesis holds and the conclusion fails for these values, "
        "so the statement is false.",
    }
)


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


# =========================================================================== proof engine


@dataclass(frozen=True)
class Condition:
    """``var ≡ remainder (mod divisor)``; ``remainder == 0`` means ``divisor | var``."""

    var: sp.Symbol
    divisor: sp.Expr
    remainder: sp.Expr


@dataclass(frozen=True)
class ProofSpec:
    ctx: MathContext
    variables: tuple[sp.Symbol, ...]
    hypotheses: dict[sp.Symbol, Condition]
    target: sp.Expr
    divisor: sp.Expr
    remainder: sp.Expr
    target_text: str
    #: overrides the default "Proof complete" message (used by impossibility proofs)
    conclusion: str | None = None


@dataclass
class _Block:
    """The preamble (index 0) or one case. Cases inherit the preamble's substitutions."""

    ctx: MathContext
    subs: dict[sp.Symbol, sp.Expr] = field(default_factory=dict)
    fresh: set[sp.Symbol] = field(default_factory=set)
    case_var: sp.Symbol | None = None
    modulus: int | None = None
    residue: int | None = None
    witness: sp.Expr | None = None

    def fork(self) -> _Block:
        return _Block(ctx=self.ctx, subs=dict(self.subs), fresh=set(self.fresh))

    def add_fresh(self, sym: sp.Symbol) -> None:
        self.fresh.add(sym)
        self.ctx = self.ctx.extend({sym.name: "integer"})


def substitute(expr: sp.Expr, subs: dict[sp.Symbol, sp.Expr]) -> sp.Expr:
    """Apply substitutions until nothing changes (c = b·k with b = a·j gives c = a·j·k)."""
    out = expr
    for _ in range(len(subs) + 1):
        new = out.xreplace(subs)
        if new == out:
            break
        out = new
    return sp.expand(out)


def _candidate_names(text: str, ctx: MathContext) -> list[str]:
    """Single letters in ``text`` that would be new variables (for let/case steps)."""
    found: list[str] = []
    for run in re.findall(r"[A-Za-z]+", normalize(text)):
        if run in RESERVED_NAMES or run in ctx.symbols:
            continue
        for ch in run:
            if ch not in ctx.symbols and ch not in RESERVED_NAMES and ch not in found:
                found.append(ch)
    return found


def _parse_definition(
    text: str, spec: ProofSpec, block: _Block
) -> tuple[sp.Symbol, sp.Expr, MathContext]:
    """``n = 2k + 1`` → (n, 2k + 1, ctx with k). Raises MathInputError(LET_FORMAT)."""
    parts, ops = split_relation(normalize(text))
    if ops != ["="] or parts[0].strip() not in spec.ctx.symbols:
        raise MathInputError(hints.message("LET_FORMAT"), "LET_FORMAT")
    var = spec.ctx[parts[0].strip()]
    ctx = block.ctx.extend({n: "integer" for n in _candidate_names(parts[1], block.ctx)})
    return var, ctx.parse(parts[1]), ctx


def _strip_witness_label(text: str) -> str:
    parts, ops = split_relation(normalize(text))
    if ops == ["="] and re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", parts[0].strip()):
        return parts[1]
    return text


def _is_int(e: sp.Expr) -> bool:
    return bool(e.is_Integer)


def form_latex(divisor: sp.Expr, witness: sp.Expr, remainder: sp.Expr) -> str:
    """LaTeX for ``d·w + r`` without SymPy distributing ``d`` over ``w``."""
    prod = sp.Mul(divisor, witness, evaluate=False) if witness != 1 else divisor
    if remainder == 0:
        return to_latex(prod)
    return to_latex(sp.Add(prod, remainder, evaluate=False))


class ModularProofHandler(TopicHandler):
    """Shared checker for structured direct proofs about integers. Not registered itself."""

    step_kinds = frozenset({"let", "case", "expr", "witness", "note"})
    syntax_help = (
        "Write the proof as steps. 'let': rewrite a hypothesis with a new integer variable "
        "(n = 2k + 1). 'case': start a case (n = 3k + 1); cases must cover every possibility. "
        "'expr': a chain of expressions, each equal to the one you're proving things about. "
        "'witness': the integer w with expression = d·w + r (write w, or m = w). "
        "'note': free text, not checked."
    )

    def has_answer(self, problem: Problem, params: Any) -> bool:
        return False

    # -- subclass hooks
    def spec(self, problem: Problem, params: Any) -> ProofSpec:
        raise NotImplementedError

    def describe(self, divisor: sp.Expr, remainder: sp.Expr) -> str:
        """Plain-language name of ``x ≡ remainder (mod divisor)``."""
        d, r = to_latex(divisor), to_latex(remainder)
        if remainder == 0:
            return f"divisible by ${d}$"
        return f"congruent to ${r}$ mod ${d}$"

    def representation_hint(
        self, cond: Condition, coeff: sp.Expr, const: sp.Expr
    ) -> tuple[str, dict[str, object]] | None:
        return None

    def single_conclusion(self, spec: ProofSpec, witness: sp.Expr) -> str:
        """Message when one witness (no cases) finishes the proof."""
        target = f"${to_latex(spec.target)}$"
        return (
            f"Proof complete: {target} = "
            f"${form_latex(spec.divisor, witness, spec.remainder)}$"
            f" with ${to_latex(witness)}$ an integer, so {target} is "
            f"{self.describe(spec.divisor, spec.remainder)}. ∎"
        )

    def incomplete_hint(self, spec: ProofSpec) -> tuple[str, dict[str, object]]:
        """Hint when every step checks out but a part has no closing step yet."""
        return "PROOF_INCOMPLETE", {}

    def cases_conclusion(self, spec: ProofSpec) -> str:
        """Message when every case has been finished."""
        return (
            f"Proof complete: in every case ${to_latex(spec.target)}$ is "
            f"{self.describe(spec.divisor, spec.remainder)}, and the cases cover every "
            "possibility. ∎"
        )

    # -- building blocks
    @staticmethod
    def build_spec(
        problem: Problem,
        variables: list[str],
        hypotheses: list[tuple[str, object, object]],
        target: str,
        divisor: object,
        remainder: object,
    ) -> ProofSpec:
        try:
            ctx = MathContext.build({v: "integer" for v in variables})
            syms = tuple(ctx[v] for v in variables)
            conds: dict[sp.Symbol, Condition] = {}
            for var, d, r in hypotheses:
                cond = Condition(ctx[var], ctx.parse(str(d)), ctx.parse(str(r)))
                ModularProofHandler._check_modulus(problem, cond.divisor, cond.remainder)
                if cond.var in conds:
                    raise ContentError(f"{problem.id}: two hypotheses about {var}")
                conds[cond.var] = cond
            d_expr, r_expr = ctx.parse(str(divisor)), ctx.parse(str(remainder))
            ModularProofHandler._check_modulus(problem, d_expr, r_expr)
            return ProofSpec(
                ctx=ctx,
                variables=syms,
                hypotheses=conds,
                target=ctx.parse(target),
                divisor=d_expr,
                remainder=r_expr,
                target_text=target,
            )
        except (MathInputError, KeyError, ValueError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    @staticmethod
    def _check_modulus(problem: Problem, d: sp.Expr, r: sp.Expr) -> None:
        # A numeric modulus needs a standard remainder 0 ≤ r < d. A symbolic modulus may have a
        # symbolic remainder: a ≡ b (mod n) means a = n·k + b (Book of Proof, Definition 5.1).
        if d.is_number:
            if not (d.is_Integer and d >= 2 and r.is_Integer and 0 <= r < d):
                raise ContentError(f"{problem.id}: need an integer divisor ≥ 2 and 0 ≤ r < d")
        elif r.is_number and r != 0:
            raise ContentError(f"{problem.id}: a symbolic divisor needs remainder 0 or a variable")

    def validate(self, problem: Problem, params: Any) -> None:
        self.spec(problem, params)

    def verify_key(self, problem: Problem, params: Any) -> bool | None:
        return None  # proofs have no single answer; the examples are the check

    # -- representation checks
    def _fresh_symbol(
        self, rep: sp.Expr, spec: ProofSpec, block: _Block, var: sp.Symbol
    ) -> tuple[sp.Symbol | None, tuple[str, dict[str, object]] | None]:
        problem_syms = set(spec.variables)
        fresh = rep.free_symbols - problem_syms
        if not fresh:
            used = rep.free_symbols & problem_syms
            if used and not all(self._is_divisor_symbol(s, spec) for s in used):
                name = sorted(str(s) for s in used)[0]
                return None, ("FRESH_NOT_NEW", {"var": name})
            return None, ("BAD_REPRESENTATION", self._rep_params(spec, var))
        if len(fresh) > 1:
            return None, ("BAD_REPRESENTATION", self._rep_params(spec, var))
        k = next(iter(fresh))
        if k in block.fresh:
            return None, ("SAME_FRESH_VARIABLE", {"fresh": f"${to_latex(k)}$"})
        return k, None

    @staticmethod
    def _is_divisor_symbol(sym: sp.Symbol, spec: ProofSpec) -> bool:
        return any(c.divisor.has(sym) for c in spec.hypotheses.values())

    def _rep_params(self, spec: ProofSpec, var: sp.Symbol) -> dict[str, object]:
        cond = spec.hypotheses.get(var)
        if cond is None:
            return {"condition": "", "var": var, "form": "…"}
        form = cond.divisor * sp.Symbol("k") + cond.remainder
        return {
            "condition": f"{var} is {self.describe(cond.divisor, cond.remainder)}",
            "var": f"${to_latex(var)}$",
            "form": f"${to_latex(form)}$",
        }

    def _check_representation(
        self, rep: sp.Expr, k: sp.Symbol, cond: Condition, spec: ProofSpec
    ) -> tuple[str, dict[str, object]] | None:
        lin = linear_in(rep, k)
        if lin is None:
            return ("BAD_REPRESENTATION", self._rep_params(spec, cond.var))
        coeff, const = lin
        d, r = cond.divisor, cond.remainder
        coeff_ok = sp.expand(coeff - d) == 0 or sp.expand(coeff + d) == 0
        if d.is_Integer:
            const_ok = _is_int(const) and (const - r) % d == 0
        else:
            const_ok = sp.expand(const - r) == 0
        if coeff_ok and const_ok:
            return None
        return self.representation_hint(cond, coeff, const) or (
            "BAD_REPRESENTATION",
            self._rep_params(spec, cond.var),
        )

    # -- the checker
    def check(
        self, problem: Problem, params: Any, submission: Submission, vb: VerdictBuilder
    ) -> None:
        spec = self.spec(problem, params)
        preamble = _Block(ctx=spec.ctx)
        blocks: list[_Block] = [preamble]
        case_valid: dict[int, bool] = {}  # block index → its case step was valid
        case_shape: tuple[sp.Symbol, int] | None = None

        for i, step in enumerate(submission.steps):
            block = blocks[-1]
            kind = step.kind
            if kind == "note":
                vb.step(i, kind, StepStatus.UNCHECKED, code="PROOF_NOTE")
                continue
            if kind == "case":
                block = preamble.fork()
                blocks.append(block)
                ok, case_shape = self._case_step(i, step.content, spec, block, case_shape, vb)
                case_valid[len(blocks) - 1] = ok
                continue
            if kind == "let":
                self._let_step(i, step.content, spec, block, vb)
            elif kind == "expr":
                self._expr_step(i, step.content, spec, block, vb)
            elif kind in ("witness", "form"):
                self._witness_step(i, step.content, spec, block, vb)

        self._finish(spec, submission, blocks, case_valid, case_shape, vb)

    def _let_step(
        self, i: int, text: str, spec: ProofSpec, block: _Block, vb: VerdictBuilder
    ) -> None:
        try:
            var, rep, _ = _parse_definition(text, spec, block)
        except MathInputError as exc:
            vb.step(i, "let", StepStatus.ERROR, exc.message, code=exc.code)
            return
        latex = f"{to_latex(var)} = {to_latex(rep)}"
        if var in block.subs:
            vb.error(i, "let", "ALREADY_INTRODUCED", latex=latex, var=f"${to_latex(var)}$")
            return
        cond = spec.hypotheses.get(var)
        if cond is None:
            vb.error(i, "let", "LET_WITHOUT_HYPOTHESIS", latex=latex, var=f"${to_latex(var)}$")
            return
        k, problem_ = self._fresh_symbol(rep, spec, block, var)
        if problem_ is None and k is not None:
            problem_ = self._check_representation(rep, k, cond, spec)
        if problem_ is not None:
            code, params = problem_
            vb.error(i, "let", code, latex=latex, **params)
            return
        assert k is not None
        block.subs[var] = rep
        block.add_fresh(k)
        vb.ok(
            i,
            "let",
            f"Since ${to_latex(var)}$ is {self.describe(cond.divisor, cond.remainder)}, "
            f"${latex}$ for some integer ${to_latex(k)}$.",
            latex=latex,
        )

    def _case_step(
        self,
        i: int,
        text: str,
        spec: ProofSpec,
        block: _Block,
        shape: tuple[sp.Symbol, int] | None,
        vb: VerdictBuilder,
    ) -> tuple[bool, tuple[sp.Symbol, int] | None]:
        try:
            var, rep, _ = _parse_definition(text, spec, block)
        except MathInputError as exc:
            vb.step(i, "case", StepStatus.ERROR, exc.message, code=exc.code)
            return False, shape
        latex = f"{to_latex(var)} = {to_latex(rep)}"
        if var in block.subs:
            vb.error(i, "case", "ALREADY_INTRODUCED", latex=latex, var=f"${to_latex(var)}$")
            return False, shape
        k, problem_ = self._fresh_symbol(rep, spec, block, var)
        if problem_ is not None and problem_[0] == "BAD_REPRESENTATION":
            problem_ = ("CASE_MISMATCH", {})
        lin = linear_in(rep, k) if k is not None and problem_ is None else None
        if problem_ is None and (
            lin is None or not (_is_int(lin[0]) and lin[0] != 0 and _is_int(lin[1]))
        ):
            problem_ = ("CASE_MISMATCH", {})
        if problem_ is not None:
            code, params = problem_
            vb.error(i, "case", code, latex=latex, **params)
            return False, shape
        assert k is not None and lin is not None
        modulus, residue = abs(int(lin[0])), int(lin[1]) % abs(int(lin[0]))
        if shape is not None and shape != (var, modulus):
            vb.error(i, "case", "CASE_MISMATCH", latex=latex)
            return False, shape
        cond = spec.hypotheses.get(var)
        if cond is not None:
            if not cond.divisor.is_Integer:
                vb.error(i, "case", "CASE_MISMATCH", latex=latex)
                return False, shape
            d, r = int(cond.divisor), int(cond.remainder)
            if modulus % d != 0 or residue % d != r:
                vb.error(
                    i, "case", "CASE_CONTRADICTS_HYPOTHESIS", latex=latex, var=f"${to_latex(var)}$"
                )
                return False, shape
        block.subs[var] = rep
        block.add_fresh(k)
        block.case_var, block.modulus, block.residue = var, modulus, residue
        vb.ok(
            i,
            "case",
            f"Case: ${to_latex(var)}$ leaves remainder {residue} when divided by {modulus}.",
            latex=latex,
        )
        return True, (var, modulus)

    def _expr_step(
        self, i: int, text: str, spec: ProofSpec, block: _Block, vb: VerdictBuilder
    ) -> None:
        try:
            expr = block.ctx.parse(text)
        except MathInputError as exc:
            vb.step(i, "expr", StepStatus.ERROR, exc.message, code=exc.code)
            return
        latex = to_latex(expr)
        same = equivalent(
            substitute(expr, block.subs), substitute(spec.target, block.subs), block.ctx
        )
        if same:
            vb.ok(i, "expr", latex=latex)
        elif same is None:
            vb.step(i, "expr", StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
        else:
            vb.error(i, "expr", "NOT_EQUIVALENT", latex=latex)

    def _witness_step(
        self, i: int, text: str, spec: ProofSpec, block: _Block, vb: VerdictBuilder
    ) -> None:
        try:
            w = block.ctx.parse(_strip_witness_label(text))
        except MathInputError as exc:
            vb.step(i, "witness", StepStatus.ERROR, exc.message, code=exc.code)
            return
        latex = to_latex(w)
        target = substitute(spec.target, block.subs)
        form = spec.divisor * w + spec.remainder
        integers = set(spec.variables) | block.fresh
        missing = [v for v in spec.hypotheses if v not in block.subs and target.has(v)]
        if not is_integer_polynomial(w, integers):
            vb.error(i, "witness", "WITNESS_NOT_INTEGER", latex=latex)
        elif not equivalent(substitute(form, block.subs), target, block.ctx):
            shown = form_latex(spec.divisor, w, spec.remainder)
            vb.error(i, "witness", "WITNESS_MISMATCH", latex=latex, form=f"${shown}$")
        else:
            block.witness = w
            vb.ok(
                i,
                "witness",
                f"${to_latex(spec.target)} = {form_latex(spec.divisor, w, spec.remainder)}$ "
                f"and ${latex}$ is an integer.",
                latex=latex,
            )
            return
        for v in missing:
            vb.hint("MISSING_LET", step=i, var=f"${to_latex(v)}$")
        unknown = [
            v
            for v in spec.variables
            if v not in spec.hypotheses
            and v not in block.subs
            and w.has(v)
            and not self._is_divisor_symbol(v, spec)
            and not spec.divisor.has(v)
        ]
        if unknown and not missing and not is_integer_polynomial(w, integers):
            vb.hint("TRY_CASES", step=i, var=f"${to_latex(unknown[0])}$")

    def _finish(
        self,
        spec: ProofSpec,
        submission: Submission,
        blocks: list[_Block],
        case_valid: dict[int, bool],
        shape: tuple[sp.Symbol, int] | None,
        vb: VerdictBuilder,
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

        preamble, cases = blocks[0], blocks[1:]
        missing_residues: list[int] = []
        if cases and shape is not None:
            var, m = shape
            required = set(range(m))
            cond = spec.hypotheses.get(var)
            if cond is not None and cond.divisor.is_Integer:
                d, r = int(cond.divisor), int(cond.remainder)
                required = {q for q in required if q % d == r}
            covered = {b.residue for idx, b in enumerate(blocks) if case_valid.get(idx)}
            missing_residues = sorted(required - covered)
        all_cases_done = bool(cases) and all(b.witness is not None for b in cases)

        if preamble.witness is not None:
            conclusion = self.single_conclusion(spec, preamble.witness)
        elif all_cases_done and not missing_residues:
            conclusion = self.cases_conclusion(spec)
        else:
            conclusion = None

        if conclusion is not None:
            vb.answer(VerdictStatus.CORRECT, code="PROOF_COMPLETE", conclusion=conclusion)
            vb.set_status(VerdictStatus.CORRECT)
            return

        vb.set_status(VerdictStatus.PARTIAL)
        if missing_residues and shape is not None:
            var, m = shape
            k = sp.Symbol("k")
            forms = ", ".join(
                f"${to_latex(var)} = {to_latex(m * k + q)}$" for q in missing_residues
            )
            vb.hint("CASES_NOT_EXHAUSTIVE", var=f"${to_latex(var)}$", missing=forms)
            vb.answer(
                VerdictStatus.PARTIAL,
                code="CASES_NOT_EXHAUSTIVE",
                var=f"${to_latex(var)}$",
                missing=forms,
            )
        else:
            code, params = self.incomplete_hint(spec)
            vb.answer(VerdictStatus.PARTIAL, code=code, **params)
            vb.hint(code, **params)
        introduced = set().union(*(b.subs for b in blocks))
        for v in spec.hypotheses:
            if v not in introduced and spec.target.has(v):
                vb.hint("MISSING_LET", var=f"${to_latex(v)}$")


# =========================================================================== divisibility_proof


class DivisorCondition(_Params):
    var: str
    divisor: int | str
    remainder: int | str = 0


class DivisorGoal(_Params):
    divisor: int | str
    remainder: int | str = 0


class DivisibilityParams(_Params):
    variables: list[str] = Field(min_length=1)
    hypotheses: list[DivisorCondition] = Field(default_factory=list)
    target: str
    goal: DivisorGoal


@register
class DivisibilityProofHandler(ModularProofHandler):
    kind = "divisibility_proof"
    Params = DivisibilityParams

    def spec(self, problem: Problem, params: DivisibilityParams) -> ProofSpec:
        return self.build_spec(
            problem,
            params.variables,
            [(h.var, h.divisor, h.remainder) for h in params.hypotheses],
            params.target,
            params.goal.divisor,
            params.goal.remainder,
        )


# =========================================================================== counterexample

PredicateOp = Literal[
    "divides", "prime", "even", "odd", "eq", "ne", "lt", "le", "gt", "ge", "and", "or", "not"
]
_ARITY: dict[str, tuple[int, int | None]] = {
    "divides": (2, 2),
    "prime": (1, 1),
    "even": (1, 1),
    "odd": (1, 1),
    "eq": (2, 2),
    "ne": (2, 2),
    "lt": (2, 2),
    "le": (2, 2),
    "gt": (2, 2),
    "ge": (2, 2),
    "and": (1, None),
    "or": (1, None),
    "not": (1, 1),
}
_LOGICAL = {"and", "or", "not"}


class Predicate(_Params):
    op: PredicateOp
    args: list[Predicate | int | str]

    @model_validator(mode="after")
    def _arity(self) -> Predicate:
        lo, hi = _ARITY[self.op]
        if len(self.args) < lo or (hi is not None and len(self.args) > hi):
            raise ValueError(f"{self.op} takes {lo}{'' if hi == lo else '+'} argument(s)")
        logical = self.op in _LOGICAL
        if any(isinstance(a, Predicate) != logical for a in self.args):
            raise ValueError(
                f"{self.op}: arguments must be {'predicates' if logical else 'expressions'}"
            )
        return self


Predicate.model_rebuild()

DomainName = Literal["integer", "positive", "nonnegative"]
_DOMAIN_WORDS = {"positive": "a positive integer", "nonnegative": "a nonnegative integer"}


class CounterexampleParams(_Params):
    variables: dict[str, DomainName] = Field(min_length=1)
    hypothesis: Predicate | None = None
    conclusion: Predicate


def _leaves(p: Predicate) -> list[int | str]:
    out: list[int | str] = []
    for a in p.args:
        out.extend(_leaves(a) if isinstance(a, Predicate) else [a])
    return out


def evaluate_predicate(p: Predicate, ctx: MathContext, values: dict[sp.Symbol, sp.Integer]) -> bool:
    if p.op == "and":
        return all(evaluate_predicate(a, ctx, values) for a in p.args)  # type: ignore[arg-type]
    if p.op == "or":
        return any(evaluate_predicate(a, ctx, values) for a in p.args)  # type: ignore[arg-type]
    if p.op == "not":
        return not evaluate_predicate(p.args[0], ctx, values)  # type: ignore[arg-type]
    nums = []
    for a in p.args:
        expr = sp.Integer(a) if isinstance(a, int) else ctx.parse(str(a))
        nums.append(expr.xreplace(values))
    if not all(n.is_Rational for n in nums):
        raise MathInputError("Those values make an expression undefined.", "COUNTEREXAMPLE_FORMAT")
    if p.op in {"divides", "prime", "even", "odd"} and not all(n.is_Integer for n in nums):
        return False
    if p.op == "divides":
        a, b = int(nums[0]), int(nums[1])
        return b == 0 if a == 0 else b % a == 0
    if p.op == "prime":
        return bool(sp.isprime(int(nums[0])))
    if p.op == "even":
        return int(nums[0]) % 2 == 0
    if p.op == "odd":
        return int(nums[0]) % 2 == 1
    left, right = nums
    return {
        "eq": left == right,
        "ne": left != right,
        "lt": left < right,
        "le": left <= right,
        "gt": left > right,
        "ge": left >= right,
    }[p.op]


def parse_assignment(text: str, names: list[str]) -> dict[str, sp.Expr]:
    """``a = 4, b = 2`` → ``{"a": 4, "b": 2}`` (values are constants)."""
    t = re.sub(r"\band\b", ",", normalize(text)).replace(";", ",")
    numbers = MathContext.build()
    out: dict[str, sp.Expr] = {}
    for part in split_top(t, ","):
        if not part:
            continue
        pieces, ops = split_relation(part)
        name = pieces[0].strip()
        if ops != ["="] or name not in names or name in out:
            raise MathInputError(hints.message("COUNTEREXAMPLE_FORMAT"), "COUNTEREXAMPLE_FORMAT")
        out[name] = numbers.parse(pieces[1])
    missing = [n for n in names if n not in out]
    if missing:
        raise MathInputError(
            hints.message("COUNTEREXAMPLE_MISSING_VALUE", names=", ".join(names)),
            "COUNTEREXAMPLE_MISSING_VALUE",
        )
    return out


@register
class CounterexampleHandler(TopicHandler):
    kind = "counterexample"
    Params = CounterexampleParams
    step_kinds = frozenset({"expr", "note"})
    syntax_help = (
        "Give integer values for every variable, like a = 4, b = 2, c = 2. They must make the "
        "hypothesis true and the conclusion false. Steps are notes for your own working and "
        "aren't checked."
    )

    def setup(self, params: CounterexampleParams) -> MathContext:
        return MathContext.build({v: "integer" for v in params.variables})

    def validate(self, problem: Problem, params: CounterexampleParams) -> None:
        try:
            ctx = self.setup(params)
            preds = [params.conclusion] + ([params.hypothesis] if params.hypothesis else [])
            for p in preds:
                for leaf in _leaves(p):
                    if isinstance(leaf, str):
                        ctx.parse(leaf)
            parse_assignment(problem.answer, list(params.variables))
        except (MathInputError, ValueError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def evaluate(
        self, params: CounterexampleParams, text: str
    ) -> tuple[str, dict[str, object], dict[str, sp.Expr]]:
        """→ (code, params, values). Code COUNTEREXAMPLE_VALID means it works."""
        ctx = self.setup(params)
        raw = parse_assignment(text, list(params.variables))
        for name, value in raw.items():
            if not value.is_Integer:
                return "COUNTEREXAMPLE_NOT_INTEGER", {"var": name}, raw
            domain = params.variables[name]
            if (domain == "positive" and value <= 0) or (domain == "nonnegative" and value < 0):
                return "COUNTEREXAMPLE_DOMAIN", {"var": name, "domain": _DOMAIN_WORDS[domain]}, raw
        values = {ctx[n]: sp.Integer(v) for n, v in raw.items()}
        if params.hypothesis is not None and not evaluate_predicate(params.hypothesis, ctx, values):
            return "HYPOTHESIS_NOT_MET", {}, raw
        if evaluate_predicate(params.conclusion, ctx, values):
            return "CONCLUSION_HOLDS", {}, raw
        return "COUNTEREXAMPLE_VALID", {}, raw

    def verify_key(self, problem: Problem, params: CounterexampleParams) -> bool | None:
        code, _, _ = self.evaluate(params, problem.answer)
        return code == "COUNTEREXAMPLE_VALID"

    def check(
        self,
        problem: Problem,
        params: CounterexampleParams,
        submission: Submission,
        vb: VerdictBuilder,
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
        if code == "COUNTEREXAMPLE_VALID":
            vb.answer(VerdictStatus.CORRECT, latex=latex, code=code)
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code=code, **extra)
        vb.hint(code, **extra)
