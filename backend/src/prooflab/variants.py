"""ProofLab-made versions of existing problems with new numbers ("variants").

A variant keeps a problem's kind, structure, functions and exponents, and changes its integer
coefficients and constants (small, nonzero, at most 9 in size). Everything about it is computed,
never invented by hand: the answer key comes from SymPy (or from the propositional and finite-set
engines), and every variant is checked by the same rules as the content tests before it is
returned:

1. it is a valid :class:`Problem` (Pydantic),
2. the kind's handler accepts its data (``validate``),
3. ``verify_key`` does not reject its answer key, and
4. each sample submission gets the expected verdict from :func:`prooflab.engine.checker.check`.

Generation is deterministic: attempt ``a`` for seed ``s`` uses
``random.Random(f"{base.id}|{s}|{a}")``, so the same base and seed always give the same problem.
A variant's id is ``<base id>-v<seed>``; it is labelled as ProofLab-made (title, tags, citation
note) and is a ``draft``, because no person has reviewed it.
"""

from __future__ import annotations

import functools
import logging
import random
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import sympy as sp
from sympy.printing.str import StrPrinter

from prooflab.engine import finite_sets, hints
from prooflab.engine import propositional as logic
from prooflab.engine.algebra import (
    MathContext,
    MathInputError,
    equivalent,
    strip_label,
    to_latex,
)
from prooflab.engine.checker import check, get_handler
from prooflab.engine.models import Problem, StepStatus, Submission

log = logging.getLogger(__name__)

VARIANT_RE = re.compile(
    r"^(?P<base>[a-z0-9]+\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9-]*)-v(?P<seed>0|[1-9][0-9]{0,8})$"
)
MAX_SEED = 999_999_999
MAX_ATTEMPTS = 8
VARIANT_TAG = "prooflab-variant"
VARIANT_NOTE = "ProofLab-made version with new numbers; not an exercise in the book."
_BOOK_TAG = "book-of-proof"


# =========================================================================== public API


def variant_id(base_id: str, seed: int) -> str:
    """The id of variant ``seed`` of ``base_id``: ``<base_id>-v<seed>``."""
    return f"{base_id}-v{seed}"


def parse_variant_id(problem_id: str) -> tuple[str, int] | None:
    """``"calc1.derivatives.chain-rule-v7"`` → ``("calc1.derivatives.chain-rule", 7)``.

    The last ``-v<digits>`` wins, so a base id that itself ends in ``-v3`` round-trips. A real
    problem id can also match (``…-v3`` reads as variant 3 of ``…``), so look the id up in the
    registry first and only treat it as a variant when it isn't a problem.
    """
    m = VARIANT_RE.fullmatch(problem_id)
    if m is None:
        return None
    return m.group("base"), int(m.group("seed"))


def supported_kinds() -> frozenset[str]:
    """Problem kinds that have a variant generator."""
    return frozenset(_GENERATORS)


def supports(base: Problem) -> bool:
    """Cheap check: a generator exists for the kind and ``base.data`` has a shape it handles."""
    gen = _GENERATORS.get(base.kind)
    if gen is None:
        return False
    try:
        return bool(gen.supports(base))
    except Exception:  # noqa: BLE001 - unusual data just means "not supported"
        return False


def make_variant(base: Problem, seed: int) -> Problem | None:
    """Variant ``seed`` of ``base``, or ``None`` if unsupported or no attempt passed the checks.

    Deterministic: the same ``(base, seed)`` always gives an identical problem.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_SEED:
        return None
    if not supports(base):
        return None
    made = _cached_variant(base.model_dump_json(), seed)
    return None if made is None else made.model_copy(deep=True)


@functools.lru_cache(maxsize=512)
def _cached_variant(base_json: str, seed: int) -> Problem | None:
    return _generate(Problem.model_validate_json(base_json), seed)


def _generate(base: Problem, seed: int) -> Problem | None:
    gen = _GENERATORS[base.kind]
    for attempt in range(MAX_ATTEMPTS):
        rng = random.Random(f"{base.id}|{seed}|{attempt}")
        try:
            draft = gen.make(base, rng)
            problem = None if draft is None else _assemble(base, seed, draft)
        except Exception:  # noqa: BLE001 - a failed attempt just moves on to the next one
            log.debug(
                "variant attempt %s of %s seed %s failed", attempt, base.id, seed, exc_info=True
            )
            continue
        if problem is not None:
            return problem
    return None


# =========================================================================== drafts


@dataclass
class _Ex:
    """A sample submission and the verdict it should get.

    ``required`` examples must get exactly this status (and first error); optional ones are
    dropped if they don't. ``hint_codes`` are kept only when the checker really gives them.
    """

    name: str
    steps: list[tuple[str, str]]
    answer: str | None
    status: str
    first_error: int | None = None
    hint_codes: tuple[str, ...] = ()
    required: bool = False


@dataclass
class _Draft:
    prompt: str
    data: dict[str, Any]
    answer: str
    solution: list[str]
    examples: list[_Ex]
    hints: list[str] = field(default_factory=list)
    mistakes: list[tuple[str, str]] = field(default_factory=list)


class _Reject(Exception):
    """This attempt can't produce a usable variant."""


def _need(condition: object) -> None:
    if not condition:
        raise _Reject


@dataclass(frozen=True)
class _Generator:
    supports: Callable[[Problem], bool]
    make: Callable[[Problem, random.Random], _Draft | None]


_GENERATORS: dict[str, _Generator] = {}


def _generator(kind: str, supports_fn: Callable[[Problem], bool]):
    def register(make: Callable[[Problem, random.Random], _Draft | None]):
        _GENERATORS[kind] = _Generator(supports_fn, make)
        return make

    return register


# =========================================================================== assembly

_DASHES = ("\u2014", "\u2013")  # em and en dash


def _short_title(title: str) -> str:
    short = title.split(" · ")[0] if " · " in title else title
    return short.removeprefix("New version of ")  # a variant of a variant keeps one prefix


def _payload(base: Problem, seed: int, d: _Draft, examples: Sequence[_Ex]) -> dict[str, Any]:
    tags = [t for t in base.tags if t != _BOOK_TAG]
    if VARIANT_TAG not in tags:
        tags.append(VARIANT_TAG)
    return {
        "id": variant_id(base.id, seed),
        "course": base.course.value,
        "topic": base.topic,
        "kind": base.kind,
        "title": f"New version of {_short_title(base.title)}",
        "prompt": d.prompt,
        "answer_format": base.answer_format,
        "difficulty": base.difficulty,
        "tags": tags,
        "data": d.data,
        "answer": d.answer,
        "mistakes": [{"answer": a, "hint": h} for a, h in d.mistakes],
        "hints": list(d.hints),
        "solution": list(d.solution),
        "reference": {
            "book": base.reference.book,
            "section": base.reference.section,
            "note": VARIANT_NOTE,
        },
        "review": {"status": "draft"},
        "examples": [
            {
                "name": e.name,
                "submission": {
                    "steps": [{"kind": k, "content": c} for k, c in e.steps],
                    "answer": e.answer,
                },
                "expect": {
                    "status": e.status,
                    "first_error": e.first_error,
                    "hint_codes": list(e.hint_codes),
                },
            }
            for e in examples
        ],
    }


def _verdict_codes(verdict: Any) -> set[str]:
    out = {h.code for h in verdict.hints} | {s.code for s in verdict.steps if s.code}
    if verdict.answer is not None and verdict.answer.code:
        out.add(verdict.answer.code)
    return out


def _settle(problem: Problem, ex: _Ex) -> _Ex | None:
    """``ex`` as the checker confirms it (codes trimmed to what it really says), or ``None``."""
    submission = Submission.model_validate(
        {"steps": [{"kind": k, "content": c} for k, c in ex.steps], "answer": ex.answer}
    )
    verdict = check(problem, submission)
    if verdict.status.value != ex.status:
        return None
    errors = [s.index for s in verdict.steps if s.status is StepStatus.ERROR]
    if ex.first_error is not None and (not errors or errors[0] != ex.first_error):
        return None
    if ex.status == "correct" and errors:
        return None
    codes = _verdict_codes(verdict)
    if "ENGINE_ERROR" in codes or not all(hints.is_registered(c) for c in codes):
        return None
    if not set(ex.hint_codes) <= codes:
        ex = _Ex(ex.name, ex.steps, ex.answer, ex.status, ex.first_error, (), ex.required)
    return ex


def _assemble(base: Problem, seed: int, d: _Draft) -> Problem | None:
    texts = [d.prompt, d.answer, *d.solution, *d.hints, *(h for _, h in d.mistakes)]
    texts += [e.name for e in d.examples]
    if any(dash in t for t in texts for dash in _DASHES):
        return None
    if d.prompt == base.prompt or d.data == base.data:
        return None
    problem = Problem.model_validate(_payload(base, seed, d, d.examples))
    handler = get_handler(problem.kind)
    params = handler.params(problem)
    handler.validate(problem, params)
    if handler.verify_key(problem, params) is False:
        return None
    for mistake in problem.mistakes:  # an authored "mistake" must really be wrong
        verdict = check(problem, Submission(answer=mistake.answer))
        if verdict.status.value == "correct":
            return None
    kept: list[_Ex] = []
    for ex in d.examples:
        settled = _settle(problem, ex)
        if settled is not None:
            kept.append(settled)
        elif ex.required:
            return None
    statuses = {e.status for e in kept}
    if "correct" not in statuses or statuses == {"correct"}:
        return None
    return Problem.model_validate(_payload(base, seed, d, kept))


# =========================================================================== math helpers


class _InputPrinter(StrPrinter):
    """SymPy → ProofLab input syntax (``ln`` for natural log, ``e^x``, ``|x|``)."""

    def _print_exp(self, expr: sp.Expr) -> str:
        arg = expr.args[0]
        inner = self._print(arg)
        simple = arg.is_Symbol or (arg.is_Integer and arg > 0)
        return f"e^{inner}" if simple else f"e^({inner})"

    def _print_log(self, expr: sp.Expr) -> str:
        return f"ln({self._print(expr.args[0])})"

    def _print_Abs(self, expr: sp.Expr) -> str:
        return f"|{self._print(expr.args[0])}|"

    def _print_Exp1(self, expr: sp.Expr) -> str:
        return "e"


_PRINTER = _InputPrinter()


def _text(expr: sp.Basic, *, explicit: bool = False) -> str:
    """ProofLab input text for ``expr`` (``explicit`` keeps every ``*``)."""
    s = _PRINTER.doprint(expr).replace("**", "^")
    if explicit:
        return s
    s = re.sub(r"(?<![\^\d.])(\d+)\*(?=\(|[A-Za-z](?![A-Za-z]))", r"\1", s)
    return re.sub(r"(?<=[A-Za-z0-9)|])\*(?=[A-Za-z(])", " ", s)


def _round_trip(expr: sp.Expr, ctx: MathContext) -> str:
    """Text for ``expr`` that ProofLab's parser reads back as the same expression."""
    text = _text(expr)
    _need(len(text) <= 400)
    parsed = ctx.parse(text)
    _need(equivalent(parsed, expr, ctx) is True)
    return text


def _tex(expr: sp.Basic) -> str:
    return to_latex(expr)


def _frac_parts(expr: sp.Expr) -> tuple[sp.Expr, sp.Expr]:
    return sp.fraction(expr) if expr.is_Mul or expr.is_Pow else (expr, sp.Integer(1))


def _frac_tex(expr: sp.Expr) -> str:
    """``5·4^(-n)`` as \\frac{5}{4^n} (SymPy would write 5 · 4^{-n})."""
    num, den = _frac_parts(expr)
    return _tex(expr) if den == 1 else f"\\frac{{{_tex(num)}}}{{{_tex(den)}}}"


def _frac_text(expr: sp.Expr, ctx: MathContext) -> str:
    num, den = _frac_parts(expr)
    if den == 1:
        return _round_trip(expr, ctx)
    top = _paren_text(_text(num), num)
    bottom = f"({_text(den)})" if den.is_Add or den.is_Mul else _text(den)
    text = f"{top}/{bottom}"
    _need(equivalent(ctx.parse(text), expr, ctx) is True)
    return text


