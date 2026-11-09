"""prooflab-tutor: the command line the repo tutor runs (SPEC §20).

An AI tutor in the learner's own coding agent (see AGENTS.md and .claude/skills/tutor/) uses
this to read lessons and problems, to have ProofLab's deterministic checker grade the
learner's work, and to keep its memory in Postgres. It never starts the API server and never
opens the site's SQLite progress database.

Output is JSON on stdout. Exit codes: 0 done, 1 bad request, 3 the memory isn't available.
Run ``uv run prooflab-tutor --help`` from ``backend/`` for every command.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, NoReturn

from pydantic import ValidationError

from prooflab.api.routes import (
    _choice_out,
    _summary,
    answer_out,
    find_problem,
    practice_test_out,
    problem_detail,
)
from prooflab.cards import build_deck
from prooflab.content import Registry, load_registry
from prooflab.engine.checker import check_isolated
from prooflab.engine.models import Course, Problem, Submission, Verdict
from prooflab.lessons import Lesson, load_lessons
from prooflab.practice import PracticeTestError
from prooflab.quiz import build_question

COURSE = Course("proofs")  # the live course, same as COURSE_ORDER in frontend/src/lib/labels.ts
BOOK_PDF = "https://richardhammack.github.io/BookOfProof/"
CHECKED_BY = "ProofLab's checker (deterministic rules and SymPy, no AI)"
CHECK_TIMEOUT = 10.0
QUESTION_TIMEOUT = 5.0  # the same limit the API gives each quiz question
REPO_ROOT = Path(__file__).resolve().parents[3]
PLACEMENT_AREAS = (
    ("Sets", ("sets", "sets")),
    ("Logic", ("logic", "logic")),
    ("Counting", ("counting", "counting")),
    ("Direct and contrapositive proof", ("direct", "contrapositive")),
    ("Contradiction and induction", ("contradiction", "induction")),
)
VARIANT_LABEL = "A ProofLab-made version with new numbers. It is not a Book of Proof exercise."
LEARNER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")


class Failure(Exception):
    def __init__(self, message: str, code: int = 1, **extra: object) -> None:
        super().__init__(message)
        self.code = code
        self.extra = extra


def emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def fail(message: str, code: int = 1, **extra: object) -> NoReturn:
    raise Failure(message, code, **extra)


# ---------------------------------------------------------------------- content and checking


class Tutor:
    def __init__(self) -> None:
        self.registry: Registry = load_registry(courses=[COURSE.value])
        self.topics: list[str] = self.registry.topics[COURSE.value]
        self.lessons: dict[int, Lesson] = load_lessons(COURSE.value)
        self.served = [p for p in self.registry.served() if p.course is COURSE]

    def chapter_of(self, problem: Problem) -> int | None:
        return self.topics.index(problem.topic) + 1 if problem.topic in self.topics else None

    def topic_of(self, chapter: int) -> str:
        if not 1 <= chapter <= len(self.topics):
            fail(f"Chapters run from 1 to {len(self.topics)}.")
        return self.topics[chapter - 1]

    def problem(self, problem_id: str) -> Problem:
        problem = find_problem(self.registry, problem_id)
        if problem is None or problem.course is not COURSE:
            fail(
                f"No problem with id {problem_id!r}.",
                hint="List a chapter's problems with: prooflab-tutor problems --chapter N",
            )
        return problem

    def run(self, problem: Problem, submission: Submission) -> Verdict:
        return check_isolated(problem, submission, timeout=QUESTION_TIMEOUT)

    def summary(self, problem: Problem) -> dict[str, Any]:
        return {**_summary(problem).model_dump(mode="json"), "chapter": self.chapter_of(problem)}

    def chapter_title(self, n: int) -> str:
        lesson = self.lessons.get(n)
        return lesson.title if lesson else self.topics[n - 1]


def cmd_chapters(t: Tutor, _: argparse.Namespace) -> Any:
    cards = Counter(c.topic for c in t.registry.cards.get(COURSE.value, []))
    out = []
    for n, topic in enumerate(t.topics, 1):
        problems = [p for p in t.served if p.topic == topic]
        lesson = t.lessons.get(n)
        out.append(
            {
                "chapter": n,
                "topic": topic,
                "title": t.chapter_title(n),
                "lesson": lesson.repo_path if lesson else None,
                "checkable": lesson.checkable if lesson else ("partly" if problems else "no"),
                "minutes": lesson.minutes if lesson else None,
                "sections": lesson.sections if lesson else [],
                "problems": len(problems),
                "by_difficulty": dict(sorted(Counter(p.difficulty for p in problems).items())),
                "concept_cards": cards.get(topic, 0),
            }
        )
    book = t.registry.references["hammack-bop3"]
    return {
        "course": COURSE.value,
        "book": {"title": book.title, "edition": book.edition, "license": book.license},
        "free_pdf": BOOK_PDF,
        "chapters": out,
    }


def cmd_lesson(t: Tutor, a: argparse.Namespace) -> Any:
    t.topic_of(a.chapter)
    lesson = t.lessons.get(a.chapter)
    if lesson is None:
        fail(f"There's no lesson note for chapter {a.chapter} yet.")
    return {**lesson.summary(), "free_pdf": BOOK_PDF, "text": lesson.body}


def cmd_problems(t: Tutor, a: argparse.Namespace) -> Any:
    topic = t.topic_of(a.chapter)
    return [
        t.summary(p)
        for p in t.served
        if p.topic == topic and (a.difficulty is None or p.difficulty == a.difficulty)
    ]


def cmd_show(t: Tutor, a: argparse.Namespace) -> Any:
    problem = t.problem(a.problem_id)
    out = {**problem_detail(t.registry, problem).model_dump(mode="json")}
    out["chapter"] = t.chapter_of(problem)
    if out.get("variant_of"):
        out["label"] = VARIANT_LABEL
    return out


def _read_submission(a: argparse.Namespace) -> Submission:
    if a.file:
        raw = Path(a.file).read_text(encoding="utf-8")
    elif sys.stdin.isatty():
        fail(
            "Pipe the work in as JSON on stdin, or pass --file.",
            expected={"steps": [{"kind": "let", "content": "x = 2a"}], "answer": None},
        )
    else:
        raw = sys.stdin.read()
    try:
        return Submission.model_validate_json(raw)
    except ValidationError as exc:
        fail(
            "The work isn't in the expected shape.",
            expected={"steps": [{"kind": "expr", "content": "..."}], "answer": "... or null"},
            errors=json.loads(exc.json(include_url=False)),
        )


def _codes(verdict: Verdict) -> list[str]:
    codes = [s.code for s in verdict.steps if s.code]
    codes += [h.code for h in verdict.hints if h.code != "AUTHORED_HINT"]
    if verdict.answer and verdict.answer.code:
        codes.append(verdict.answer.code)
    return sorted(set(codes))


# Codes that mean ProofLab couldn't read the input, so the attempt says nothing about the math.
FORMAT_CODES = frozenset(
    {
        "PARSE_ERROR",
        "NOT_AN_EXPRESSION",
        "NOT_AN_EQUATION",
        "UNKNOWN_STEP_KIND",
        "UNKNOWN_NAME",
        "LET_FORMAT",
        "EMPTY_SUBMISSION",
        "TOO_LONG",
        "TOO_LARGE",
        "TIMEOUT",
        "ENGINE_ERROR",
        "SET_SYNTAX",
        "SET_UNKNOWN_NAME",
        "SET_NOT_A_LIST",
        "SET_NOT_COUNT",
        "SET_STEP_UNLABELED",
        "SET_MIXED_OPERATORS",
        "SETID_SYNTAX",
        "LOGIC_SYNTAX",
        "LOGIC_AMBIGUOUS",
        "LOGIC_BAD_ROW",
        "LOGIC_DECIDE_FORMAT",
        "LOGIC_VALUES_MISSING",
        "TT_STEP_FORMAT",
        "TT_BAD_COLUMN",
        "COUNTEREXAMPLE_FORMAT",
        "COUNTEREXAMPLE_MISSING_VALUE",
        "EXISTS_FORMAT",
        "IND_ASSUME_FORMAT",
    }
)
NOT_COUNTED = (
    "ProofLab couldn't read part of this input, so it isn't counted as an attempt. Fix the"
    " format (not the math) and check again."
)


def format_only(verdict: Verdict) -> bool:
    """True when the checker never got to the math: the input couldn't be read, or the first
    error is an input-format code. Such attempts are saved but don't count (SPEC §20)."""
    if verdict.status.value == "correct":
        return False
    if verdict.status.value == "invalid":
        return True
    first = next((s for s in verdict.steps if s.status.value == "error"), None)
    if first is not None:
        return first.code in FORMAT_CODES
    answer = verdict.answer
    return bool(answer and answer.code in FORMAT_CODES)


