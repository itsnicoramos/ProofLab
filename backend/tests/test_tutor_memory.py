"""The tutor memory in Postgres (SPEC §20).

These run only when PROOFLAB_TUTOR_TEST_DATABASE_URL points at a Postgres you don't mind
tests writing to, for example the compose service:

    PROOFLAB_TUTOR_TEST_DATABASE_URL=postgresql://prooflab:prooflab-local@127.0.0.1:5433/prooflab_tutor

Each test gets its own throwaway schema (dropped afterwards), so a learner's real memory in
the "tutor" schema is never touched.
"""

from __future__ import annotations

import io
import json
import os
import sys
import uuid
from datetime import date

import pytest

URL = os.environ.get("PROOFLAB_TUTOR_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="PROOFLAB_TUTOR_TEST_DATABASE_URL isn't set")

psycopg = pytest.importorskip("psycopg") if URL else None

from prooflab import tutor  # noqa: E402
from prooflab.tutor_memory.db import connect, migrations  # noqa: E402
from prooflab.tutor_memory.models import NoteIn, PlanIn, QuizIn, ReviewIn  # noqa: E402


@pytest.fixture
def schema():
    name = f"test_{uuid.uuid4().hex[:10]}"
    yield name
    import psycopg.sql

    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute(
            psycopg.sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(psycopg.sql.Identifier(name))
        )


@pytest.fixture
def memory(schema):
    from prooflab.tutor_memory.queries import Memory

    with connect(URL, schema) as conn:
        yield Memory(conn, "tester")


@pytest.fixture
def cli(schema, monkeypatch, capsys):
    """Run the CLI against the throwaway schema."""
    monkeypatch.setenv("PROOFLAB_TUTOR_DATABASE_URL", URL)
    monkeypatch.setenv("PROOFLAB_TUTOR_DB_SCHEMA", schema)
    monkeypatch.setenv("PROOFLAB_TUTOR_LEARNER", "cli-tester")

    def run(*argv: str, stdin: str | None = None):
        old = sys.stdin
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            code = tutor.main(list(argv))
        finally:
            sys.stdin = old
        return code, json.loads(capsys.readouterr().out)

    return run


def test_init_twice_is_a_no_op(schema):
    with connect(URL, schema) as conn:
        first = conn.execute("SELECT max(version) AS v FROM schema_version").fetchone()["v"]
    with connect(URL, schema) as conn:
        rows = conn.execute("SELECT count(*) AS n FROM schema_version").fetchone()["n"]
    assert first == migrations()[-1][0] and rows == len(migrations())


def test_plan_set_update_and_archive(memory):
    out = memory.set_plan(
        PlanIn(
            mission="Pass MATH 123",
            pace="~5 h/week",
            exam_date=date(2026, 12, 10),
            entry_chapter=4,
            placement={"score": 6, "total": 10},
            chapters={1: "done", 4: "do"},
        )
    )
    assert out["plan"]["entry_chapter"] == 4 and out["chapters"] == {1: "done", 4: "do"}
    memory.set_plan(PlanIn(pace="~2 h/week"))  # a partial update keeps the rest
    plan = memory.plan()
    assert plan["mission"] == "Pass MATH 123" and plan["pace"] == "~2 h/week"
    archived = memory.archive_plan()
    assert archived["chapters_at_archive"] == {"1": "done", "4": "do"}
    assert memory.plan() is None and memory.chapters() == {}
    count = memory.conn.execute("SELECT count(*) AS n FROM plans").fetchone()["n"]
    assert count == 1  # archived, not deleted


def test_a_new_plan_needs_a_mission(memory):
    from prooflab.tutor_memory.queries import MemoryRefused

    with pytest.raises(MemoryRefused):
        memory.set_plan(PlanIn(pace="fast"))


def test_sessions_attempts_and_show(memory):
    sid = memory.start_session("practice", 4)["session_id"]
    wrong = memory.record_attempt(
        problem_id="proofs.direct.ch4-ex01",
        chapter=4,
        status="incorrect",
        score=0.0,
        hint_codes=["NOT_EQUIVALENT"],
        hints_shown=0,
        steps={"steps": [{"kind": "expr", "content": "x^2"}], "answer": None},
        session_id=sid,
    )
    right = memory.record_attempt(
        problem_id="proofs.direct.ch4-ex01",
        chapter=4,
        status="correct",
        score=1.0,
        hint_codes=[],
        hints_shown=1,
        steps={"steps": [], "answer": None},
        session_id=sid,
    )
    assert wrong["first_try"] is True and right["first_try"] is False
    memory.end_session(sid, "Got it after one hint.")
    shown = memory.show()
    assert shown["stats"] == {"attempts": 2, "problems_correct": 1, "first_try_correct": 0}
    assert shown["recent_sessions"][0]["summary"] == "Got it after one hint."
    assert len(shown["chapters"]) == 14


def test_format_slips_never_take_away_first_try(memory):
    attempt = {
        "problem_id": "proofs.direct.ch4-ex02",
        "chapter": 4,
        "score": 0.0,
        "hint_codes": [],
        "hints_shown": 0,
        "steps": {"steps": []},
    }
    slip = memory.record_attempt(**attempt, status="incorrect", counted=False)
    assert slip == {**slip, "first_try": False, "counted": False}
    real = memory.record_attempt(**{**attempt, "score": 1.0}, status="correct")
    assert real["first_try"] is True and real["counted"] is True
    stats = memory.show()["stats"]
    assert stats == {"attempts": 1, "problems_correct": 1, "first_try_correct": 1}


def test_quiz_scores_come_from_recorded_answers(memory):
    quiz = memory.start_quiz(QuizIn(kind="chapter", chapters=[6], seed=3, total=3))["quiz_id"]
    assert memory.record_answer(quiz, "proofs.a.x", 3, "answer", "b", True)["counted"]
    # A second answer to the same question doesn't count.
    assert not memory.record_answer(quiz, "proofs.a.x", 3, "answer", "c", False)["counted"]
    memory.record_answer(quiz, "proofs.a.y", 4, "spot", "a", False)
    memory.record_attempt(
        problem_id="proofs.a.z",
        chapter=6,
        status="correct",
        score=1.0,
        hint_codes=[],
        hints_shown=0,
        steps={"steps": []},
        quiz_id=quiz,
    )
    result = memory.finish_quiz(quiz)
    assert (result["score"], result["total"], result["missed"]) == (2, 3, ["proofs.a.y"])
    from prooflab.tutor_memory.queries import MemoryRefused

    with pytest.raises(MemoryRefused):
        memory.record_answer(quiz, "proofs.a.w", 5, "answer", "a", True)  # already finished


def test_review_notes_and_cards(memory):
    rid = memory.add_review(ReviewIn(chapter=5, idea="Converse vs contrapositive"))["review_id"]
    memory.add_note(NoteIn(kind="preference", text="Short explanations, then an example."))
    memory.review_card("proofs.logic.def-converse", False)
    memory.review_card("proofs.sets.def-set", True)
    shown = memory.show()
    assert [r["id"] for r in shown["open_review"]] == [rid]
    assert shown["cards_due"] == ["proofs.logic.def-converse"]
    memory.clear_review(rid)
    assert memory.show()["open_review"] == []


def test_text_is_stored_as_plain_text(memory):
    nasty = 'it\'s "P => Q"; DROP TABLE notes; --'
    memory.add_note(NoteIn(kind="misconception", text=nasty, chapter=2))
    assert memory.show()["notes"][0]["text"] == nasty


def test_forget_removes_only_that_learner(schema):
    from prooflab.tutor_memory.queries import Memory, MemoryRefused

    with connect(URL, schema) as conn:
        a, b = Memory(conn, "alice"), Memory(conn, "bob")
        a.add_note(NoteIn(kind="goal", text="Finish chapter 10"))
        sid = b.start_session("learn", 1)["session_id"]
        b.add_note(NoteIn(kind="goal", text="Pass the final"))
        with pytest.raises(MemoryRefused):
            a.end_session(sid, "not mine")  # one learner can't touch another's rows
        a.forget()
        assert Memory(conn, "bob").show()["notes"][0]["text"] == "Pass the final"
        assert Memory(conn, "alice").show()["notes"] == []


def test_cli_records_the_checkers_own_verdict(cli):
    code, out = cli("memory", "init")
    assert code == 0 and out["connected"]
    code, plan = cli("memory", "plan", "set", stdin=json.dumps({"mission": "Learn proofs"}))
    assert code == 0
    _, session = cli("memory", "session", "start", "practice", "--chapter", "4")
    wrong = json.dumps(
        {"steps": [{"kind": "let", "content": "x = 2a"}, {"kind": "expr", "content": "x^2 + 1"}]}
    )
    code, out = cli(
        "check",
        "proofs.direct.ch4-ex01",
        "--record",
        "--session",
        str(session["session_id"]),
        stdin=wrong,
    )
    assert code == 0 and out["recorded"] and out["verdict"]["status"] != "correct"
    _, shown = cli("memory", "show")
    attempt = shown["recent_attempts"][0]
    assert attempt["status"] == out["verdict"]["status"]  # stored exactly what the checker said
    assert shown["chapters"][3]["title"]  # titles come from the lesson notes or topics


def test_export_renders_every_section(cli, tmp_path):
    cli("memory", "plan", "set", stdin=json.dumps({"mission": "Pass MATH 123", "entry_chapter": 2}))
    cli("memory", "note", "add", "--kind", "struggle", "--text", "Negating quantifiers")
    cli("memory", "review", "add", "--chapter", "2", "--idea", "Negations")
    path = tmp_path / "LEARNING.md"
    code, out = cli("memory", "export", "--path", str(path))
    assert code == 0
    text = path.read_text(encoding="utf-8")
    for heading in (
        "## Why I'm learning",
        "## Placement",
        "## Path",
        "## Progress log",
        "## Solved",
        "## Quizzes",
        "## Review queue",
        "## What the tutor remembers",
    ):
        assert heading in text
    assert "Pass MATH 123" in text and "Negating quantifiers" in text