def _paren_tex(expr: sp.Expr) -> str:
    wrap = expr.is_Add or (expr.is_number and expr < 0) or _tex(expr).startswith("-")
    return f"\\left({_tex(expr)}\\right)" if wrap else _tex(expr)


def _paren_text(text: str, expr: sp.Expr) -> str:
    return f"({text})" if expr.is_Add or text.startswith("-") else text


_ALLOWED_FUNCS = (
    sp.sin,
    sp.cos,
    sp.tan,
    sp.sec,
    sp.csc,
    sp.cot,
    sp.asin,
    sp.acos,
    sp.atan,
    sp.sinh,
    sp.cosh,
    sp.tanh,
    sp.exp,
    sp.log,
    sp.Abs,
)


def _has_radical(expr: sp.Basic) -> bool:
    return any(
        p.base.is_Number and not p.exp.is_Integer for p in expr.atoms(sp.Pow) if p.exp.is_Number
    )


def _nice(expr: sp.Expr, like: sp.Expr | None = None, *, max_len: int = 160) -> bool:
    """A key a student can reasonably type: allowed functions, no new radicals, small numbers."""
    if expr.has(sp.I, sp.zoo, sp.nan, sp.Integral, sp.Piecewise, sp.Sum):
        return False
    if any(not isinstance(f, _ALLOWED_FUNCS) for f in expr.atoms(sp.Function)):
        return False
    if _has_radical(expr) and not (like is not None and _has_radical(like)):
        return False
    if any(abs(r.p) > 5000 or r.q > 5000 for r in expr.atoms(sp.Rational)):
        return False
    return len(_text(expr)) <= max_len


def _tidy(expr: sp.Expr, ctx: MathContext) -> tuple[str, sp.Expr]:
    """The shortest of a few equivalent forms of ``expr``, as (text, parsed expression)."""
    candidates = [expr, sp.expand(expr), sp.factor(expr), sp.cancel(sp.together(expr))]
    if sp.count_ops(expr) <= 40:
        candidates.append(sp.simplify(expr))
    best: tuple[str, int] | None = None
    for cand in candidates:
        try:
            text = _round_trip(cand, ctx)
        except (_Reject, MathInputError):
            continue
        score = len(text) + 8 * text.count("(-")  # avoid forms like -9(-ln(...) + ...)
        if best is None or score < best[1]:
            best = (text, score)
    _need(best is not None)
    assert best is not None
    return best[0], ctx.parse(best[0])


# --------------------------------------------------------------------------- perturbation


def _pick(rng: random.Random, old: int, lo: int = 1, hi: int = 9) -> int:
    """A new integer with the sign of ``old`` and size in [lo, hi], different when possible."""
    sign = -1 if old < 0 else 1
    choices = [v for v in range(lo, hi + 1) if v != abs(old)] or list(range(lo, hi + 1))
    return sign * rng.choice(choices)


def _implicit(rng: random.Random, sign: int, hi: int = 9) -> int:
    """A hidden coefficient ±1 stays half the time, otherwise becomes 2..hi (same sign)."""
    return sign if rng.random() < 0.5 or hi < 2 else sign * rng.randint(2, hi)


def _new_number(c: sp.Expr, rng: random.Random, hi: int = 9) -> sp.Expr:
    if c == 0 or not c.is_Rational:
        return c
    if c.is_Integer:
        if abs(c) in (4, 9) and hi >= 9:  # keep perfect squares square (x^2 + 4, x^2 - 9)
            return sp.Integer(_sign(c) * rng.choice([v for v in (1, 4, 9) if v != abs(c)]))
        return sp.Integer(_pick(rng, int(c), 1, hi))
    for _ in range(20):
        p, q = _pick(rng, int(c.p), 1, hi), rng.randint(2, max(hi, 2))
        if p % q:
            return sp.Rational(p, q)
    return c


def _sign(c: sp.Expr | int) -> int:
    return -1 if c < 0 else 1


def _perturb(expr: sp.Expr, rng: random.Random, implicit: bool = True, hi: int = 9) -> sp.Expr:
    """New integer coefficients and constants; same structure, functions and exponents.

    Explicit numbers always change. Hidden coefficients (the 1 in ``x^2`` or ``x + 3``) change
    only for whole terms of a sum or of the top-level expression, so ``sin(x)`` stays ``sin(x)``.
    Inside a square or a cube the new numbers stay small (``hi``), so powers don't explode.
    """
    if expr.is_Number:
        return _new_number(expr, rng, hi)
    if expr.is_Symbol:
        return _implicit(rng, 1, hi) * expr if implicit else expr
    if implicit and (expr.is_Pow or isinstance(expr, sp.Function)):
        return _implicit(rng, 1, hi) * _perturb(expr, rng, False, hi)
    if expr.is_Add:
        return sp.Add(*[_perturb_term(t, rng, True, hi) for t in expr.args])
    if expr.is_Mul:
        return _perturb_term(expr, rng, implicit, hi)
    if expr.is_Pow:
        b, e = expr.args
        if b.is_Integer and abs(b) >= 2:
            return sp.Integer(_pick(rng, int(b), 2, max(hi, 3))) ** e
        inner = hi
        if e.is_Integer and abs(e) >= 2:
            inner = min(hi, 4 if abs(e) == 2 else 3)
        return _perturb(b, rng, False, inner) ** e
    if isinstance(expr, sp.Function):
        return expr.func(*[_perturb(a, rng, False, hi) for a in expr.args])
    return expr


def _perturb_term(term: sp.Expr, rng: random.Random, implicit: bool, hi: int = 9) -> sp.Expr:
    c, rest = term.as_coeff_Mul()
    if rest == 1:
        return _new_number(c, rng, hi)
    factors = rest.args if rest.is_Mul else (rest,)
    if any(f.is_Add for f in factors):
        implicit = False  # 2·(x + 1) would be multiplied out when the text is read back
    if c in (1, -1):
        new_c: sp.Expr = sp.Integer(_implicit(rng, int(c), hi) if implicit else int(c))
    else:
        new_c = _new_number(c, rng, hi)
    return new_c * sp.Mul(*[_perturb(f, rng, False, hi) for f in factors])


def _changed(expr: sp.Expr, rng: random.Random, tries: int = 12, hi: int = 9) -> sp.Expr:
    """A perturbation of ``expr`` that really differs from it."""
    for _ in range(tries):
        new = _perturb(expr, rng, hi=hi)
        if new != expr and sp.simplify(new - expr) != 0:
            return new
    raise _Reject


def _new_bound(rng: random.Random, value: sp.Expr, hi: int = 4) -> sp.Expr:
    """A nonzero integer bound or point moves (same sign, size up to ``hi``); 0, π, ∞ stay."""
    if value.is_Integer and value != 0:
        return sp.Integer(_sign(value) * rng.randint(1, hi))
    return value


def _new_bounds(rng: random.Random, a: sp.Expr, b: sp.Expr, hi: int = 4) -> tuple[sp.Expr, sp.Expr]:
    for _ in range(12):
        na, nb = _new_bound(rng, a, hi), _new_bound(rng, b, hi)
        numbers = na.is_number and nb.is_number and na.is_finite and nb.is_finite
        if not numbers or bool(na < nb):
            return na, nb
    return a, b


def _ctx(data: dict[str, Any], var: str, **kw: Any) -> MathContext:
    return MathContext.build(data.get("variables") or {var: "real"}, **kw)


def _parses(text: str, ctx: MathContext) -> bool:
    try:
        ctx.parse(text)
    except MathInputError:
        return False
    return True


# =========================================================================== proofs: parity

_FRESH = "abkmjpqrstuvw"


def _parity_supports(base: Problem) -> bool:
    d = base.data
    variables = d.get("variables") or []
    hyps = d.get("hypotheses") or []
    if not all(set(h) == {"var", "is"} and h["is"] in ("even", "odd") for h in hyps):
        return False
    if not hyps and len(variables) != 1:
        return False
    ctx = MathContext.build({v: "integer" for v in variables})
    target = ctx.parse(d["target"])
    poly = sp.Poly(target, *[ctx[v] for v in variables])
    return all(c.is_Integer for c in poly.coeffs())


def _pick_same_parity(rng: random.Random, old: int) -> int:
    sign = -1 if old < 0 else 1
    choices = [v for v in range(1, 10) if v % 2 == abs(old) % 2 and v != abs(old)]
    return sign * rng.choice(choices or [abs(old)])


def _split_parity(expr: sp.Expr, syms: Sequence[sp.Symbol]) -> tuple[sp.Expr, int] | None:
    """``expr = 2·w + r`` with ``w`` an integer polynomial in ``syms`` and r ∈ {0, 1}."""
    poly = sp.Poly(sp.expand(expr), *syms)
    const = poly.coeff_monomial(1)
    r = int(const) % 2
    w = sp.expand((expr - r) / 2)
    if not all(c.is_Integer for c in sp.Poly(w, *syms).coeffs()):
        return None
    return w, r


def _parity_form(w: sp.Expr, r: int) -> str:
    inner = _text(w)
    return f"2({inner}) + 1" if r else f"2({inner})"


def _parity_form_tex(w: sp.Expr, r: int) -> str:
    return f"2\\left({_tex(w)}\\right) + 1" if r else f"2\\left({_tex(w)}\\right)"


def _join_tex(names: Sequence[str]) -> str:
    items = [f"${n}$" for n in names]
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


