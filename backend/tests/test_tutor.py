"""The repo tutor's CLI (SPEC §20): same answers as the API, no answer leaks, no progress DB."""

from __future__ import annotations

import io
import json
from argparse import Namespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from prooflab import tutor
from prooflab.main import Settings, create_app
from prooflab.tutor import Failure, Tutor


@pytest.fixture(scope="module")
def t() -> Tutor:
    return Tutor()


@pytest.fixture(scope="module")
def client(t: Tutor) -> TestClient:
    return TestClient(create_app(Settings(isolate=False, store=False), t.registry))


def run_cli(capsys: pytest.CaptureFixture[str], *argv: str, stdin: str | None = None) -> Any:
    if stdin is not None:
        import sys

        old, sys.stdin = sys.stdin, io.StringIO(stdin)
        try:
            code = tutor.main(list(argv))
        finally:
            sys.stdin = old
    else:
        code = tutor.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def keys_in(obj: Any) -> set[str]:
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in keys_in(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in keys_in(v)}
    return set()


def ns(**kw: Any) -> Namespace:
    return Namespace(**kw)


def test_chapters_follow_the_book(t: Tutor) -> None:
    out = tutor.cmd_chapters(t, ns())
    chapters = out["chapters"]
    assert [c["chapter"] for c in chapters] == list(range(1, 15))
    assert [c["topic"] for c in chapters][:4] == ["sets", "logic", "counting", "direct"]
    assert all(c["problems"] > 0 for c in chapters[:10])
    assert all(c["problems"] == 0 and c["checkable"] == "no" for c in chapters[10:])
    assert out["free_pdf"].startswith("https://")


def test_show_and_problems_never_reveal_answers(t: Tutor) -> None:
    for chapter in range(1, 11):
        listed = tutor.cmd_problems(t, ns(chapter=chapter, difficulty=None))
        assert listed and all(p["chapter"] == chapter for p in listed)
        for summary in listed:
            problem = t.problem(summary["id"])
            shown = tutor.cmd_show(t, ns(problem_id=problem.id))
            assert not {"solution", "examples", "answer", "mistakes"} & set(shown)
            text = json.dumps([summary, shown])
            for line in problem.solution:
                if len(line) > 25:
                    assert line not in text, (problem.id, line)
            for example in problem.examples:
                if example.submission.steps and len(example.submission.steps) > 1:
                    contents = [s.content for s in example.submission.steps]
                    assert json.dumps(contents)[1:-1] not in text


def test_quizzes_and_tests_carry_no_answer_keys(t: Tutor) -> None:
    placement = tutor.cmd_quiz(t, ns(placement=True, chapter=None, seed=3, count=5))
    assert len(placement["questions"]) == 10
    areas = [q["area"] for q in placement["questions"]]
    assert all(areas.count(a) == 2 for a in set(areas))
    chapter_quiz = tutor.cmd_quiz(t, ns(placement=False, chapter=4, seed=3, count=4))
    mock = tutor.cmd_test(
        t, ns(kind="midterm", chapters="1-5", seed=2, style="mixed", length=None, variants=False)
    )
    for out in (placement, chapter_quiz, mock):
        assert not {"correct", "correct_choice", "explanation", "solution"} & keys_in(out)


def test_check_matches_the_api(t: Tutor, client: TestClient, capsys, monkeypatch) -> None:
    """Every chapter's worked examples get the same verdict from the CLI as from POST /check."""
    for chapter in range(1, 11):
        problem = next(p for p in t.served if t.chapter_of(p) == chapter and p.examples)
        for example in problem.examples:
            body = example.submission.model_dump(mode="json")
            code, out = run_cli(capsys, "check", problem.id, stdin=json.dumps(body))
            assert code == 0
            assert out["verdict"]["status"] == example.expect.status.value
            api = client.post("/check", json={"problem_id": problem.id, **body}).json()
            assert out["verdict"] == api
            assert "recorded" not in out  # nothing is saved without --record


def test_answers_match_the_api(t: Tutor, client: TestClient) -> None:
    placement = tutor.cmd_quiz(t, ns(placement=True, chapter=None, seed=5, count=5))
    for q in placement["questions"]:
        choice = q["choice"]
        for key in ("a", "b"):
            ours = tutor.cmd_answer(
                t,
                ns(
                    problem_id=q["problem"]["id"],
                    seed=choice["seed"],
                    format=choice["format"],
                    choice=key,
                    record=False,
                    quiz=None,
                ),
            )
            api = client.post(
                "/quiz/answer",
                json={
                    "problem_id": q["problem"]["id"],
                    "seed": choice["seed"],
                    "format": choice["format"],
                    "choice": key,
                },
            ).json()
            assert {k: v for k, v in ours.items() if k != "checked_by"} == api


