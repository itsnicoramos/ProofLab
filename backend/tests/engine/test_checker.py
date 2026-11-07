from __future__ import annotations

import pytest

from prooflab.engine import checker, hints
from prooflab.engine.checker import (
    ContentError,
    TopicHandler,
    VerdictBuilder,
    check,
    check_isolated,
    get_handler,
    handlers,
)
from prooflab.engine.models import StepStatus, Submission, VerdictStatus
from prooflab.engine.topics.calc1.derivatives import DerivativeParams


@pytest.fixture
def cubic(make_problem):
    return make_problem(
        "derivative", {"function": "x^3"}, "3x^2", hints=["first hint", "second hint"]
    )


def test_every_topic_module_registers_its_kinds():
    by_module = {h.engine_module for h in handlers().values()}
    assert {"calc1.limits", "calc1.derivatives"} <= by_module
    for handler in handlers().values():
        assert handler.syntax_help, f"{handler.kind} needs syntax_help"
        assert handler.engine_module.count(".") == 1


def test_unknown_kind():
    with pytest.raises(ContentError):
        get_handler("telepathy")


def test_unknown_step_kind_is_invalid(cubic, check_submission, verdict_codes):
    verdict = check_submission(cubic, ("lhopital", "3x^2"), answer="3x^2")
    assert verdict.status is VerdictStatus.INVALID
    assert "UNKNOWN_STEP_KIND" in verdict_codes(verdict)


def test_verdict_combination_rules(cubic, check_submission, verdict_codes):
    assert check_submission(cubic, answer="3x^2").status is VerdictStatus.CORRECT
    assert check_submission(cubic, answer="3x^").status is VerdictStatus.INVALID
    assert check_submission(cubic, answer="2x^2").status is VerdictStatus.INCORRECT
    partial = check_submission(cubic, "x^2", answer="3x^2")
    assert partial.status is VerdictStatus.PARTIAL and "STEP_ERRORS" in verdict_codes(partial)
    no_answer = check_submission(cubic, "3x^2")
    assert no_answer.status is VerdictStatus.PARTIAL and "NO_ANSWER" in verdict_codes(no_answer)
    nothing = check_submission(cubic)
    assert nothing.status is VerdictStatus.INCORRECT and "EMPTY_SUBMISSION" in verdict_codes(
        nothing
    )
    assert check_submission(cubic, "x^2").status is VerdictStatus.INCORRECT


def test_scores(cubic, check_submission):
    assert check_submission(cubic, answer="3x^2").score == 1.0
    assert check_submission(cubic, "x^2", answer="3x^2").score == 0.5
    assert check_submission(cubic, answer="x").score == 0.0


def test_authored_hints_are_revealed_in_order(cubic, check_submission):
    def authored(n):
        verdict = check_submission(cubic, answer="x^2", hints_revealed=n)
        return [h.message for h in verdict.hints if h.code == "AUTHORED_HINT"]

    assert authored(0) == ["Hint 1: first hint"]
    assert authored(1) == ["Hint 2: second hint"]
    assert authored(2) == []
    correct = check_submission(cubic, answer="3x^2")
    assert not any(h.code == "AUTHORED_HINT" for h in correct.hints)


def test_handler_crash_becomes_engine_error(monkeypatch, make_problem):
    class Boom(TopicHandler):
        kind = "boom"
        Params = DerivativeParams

        def check(self, problem, params, submission, vb):
            raise RuntimeError("bug")

    monkeypatch.setitem(checker._HANDLERS, "boom", Boom())
    verdict = check(make_problem("boom", {"function": "x"}), Submission(answer="1"))
    assert verdict.status is VerdictStatus.INVALID
    assert [h.code for h in verdict.hints][0] == "ENGINE_ERROR"


def test_verdict_builder_dedupes_hints(cubic):
    vb = VerdictBuilder(cubic)
    vb.hint("SIGN_ERROR")
    vb.hint("SIGN_ERROR")
    vb.step(0, "expr", StepStatus.OK, code="STEP_OK")
    assert [h.code for h in vb.build().hints].count("SIGN_ERROR") == 1


def test_hint_registry_rejects_conflicts():
    hints.register("TEST_ONLY_CODE", "same text")
    hints.register("TEST_ONLY_CODE", "same text")
    with pytest.raises(ValueError):
        hints.register("TEST_ONLY_CODE", "different text")
    with pytest.raises(ValueError):
        hints.register("lower_case", "x")


def test_isolated_check_matches_in_process(cubic):
    sub = Submission(answer="3x^2")
    assert check_isolated(cubic, sub, timeout=60).model_dump() == check(cubic, sub).model_dump()


def test_isolated_check_times_out(cubic):
    verdict = check_isolated(cubic, Submission(answer="3x^2"), timeout=0)
    assert verdict.status is VerdictStatus.INVALID
    assert verdict.hints[0].code == "TIMEOUT"


def test_worker_pool_reuses_and_recovers(cubic):
    from prooflab.engine.checker import WorkerPool

    pool = WorkerPool()
    ok = Submission(answer="3x^2")
    assert pool.run(cubic, ok, 0, 60).status is VerdictStatus.CORRECT
    worker = pool._idle.queue[-1]
    assert pool.run(cubic, ok, 0, 60).status is VerdictStatus.CORRECT
    assert pool._idle.queue[-1] is worker, "the idle worker should be reused"

    assert pool.run(cubic, ok, 0, 0).hints[0].code == "TIMEOUT"
    assert pool.run(cubic, ok, 0, 60).status is VerdictStatus.CORRECT

    pool._idle.queue[-1].proc.kill()
    pool._idle.queue[-1].proc.join()
    assert pool.run(cubic, ok, 0, 60).status is VerdictStatus.CORRECT
