"""Route a submission to its problem kind and build the verdict (SPEC §4.1, §5).

Topic modules define a :class:`TopicHandler` subclass per problem kind and decorate it with
:func:`register`. :func:`check` runs a handler in-process; :func:`check_isolated` runs it in a
separate worker process with a hard timeout (what the API uses).
"""

from __future__ import annotations

import importlib
import logging
import multiprocessing as mp
import queue
import sys
import threading
from collections.abc import Callable, Sequence
from typing import Any, ClassVar

import sympy as sp
from pydantic import BaseModel, ValidationError

from prooflab.engine import hints
from prooflab.engine.algebra import (
    MathContext,
    MathInputError,
    approximately_equal,
    contains_float,
    equivalent,
    relation,
    strip_label,
    to_latex,
)
from prooflab.engine.models import (
    SCORES,
    AnswerResult,
    Feedback,
    Mistake,
    Problem,
    Step,
    StepResult,
    StepStatus,
    Submission,
    Verdict,
    VerdictStatus,
)

log = logging.getLogger(__name__)

# Engine modules that register problem kinds, as "<course>.<module>" under engine/topics/.
# They are *not* the content topics: those are listed per course in content/courses.json (for
# MATH 123, the book's chapters), and one engine module can serve several topics.
ENGINE_MODULES: tuple[str, ...] = (
    "proofs.parity",
    "proofs.divisibility",
    "proofs.sets",
    "proofs.logic",
    "proofs.counting",
    "proofs.contradiction",
    "proofs.set_proofs",
    "proofs.induction",
    "precalc.functions",
    "precalc.trig",
    "precalc.exp_log",
    "calc1.limits",
    "calc1.derivatives",
    "calc2.integrals",
    "calc2.series",
    "calc3.partials",
    "calc3.multiple_integrals",
    "calc4.vector_calc",
    "calc4.diff_eq",
)


class ContentError(ValueError):
    """A problem's data or answer key is unusable."""


# --------------------------------------------------------------------------- verdict builder


class VerdictBuilder:
    """Collects step results, the answer result and hints, then applies SPEC §4.1."""

    def __init__(self, problem: Problem) -> None:
        self.problem = problem
        self.steps: list[StepResult] = []
        self.answer_result: AnswerResult | None = None
        self.hints: list[Feedback] = []
        self.status_override: VerdictStatus | None = None

    # -- recording
    def step(
        self,
        index: int,
        kind: str,
        status: StepStatus,
        message: str | None = None,
        *,
        latex: str | None = None,
        code: str | None = None,
        **params: object,
    ) -> StepResult:
        if message is None:
            message = hints.message(code, **params) if code else ""
        result = StepResult(
            index=index, kind=kind, status=status, message=message, latex=latex, code=code
        )
        self.steps.append(result)
        return result

    def ok(self, index: int, kind: str, message: str | None = None, **kw: Any) -> StepResult:
        return self.step(index, kind, StepStatus.OK, message or hints.message("STEP_OK"), **kw)

    def error(
        self, index: int, kind: str, code: str, message: str | None = None, **kw: Any
    ) -> StepResult:
        latex = kw.pop("latex", None)
        result = self.step(index, kind, StepStatus.ERROR, message, latex=latex, code=code, **kw)
        return result

    def answer(
        self,
        status: VerdictStatus,
        message: str | None = None,
        *,
        latex: str | None = None,
        code: str | None = None,
        **params: object,
    ) -> AnswerResult:
        if message is None:
            message = hints.message(code, **params) if code else ""
        self.answer_result = AnswerResult(status=status, message=message, latex=latex, code=code)
        return self.answer_result

    def hint(
        self, code: str, *, step: int | None = None, message: str | None = None, **params: object
    ) -> None:
        text = message if message is not None else hints.message(code, **params)
        if any(h.code == code and h.message == text for h in self.hints):
            return  # same advice already given (e.g. for a step and again for the answer)
        self.hints.append(Feedback(code=code, message=text, step=step))

    def set_status(self, status: VerdictStatus) -> None:
        self.status_override = status

    # -- queries
    @property
    def first_error(self) -> int | None:
        for s in self.steps:
            if s.status is StepStatus.ERROR:
                return s.index
        return None

    # -- result
    def build(self) -> Verdict:
        status = self.status_override or self._combine()
        steps = sorted(self.steps, key=lambda s: s.index)
        return Verdict(
            problem_id=self.problem.id,
            status=status,
            score=SCORES.get(status, 0.0),
            steps=steps,
            answer=self.answer_result,
            hints=self.hints,
        )

    def _combine(self) -> VerdictStatus:
        first_error = self.first_error
        answer = self.answer_result
        if answer is None:
            if not self.steps:
                self.hint("EMPTY_SUBMISSION")
                return VerdictStatus.INCORRECT
            if first_error is not None:
                return VerdictStatus.INCORRECT
            self.hint("NO_ANSWER")
            return VerdictStatus.PARTIAL
        if answer.status is VerdictStatus.CORRECT and first_error is not None:
            self.hint("STEP_ERRORS", step=first_error, step_number=first_error + 1)
            return VerdictStatus.PARTIAL
        return answer.status