@_generator("parity_proof", _parity_supports)
def _parity_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    variables: list[str] = list(d["variables"])
    hyps: list[dict[str, str]] = list(d.get("hypotheses") or [])
    ctx = MathContext.build({v: "integer" for v in variables})
    syms = [ctx[v] for v in variables]
    target = ctx.parse(d["target"])
    poly = sp.Poly(target, *syms)
    letters = [ch for ch in _FRESH if ch not in variables]

    for _ in range(30):
        terms = []
        for monom, c in poly.terms():
            # Same parity as before, so the parity argument (and the goal) keeps its shape.
            if abs(c) == 1 and any(monom) and rng.random() < 0.5:
                coeff = int(c)
            else:
                coeff = _pick_same_parity(rng, int(c))
            terms.append(coeff * sp.Mul(*[s**e for s, e in zip(syms, monom, strict=True)]))
        if len(poly.terms()) == 1 and any(e > 0 for e in poly.terms()[0][0]):
            terms.append(sp.Integer(rng.randint(1, 9)))
        new = sp.Add(*terms)
        if sp.expand(new - target) == 0:
            continue
        plan = _parity_plan(new, variables, hyps, ctx, letters)
        if plan is not None:
            break
    else:
        return None

    goal, blocks = plan
    target_text = _round_trip(new, ctx)
    t_tex = _tex(new)
    data = dict(d)
    data["target"] = target_text
    data["goal"] = goal

    examples: list[_Ex] = []
    solution: list[str] = []
    if hyps:
        lets, expanded, w, r, subs = blocks[0]
        steps = [("let", t) for t in lets]
        witness_at = len(steps) + 2
        full = steps + [
            ("expr", _text(expanded)),
            ("expr", _parity_form(w, r)),
            ("witness", _text(w)),
        ]
        examples.append(_Ex("expand and regroup", full, None, "correct", required=True))
        examples.append(
            _Ex(
                "witness off by one",
                steps + [("expr", _text(expanded)), ("witness", _text(w + 1))],
                None,
                "incorrect",
                first_error=witness_at - 1,
                hint_codes=("WITNESS_MISMATCH",),
                required=True,
            )
        )
        examples.append(
            _Ex(
                "stopped before the witness",
                steps + [("expr", _text(expanded))],
                None,
                "partial",
                hint_codes=("PROOF_INCOMPLETE",),
            )
        )
        if len(hyps) >= 2:
            first = lets[0]
            fresh0 = first.split("=")[1].strip()
            same = [first] + [
                f"{h['var']} = {fresh0.replace(' + 1', '')}" + (" + 1" if h["is"] == "odd" else "")
                for h in hyps[1:]
            ]
            examples.append(
                _Ex(
                    "same letter for every variable",
                    [("let", t) for t in same],
                    None,
                    "incorrect",
                    first_error=1,
                    hint_codes=("SAME_FRESH_VARIABLE",),
                )
            )
        by_parity: dict[str, list[str]] = {}
        for h in hyps:
            by_parity.setdefault(h["is"], []).append(h["var"])
        reps = ", ".join(f"${t}$" for t in lets)
        fresh_names = [t.split("=")[1].strip()[1] for t in lets]
        intro = " and ".join(
            f"{_join_tex(vs)} {'is' if len(vs) == 1 else 'are'} {p}" for p, vs in by_parity.items()
        )
        noun = "integer" if len(fresh_names) == 1 else "integers"
        solution.append(f"Since {intro}, {reps} for some {noun} {_join_tex(fresh_names)}.")
        chain = f"{_tex(new.subs(subs))} = {_tex(expanded)} = {_parity_form_tex(w, r)}"
        solution.append(f"Then ${t_tex} = {chain}$.")
        solution.append(f"${_tex(w)}$ is an integer, so ${t_tex}$ is {goal}. $\\blacksquare$")
        prompt = _parity_prompt(variables, hyps, t_tex, goal)
        hint_list = [
            "An even integer is 2 times an integer; an odd integer is 2 times an integer, plus 1. "
            "Use a different new letter for each variable.",
            "Substitute, expand, and group every term except the constant into a multiple of 2.",
        ]
    else:
        v = variables[0]
        steps: list[tuple[str, str]] = []
        for case, expanded, w, r, _ in blocks:
            steps += [("case", case), ("expr", _text(expanded)), ("witness", _text(w))]
            label = case.split("=")[1].strip()
            solution.append(
                f"Case ${v} = {label}$: ${t_tex} = {_tex(expanded)} = {_parity_form_tex(w, r)}$, "
                f"which is {goal}."
            )
        solution.append(
            f"Every integer is even or odd, so ${t_tex}$ is always {goal}. $\\blacksquare$"
        )
        examples.append(_Ex("two cases", steps, None, "correct", required=True))
        examples.append(
            _Ex(
                "only the even case",
                steps[:3],
                None,
                "partial",
                hint_codes=("CASES_NOT_EXHAUSTIVE",),
                required=True,
            )
        )
        bad = steps[:5] + [("witness", _text(blocks[1][2] + 1))]
        examples.append(
            _Ex(
                "wrong witness in the odd case",
                bad,
                None,
                "incorrect",
                first_error=5,
                hint_codes=("WITNESS_MISMATCH",),
            )
        )
        prompt = (
            f"Use a direct proof with cases. Prove that for every integer ${v}$, the number "
            f"${t_tex}$ is {goal}."
        )
        hint_list = [
            f"Nothing is assumed about {v}, so split into cases: {v} even and {v} odd.",
            "In each case, write the number as 2 times an integer (plus 1 if odd) and give that "
            "integer as the case's witness.",
        ]
    return _Draft(
        prompt=prompt,
        data=data,
        answer="",
        solution=solution,
        examples=examples,
        hints=hint_list,
    )


def _parity_plan(
    target: sp.Expr,
    variables: list[str],
    hyps: list[dict[str, str]],
    ctx: MathContext,
    letters: list[str],
) -> tuple[str, list[tuple[Any, ...]]] | None:
    syms = [ctx[v] for v in variables]
    if hyps:
        subs: dict[sp.Symbol, sp.Expr] = {}
        lets: list[str] = []
        fresh: list[sp.Symbol] = []
        for h, letter in zip(hyps, letters, strict=False):
            k = sp.Symbol(letter, integer=True)
            r = 1 if h["is"] == "odd" else 0
            subs[ctx[h["var"]]] = 2 * k + r
            fresh.append(k)
            lets.append(f"{h['var']} = 2{letter}" + (" + 1" if r else ""))
        expanded = sp.expand(target.subs(subs))
        free = [s for s in syms if s not in subs]
        split = _split_parity(expanded, fresh + free)
        if split is None:
            return None
        w, r = split
        if w == 0:
            return None
        return ("odd" if r else "even"), [(lets, expanded, w, r, subs)]
    (n,) = syms
    k = sp.Symbol(letters[0], integer=True)
    blocks = []
    parities = set()
    for r0 in (0, 1):
        expanded = sp.expand(target.subs(n, 2 * k + r0))
        split = _split_parity(expanded, [k])
        if split is None:
            return None
        w, r = split
        parities.add(r)
        case = f"{variables[0]} = 2{letters[0]}" + (" + 1" if r0 else "")
        blocks.append((case, expanded, w, r, {n: 2 * k + r0}))
    if len(parities) != 1:
        return None
    return ("odd" if parities.pop() else "even"), blocks


def _parity_prompt(variables: list[str], hyps: list[dict[str, str]], t_tex: str, goal: str) -> str:
    if len(variables) == 1:
        (h,) = hyps
        return (
            f"Use a direct proof. Let ${h['var']}$ be an {h['is']} integer. "
            f"Show that ${t_tex}$ is {goal}."
        )
    parities = {h["is"] for h in hyps}
    names = [h["var"] for h in hyps]
    if len(hyps) >= 2 and len(parities) == 1:
        cond = f"{_join_tex(names)} are both {parities.pop()}"
        if len(hyps) > 2:
            cond = cond.replace("both", "all")
    else:
        cond = " and ".join(f"${h['var']}$ is {h['is']}" for h in hyps)
    return (
        f"Use a direct proof. Let {_join_tex(variables)} be integers. Show that if {cond}, "
        f"then ${t_tex}$ is {goal}."
    )


# =========================================================================== proofs: truth tables

_BINARY = ("and", "or", "implies", "iff")


def _truth_supports(base: Problem) -> bool:
    d = base.data
    if d.get("ask", "column") != "column" or not d.get("formula") or d.get("constraints"):
        return False
    letters = d.get("variables") or _logic_letters(d["formula"])
    ctx = logic.LogicContext.build(letters)
    ctx.parse(d["formula"])
    return True


def _logic_letters(formula: str) -> list[str]:
    plain = re.sub(r"[A-Za-z]{2,}", " ", logic.normalize_logic(formula))
    return sorted({ch for ch in plain if "A" <= ch <= "Z" and ch not in "TF"})


def _mutate_formula(f: logic.Formula, rng: random.Random) -> logic.Formula:
    """Change connectives and negations, keeping the same statement letters."""
    if f.op in ("var", "const"):
        return logic.Formula("not", (f,)) if rng.random() < 0.2 else f
    if f.op == "not":
        inner = _mutate_formula(f.args[0], rng)
        if rng.random() < 0.25 or inner.op == "not":
            return inner
        return logic.Formula("not", (inner,))
    op = f.op
    if rng.random() < 0.5:
        op = rng.choice([o for o in _BINARY if o != f.op])
    node = logic.Formula(op, tuple(_mutate_formula(a, rng) for a in f.args))
    return logic.Formula("not", (node,)) if rng.random() < 0.1 else node


def _repeats(f: logic.Formula) -> bool:
    """A connective with the same statement on both sides, like P ∧ P."""
    if len(f.args) == 2 and logic.same_statement(f.args[0], f.args[1]):
        return True
    return any(_repeats(a) for a in f.args)


def _count_not(f: logic.Formula) -> int:
    return (f.op == "not") + sum(_count_not(a) for a in f.args)


def _helper_parts(f: logic.Formula) -> list[logic.Formula]:
    """Compound parts of ``f`` worth a helper column (inner first), without ``f`` itself."""
    out: list[logic.Formula] = []

    def walk(g: logic.Formula, top: bool) -> None:
        for a in g.args:
            walk(a, False)
        compound = g.op not in ("var", "const") and not (
            g.op == "not" and g.args[0].op in ("var", "const")
        )
        if not top and compound and g not in out:
            out.append(g)

    walk(f, True)
    return out


@_generator("truth_table", _truth_supports)
def _truth_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    letters = d.get("variables") or _logic_letters(d["formula"])
    ctx = logic.LogicContext.build(letters)
    original = ctx.parse(d["formula"])
    old_column = logic.column(original, ctx.variables)
    constant_ok = len(set(old_column)) == 1
    negations = _count_not(original)
    for _ in range(60):
        new = _mutate_formula(original, rng)
        if new.variables() != original.variables() or logic.same_statement(new, original):
            continue
        if _count_not(new) != negations or _repeats(new):
            continue
        col = logic.column(new, ctx.variables)
        if col == old_column or (len(set(col)) == 1 and not constant_ok):
            continue
        text = logic.to_text(new)
        reread = ctx.parse(text)
        if logic.column(reread, ctx.variables) == col:
            break
    else:
        return None
    new = reread
    tex = logic.to_latex(new)
    answer = logic.column_text(col)
    data = dict(d)
    data["formula"] = text
    parts = _helper_parts(new)[:3]

    examples = [_Ex("correct column", [], answer, "correct", required=True)]
    if parts:
        part = parts[-1]
        step = f"{logic.to_text(part)} : {logic.column_text(logic.column(part, ctx.variables))}"
        examples.append(_Ex("with a helper column", [("column", step)], answer, "correct"))
    wrong = None
    for code, mutated in logic.mutations(new):
        mcol = logic.column(mutated, ctx.variables)
        if mcol != col:
            wrong = (code, mcol)
            break
    if wrong is None:
        flipped = [not col[0], *col[1:]]
        wrong = ("", flipped)
    examples.append(
        _Ex(
            "a typical slip",
            [],
            logic.column_text(wrong[1]),
            "incorrect",
            hint_codes=("TT_ROWS_WRONG", wrong[0]) if wrong[0] else ("TT_ROWS_WRONG",),
            required=True,
        )
    )
    solution = [
        f"The helper column for ${logic.to_latex(p)}$ is "
        f"{logic.column_text(logic.column(p, ctx.variables))}."
        for p in parts
    ]
    solution.append(f"Combining these with the main connective, the column is {answer}.")
    ops = {g.op for g in [new, *parts]}
    hint_list = ["Make a helper column for each part in parentheses first, then combine them."]
    if ops & {"implies", "iff"}:
        hint_list.append(
            "P ⇒ Q is false only when P is true and Q is false; P ⇔ Q is true exactly when both "
            "sides have the same truth value."
        )
    else:
        hint_list.append("P ∧ Q needs both sides true; P ∨ Q needs at least one side true.")
    return _Draft(
        prompt=(
            f"Build a truth table for ${tex}$ and enter the truth value of the whole statement in "
            "each row."
        ),
        data=data,
        answer=answer,
        solution=solution,
        examples=examples,
        hints=hint_list,
    )


# =========================================================================== proofs: finite sets

_SET_DOMAIN_TEX = {"Z": r"\mathbb{Z}", "N": r"\mathbb{N}"}
_SET_NUMBER_RE = re.compile(r"(\^\s*)?(?<![\w.])(-?)(\d+)")


def _set_supports(base: Problem) -> bool:
    d = base.data
    b = d.get("compute")
    if not isinstance(b, dict) or set(d) - {"compute", "ask"} or d.get("sets"):
        return False
    if set(b) - {"var", "domain", "element", "where"} or b.get("domain") not in _SET_DOMAIN_TEX:
        return False
    var = b["var"]
    where = b.get("where") or []
    if not re.fullmatch(r"[a-z]", var) or len(where) != 1:
        return False
    cond = where[0]
    if not re.fullmatch(rf"[\d\s<>=|^{var}-]+", cond):
        return False
    if re.search(r"-(?!\d)|[^\s<>=|]-", cond):  # '-' only as the sign of a number
        return False
    element = b.get("element")
    if element is not None and not re.fullmatch(rf"\d+\s*{var}", element):
        return False
    numbers = [m for m in _SET_NUMBER_RE.finditer(cond) if not m.group(1)]
    return any(int(m.group(3)) != 0 for m in numbers)