def cmd_check(t: Tutor, a: argparse.Namespace) -> Any:
    problem = t.problem(a.problem_id)
    submission = _read_submission(a)
    verdict = check_isolated(
        problem, submission, hints_revealed=a.hints_shown, timeout=CHECK_TIMEOUT
    )
    out: dict[str, Any] = {
        "checked_by": CHECKED_BY,
        "problem_id": problem.id,
        "chapter": t.chapter_of(problem),
        "verdict": verdict.model_dump(mode="json"),
    }
    if a.record:
        out.update(
            _with_memory(
                a,
                lambda m: m.record_attempt(
                    problem_id=problem.id,
                    chapter=t.chapter_of(problem),
                    status=verdict.status.value,
                    score=verdict.score,
                    hint_codes=_codes(verdict),
                    hints_shown=a.hints_shown,
                    steps=submission.model_dump(mode="json"),
                    session_id=a.session,
                    quiz_id=a.quiz,
                    counted=not format_only(verdict),
                ),
                soft=True,
            )
        )
        if out.get("counted") is False:
            out["not_counted"] = NOT_COUNTED
    return out


def cmd_hint(t: Tutor, a: argparse.Namespace) -> Any:
    problem = t.problem(a.problem_id)
    if not 1 <= a.number <= len(problem.hints):
        fail(f"This problem has {len(problem.hints)} authored hint(s).")
    return {
        "problem_id": problem.id,
        "number": a.number,
        "of": len(problem.hints),
        "hint": problem.hints[a.number - 1],
    }


