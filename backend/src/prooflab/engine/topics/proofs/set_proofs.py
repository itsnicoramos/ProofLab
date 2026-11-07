"""Proofs involving sets (SPEC §5.1, Book of Proof Chapter 8): ``set_identity``.

Prove that two sets are equal, like A ∪ (B ∩ C) = (A ∪ B) ∩ (A ∪ C), as a chain of lines that
each describe the same set as the line before. A line is either

- a set expression: ``A ∪ (B ∩ C)``, ``(A − B) ∩ (A − C)``, ``(A ∩ B)'`` (complement), ``A × B``
- or a statement about an element, the book's element-chasing style:
  ``x ∈ A or (x ∈ B and x ∈ C)``, ``(x, y) ∈ A × (B ∪ C)``, ``x ∉ B``.

Every line is translated into a statement about membership ("x ∈ A" becomes a statement
letter), and two lines describe the same set exactly when those statements have the same truth
table. So each step is checked on every possible way an element can sit in the sets: the
verdict is exact, never a guess. Products use one letter per set and coordinate.

The proof is complete when the chain ends at the right side and shows some work: a line that is
neither side, or membership unpacked into and/or/not (going straight from one side to the other
isn't a proof).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from prooflab.engine import hints
from prooflab.engine.algebra import MAX_INPUT_CHARS, MathInputError
from prooflab.engine.checker import ContentError, TopicHandler, VerdictBuilder, register
from prooflab.engine.models import Problem, StepStatus, Submission, VerdictStatus
from prooflab.engine.propositional import Formula, equivalent, first_difference

hints.register_many(
    {
        "SETID_SYNTAX": "ProofLab couldn't read that: {detail}",
        "SETID_STEP_OK": "Same elements as the line before.",
        "SETID_FIRST_OK": "This is the left side.",
        "SETID_STEP_DIFFERS": "This doesn't match the line before: they disagree about an element "
        "with {row}.",
        "SETID_FIRST_DIFFERS": "Start from the left side, ${left}$. This line disagrees with it "
        "about an element with {row}.",
        "SETID_NO_WORK": "You went straight from one side to the other. Show the steps in between: "
        "what membership in a side means (x ∈ … and/or …), or one set law at a time.",
        "SETID_INCOMPLETE": "Everything checks out so far. Finish with the right side, ${right}$.",
        "SETID_PROVED": "Proof complete: every line has exactly the same elements, from ${left}$ "
        "to "
        "${right}$. ∎",
        "SETID_NOTE": "Notes aren't checked.",
    }
)

_ALIASES = [
    (r"\\setminus|\\smallsetminus", "−"),
    (r"\\cup|\bunion\b|\bcup\b", "∪"),
    (r"\\cap|\bintersect(?:ion)?\b|\bcap\b", "∩"),
    (r"\\times|\btimes\b", "×"),
    (r"\\emptyset|\\varnothing|\bemptyset\b|\{\s*\}", "∅"),
    (r"\\notin|\bnot\s+in\b|\bnotin\b", "∉"),
    (r"\\in\b|\bin\b|\belement\s+of\b", "∈"),
    (r"\\land|\\wedge|\band\b|/\\", "∧"),
    (r"\\lor|\\vee|\bor\b|\\/", "∨"),
    (r"\\neg|\\lnot|\bnot\b", "¬"),
    (r"\^\s*[cC]\b|ᶜ|′|’", "'"),
]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    # A combining overline/macron after a letter or ')' means complement: Ā → A'
    text = re.sub(r"[\u0304\u0305]", "'", text)
    text = unicodedata.normalize("NFC", text)
    for pattern, repl in _ALIASES:
        text = re.sub(pattern, repl, text)
    return (
        text.replace("Ø", "∅")
        .replace("ø", "∅")
        .replace("&", "∧")
        .replace("|", "∨")
        .replace("~", "¬")
        .replace("\\", "−")
        .replace("-", "−")
        .replace("*", "×")
    )


# --------------------------------------------------------------------------- syntax tree


@dataclass(frozen=True)
class Node:
    op: str  # set, empty, universe, union, inter, diff, comp, prod | in, notin, and, or, not
    args: tuple[Node, ...] = ()
    name: str = ""  # set letter; for in/notin: the point, e.g. "x" or "x,y"


_SET_OPS = {"∪": "union", "∩": "inter", "−": "diff", "×": "prod"}
_LOGIC_OPS = {"∧": "and", "∨": "or"}


class _Parser:
    def __init__(self, text: str, sets: list[str], universe: bool) -> None:
        if len(text) > MAX_INPUT_CHARS:
            raise MathInputError("That line is too long.", "SETID_SYNTAX")
        self.tokens = self._tokenize(_normalize(text))
        self.pos = 0
        self.sets = sets
        self.universe = universe

    @staticmethod
    def _tokenize(src: str) -> list[str]:
        tokens: list[str] = []
        i = 0
        while i < len(src):
            ch = src[i]
            if ch.isspace():
                i += 1
            elif ch in "()∪∩−×∅∈∉∧∨¬',":
                tokens.append(ch)
                i += 1
            elif ch.isalpha():
                tokens.append(ch)  # one letter per name: sets are capitals, elements lowercase
                i += 1
            elif ch.isdigit():
                j = i
                while j < len(src) and src[j].isdigit():
                    j += 1
                tokens.append(src[i:j])  # subscripts like A1 are written A1 → "A", "1"
                i = j
            else:
                raise _error(f"'{ch}' isn't a symbol ProofLab knows here.")
        return tokens

    # -- helpers
    def peek(self, offset: int = 0) -> str | None:
        k = self.pos + offset
        return self.tokens[k] if k < len(self.tokens) else None

    def take(self, expected: str | None = None) -> str:
        tok = self.peek()
        if tok is None or (expected is not None and tok != expected):
            raise _error(f"expected '{expected}'" if expected else "the line ends too early")
        self.pos += 1
        return tok

    def done(self) -> None:
        if self.peek() is not None:
            raise _error(f"unexpected '{self.peek()}'")

    # -- statements
    def statement(self) -> Node:
        left = self._not()
        op = None
        args = [left]
        while self.peek() in _LOGIC_OPS:
            tok = self.take()
            if op is not None and _LOGIC_OPS[tok] != op:
                raise _error("add parentheses: ProofLab won't guess how 'and' and 'or' group")
            op = _LOGIC_OPS[tok]
            args.append(self._not())
        return Node(op, tuple(args)) if op else left

    def _not(self) -> Node:
        if self.peek() == "¬":
            self.take()
            return Node("not", (self._not(),))
        return self._membership()

    def _point(self) -> str | None:
        """``x`` or ``(x, y)`` followed by ∈/∉, without consuming anything otherwise."""
        tok = self.peek()
        if tok is not None and tok.isalpha() and tok.islower() and self.peek(1) in ("∈", "∉"):
            self.pos += 1
            return tok
        if (
            tok == "("
            and (a := self.peek(1)) is not None
            and a.islower()
            and self.peek(2) == ","
            and (b := self.peek(3)) is not None
            and b.islower()
            and self.peek(4) == ")"
            and self.peek(5) in ("∈", "∉")
        ):
            self.pos += 5
            return f"{a},{b}"
        return None

    def _membership(self) -> Node:
        point = self._point()
        if point is not None:
            op = "in" if self.take() == "∈" else "notin"
            return Node(op, (self.set_expr(),), point)
        if self.peek() == "(":
            self.take("(")
            inner = self.statement()
            self.take(")")
            return inner
        raise _error("write a statement like x ∈ A, or a set like A ∪ B")

    # -- sets
    def set_expr(self) -> Node:
        left = self._set_term()
        op = None
        args = [left]
        while self.peek() in _SET_OPS:
            tok = self.take()
            name = _SET_OPS[tok]
            if op is not None and (name != op or name in ("diff", "prod")):
                raise _error("add parentheses: ProofLab won't guess how ∪, ∩, − and × group")
            op = name
            args.append(self._set_term())
        return Node(op, tuple(args)) if op else left

    def _set_term(self) -> Node:
        tok = self.peek()
        if tok == "(":
            self.take("(")
            node = self.set_expr()
            self.take(")")
        elif tok == "∅":
            self.take()
            node = Node("empty")
        elif tok is not None and tok.isalpha() and tok.isupper():
            self.take()
            name = tok + (self.take() if (self.peek() or "").isdigit() else "")
            if name in self.sets:
                node = Node("set", name=name)
            elif name == "U" and self.universe:
                node = Node("universe")
            else:
                raise _error(f"{name} isn't one of this problem's sets ({', '.join(self.sets)})")
        else:
            raise _error("expected a set, like A or (A ∪ B)")
        while self.peek() == "'":
            self.take()
            node = Node("comp", (node,))
        return node


def _error(detail: str) -> MathInputError:
    return MathInputError(hints.message("SETID_SYNTAX", detail=detail), "SETID_SYNTAX")


def parse_line(text: str, sets: list[str], universe: bool) -> Node:
    """A statement if it mentions ∈/∉, otherwise a set expression."""
    p = _Parser(text, sets, universe)
    if not p.tokens:
        raise _error("the line is empty")
    node = p.statement() if any(t in ("∈", "∉") for t in p.tokens) else p.set_expr()
    p.done()
    return node


# --------------------------------------------------------------------------- meaning


def _atom(name: str, coord: int) -> Formula:
    return Formula("var", name=name if coord == 0 else f"{name}@{coord}")


def set_formula(node: Node, coords: tuple[int, ...]) -> Formula:
    """The statement "the point is in this set". ``coords`` is (0,) for elements, (1, 2) for
    pairs."""
    op = node.op
    if op == "prod":
        if len(coords) != 2:
            raise _error("a product like A × B contains pairs; compare it with (x, y) ∈ …")
        left, right = node.args
        return Formula("and", (set_formula(left, (1,)), set_formula(right, (2,))))
    if op in ("set", "empty", "universe") and len(coords) == 2:
        raise _error("the sides of this problem contain pairs: use products like A × B")
    if op == "set":
        return _atom(node.name, coords[0])
    if op == "empty":
        return Formula("const", name="F")
    if op == "universe":
        return Formula("const", name="T")
    if op == "union":
        return Formula("or", tuple(set_formula(a, coords) for a in node.args))
    if op == "inter":
        return Formula("and", tuple(set_formula(a, coords) for a in node.args))
    if op == "diff":
        a, b = node.args
        return Formula("and", (set_formula(a, coords), Formula("not", (set_formula(b, coords),))))
    if op == "comp":
        if len(coords) == 2:
            raise _error("complements of sets of pairs aren't supported here")
        return Formula("not", (set_formula(node.args[0], coords),))
    raise _error("expected a set")


def line_formula(node: Node, point: list[str]) -> Formula:
    """The statement a line makes about the problem's element (or pair)."""
    op = node.op
    if op in ("in", "notin"):
        names = node.name.split(",")
        if len(point) == 1:
            if len(names) != 1:
                raise _error("the elements here are single elements, not pairs")
            coords: tuple[int, ...] = (0,)
        elif len(names) == 2:
            coords = (1, 2)
        elif names[0] in point:
            coords = (point.index(names[0]) + 1,)
        else:
            raise _error(f"name the coordinates {' and '.join(point)}, like {point[0]} ∈ A")
        f = set_formula(node.args[0], coords)
        return f if op == "in" else Formula("not", (f,))
    if op == "not":
        return Formula("not", (line_formula(node.args[0], point),))
    if op in ("and", "or"):
        return Formula(op, tuple(line_formula(a, point) for a in node.args))
    return set_formula(node, (0,) if len(point) == 1 else (1, 2))