# --------------------------------------------------------------------------- handlers

Detector = Callable[[sp.Expr], "tuple[str, dict[str, object]] | None"]


class TopicHandler:
    """Base class for one problem kind. Subclasses set ``kind`` and ``Params``."""

    kind: ClassVar[str]
    Params: ClassVar[type[BaseModel]]
    step_kinds: ClassVar[frozenset[str]] = frozenset({"expr"})
    syntax_help: ClassVar[str] = ""
    engine_module: ClassVar[str] = ""  # "<course>.<module>", set by @register

    # -- lifecycle
    def params(self, problem: Problem) -> Any:
        try:
            return self.Params.model_validate(problem.data)
        except ValidationError as exc:
            raise ContentError(f"{problem.id}: bad data for kind {self.kind!r}: {exc}") from exc

    def validate(self, problem: Problem, params: Any) -> None:
        """Raise :class:`ContentError` if the answer key or data can't be used."""

    def check(
        self, problem: Problem, params: Any, submission: Submission, vb: VerdictBuilder
    ) -> None:
        raise NotImplementedError

    def verify_key(self, problem: Problem, params: Any) -> bool | None:
        """Independently re-derive the answer key with SymPy. ``None`` = not supported."""
        return None

    def has_answer(self, problem: Problem, params: Any) -> bool:
        """Whether the student enters a final answer (``False``: the steps are the work)."""
        return True

    # -- shared helpers
    @staticmethod
    def parse_step(
        vb: VerdictBuilder, index: int, step: Step, parse: Callable[[str], Any]
    ) -> Any | None:
        """Parse a step; on failure record an error step and return ``None``."""
        try:
            return parse(step.content)
        except MathInputError as exc:
            vb.step(index, step.kind, StepStatus.ERROR, exc.message, code=exc.code)
            return None

    @staticmethod
    def match_mistake(
        problem: Problem,
        student: Any,
        parse: Callable[[str], Any],
        same: Callable[[Any, Any], bool | None],
    ) -> Mistake | None:
        for mistake in problem.mistakes:
            try:
                candidate = parse(mistake.answer)
            except MathInputError:
                continue
            if same(student, candidate):
                return mistake
        return None

    def diagnose_expression(
        self,
        vb: VerdictBuilder,
        problem: Problem,
        ctx: MathContext,
        student: sp.Expr,
        key: sp.Expr,
        *,
        detectors: Sequence[Detector] = (),
        step: int | None = None,
    ) -> None:
        """Explain a wrong expression: authored mistakes, then kind detectors, then generic."""
        mistake = self.match_mistake(
            problem, student, ctx.parse, lambda a, b: equivalent(a, b, ctx)
        )
        if mistake is not None:
            vb.hint("KNOWN_MISTAKE", step=step, hint=mistake.hint)
            return
        for detect in detectors:
            found = detect(student)
            if found is not None:
                code, params = found
                vb.hint(code, step=step, **params)
                return
        if contains_float(student) and approximately_equal(student, key, ctx):
            vb.hint("INEXACT", step=step)
            return
        rel = relation(student, key, ctx)
        if rel is None:
            return
        name, value = rel
        if name == "negated":
            vb.hint("SIGN_ERROR", step=step)
        elif name == "scaled":
            vb.hint("CONSTANT_FACTOR", step=step, factor=f"${to_latex(value)}$")
        elif name == "shifted":
            vb.hint("ADDITIVE_CONSTANT", step=step, shift=f"${to_latex(value)}$")

    def grade_expression(
        self,
        vb: VerdictBuilder,
        problem: Problem,
        ctx: MathContext,
        text: str | None,
        key: sp.Expr,
        *,
        require_exact: bool = False,
        strip: bool = True,
        detectors: Sequence[Detector] = (),
        equal: Callable[[sp.Expr, sp.Expr], bool | None] | None = None,
    ) -> sp.Expr | None:
        """Grade an expression answer against ``key`` and record the answer result."""
        if text is None or not text.strip():
            return None
        try:
            student = ctx.parse(strip_label(text) if strip else text)
        except MathInputError as exc:
            vb.answer(VerdictStatus.INVALID, exc.message, code=exc.code)
            return None
        latex = to_latex(student)
        same = (equal or (lambda a, b: equivalent(a, b, ctx)))(student, key)
        if same:
            if require_exact and contains_float(student) and not contains_float(key):
                vb.answer(VerdictStatus.PARTIAL, latex=latex, code="INEXACT")
                vb.hint("INEXACT")
            else:
                vb.answer(VerdictStatus.CORRECT, latex=latex, code="CORRECT")
            return student
        if same is None:
            vb.answer(VerdictStatus.INVALID, latex=latex, code="UNVERIFIED")
            return student
        if contains_float(student) and approximately_equal(student, key, ctx):
            vb.answer(VerdictStatus.PARTIAL, latex=latex, code="INEXACT")
            vb.hint("INEXACT")
            return student
        vb.answer(VerdictStatus.INCORRECT, latex=latex, code="WRONG")
        self.diagnose_expression(vb, problem, ctx, student, key, detectors=detectors)
        return student

    def check_steps_against(
        self,
        vb: VerdictBuilder,
        steps: Sequence[Step],
        ctx: MathContext,
        target: sp.Expr,
        *,
        strip: bool = True,
        problem: Problem | None = None,
        detectors: Sequence[Detector] = (),
        indices: Sequence[int] | None = None,
        target_name: str | None = None,
    ) -> list[sp.Expr | None]:
        """Every step must equal ``target`` (e.g. successive rewrites of f′(x)).

        ``target_name`` (like "f′(x)") makes the error message say what the step should equal.
        """
        parsed: list[sp.Expr | None] = []
        for pos, step in enumerate(steps):
            index = indices[pos] if indices is not None else pos
            expr = self.parse_step(
                vb, index, step, lambda t: ctx.parse(strip_label(t) if strip else t)
            )
            parsed.append(expr)
            if expr is None:
                continue
            latex = to_latex(expr)
            same = equivalent(expr, target, ctx)
            if same:
                vb.ok(index, step.kind, latex=latex)
            elif same is None:
                vb.step(index, step.kind, StepStatus.UNCHECKED, latex=latex, code="UNVERIFIED_STEP")
            else:
                message = f"This step isn't equal to {target_name}." if target_name else None
                vb.error(index, step.kind, "STEP_NOT_EQUAL_TO_TARGET", message, latex=latex)
                if problem is not None and vb.first_error == index:
                    self.diagnose_expression(
                        vb, problem, ctx, expr, target, detectors=detectors, step=index
                    )
        return parsed


