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
from prooflab.content import ContentLoadError, Registry, load_registry
from prooflab.engine.checker import check_isolated
from prooflab.engine.models import Course, Problem, Submission, Verdict
from prooflab.lessons import Lesson, LessonError, load_lessons
from prooflab.packs import CoursePack, PackError, find_pack, load_packs
from prooflab.practice import PracticeTestError
from prooflab.quiz import build_question

CHECKED_BY = "ProofLab's checker (deterministic rules and SymPy, no AI)"
CHECK_TIMEOUT = 10.0
QUESTION_TIMEOUT = 5.0  # the same limit the API gives each quiz question
REPO_ROOT = Path(__file__).resolve().parents[3]
LEARNER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
# Options that hold free text: what follows one of them is its value, never another option.
TEXT_OPTIONS = ("--text", "--summary", "--idea")


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
    """One course pack's content (SPEC §22): the problems, concept cards and lesson notes of
    the track it draws on. An empty slot has a pack and nothing else."""

    def __init__(self, pack: CoursePack | None = None) -> None:
        self.pack: CoursePack = pack or find_pack()
        self.course: Course | None = self.pack.track
        tracks = [self.course.value] if self.course else []
        self.registry: Registry = load_registry(courses=tracks)
        self.topics: list[str] = self.pack.topics
        self.lessons: dict[int, Lesson] = load_lessons(self.course.value) if self.course else {}
        self.served = [p for p in self.registry.served() if p.course is self.course]

    @property
    def variant_label(self) -> str:
        source = f"a {self.pack.book_name} exercise" if self.pack.book_name else "a book exercise"
        return f"A ProofLab-made version with new numbers. It is not {source}."

    def need_content(self) -> Course:
        """The pack's track, or a plain refusal when the pack is an empty slot."""
        if self.course is None:
            fail(
                f"{self.pack.code} is an empty slot: ProofLab has no lessons or exercises for"
                " it yet. The tutor can still plan, coach from the learner's own course"
                " materials (feedback, not a verdict) and remember.",
                course=self.pack.id,
                status=self.pack.status,
            )
        return self.course

    def chapter_of(self, problem: Problem) -> int | None:
        return self.topics.index(problem.topic) + 1 if problem.topic in self.topics else None

    def topic_of(self, chapter: int) -> str:
        self.need_content()
        if not 1 <= chapter <= len(self.topics):
            fail(f"Chapters run from 1 to {len(self.topics)}.")
        return self.topics[chapter - 1]

    def problem(self, problem_id: str) -> Problem:
        self.need_content()
        problem = find_problem(self.registry, problem_id)
        if problem is None or problem.course is not self.course:
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


def cmd_courses(_t: Tutor | None, a: argparse.Namespace) -> Any:
    """Every course pack, and which one this call would use."""
    current = getattr(a, "pack", None) or find_pack()
    return {
        "selected": current.id,
        "select_with": "prooflab-tutor --course <course> <command>",
        "courses": [pack.describe() for pack in load_packs().values()],
    }


def cmd_chapters(t: Tutor, _: argparse.Namespace) -> Any:
    track = t.course.value if t.course else ""
    cards = Counter(c.topic for c in t.registry.cards.get(track, []))
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
    book = t.registry.references.get(t.pack.book) if t.pack.book else None
    return {
        **{k: v for k, v in t.pack.describe().items() if k != "chapters"},
        "book": book and {"title": book.title, "edition": book.edition, "license": book.license},
        "free_pdf": t.pack.free_pdf,
        "chapters": out,
    }


def cmd_lesson(t: Tutor, a: argparse.Namespace) -> Any:
    t.topic_of(a.chapter)
    lesson = t.lessons.get(a.chapter)
    if lesson is None:
        fail(f"There's no lesson note for chapter {a.chapter} yet.")
    return {**lesson.summary(), "free_pdf": t.pack.free_pdf, "text": lesson.body}


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
        out["label"] = t.variant_label
    return out


UNKNOWN_FIELD = "(a field that isn't expected)"


def _field_names(model: Any) -> set[str]:
    names: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            names.update(node.get("properties", {}))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(model.model_json_schema())
    return names


