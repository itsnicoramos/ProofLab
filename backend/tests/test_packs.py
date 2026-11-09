"""Course packs (SPEC §22): the tutor's tools work for any pack, not only MATH 123."""

from __future__ import annotations

import io
import json
from argparse import Namespace
from typing import Any

import pytest

from prooflab import tutor
from prooflab.packs import CoursePack, PackError, find_pack, load_packs
from prooflab.tutor import Failure, Tutor


def run_cli(capsys: pytest.CaptureFixture[str], *argv: str, stdin: str | None = None) -> Any:
    import sys

    old = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        code = tutor.main(list(argv))
    finally:
        sys.stdin = old
    return code, json.loads(capsys.readouterr().out)


def test_the_two_courses() -> None:
    packs = load_packs()
    assert list(packs) == ["math123", "math223"]
    math123, math223 = packs["math123"], packs["math223"]
    assert (math123.status, len(math123.topics), math123.track) == ("ready", 14, "proofs")
    assert sum(len(area.topics) for area in math123.placement) == 10
    # MATH 223 is an honest empty slot: no track, no invented outline.
    assert (math223.status, math223.topics, math223.book, math223.placement) == (
        "empty",
        [],
        None,
        [],
    )


@pytest.mark.parametrize(
    ("name", "pack"),
    [
        ("math123", "math123"),
        ("MATH 123", "math123"),
        ("Book of Proof", "math123"),
        ("proofs", "math123"),
        ("MATH 223", "math223"),
        ("math-223", "math223"),
        ("223", "math223"),
        ("Discrete", "math223"),
    ],
)
def test_a_course_can_be_named_the_way_people_say_it(name: str, pack: str) -> None:
    assert find_pack(name).id == pack


def test_the_default_course_and_unknown_names(monkeypatch) -> None:
    monkeypatch.delenv("PROOFLAB_TUTOR_COURSE", raising=False)
    assert find_pack().id == "math123"
    monkeypatch.setenv("PROOFLAB_TUTOR_COURSE", "MATH 223")
    assert find_pack().id == "math223"
    assert find_pack("123").id == "math123"  # a name given outright wins over the setting
    with pytest.raises(PackError, match="math123.*math223"):
        find_pack("chem101")


