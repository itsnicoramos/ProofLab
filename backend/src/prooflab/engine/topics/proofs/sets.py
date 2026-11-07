"""Finite sets (SPEC §5.1, Book of Proof Chapter 1): ``finite_set``.

The answer is a finite set listed between braces (or, with ``ask: cardinality``, its number of
elements). Sets of tuples (Cartesian products) and sets of sets (power sets) compare as sets.
Steps are optional equations between set expressions, like ``A ∪ B = {1, 2, 3}``; each side is
evaluated and all sides must be the same set.
"""

from __future__ import annotations

from typing import Literal

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field

from prooflab.engine import hints
from prooflab.engine.algebra import MathContext, MathInputError, split_relation
from prooflab.engine.checker import ContentError, TopicHandler, VerdictBuilder, register
from prooflab.engine.finite_sets import (
    Builder,
    ElementContext,
    count_leaves,
    count_members_deep,
    evaluate,
    flatten_tuples,
    latex,
    node_latex,
    parse_expression,
    parse_literal,
    sort_key,
    tuple_lengths,
)
from prooflab.engine.finite_sets import build_set as _build_set
from prooflab.engine.models import Problem, StepStatus, Submission, VerdictStatus

hints.register_many(
    {
        "SET_SYNTAX": "ProofLab couldn't read that set: {detail}",
        "SET_NOT_A_LIST": "Write the set by listing its elements between braces, like {1, 2, 3} "
        "(∅ for the empty set).",
        "SET_BUILDER": "ProofLab can't evaluate set-builder notation here. List the elements "
        "instead.",
        "SET_INFINITE": "This set goes on forever. ProofLab only checks finite sets.",
        "SET_TOO_LARGE": "That set is too large for ProofLab to work with.",
        "SET_UNKNOWN_NAME": "{detail}",
        "SET_MIXED_OPERATORS": "Add parentheses: ProofLab won't guess how ∪, ∩ and − group when "
        "they're mixed.",
        "SET_NO_UNIVERSE": "This problem has no universal set, so complements aren't defined.",
        "SET_STEP_OK": "Both sides are the same set.",
        "SET_STEP_NOT_EQUAL": "The two sides of this step aren't the same set.",
        "SET_STEP_UNLABELED": "Write the step as an equation, like A ∪ B = {1, 2, 3}, so ProofLab "
        "knows what to compare it with.",
        "SET_STEP_MIXED": "One side of this step is a set and the other is a number.",
        "SET_NOTE": "Notes aren't checked.",
        "SET_MISSING": "Your set is missing {count} element(s).",
        "SET_EXTRA": "These don't belong in the set: {elements}.",
        "SET_PAIRS_REVERSED": "The entries of your ordered pairs are the wrong way round: in "
        "A × B the first entry comes from A and the second from B.",
        "SET_TUPLE_LENGTH": "Every element of this set is an ordered list of {n} entries in "
        "parentheses, but some of yours have a different number of entries.",
        "SET_TUPLE_GROUPING": "Check how the entries are grouped: ((1, 2), 3), (1, (2, 3)) and "
        "(1, 2, 3) are three different things.",
        "SET_EMPTY_MISSING": "Don't forget the empty set ∅: it is a subset of every set.",
        "SET_BRACES": "Check your braces: {1, 2} and {{1, 2}} are different sets.",
        "SET_NATURALS_ZERO": "In Book of Proof, ℕ = {1, 2, 3, …}: 0 is not a natural number.",
        "SET_COUNT_INNER": "An element that is itself a set counts as one element, however many "
        "elements it has inside.",
        "SET_NOT_COUNT": "Enter the number of elements: a whole number like 4.",
    }
)


class FiniteSetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Named sets the prompt defines (A, B, U, A1, ...): a set expression (usually a literal)
    # or a set-builder description.
    sets: dict[str, str | Builder] = Field(default_factory=dict)
    universe: str | None = None  # the name of the universal set, for complements
    atoms: list[str] = Field(default_factory=list)  # letters/names used as elements
    # How to compute the answer from the named sets; None when it can't be computed
    # (e.g. an intersection over infinitely many sets) and the authored key stands alone.
    compute: str | Builder | None = None
    ask: Literal["set", "cardinality"] = "set"


class _Setup:
    def __init__(self, ectx: ElementContext, env: dict[str, frozenset], universe: frozenset | None):
        self.ectx = ectx
        self.env = env
        self.universe = universe