def _shape_errors(exc: ValidationError, model: Any) -> list[dict[str, Any]]:
    """What is wrong with some input's shape, without repeating any of the input.

    The input can be a file (``check --file``, or a file redirected into stdin), and that file
    may not be the learner's work at all. So an error says where and why, never what was
    there: no values, and no names of fields the model doesn't have (SPEC §20).
    """
    known = _field_names(model)
    out = []
    for error in exc.errors(include_url=False, include_context=False, include_input=False):
        loc = [
            part if isinstance(part, int) or part in known or part.isdigit() else UNKNOWN_FIELD
            for part in error["loc"]
        ]
        out.append({"type": error["type"], "loc": loc, "msg": error["msg"]})
    return out


def _read_submission(a: argparse.Namespace) -> Submission:
    if a.file:
        try:
            raw = Path(a.file).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            fail("That file isn't UTF-8 text. Pass the work as JSON.")
        except OSError as exc:
            fail(f"Couldn't read the work file ({exc.strerror}).")
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
            errors=_shape_errors(exc, Submission),
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
    course = t.need_content()
    topics = [t.topic_of(a.chapter)] if a.chapter else None
    deck = build_deck(
        t.registry.cards,
        t.served,
        {b.id: b.title for b in t.registry.references.values()},
        course,
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


def _test_out(t: Tutor, kind: str, seed: int, topics: list[str], **kw: Any) -> Any:
    course = t.need_content()
    try:
        test = practice_test_out(t.registry, course, kind, t.run, seed=seed, topics=topics, **kw)
    except PracticeTestError as exc:
        fail(str(exc))
    out = test.model_dump(mode="json")
    for q in out["questions"]:
        q["problem"]["chapter"] = t.topics.index(q["problem"]["topic"]) + 1
    return out


def _chapter_quiz(t: Tutor, chapter: int, count: int, seed: int) -> Any:
    topic = t.topic_of(chapter)
    if not any(p.topic == topic for p in t.served):
        fail(f"ProofLab has no checked problems for chapter {chapter} yet.")
    return _test_out(t, "quiz", seed, [topic], length=count, style="choice")


def cmd_quiz(t: Tutor, a: argparse.Namespace) -> Any:
    if a.placement:
        return _placement(t, a.seed)
    if not a.chapter:
        fail("Give --chapter N, or --placement.")
    return _chapter_quiz(t, a.chapter, a.count, a.seed)


def _placement(t: Tutor, seed: int) -> Any:
    t.need_content()
    areas = [(item.area, item.topics) for item in t.pack.placement]
    if not areas:
        fail(f"{t.pack.code} has no placement quiz yet. Let the learner pick a starting chapter.")
    rng = random.Random(f"placement|{seed}")
    siblings = t.served
    questions: list[dict[str, Any]] = []
    used: set[str] = set()
    offset = 0
    for area, topics in areas:
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
        "areas": [area for area, _ in areas],
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


def _mock_test(
    t: Tutor,
    kind: str,
    chapters: list[int],
    seed: int,
    *,
    length: int | None,
    style: str,
    variants: bool,
) -> Any:
    topics = [t.topic_of(n) for n in chapters]
    usable = [x for x in topics if any(p.topic == x for p in t.served)]
    if not usable:
        fail("None of those chapters has checked problems yet.")
    out = _test_out(t, kind, seed, usable, length=length, style=style, variants=variants)
    skipped = [n for n, x in zip(chapters, topics, strict=True) if x not in usable]
    if skipped:
        out["skipped_chapters"] = skipped
    return out


def cmd_test(t: Tutor, a: argparse.Namespace) -> Any:
    return _mock_test(
        t,
        a.kind,
        _chapter_list(a.chapters),
        a.seed,
        length=a.length,
        style=a.style,
        variants=a.variants,
    )


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
    out["label"] = t.variant_label
    return out


# ---------------------------------------------------------------------- memory


def _learner(a: argparse.Namespace) -> str:
    name = getattr(a, "learner", None) or os.environ.get("PROOFLAB_TUTOR_LEARNER") or "me"
    if not LEARNER_RE.match(name):
        fail("A learner name is lowercase letters, digits, - and _ (up to 40).")
    return name


def _pack(a: argparse.Namespace) -> CoursePack:
    """The course pack this call is about (``main`` resolves ``--course`` into ``a.pack``)."""
    return getattr(a, "pack", None) or find_pack()


def _chapter_in(pack: CoursePack, chapter: int | None) -> None:
    """Chapter numbers are checked against the pack: courses differ in length."""
    count = len(pack.topics)
    if chapter is None:
        return
    if count == 0:
        fail(f"{pack.code} has no chapters yet, so leave the chapter out.")
    if not 1 <= chapter <= count:
        fail(f"Chapters run from 1 to {count} in {pack.code}.")


def _with_memory(a: argparse.Namespace, action: Any, *, soft: bool = False) -> dict[str, Any]:
    """Run ``action(Memory)``. With ``soft``, a missing memory is reported, not fatal."""
    from prooflab.tutor_memory import MemoryUnavailable, connect

    try:
        with connect() as conn:
            import psycopg

            from prooflab.tutor_memory.queries import Memory, MemoryRefused

            try:
                memory = Memory(conn, _learner(a), _pack(a).id)
                return {"recorded": True, **action(memory)}
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


def _text(value: str | None) -> str | None:
    """A text argument. ``-`` means "read it from stdin" (as one line), so words that came
    from the learner never have to be quoted into a shell command (SPEC §20)."""
    if value != "-":
        return value
    if sys.stdin.isatty():
        fail("Pipe the text in on stdin, or pass it as the argument.")
    return " ".join(sys.stdin.read().split())


LEARNING_FILE = "LEARNING.md"


def _write_learning(text: str) -> Path:
    """Write the export to ``LEARNING.md`` at the repo root, the only place it may go.

    The destination is fixed, so no tutor command can be pointed at another file. A link (or
    anything else that isn't a plain file) sitting there is refused instead of followed, and
    the open itself doesn't follow links either (SPEC §20).
    """
    path = REPO_ROOT / LEARNING_FILE
    if path.is_symlink() or (path.exists() and not path.is_file()):
        fail(
            f"{LEARNING_FILE} at the repo root is a link or not a plain file, so the export"
            " won't write to it. Remove it, then export again."
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o644)
    except OSError as exc:
        fail(f"Couldn't write {LEARNING_FILE} at the repo root ({exc.strerror}).")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _quiz_questions(t: Tutor, quiz: Any, style: str, variants: bool) -> list[dict[str, Any]]:
    """The questions of the quiz a memory row is for: rebuilt from its kind, chapters, seed and
    length by the same code that ``quiz`` and ``test`` run. Memory keeps them, so only answers
    to these questions can count toward the score (SPEC §20)."""
    if quiz.kind == "placement":
        built = _placement(t, quiz.seed)
    elif quiz.kind == "chapter":
        if len(quiz.chapters) != 1:
            fail("A chapter check covers one chapter: pass --chapters N.")
        built = _chapter_quiz(t, quiz.chapters[0], quiz.total, quiz.seed)
    else:
        if not quiz.chapters:
            fail("Pass the test's chapters, like --chapters 1-6.")
        built = _mock_test(
            t,
            quiz.kind,
            quiz.chapters,
            quiz.seed,
            length=quiz.total,
            style=style,
            variants=variants,
        )
    out = []
    for q in built["questions"]:
        choice = q.get("choice")
        out.append(
            {
                "problem_id": q["problem"]["id"],
                "format": choice["format"] if choice else "written",
                "seed": choice["seed"] if choice else None,
            }
        )
    return out


def _validated(model: Any, data: Any) -> Any:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        fail("Invalid input.", errors=_shape_errors(exc, model))


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
                "course": m.course,
                "has_plan": m.plan() is not None,
            }

        out = _memory(a, status)
        if what == "init":
            out["message"] = "The tutor memory is ready."
        return out
    pack = _pack(a)
    if what == "courses":
        packs = load_packs()

        def courses(m: Any) -> dict[str, Any]:
            rows = m.courses()
            for row in rows:
                known = packs.get(row["course"])
                row["code"] = known.code if known else None
                row["status"] = known.status if known else "removed"
            return {"learner": m.learner, "selected": pack.id, "courses": rows}

        return _memory(a, courses)
    if what == "show":
        assert t is not None
        out = _memory(a, lambda m: m.show(chapters=len(t.topics)))
        for row in out["chapters"]:
            row["title"] = t.chapter_title(row["chapter"])
            row["topic"] = t.topics[row["chapter"] - 1]
        return out
    if what == "plan":
        if a.plan_command == "set":
            plan = _validated(models.PlanIn, _stdin_json())
            for chapter in (plan.entry_chapter, *(plan.chapters or {})):
                _chapter_in(pack, chapter)
            return _memory(a, lambda m: m.set_plan(plan))
        if a.plan_command == "archive":
            return _memory(a, lambda m: m.archive_plan())
    if what == "chapter":
        _chapter_in(pack, a.chapter)
        return _memory(a, lambda m: m.set_chapter(a.chapter, a.status))
    if what == "session":
        if a.session_command == "start":
            _chapter_in(pack, a.chapter)
            return _memory(a, lambda m: m.start_session(a.mode, a.chapter))
        summary = _text(a.summary)
        return _memory(a, lambda m: m.end_session(a.session_id, summary))
    if what == "note":
        _chapter_in(pack, a.chapter)
        note = _validated(
            models.NoteIn, {"kind": a.kind, "text": _text(a.text), "chapter": a.chapter}
        )
        return _memory(a, lambda m: m.add_note(note))
    if what == "review":
        if a.review_command == "add":
            if a.chapter is None and pack.topics:
                fail("Pass --chapter N: the chapter the missed idea belongs to.")
            _chapter_in(pack, a.chapter)
            ids = [i.strip() for i in (a.problems or "").split(",") if i.strip()]
            item = _validated(
                models.ReviewIn, {"chapter": a.chapter, "idea": _text(a.idea), "problem_ids": ids}
            )
            return _memory(a, lambda m: m.add_review(item))
        return _memory(a, lambda m: m.clear_review(a.review_id))
    if what == "card":
        return _memory(a, lambda m: m.review_card(a.card_id, a.recalled == "yes"))
    if what == "quiz":
        if a.quiz_command == "start":
            fields = {
                "kind": a.kind,
                "chapters": _chapter_list(a.chapters or ""),
                "seed": a.seed,
                "total": a.total,
                "session_id": a.session,
            }
            # The CLI, not the agent, says which questions the quiz has and how many.
            asked = _validated(models.QuizIn, fields)
            questions = _quiz_questions(t or Tutor(pack), asked, a.style, a.variants)
            if not questions:
                fail("That quiz has no questions.")
            quiz = _validated(
                models.QuizIn, {**fields, "total": len(questions), "questions": questions}
            )
            return _memory(a, lambda m: m.start_quiz(quiz))
        return _memory(a, lambda m: m.finish_quiz(a.quiz_id))
    if what == "export":
        assert t is not None
        text = _memory(a, lambda m: {"text": _learning_text(m, t)})["text"]
        path = _write_learning(text)
        return {"path": str(path), "bytes": len(text.encode("utf-8"))}
    if what == "forget":
        if not a.confirm:
            scope = "in every course" if a.all_courses else f"in {pack.code}"
            fail(f"This deletes everything the tutor remembers about you {scope}. Pass --confirm.")
        return _memory(a, lambda m: m.forget(all_courses=a.all_courses))
    fail("Unknown memory command.")