def test_hints_solution_and_versions(t: Tutor) -> None:
    problem = t.problem("proofs.direct.ch4-ex01")
    assert tutor.cmd_hint(t, ns(problem_id=problem.id, number=1))["hint"] == problem.hints[0]
    with pytest.raises(Failure):
        tutor.cmd_hint(t, ns(problem_id=problem.id, number=len(problem.hints) + 1))
    assert tutor.cmd_solution(t, ns(problem_id=problem.id))["solution"] == problem.solution
    version = tutor.cmd_variant(t, ns(problem_id=problem.id, seed=4))
    assert version["variant_of"] == problem.id and "not a Book of Proof" in version["label"]
    assert t.problem(version["id"]).id == version["id"]  # checkable by its id
    with pytest.raises(Failure):
        t.problem("proofs.direct.does-not-exist")


def test_cards_are_seeded(t: Tutor) -> None:
    first = tutor.cmd_cards(t, ns(chapter=4, count=3, seed=9, ids=None))
    again = tutor.cmd_cards(t, ns(chapter=4, count=3, seed=9, ids=None))
    assert first == again and len(first) == 3 and all(c["topic"] == "direct" for c in first)
    picked = tutor.cmd_cards(t, ns(chapter=None, count=3, seed=1, ids=first[0]["id"]))
    assert [c["id"] for c in picked] == [first[0]["id"]]


def test_never_opens_the_progress_database(tmp_path, monkeypatch, capsys) -> None:
    import prooflab.store

    db = tmp_path / "progress.sqlite3"
    monkeypatch.setenv("PROOFLAB_DB", str(db))

    def refuse(*_a: object, **_k: object) -> None:
        raise AssertionError("the tutor opened the progress database")

    monkeypatch.setattr(prooflab.store, "open_store", refuse)
    monkeypatch.setattr(prooflab.store.Store, "__init__", refuse)
    problem = "proofs.direct.ch4-ex01"
    assert run_cli(capsys, "chapters")[0] == 0
    assert run_cli(capsys, "show", problem)[0] == 0
    assert run_cli(capsys, "check", problem, "--record", stdin='{"steps": []}')[0] == 0
    assert run_cli(capsys, "quiz", "--chapter", "2")[0] == 0
    assert not db.exists()


def test_memory_unreachable_is_clear_and_checking_still_works(capsys) -> None:
    # conftest points the memory at a closed port.
    code, out = run_cli(capsys, "memory", "status")
    # The fix it names: start the database, or install the extra where psycopg is missing.
    assert code == 3
    assert "docker compose up -d tutor-db" in out["error"] or "--extra tutor" in out["error"]
    assert "none@" not in out["error"]  # the password is redacted
    code, out = run_cli(
        capsys, "check", "proofs.direct.ch4-ex01", "--record", stdin='{"steps": []}'
    )
    assert code == 0 and out["verdict"]["status"] and out["recorded"] is False


def test_memory_without_psycopg(monkeypatch, capsys) -> None:
    from prooflab.tutor_memory import db

    def missing() -> None:
        raise db.MemoryUnavailable(f"The tutor memory needs psycopg. {db.INSTALL_HINT}")

    monkeypatch.setattr(db, "_psycopg", missing)
    code, out = run_cli(capsys, "memory", "show")
    assert code == 3 and "uv sync --extra tutor" in out["error"]


def test_bad_work_is_explained(capsys) -> None:
    code, out = run_cli(capsys, "check", "proofs.direct.ch4-ex01", stdin='{"lines": []}')
    assert code == 1 and "expected" in out
    code, out = run_cli(capsys, "memory", "forget")
    assert code == 1 and "--confirm" in out["error"]


def test_format_slips_are_not_counted(t: Tutor) -> None:
    from prooflab.engine import hints
    from prooflab.engine.checker import check
    from prooflab.engine.models import Submission

    assert all(hints.is_registered(code) for code in tutor.FORMAT_CODES)
    problem = t.problem("proofs.direct.ch4-ex01")

    def verdict(*steps: tuple[str, str]):
        body = {"steps": [{"kind": k, "content": c} for k, c in steps]}
        return check(problem, Submission.model_validate(body))

    # An equation in an expr step: ProofLab can't read it, so it says nothing about the math.
    assert tutor.format_only(verdict(("let", "x = 2a"), ("expr", "x^2 = 2a^2")))
    # A real algebra slip counts.
    assert not tutor.format_only(verdict(("let", "x = 2a"), ("expr", "x^2"), ("expr", "2a^2")))
    worked = problem.examples[0].submission
    assert not tutor.format_only(check(problem, worked))