def _set_renumber(text: str, rng: random.Random, lo: int = 1) -> str:
    def repl(m: re.Match[str]) -> str:
        caret, sign, digits = m.group(1), m.group(2), m.group(3)
        if caret or int(digits) == 0:
            return m.group(0)
        # A coefficient ("5x") never becomes 1: "1x" reads badly and changes the problem's shape.
        least = max(lo, 2) if re.match(r"\s*[a-z]", m.string[m.end() :]) else lo
        value = _pick(rng, -int(digits) if sign else int(digits), least, 9)
        return str(value)

    return _SET_NUMBER_RE.sub(repl, text)


def _cond_tex(cond: str) -> str:
    s = cond.replace("<=", r"\le ").replace(">=", r"\ge ").replace("!=", r"\ne ")
    return re.sub(r"\s+", " ", s).replace(r"\le  ", r"\le ").strip()


@_generator("finite_set", _set_supports)
def _set_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    b = dict(d["compute"])
    var, domain = b["var"], b["domain"]
    ask = d.get("ask", "set")
    ectx = finite_sets.ElementContext.build([])
    old = finite_sets.build_set(finite_sets.Builder.model_validate(b), {}, ectx)
    for _ in range(30):
        nb = dict(b)
        nb["where"] = [_set_renumber(b["where"][0], rng)]
        if b.get("element"):
            nb["element"] = _set_renumber(b["element"], rng, lo=2)
        try:
            value = finite_sets.build_set(finite_sets.Builder.model_validate(nb), {}, ectx)
        except (ValueError, MathInputError):
            continue
        if value != old and min(len(old), 2) <= len(value) <= 20:
            break
    else:
        return None
    cond = nb["where"][0]
    elem = nb.get("element")
    dom = _SET_DOMAIN_TEX[domain]
    elem_tex = elem.replace(" ", "") if elem else None
    if elem_tex:
        builder = rf"\{{{elem_tex} : {var} \in {dom}, {_cond_tex(cond)}\}}"
    else:
        builder = rf"\{{{var} \in {dom} : {_cond_tex(cond)}\}}"
    data = dict(d)
    data["compute"] = nb
    listed = finite_sets.text(value)
    shown = finite_sets.latex(value)
    numbers = sorted(int(v) for v in value)
    kind_word = "natural numbers (1, 2, 3, ...)" if domain == "N" else "integers"
    solution = [f"Find the {kind_word} ${var}$ with ${_cond_tex(cond)}$."]
    if elem_tex:
        solution.append(f"Each of them gives the element ${elem_tex}$.")
    hint_list = ["Find the smallest and the largest values that work, and check the endpoints."]
    if domain == "N":
        hint_list.append("In Book of Proof, N = {1, 2, 3, ...}: 0 is not a natural number.")
    if ask == "cardinality":
        answer = str(len(value))
        solution.append(f"The set is ${shown}$, so it has {len(value)} elements.")
        prompt = f"Find the cardinality $|{builder}|$: how many elements does the set have?"
        examples = [
            _Ex("correct count", [], answer, "correct", required=True),
            _Ex("off by one", [], str(len(value) + 1), "incorrect", required=True),
        ]
    else:
        answer = listed
        solution.append(f"So the answer is ${shown}$.")
        prompt = f"Write the set ${builder}$ by listing its elements between braces."
        step = numbers[1] - numbers[0] if len(numbers) >= 2 else 1
        extra = numbers[-1] + step
        examples = [
            _Ex("correct set", [], answer, "correct", required=True),
            _Ex(
                "one element too many",
                [],
                finite_sets.text(value | {sp.Integer(extra)}),
                "incorrect",
                hint_codes=("SET_EXTRA",),
                required=True,
            ),
        ]
        if len(numbers) >= 2:
            examples.append(
                _Ex(
                    "missed an endpoint",
                    [],
                    finite_sets.text(value - {sp.Integer(numbers[0])}),
                    "incorrect",
                    hint_codes=("SET_MISSING",),
                )
            )
        run = numbers == list(range(numbers[0], numbers[0] + len(numbers)))
        if run and len(numbers) >= 5:
            examples.append(
                _Ex(
                    "written with ...",
                    [],
                    f"{{{numbers[0]}, {numbers[1]}, ..., {numbers[-1]}}}",
                    "correct",
                )
            )
    return _Draft(
        prompt=prompt,
        data=data,
        answer=answer,
        solution=solution,
        examples=examples,
        hints=hint_list,
    )


# =========================================================================== proofs: induction


def _induction_ctx(index: str) -> MathContext:
    return MathContext.build({"n": "integer", "k": "integer", "m": "integer", index: "integer"})


def _induction_supports(base: Problem) -> bool:
    d = base.data
    s = d.get("sum")
    if not isinstance(s, dict) or d.get("divides"):
        return False
    index = s.get("index", "i")
    ctx = _induction_ctx(index)
    term = ctx.parse(s["term"])
    if not term.is_polynomial(ctx[index]) or term.free_symbols - {ctx[index]}:
        return False
    return int(d.get("base", 1)) >= int(s.get("start", 1))


def _with_number(expr: sp.Expr, sym: sp.Symbol, value: int) -> str:
    """``expr`` at ``sym = value``, written out with the number in place (not evaluated)."""
    text = _text(expr, explicit=True)
    return re.sub(rf"\b{sym.name}\b", f"({value})" if value < 0 else str(value), text)


@_generator("induction", _induction_supports)
def _induction_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    s = d["sum"]
    index = s.get("index", "i")
    start = int(s.get("start", 1))
    b0 = int(d.get("base", 1))
    ctx = _induction_ctx(index)
    i, n, k = ctx[index], ctx["n"], ctx["k"]
    term = _changed(ctx.parse(s["term"]), rng)
    _need(term.is_polynomial(i) and sp.degree(term, i) >= 1)
    total = sp.summation(term, (i, start, n))
    factored, expanded = _round_trip(sp.factor(total), ctx), _round_trip(sp.expand(total), ctx)
    rhs_text = factored if len(factored) <= len(expanded) + 6 else expanded
    rhs = ctx.parse(rhs_text)
    term_text = _round_trip(term, ctx)
    data = dict(d)
    data["sum"] = {**s, "term": term_text, "rhs": rhs_text}

    def at(expr: sp.Expr, value: sp.Expr) -> sp.Expr:
        return expr.subs(n, value)

    rhs_k = at(rhs, k)
    next_term = term.subs(i, k + 1)
    this_term = term.subs(i, k)
    left_base = sum(term.subs(i, j) for j in range(start, b0 + 1))
    base_step = f"{_text(sp.Integer(left_base))} = {_with_number(rhs, n, b0)}"
    first_terms = [_paren_text(_text(term.subs(i, j)), term.subs(i, j)) for j in (start, start + 1)]
    assume = (
        f"{first_terms[0]} + {first_terms[1]} + ... + {_paren_text(_text(this_term), this_term)}"
        f" = {_text(rhs_k)}"
    )
    uses = f"{_paren_text(_text(rhs_k), rhs_k)} + ({_text(next_term)})"
    combined = sp.factor(rhs_k + next_term)
    target = sp.factor(at(rhs, k + 1))
    steps = [("base", base_step), ("assume", assume), ("expr", uses)]
    middle = [("expr", _text(sp.expand(rhs_k + next_term))), ("expr", _text(target))]
    examples = [
        _Ex("induction proof", steps + middle, None, "correct", required=True),
        _Ex(
            "added the k-th term again",
            steps[:2] + [("expr", f"{_paren_text(_text(rhs_k), rhs_k)} + ({_text(this_term)})")],
            None,
            "incorrect",
            first_error=2,
            hint_codes=("IND_STEP_WRONG",),
            required=True,
        ),
        _Ex(
            "skips the hypothesis",
            steps[:2] + [("expr", _text(target))],
            None,
            "partial",
            hint_codes=("IND_USE_HYPOTHESIS",),
        ),
    ]
    sum_tex = rf"\sum_{{{index}={start}}}^{{n}} {_paren_tex(term)}"
    sum_k_tex = rf"\sum_{{{index}={start}}}^{{k}} {_paren_tex(term)}"
    sum_k1_tex = rf"\sum_{{{index}={start}}}^{{k+1}} {_paren_tex(term)}"
    who = "every positive integer $n$" if b0 == 1 else f"every integer $n \\ge {b0}$"
    prompt = (
        f"Prove by induction that $\\displaystyle {sum_tex} = {_tex(rhs)}$ for {who}. Check "
        f"$n = {b0}$, assume the formula for $n = k$, and deduce it for $n = k + 1$."
    )
    solution = [
        f"Base case: for $n = {b0}$ the left side is ${left_base}$ and the right side is "
        f"${_tex(sp.nsimplify(at(rhs, b0)))}$.",
        f"Inductive step: suppose ${sum_k_tex} = {_tex(rhs_k)}$ for some $k \\ge {b0}$. Adding the "
        f"next term, ${sum_k1_tex} = {_tex(rhs_k)} + {_paren_tex(next_term)} = "
        f"{_tex(combined)}$.",
        f"This equals ${_tex(target)}$, the formula for $n = k + 1$.",
        f"By induction the formula holds for {who}. $\\blacksquare$",
    ]
    hint_list = [
        f"Base case: put n = {b0} into both sides and compare.",
        "Assume the formula for n = k. The sum up to k + 1 is that sum plus one more term: "
        "the term with i = k + 1.",
        "Simplify the result and compare it with the formula for n = k + 1.",
    ]
    if index != "i":
        hint_list[1] = hint_list[1].replace("i = k + 1", f"{index} = k + 1")
    return _Draft(
        prompt=prompt,
        data=data,
        answer="",
        solution=solution,
        examples=examples,
        hints=hint_list,
    )


# =========================================================================== calculus helpers


def _parse_data(base: Problem, key: str, ctx: MathContext) -> sp.Expr:
    return ctx.parse(str(base.data[key]))


def _base_key(base: Problem, ctx: MathContext) -> sp.Expr | None:
    try:
        return ctx.parse(strip_label(base.answer.replace("+ C", "").strip()))
    except MathInputError:
        return None


def _simple_supports(*fields: str, var_default: str = "x") -> Callable[[Problem], bool]:
    """The handler accepts the data and each named field parses in the problem's context."""

    def supports(base: Problem) -> bool:
        handler = get_handler(base.kind)
        handler.params(base)
        ctx = _ctx(base.data, base.data.get("var", var_default), allow_integral=True)
        return all(isinstance(base.data.get(f), str) and _parses(base.data[f], ctx) for f in fields)

    return supports


def _rule_hints(f: sp.Expr, x: sp.Symbol) -> list[str]:
    """Which differentiation rules the structure of ``f`` calls for."""
    out: list[str] = []
    _, body = f.as_independent(x, as_Add=False)
    num, den = sp.fraction(sp.together(body)) if not body.is_Add else (body, sp.Integer(1))
    if f.is_Add:
        out.append("Differentiate term by term.")
    if den.has(x) and num.has(x):
        out.append("Use the quotient rule: (u/v)' = (u'v - uv')/v^2.")
    elif body.is_Mul and sum(1 for a in body.args if a.has(x)) >= 2:
        out.append("f is a product u v: use the product rule (uv)' = u'v + uv'.")
    inner = [
        g
        for g in sp.preorder_traversal(f)
        if (isinstance(g, sp.Function) and g.args[0] != x and g.args[0].has(x))
        or (g.is_Pow and g.base.has(x) and not g.base.is_Symbol and not g.exp.has(x))
    ]
    if inner:
        out.append(
            "Use the chain rule: differentiate the outside function, then multiply by the "
            "derivative of the inside."
        )
    return out[:2] or ["Use the power rule and the derivatives of the basic functions."]


# =========================================================================== calc1: derivative