def _learning_text(m: Any, t: Tutor) -> str:
    """``LEARNING.md``: this course first, then every other course the learner has a plan or a
    session in. With one course it is exactly that course's view."""
    from prooflab.tutor_memory.export import render

    def view(memory: Any, tutor: Tutor) -> str:
        count = len(tutor.topics)
        meta = {n: {"title": tutor.chapter_title(n), "minutes": None} for n in range(1, count + 1)}
        for n, lesson in tutor.lessons.items():
            meta[n]["minutes"] = lesson.minutes
        name = tutor.pack.book_name or tutor.pack.code
        return render(memory.show(chapters=count), memory.history(), meta, f"My {name} path")

    parts = [view(m, t)]
    packs = load_packs()
    for row in m.courses():
        other = packs.get(row["course"])
        if other is None or other.id == t.pack.id or not (row["has_plan"] or row["sessions"]):
            continue
        parts.append(view(type(m)(m.conn, m.learner, other.id), Tutor(other)))
    return "\n".join(parts)


# ---------------------------------------------------------------------- setup check

SKILL_DIR = Path(".claude") / "skills" / "tutor"
SKILL_FILES = ("SKILL.md", *(f"modes/{m}.md" for m in ("start", "level", "learn", "practice")))
SKILL_FILES += ("modes/quiz.md", "modes/guide.md", "modes/coach.md")
GUARD_HOOK = Path(".claude") / "hooks" / "tutor-guard.sh"