def _canon(f: Formula) -> Formula:
    """Flatten and sort ∧/∨ so A ∪ B and B ∪ A count as the same written line."""
    if f.op in ("and", "or"):
        flat: list[Formula] = []
        for a in f.args:
            ca = _canon(a)
            flat.extend(ca.args if ca.op == f.op else (ca,))
        return Formula(f.op, tuple(sorted(flat, key=repr)))
    if f.args:
        return Formula(f.op, tuple(_canon(a) for a in f.args), f.name)
    return f


def _unpacked(node: Node) -> bool:
    """A statement that spells membership out with and/or/not (element chasing)."""
    return node.op in ("and", "or", "not")


# --------------------------------------------------------------------------- rendering

_LATEX = {"union": r"\cup", "inter": r"\cap", "diff": "-", "prod": r"\times"}


def to_latex(node: Node, parent: str | None = None) -> str:
    op = node.op
    if op == "set":
        return re.sub(r"^([A-Z])(\d+)$", r"\1_{\2}", node.name)
    if op == "empty":
        return r"\emptyset"
    if op == "universe":
        return "U"
    if op == "comp":
        return r"\overline{" + to_latex(node.args[0]) + "}"
    if op in ("in", "notin"):
        point = node.name if "," not in node.name else "(" + node.name.replace(",", ", ") + ")"
        rel = r"\in" if op == "in" else r"\notin"
        out = f"{point} {rel} {to_latex(node.args[0])}"
        return f"({out})" if parent in ("and", "or") and len(node.args[0].args) > 1 else out
    if op == "not":
        return r"\neg " + to_latex(node.args[0], "not")
    if op in ("and", "or"):
        joiner = r" \text{ and } " if op == "and" else r" \text{ or } "
        out = joiner.join(to_latex(a, op) for a in node.args)
        return f"({out})" if parent in ("and", "or", "not") else out
    out = f" {_LATEX[op]} ".join(to_latex(a, op) for a in node.args)
    return f"({out})" if parent is not None else out