def _derivative_lhs(base: Problem, var: str, order: int) -> tuple[str, str, str]:
    """(LaTeX of what is asked, its text label, LaTeX of the function's name)."""
    if "dy}{dx}" in base.prompt or "dy/dx" in base.prompt:
        if order == 1:
            return rf"\dfrac{{dy}}{{d{var}}}", f"dy/d{var}", "y"
        return rf"\dfrac{{d^{order}y}}{{d{var}^{order}}}", f"y{chr(39) * order}", "y"
    primes = "'" * order if order <= 3 else f"^{{({order})}}"
    label = "'" * order if order <= 3 else f"^({order})"
    return f"f{primes}({var})", f"f{label}({var})", f"f({var})"


@_generator("derivative", _simple_supports("function"))
def _derivative_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    var = d.get("var", "x")
    order = int(d.get("order", 1))
    ctx = _ctx(d, var)
    x = ctx[var]
    f = _changed(_parse_data(base, "function", ctx), rng)
    f_text = _round_trip(f, ctx)
    f = ctx.parse(f_text)
    derivs = [sp.diff(f, x, k) for k in range(1, order + 1)]
    raw = derivs[-1]
    _need(raw != 0)
    key_text, key = _tidy(raw, ctx)
    _need(_nice(key, _base_key(base, ctx)))
    asked_tex, label, name_tex = _derivative_lhs(base, var, order)
    data = {**d, "function": f_text}
    prompt = f"Find ${asked_tex}$ for ${name_tex} = {_tex(f)}$."

    if order == 1:
        steps = [("expr", f"{label} = {_text(raw)}")]
        solution = [f"Differentiate: ${asked_tex} = {_tex(raw)}$."]
        if _tex(raw) != _tex(key):
            solution.append(f"Simplify: ${asked_tex} = {_tex(key)}$.")
    else:
        steps = [("expr", _text(derivs[k])) for k in range(order)]
        solution = [
            f"${_derivative_lhs(base, var, k + 1)[0]} = {_tex(derivs[k])}$." for k in range(order)
        ]
    examples = [
        _Ex("differentiate", steps, key_text, "correct", required=True),
        _Ex(
            "sign slip",
            [],
            _text(-key),
            "incorrect",
            hint_codes=("SIGN_ERROR",),
            required=True,
        ),
        _Ex(
            "wrong step, right answer",
            [("expr", _text(-key))],
            key_text,
            "partial",
            first_error=0,
            hint_codes=("STEP_ERRORS",),
        ),
    ]
    if order >= 2:
        examples.append(
            _Ex(
                "stopped after one derivative",
                [],
                _text(derivs[0]),
                "incorrect",
                hint_codes=("WRONG_ORDER",),
            )
        )
    else:
        coeff, body = f.as_independent(x, as_Add=False)
        if body.is_Mul and not sp.fraction(body)[1].has(x):
            factors = [a for a in body.args if a.has(x)]
            if len(factors) >= 2:
                u, v = factors[0], sp.Mul(*factors[1:])
                wrong = coeff * sp.diff(u, x) * sp.diff(v, x)
                examples.append(
                    _Ex(
                        "multiplied the derivatives",
                        [],
                        _text(wrong),
                        "incorrect",
                        hint_codes=("PRODUCT_RULE",),
                    )
                )
        if isinstance(body, sp.Function) and body.args[0] != x:
            u = sp.Dummy("u")
            no_chain = coeff * sp.diff(body.func(u), u).subs(u, body.args[0])
            examples.append(
                _Ex(
                    "forgot the inside derivative",
                    [],
                    _text(no_chain),
                    "incorrect",
                    hint_codes=("CHAIN_RULE",),
                )
            )
    hint_list = _rule_hints(f, x)
    if order >= 2:
        hint_list = [f"Differentiate once to get f'({var}), then differentiate again.", *hint_list]
    return _Draft(prompt, data, key_text, solution, examples, hint_list[:2])


# =========================================================================== calc1: tangent line


@_generator("tangent_line", _simple_supports("function", "at"))
def _tangent_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    var = d.get("var", "x")
    ctx = MathContext.build({var: "real", "y": "real"})
    x, y = ctx[var], ctx["y"]
    f = _changed(_parse_data(base, "function", ctx), rng)
    f_text = _round_trip(f, ctx)
    f = ctx.parse(f_text)
    a = _new_bound(rng, _parse_data(base, "at", ctx), 2)
    fprime = sp.diff(f, x)
    m, fa = sp.nsimplify(fprime.subs(x, a)), sp.nsimplify(f.subs(x, a))
    _need(m.is_Rational and fa.is_Rational and abs(m) <= 200 and abs(fa) <= 200)
    line = sp.expand(fa + m * (x - a))
    answer = f"y = {_text(line)}"
    a_text = _text(a)
    shift = f"{var} - {a_text}" if a >= 0 else f"{var} + {_text(-a)}"
    data = {**d, "function": f_text, "at": a_text}
    examples = [
        _Ex(
            "point-slope",
            [
                ("expr", f"f'({var}) = {_text(fprime)}"),
                ("expr", f"f'({a_text}) = {_text(m)}"),
                ("expr", f"f({a_text}) = {_text(fa)}"),
                ("expr", f"{_text(y - fa)} = ({_text(m)})({shift})"),
            ],
            answer,
            "correct",
            required=True,
        ),
        _Ex("slope only", [], _text(m), "incorrect", hint_codes=("SLOPE_ONLY",), required=True),
        _Ex(
            "wrong point",
            [],
            f"y = {_text(line + 1)}",
            "incorrect",
            hint_codes=("WRONG_POINT",),
        ),
        _Ex(
            "wrong slope",
            [],
            f"y = {_text(sp.expand(fa + (m + 1) * (x - a)))}",
            "incorrect",
            hint_codes=("WRONG_SLOPE",),
        ),
    ]
    solution = [
        f"$f({a_text}) = {_tex(fa)}$, so the point is $({a_text}, {_tex(fa)})$.",
        f"$f'({var}) = {_tex(fprime)}$, so the slope is $f'({a_text}) = {_tex(m)}$.",
        f"$y - ({_tex(fa)}) = {_tex(m)}({var} - {_tex(a)})$, i.e. $y = {_tex(line)}$.",
    ]
    hint_list = [
        f"You need a point ({a_text}, f({a_text})) and a slope f'({a_text}).",
        f"Point-slope form: y - f(a) = f'(a)({var} - a).",
    ]
    prompt = (
        f"Find the equation of the tangent line to $f({var}) = {_tex(f)}$ at ${var} = {a_text}$."
    )
    return _Draft(prompt, data, answer, solution, examples, hint_list)


# =========================================================================== calc1: limit


def _limit_supports(base: Problem) -> bool:
    # Imported here, not at the top, so importing this module doesn't change the order in which
    # the checker registers its topic modules.
    from prooflab.engine.topics.calc1.limits import parse_limit_value

    d = base.data
    if d.get("direction", "both") != "both" or d.get("variables"):
        return False
    ctx = MathContext.build({d.get("var", "x"): "real"})
    ctx.parse(d["expression"])
    value = parse_limit_value(base.answer, ctx)
    return not isinstance(value, str) and bool(value.is_finite)


def _vanishes(expr: sp.Expr, x: sp.Symbol, a: sp.Expr) -> bool:
    return sp.simplify(expr.subs(x, a)) == 0


@_generator("limit", _limit_supports)
def _limit_make(base: Problem, rng: random.Random) -> _Draft | None:
    from prooflab.engine.topics.calc1.limits import compute_limit

    d = base.data
    var = d.get("var", "x")
    ctx = MathContext.build({var: "real"})
    x = ctx[var]
    f = ctx.parse(d["expression"])
    a = ctx.parse(d["point"])
    num, den = sp.fraction(f)
    if den == 1:
        num, den = sp.fraction(sp.together(f))
    finite = bool(a.is_finite)
    zero_zero = finite and _vanishes(num, x, a) and _vanishes(den, x, a)
    found = None
    for _ in range(12):
        n2, d2 = _perturb(num, rng), _perturb(den, rng)
        a2 = _new_bound(rng, a, 4) if finite else a
        if zero_zero:  # keep the 0/0 form: move the constant terms so both vanish at a2
            n2, d2 = sp.expand(n2 - n2.subs(x, a2)), sp.expand(d2 - d2.subs(x, a2))
        if n2 == 0 or not d2.has(x):
            continue
        f2 = n2 / d2
        if sp.simplify(f2 - f) == 0 and a2 == a:
            continue
        value = compute_limit(f2, x, a2, "both")
        if isinstance(value, str) or value is None or not value.is_finite:
            continue
        value = sp.nsimplify(value)
        if _nice(value) and len(_text(value)) <= 12:
            found = (n2, d2, a2, value)
            break
    if found is None:
        return None
    n2, d2, a2, value = found
    n_text, d_text = _round_trip(n2, ctx), _round_trip(d2, ctx)
    expr_text = f"({n_text})/({d_text})"
    point_text = "oo" if a2 == sp.oo else ("-oo" if a2 == -sp.oo else _text(a2))
    point_tex = _tex(a2)
    value_text = _text(value)
    data = {**d, "expression": expr_text, "point": point_text}
    frac_tex = rf"\frac{{{_tex(n2)}}}{{{_tex(d2)}}}"
    prompt = f"Evaluate $\\displaystyle \\lim_{{{var} \\to {point_tex}}} {frac_tex}$."
    rational = n2.is_polynomial(x) and d2.is_polynomial(x)
    steps: list[tuple[str, str]] = []
    solution: list[str] = []
    hint_list: list[str] = []
    if not finite:
        deg = sp.degree(d2, x)
        nn, dd = sp.expand(n2 / x**deg), sp.expand(d2 / x**deg)
        steps = [("expr", f"({_text(nn)})/({_text(dd)})"), ("expr", value_text)]
        solution = [
            f"Divide the numerator and the denominator by ${_tex(x**deg)}$: "
            rf"$\frac{{{_tex(nn)}}}{{{_tex(dd)}}}$.",
            f"As ${var} \\to \\infty$, every term with ${var}$ in a denominator tends to $0$, so "
            f"the limit is ${_tex(value)}$.",
        ]
        hint_list = [f"Divide every term by the highest power of {var} in the denominator."]
    elif zero_zero and rational:
        cancelled = sp.factor(sp.cancel(f2))
        fn, fd = sp.factor(n2), sp.factor(d2)
        steps = [
            ("expr", f"({_text(fn)})/({_text(fd)})"),
            ("expr", _text(cancelled)),
            ("expr", value_text),
        ]
        solution = [
            r"Direct substitution gives $\frac{0}{0}$, an indeterminate form.",
            rf"Factor and cancel: $\frac{{{_tex(fn)}}}{{{_tex(fd)}}} = {_tex(cancelled)}$ for "
            f"${var} \\ne {point_tex}$.",
            f"The limit only depends on values near ${point_tex}$, so it is ${_tex(value)}$.",
        ]
        hint_list = [
            f"Plugging in {var} = {point_text} gives 0/0. That means more work is needed, not that "
            "there is no limit.",
            "Factor the numerator and the denominator and cancel the common factor.",
        ]
    elif zero_zero:
        cn, cd = n2, d2
        lines = []
        for _ in range(3):
            cn, cd = sp.diff(cn, x), sp.diff(cd, x)
            steps.append(("lhopital", f"({_text(cn)})/({_text(cd)})"))
            lines.append(rf"$\lim \frac{{{_tex(cn)}}}{{{_tex(cd)}}}$")
            if not (_vanishes(cn, x, a2) and _vanishes(cd, x, a2)):
                break
        else:
            raise _Reject
        steps.append(("expr", value_text))
        solution = [
            f"At ${var} = {point_tex}$ the form is $\\frac{{0}}{{0}}$, so L'Hôpital's rule "
            f"applies: {', then '.join(lines)}.",
            f"Now substitute ${var} = {point_tex}$: the limit is ${_tex(value)}$.",
        ]
        hint_list = [
            "Check the form first: what do the numerator and the denominator approach?",
            "You may need L'Hôpital's rule more than once.",
        ]
    else:
        raise _Reject
    mistakes: list[tuple[str, str]] = []
    if not finite:
        lead = sp.LC(sp.Poly(n2, x))
        if lead != value:
            mistakes.append(
                (
                    _text(lead),
                    f"Divide the numerator and the denominator by {_text(x**deg)}, not just the "
                    "numerator.",
                )
            )
        mistakes.append(
            (
                "oo",
                "The numerator and the denominator grow at the same rate. Compare their leading "
                "terms.",
            )
        )
    examples = [_Ex("worked steps", steps, value_text, "correct", required=True)]
    if finite:
        examples.append(
            _Ex(
                "says DNE because of 0/0",
                [],
                "DNE",
                "incorrect",
                hint_codes=("INDETERMINATE_IS_NOT_DNE",),
                required=True,
            )
        )
        examples.append(
            _Ex("answers 0/0", [], "0/0", "incorrect", hint_codes=("INDETERMINATE_FORM",))
        )
    else:
        examples.append(
            _Ex(
                "says infinity", [], "oo", "incorrect", hint_codes=("KNOWN_MISTAKE",), required=True
            )
        )
        if len(mistakes) == 2:
            examples.append(
                _Ex(
                    "only divided the top",
                    [],
                    mistakes[0][0],
                    "incorrect",
                    hint_codes=("KNOWN_MISTAKE",),
                )
            )
    if not value.is_Integer:
        examples.append(
            _Ex("decimal", [], f"{float(value):.4f}", "partial", hint_codes=("INEXACT",))
        )
    return _Draft(prompt, data, value_text, solution, examples, hint_list, mistakes)