def cmd_doctor(_t: Tutor | None, a: argparse.Namespace) -> Any:
    """Is this clone ready to tutor? Every check says what it found and, if it failed, the
    fix. Teaching needs the course content, the checker and the skill files; saving progress
    also needs the memory. Exit code 1 means it can't teach yet (SPEC §22)."""
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, found: str, fix: str = "", needed: bool = True) -> None:
        row: dict[str, Any] = {"check": name, "ok": ok, "needed_to_teach": needed, "found": found}
        if not ok and fix:
            row["fix"] = fix
        checks.append(row)

    try:
        packs = list(load_packs().values())
        add("course packs", True, ", ".join(f"{p.code} ({p.status})" for p in packs))
    except PackError as exc:
        packs = []
        add(
            "course packs", False, str(exc), "Fix the files in backend/src/prooflab/content/packs/."
        )

    for pack in packs:
        if pack.track is None:
            found = "an empty slot: the tutor plans, coaches and remembers, with no verdicts"
            add(f"{pack.code} content", True, found, needed=False)
            continue
        try:
            t = Tutor(pack)
        except (ContentLoadError, LessonError) as exc:
            first = str(exc).strip().splitlines()[0]
            add(f"{pack.code} content", False, first, "Run: cd backend && uv run pytest -q")
            continue
        found = (
            f"{len(t.topics)} chapters, {len(t.lessons)} lesson notes, {len(t.served)} exercises"
        )
        add(f"{pack.code} content", bool(t.served), found, "This course has no exercises to check.")
        known = next(
            ((p, e) for p in t.served for e in p.examples if e.expect.status.value == "correct"),
            None,
        )
        if known is not None:
            verdict = check_isolated(known[0], known[1].submission, timeout=CHECK_TIMEOUT)
            ok = verdict.status.value == "correct"
            found = (
                "graded a known-correct answer as correct, in its own worker process"
                if ok
                else f"a known-correct answer came back {verdict.status.value} {_codes(verdict)}"
            )
            add(
                f"{pack.code} checker",
                ok,
                found,
                "Run: cd backend && uv run pytest tests/engine -q",
            )

    missing = [f for f in SKILL_FILES if not (REPO_ROOT / SKILL_DIR / f).is_file()]
    missing += [] if (REPO_ROOT / "AGENTS.md").is_file() else ["AGENTS.md"]
    found = "the skill, its modes and AGENTS.md" if not missing else f"missing: {missing}"
    add(
        "tutor instructions",
        not missing,
        found,
        "Restore them with: git checkout -- .claude AGENTS.md",
    )

    hook = REPO_ROOT / GUARD_HOOK
    ok = hook.is_file() and os.access(hook, os.X_OK)
    found = (
        "the Claude Code guard hook is in place"
        if ok
        else f"{GUARD_HOOK} is missing or not executable"
    )
    add("guardrail hook", ok, found, f"Run: chmod +x {GUARD_HOOK}", needed=False)

    learning = REPO_ROOT / LEARNING_FILE
    ok = not learning.is_symlink() and (not learning.exists() or learning.is_file())
    found = "a plain file, or not written yet" if ok else "a link or not a plain file"
    add(LEARNING_FILE, ok, found, f"Remove {LEARNING_FILE} at the repo root.", needed=False)

    def status(m: Any) -> dict[str, Any]:
        version = m.conn.execute("SELECT max(version) AS v FROM schema_version").fetchone()
        return {"schema_version": version["v"], "courses": [r["course"] for r in m.courses()]}

    memory = _with_memory(a, status, soft=True)
    saved = bool(memory.get("recorded"))
    found = (
        f"reachable, schema version {memory['schema_version']}"
        if saved
        else str(memory.get("memory_error"))
    )
    add("memory (Postgres)", saved, found, "Run: docker compose up -d tutor-db", needed=False)

    result = {
        "ready_to_teach": all(c["ok"] for c in checks if c["needed_to_teach"]),
        "can_save_progress": saved,
        "checks": checks,
    }
    if not result["ready_to_teach"]:
        fail("This clone can't tutor yet. See the checks that failed.", **result)
    return result


