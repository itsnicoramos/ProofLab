"""Logic (SPEC §5.1, Book of Proof Chapter 2): ``truth_table`` and ``logical_equivalence``.

Every verdict comes from evaluating formulas on every row of a truth table (at most 6 statement
letters, 64 rows). Rows are in the book's order (see ``engine/propositional.py``).

- ``truth_table``: the answer is the statement's final column (``ask: column``), or, for "find
  the truth values" exercises, the one assignment that satisfies the given facts
  (``ask: values``). Optional ``column`` steps are helper columns (``~P : F F T T``), each
  checked, like the helper columns in the book's tables.
- ``logical_equivalence``: show that two statements are equivalent, either by a chain of
  rewrites (``expr`` steps; each must be truth-table equivalent to the one before, starting
  from the left statement and ending at the right one) or by giving the truth-table columns of
  both statements (``column`` steps). With ``decide: true`` the answer is ``equivalent`` or
  ``not equivalent``, and a ``row`` step can show a row where the two differ.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from prooflab.engine import hints
from prooflab.engine.algebra import MathInputError
from prooflab.engine.checker import ContentError, TopicHandler, VerdictBuilder, register
from prooflab.engine.models import Problem, Step, StepStatus, Submission, VerdictStatus
from prooflab.engine.propositional import (
    Formula,
    LogicContext,
    column,
    column_text,
    diagnose_column,
    diagnose_rewrite,
    equivalent,
    first_difference,
    normalize_logic,
    other_orders,
    parse_assignment,
    parse_column,
    row_text,
    rows,
    same_statement,
    to_latex,
)

hints.register_many(
    {
        "LOGIC_SYNTAX": "ProofLab couldn't read that statement: {detail}",
        "LOGIC_AMBIGUOUS": "Add parentheses so ProofLab doesn't have to guess how this groups.",
        "LOGIC_BAD_ROW": "Write truth values like P = T, Q = F (one for each letter).",
        "TT_BAD_COLUMN": "Write a column as T/F values, one per row, like T T F T.",
        "TT_STEP_FORMAT": "Write a column step as statement : values, like ~P ∨ Q : T F T T.",
        "TT_WRONG_LENGTH": "This table has {rows} rows, but your column has {got} values.",
        "TT_COLUMN_OK": "This column is right.",
        "TT_COLUMN_WRONG": "This column has {count} wrong value(s).",
        "TT_ROWS_WRONG": "Wrong values: {count} of {total}.",
        "TT_ROW_ORDER": "Your values would be right with the rows in another order. List rows "
        "the book's way: the first letter is T in the top half and F in the bottom half, and "
        "the last letter alternates T, F, T, F.",
        "TT_ALL_FLIPPED": "Every value is flipped. Check the main connective, or a ~ in front.",
        "TT_NOTE": "Notes aren't checked.",
        "LOGIC_VALUES_WRONG": "With your values, ${statement}$ is {got}, but it's supposed to "
        "be {want}.",
        "LOGIC_VALUES_MISSING": "Give a value for each of {names}.",
        "LOGIC_STEP_OK": "Equivalent to the previous statement.",
        "LOGIC_STEP_NOT_EQUIVALENT": "This isn't equivalent to the statement before it: they "
        "differ when {row}.",
        "LOGIC_ROW_DIFFERS": "In this row the two statements have different truth values.",
        "LOGIC_ROW_SAME": "In this row both statements are {value}, so this row doesn't tell "
        "them apart.",
        "LOGIC_NO_WORK": "You went straight from one statement to the other. Add the rewrites "
        "in between, or give the truth-table columns of both statements.",
        "LOGIC_INCOMPLETE": "Everything checks out so far. Finish by reaching the other "
        "statement, or by giving the columns of both statements.",
        "LOGIC_EQUIVALENCE_SHOWN": "Both statements have the same truth table: they're "
        "logically equivalent.",
        "LOGIC_DECIDE_FORMAT": "Answer 'equivalent' or 'not equivalent'.",
        "LOGIC_LOOK_FOR_ROW": "Look for a row of the truth table where the two statements have "
        "different values.",
        "LOGIC_TRY_LAWS": "Compare the two full truth tables, or rewrite one statement with the "
        "laws of Section 2.6 (DeMorgan, distributive, P ⇒ Q = (~P) ∨ Q).",
        "LOGIC_NOTE": "Notes aren't checked.",
        # typical mistakes (engine/propositional.py mutations)
        "IMPLIES_CONVERSE": "Careful with the direction of ⇒: P ⇒ Q is not the same as its "
        "converse Q ⇒ P.",
        "IMPLIES_INVERSE": "P ⇒ Q is not equivalent to ~P ⇒ ~Q. Its contrapositive ~Q ⇒ ~P is.",
        "IMPLIES_AS_OR": "P ⇒ Q is equivalent to (~P) ∨ Q: the first statement gets negated.",
        "IMPLIES_AS_AND": "P ⇒ Q is true whenever P is false. It is false only when P is true "
        "and Q is false.",
        "IMPLIES_AS_IFF": "P ⇒ Q is true when P is false and Q is true; P ⇔ Q isn't.",
        "IFF_AS_IMPLIES": "P ⇔ Q needs both directions: it is false when P is false and Q is true.",
        "AND_OR_SWAPPED": "Check ∧ against ∨ somewhere: P ∧ Q needs both true, P ∨ Q needs at "
        "least one.",
        "NEGATION_DROPPED": "A ~ seems to have gone missing somewhere.",
        "DEMORGAN_CONNECTIVE": "DeMorgan's laws flip the connective: ~(P ∧ Q) = ~P ∨ ~Q and "
        "~(P ∨ Q) = ~P ∧ ~Q.",
        "NEGATION_SCOPE": "Check what the ~ applies to: ~(P ∨ Q) negates the whole statement, "
        "~P ∨ Q only P.",
    }
)


def _tf(value: bool) -> str:
    return "true" if value else "false"


def _letters(names: list[str] | None, *formulas: str) -> list[str]:
    if names:
        return names
    found: set[str] = set()
    for f in formulas:
        plain = re.sub(r"[A-Za-z]{2,}", " ", normalize_logic(f))  # drop words like 'and'
        found |= {ch for ch in plain if "A" <= ch <= "Z" and ch not in "TF"}
    return sorted(found)


class _LogicHandler(TopicHandler):
    """Shared step checking for both logic kinds."""

    @staticmethod
    def parse_formula(vb: VerdictBuilder, i: int, step: Step, ctx: LogicContext) -> Formula | None:
        try:
            return ctx.parse(step.content)
        except MathInputError as exc:
            vb.step(i, step.kind, StepStatus.ERROR, exc.message, code=exc.code)
            return None

    def check_column_step(
        self, vb: VerdictBuilder, i: int, step: Step, ctx: LogicContext
    ) -> tuple[Formula, bool] | None:
        """``formula : T F T T``. Returns the formula and whether the column is right."""
        if ":" not in step.content:
            vb.error(i, step.kind, "TT_STEP_FORMAT")
            return None
        left, _, right = step.content.rpartition(":")
        try:
            formula = ctx.parse(left)
            values = parse_column(right)
        except MathInputError as exc:
            vb.step(i, step.kind, StepStatus.ERROR, exc.message, code=exc.code)
            return None
        tex = f"{to_latex(formula)} : \\text{{{column_text(values)}}}"
        n = len(ctx.rows)
        if len(values) != n:
            vb.error(i, step.kind, "TT_WRONG_LENGTH", latex=tex, rows=n, got=len(values))
            return None
        truth = column(formula, ctx.variables)
        wrong = sum(a != b for a, b in zip(values, truth, strict=True))
        if not wrong:
            vb.ok(i, step.kind, hints.message("TT_COLUMN_OK"), latex=tex)
            return formula, True
        vb.error(i, step.kind, "TT_COLUMN_WRONG", latex=tex, count=wrong)
        if vb.first_error == i:
            self.diagnose_values(vb, formula, values, ctx, step=i)
        return formula, False

    @staticmethod
    def diagnose_values(
        vb: VerdictBuilder,
        formula: Formula,
        values: list[bool],
        ctx: LogicContext,
        *,
        step: int | None = None,
    ) -> None:
        truth = column(formula, ctx.variables)
        if all(a != b for a, b in zip(values, truth, strict=True)):
            vb.hint("TT_ALL_FLIPPED", step=step)
            return
        for order in other_orders(ctx.variables):
            if column(formula, ctx.variables, order) == values:
                vb.hint("TT_ROW_ORDER", step=step)
                return
        code = diagnose_column(formula, values, ctx.variables)
        if code is not None:
            vb.hint(code, step=step)


# --------------------------------------------------------------------------- truth tables


class Constraint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    formula: str
    value: bool


class TruthTableParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    formula: str | None = None  # ask: column
    variables: list[str] | None = None  # table order; default: letters in alphabetical order
    ask: Literal["column", "values"] = "column"
    constraints: list[Constraint] = Field(default_factory=list)  # ask: values
    solve_for: list[str] | None = None  # ask: values; default: every letter


@register
class TruthTableHandler(_LogicHandler):
    kind = "truth_table"
    Params = TruthTableParams
    step_kinds = frozenset({"column", "note"})
    syntax_help = (
        "Connectives: ~ (not), ∧ or & (and), ∨ or | (or), ⇒ or => (implies), ⇔ or <=> (iff). "
        "Give a column as T/F values, one per row, top to bottom: the first letter is T in the "
        "top half and F in the bottom half, and the last letter alternates T, F, T, F. Optional "
        "'column' steps are helper columns, like ~P : F F T T. For truth values, write "
        "P = T, Q = F."
    )

    def setup(self, problem: Problem, p: TruthTableParams) -> LogicContext:
        texts = [p.formula or ""] + [c.formula for c in p.constraints]
        return LogicContext.build(_letters(p.variables, *texts))

    def validate(self, problem: Problem, params: TruthTableParams) -> None:
        try:
            ctx = self.setup(problem, params)
            if params.ask == "column":
                if params.formula is None or params.constraints:
                    raise ValueError("ask: column needs 'formula' and no constraints")
                ctx.parse(params.formula)
                parse_column(problem.answer)
            else:
                if not params.constraints:
                    raise ValueError("ask: values needs constraints")
                if len(self.solutions(ctx, params)) != 1:
                    raise ValueError("the constraints must have exactly one solution")
                self.parse_values(ctx, params, problem.answer)
        except (MathInputError, ValueError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def solve_vars(self, ctx: LogicContext, p: TruthTableParams) -> list[str]:
        return list(p.solve_for or ctx.variables)

    def solutions(self, ctx: LogicContext, p: TruthTableParams) -> set[tuple[bool, ...]]:
        """Distinct values of the ``solve_for`` letters over rows meeting every constraint."""
        formulas = [(ctx.parse(c.formula), c.value) for c in p.constraints]
        names = self.solve_vars(ctx, p)
        out: set[tuple[bool, ...]] = set()
        for row in rows(len(ctx.variables)):
            env = dict(zip(ctx.variables, row, strict=True))
            if all(f.value(env) == want for f, want in formulas):
                out.add(tuple(env[n] for n in names))
        return out

    def parse_values(self, ctx: LogicContext, p: TruthTableParams, text: str) -> dict[str, bool]:
        names = self.solve_vars(ctx, p)
        values = parse_assignment(text, ctx.variables)
        missing = [n for n in names if n not in values]
        if missing:
            raise MathInputError(
                hints.message("LOGIC_VALUES_MISSING", names=", ".join(names)),
                "LOGIC_VALUES_MISSING",
            )
        return values

    def verify_key(self, problem: Problem, params: TruthTableParams) -> bool | None:
        ctx = self.setup(problem, params)
        if params.ask == "column":
            formula = ctx.parse(params.formula or "")
            return column(formula, ctx.variables) == parse_column(problem.answer)
        names = self.solve_vars(ctx, params)
        key = self.parse_values(ctx, params, problem.answer)
        return self.solutions(ctx, params) == {tuple(key[n] for n in names)}

    def check(
        self,
        problem: Problem,
        params: TruthTableParams,
        submission: Submission,
        vb: VerdictBuilder,
    ) -> None:
        ctx = self.setup(problem, params)
        for i, step in enumerate(submission.steps):
            if step.kind == "note":
                vb.step(i, step.kind, StepStatus.UNCHECKED, code="TT_NOTE")
            else:
                self.check_column_step(vb, i, step, ctx)
        text = (submission.answer or "").strip()
        if not text:
            return
        if params.ask == "column":
            self.grade_column(vb, ctx, ctx.parse(params.formula or ""), text)
        else:
            self.grade_values(vb, ctx, params, problem, text)

    def grade_column(
        self, vb: VerdictBuilder, ctx: LogicContext, formula: Formula, text: str
    ) -> None:
        try:
            values = parse_column(text)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        tex = rf"\text{{{column_text(values)}}}"
        n = len(ctx.rows)
        if len(values) != n:
            vb.answer(
                VerdictStatus.INVALID, latex=tex, code="TT_WRONG_LENGTH", rows=n, got=len(values)
            )
            return
        truth = column(formula, ctx.variables)
        wrong = sum(a != b for a, b in zip(values, truth, strict=True))
        if not wrong:
            vb.answer(VerdictStatus.CORRECT, latex=tex, code="CORRECT")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=tex, code="WRONG")
        vb.hint("TT_ROWS_WRONG", count=wrong, total=n)
        self.diagnose_values(vb, formula, values, ctx)

    def grade_values(
        self,
        vb: VerdictBuilder,
        ctx: LogicContext,
        params: TruthTableParams,
        problem: Problem,
        text: str,
    ) -> None:
        names = self.solve_vars(ctx, params)
        try:
            values = self.parse_values(ctx, params, text)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        tex = r"\text{" + row_text(values, ctx.variables) + "}"
        key = self.parse_values(ctx, params, problem.answer)
        if all(values[n] == key[n] for n in names):
            vb.answer(VerdictStatus.CORRECT, latex=tex, code="CORRECT")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=tex, code="WRONG")
        if any(n not in values for n in ctx.variables):
            return  # can't evaluate the facts without every letter
        for c in params.constraints:
            f = ctx.parse(c.formula)
            got = f.value(values)
            if got != c.value:
                vb.hint(
                    "LOGIC_VALUES_WRONG", statement=to_latex(f), got=_tf(got), want=_tf(c.value)
                )
                return


# --------------------------------------------------------------------------- equivalence


class EquivalenceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left: str
    right: str
    variables: list[str] | None = None
    decide: bool = False  # True: the answer is 'equivalent' or 'not equivalent'


_NO_WORDS = {"not", "no", "inequivalent", "nonequivalent", "isnt", "arent", "false", "non"}
_YES_WORDS = {"equivalent", "yes", "equiv", "true", "same"}


def parse_decision(text: str) -> bool:
    words = set(re.findall(r"[a-z]+", text.lower().replace("'", "")))
    if words & _NO_WORDS:
        return False
    if words & _YES_WORDS:
        return True
    raise MathInputError(hints.message("LOGIC_DECIDE_FORMAT"), "LOGIC_DECIDE_FORMAT")


@register
class LogicalEquivalenceHandler(_LogicHandler):
    kind = "logical_equivalence"
    Params = EquivalenceParams
    step_kinds = frozenset({"expr", "column", "row", "note"})
    syntax_help = (
        "Connectives: ~ (not), ∧ or & (and), ∨ or | (or), ⇒ or => (implies), ⇔ or <=> (iff). "
        "Either rewrite step by step from the left statement to the right one ('step': each "
        "must be equivalent to the one before), or give both truth-table columns ('column': "
        "statement : T F T T, rows top to bottom with the first letter T in the top half). A "
        "'row' step like P = T, Q = F shows a row where two statements differ."
    )

    def setup(
        self, problem: Problem, p: EquivalenceParams
    ) -> tuple[LogicContext, Formula, Formula]:
        ctx = LogicContext.build(_letters(p.variables, p.left, p.right))
        return ctx, ctx.parse(p.left), ctx.parse(p.right)

    def has_answer(self, problem: Problem, params: EquivalenceParams) -> bool:
        return params.decide

    def validate(self, problem: Problem, params: EquivalenceParams) -> None:
        try:
            self.setup(problem, params)
            if params.decide:
                parse_decision(problem.answer)
            elif problem.answer:
                raise ValueError("a 'show' problem has no answer key")
        except (MathInputError, ValueError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def verify_key(self, problem: Problem, params: EquivalenceParams) -> bool | None:
        ctx, left, right = self.setup(problem, params)
        same = equivalent(left, right, ctx.variables)
        if params.decide:
            return parse_decision(problem.answer) == same
        return same

    def check(
        self,
        problem: Problem,
        params: EquivalenceParams,
        submission: Submission,
        vb: VerdictBuilder,
    ) -> None:
        ctx, left, right = self.setup(problem, params)
        chain: list[Formula] = []
        prev = left
        shown_columns: list[Formula] = []
        for i, step in enumerate(submission.steps):
            if step.kind == "note":
                vb.step(i, step.kind, StepStatus.UNCHECKED, code="LOGIC_NOTE")
            elif step.kind == "column":
                result = self.check_column_step(vb, i, step, ctx)
                if result is not None and result[1]:
                    shown_columns.append(result[0])
            elif step.kind == "row":
                self.check_row(vb, i, step, ctx, left, right)
            else:
                formula = self.parse_formula(vb, i, step, ctx)
                if formula is None:
                    continue
                tex = to_latex(formula)
                diff = first_difference(prev, formula, ctx.variables)
                if diff is None:
                    vb.ok(i, step.kind, hints.message("LOGIC_STEP_OK"), latex=tex)
                else:
                    vb.error(
                        i,
                        step.kind,
                        "LOGIC_STEP_NOT_EQUIVALENT",
                        latex=tex,
                        row=row_text(diff, ctx.variables),
                    )
                    if vb.first_error == i:
                        code = diagnose_rewrite(prev, formula, ctx.variables)
                        if code is not None:
                            vb.hint(code, step=i)
                chain.append(formula)
                prev = formula

        if params.decide:
            self.grade_decision(vb, ctx, left, right, submission.answer)
            return
        if not submission.steps:
            vb.hint("EMPTY_SUBMISSION")
            vb.set_status(VerdictStatus.INCORRECT)
            return
        if vb.first_error is not None:
            vb.set_status(VerdictStatus.INCORRECT)
            return
        table = any(same_statement(f, left) for f in shown_columns) and any(
            same_statement(f, right) for f in shown_columns
        )
        forwards = bool(chain) and same_statement(chain[-1], right)
        backwards = (
            len(chain) > 1 and same_statement(chain[0], right) and same_statement(chain[-1], left)
        )
        work = any(not (same_statement(f, left) or same_statement(f, right)) for f in chain)
        if table or ((forwards or backwards) and work):
            vb.answer(VerdictStatus.CORRECT, code="LOGIC_EQUIVALENCE_SHOWN")
            vb.set_status(VerdictStatus.CORRECT)
        elif forwards or backwards:
            vb.hint("LOGIC_NO_WORK")
            vb.set_status(VerdictStatus.PARTIAL)
        else:
            vb.hint("LOGIC_INCOMPLETE")
            vb.set_status(VerdictStatus.PARTIAL)

    def check_row(
        self,
        vb: VerdictBuilder,
        i: int,
        step: Step,
        ctx: LogicContext,
        left: Formula,
        right: Formula,
    ) -> None:
        try:
            env = parse_assignment(step.content, ctx.variables)
        except MathInputError as exc:
            vb.step(i, step.kind, StepStatus.ERROR, exc.message, code=exc.code)
            return
        missing = [v for v in ctx.variables if v not in env]
        if missing:
            vb.error(i, step.kind, "LOGIC_VALUES_MISSING", names=", ".join(ctx.variables))
            return
        tex = r"\text{" + row_text(env, ctx.variables) + "}"
        a, b = left.value(env), right.value(env)
        if a != b:
            vb.ok(i, step.kind, hints.message("LOGIC_ROW_DIFFERS"), latex=tex)
        else:
            vb.error(i, step.kind, "LOGIC_ROW_SAME", latex=tex, value=_tf(a))

    def grade_decision(
        self,
        vb: VerdictBuilder,
        ctx: LogicContext,
        left: Formula,
        right: Formula,
        answer: str | None,
    ) -> None:
        text = (answer or "").strip()
        if not text:
            return
        try:
            said = parse_decision(text)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        truth = equivalent(left, right, ctx.variables)
        label = r"\text{" + ("equivalent" if said else "not equivalent") + "}"
        if said == truth:
            vb.answer(VerdictStatus.CORRECT, latex=label, code="CORRECT")
            return
        vb.answer(VerdictStatus.INCORRECT, latex=label, code="WRONG")
        vb.hint("LOGIC_LOOK_FOR_ROW" if said else "LOGIC_TRY_LAWS")