# =========================================================================== calc2: integrals


def _integral_ctx(d: dict[str, Any]) -> MathContext:
    return _ctx(d, d.get("var", "x"), constants=("C", "K", "c"), allow_integral=True)


def _log_abs(expr: sp.Expr) -> sp.Expr:
    """``ln(g)`` → ``ln|g|`` wherever g can be negative (antiderivatives on the whole domain)."""
    return expr.replace(
        lambda e: isinstance(e, sp.log) and not e.args[0].is_positive,
        lambda e: sp.log(sp.Abs(e.args[0])),
    )


def _antiderivative(f: sp.Expr, x: sp.Symbol, like: sp.Expr | None) -> sp.Expr:
    """An antiderivative a student could write: the shorter of SymPy's two methods."""
    found: list[sp.Expr] = []
    for manual in (False, True):
        try:
            F = sp.integrate(f, x, manual=manual)
        except Exception:  # noqa: BLE001 - manualintegrate gives up on some inputs
            continue
        if not F.has(sp.Integral):
            F = _log_abs(F)
            if _nice(F, like):
                found.append(F)
    _need(found)
    return min(found, key=lambda F: (len(_text(F)), _text(F)))


def _integral_tex(f: sp.Expr, var: str, lower: sp.Expr | None = None, upper: sp.Expr | None = None):
    limits = "" if lower is None else f"_{{{_tex(lower)}}}^{{{_tex(upper)}}}"
    return f"\\int{limits} {_paren_tex(f)}\\,d{var}"


@_generator("antiderivative", _simple_supports("integrand"))
def _antiderivative_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    var = d.get("var", "x")
    ctx = _integral_ctx(d)
    x = ctx[var]
    like = _base_key(base, ctx)
    original = _parse_data(base, "integrand", ctx)
    for _ in range(5):
        f = _changed(original, rng)
        f_text = _round_trip(f, ctx)
        f = ctx.parse(f_text)
        try:
            F_text, F = _tidy(_antiderivative(f, x, like), ctx)
        except _Reject:
            continue
        if _nice(F, like):
            break
    else:
        return None
    answer = f"{F_text} + C"
    data = {**d, "integrand": f_text}
    integral = _integral_tex(f, var)
    prompt = f"Find $\\displaystyle {integral}$."
    examples = [
        _Ex("antiderivative + C", [], answer, "correct", required=True),
        _Ex("no + C", [], F_text, "partial", hint_codes=("MISSING_C",), required=True),
        _Ex("sign slip", [], f"{_text(-F)} + C", "incorrect", hint_codes=("INTEGRAL_SIGN",)),
        _Ex(
            "differentiated instead",
            [],
            _text(sp.diff(f, x)),
            "incorrect",
            hint_codes=("DIFFERENTIATED_INSTEAD",),
        ),
    ]
    if F.has(sp.Abs):
        no_abs = F.replace(lambda e: isinstance(e, sp.Abs), lambda e: e.args[0])
        examples.append(
            _Ex("no absolute value", [], f"{_text(no_abs)} + C", "partial", hint_codes=("LOG_ABS",))
        )
    solution = [
        f"An antiderivative of ${_tex(f)}$ is ${_tex(F)}$, so "
        f"$\\displaystyle {integral} = {_tex(F)} + C$.",
        f"Check: $\\dfrac{{d}}{{d{var}}}\\left({_tex(F)}\\right) = {_tex(f)}$.",
    ]
    hint_list = [
        "Look for a substitution u = g(x) whose derivative appears, integration by parts, or a "
        "standard formula.",
        "Check your answer by differentiating it, and remember + C.",
    ]
    return _Draft(prompt, data, answer, solution, examples, hint_list)


def _definite_try(original, lower, upper, x, ctx, like, rng):
    f = _changed(original, rng)
    f_text = _round_trip(f, ctx)
    f = ctx.parse(f_text)
    a, b = _new_bounds(rng, lower, upper, 3)
    value = sp.integrate(f, (x, a, b))
    _need(not value.has(sp.Integral))
    F = _antiderivative(f, x, None)
    if value not in (sp.oo, -sp.oo):
        _need(value.is_finite and value != 0)
        value = sp.nsimplify(value) if value.is_Rational else sp.simplify(value)
        _need(_nice(value, like, max_len=40))
        _need(not any(abs(r.p) > 2000 or r.q > 2000 for r in value.atoms(sp.Rational)))
    return f, f_text, a, b, value, F


@_generator("definite_integral", _simple_supports("integrand", "lower", "upper"))
def _definite_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    var = d.get("var", "x")
    ctx = _integral_ctx(d)
    x = ctx[var]
    diverges = base.answer.strip().lower() in ("diverges", "divergent", "diverge")
    like = None if diverges else _base_key(base, ctx)
    original = _parse_data(base, "integrand", ctx)
    lower, upper = _parse_data(base, "lower", ctx), _parse_data(base, "upper", ctx)
    for _ in range(5):
        try:
            f, f_text, a, b, value, F = _definite_try(original, lower, upper, x, ctx, like, rng)
        except _Reject:
            continue
        if diverges == (value in (sp.oo, -sp.oo)):
            break
    else:
        return None
    improper = not (a.is_finite and b.is_finite)
    answer = "diverges" if diverges else _round_trip(value, ctx)
    data = {**d, "integrand": f_text, "lower": _text(a), "upper": _text(b)}
    integral = _integral_tex(f, var, a, b)
    prompt = f"Evaluate $\\displaystyle {integral}$" + (
        ", or say that it diverges." if improper else "."
    )

    def end(point: sp.Expr) -> sp.Expr:
        return sp.limit(F, x, point) if not point.is_finite else sp.simplify(F.subs(x, point))

    if diverges:
        examples = [
            _Ex("diverges", [("expr", _text(F))], "diverges", "correct", required=True),
            _Ex("gives a number", [], "0", "incorrect", required=True),
        ]
        solution = [
            f"An antiderivative is ${_tex(F)}$.",
            f"As the upper limit grows, ${_tex(F)}$ grows without bound, so the integral diverges.",
        ]
    else:
        Fa, Fb = end(a), end(b)
        steps = [("expr", _text(F))]
        if Fa.is_finite and Fb.is_finite:
            steps.append(("expr", f"{_text(Fb)} - ({_text(Fa)})"))
        examples = [
            _Ex("antiderivative, then F(b) - F(a)", steps, answer, "correct", required=True),
            _Ex(
                "sign error",
                [],
                _text(-value),
                "incorrect",
                hint_codes=("SIGN_ERROR",),
                required=True,
            ),
            _Ex(
                "stopped at the antiderivative",
                [],
                _text(F),
                "incorrect",
                hint_codes=("INTEGRAL_NEEDS_VALUE",),
            ),
        ]
        if not value.is_Integer:
            examples.append(
                _Ex("decimal", [], f"{float(value):.4f}", "partial", hint_codes=("INEXACT",))
            )
        if improper:
            solution = [
                f"An antiderivative is $F({var}) = {_tex(F)}$.",
                f"Take the limit of $F$ at the infinite end: the integral is "
                f"${_tex(Fb)} - \\left({_tex(Fa)}\\right) = {_tex(value)}$.",
            ]
        else:
            solution = [
                f"An antiderivative is $F({var}) = {_tex(F)}$.",
                f"$F({_tex(b)}) - F({_tex(a)}) = {_tex(Fb)} - \\left({_tex(Fa)}\\right) = "
                f"{_tex(value)}$.",
            ]
    hint_list = [
        "Find an antiderivative F first (a substitution may help), then evaluate F at the limits.",
    ]
    if improper:
        hint_list.append("For an infinite limit, integrate up to t and let t go to infinity.")
    return _Draft(prompt, data, answer, solution, examples, hint_list)


# =========================================================================== calc2: series


def _geometric_ratio(term: sp.Expr, n: sp.Symbol) -> sp.Expr | None:
    r = sp.simplify(term.subs(n, n + 1) / term)
    if r.free_symbols or not r.is_Rational or not 0 < abs(r) < 1:
        return None
    return r


def _series_ctx(d: dict[str, Any]) -> MathContext:
    return MathContext.build({d.get("var", "n"): "integer"})


def _series_supports(base: Problem) -> bool:
    d = base.data
    ctx = _series_ctx(d)
    return _geometric_ratio(ctx.parse(d["term"]), ctx[d.get("var", "n")]) is not None


@_generator("series_sum", _series_supports)
def _series_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    var = d.get("var", "n")
    start = int(d.get("start", 1))
    ctx = _series_ctx(d)
    n = ctx[var]
    for _ in range(12):
        term = _changed(ctx.parse(d["term"]), rng)
        r = _geometric_ratio(term, n)
        if r is not None:
            break
    else:
        return None
    term_text = _frac_text(term, ctx)
    term = ctx.parse(term_text)
    a0 = sp.nsimplify(term.subs(n, start))
    total = sp.nsimplify(sp.summation(term, (n, start, sp.oo)))
    _need(total.is_Rational and sp.simplify(total - a0 / (1 - r)) == 0)
    answer = _text(total)
    data = {**d, "term": term_text}
    r_text = _text(r)
    first = [("expr", f"({_text(a0)})/(1 - ({r_text}))")]
    examples = [_Ex("a/(1 - r)", first, answer, "correct", required=True)]
    if start >= 1:
        before = sp.nsimplify(term.subs(n, start - 1))
        examples.append(
            _Ex(
                f"started at {var} = {start - 1}",
                [("expr", f"({_text(before)})/(1 - ({r_text}))")],
                _text(before / (1 - r)),
                "incorrect",
                first_error=0,
                hint_codes=("START_INDEX",),
                required=True,
            )
        )
    if not total.is_Integer:
        examples.append(
            _Ex("decimal", [], f"{float(total):.4f}", "partial", hint_codes=("INEXACT",))
        )
    one_minus = f"1 - {_tex(r)}" if r > 0 else f"1 + {_tex(-r)}"
    solution = [
        f"First term $a = {_tex(a0)}$, ratio $r = {_tex(r)}$.",
        rf"Sum $= \frac{{a}}{{1 - r}} = \frac{{{_tex(a0)}}}{{{one_minus}}} = {_tex(total)}$.",
    ]
    hint_list = [
        f"Write out the first two terms to find the first term a and the ratio r. The sum starts "
        f"at {var} = {start}.",
        "A geometric series with |r| < 1 sums to a/(1 - r).",
    ]
    prompt = f"Find $\\displaystyle \\sum_{{{var}={start}}}^{{\\infty}} {_frac_tex(term)}$."
    return _Draft(prompt, data, answer, solution, examples, hint_list)