def _row_text(env: dict[str, bool], point: list[str]) -> str:
    parts = []
    for name in sorted(env, key=lambda n: (n.split("@")[-1] if "@" in n else "0", n)):
        if "@" in name:
            letter, coord = name.split("@")
            who = point[int(coord) - 1]
        else:
            letter, who = name, point[0]
        rel = "∈" if env[name] else "∉"
        parts.append(f"${who} {rel} {to_latex(Node('set', name=letter))}$")
    return ", ".join(parts)


# --------------------------------------------------------------------------- handler


class SetIdentityParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sets: list[str] = Field(min_length=1, max_length=6)
    left: str
    right: str
    #: the element's name, or two names for pairs (products)
    point: list[str] = Field(default_factory=lambda: ["x"], min_length=1, max_length=2)
    #: "U" means the universal set (for complements)
    universe: bool = False


@dataclass(frozen=True)
class _Sides:
    left: Formula
    right: Formula
    left_latex: str
    right_latex: str
    variables: tuple[str, ...]


@register
class SetIdentityHandler(TopicHandler):
    kind = "set_identity"
    Params = SetIdentityParams
    step_kinds = frozenset({"expr", "note"})
    syntax_help = (
        "Each line is a set (A ∪ (B ∩ C), A − B, A' for the complement, A × B) or a statement "
        "about an element (x ∈ A or (x ∈ B and x ∈ C)). Type ∪ as 'union', ∩ as 'intersect', "
        "∈ as 'in', ∉ as 'not in'. Each line must have the same elements as the line before; "
        "end with the right side."
    )

    def has_answer(self, problem: Problem, params: SetIdentityParams) -> bool:
        return False

    def sides(self, problem: Problem, params: SetIdentityParams) -> _Sides:
        try:
            ln = parse_line(params.left, params.sets, params.universe)
            rn = parse_line(params.right, params.sets, params.universe)
            lf, rf = line_formula(ln, params.point), line_formula(rn, params.point)
        except MathInputError as exc:
            raise ContentError(f"{problem.id}: {exc.message}") from exc
        names = set(params.sets)
        coords = [0] if len(params.point) == 1 else [1, 2]
        variables = tuple(
            n if c == 0 else f"{n}@{c}"
            for c in coords
            for n in sorted(names)
            if (n if c == 0 else f"{n}@{c}") in (lf.variables() | rf.variables())
        )
        if len(variables) > 6:
            raise ContentError(f"{problem.id}: at most 6 set/coordinate letters")
        return _Sides(lf, rf, to_latex(ln), to_latex(rn), variables)

    def validate(self, problem: Problem, params: SetIdentityParams) -> None:
        s = self.sides(problem, params)
        if not equivalent(s.left, s.right, s.variables):
            raise ContentError(f"{problem.id}: the two sides aren't equal sets")

    def verify_key(self, problem: Problem, params: SetIdentityParams) -> bool | None:
        s = self.sides(problem, params)
        return equivalent(s.left, s.right, s.variables)

    def check(
        self,
        problem: Problem,
        params: SetIdentityParams,
        submission: Submission,
        vb: VerdictBuilder,
    ) -> None:
        s = self.sides(problem, params)
        prev = s.left
        chain: list[tuple[Formula, Node]] = []
        for i, step in enumerate(submission.steps):
            if step.kind == "note":
                vb.step(i, "note", StepStatus.UNCHECKED, code="SETID_NOTE")
                continue
            try:
                node = parse_line(step.content, params.sets, params.universe)
                f = line_formula(node, params.point)
            except MathInputError as exc:
                vb.step(i, step.kind, StepStatus.ERROR, exc.message, code=exc.code)
                continue
            latex = to_latex(node)
            variables = tuple(sorted(set(s.variables) | f.variables()))
            if equivalent(prev, f, variables):
                code = (
                    "SETID_FIRST_OK"
                    if not chain and _canon(f) == _canon(s.left)
                    else "SETID_STEP_OK"
                )
                vb.ok(i, step.kind, hints.message(code), latex=latex)
            else:
                env = first_difference(prev, f, variables) or {}
                row = _row_text(env, params.point)
                if not chain:
                    vb.error(
                        i, step.kind, "SETID_FIRST_DIFFERS", latex=latex, left=s.left_latex, row=row
                    )
                else:
                    vb.error(i, step.kind, "SETID_STEP_DIFFERS", latex=latex, row=row)
            chain.append((f, node))
            prev = f

        if not submission.steps:
            vb.hint("EMPTY_SUBMISSION")
            vb.set_status(VerdictStatus.INCORRECT)
            return
        first_error = vb.first_error
        if first_error is not None:
            vb.answer(VerdictStatus.INCORRECT, code="PROOF_HAS_ERRORS", step_number=first_error + 1)
            vb.set_status(VerdictStatus.INCORRECT)
            return
        reached = bool(chain) and _canon(chain[-1][0]) == _canon(s.right)
        work = any(
            _unpacked(node) or _canon(f) not in (_canon(s.left), _canon(s.right))
            for f, node in chain
        )
        if reached and work:
            vb.answer(
                VerdictStatus.CORRECT, code="SETID_PROVED", left=s.left_latex, right=s.right_latex
            )
            vb.set_status(VerdictStatus.CORRECT)
        elif reached:
            vb.answer(VerdictStatus.PARTIAL, code="SETID_NO_WORK")
            vb.hint("SETID_NO_WORK")
            vb.set_status(VerdictStatus.PARTIAL)
        else:
            vb.answer(VerdictStatus.PARTIAL, code="SETID_INCOMPLETE", right=s.right_latex)
            vb.hint("SETID_INCOMPLETE", right=s.right_latex)
            vb.set_status(VerdictStatus.PARTIAL)
