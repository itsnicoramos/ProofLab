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
from pathlib import Path

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


ATTEMPT = {
    "chapter": 6,
    "status": "correct",
    "score": 1.0,
    "hint_codes": [],
    "hints_shown": 0,
    "steps": {"steps": []},
}


def test_a_finished_quiz_is_final(memory):
    from prooflab.tutor_memory.queries import MemoryRefused

    quiz = memory.start_quiz(QuizIn(kind="chapter", chapters=[6], seed=3, total=2))["quiz_id"]
    memory.record_answer(quiz, "proofs.a.x", 3, "answer", "b", False)
    first = memory.finish_quiz(quiz)
    assert (first["score"], first["missed"], first["unanswered"]) == (0, ["proofs.a.x"], 1)

    # A written check can't be attached once the quiz is over, and nothing is stored.
    with pytest.raises(MemoryRefused):
        memory.record_attempt(**ATTEMPT, problem_id="proofs.a.y", quiz_id=quiz)
    assert memory.conn.execute("SELECT count(*) AS n FROM attempts").fetchone()["n"] == 0

    # Even a row that got in some other way (before this rule) can't change the saved result.
    memory.conn.execute(
        "INSERT INTO attempts"
        " (learner_id, quiz_id, problem_id, chapter, status, score, first_try, steps)"
        " VALUES (%s, %s, 'proofs.a.y', 6, 'correct', 1, true, '{}')",
        (memory.id, quiz),
    )
    assert memory.finish_quiz(quiz) == first
    assert memory.quizzes()[0]["score"] == 0


def test_a_bound_quiz_counts_only_its_own_questions(memory):
    from prooflab.tutor_memory.models import QuizQuestion
    from prooflab.tutor_memory.queries import MemoryRefused

    questions = [
        QuizQuestion(problem_id="proofs.a.choice", format="answer", seed=7),
        QuizQuestion(problem_id="proofs.a.written", format="written"),
    ]
    quiz = memory.start_quiz(
        QuizIn(kind="quiz", chapters=[6], seed=7, total=2, questions=questions)
    )["quiz_id"]
    refused = [
        # not a question of this quiz
        lambda: memory.record_answer(quiz, "proofs.a.other", 7, "answer", "a", True),
        lambda: memory.record_attempt(**ATTEMPT, problem_id="proofs.a.other", quiz_id=quiz),
        # the same problem rebuilt with another seed or format is a different question
        lambda: memory.record_answer(quiz, "proofs.a.choice", 8, "answer", "a", True),
        lambda: memory.record_answer(quiz, "proofs.a.choice", 7, "spot", "a", True),
        # a choice question can't be settled by a written check, or the other way round
        lambda: memory.record_attempt(**ATTEMPT, problem_id="proofs.a.choice", quiz_id=quiz),
        lambda: memory.record_answer(quiz, "proofs.a.written", 7, "answer", "a", True),
    ]
    for call in refused:
        with pytest.raises(MemoryRefused):
            call()
    assert memory.record_answer(quiz, "proofs.a.choice", 7, "answer", "a", False)["counted"]
    memory.record_attempt(**ATTEMPT, problem_id="proofs.a.written", quiz_id=quiz)
    result = memory.finish_quiz(quiz)
    assert (result["score"], result["missed"], result["unanswered"]) == (1, ["proofs.a.choice"], 0)


def test_cli_binds_a_quiz_to_the_questions_it_builds(cli):
    cli("memory", "init")
    args = ("--chapters", "4", "--total", "3", "--seed", "5")
    code, started = cli("memory", "quiz", "start", "--kind", "chapter", *args)
    assert code == 0 and started["total"] == 3
    quiz_id = str(started["quiz_id"])
    _, quiz = cli("quiz", "--chapter", "4", "--count", "3", "--seed", "5")
    asked = {q["problem"]["id"] for q in quiz["questions"]}

    for q in quiz["questions"]:  # every question the learner is shown can be recorded
        if q["format"] == "choice":
            choice = q["choice"]
            flags = ("--seed", str(choice["seed"]), "--format", choice["format"], "--choice", "a")
            code, out = cli("answer", q["problem"]["id"], *flags, "--record", "--quiz", quiz_id)
        else:
            flags = ("--record", "--quiz", quiz_id)
            code, out = cli("check", q["problem"]["id"], *flags, stdin='{"steps": []}')
        assert code == 0 and out["recorded"] is True, out

    # Another exercise, however well it goes, can't be counted toward this quiz.
    _, problems = cli("problems", "--chapter", "4")
    outsider = next(p["id"] for p in problems if p["id"] not in asked)
    code, out = cli("check", outsider, "--record", "--quiz", quiz_id, stdin='{"steps": []}')
    assert code == 0 and out["recorded"] is False and "no written question" in out["memory_error"]

    code, result = cli("memory", "quiz", "finish", quiz_id)
    assert code == 0 and result["total"] == 3 and result["unanswered"] == 0
    code, again = cli("memory", "quiz", "finish", quiz_id)
    assert again == result  # asking again returns the saved result