# =========================================================================== calc3: partials


def _partials_ctx(d: dict[str, Any]) -> MathContext:
    return MathContext.build(d.get("variables") or ["x", "y"])


def _var_names(d: dict[str, Any]) -> list[str]:
    return list(d.get("variables") or ["x", "y"])


def _positive_note(d: dict[str, Any]) -> str:
    v = d.get("variables")
    if isinstance(v, dict):
        pos = [n for n, spec in v.items() if str(spec).startswith("positive")]
        if pos:
            return ", where " + " and ".join(f"${n} > 0$" for n in pos)
    return ""


def _partials_supports(base: Problem) -> bool:
    get_handler(base.kind).params(base)
    d = base.data
    _partials_ctx(d).parse(d["function"])
    return len(d.get("respect") or [None]) <= 2


@_generator("partial_derivative", _partials_supports)
def _partial_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    ctx = _partials_ctx(d)
    names = _var_names(d)
    respect: list[str] = list(d["respect"])
    f = _changed(ctx.parse(d["function"]), rng)
    f_text = _round_trip(f, ctx)
    f = ctx.parse(f_text)
    stages = [sp.diff(f, *[ctx[v] for v in respect[: k + 1]]) for k in range(len(respect))]
    _need(stages[-1] != 0)
    key_text, key = _tidy(stages[-1], ctx)
    _need(_nice(key, _base_key(base, ctx)))
    label = "".join(respect)
    data = {**d, "function": f_text}
    f_tex = f"f({', '.join(names)}) = {_tex(f)}"
    if len(respect) == 1:
        (r,) = respect
        prompt = f"Find $\\dfrac{{\\partial f}}{{\\partial {r}}}$ for ${f_tex}${_positive_note(d)}."
        steps = [("expr", f"f_{r} = {_text(stages[0])}")]
        others = [n for n in names if n != r]
        solution = [
            f"Holding {_join_tex(others)} constant, $f_{{{r}}} = {_tex(key)}$.",
        ]
        hint_list = [
            f"Treat {' and '.join(others)} exactly like constant numbers, then differentiate "
            f"in {r}."
        ]
    else:
        r1, r2 = respect
        outer = f"\\dfrac{{\\partial}}{{\\partial {r2}}}"
        inner = f"\\dfrac{{\\partial f}}{{\\partial {r1}}}"
        prompt = (
            f"Find $f_{{{label}}} = {outer}\\left({inner}\\right)$ for ${f_tex}$"
            f"{_positive_note(d)}."
        )
        steps = [("expr", f"f_{r1} = {_text(stages[0])}"), ("expr", f"f_{label} = {key_text}")]
        solution = [f"$f_{{{r1}}} = {_tex(stages[0])}$.", f"$f_{{{label}}} = {_tex(key)}$."]
        hint_list = [f"First find f_{r1}. Then differentiate that result with respect to {r2}."]
    examples = [
        _Ex("partial derivative", steps, key_text, "correct", required=True),
        _Ex("sign slip", [], _text(-key), "incorrect", hint_codes=("SIGN_ERROR",), required=True),
    ]
    if len(respect) == 2:
        examples.append(
            _Ex(
                f"stopped after f_{respect[0]}",
                [],
                _text(stages[0]),
                "incorrect",
                hint_codes=("PARTIAL_INCOMPLETE",),
            )
        )
    for other in names:
        seq = [other] if len(respect) == 1 else [respect[0], respect[0]]
        if sorted(seq) == sorted(respect):
            continue
        wrong = sp.diff(f, *[ctx[v] for v in seq])
        if wrong != 0 and sp.simplify(wrong - key) != 0:
            examples.append(
                _Ex(
                    f"differentiated in {other}" if len(seq) == 1 else f"took f_{''.join(seq)}",
                    [],
                    _text(wrong),
                    "incorrect",
                    hint_codes=("WRONG_VARIABLE",),
                )
            )
            break
    return _Draft(prompt, data, key_text, solution, examples, hint_list)


def _vector_text(components: Sequence[sp.Expr]) -> str:
    return "<" + ", ".join(_text(c) for c in components) + ">"


def _vector_tex(components: Sequence[sp.Expr]) -> str:
    return r"\left\langle " + ",\\ ".join(_tex(c) for c in components) + r" \right\rangle"


@_generator("gradient", _partials_supports)
def _gradient_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    ctx = _partials_ctx(d)
    names = _var_names(d)
    syms = [ctx[n] for n in names]
    f = _changed(ctx.parse(d["function"]), rng)
    f_text = _round_trip(f, ctx)
    f = ctx.parse(f_text)
    grad = [sp.diff(f, s) for s in syms]
    _need(all(_nice(g) for g in grad))
    data = {**d, "function": f_text}
    f_tex = f"f({', '.join(names)}) = {_tex(f)}"
    at = d.get("at")
    if at is not None:
        point = [_new_bound(rng, ctx.parse(str(v)), 3) for v in at]
        values = [
            sp.nsimplify(sp.simplify(g.subs(dict(zip(syms, point, strict=True))))) for g in grad
        ]
        _need(all(v.is_finite and v.is_real and _nice(v, max_len=12) for v in values))
        key = values
        data["at"] = [_text(v) for v in point]
        pt = ", ".join(_text(v) for v in point)
        prompt = f"Let ${f_tex}$. Find $\\nabla f({pt})${_positive_note(d)}."
        steps = [("expr", _vector_text(grad)), ("expr", _vector_text(values))]
        solution = [
            f"$\\nabla f = {_vector_tex(grad)}$.",
            f"At $({pt})$: $\\nabla f({pt}) = {_vector_tex(values)}$.",
        ]
        hint_list = [f"Find the gradient as a formula first, then substitute the point ({pt})."]
    else:
        key = grad
        prompt = f"Find $\\nabla f$ for ${f_tex}${_positive_note(d)}."
        steps = [("expr", f"f_{n} = {_text(g)}") for n, g in zip(names, grad, strict=True)]
        solution = [
            " and ".join(f"$f_{{{n}}} = {_tex(g)}$" for n, g in zip(names, grad, strict=True))
            + ".",
            f"$\\nabla f = {_vector_tex(grad)}$.",
        ]
        hint_list = ["The gradient lists the partial derivatives: find each one separately."]
    answer = _vector_text(key)
    flipped = list(key)
    j = next((i for i, v in enumerate(key) if v != 0), None)
    _need(j is not None)
    flipped[j] = -flipped[j]
    examples = [
        _Ex("partials", steps, answer, "correct", required=True),
        _Ex("one sign slip", [], _vector_text(flipped), "incorrect", required=True),
    ]
    if len(key) == 2 and sp.simplify(key[0] - key[1]) != 0:
        examples.append(
            _Ex(
                "components in the wrong order",
                [],
                _vector_text(key[::-1]),
                "incorrect",
                hint_codes=("COMPONENTS_SWAPPED",),
            )
        )
    if at is not None:
        examples.append(
            _Ex(
                "didn't plug in the point",
                [],
                _vector_text(grad),
                "incorrect",
                hint_codes=("NOT_EVALUATED_AT_POINT",),
            )
        )
    return _Draft(prompt, data, answer, solution, examples, hint_list)


# =========================================================================== calc4: div and curl


def _field_supports(base: Problem) -> bool:
    d = base.data
    if d.get("vars") or d.get("variables"):
        return False
    ctx = MathContext.build(["x", "y", "z"][: len(d["field"])])
    return all(_parses(c, ctx) for c in d["field"])


def _new_field(
    base: Problem, rng: random.Random
) -> tuple[MathContext, list[sp.Symbol], list[sp.Expr]]:
    names = ["x", "y", "z"][: len(base.data["field"])]
    ctx = MathContext.build(names)
    old = [ctx.parse(c) for c in base.data["field"]]
    new = [_perturb(c, rng) for c in old]
    _need(any(sp.simplify(a - b) != 0 for a, b in zip(new, old, strict=True)))
    new = [ctx.parse(_round_trip(c, ctx)) for c in new]
    return ctx, [ctx[n] for n in names], new


def _field_tex(field_: Sequence[sp.Expr]) -> str:
    args = ",".join(str(s) for s in ["x", "y", "z"][: len(field_)])
    inner = ",\\ ".join(_tex(c) for c in field_)
    return f"\\mathbf F({args}) = \\langle {inner} \\rangle"


def _curl(field_: Sequence[sp.Expr], syms: Sequence[sp.Symbol]) -> list[sp.Expr]:
    P, Q, R = field_
    x, y, z = syms
    return [
        sp.diff(R, y) - sp.diff(Q, z),
        sp.diff(P, z) - sp.diff(R, x),
        sp.diff(Q, x) - sp.diff(P, y),
    ]


@_generator("divergence", _field_supports)
def _divergence_make(base: Problem, rng: random.Random) -> _Draft | None:
    ctx, syms, field_ = _new_field(base, rng)
    parts = [sp.diff(c, s) for c, s in zip(field_, syms, strict=True)]
    key_text, key = _tidy(sp.Add(*parts), ctx)
    _need(key != 0)
    data = {**base.data, "field": [_text(c) for c in field_]}
    prompt = f"Find $\\operatorname{{div}}\\mathbf F$ for ${_field_tex(field_)}$."
    examples = [
        _Ex("sum of partials", [("expr", key_text)], key_text, "correct", required=True),
        _Ex("sign slip", [], _text(-key), "incorrect", hint_codes=("SIGN_ERROR",), required=True),
    ]
    if len(field_) == 3:
        curl = _curl(field_, syms)
        if any(c != 0 for c in curl):
            examples.append(
                _Ex(
                    "computed the curl instead",
                    [],
                    _vector_text(curl),
                    "incorrect",
                    hint_codes=("CURL_NOT_DIV",),
                )
            )
    n = len(syms)
    mixed = sp.Add(*[sp.diff(c, syms[(j + 1) % n]) for j, c in enumerate(field_)])
    if sp.simplify(mixed - key) != 0 and mixed != 0:
        examples.append(
            _Ex(
                "paired components with the wrong variables",
                [],
                _text(mixed),
                "incorrect",
                hint_codes=("DIV_MIXED_PARTIALS",),
            )
        )
    names = [str(s) for s in syms]
    comps = ["P", "Q", "R"][:n]
    solution = [
        ", ".join(
            f"$\\frac{{\\partial}}{{\\partial {v}}}\\left({_tex(c)}\\right) = {_tex(p)}$"
            for v, c, p in zip(names, field_, parts, strict=True)
        )
        + ".",
        f"$\\operatorname{{div}}\\mathbf F = {_tex(key)}$.",
    ]
    hint_list = [
        "div F = "
        + " + ".join(f"∂{c}/∂{v}" for c, v in zip(comps, names, strict=True))
        + f", where F = ⟨{', '.join(comps)}⟩.",
        "Differentiate each component only with respect to its own variable.",
    ]
    return _Draft(prompt, data, key_text, solution, examples, hint_list)