def cmd_solution(t: Tutor, a: argparse.Namespace) -> Any:
    problem = t.problem(a.problem_id)
    return {
        "problem_id": problem.id,
        "answer": problem.answer or None,
        "solution": problem.solution,
        "citation": problem.reference.section,
    }


def cmd_cards(t: Tutor, a: argparse.Namespace) -> Any:
    topics = [t.topic_of(a.chapter)] if a.chapter else None
    deck = build_deck(
        t.registry.cards,
        t.served,
        {b.id: b.title for b in t.registry.references.values()},
        COURSE,
        topics=topics,
        parts=["concepts"],
        topic_order=t.topics,
    )
    if a.ids:
        wanted = [i.strip() for i in a.ids.split(",") if i.strip()]
        by_id = {c.id: c for c in deck}
        deck = [by_id[i] for i in wanted if i in by_id]
    else:
        random.Random(f"cards|{a.chapter}|{a.seed}").shuffle(deck)
        deck = deck[: a.count]
    return [c.model_dump(mode="json") for c in deck]


def _test_out(t: Tutor, kind: str, a: argparse.Namespace, topics: list[str], **kw: Any) -> Any:
    try:
        test = practice_test_out(t.registry, COURSE, kind, t.run, seed=a.seed, topics=topics, **kw)
    except PracticeTestError as exc:
        fail(str(exc))
    out = test.model_dump(mode="json")
    for q in out["questions"]:
        q["problem"]["chapter"] = t.topics.index(q["problem"]["topic"]) + 1
    return out


