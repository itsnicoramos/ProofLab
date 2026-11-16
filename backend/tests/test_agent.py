"""prooflab-agent (SPEC §23): the bounded loop, error trapping, approvals, the guard and the
event log, all driven by a scripted model. No network, no API key, no real memory."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from prooflab.agent.controls import Approver, EventLog, Risk
from prooflab.agent.loop import MAX_ERRORS_IN_A_ROW, Agent
from prooflab.agent.tools import TOOLS, run_cli
from prooflab.tutor_guard import Finding

EX = "proofs.direct.ch4-ex01"
PROOF = "secret-proof-text: let x = 2a so x^2 = 4a^2"


def text(t: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=t)


def use(name: str, args: dict[str, Any], i: int = 1) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=f"call-{i}", name=name, input=args)


def reply(*blocks: SimpleNamespace, stop: str | None = None) -> SimpleNamespace:
    calls = any(b.type == "tool_use" for b in blocks)
    return SimpleNamespace(
        stop_reason=stop or ("tool_use" if calls else "end_turn"), content=list(blocks)
    )


class Scripted:
    """A model that plays back replies in order, then repeats the last one forever."""

    name = "scripted"

    def __init__(self, *replies: SimpleNamespace) -> None:
        self.replies, self.calls = list(replies), 0
        self.seen: list[list[dict[str, Any]]] = []

    def complete(self, system: str, messages: list[dict[str, Any]], tools: list[dict]) -> Any:
        self.seen.append(list(messages))
        self.calls += 1
        return self.replies[min(self.calls, len(self.replies)) - 1]


def make(
    model: Scripted,
    *,
    ask: Callable[[str], str] | None = None,
    run: Callable[..., tuple[int, str]] | None = None,
    guard: Callable[..., Finding | None] | None = None,
    max_steps: int = 12,
) -> tuple[Agent, io.StringIO, list[list[str]]]:
    ran: list[list[str]] = []

    def fake_run(argv: list[str], stdin: str | None) -> tuple[int, str]:
        ran.append(argv)
        return 0, '{"ok": true}'

    log = io.StringIO()
    agent = Agent(
        model,
        Approver(ask),
        EventLog(log, "test"),
        max_steps=max_steps,
        run=run or fake_run,
        guard=guard or (lambda *a: None),
    )
    return agent, log, ran


def events(log: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log.getvalue().splitlines()]


def last_results(model: Scripted) -> list[dict[str, Any]]:
    return model.seen[-1][-1]["content"]


# ---------------------------------------------------------------------- the loop


def test_a_model_that_never_stops_ends_at_the_step_limit() -> None:
    model = Scripted(reply(use("list_chapters", {})))
    agent, log, ran = make(model, max_steps=5)
    outcome = agent.turn("teach me")
    assert (outcome.stop_reason, outcome.steps, model.calls, len(ran)) == ("step_limit", 5, 5, 5)
    assert events(log)[-1]["stop_reason"] == "step_limit"


def test_a_plain_answer_ends_the_turn_and_keeps_the_conversation() -> None:
    model = Scripted(reply(use("list_chapters", {})), reply(text("Chapter 4 is direct proof.")))
    agent, _, ran = make(model)
    outcome = agent.turn("what is there?")
    assert (outcome.stop_reason, outcome.steps) == ("end_turn", 2)
    assert outcome.text == "Chapter 4 is direct proof."
    assert ran == [["chapters"]]
    assert [m["role"] for m in agent.messages] == ["user", "assistant", "user", "assistant"]


# ---------------------------------------------------------------------- error trapping


def test_a_tool_that_raises_goes_back_to_the_model_as_an_error() -> None:
    def broken(argv: list[str], stdin: str | None) -> tuple[int, str]:
        raise OSError("disk on fire")

    model = Scripted(reply(use("list_chapters", {})), reply(text("Let me try something else.")))
    agent, log, _ = make(model, run=broken)
    outcome = agent.turn("go")
    assert outcome.stop_reason == "end_turn"
    [result] = last_results(model)
    assert result["is_error"] and "ToolError: OSError: disk on fire" in result["content"]
    assert any(e["event"] == "tool_error" and e["error_kind"] == "OSError" for e in events(log))


def test_bad_arguments_name_the_field_and_never_run() -> None:
    model = Scripted(reply(use("read_lesson", {"chapter": 400})), reply(text("ok")))
    agent, _, ran = make(model)
    agent.turn("lesson please")
    [result] = last_results(model)
    assert result["is_error"] and "chapter" in result["content"] and ran == []


def test_an_unknown_tool_lists_the_real_ones() -> None:
    model = Scripted(reply(use("rm_rf", {})), reply(text("ok")))
    agent, _, _ = make(model)
    agent.turn("hi")
    [result] = last_results(model)
    assert result["is_error"] and "show_problem" in result["content"]


def test_repeated_failures_stop_the_turn() -> None:
    model = Scripted(reply(use("read_lesson", {"chapter": 0})))
    agent, _, _ = make(model)
    outcome = agent.turn("go")
    assert (outcome.stop_reason, outcome.steps) == ("too_many_errors", MAX_ERRORS_IN_A_ROW)


def test_ctrl_c_is_not_swallowed() -> None:
    def interrupted(argv: list[str], stdin: str | None) -> tuple[int, str]:
        raise KeyboardInterrupt

    agent, _, _ = make(Scripted(reply(use("list_chapters", {}))), run=interrupted)
    with pytest.raises(KeyboardInterrupt):
        agent.turn("go")


def test_a_failed_model_call_ends_the_turn_and_forgets_the_message() -> None:
    class Down(Scripted):
        def complete(self, *a: Any) -> Any:
            raise ConnectionError("offline")

    agent, _, _ = make(Down())
    outcome = agent.turn("hello")
    assert outcome.stop_reason == "model_error" and agent.messages == []


def test_a_cut_off_reply_still_answers_every_tool_call() -> None:
    model = Scripted(reply(use("list_chapters", {}), stop="max_tokens"))
    agent, _, ran = make(model)
    outcome = agent.turn("go")
    assert outcome.stop_reason == "max_tokens" and ran == []
    assert agent.messages[-1]["content"][0]["tool_use_id"] == "call-1"


# ---------------------------------------------------------------------- controls


NOTE = {"kind": "struggle", "text": "mixes up converse and contrapositive"}


@pytest.mark.parametrize(
    ("answer", "runs"), [("y", True), ("yes", True), ("n", False), ("", False)]
)
def test_a_write_asks_y_or_n(answer: str, runs: bool) -> None:
    model = Scripted(reply(use("remember_note", NOTE)), reply(text("ok")))
    prompts: list[str] = []

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return answer

    agent, log, ran = make(model, ask=ask)
    agent.turn("remember that")
    assert "[y/N]" in prompts[0] and "memory note add" in prompts[0]
    assert bool(ran) is runs
    assert any(e["event"] == ("human_approved" if runs else "human_denied") for e in events(log))


@pytest.mark.parametrize(("answer", "runs"), [("y", False), ("yes", True), ("YES ", True)])
def test_a_solution_needs_a_typed_yes(answer: str, runs: bool) -> None:
    model = Scripted(reply(use("show_solution", {"problem_id": EX})), reply(text("ok")))
    agent, _, ran = make(model, ask=lambda p: answer)
    agent.turn("I give up")
    assert bool(ran) is runs


def test_with_no_terminal_only_reads_run() -> None:
    approver = Approver(None)
    assert approver.approve("x", Risk.READ)
    assert not approver.approve("x", Risk.WRITE)
    assert not approver.approve("x", Risk.DESTRUCTIVE)


def test_a_closed_input_is_a_no() -> None:
    def closed(prompt: str) -> str:
        raise EOFError

    assert not Approver(closed).approve("x", Risk.WRITE)


def test_a_guard_deny_is_final_even_with_a_yes() -> None:
    deny = Finding("stay-local", "deny", "no")
    asked: list[str] = []

    def ask(prompt: str) -> str:
        asked.append(prompt)
        return "yes"

    model = Scripted(reply(use("remember_note", NOTE)), reply(text("ok")))
    agent, log, ran = make(model, ask=ask, guard=lambda *a: deny)
    agent.turn("go")
    assert ran == [] and asked == []
    assert "Blocked by the guard (stay-local)" in last_results(model)[0]["content"]
    assert any(e["event"] == "guard_denied" for e in events(log))


def test_a_guard_ask_raises_a_read_to_a_typed_yes() -> None:
    ask_first = Finding("confirm-destructive", "ask", "sure?")
    model = Scripted(reply(use("list_chapters", {})), reply(text("ok")))
    agent, _, ran = make(model, ask=lambda p: "y", guard=lambda *a: ask_first)
    agent.turn("go")
    assert ran == []


def test_the_real_guard_lets_every_tool_through() -> None:
    from prooflab.agent.loop import REPO
    from prooflab.tutor_guard import judge

    samples = {
        "list_chapters": {},
        "read_lesson": {"chapter": 4},
        "list_problems": {"chapter": 4, "difficulty": 1},
        "show_problem": {"problem_id": EX},
        "get_hint": {"problem_id": EX, "n": 1},
        "check_work": {"problem_id": EX, "steps": [{"kind": "let", "content": "x"}]},
        "show_memory": {},
        "remember_note": NOTE,
        "show_solution": {"problem_id": EX},
    }
    assert set(samples) == set(TOOLS)
    for name, args in samples.items():
        tool = TOOLS[name]
        command = tool.command(tool.params.model_validate(args))
        assert judge("Bash", {"command": command}, str(REPO), str(REPO)) is None, name


# ---------------------------------------------------------------------- the event log


def test_every_log_line_is_json_and_holds_no_proof_text() -> None:
    work = {"problem_id": EX, "steps": [{"kind": "note", "content": PROOF}]}
    model = Scripted(
        reply(use("check_work", work)), reply(use("remember_note", NOTE, i=2)), reply(text("done"))
    )
    agent, log, _ = make(model, ask=lambda p: "y")
    agent.turn(PROOF)
    rows = events(log)
    assert {"llm_call", "tool_requested", "tool_ok", "human_approved"} <= {r["event"] for r in rows}
    assert all(r["run_id"] == "test" for r in rows)
    assert "secret-proof-text" not in log.getvalue() and "contrapositive" not in log.getvalue()


def test_learner_text_goes_on_stdin_not_the_command_line() -> None:
    work = {"problem_id": EX, "steps": [{"kind": "note", "content": PROOF}]}
    tool = TOOLS["check_work"]
    args = tool.params.model_validate(work)
    assert PROOF not in tool.command(args) and PROOF in (tool.stdin(args) or "")


# ---------------------------------------------------------------------- the real CLI


def test_tool_schemas_are_objects_the_api_accepts() -> None:
    for tool in TOOLS.values():
        schema = tool.schema()
        assert schema["input_schema"]["type"] == "object" and schema["description"]


def test_a_tool_runs_the_real_cli() -> None:
    code, out = run_cli(["chapters"], None)
    assert code == 0 and "chapters" in json.loads(out)


def test_a_cli_error_comes_back_as_its_json() -> None:
    code, out = run_cli(["show", "proofs.nope"], None)
    assert code == 1 and "error" in json.loads(out)