_HANDLERS: dict[str, TopicHandler] = {}
_LOADED = False


def register[H: type[TopicHandler]](cls: H) -> H:
    """Class decorator: register a handler for ``cls.kind``."""
    kind = getattr(cls, "kind", None)
    if not kind:
        raise TypeError(f"{cls.__name__} must define 'kind'")
    module = cls.__module__
    prefix = "prooflab.engine.topics."
    if module.startswith(prefix):
        cls.engine_module = module[len(prefix) :]
    existing = _HANDLERS.get(kind)
    if existing is not None and type(existing).__qualname__ != cls.__qualname__:
        raise ValueError(f"problem kind {kind!r} is registered twice")
    _HANDLERS[kind] = cls()
    return cls


def load_topics() -> None:
    global _LOADED
    if _LOADED:
        return
    for mod in ENGINE_MODULES:
        importlib.import_module(f"prooflab.engine.topics.{mod}")
    _LOADED = True


def handlers() -> dict[str, TopicHandler]:
    load_topics()
    return dict(_HANDLERS)


def get_handler(kind: str) -> TopicHandler:
    load_topics()
    try:
        return _HANDLERS[kind]
    except KeyError:
        raise ContentError(f"unknown problem kind {kind!r}") from None


# --------------------------------------------------------------------------- checking