@register
class FiniteSetHandler(TopicHandler):
    kind = "finite_set"
    Params = FiniteSetParams
    step_kinds = frozenset({"expr", "note"})
    syntax_help = (
        "List a set between braces: {1, 2, 3}; ∅ (or {}) is the empty set. Elements can be "
        "numbers (sqrt(3), -1/2, pi), ordered pairs (1, a), or sets {1, 2}; 1, 2, ..., 9 is a run "
        "of whole numbers. Optional steps are equations such as A ∪ B = {1, 2, 3}, using ∪ (or "
        "cup), ∩ (or cap), − (or -), × (or x), A' (complement) and P(A) (power set); ∪, ∩ and − "
        "need parentheses when mixed."
    )

    # -- setup
    def setup(self, problem: Problem, p: FiniteSetParams) -> _Setup:
        ectx = ElementContext.build(p.atoms)
        env: dict[str, frozenset] = {}
        for name, spec in p.sets.items():
            env[name] = self._evaluate(spec, env, ectx, None)
        universe = None
        if p.universe is not None:
            if p.universe not in env:
                raise ContentError(f"{problem.id}: universe {p.universe!r} is not in 'sets'")
            universe = env[p.universe]
        return _Setup(ectx, env, universe)

    @staticmethod
    def _evaluate(
        spec: str | Builder,
        env: dict[str, frozenset],
        ectx: ElementContext,
        universe: frozenset | None,
        *,
        naturals_from: int = 1,
    ) -> frozenset:
        if isinstance(spec, Builder):
            return _build_set(spec, env, ectx, universe, naturals_from=naturals_from)
        return evaluate(parse_expression(spec, ectx), env, universe)

    def computed(self, s: _Setup, p: FiniteSetParams, *, naturals_from: int = 1) -> frozenset:
        assert p.compute is not None
        env = s.env
        if naturals_from != 1:  # the "ℕ starts at 0" variant of every named builder
            env = {}
            for name, spec in p.sets.items():
                env[name] = self._evaluate(spec, env, s.ectx, None, naturals_from=naturals_from)
        return self._evaluate(p.compute, env, s.ectx, s.universe, naturals_from=naturals_from)

    def key(self, problem: Problem, p: FiniteSetParams, s: _Setup) -> frozenset | int:
        if p.ask == "cardinality":
            return _parse_count(problem.answer)
        return parse_literal(problem.answer, s.ectx)

    def validate(self, problem: Problem, params: FiniteSetParams) -> None:
        try:
            s = self.setup(problem, params)
            self.key(problem, params, s)
            if params.compute is not None:
                self.computed(s, params)
        except (MathInputError, ValueError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def verify_key(self, problem: Problem, params: FiniteSetParams) -> bool | None:
        if params.compute is None:
            return None
        s = self.setup(problem, params)
        value = self.computed(s, params)
        key = self.key(problem, params, s)
        return (len(value) if params.ask == "cardinality" else value) == key

    # -- checking
    def check(
        self, problem: Problem, params: FiniteSetParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        s = self.setup(problem, params)
        for i, step in enumerate(submission.steps):
            if step.kind == "note":
                vb.step(i, step.kind, StepStatus.UNCHECKED, code="SET_NOTE")
            else:
                self.check_step(vb, i, step.content, s)
        text = (submission.answer or "").strip()
        if not text:
            return
        key = self.key(problem, params, s)
        if params.ask == "cardinality":
            self.grade_count(vb, problem, params, s, text, key)  # type: ignore[arg-type]
        else:
            self.grade_set(vb, problem, params, s, text, key)  # type: ignore[arg-type]

    def check_step(self, vb: VerdictBuilder, i: int, content: str, s: _Setup) -> None:
        parts, ops = split_relation(content)
        if any(op != "=" for op in ops):
            vb.error(i, "expr", "SET_SYNTAX", detail="a step is an equation, with '=' only.")
            return
        if len(parts) < 2:
            try:
                node = parse_expression(content, s.ectx)
                value = evaluate(node, s.env, s.universe)
            except MathInputError as exc:
                vb.step(i, "expr", StepStatus.ERROR, exc.message, code=exc.code)
                return
            del value  # evaluated only to report errors in the expression
            vb.step(
                i, "expr", StepStatus.UNCHECKED, latex=node_latex(node), code="SET_STEP_UNLABELED"
            )
            return
        values: list[frozenset | int] = []
        pieces: list[str] = []
        for part in parts:
            try:
                value, tex = self._side(part, s)
            except MathInputError as exc:
                vb.step(i, "expr", StepStatus.ERROR, exc.message, code=exc.code)
                return
            values.append(value)
            pieces.append(tex)
        tex = " = ".join(pieces)
        kinds = {isinstance(v, frozenset) for v in values}
        if len(kinds) > 1:
            vb.error(i, "expr", "SET_STEP_MIXED", latex=tex)
            return
        for left, right in zip(values, values[1:], strict=False):
            if left != right:
                vb.error(i, "expr", "SET_STEP_NOT_EQUAL", latex=tex)
                if vb.first_error == i and isinstance(left, frozenset):
                    self.diagnose(vb, right, left, step=i)  # type: ignore[arg-type]
                return
        vb.ok(i, "expr", hints.message("SET_STEP_OK"), latex=tex)

    @staticmethod
    def _side(part: str, s: _Setup) -> tuple[frozenset | int, str]:
        t = part.strip()
        if t.startswith("|") and t.endswith("|") and len(t) > 2:
            node = parse_expression(t[1:-1], s.ectx)
            value = evaluate(node, s.env, s.universe)
            return len(value), rf"\left|{node_latex(node)}\right|"
        if t and (t[0].isdigit() or t[0] == "-"):
            n = _parse_count(t)
            return n, str(n)
        node = parse_expression(t, s.ectx)
        return evaluate(node, s.env, s.universe), node_latex(node)

    def grade_set(
        self,
        vb: VerdictBuilder,
        problem: Problem,
        params: FiniteSetParams,
        s: _Setup,
        text: str,
        key: frozenset,
    ) -> None:
        try:
            student = parse_literal(text, s.ectx)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        tex = latex(student)
        if student == key:
            vb.answer(VerdictStatus.CORRECT, latex=tex, code="CORRECT")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=tex, code="WRONG")
        mistake = self.match_mistake(
            problem, student, lambda t: parse_literal(t, s.ectx), lambda a, b: a == b
        )
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
            return
        if self._naturals_zero(params, s, student):
            vb.hint("SET_NATURALS_ZERO")
            return
        self.diagnose(vb, student, key)

    def _naturals_zero(self, params: FiniteSetParams, s: _Setup, student: object) -> bool:
        if params.compute is None or not _uses_naturals(params):
            return False
        try:
            alt = self.computed(s, params, naturals_from=0)
        except (MathInputError, ValueError):
            return False
        if params.ask == "cardinality":
            return student == len(alt)
        return student == alt

    @staticmethod
    def diagnose(
        vb: VerdictBuilder, student: frozenset, key: frozenset, *, step: int | None = None
    ) -> None:
        """Explain how ``student`` differs from ``key`` without listing what's missing."""
        if key == frozenset({student}) or student == frozenset({key}):
            vb.hint("SET_BRACES", step=step)
            return
        if flatten_tuples(student) == flatten_tuples(key):
            vb.hint("SET_TUPLE_GROUPING", step=step)
            return
        if key and all(isinstance(x, tuple) and len(x) == 2 for x in key):
            if (
                frozenset(
                    (x[1], x[0]) if isinstance(x, tuple) and len(x) == 2 else x for x in student
                )
                == key
            ):
                vb.hint("SET_PAIRS_REVERSED", step=step)
                return
        key_lengths = tuple_lengths(key)
        if len(key_lengths) == 1 and 0 not in key_lengths and key_lengths != tuple_lengths(student):
            if student:
                vb.hint("SET_TUPLE_LENGTH", step=step, n=next(iter(key_lengths)))
                return
        if frozenset() in key and frozenset() not in student:
            vb.hint("SET_EMPTY_MISSING", step=step)
        extra = [x for x in student if x not in key]
        missing = [x for x in key if x not in student]
        if extra:
            shown = ", ".join(f"${latex(x)}$" for x in sorted(extra, key=sort_key)[:5])
            more = f" (and {len(extra) - 5} more)" if len(extra) > 5 else ""
            vb.hint("SET_EXTRA", step=step, elements=shown + more)
        if missing:
            vb.hint("SET_MISSING", step=step, count=len(missing))

    def grade_count(
        self,
        vb: VerdictBuilder,
        problem: Problem,
        params: FiniteSetParams,
        s: _Setup,
        text: str,
        key: int,
    ) -> None:
        try:
            n = _parse_count(text)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        if n == key:
            vb.answer(VerdictStatus.CORRECT, latex=str(n), code="CORRECT")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=str(n), code="WRONG")
        mistake = self.match_mistake(problem, n, _parse_count, lambda a, b: a == b)
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
            return
        if self._naturals_zero(params, s, n):
            vb.hint("SET_NATURALS_ZERO")
            return
        if params.compute is not None:
            value = self.computed(s, params)
            inner = {count_leaves(value), count_members_deep(value)}
            inner |= {len(x) for x in value if isinstance(x, frozenset)}
            if n in inner - {key}:
                vb.hint("SET_COUNT_INNER")


def _uses_naturals(params: FiniteSetParams) -> bool:
    builders = [b for b in [params.compute, *params.sets.values()] if isinstance(b, Builder)]
    return any(b.domain == "N" for b in builders)


def _parse_count(text: str) -> int:
    try:
        value = MathContext.build().parse(text)
    except MathInputError as exc:
        raise MathInputError(hints.message("SET_NOT_COUNT"), "SET_NOT_COUNT") from exc
    if not (isinstance(value, sp.Integer) and value >= 0):
        raise MathInputError(hints.message("SET_NOT_COUNT"), "SET_NOT_COUNT")
    return int(value)