@_generator("curl", lambda base: len(base.data.get("field", [])) == 3 and _field_supports(base))
def _curl_make(base: Problem, rng: random.Random) -> _Draft | None:
    ctx, syms, field_ = _new_field(base, rng)
    P, Q, R = field_
    x, y, z = syms
    pairs = [
        (sp.diff(R, y), sp.diff(Q, z)),
        (sp.diff(P, z), sp.diff(R, x)),
        (sp.diff(Q, x), sp.diff(P, y)),
    ]
    key = [sp.expand(a - b) for a, b in pairs]
    _need(any(k != 0 for k in key))
    answer = _vector_text(key)
    data = {**base.data, "field": [_text(c) for c in field_]}
    prompt = f"Find $\\operatorname{{curl}}\\mathbf F$ for ${_field_tex(field_)}$."
    by_parts = "<" + ", ".join(f"{_text(a)} - {_paren_text(_text(b), b)}" for a, b in pairs) + ">"
    examples = [
        _Ex("component by component", [("expr", by_parts)], answer, "correct", required=True),
        _Ex(
            "every difference subtracted the wrong way",
            [],
            _vector_text([-k for k in key]),
            "incorrect",
            hint_codes=("CURL_SIGN",),
            required=True,
        ),
    ]
    div = sp.diff(P, x) + sp.diff(Q, y) + sp.diff(R, z)
    if div != 0:
        examples.append(
            _Ex(
                "computed the divergence instead",
                [],
                _text(div),
                "incorrect",
                hint_codes=("DIV_NOT_CURL",),
            )
        )
    solution = [
        f"$P = {_tex(P)}$, $Q = {_tex(Q)}$, $R = {_tex(R)}$.",
        ", ".join(
            f"${lab} = {_tex(a)} - {_paren_tex(b)}$"
            for lab, (a, b) in zip(("R_y - Q_z", "P_z - R_x", "Q_x - P_y"), pairs, strict=True)
        )
        + ".",
        f"$\\operatorname{{curl}}\\mathbf F = {_vector_tex(key)}$.",
    ]
    hint_list = [
        "curl F = ⟨R_y - Q_z, P_z - R_x, Q_x - P_y⟩.",
        "Expanding the determinant with rows i j k / ∂x ∂y ∂z / P Q R gives the same formula.",
    ]
    return _Draft(prompt, data, answer, solution, examples, hint_list)


# =========================================================================== precalc: composition


def _compose_supports(base: Problem) -> bool:
    d = base.data
    if not isinstance(d.get("compose"), list) or d.get("form", "any") not in ("any", "expanded"):
        return False
    if d.get("forbid") or d.get("expression") or d.get("difference_quotient"):
        return False
    ctx = MathContext.build(d.get("variables") or {"x": "real"})
    return all(_parses(t, ctx) for t in d["compose"])


@_generator("expression", _compose_supports)
def _compose_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    var = d.get("var", "x")
    ctx = MathContext.build(d.get("variables") or {var: "real"})
    x = ctx[var]
    f, g = (_changed(ctx.parse(t), rng, hi=4) for t in d["compose"])
    f_text, g_text = _round_trip(f, ctx), _round_trip(g, ctx)
    f, g = ctx.parse(f_text), ctx.parse(g_text)
    inside = f.subs(x, g)
    expanded = d.get("form", "any") == "expanded"
    key = sp.expand(inside)
    key_text = _round_trip(key, ctx)
    data = {**d, "compose": [f_text, g_text]}
    mistakes: list[tuple[str, str]] = []
    other = sp.expand(g.subs(x, f))
    if sp.simplify(other - key) != 0:
        mistakes.append(
            (
                _text(other),
                "That's g(f(x)). (f ∘ g)(x) means f(g(x)): put g(x) inside f.",
            )
        )
    product = sp.expand(f * g)
    if sp.simplify(product - key) != 0 and sp.simplify(product - other) != 0:
        mistakes.append(
            (_text(product), "Composition isn't multiplication. Replace the x in f with g(x).")
        )
    _need(mistakes)
    examples = [
        _Ex(
            "substitute and expand",
            [("expr", _text(inside)), ("expr", key_text)],
            key_text,
            "correct",
            required=True,
        ),
        _Ex(
            "a known slip",
            [],
            mistakes[0][0],
            "incorrect",
            hint_codes=("KNOWN_MISTAKE",),
            required=True,
        ),
    ]
    if expanded and _text(inside) != key_text:
        examples.append(
            _Ex("not expanded", [], _text(inside), "partial", hint_codes=("FORM_NOT_EXPANDED",))
        )
    ask = "Find $(f \\circ g)(x)$" + (" and expand it." if expanded else ".")
    prompt = f"Let $f({var}) = {_tex(f)}$ and $g({var}) = {_tex(g)}$. {ask}".replace(
        "(x)", f"({var})"
    )
    solution = [
        f"$(f\\circ g)({var}) = f\\left({_tex(g)}\\right) = {_tex(inside)}$.",
        f"$= {_tex(key)}$.",
    ]
    hint_list = [
        f"(f ∘ g)({var}) = f(g({var})): replace every {var} in f with g({var}).",
        "Expand carefully: a squared binomial has a middle term.",
    ]
    return _Draft(prompt, data, key_text, solution, examples, hint_list, mistakes)


# =========================================================================== calc3: iterated


def _iterated_supports(base: Problem) -> bool:
    d = base.data
    if d.get("variables"):
        return False
    get_handler(base.kind).params(base)
    names = [b[0] for b in d["bounds"]]
    ctx = MathContext.build(names)
    ctx.parse(d["integrand"])
    return all(_parses(lo, ctx) and _parses(hi, ctx) for _, lo, hi in d["bounds"])


@_generator("iterated_integral", _iterated_supports)
def _iterated_make(base: Problem, rng: random.Random) -> _Draft | None:
    d = base.data
    names = [b[0] for b in d["bounds"]]
    ctx = MathContext.build(names, allow_integral=True)
    like = _base_key(base, ctx)
    f = _changed(ctx.parse(d["integrand"]), rng)
    f_text = _round_trip(f, ctx)
    f = ctx.parse(f_text)
    bounds = []
    for name, lo, hi in d["bounds"]:
        a, b = _new_bounds(rng, ctx.parse(lo), ctx.parse(hi), 3)
        bounds.append((name, a, b))
    stages = [f]
    for name, a, b in bounds:
        nxt = sp.integrate(stages[-1], (ctx[name], a, b))
        _need(not nxt.has(sp.Integral))
        stages.append(sp.simplify(nxt))
    key = sp.nsimplify(stages[-1]) if stages[-1].is_Rational else stages[-1]
    _need(not key.free_symbols and key != 0 and _nice(key, like, max_len=30))
    _need(not any(abs(r.p) > 2000 or r.q > 2000 for r in key.atoms(sp.Rational)))
    key_text = _round_trip(key, ctx)
    data = {**d, "integrand": f_text, "bounds": [[n, _text(a), _text(b)] for n, a, b in bounds]}
    integrals = "".join(f"\\int_{{{_tex(a)}}}^{{{_tex(b)}}} " for _, a, b in reversed(bounds))
    ds = "\\,".join(f"d{n}" for n, _, _ in bounds)
    prompt = f"Evaluate $\\displaystyle{integrals}{_paren_tex(f)}\\,{ds}$."
    inner = stages[1]
    steps = [("expr", _text(s)) for s in stages[1:-1]] + [("expr", key_text)]
    examples = [
        _Ex("inner then outer", steps, key_text, "correct", required=True),
        _Ex(
            "inner integral slip",
            [("expr", _text(2 * inner))],
            _text(2 * key),
            "incorrect",
            first_error=0,
            hint_codes=("ITERATED_STEP_WRONG",),
            required=True,
        ),
    ]
    if len(bounds) == 2:
        outer, a, b = bounds[1]
        examples.append(
            _Ex(
                "left the integral in",
                [],
                f"int({_text(inner)}, {outer}, {_text(a)}, {_text(b)})",
                "incorrect",
                hint_codes=("ANSWER_HAS_INTEGRAL",),
            )
        )
    if not key.is_Integer:
        examples.append(_Ex("decimal", [], f"{float(key):.4f}", "partial", hint_codes=("INEXACT",)))
    solution = []
    for k, (name, a, b) in enumerate(bounds):
        which = "Inner" if k == 0 else ("Outer" if k == len(bounds) - 1 else "Next")
        solution.append(
            f"{which}: $\\int_{{{_tex(a)}}}^{{{_tex(b)}}} {_paren_tex(stages[k])}\\,d{name} = "
            f"{_tex(stages[k + 1])}$."
        )
    hint_list = [f"Do the inner integral first, treating {', '.join(names[1:])} as constant."]
    return _Draft(prompt, data, key_text, solution, examples, hint_list)


# =========================================================================== calc4: ODEs


def _ode_coefficients(base: Problem) -> tuple[int, int] | None:
    """``y'' + b y' + c y = 0`` with integer b, c and distinct integer roots, else ``None``."""
    d = base.data
    if d.get("ics") or d.get("variables") or d.get("func", "y") != "y" or d.get("var", "x") != "x":
        return None
    handler = get_handler("ode_solution")
    s = handler.setup(base, handler.params(base))
    if s.order != 2:
        return None
    y0, y1, y2 = s.dsym
    E = sp.expand(s.E)
    poly = sp.Poly(E, y2, y1, y0)
    if poly.total_degree() != 1 or E.subs({y0: 0, y1: 0, y2: 0}) != 0:
        return None
    a2, a1, a0 = (poly.coeff_monomial(v) for v in (y2, y1, y0))
    if a2 != 1 or not (a1.is_Integer and a0.is_Integer):
        return None
    r = sp.Symbol("r")
    roots = sp.roots(r**2 + a1 * r + a0, r)
    if len(roots) != 2 or not all(k.is_Integer for k in roots):
        return None
    return int(a1), int(a0)


def _signed(coeff: int, name: str, first: bool = False) -> str:
    if coeff == 0:
        return ""
    body = name if abs(coeff) == 1 else f"{abs(coeff)}{name}"
    if first:
        return f"-{body}" if coeff < 0 else body
    return f" - {body}" if coeff < 0 else f" + {body}"


def _constant(c: int) -> str:
    return f" + {c}" if c > 0 else f" - {-c}"


def _exp_text(r: int) -> str:
    return {1: "e^x", -1: "e^(-x)"}.get(r, f"e^({r}x)")


def _exp_tex(r: int) -> str:
    return {1: "e^{x}", -1: "e^{-x}"}.get(r, f"e^{{{r}x}}")


@_generator("ode_solution", lambda base: _ode_coefficients(base) is not None)
def _ode_make(base: Problem, rng: random.Random) -> _Draft | None:
    coeffs = _ode_coefficients(base)
    assert coeffs is not None
    r = sp.Symbol("r")
    old_roots = set(sp.roots(r**2 + coeffs[0] * r + coeffs[1], r))
    for _ in range(40):
        r1, r2 = sorted(rng.sample([-4, -3, -2, -1, 1, 2, 3, 4], 2))
        b, c = -(r1 + r2), r1 * r2
        if b != 0 and abs(b) <= 9 and abs(c) <= 9 and {r1, r2} != old_roots:
            break
    else:
        return None
    ode = f"y''{_signed(b, "y'")}{_signed(c, 'y')} = 0"
    char_lhs = f"r^2{_signed(b, 'r')}{_constant(c)}"
    char = f"{char_lhs} = 0"
    answer = f"y = C1 {_exp_text(r1)} + C2 {_exp_text(r2)}"
    data = {**base.data, "ode": ode}
    flipped = f"r^2{_signed(-b, 'r')}{_constant(c)} = 0"
    examples = [
        _Ex(
            "characteristic equation",
            [("characteristic", char), ("roots", f"r = {r1} or r = {r2}")],
            answer,
            "correct",
            required=True,
        ),
        _Ex(
            "only one constant",
            [],
            f"y = C {_exp_text(r2)}",
            "partial",
            hint_codes=("NOT_GENERAL",),
            required=True,
        ),
        _Ex(
            "sign slip in the characteristic equation",
            [("characteristic", flipped), ("roots", f"r = {-r2}, {-r1}")],
            f"y = C1 {_exp_text(-r2)} + C2 {_exp_text(-r1)}",
            "incorrect",
            first_error=0,
            hint_codes=("ROOT_SIGNS",),
        ),
    ]
    factored = f"(r{_constant(-r1)})(r{_constant(-r2)})"
    prompt = f"Find the general solution of ${ode}$."
    solution = [
        f"Characteristic equation: ${char_lhs} = {factored} = 0$, so $r = {r1}, {r2}$.",
        f"$y = C_1 {_exp_tex(r1)} + C_2 {_exp_tex(r2)}$.",
    ]
    hint_list = [
        "Try y = e^(rx): you get the characteristic equation, a quadratic in r.",
        "Two different real roots r1 and r2 give y = C1 e^(r1 x) + C2 e^(r2 x).",
    ]
    return _Draft(prompt, data, answer, solution, examples, hint_list)