def test_a_bad_pack_is_refused_with_every_reason(tmp_path) -> None:
    def write(name: str, **fields: Any) -> None:
        base = {"id": name, "code": name.upper(), "title": "T", "summary": "S"}
        (tmp_path / f"{name}.json").write_text(json.dumps({**base, **fields}), encoding="utf-8")

    write("good", aliases=["shared"])
    write("wrongbook", track="proofs", book="no-such-book", book_name="X")
    write("nobook", track="proofs")
    write("badtopic", track="proofs", book="hammack-bop3", book_name="Book of Proof")
    write("emptyplaced", placement=[{"area": "Sets", "topics": ["sets"]}])
    write("dupe", aliases=["Shared"])
    write("renamed", id="other")
    bad = json.loads((tmp_path / "badtopic.json").read_text(encoding="utf-8"))
    bad["placement"] = [{"area": "Graphs", "topics": ["graphs"]}]
    (tmp_path / "badtopic.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(PackError) as caught:
        load_packs(tmp_path)
    message = str(caught.value)
    for reason in (
        "no-such-book",
        "needs its book",
        "unknown topics ['graphs']",
        "can't have placement",
        "already used by",
        "must match the file name",
    ):
        assert reason in message, reason


def test_cli_lists_courses_and_takes_the_option_anywhere(capsys) -> None:
    code, out = run_cli(capsys, "courses")
    assert code == 0 and out["selected"] == "math123"
    assert [c["course"] for c in out["courses"]] == ["math123", "math223"]
    assert [c["status"] for c in out["courses"]] == ["ready", "empty"]
    for argv in (
        ("--course", "math223", "courses"),
        ("courses", "--course", "MATH 223"),
        ("courses", "--course=223"),
    ):
        assert run_cli(capsys, *argv)[1]["selected"] == "math223"
    code, out = run_cli(capsys, "chapters", "--course", "chem101")
    assert code == 1 and "math223" in out["error"]


def test_free_text_is_never_taken_for_an_option() -> None:
    argv = ["memory", "note", "add", "--text", "--course", "--kind", "goal", "--course", "223"]
    assert tutor._pop_option(argv, "--course") == "223"
    assert argv == ["memory", "note", "add", "--text", "--course", "--kind", "goal"]


def test_math123_is_unchanged_under_its_pack(capsys) -> None:
    code, out = run_cli(capsys, "chapters")
    assert code == 0 and (out["course"], out["track"], out["status"]) == (
        "math123",
        "proofs",
        "ready",
    )
    assert len(out["chapters"]) == 14 and out["book"]["title"] == "Book of Proof"
    assert out["free_pdf"].startswith("https://")


def test_an_empty_slot_refuses_content_and_says_why(capsys) -> None:
    code, out = run_cli(capsys, "chapters", "--course", "math223")
    assert code == 0 and (out["status"], out["chapters"], out["book"]) == ("empty", [], None)
    for argv in (
        ("lesson", "1"),
        ("problems", "--chapter", "1"),
        ("show", "proofs.direct.ch4-ex01"),  # another course's exercise is not this course's
        ("cards",),
        ("quiz", "--chapter", "1"),
        ("quiz", "--placement"),
        ("test", "--chapters", "1-3"),
        ("solution", "proofs.direct.ch4-ex01"),
    ):
        code, out = run_cli(capsys, *argv, "--course", "math223")
        assert code == 1 and out["status"] == "empty" and "feedback, not a verdict" in out["error"]
    # Nothing is graded there either, so no verdict can be claimed for the course.
    work = '{"steps": []}'
    code, out = run_cli(capsys, "check", "proofs.direct.ch4-ex01", "--course", "223", stdin=work)
    assert code == 1 and "verdict" not in out


def ns(**kw: Any) -> Namespace:
    return Namespace(**kw)


def test_the_tools_work_for_a_pack_on_another_track() -> None:
    """The harness is not built around Book of Proof: any track with problems can be taught."""
    pack = CoursePack(
        id="calc1x",
        code="MATH 151",
        title="Calculus 1",
        summary="A throwaway pack for this test.",
        track="calc1",
        book="openstax-calc1",
        book_name="Calculus Volume 1",
    )
    t = Tutor(pack)
    chapters = tutor.cmd_chapters(t, ns())
    assert chapters["course"] == "calc1x" and chapters["track"] == "calc1"
    assert [c["topic"] for c in chapters["chapters"]] == ["limits", "derivatives"]
    assert all(c["problems"] > 0 and c["lesson"] is None for c in chapters["chapters"])

    listed = tutor.cmd_problems(t, ns(chapter=2, difficulty=None))
    problem = t.problem(listed[0]["id"])
    assert problem.course.value == "calc1" and listed[0]["chapter"] == 2
    worked = next(e for e in problem.examples if e.expect.status.value == "correct")
    verdict = t.run(problem, worked.submission)
    assert verdict.status.value == "correct"  # the same checker, another course

    quiz = tutor.cmd_quiz(t, ns(placement=False, chapter=2, seed=3, count=3))
    assert len(quiz["questions"]) == 3
    assert "Calculus Volume 1" in t.variant_label
    with pytest.raises(Failure, match="no placement quiz"):
        tutor.cmd_quiz(t, ns(placement=True, chapter=None, seed=3, count=3))
    with pytest.raises(Failure, match="no lesson note"):
        tutor.cmd_lesson(t, ns(chapter=1))
    with pytest.raises(Failure):  # MATH 123's exercises are not this course's
        t.problem("proofs.direct.ch4-ex01")