def cmd_quiz(t: Tutor, a: argparse.Namespace) -> Any:
    if a.placement:
        return _placement(t, a.seed)
    if not a.chapter:
        fail("Give --chapter N, or --placement.")
    topic = t.topic_of(a.chapter)
    if not any(p.topic == topic for p in t.served):
        fail(f"ProofLab has no checked problems for chapter {a.chapter} yet.")
    return _test_out(t, "quiz", a, [topic], length=a.count, style="choice")


def _placement(t: Tutor, seed: int) -> Any:
    rng = random.Random(f"placement|{seed}")
    siblings = t.served
    questions: list[dict[str, Any]] = []
    used: set[str] = set()
    offset = 0
    for area, topics in PLACEMENT_AREAS:
        for topic in topics:
            pool = [
                p for p in t.served if p.topic == topic and p.difficulty <= 2 and p.id not in used
            ]
            rng.shuffle(pool)
            for problem in pool[:15]:
                made = build_question(problem, seed * 100 + offset, t.run, siblings)
                offset += 1
                if made is not None:
                    used.add(problem.id)
                    questions.append(
                        {
                            "area": area,
                            "chapter": t.chapter_of(problem),
                            "problem": t.summary(problem),
                            "choice": _choice_out(made).model_dump(mode="json"),
                        }
                    )
                    break
    return {
        "kind": "placement",
        "seed": seed,
        "areas": [area for area, _ in PLACEMENT_AREAS],
        "questions": questions,
        "grade_with": "prooflab-tutor answer <problem id> --seed <choice.seed>"
        " --format <choice.format> --choice <key>",
    }


def cmd_answer(t: Tutor, a: argparse.Namespace) -> Any:
    problem = t.problem(a.problem_id)
    graded = answer_out(t.registry, problem, a.seed, a.format, a.choice, t.run)
    if graded is None:
        fail("That question can't be rebuilt any more. Make a new quiz.")
    out: dict[str, Any] = {"checked_by": CHECKED_BY, **graded.model_dump(mode="json")}
    if a.record:
        if a.quiz is None:
            fail("--record needs --quiz <id> (from: prooflab-tutor memory quiz start).")
        out.update(
            _with_memory(
                a,
                lambda m: m.record_answer(
                    a.quiz, problem.id, a.seed, a.format, a.choice, graded.correct
                ),
                soft=True,
            )
        )
    return out


def _chapter_list(text: str) -> list[int]:
    out: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        low, dash, high = part.partition("-")
        try:
            out += list(range(int(low), int(high) + 1)) if dash else [int(low)]
        except ValueError:
            fail(f"Bad chapter list {text!r}: use forms like 1-5 or 1,2,4.")
    return sorted(set(out))


def cmd_test(t: Tutor, a: argparse.Namespace) -> Any:
    chapters = _chapter_list(a.chapters)
    topics = [t.topic_of(n) for n in chapters]
    usable = [x for x in topics if any(p.topic == x for p in t.served)]
    if not usable:
        fail("None of those chapters has checked problems yet.")
    out = _test_out(t, a.kind, a, usable, length=a.length, style=a.style, variants=a.variants)
    skipped = [n for n, x in zip(chapters, topics, strict=True) if x not in usable]
    if skipped:
        out["skipped_chapters"] = skipped
    return out


def cmd_variant(t: Tutor, a: argparse.Namespace) -> Any:
    from prooflab.variants import make_variant

    base = t.problem(a.problem_id)
    if "prooflab-variant" in base.tags:
        fail("That's already a version. Give the original problem's id.")
    made = make_variant(base, a.seed)
    if made is None:
        fail("ProofLab can't make a new-number version of this problem.")
    out = {**problem_detail(t.registry, made).model_dump(mode="json")}
    out["chapter"] = t.chapter_of(made)
    out["label"] = VARIANT_LABEL
    return out


# ---------------------------------------------------------------------- memory


def _learner(a: argparse.Namespace) -> str:
    name = a.learner or os.environ.get("PROOFLAB_TUTOR_LEARNER") or "me"
    if not LEARNER_RE.match(name):
        fail("A learner name is lowercase letters, digits, - and _ (up to 40).")
    return name