# ---------------------------------------------------------------------- rule evals


def cmd_scenarios(_t: Tutor | None, _a: argparse.Namespace) -> Any:
    from prooflab.tutor_evals import load_scenarios

    return [
        {k: s.get(k) for k in ("id", "title", "course", "tests")} | {"turns": len(s["turns"])}
        for s in load_scenarios().values()
    ]


def _scenario(name: str) -> dict[str, Any]:
    from prooflab.tutor_evals import load_scenarios

    scenarios = load_scenarios()
    if name not in scenarios:
        fail(f"No scenario {name!r}. They are: {', '.join(scenarios)}.")
    return scenarios[name]


def _audit(path: Path, scenario: dict[str, Any] | None) -> Any:
    from prooflab.tutor_evals import EvalError, audit, read_trace

    try:
        events = read_trace(path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError, EvalError) as exc:
        fail(f"Couldn't read that trace ({exc}).")
    report = audit(events, (scenario or {}).get("expect"))
    if scenario is not None:
        report = {"scenario": scenario["id"], **report}
    if not report["passed"]:
        fail("This session broke a rule. See violations and expectations.", **report)
    return report


def cmd_audit(_t: Tutor | None, a: argparse.Namespace) -> Any:
    """Grade a recorded session against the tutor's rules (exit code 1 when one was broken)."""
    return _audit(Path(a.trace), _scenario(a.scenario) if a.scenario else None)