def check(problem: Problem, submission: Submission, *, hints_revealed: int = 0) -> Verdict:
    """Check a submission in-process."""
    handler = get_handler(problem.kind)
    vb = VerdictBuilder(problem)
    bad = [(i, s) for i, s in enumerate(submission.steps) if s.kind not in handler.step_kinds]
    if bad:
        for i, s in bad:
            vb.step(
                i,
                s.kind,
                StepStatus.ERROR,
                code="UNKNOWN_STEP_KIND",
                step_number=i + 1,
                step_kind=s.kind,
            )
            vb.hint("UNKNOWN_STEP_KIND", step=i, step_number=i + 1, step_kind=s.kind)
        vb.set_status(VerdictStatus.INVALID)
        return vb.build()
    try:
        params = handler.params(problem)
        handler.check(problem, params, submission, vb)
    except MathInputError as exc:
        vb.set_status(VerdictStatus.INVALID)
        vb.hint(exc.code if hints.is_registered(exc.code) else "PARSE_ERROR", message=exc.message)
    except Exception:  # noqa: BLE001 — a bug in a handler must not take the API down
        log.exception("engine error checking %s", problem.id)
        vb.set_status(VerdictStatus.INVALID)
        vb.hint("ENGINE_ERROR")
    verdict = vb.build()
    if verdict.status is not VerdictStatus.CORRECT and 0 <= hints_revealed < len(problem.hints):
        verdict.hints.append(
            Feedback(
                code="AUTHORED_HINT",
                message=hints.message(
                    "AUTHORED_HINT", level=hints_revealed + 1, hint=problem.hints[hints_revealed]
                ),
            )
        )
    return verdict


def failure_verdict(problem: Problem, code: str) -> Verdict:
    return Verdict(
        problem_id=problem.id,
        status=VerdictStatus.INVALID,
        score=0.0,
        hints=[Feedback(code=code, message=hints.message(code))],
    )


# --------------------------------------------------------------------------- isolation

_MP_CONTEXT: Any = None
_MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024


def _mp_context() -> Any:
    global _MP_CONTEXT
    if _MP_CONTEXT is None:
        if "forkserver" in mp.get_all_start_methods():
            ctx = mp.get_context("forkserver")
            modules = [f"prooflab.engine.topics.{m}" for m in ENGINE_MODULES]
            ctx.set_forkserver_preload(["prooflab.engine.checker", *modules])
        else:  # pragma: no cover — Windows
            ctx = mp.get_context("spawn")
        _MP_CONTEXT = ctx
    return _MP_CONTEXT


def _limit_memory() -> None:
    if sys.platform != "linux":
        return
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (_MEMORY_LIMIT_BYTES, _MEMORY_LIMIT_BYTES))
    except (ImportError, ValueError, OSError):  # pragma: no cover
        pass


