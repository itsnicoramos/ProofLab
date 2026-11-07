"""Series (SPEC §5.4): ``series_convergence``, ``series_sum``, ``taylor_polynomial``.

Convergence submissions name tests (``test`` steps), give the limit a test needs (``limit``
steps) and comparison series (``compare`` steps). ProofLab runs each named test on the
problem's own aₙ and checks that it applies, is conclusive, and that the student's limit is
right. The answer itself is compared with the key; the content tests re-derive the key with
``Sum(...).is_convergent()``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

import mpmath
import sympy as sp
from pydantic import BaseModel, ConfigDict, Field

from prooflab.engine import hints
from prooflab.engine.algebra import (
    MathContext,
    MathInputError,
    VarSpec,
    compile_numeric,
    equivalent,
    strip_label,
    to_latex,
    values_equal,
)
from prooflab.engine.checker import (
    ContentError,
    Detector,
    TopicHandler,
    VerdictBuilder,
    register,
)
from prooflab.engine.models import Problem, StepStatus, Submission, VerdictStatus
from prooflab.engine.topics.calc1.limits import (
    DNE,
    LimitValue,
    compute_limit,
    limit_values_equal,
    parse_limit_value,
)

hints.register_many(
    {
        "SERIES_BAD_ANSWER": "Answer with 'converges' or 'diverges' (you can add 'absolutely' "
        "or 'conditionally').",
        "SERIES_UNKNOWN_TEST": "ProofLab doesn't recognise that test. Use: ratio, root, "
        "divergence, p-series, geometric, integral, comparison, limit comparison, or alternating.",
        "SERIES_TEST_OK": "The {test} applies here and settles the question.",
        "SERIES_TEST_DOES_NOT_APPLY": "The {test} doesn't apply here: {reason}.",
        "DIVERGENCE_TEST_INCONCLUSIVE": "The terms go to 0, so the divergence test is "
        "inconclusive. It can only ever show divergence.",
        "RATIO_TEST_INCONCLUSIVE": "The limit is 1, so the {test} is inconclusive. Try another "
        "test.",
        "LIMIT_COMPARISON_INCONCLUSIVE": "For the limit comparison test, lim aₙ/bₙ must be a "
        "positive finite number. Pick a different bₙ.",
        "COMPARISON_WRONG_DIRECTION": "This comparison doesn't settle anything: being smaller "
        "than a divergent series, or bigger than a convergent one, tells you nothing.",
        "SERIES_COMPARISON_INEQUALITY": "The inequality between aₙ and your comparison series "
        "doesn't hold for large n.",
        "SERIES_COMPARE_MISSING": "A comparison test needs a series to compare with. Add a "
        "'compare' step, like 1/n^2.",
        "SERIES_COMPARE_NOTED": "Comparison series noted.",
        "WRONG_TEST_LIMIT": "That isn't the limit this test needs. Recompute it carefully.",
        "SERIES_LIMIT_NOT_NEEDED": "This test doesn't use a limit, so this step wasn't checked.",
        "SERIES_LIMIT_WITHOUT_TEST": "Name the test (a 'test' step) before giving its limit.",
        "SERIES_NOTE": "Notes aren't checked.",
        "SERIES_NO_CONCLUSIVE_TEST": "Your answer is right, but none of your tests actually "
        "settles it. Add a test that does.",
        "SERIES_CONCLUSION_MISMATCH": "Your {test} result doesn't support that conclusion. Look "
        "again at what the test says.",
        "SERIES_ABS_DIVERGES_ONLY": "Σ|aₙ| diverging only rules out absolute convergence. "
        "The series Σaₙ itself can still converge.",
        "TERMS_TO_ZERO_NOT_ENOUGH": "aₙ → 0 is not enough for convergence: the harmonic series "
        "Σ1/n is the classic counterexample.",
        "SERIES_SPECIFY_TYPE": "It does converge, but say how: absolutely or conditionally?",
        "SERIES_POSITIVE_TERMS": "All the terms have the same sign, so if the series converges, "
        "it converges absolutely.",
        "SERIES_CONVERGENCE_TYPE": "Check Σ|aₙ|: whether it converges decides absolute versus "
        "conditional convergence.",
        "START_INDEX": "Check the starting index: a/(1 − r) needs a to be the series' first term.",
        "SERIES_SUM_TERM_LIMIT": "The sum of a series isn't the limit of its terms.",
        "SERIES_SUM_STEP_WRONG": "This value isn't the sum of the series.",
        "SERIES_PARTIAL_SUM_WRONG": "That formula doesn't match the partial sums S_N. Test it "
        "with a small N.",
        "SERIES_PARTIAL_SUM_VARIABLE": "Write partial sums in terms of N (the last index), and "
        "values as plain numbers.",
        "MISSING_FACTORIALS": "Each Taylor coefficient is f⁽ᵏ⁾(a)/k!. Don't forget to divide by "
        "k!.",
        "WRONG_CENTER": "Center the polynomial at x = a: use powers of (x − a) and evaluate the "
        "derivatives at a.",
        "TAYLOR_WRONG_DEGREE": "Check the degree: include every term up to the requested power, "
        "and no higher.",
    }
)


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SeriesParams(_Params):
    term: str
    var: str = "n"
    start: int = Field(default=1, ge=0, le=10)


class TaylorParams(_Params):
    function: str
    var: str = "x"
    center: str = "0"
    degree: int = Field(ge=0, le=12)
    variables: dict[str, str] | None = None


def series_context(var: str, start: int, *, partial: bool = False) -> MathContext:
    """An integer index ``n ≥ start`` (and ``N`` for partial sums)."""
    sym = (
        sp.Symbol(var, integer=True, positive=True)
        if start >= 1
        else sp.Symbol(var, integer=True, nonnegative=True)
    )
    symbols = {var: sym}
    specs = {sym: VarSpec("integer", max(start, 1), start + 30)}
    if partial:
        big_n = sp.Symbol("N", integer=True, positive=True)
        symbols["N"] = big_n
        specs[big_n] = VarSpec("integer", max(start, 1), start + 12)
    return MathContext(symbols=symbols, specs=specs)


# --------------------------------------------------------------------------- numerics


def _values(expr: sp.Expr, n: sp.Symbol, ns: list[int]) -> list[float | None]:
    fn = compile_numeric(expr, [n])
    out: list[float | None] = []
    with mpmath.workdps(30):
        for k in ns:
            try:
                v = mpmath.mpc(fn(mpmath.mpf(k)))
            except Exception:  # noqa: BLE001
                out.append(None)
                continue
            if not mpmath.isfinite(v.real) or abs(v.imag) > 1e-12 * max(1, abs(v.real)):
                out.append(None)
            else:
                out.append(float(v.real))
    return out


def _signs(a: sp.Expr, n: sp.Symbol, start: int) -> str:
    """``positive``, ``negative``, ``alternating`` or ``mixed`` (sampled over 40 terms)."""
    vals = [v for v in _values(a, n, list(range(start, start + 40))) if v is not None]
    if not vals:
        return "mixed"
    if all(v > 0 for v in vals):
        return "positive"
    if all(v < 0 for v in vals):
        return "negative"
    if all(v != 0 for v in vals) and all(
        (u > 0) != (w > 0) for u, w in zip(vals, vals[1:], strict=False)
    ):
        return "alternating"
    return "mixed"


def _eventually_decreasing(a: sp.Expr, n: sp.Symbol, start: int) -> bool:
    ns = list(range(start + 5, start + 200)) + [1000, 10_000]
    vals = _values(a, n, ns)
    if any(v is None for v in vals):
        return False
    return all(u >= w for u, w in zip(vals, vals[1:], strict=False))


def _limit(expr: sp.Expr, n: sp.Symbol) -> LimitValue | None:
    return compute_limit(expr, n, sp.oo, "both")


def p_value(a: sp.Expr, n: sp.Symbol) -> sp.Expr | None:
    """p if ``a = c / n^p`` (c ≠ 0), else ``None``."""
    try:
        r = sp.simplify(n * sp.diff(a, n) / a)
    except Exception:  # noqa: BLE001
        return None
    if r.has(n) or r.has(sp.I):
        return None
    p = -r
    c = sp.simplify(a * n**p)
    if c.has(n) or c == 0:
        return None
    return p


def geometric_ratio(a: sp.Expr, n: sp.Symbol) -> sp.Expr | None:
    try:
        r = sp.simplify(sp.combsimp(a.subs(n, n + 1) / a))
    except Exception:  # noqa: BLE001
        return None
    return None if r.has(n) else r


def _is_zero(v: LimitValue | None) -> bool:
    return v is not None and not isinstance(v, str) and v == 0


def _finite_positive(v: LimitValue | None) -> bool:
    return v is not None and not isinstance(v, str) and v.is_finite and bool(v > 0)


def _compare_one(v: LimitValue, one: int = 1) -> int | None:
    """-1, 0, 1 for v <, =, > 1 (∞ counts as > 1); ``None`` for DNE."""
    if isinstance(v, str):
        return None
    if v is sp.oo:
        return 1
    if values_equal(v, one):
        return 0
    return -1 if bool(v < one) else 1


def known_convergence(b: sp.Expr, n: sp.Symbol, start: int) -> bool | None:
    """Does Σbₙ converge? p-series and geometric first, then SymPy."""
    p = p_value(b, n)
    if p is not None:
        return bool(p > 1)
    r = geometric_ratio(b, n)
    if r is not None:
        return bool(abs(r) < 1)
    try:
        result = sp.Sum(b, (n, start, sp.oo)).is_convergent()
    except Exception:  # noqa: BLE001
        return None
    return bool(result) if result in (True, False, sp.true, sp.false) else None


# --------------------------------------------------------------------------- tests

TEST_NAMES = {
    "ratio": "ratio test",
    "root": "root test",
    "divergence": "divergence test",
    "p_series": "p-series test",
    "geometric": "geometric series test",
    "integral": "integral test",
    "comparison": "comparison test",
    "limit_comparison": "limit comparison test",
    "alternating": "alternating series test",
}
_ALIASES = {
    "ratio": "ratio",
    "root": "root",
    "nth root": "root",
    "n th root": "root",
    "divergence": "divergence",
    "nth term": "divergence",
    "n th term": "divergence",
    "term": "divergence",
    "p": "p_series",
    "geometric": "geometric",
    "integral": "integral",
    "comparison": "comparison",
    "direct comparison": "comparison",
    "limit comparison": "limit_comparison",
    "lct": "limit_comparison",
    "alternating": "alternating",
    "ast": "alternating",
    "leibniz": "alternating",
}
_FILLER = re.compile(r"\b(the|test|for|series|use|using|by)\b")


def normalize_test(text: str) -> str | None:
    t = text.lower().replace("-", " ")
    t = _FILLER.sub(" ", t)
    t = re.sub(r"[^a-z ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return _ALIASES.get(t)


CONVERGES, ABSOLUTELY, NOT_ABSOLUTELY, DIVERGES = (
    "converges",
    "absolutely",
    "not_absolutely",
    "diverges",
)


@dataclass(frozen=True)
class TestResult:
    applies: bool = True
    facts: frozenset[str] = frozenset()
    value: LimitValue | None = None
    reason: str = ""
    inconclusive: str | None = None
    unknown: bool = False
    comparison_fails: bool = False


_ABS = frozenset({CONVERGES, ABSOLUTELY})


@lru_cache(maxsize=256)
def run_test(
    name: str, a: sp.Expr, n: sp.Symbol, start: int, b: sp.Expr | None = None
) -> TestResult:
    """Run a convergence test on Σaₙ (n ≥ start). ``b`` is the comparison series, if any."""
    signs = _signs(a, n, start)
    same_sign = signs in ("positive", "negative")
    pos = -a if signs == "negative" else (a if same_sign else sp.Abs(a))
    if not same_sign:
        pos = sp.simplify(pos)

    def by_abs(converges: bool) -> frozenset[str]:
        # Behaviour of Σ|aₙ| (or of Σaₙ itself when the terms don't change sign).
        if converges:
            return _ABS
        return frozenset({DIVERGES}) if same_sign else frozenset({NOT_ABSOLUTELY})

    if name == "divergence":
        lim = _limit(a, n)
        if lim is None:
            return TestResult(unknown=True)
        if _is_zero(lim):
            return TestResult(value=lim, inconclusive="DIVERGENCE_TEST_INCONCLUSIVE")
        return TestResult(facts=frozenset({DIVERGES}), value=lim)

    if name in ("ratio", "root"):
        if name == "ratio":
            try:
                inner = sp.Abs(sp.simplify(sp.combsimp(a.subs(n, n + 1) / a)))
            except Exception:  # noqa: BLE001
                return TestResult(unknown=True)
        else:
            inner = sp.Abs(a) ** (sp.Integer(1) / n)
        lim = _limit(inner, n)
        if lim is None:
            return TestResult(unknown=True)
        side = _compare_one(lim)
        if side is None:
            return TestResult(applies=False, value=lim, reason="the limit it needs doesn't exist")
        if side == 0:
            return TestResult(value=lim, inconclusive="RATIO_TEST_INCONCLUSIVE")
        return TestResult(facts=_ABS if side < 0 else frozenset({DIVERGES}), value=lim)

    if name == "p_series":
        p = p_value(pos, n)
        if p is None:
            return TestResult(applies=False, reason="the terms aren't a constant times 1/nᵖ")
        return TestResult(facts=by_abs(bool(p > 1)), value=p)

    if name == "geometric":
        r = geometric_ratio(a, n)
        if r is None:
            return TestResult(applies=False, reason="the ratio of consecutive terms isn't constant")
        return TestResult(facts=_ABS if bool(abs(r) < 1) else frozenset({DIVERGES}), value=r)

    if name == "integral":
        if not _eventually_decreasing(pos, n, start) or any(
            v is None or v <= 0 for v in _values(pos, n, list(range(start, start + 40)))
        ):
            return TestResult(applies=False, reason="the terms aren't positive and decreasing")
        x = sp.Dummy("x", positive=True)
        try:
            value = sp.integrate(pos.subs(n, x), (x, start, sp.oo))
        except Exception:  # noqa: BLE001
            return TestResult(unknown=True)
        if value.has(sp.Integral):
            return TestResult(unknown=True)
        finite = value.is_finite
        if finite is None:
            return TestResult(unknown=True)
        return TestResult(facts=by_abs(bool(finite)), value=value if finite else sp.oo)

    if name in ("comparison", "limit_comparison"):
        if b is None:
            return TestResult(applies=False, reason="it needs a comparison series")
        b_vals = _values(b, n, list(range(start, start + 40)))
        if any(v is None or v < 0 for v in b_vals):
            return TestResult(applies=False, reason="the comparison series needs nonnegative terms")
        b_conv = known_convergence(b, n, start)
        if name == "limit_comparison":
            lim = _limit(pos / b, n)
            if lim is None or b_conv is None:
                return TestResult(unknown=True)
            if not _finite_positive(lim):
                return TestResult(value=lim, inconclusive="LIMIT_COMPARISON_INCONCLUSIVE")
            return TestResult(facts=by_abs(b_conv), value=lim)
        ns = list(range(start + 10, start + 80)) + [200, 1000, 10_000, 1_000_000]
        av, bv = _values(pos, n, ns), _values(b, n, ns)
        pairs = [(u, w) for u, w in zip(av, bv, strict=False) if u is not None and w is not None]
        if len(pairs) < 10 or b_conv is None:
            return TestResult(unknown=True)
        le = all(u <= w * (1 + 1e-12) + 1e-300 for u, w in pairs)
        ge = all(u >= w * (1 - 1e-12) for u, w in pairs)
        if le and b_conv:
            return TestResult(facts=_ABS)
        if ge and not b_conv:
            return TestResult(facts=by_abs(False))
        if le or ge:
            return TestResult(inconclusive="COMPARISON_WRONG_DIRECTION")
        return TestResult(applies=False, comparison_fails=True)

    if name == "alternating":
        if signs != "alternating":
            return TestResult(applies=False, reason="the terms don't alternate in sign")
        lim = _limit(sp.Abs(a), n)
        if lim is None:
            return TestResult(unknown=True)
        if not _is_zero(lim) or not _eventually_decreasing(pos, n, start):
            return TestResult(applies=False, value=lim, reason="|aₙ| must decrease to 0")
        return TestResult(facts=frozenset({CONVERGES}), value=lim)

    raise ValueError(f"unknown test {name!r}")


# --------------------------------------------------------------------------- convergence


def parse_convergence(text: str) -> tuple[str, str | None]:
    t = re.sub(r"\s+", " ", text.strip().lower())
    if "diverg" in t or re.search(r"\b(not|doesn't|does not|never)\b.*converg", t):
        return (DIVERGES, None)
    if "converg" in t:
        if "absolut" in t:
            return (CONVERGES, ABSOLUTELY)
        if "condition" in t:
            return (CONVERGES, "conditionally")
        return (CONVERGES, None)
    raise MathInputError(hints.message("SERIES_BAD_ANSWER"), "SERIES_BAD_ANSWER")


def _describe(answer: tuple[str, str | None]) -> str:
    verdict, kind = answer
    return rf"\text{{{verdict}{' ' + kind if kind else ''}}}"


@dataclass
class _TestStep:
    index: int
    name: str
    result: TestResult | None = None
    facts: frozenset[str] = field(default_factory=frozenset)


@register
class SeriesConvergenceHandler(TopicHandler):
    kind = "series_convergence"
    Params = SeriesParams
    step_kinds = frozenset({"test", "limit", "compare", "note"})
    syntax_help = (
        "Answer 'converges' or 'diverges' (add 'absolutely' or 'conditionally' for series with "
        "mixed signs). Justify with steps: 'test' (ratio, root, divergence, p-series, geometric, "
        "integral, comparison, limit comparison, alternating), 'limit' (the value the test "
        "needs, like L = 1/2), and 'compare' (a comparison series, like 1/n^2)."
    )

    def setup(self, problem: Problem, p: SeriesParams):
        ctx = series_context(p.var, p.start)
        return ctx, ctx[p.var], ctx.parse(p.term), parse_convergence(problem.answer)

    def validate(self, problem: Problem, params: SeriesParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def verify_key(self, problem: Problem, params: SeriesParams) -> bool | None:
        ctx, n, a, key = self.setup(problem, params)
        try:
            conv = sp.Sum(a, (n, params.start, sp.oo)).is_convergent()
            if key[0] == DIVERGES:
                return conv is False or conv == sp.false
            if not conv:
                return False
            if key[1] is None:
                return True
            absolute = sp.Sum(sp.Abs(a), (n, params.start, sp.oo)).is_convergent()
        except Exception:  # noqa: BLE001
            return None
        return bool(absolute) == (key[1] == ABSOLUTELY)

    def check(
        self, problem: Problem, params: SeriesParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, n, a, key = self.setup(problem, params)
        start = params.start
        tests: list[_TestStep] = []
        compares: list[tuple[int, sp.Expr]] = []
        limits: list[tuple[int, str, LimitValue]] = []

        for i, step in enumerate(submission.steps):
            if step.kind == "note":
                vb.step(i, step.kind, StepStatus.UNCHECKED, code="SERIES_NOTE")
            elif step.kind == "test":
                name = normalize_test(step.content)
                if name is None:
                    vb.error(i, step.kind, "SERIES_UNKNOWN_TEST")
                else:
                    tests.append(_TestStep(i, name))
            elif step.kind == "compare":
                b = self.parse_step(vb, i, step, lambda t: ctx.parse(strip_label(t)))
                if b is not None:
                    compares.append((i, b))
                    vb.ok(i, step.kind, latex=to_latex(b), code="SERIES_COMPARE_NOTED")
            elif step.kind == "limit":
                value = self.parse_step(vb, i, step, lambda t: parse_limit_value(t, ctx))
                if value is not None:
                    limits.append((i, step.kind, value))

        for t in tests:
            self._run_test_step(t, a, n, start, compares, vb)
        for i, kind, value in limits:
            self._check_limit_step(i, kind, value, tests, vb)

        facts = frozenset().union(*(t.facts for t in tests)) if tests else frozenset()
        self._grade(problem, a, n, start, key, facts, tests, submission.answer, vb)

    def _run_test_step(self, t: _TestStep, a, n, start, compares, vb: VerdictBuilder) -> None:
        display = TEST_NAMES[t.name]
        b = None
        if t.name in ("comparison", "limit_comparison"):
            before = [e for i, e in compares if i < t.index]
            after = [e for i, e in compares if i > t.index]
            b = before[-1] if before else (after[0] if after else None)
            if b is None:
                vb.error(t.index, "test", "SERIES_COMPARE_MISSING")
                return
        result = run_test(t.name, a, n, start, b)
        t.result = result
        if result.unknown:
            vb.step(t.index, "test", StepStatus.UNCHECKED, code="UNVERIFIED_STEP")
        elif result.comparison_fails:
            vb.error(t.index, "test", "SERIES_COMPARISON_INEQUALITY")
        elif not result.applies:
            vb.error(
                t.index, "test", "SERIES_TEST_DOES_NOT_APPLY", test=display, reason=result.reason
            )
        elif result.inconclusive:
            vb.step(t.index, "test", StepStatus.WARNING, code=result.inconclusive, test=display)
        else:
            t.facts = result.facts
            vb.ok(t.index, "test", code="SERIES_TEST_OK", test=display)

    @staticmethod
    def _check_limit_step(
        i: int, kind: str, value: LimitValue, tests: list[_TestStep], vb: VerdictBuilder
    ) -> None:
        latex = r"\text{DNE}" if value == DNE else to_latex(value)
        owner = [t for t in tests if t.index < i]
        if not owner:
            vb.error(i, kind, "SERIES_LIMIT_WITHOUT_TEST", latex=latex)
            return
        result = owner[-1].result
        if result is None or result.unknown:
            vb.step(i, kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
        elif result.value is None:
            vb.step(i, kind, StepStatus.UNCHECKED, latex=latex, code="SERIES_LIMIT_NOT_NEEDED")
        elif limit_values_equal(value, result.value):
            vb.ok(i, kind, latex=latex)
        else:
            vb.error(i, kind, "WRONG_TEST_LIMIT", latex=latex)

    def _grade(self, problem, a, n, start, key, facts, tests, text, vb: VerdictBuilder) -> None:
        if text is None or not text.strip():
            return
        try:
            student = parse_convergence(text)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return
        latex = _describe(student)
        same_sign = _signs(a, n, start) in ("positive", "negative")
        verdict, kind = student
        key_verdict, key_kind = key

        status, code = VerdictStatus.INCORRECT, "WRONG"
        if verdict == key_verdict == DIVERGES:
            status, code = VerdictStatus.CORRECT, "CORRECT"
        elif verdict == key_verdict == CONVERGES:
            if kind == "conditionally" and same_sign:
                code = "SERIES_POSITIVE_TERMS"
            elif key_kind is None or kind == key_kind or (kind is None and same_sign):
                status, code = VerdictStatus.CORRECT, "CORRECT"
            elif kind is None:
                status, code = VerdictStatus.PARTIAL, "SERIES_SPECIFY_TYPE"
            else:
                code = "SERIES_CONVERGENCE_TYPE"

        if status is VerdictStatus.CORRECT and tests and not facts & {CONVERGES, DIVERGES}:
            status, code = VerdictStatus.PARTIAL, "SERIES_NO_CONCLUSIVE_TEST"
        vb.answer(status, latex=latex, code=code)
        if code not in ("CORRECT", "WRONG"):
            vb.hint(code)
        if status is not VerdictStatus.INCORRECT:
            return

        contradicted = (
            (verdict == DIVERGES and CONVERGES in facts)
            or (verdict == CONVERGES and DIVERGES in facts)
            or (kind == "conditionally" and ABSOLUTELY in facts)
            or (kind == ABSOLUTELY and NOT_ABSOLUTELY in facts)
        )
        if contradicted:
            settling = next(t for t in tests if t.facts)
            vb.hint("SERIES_CONCLUSION_MISMATCH", test=TEST_NAMES[settling.name])
            return
        mistake = self.match_mistake(problem, student, parse_convergence, lambda s, m: s == m)
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", hint=mistake.hint)
        elif verdict == DIVERGES and NOT_ABSOLUTELY in facts:
            vb.hint("SERIES_ABS_DIVERGES_ONLY")
        elif verdict == CONVERGES and key_verdict == DIVERGES and _is_zero(_limit(a, n)):
            vb.hint("TERMS_TO_ZERO_NOT_ENOUGH")


# --------------------------------------------------------------------------- sums


@register
class SeriesSumHandler(TopicHandler):
    kind = "series_sum"
    Params = SeriesParams
    syntax_help = (
        "Enter the exact sum. Steps can be values (like (1/2)/(1 - 1/2)) or a partial-sum "
        "formula in N, like 1 - 1/(N+1)."
    )

    def setup(self, problem: Problem, p: SeriesParams):
        ctx = series_context(p.var, p.start, partial=True)
        key = ctx.parse(strip_label(problem.answer))
        if key.free_symbols:
            raise ContentError(f"{problem.id}: the sum must be a number")
        return ctx, ctx[p.var], ctx["N"], ctx.parse(p.term), key

    def validate(self, problem: Problem, params: SeriesParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def verify_key(self, problem: Problem, params: SeriesParams) -> bool | None:
        ctx, n, big_n, a, key = self.setup(problem, params)
        try:
            total = sp.summation(a, (n, params.start, sp.oo))
        except Exception:  # noqa: BLE001
            return None
        if total.has(sp.Sum):
            return None
        return values_equal(total, key)

    def check(
        self, problem: Problem, params: SeriesParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, n, big_n, a, key = self.setup(problem, params)
        start = params.start
        for i, step in enumerate(submission.steps):
            expr = self.parse_step(vb, i, step, lambda t: ctx.parse(strip_label(t)))
            if expr is None:
                continue
            latex = to_latex(expr)
            if expr.has(n):
                vb.error(i, step.kind, "SERIES_PARTIAL_SUM_VARIABLE", latex=latex)
            elif expr.has(big_n):
                ok = all(
                    values_equal(
                        expr.subs(big_n, m), sum(a.subs(n, k) for k in range(start, m + 1))
                    )
                    for m in range(max(start, 1), max(start, 1) + 6)
                )
                if ok:
                    vb.ok(i, step.kind, latex=latex)
                else:
                    vb.error(i, step.kind, "SERIES_PARTIAL_SUM_WRONG", latex=latex)
            elif values_equal(expr, key):
                vb.ok(i, step.kind, latex=latex)
            else:
                vb.error(i, step.kind, "SERIES_SUM_STEP_WRONG", latex=latex)

        detectors: list[Detector] = []
        shifted = [key - a.subs(n, start)]
        if start >= 1:
            before = a.subs(n, start - 1)
            if before.is_finite:
                shifted.append(key + before)
        for wrong in shifted:
            detectors.append(lambda s, w=wrong: ("START_INDEX", {}) if values_equal(s, w) else None)
        term_limit = _limit(a, n)
        if term_limit is not None and not isinstance(term_limit, str) and term_limit.is_finite:
            detectors.append(
                lambda s, w=term_limit: (
                    ("SERIES_SUM_TERM_LIMIT", {}) if values_equal(s, w) else None
                )
            )
        self.grade_expression(
            vb, problem, ctx, submission.answer, key, require_exact=True, detectors=detectors
        )


# --------------------------------------------------------------------------- Taylor


def taylor(
    f: sp.Expr,
    x: sp.Symbol,
    a: sp.Expr,
    degree: int,
    *,
    factorials: bool = True,
    shift: bool = True,
) -> sp.Expr:
    total = sp.Integer(0)
    d = f
    for k in range(degree + 1):
        coeff = d.subs(x, a)
        if factorials:
            coeff = coeff / sp.factorial(k)
        total += coeff * ((x - a) if shift else x) ** k
        d = sp.diff(d, x)
    return sp.expand(total)


@register
class TaylorPolynomialHandler(TopicHandler):
    kind = "taylor_polynomial"
    Params = TaylorParams
    syntax_help = (
        "Enter the polynomial, e.g. 1 + x + x^2/2. Powers of (x - a) are fine, expanded or not. "
        "Each step should be the same polynomial in another form."
    )

    def setup(self, problem: Problem, p: TaylorParams):
        ctx = MathContext.build(p.variables or {p.var: "real"})
        x = ctx[p.var]
        a = ctx.parse(p.center)
        if a.free_symbols:
            raise ContentError(f"{problem.id}: the center must be a number")
        return ctx, x, ctx.parse(p.function), a, ctx.parse(strip_label(problem.answer))

    def validate(self, problem: Problem, params: TaylorParams) -> None:
        try:
            self.setup(problem, params)
        except (MathInputError, KeyError) as exc:
            raise ContentError(f"{problem.id}: {exc}") from exc

    def verify_key(self, problem: Problem, params: TaylorParams) -> bool | None:
        ctx, x, f, a, key = self.setup(problem, params)
        try:
            reference = sp.series(f, x, a, params.degree + 1).removeO()
        except Exception:  # noqa: BLE001
            reference = taylor(f, x, a, params.degree)
        return equivalent(reference, key, ctx)

    def check(
        self, problem: Problem, params: TaylorParams, submission: Submission, vb: VerdictBuilder
    ) -> None:
        ctx, x, f, a, key = self.setup(problem, params)
        n = params.degree
        candidates: list[tuple[sp.Expr, str]] = [
            (taylor(f, x, a, n, factorials=False), "MISSING_FACTORIALS")
        ]
        if a != 0:
            candidates += [
                (taylor(f, x, sp.Integer(0), n), "WRONG_CENTER"),
                (taylor(f, x, a, n, shift=False), "WRONG_CENTER"),
            ]
        if n >= 1:
            candidates.append((taylor(f, x, a, n - 1), "TAYLOR_WRONG_DEGREE"))
        candidates.append((taylor(f, x, a, n + 1), "TAYLOR_WRONG_DEGREE"))
        detectors: list[Detector] = []
        for wrong, code in candidates:
            if equivalent(wrong, key, ctx):
                continue
            detectors.append(
                lambda s, w=wrong, c=code: (
                    (c, {}) if equivalent(s, w, ctx, symbolic_fallback=False) else None
                )
            )
        self.check_steps_against(
            vb, submission.steps, ctx, key, problem=problem, detectors=detectors
        )
        self.grade_expression(
            vb, problem, ctx, submission.answer, key, require_exact=True, detectors=detectors
        )