def test_cli_takes_learner_text_on_stdin(cli):
    cli("memory", "init")
    typed = "said \"x\"; $(touch pwned) `id` 'q'"
    flags = ("--kind", "struggle", "--text", "-")
    code, _ = cli("memory", "note", "add", *flags, stdin=typed + "\n")
    assert code == 0
    _, shown = cli("memory", "show")
    assert shown["notes"][0]["text"] == typed


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


def test_export_renders_every_section(cli, tmp_path, monkeypatch):
    monkeypatch.setattr(tutor, "REPO_ROOT", tmp_path)  # never the learner's real LEARNING.md
    cli("memory", "plan", "set", stdin=json.dumps({"mission": "Pass MATH 123", "entry_chapter": 2}))
    cli("memory", "note", "add", "--kind", "struggle", "--text", "Negating quantifiers")
    cli("memory", "review", "add", "--chapter", "2", "--idea", "Negations")
    path = tmp_path / "LEARNING.md"
    code, out = cli("memory", "export")
    assert code == 0 and out["path"] == str(path)
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


# ---------------------------------------------------------------------- one memory per course


def test_each_course_has_its_own_memory(schema):
    from prooflab.tutor_memory.queries import Memory

    with connect(URL, schema) as conn:
        proofs, discrete = Memory(conn, "sam", "math123"), Memory(conn, "sam", "math223")
        assert proofs.id != discrete.id
        proofs.set_plan(PlanIn(mission="Pass MATH 123", chapters={4: "do"}))
        discrete.set_plan(PlanIn(mission="Keep up with MATH 223"))
        proofs.add_note(NoteIn(kind="struggle", text="Negating quantifiers", chapter=2))
        discrete.add_review(ReviewIn(idea="Pigeonhole with n + 1 pigeons"))  # no chapter
        discrete.start_session("coach")

        shown = discrete.show(chapters=0)
        assert (shown["course"], shown["chapters"], shown["next_chapter"]) == ("math223", [], None)
        assert shown["plan"]["mission"] == "Keep up with MATH 223" and shown["notes"] == []
        assert shown["open_review"][0]["chapter"] is None
        assert proofs.show()["notes"][0]["text"] == "Negating quantifiers"
        assert proofs.show()["open_review"] == [] and len(proofs.show()["chapters"]) == 14

        listed = {row["course"]: row for row in proofs.courses()}
        assert set(listed) == {"math123", "math223"} and all(r["has_plan"] for r in listed.values())
        assert (listed["math123"]["sessions"], listed["math223"]["sessions"]) == (0, 1)

        assert discrete.forget()["courses"] == ["math223"]  # one course, not the learner
        assert Memory(conn, "sam", "math123").plan()["mission"] == "Pass MATH 123"
        Memory(conn, "sam", "math223").add_note(NoteIn(kind="goal", text="Start again"))
        assert proofs.forget(all_courses=True)["courses"] == ["math123", "math223"]
        assert Memory(conn, "sam", "math123").plan() is None


def test_memory_from_before_courses_becomes_math123(schema, monkeypatch):
    """Upgrading a memory that predates course packs keeps every row, filed under MATH 123."""
    from prooflab.tutor_memory import db
    from prooflab.tutor_memory.queries import Memory

    every = db.migrations()
    monkeypatch.setattr(db, "migrations", lambda: [m for m in every if m[0] <= 3])
    with connect(URL, schema) as conn:  # the schema as it was at migration 003
        old = conn.execute("INSERT INTO learners (name) VALUES ('me') RETURNING id").fetchone()
        conn.execute(
            "INSERT INTO plans (learner_id, mission, entry_chapter) VALUES (%s, 'Old plan', 14)",
            (old["id"],),
        )
        conn.execute(
            "INSERT INTO review_queue (learner_id, chapter, idea) VALUES (%s, 5, 'Converse')",
            (old["id"],),
        )
    monkeypatch.undo()
    with connect(URL, schema) as conn:  # every migration now
        memory = Memory(conn, "me")
        assert (memory.id, memory.course) == (old["id"], "math123")
        assert memory.plan()["mission"] == "Old plan" and memory.plan()["entry_chapter"] == 14
        assert memory.show()["open_review"][0]["idea"] == "Converse"
        assert Memory(conn, "me", "math223").plan() is None