def cmd_eval(_t: Tutor | None, a: argparse.Namespace) -> Any:
    """Play a scripted learner against an agent, then grade what the agent did. This starts
    the agent named by --agent and costs what that agent costs.

    The run never touches a learner's own memory or LEARNING.md: the agent's tutor commands
    get a fresh throwaway memory schema, dropped afterwards, and LEARNING.md is put back."""
    import shlex
    import uuid

    from prooflab.tutor_evals import EvalError, run_scenario
    from prooflab.tutor_memory.db import drop_eval_schema

    scenario = _scenario(a.scenario)
    out = Path(a.out)
    schema = f"eval_{uuid.uuid4().hex[:12]}"
    env = {**os.environ, "PROOFLAB_TUTOR_DB_SCHEMA": schema, "PROOFLAB_TUTOR_LEARNER": "eval"}
    learning = REPO_ROOT / LEARNING_FILE
    kept = learning.read_bytes() if learning.is_file() and not learning.is_symlink() else None
    try:
        run_scenario(scenario, shlex.split(a.agent), out, cwd=REPO_ROOT, env=env)
    except EvalError as exc:
        fail(str(exc), trace=str(out))
    finally:
        drop_eval_schema(schema)
        if not learning.is_symlink():
            if kept is not None:
                learning.write_bytes(kept)
            elif learning.is_file():
                learning.unlink()
    return {
        "trace": str(out),
        "memory": f"throwaway schema {schema}, dropped",
        **_audit(out, scenario),
    }