def _with_memory(a: argparse.Namespace, action: Any, *, soft: bool = False) -> dict[str, Any]:
    """Run ``action(Memory)``. With ``soft``, a missing memory is reported, not fatal."""
    from prooflab.tutor_memory import MemoryUnavailable, connect

    try:
        with connect() as conn:
            import psycopg

            from prooflab.tutor_memory.queries import Memory, MemoryRefused

            try:
                return {"recorded": True, **action(Memory(conn, _learner(a)))}
            except (MemoryRefused, psycopg.DataError, psycopg.IntegrityError) as exc:
                # A refused request, or a value the schema's own checks rejected.
                message = str(exc).strip().splitlines()[0]
                if soft:
                    return {"recorded": False, "memory_error": message}
                fail(message)
    except MemoryUnavailable as exc:
        if soft:
            return {"recorded": False, "memory_error": str(exc)}
        fail(str(exc), code=3)


def _memory(a: argparse.Namespace, action: Any) -> Any:
    out = _with_memory(a, action)
    out.pop("recorded", None)
    return out


def _stdin_json() -> Any:
    if sys.stdin.isatty():
        fail("Pipe the JSON in on stdin.")
    try:
        return json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        fail(f"That isn't JSON: {exc}")


def _validated(model: Any, data: Any) -> Any:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        fail("Invalid input.", errors=json.loads(exc.json(include_url=False)))


def cmd_memory(t: Tutor | None, a: argparse.Namespace) -> Any:
    from prooflab.tutor_memory import models
    from prooflab.tutor_memory.db import database_url, redact, schema_name

    what = a.memory_command
    if what in ("status", "init"):

        def status(m: Any) -> dict[str, Any]:
            version = m.conn.execute("SELECT max(version) AS v FROM schema_version").fetchone()
            return {
                "connected": True,
                "database": redact(database_url()),
                "schema": schema_name(),
                "schema_version": version["v"],
                "server_version": m.conn.info.server_version,
                "learner": m.learner,
                "has_plan": m.plan() is not None,
            }

        out = _memory(a, status)
        if what == "init":
            out["message"] = "The tutor memory is ready."
        return out
    if what == "show":
        assert t is not None
        out = _memory(a, lambda m: m.show())
        for row in out["chapters"]:
            row["title"] = t.chapter_title(row["chapter"])
            row["topic"] = t.topics[row["chapter"] - 1]
        return out
    if what == "plan":
        if a.plan_command == "set":
            plan = _validated(models.PlanIn, _stdin_json())
            return _memory(a, lambda m: m.set_plan(plan))
        if a.plan_command == "archive":
            return _memory(a, lambda m: m.archive_plan())
    if what == "chapter":
        if not 1 <= a.chapter <= 14:
            fail("Chapters run from 1 to 14.")
        return _memory(a, lambda m: m.set_chapter(a.chapter, a.status))
    if what == "session":
        if a.session_command == "start":
            return _memory(a, lambda m: m.start_session(a.mode, a.chapter))
        return _memory(a, lambda m: m.end_session(a.session_id, a.summary))
    if what == "note":
        note = _validated(models.NoteIn, {"kind": a.kind, "text": a.text, "chapter": a.chapter})
        return _memory(a, lambda m: m.add_note(note))
    if what == "review":
        if a.review_command == "add":
            ids = [i.strip() for i in (a.problems or "").split(",") if i.strip()]
            item = _validated(
                models.ReviewIn, {"chapter": a.chapter, "idea": a.idea, "problem_ids": ids}
            )
            return _memory(a, lambda m: m.add_review(item))
        return _memory(a, lambda m: m.clear_review(a.review_id))
    if what == "card":
        return _memory(a, lambda m: m.review_card(a.card_id, a.recalled == "yes"))
    if what == "quiz":
        if a.quiz_command == "start":
            quiz = _validated(
                models.QuizIn,
                {
                    "kind": a.kind,
                    "chapters": _chapter_list(a.chapters or ""),
                    "seed": a.seed,
                    "total": a.total,
                    "session_id": a.session,
                },
            )
            return _memory(a, lambda m: m.start_quiz(quiz))
        return _memory(a, lambda m: m.finish_quiz(a.quiz_id))
    if what == "export":
        assert t is not None
        from prooflab.tutor_memory.export import render

        path = Path(a.path) if a.path else REPO_ROOT / "LEARNING.md"
        meta = {n: {"title": t.chapter_title(n), "minutes": None} for n in range(1, 15)}
        for n, lesson in t.lessons.items():
            meta[n]["minutes"] = lesson.minutes
        text = _memory(a, lambda m: {"text": render(m.show(), m.history(), meta)})["text"]
        path.write_text(text, encoding="utf-8")
        return {"path": str(path), "bytes": len(text.encode("utf-8"))}
    if what == "forget":
        if not a.confirm:
            fail("This deletes everything the tutor remembers about you. Pass --confirm.")
        return _memory(a, lambda m: m.forget())
    fail("Unknown memory command.")