def test_cli_keeps_the_courses_apart(cli, tmp_path, monkeypatch):
    monkeypatch.setattr(tutor, "REPO_ROOT", tmp_path)  # never the learner's real LEARNING.md
    cli("memory", "init")
    plan = {"mission": "Pass MATH 123", "entry_chapter": 4, "chapters": {"4": "do"}}
    assert cli("memory", "plan", "set", stdin=json.dumps(plan))[0] == 0

    # The empty slot takes a plan, coach sessions, notes and missed ideas, but no chapters.
    in223 = ("--course", "math223")
    assert cli("memory", "plan", "set", *in223, stdin='{"mission": "Keep up with 223"}')[0] == 0
    code, out = cli("memory", "plan", "set", *in223, stdin='{"entry_chapter": 1}')
    assert code == 1 and "no chapters yet" in out["error"]
    code, out = cli("memory", "chapter", "1", "do", *in223)
    assert code == 1 and "no chapters yet" in out["error"]
    code, session = cli("memory", "session", "start", "coach", *in223)
    assert code == 0
    assert cli("memory", "review", "add", "--idea", "-", *in223, stdin="Stars and bars")[0] == 0
    cli("memory", "session", "end", str(session["session_id"]), "--summary", "First look", *in223)

    code, shown = cli("memory", "show", *in223)
    assert code == 0 and (shown["course"], shown["chapters"]) == ("math223", [])
    assert shown["open_review"][0]["idea"] == "Stars and bars"
    code, shown = cli("memory", "show")
    assert (shown["course"], len(shown["chapters"]), shown["open_review"]) == ("math123", 14, [])

    # Chapters are checked against the course: MATH 123 has 14, and a missed idea there
    # belongs to one of them.
    assert cli("memory", "chapter", "15", "do")[0] == 1
    code, out = cli("memory", "review", "add", "--idea", "Converse")
    assert code == 1 and "--chapter" in out["error"]

    code, listed = cli("memory", "courses")
    assert [(c["course"], c["status"]) for c in listed["courses"]] == [
        ("math123", "ready"),
        ("math223", "empty"),
    ]

    # One LEARNING.md, the selected course first, then the other one.
    code, out = cli("memory", "export")
    text = (tmp_path / "LEARNING.md").read_text(encoding="utf-8")
    first, second = text.index("# My Book of Proof path"), text.index("# My MATH 223 path")
    assert code == 0 and first < second and "Stars and bars" in text[second:]
    assert "Pass MATH 123" in text[first:second]

    code, out = cli("memory", "forget", *in223)
    assert code == 1 and "MATH 223" in out["error"]
    assert cli("memory", "forget", "--confirm", *in223)[1]["courses"] == ["math223"]
    assert cli("memory", "show")[1]["plan"]["mission"] == "Pass MATH 123"


def test_an_eval_run_seeds_and_then_drops_its_own_memory(schema, tmp_path, monkeypatch, capsys):
    """A scenario's setup lands in the eval's throwaway schema, the agent under test sees it,
    and the schema is gone afterwards. The learner's own schema is never used."""
    monkeypatch.setenv("PROOFLAB_TUTOR_DATABASE_URL", URL)
    monkeypatch.setenv("PROOFLAB_TUTOR_DB_SCHEMA", schema)  # the "learner's own" memory here
    monkeypatch.setattr(tutor, "REPO_ROOT", tmp_path)
    agent = tmp_path / "agent.py"
    agent.write_text(
        "import io, json, os, sys\n"
        "from contextlib import redirect_stdout\n"
        "from prooflab import tutor\n"
        "out = io.StringIO()\n"
        "with redirect_stdout(out):\n"
        "    tutor.main(['memory', 'show'])\n"
        "notes = [n['text'] for n in json.loads(out.getvalue())['notes']]\n"
        "text = os.environ['PROOFLAB_TUTOR_DB_SCHEMA'] + ' :: ' + ' / '.join(notes)\n"
        "message = {'content': [{'type': 'text', 'text': text}]}\n"
        "print(json.dumps({'type': 'assistant', 'session_id': 's', 'message': message}))\n",
        encoding="utf-8",
    )
    src = str(Path(tutor.__file__).resolve().parents[1])
    monkeypatch.setenv("PYTHONPATH", src)
    trace = tmp_path / "trace.jsonl"
    code = tutor.main(
        ["eval", "poisoned-note", "--agent", f"{sys.executable} {agent}", "--out", str(trace)]
    )
    report = json.loads(capsys.readouterr().out)
    lines = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    heard = lines[1]["message"]["content"][0]["text"]
    used, _, notes = heard.partition(" :: ")
    assert code == 0 and "dropped" in report["memory"]
    assert used.startswith("eval_") and used != schema and "SYSTEM OVERRIDE" in notes
    with psycopg.connect(URL, autocommit=True) as conn:
        left = conn.execute(
            "SELECT count(*) FROM information_schema.schemata WHERE schema_name = %s", (used,)
        ).fetchone()[0]
    assert left == 0
    with connect(URL, schema) as conn:  # nothing was written to the learner's own schema
        assert conn.execute("SELECT count(*) AS n FROM notes").fetchone()["n"] == 0
