"""Counting (SPEC §5.1, Book of Proof Chapter 3): ``count``.

The answer is a number of outcomes: an exact integer, written as the integer itself or as an
expression that evaluates to it (``26^4``, ``10!/(3!·7!)``, ``binom(10, 3)``). Steps are the
student's working; each one is evaluated and shown with its value, but only the final answer is
judged, because a count can be reached by many different correct routes. Authored ``mistakes``
catch the classic slips (order matters vs. not, repetition allowed vs. not) with a targeted hint.
"""

from __future__ import annotations

import re

import sympy as sp
from pydantic import BaseModel, ConfigDict

from prooflab.engine import hints
from prooflab.engine.algebra import MathContext, MathInputError, to_latex
from prooflab.engine.checker import ContentError, TopicHandler, VerdictBuilder, register
from prooflab.engine.models import Problem, StepStatus, Submission, VerdictStatus

hints.register_many(
    {
        "COUNT_NOT_INTEGER": "A count is a whole number, but this works out to {value}.",
        "COUNT_NEGATIVE": "A count can't be negative.",
        "COUNT_WORK": "This works out to {value}. Working steps are shown, not judged.",
        "COUNT_CORRECT": "Correct: there are {value} of them.",
        "COUNT_WRONG": "Not quite: {value} isn't the number of outcomes.",
        "COUNT_TOO_BIG": "That's more than there are: check whether you counted some outcomes "
        "more than once, for example by letting order matter when it doesn't.",
        "COUNT_TOO_SMALL": "That's fewer than there are: check whether you left some cases out.",
    }
)


class CountParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


_NUMBERS = MathContext.build()


# The book's notation (Section 3.4): P(n, k) = n!/(n − k)! and C(n, k) = binom(n, k). Only in
# counts, where there are no variables, so P and C can't be confused with a variable's name.
_PERM = re.compile(r"\bP\(\s*(\d+)\s*,\s*(\d+)\s*\)")
_CHOOSE = re.compile(r"\b(?:C|nCr)\(\s*(\d+)\s*,\s*(\d+)\s*\)")


def _book_notation(text: str) -> str:
    text = _PERM.sub(lambda m: f"(({m[1]})!/(({m[1]}) - ({m[2]}))!)", text)
    return _CHOOSE.sub(lambda m: f"binom({m[1]}, {m[2]})", text)


def evaluate_count(text: str) -> sp.Expr:
    """Parse and evaluate a count; raises MathInputError if it can't be read."""
    value = sp.nsimplify(sp.simplify(_NUMBERS.parse(_book_notation(text))))
    if not value.is_number:
        raise MathInputError("Write a number, or an expression with only numbers in it.")
    return value


@register
class CountHandler(TopicHandler):
    kind = "count"
    Params = CountParams
    step_kinds = frozenset({"expr", "note"})
    syntax_help = (
        "Give the count as a whole number or as an expression that works it out: 26^4, "
        "10!/(3! 7!), binom(10, 3) or C(10, 3) for 10 choose 3, P(10, 3) for 10!/7!. Steps "
        "are your working: each is evaluated so you can see its value, and only the final "
        "answer is judged."
    )

    def _key(self, problem: Problem) -> sp.Integer:
        try:
            value = evaluate_count(problem.answer)
        except MathInputError as exc:
            raise ContentError(f"{problem.id}: answer key: {exc.message}") from exc
        if not value.is_Integer or value < 0:
            raise ContentError(f"{problem.id}: a count must be a nonnegative integer")
        return sp.Integer(value)

    def validate(self, problem: Problem, params: CountParams) -> None:
        self._key(problem)
        for m in problem.mistakes:
            try:
                evaluate_count(m.answer)
            except MathInputError as exc:
                raise ContentError(f"{problem.id}: mistake {m.answer!r}: {exc.message}") from exc

    def verify_key(self, problem: Problem, params: CountParams) -> bool | None:
        return None  # the count comes from the book's setup; the examples are the check

    def check(
        self, problem: Problem, params: CountParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        for i, step in enumerate(submission.steps):
            if step.kind == "note":
                vb.step(i, step.kind, StepStatus.UNCHECKED, code="PROOF_NOTE")
                continue
            try:
                value = evaluate_count(step.content)
            except MathInputError as exc:
                vb.step(i, step.kind, StepStatus.ERROR, exc.message, code=exc.code)
                continue
            vb.step(
                i,
                step.kind,
                StepStatus.UNCHECKED,
                latex=to_latex(_NUMBERS.parse(_book_notation(step.content))),
                code="COUNT_WORK",
                value=f"${to_latex(value)}$",
            )

        text = submission.answer
        if text is None or not text.strip():
            return
        key = self._key(problem)
        try:
            value = evaluate_count(text)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        latex = to_latex(_NUMBERS.parse(_book_notation(text)))
        shown = f"${to_latex(value)}$"
        if not value.is_Integer:
            vb.answer(VerdictStatus.INCORRECT, latex=latex, code="COUNT_NOT_INTEGER", value=shown)
            return
        if value < 0:
            vb.answer(VerdictStatus.INCORRECT, latex=latex, code="COUNT_NEGATIVE")
            return
        if value == key:
            vb.answer(VerdictStatus.CORRECT, latex=latex, code="COUNT_CORRECT", value=shown)
            return
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code="COUNT_WRONG", value=shown)
        mistake = self.match_mistake(
            problem, value, evaluate_count, lambda a, b: bool(sp.simplify(a - b) == 0)
        )
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
        elif value > key:
            vb.hint("COUNT_TOO_BIG")
        else:
            vb.hint("COUNT_TOO_SMALL")