# ---------------------------------------------------------------------- arguments


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="prooflab-tutor",
        description="The repo tutor's tools: lessons, problems, ProofLab's checker, and memory."
        " Prints JSON.",
    )
    p.add_argument("--learner", help="memory profile (default: PROOFLAB_TUTOR_LEARNER or 'me')")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("chapters", help="the 14 chapters, their lessons and problem counts")
    s = sub.add_parser("lesson", help="a chapter's lesson note")
    s.add_argument("chapter", type=int)
    s = sub.add_parser("problems", help="a chapter's problems (never solutions)")
    s.add_argument("--chapter", type=int, required=True)
    s.add_argument("--difficulty", type=int, choices=[1, 2, 3])
    s = sub.add_parser("show", help="one problem: prompt, format, step kinds (never the answer)")
    s.add_argument("problem_id")
    s = sub.add_parser("check", help="grade work with ProofLab's checker (JSON on stdin)")
    s.add_argument("problem_id")
    s.add_argument("--hints-shown", type=int, default=0, help="authored hints already shown")
    s.add_argument("--file", help="read the work from this JSON file instead of stdin")
    s.add_argument("--record", action="store_true", help="save the verdict to memory")
    s.add_argument("--session", type=int, help="memory session id")
    s.add_argument("--quiz", type=int, help="memory quiz id, for a written test question")
    s = sub.add_parser("hint", help="authored hint number N")
    s.add_argument("problem_id")
    s.add_argument("number", type=int)
    s = sub.add_parser("solution", help="the worked solution (only once the learner gives up)")
    s.add_argument("problem_id")
    s = sub.add_parser("cards", help="concept flashcards for warm-ups")
    s.add_argument("--chapter", type=int)
    s.add_argument("--count", type=int, default=3)
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--ids", help="specific card ids, comma-separated (e.g. cards due)")
    s = sub.add_parser("quiz", help="choice questions without their keys")
    s.add_argument("--chapter", type=int)
    s.add_argument("--placement", action="store_true", help="the 10-question placement")
    s.add_argument("--count", type=int, default=5)
    s.add_argument("--seed", type=int, default=1)
    s = sub.add_parser("answer", help="grade one choice")
    s.add_argument("problem_id")
    s.add_argument("--seed", type=int, required=True)
    s.add_argument("--format", choices=["answer", "spot"])
    s.add_argument("--choice", required=True, choices=list("abcde"))
    s.add_argument("--record", action="store_true", help="save the result to a memory quiz")
    s.add_argument("--quiz", type=int, help="memory quiz id")
    s = sub.add_parser("test", help="a practice quiz, midterm or final in the site's format")
    s.add_argument("--kind", choices=["quiz", "midterm", "final"], default="midterm")
    s.add_argument("--chapters", required=True, help="like 1-5 or 1,2,4")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--style", choices=["written", "mixed", "choice"], default="mixed")
    s.add_argument("--length", type=int)
    s.add_argument("--variants", action="store_true", help="allow new-number versions")
    s = sub.add_parser("variant", help="a labelled new-number version of a problem")
    s.add_argument("problem_id")
    s.add_argument("--seed", type=int, default=1)

    mem = sub.add_parser("memory", help="the tutor's memory in Postgres")
    ms = mem.add_subparsers(dest="memory_command", required=True)
    ms.add_parser("status", help="is the memory reachable?")
    ms.add_parser("init", help="create or update the memory's tables")
    ms.add_parser("show", help="everything a session needs")
    plan = ms.add_parser("plan", help="the study plan")
    ps = plan.add_subparsers(dest="plan_command", required=True)
    ps.add_parser("set", help="set plan fields (JSON on stdin)")
    ps.add_parser("archive", help="start over: archive the plan, keep its history")
    s = ms.add_parser("chapter", help="set a chapter's status")
    s.add_argument("chapter", type=int)
    s.add_argument("status", choices=["skip", "review", "do", "done"])
    sess = ms.add_parser("session", help="tutoring sessions")
    ss = sess.add_subparsers(dest="session_command", required=True)
    s = ss.add_parser("start")
    s.add_argument("mode", choices=["start", "level", "learn", "practice", "quiz", "guide"])
    s.add_argument("--chapter", type=int)
    s = ss.add_parser("end")
    s.add_argument("session_id", type=int)
    s.add_argument("--summary", help="one line for the next warm-up")
    note = ms.add_parser("note", help="remember something about the learner")
    ns = note.add_subparsers(dest="note_command", required=True)
    s = ns.add_parser("add")
    s.add_argument(
        "--kind", required=True, choices=["struggle", "misconception", "preference", "goal"]
    )
    s.add_argument("--text", required=True)
    s.add_argument("--chapter", type=int)
    rev = ms.add_parser("review", help="the review queue")
    rs = rev.add_subparsers(dest="review_command", required=True)
    s = rs.add_parser("add")
    s.add_argument("--chapter", type=int, required=True)
    s.add_argument("--idea", required=True)
    s.add_argument("--problems", help="problem ids to retry, comma-separated")
    s = rs.add_parser("clear")
    s.add_argument("review_id", type=int)
    s = ms.add_parser("card", help="record a concept card recall")
    s.add_argument("card_id")
    s.add_argument("--recalled", required=True, choices=["yes", "no"])
    quiz = ms.add_parser("quiz", help="quizzes and mock tests")
    qs = quiz.add_subparsers(dest="quiz_command", required=True)
    s = qs.add_parser("start")
    s.add_argument(
        "--kind", required=True, choices=["placement", "chapter", "quiz", "midterm", "final"]
    )
    s.add_argument("--total", type=int, required=True, help="number of questions")
    s.add_argument("--seed", type=int, required=True)
    s.add_argument("--chapters", help="like 1-5 or 1,2,4")
    s.add_argument("--session", type=int)
    s = qs.add_parser("finish")
    s.add_argument("quiz_id", type=int)
    s = ms.add_parser("export", help="write the readable LEARNING.md view")
    s.add_argument("--path", help="default: LEARNING.md at the repo root")
    s = ms.add_parser("forget", help="delete this learner's memory")
    s.add_argument("--confirm", action="store_true")
    return p


COMMANDS = {
    "chapters": cmd_chapters,
    "lesson": cmd_lesson,
    "problems": cmd_problems,
    "show": cmd_show,
    "check": cmd_check,
    "hint": cmd_hint,
    "solution": cmd_solution,
    "cards": cmd_cards,
    "quiz": cmd_quiz,
    "answer": cmd_answer,
    "test": cmd_test,
    "variant": cmd_variant,
    "memory": cmd_memory,
}
_NO_CONTENT = {("memory", c) for c in ("status", "init", "plan", "chapter", "session", "note")} | {
    ("memory", c) for c in ("review", "card", "quiz", "forget")
}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        key = (args.command, getattr(args, "memory_command", None))
        tutor = None if key in _NO_CONTENT else Tutor()
        emit(COMMANDS[args.command](tutor, args))
        return 0
    except Failure as exc:
        emit({"error": str(exc), **exc.extra})
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