# ---------------------------------------------------------------------- arguments


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="prooflab-tutor",
        description="The repo tutor's tools: lessons, problems, ProofLab's checker, and memory."
        " Prints JSON.",
    )
    p.add_argument("--learner", help="memory profile (default: PROOFLAB_TUTOR_LEARNER or 'me')")
    p.add_argument(
        "--course",
        help="course pack, like math123 or 'MATH 223' (default: PROOFLAB_TUTOR_COURSE or"
        " math123). Both options may also follow the command.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("courses", help="the course packs the tutor can teach")
    sub.add_parser("doctor", help="check that this clone is set up to tutor")
    sub.add_parser("scenarios", help="the scripted learners used to test an agent")
    s = sub.add_parser("audit", help="grade a recorded session against the tutor's rules")
    s.add_argument("trace", help="a JSONL trace, or Claude Code stream-json output")
    s.add_argument("--scenario", help="also check this scenario's own expectations")
    s = sub.add_parser("eval", help="play a scripted learner against an agent, then audit it")
    s.add_argument("scenario")
    s.add_argument("--agent", required=True, help="the agent's command line, for example: claude")
    s.add_argument("--out", required=True, help="where to write the trace")
    sub.add_parser("chapters", help="the course's chapters, their lessons and problem counts")
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
    ms.add_parser("courses", help="the courses this learner has memory in")
    ms.add_parser("show", help="everything a session needs, for the selected course")
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
    s.add_argument(
        "mode", choices=["start", "level", "learn", "practice", "quiz", "guide", "coach"]
    )
    s.add_argument("--chapter", type=int)
    s = ss.add_parser("end")
    s.add_argument("session_id", type=int)
    s.add_argument("--summary", help="one line for the next warm-up ('-' reads it from stdin)")
    note = ms.add_parser("note", help="remember something about the learner")
    ns = note.add_subparsers(dest="note_command", required=True)
    s = ns.add_parser("add")
    s.add_argument(
        "--kind", required=True, choices=["struggle", "misconception", "preference", "goal"]
    )
    s.add_argument("--text", required=True, help="the note ('-' reads it from stdin)")
    s.add_argument("--chapter", type=int)
    rev = ms.add_parser("review", help="the review queue")
    rs = rev.add_subparsers(dest="review_command", required=True)
    s = rs.add_parser("add")
    s.add_argument("--chapter", type=int, help="needed when the course has chapters")
    s.add_argument("--idea", required=True, help="the missed idea ('-' reads it from stdin)")
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
    s.add_argument(
        "--style",
        choices=["written", "mixed", "choice"],
        default="mixed",
        help="the --style the mock test was built with",
    )
    s.add_argument("--variants", action="store_true", help="the mock test used --variants")
    s = qs.add_parser("finish")
    s.add_argument("quiz_id", type=int)
    ms.add_parser("export", help="write the readable view to LEARNING.md at the repo root")
    s = ms.add_parser("forget", help="delete this learner's memory of the selected course")
    s.add_argument("--confirm", action="store_true")
    s.add_argument("--all-courses", action="store_true", help="every course, not just this one")
    return p


COMMANDS = {
    "courses": cmd_courses,
    "doctor": cmd_doctor,
    "scenarios": cmd_scenarios,
    "audit": cmd_audit,
    "eval": cmd_eval,
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
    ("memory", c) for c in ("review", "card", "quiz", "forget", "courses")
}
_NO_CONTENT |= {(c, None) for c in ("courses", "doctor", "scenarios", "audit", "eval")}


def _pop_option(argv: list[str], name: str) -> str | None:
    """Take ``name VALUE`` or ``name=VALUE`` out of ``argv``, wherever it stands, so agents can
    write ``--course`` before or after the command. The value of a free-text option is left
    alone, even when it happens to read ``--course``."""
    value = None
    i = 0
    while i < len(argv):
        token = argv[i]
        if i > 0 and argv[i - 1] in TEXT_OPTIONS:
            i += 1
        elif token == name and i + 1 < len(argv):
            value = argv[i + 1]
            del argv[i : i + 2]
        elif token.startswith(name + "="):
            value = token[len(name) + 1 :]
            del argv[i]
        else:
            i += 1
    return value


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    course, learner = _pop_option(argv, "--course"), _pop_option(argv, "--learner")
    args = _parser().parse_args(argv)
    args.learner = learner
    try:
        try:
            args.pack = find_pack(course)
        except PackError as exc:
            fail(str(exc))
        key = (args.command, getattr(args, "memory_command", None))
        # Starting a quiz rebuilds its questions, so it needs the content like `quiz` does.
        starts_quiz = getattr(args, "quiz_command", None) == "start"
        tutor = None if key in _NO_CONTENT and not starts_quiz else Tutor(args.pack)
        emit(COMMANDS[args.command](tutor, args))
        return 0
    except Failure as exc:
        emit({"error": str(exc), **exc.extra})
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