_WORKER_MAX_TASKS = 200


def _worker_loop(conn: Any) -> None:
    """A long-lived check worker: receive jobs, send verdicts, until the pipe closes."""
    _limit_memory()
    while True:
        try:
            problem_json, submission_json, hints_revealed = conn.recv()
        except (EOFError, OSError):
            return
        try:
            problem = Problem.model_validate_json(problem_json)
            submission = Submission.model_validate_json(submission_json)
            verdict = check(problem, submission, hints_revealed=hints_revealed)
            conn.send(("ok", verdict.model_dump_json()))
        except BaseException as exc:  # noqa: BLE001
            try:
                conn.send(("error", repr(exc)))
            except Exception:  # noqa: BLE001
                return


class _Worker:
    def __init__(self, ctx: Any) -> None:
        self.conn, child = ctx.Pipe()
        self.proc = ctx.Process(target=_worker_loop, args=(child,), daemon=True)
        self.proc.start()
        child.close()
        self.tasks = 0

    def kill(self) -> None:
        try:
            self.conn.close()
        finally:
            if self.proc.is_alive():
                self.proc.kill()
            self.proc.join(timeout=2)


class WorkerPool:
    """Reusable check workers. A worker that times out or fails is killed and replaced.

    Starting a process per check costs ~200 ms (the child re-imports the parent's
    ``__main__``); reusing workers makes isolation nearly free while keeping a hard timeout.
    Concurrency is bounded by the caller (the API's check semaphore).
    """

    def __init__(self) -> None:
        self._idle: queue.LifoQueue[_Worker] = queue.LifoQueue()

    def _take(self) -> _Worker:
        while True:
            try:
                worker = self._idle.get_nowait()
            except queue.Empty:
                return _Worker(_mp_context())
            if worker.proc.is_alive():
                return worker
            worker.kill()

    def run(
        self, problem: Problem, submission: Submission, hints_revealed: int, timeout: float
    ) -> Verdict:
        job = (problem.model_dump_json(), submission.model_dump_json(), hints_revealed)
        try:
            worker = self._take()
            try:
                worker.conn.send(job)
            except (BrokenPipeError, OSError):
                worker.kill()
                worker = _Worker(_mp_context())
                worker.conn.send(job)
        except Exception:  # noqa: BLE001 — e.g. the worker process couldn't be started
            log.exception("could not start a check worker for %s", problem.id)
            return failure_verdict(problem, "ENGINE_ERROR")
        if not worker.conn.poll(timeout):
            log.warning("check of %s timed out after %.1fs", problem.id, timeout)
            worker.kill()
            return failure_verdict(problem, "TIMEOUT")
        try:
            status, payload = worker.conn.recv()
        except (EOFError, OSError):
            log.error("check worker for %s exited without a result", problem.id)
            worker.kill()
            return failure_verdict(problem, "ENGINE_ERROR")
        if status != "ok":
            log.error("check worker for %s failed: %s", problem.id, payload)
            worker.kill()
            return failure_verdict(problem, "ENGINE_ERROR")
        worker.tasks += 1
        if worker.tasks >= _WORKER_MAX_TASKS:
            worker.kill()  # recycle to keep memory (SymPy caches) bounded
        else:
            self._idle.put(worker)
        return Verdict.model_validate_json(payload)


_POOL: WorkerPool | None = None
_POOL_LOCK = threading.Lock()


def _pool() -> WorkerPool:
    global _POOL
    with _POOL_LOCK:
        if _POOL is None:
            _POOL = WorkerPool()
        return _POOL


def check_isolated(
    problem: Problem, submission: Submission, *, hints_revealed: int = 0, timeout: float = 10.0
) -> Verdict:
    """Run :func:`check` in a worker process; kill the worker after ``timeout`` seconds."""
    return _pool().run(problem, submission, hints_revealed, timeout)
