"""The tutor memory's reads and writes. Parameterized SQL only; inputs arrive validated."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from psycopg.types.json import Jsonb

from prooflab.tutor_memory.models import (
    ChapterStatus,
    Mode,
    NoteIn,
    PlanIn,
    QuizIn,
    ReviewIn,
)

CARD_REVIEW_DAYS = 7
DEFAULT_COURSE = "math123"
ATTEMPT_STATUSES = ("correct", "partial", "incorrect", "invalid")


class MemoryRefused(ValueError):
    """A request the memory refuses (unknown id, wrong learner, bad state)."""


def _plain(value: Any) -> Any:
    """Rows as JSON-ready values."""
    if isinstance(value, datetime):
        # Shown to the learner: their own clock, not the server's UTC.
        return (value.astimezone() if value.tzinfo else value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


def _rows(cur: Any) -> list[dict[str, Any]]:
    return [_plain(r) for r in cur.fetchall()]


class Memory:
    """One learner's memory of one course, on an open connection from ``db.connect``.

    A ``learners`` row is a learner in a course (SPEC §22), so everything below is kept apart
    per course just by hanging off ``self.id``."""

    def __init__(self, conn: Any, learner: str, course: str = DEFAULT_COURSE) -> None:
        self.conn = conn
        self.learner = learner
        self.course = course
        row = conn.execute(
            "INSERT INTO learners (name, course) VALUES (%s, %s)"
            " ON CONFLICT (name, course) DO NOTHING RETURNING id",
            (learner, course),
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT id FROM learners WHERE name = %s AND course = %s", (learner, course)
            ).fetchone()
        self.id: int = row["id"]

    # ------------------------------------------------------------------ reading

    def plan(self) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT id, mission, goal, pace, exam_date, entry_chapter, placement, created_at,"
            " updated_at FROM plans WHERE learner_id = %s AND archived_at IS NULL",
            (self.id,),
        ).fetchone()
        return _plain(row) if row else None

    def chapters(self) -> dict[int, str]:
        cur = self.conn.execute(
            "SELECT chapter, status FROM chapter_status WHERE learner_id = %s", (self.id,)
        )
        return {r["chapter"]: r["status"] for r in cur.fetchall()}

    def courses(self) -> list[dict[str, Any]]:
        """Every course this learner has a memory row in, with how much is there."""
        return _rows(
            self.conn.execute(
                "SELECT l.course,"
                " EXISTS (SELECT 1 FROM plans p"
                "         WHERE p.learner_id = l.id AND p.archived_at IS NULL) AS has_plan,"
                " (SELECT count(*) FROM sessions s WHERE s.learner_id = l.id) AS sessions,"
                " (SELECT max(s.started_at) FROM sessions s"
                "  WHERE s.learner_id = l.id) AS last_session"
                " FROM learners l WHERE l.name = %s ORDER BY l.course",
                (self.learner,),
            )
        )

    def show(self, chapters: int = 14) -> dict[str, Any]:
        """Everything a tutoring session needs, in one call. ``chapters`` is how many the
        course has (the course pack knows; the memory doesn't)."""
        numbers = range(1, chapters + 1)
        q = self.conn.execute
        statuses = self.chapters()
        stats = q(
            "SELECT count(*) AS attempts,"
            " count(DISTINCT problem_id) FILTER (WHERE status = 'correct') AS problems_correct,"
            " count(*) FILTER (WHERE status = 'correct' AND first_try) AS first_try_correct"
            " FROM attempts WHERE learner_id = %s AND counted",
            (self.id,),
        ).fetchone()
        return {
            "learner": self.learner,
            "course": self.course,
            "plan": self.plan(),
            "chapters": [{"chapter": n, "status": statuses.get(n)} for n in numbers],
            "next_chapter": next((n for n in numbers if statuses.get(n) in ("do", "review")), None),
            "recent_sessions": _rows(
                q(
                    "SELECT id, mode, chapter, started_at, ended_at, summary FROM sessions"
                    " WHERE learner_id = %s ORDER BY started_at DESC, id DESC LIMIT 10",
                    (self.id,),
                )
            ),
            "recent_attempts": _rows(
                q(
                    "SELECT problem_id, chapter, status, counted, first_try, hints_shown,"
                    " hint_codes, checked_at FROM attempts WHERE learner_id = %s"
                    " ORDER BY checked_at DESC, id DESC LIMIT 10",
                    (self.id,),
                )
            ),
            "quizzes": self.quizzes(limit=5),
            "open_review": _rows(
                q(
                    "SELECT id, chapter, idea, problem_ids, added_at FROM review_queue"
                    " WHERE learner_id = %s AND cleared_at IS NULL ORDER BY added_at, id",
                    (self.id,),
                )
            ),
            "notes": _rows(
                q(
                    "SELECT id, kind, text, chapter, created_at FROM notes"
                    " WHERE learner_id = %s ORDER BY created_at DESC, id DESC LIMIT 20",
                    (self.id,),
                )
            ),
            "cards_due": self.cards_due(),
            "stats": dict(stats),
            "solved": [
                r["problem_id"]
                for r in q(
                    "SELECT DISTINCT problem_id FROM attempts"
                    " WHERE learner_id = %s AND status = 'correct' ORDER BY problem_id",
                    (self.id,),
                ).fetchall()
            ],
        }

    def quizzes(self, limit: int = 50) -> list[dict[str, Any]]:
        return _rows(
            self.conn.execute(
                "SELECT id, kind, chapters, seed, total, score, started_at, finished_at"
                " FROM quiz_results WHERE learner_id = %s"
                " ORDER BY started_at DESC, id DESC LIMIT %s",
                (self.id, limit),
            )
        )

    def cards_due(self, limit: int = 10) -> list[str]:
        """Cards last missed, or last recalled more than a week ago."""
        cur = self.conn.execute(
            "SELECT card_id FROM ("
            "  SELECT DISTINCT ON (card_id) card_id, recalled, reviewed_at FROM card_reviews"
            "  WHERE learner_id = %s ORDER BY card_id, reviewed_at DESC, id DESC"
            ") last"
            " WHERE NOT recalled OR reviewed_at < now() - make_interval(days => %s)"
            " ORDER BY reviewed_at LIMIT %s",
            (self.id, CARD_REVIEW_DAYS, limit),
        )
        return [r["card_id"] for r in cur.fetchall()]

    def history(self) -> dict[str, Any]:
        """The full log, for the LEARNING.md export."""
        q = self.conn.execute
        return {
            "sessions": _rows(
                q(
                    "SELECT s.id, s.mode, s.chapter, s.started_at, s.ended_at, s.summary,"
                    " count(a.id) FILTER (WHERE a.status = 'correct') AS correct,"
                    " count(a.id) AS checked"
                    " FROM sessions s LEFT JOIN attempts a ON a.session_id = s.id"
                    " WHERE s.learner_id = %s GROUP BY s.id ORDER BY s.started_at, s.id",
                    (self.id,),
                )
            ),
            "quizzes": list(reversed(self.quizzes())),
            "solved": _rows(
                q(
                    "SELECT problem_id, chapter, min(checked_at) AS first_correct,"
                    " bool_or(first_try) AS first_try FROM attempts"
                    " WHERE learner_id = %s AND status = 'correct'"
                    " GROUP BY problem_id, chapter ORDER BY min(checked_at)",
                    (self.id,),
                )
            ),
        }

    # ------------------------------------------------------------------ plan and chapters

    def set_plan(self, plan: PlanIn) -> dict[str, Any]:
        fields = plan.model_dump(exclude_unset=True, exclude={"chapters"})
        if "placement" in fields and fields["placement"] is not None:
            fields["placement"] = Jsonb(fields["placement"])
        with self.conn.transaction():
            current = self.plan()
            if current is None:
                if not plan.mission:
                    raise MemoryRefused("A new plan needs a mission (why you're learning).")
                cols = ["learner_id", *fields]
                self.conn.execute(
                    f"INSERT INTO plans ({', '.join(cols)})"  # noqa: S608 - column names are fixed
                    f" VALUES ({', '.join(['%s'] * len(cols))})",
                    (self.id, *fields.values()),
                )
            elif fields:
                sets = ", ".join(f"{k} = %s" for k in fields)
                self.conn.execute(
                    f"UPDATE plans SET {sets}, updated_at = now() WHERE id = %s",  # noqa: S608
                    (*fields.values(), current["id"]),
                )
            for chapter, status in (plan.chapters or {}).items():
                self.set_chapter(chapter, status)
        return {"plan": self.plan(), "chapters": self.chapters()}

    def archive_plan(self) -> dict[str, Any]:
        """Start over: the current plan and chapter statuses are kept, marked archived."""
        with self.conn.transaction():
            current = self.plan()
            if current is None:
                raise MemoryRefused("There's no active plan to archive.")
            snapshot = {str(k): v for k, v in self.chapters().items()}
            self.conn.execute(
                "UPDATE plans SET archived_at = now(), chapters_at_archive = %s WHERE id = %s",
                (Jsonb(snapshot), current["id"]),
            )
            self.conn.execute("DELETE FROM chapter_status WHERE learner_id = %s", (self.id,))
        return {"archived_plan": current["id"], "chapters_at_archive": snapshot}

    def set_chapter(self, chapter: int, status: ChapterStatus) -> dict[str, Any]:
        self.conn.execute(
            "INSERT INTO chapter_status (learner_id, chapter, status) VALUES (%s, %s, %s)"
            " ON CONFLICT (learner_id, chapter)"
            " DO UPDATE SET status = excluded.status, updated_at = now()",
            (self.id, chapter, status),
        )
        return {"chapter": chapter, "status": status}

    # ------------------------------------------------------------------ sessions

    def start_session(self, mode: Mode, chapter: int | None = None) -> dict[str, Any]:
        row = self.conn.execute(
            "INSERT INTO sessions (learner_id, mode, chapter) VALUES (%s, %s, %s)"
            " RETURNING id, started_at",
            (self.id, mode, chapter),
        ).fetchone()
        return {"session_id": row["id"], "started_at": _plain(row["started_at"])}

    def _own(self, table: str, row_id: int) -> None:
        row = self.conn.execute(
            f"SELECT learner_id FROM {table} WHERE id = %s",  # noqa: S608 - table names are fixed
            (row_id,),
        ).fetchone()
        if row is None or row["learner_id"] != self.id:
            raise MemoryRefused(
                f"No {table.rstrip('s').replace('_', ' ')} {row_id} for this learner."
            )

    def end_session(self, session_id: int, summary: str | None) -> dict[str, Any]:
        self._own("sessions", session_id)
        if summary is not None and len(summary) > 1000:
            raise MemoryRefused("Keep the summary under 1000 characters.")
        self.conn.execute(
            "UPDATE sessions SET ended_at = now(), summary = coalesce(%s, summary) WHERE id = %s",
            (summary, session_id),
        )
        return {"session_id": session_id, "ended": True}

    # ------------------------------------------------------------------ notes, review, cards

    def add_note(self, note: NoteIn) -> dict[str, Any]:
        row = self.conn.execute(
            "INSERT INTO notes (learner_id, kind, text, chapter) VALUES (%s, %s, %s, %s)"
            " RETURNING id",
            (self.id, note.kind, note.text, note.chapter),
        ).fetchone()
        return {"note_id": row["id"]}

    def add_review(self, item: ReviewIn) -> dict[str, Any]:
        row = self.conn.execute(
            "INSERT INTO review_queue (learner_id, chapter, idea, problem_ids)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (self.id, item.chapter, item.idea, item.problem_ids),
        ).fetchone()
        return {"review_id": row["id"]}

    def clear_review(self, review_id: int) -> dict[str, Any]:
        self._own("review_queue", review_id)
        self.conn.execute(
            "UPDATE review_queue SET cleared_at = coalesce(cleared_at, now()) WHERE id = %s",
            (review_id,),
        )
        return {"review_id": review_id, "cleared": True}

    def review_card(self, card_id: str, recalled: bool) -> dict[str, Any]:
        self.conn.execute(
            "INSERT INTO card_reviews (learner_id, card_id, recalled) VALUES (%s, %s, %s)",
            (self.id, card_id, recalled),
        )
        return {"card_id": card_id, "recalled": recalled}

    # ------------------------------------------------------------------ checker results

    def record_attempt(
        self,
        *,
        problem_id: str,
        chapter: int | None,
        status: str,
        score: float,
        hint_codes: list[str],
        hints_shown: int,
        steps: dict[str, Any],
        session_id: int | None = None,
        quiz_id: int | None = None,
        counted: bool = True,
    ) -> dict[str, Any]:
        """Store one checker verdict. Called by the CLI right after it runs the checker.

        ``counted`` is False when the checker couldn't read the input (a format slip, not a
        try at the math): the row is kept, but it never takes away "first try"."""
        if status not in ATTEMPT_STATUSES:
            raise MemoryRefused(f"Unknown verdict status {status!r}.")
        if session_id is not None:
            self._own("sessions", session_id)
        with self.conn.transaction():
            if quiz_id is not None:
                questions = self._open_quiz(quiz_id)
                if questions is not None and not any(
                    q["problem_id"] == problem_id and q["format"] == "written" for q in questions
                ):
                    raise MemoryRefused(
                        f"Quiz {quiz_id} has no written question {problem_id},"
                        " so this check can't count toward it."
                    )
            earlier = self.conn.execute(
                "SELECT 1 FROM attempts"
                " WHERE learner_id = %s AND problem_id = %s AND counted LIMIT 1",
                (self.id, problem_id),
            ).fetchone()
            row = self.conn.execute(
                "INSERT INTO attempts (learner_id, session_id, quiz_id, problem_id, chapter,"
                " status, score, hint_codes, hints_shown, first_try, steps, counted)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " RETURNING id, first_try, counted",
                (
                    self.id,
                    session_id,
                    quiz_id,
                    problem_id,
                    chapter,
                    status,
                    score,
                    sorted(set(hint_codes)),
                    hints_shown,
                    counted and earlier is None,
                    Jsonb(steps),
                    counted,
                ),
            ).fetchone()
        return {"attempt_id": row["id"], "first_try": row["first_try"], "counted": row["counted"]}

    def start_quiz(self, quiz: QuizIn) -> dict[str, Any]:
        if quiz.session_id is not None:
            self._own("sessions", quiz.session_id)
        questions = (
            None if quiz.questions is None else Jsonb([q.model_dump() for q in quiz.questions])
        )
        row = self.conn.execute(
            "INSERT INTO quiz_results"
            " (learner_id, session_id, kind, chapters, seed, total, questions)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                self.id,
                quiz.session_id,
                quiz.kind,
                quiz.chapters,
                quiz.seed,
                quiz.total,
                questions,
            ),
        ).fetchone()
        return {"quiz_id": row["id"], "total": quiz.total}

    def _open_quiz(self, quiz_id: int) -> list[dict[str, Any]] | None:
        """Lock the learner's quiz for a new result and return its question list (None when it
        has none on record). A finished quiz is refused: its score is final. Call this inside
        a transaction, so ``finish_quiz`` can't slip in between the check and the insert."""
        self._own("quiz_results", quiz_id)
        row = self.conn.execute(
            "SELECT finished_at, questions FROM quiz_results WHERE id = %s FOR SHARE", (quiz_id,)
        ).fetchone()
        if row["finished_at"] is not None:
            raise MemoryRefused(
                f"Quiz {quiz_id} is already finished, so nothing more can count toward it."
            )
        return row["questions"]

    def record_answer(
        self, quiz_id: int, problem_id: str, seed: int, fmt: str | None, choice: str, correct: bool
    ) -> dict[str, Any]:
        """Store one graded choice. The first answer to a question is the one that counts."""
        with self.conn.transaction():
            questions = self._open_quiz(quiz_id)
            if questions is not None and not any(
                q["problem_id"] == problem_id
                and q["format"] != "written"
                and q["seed"] == seed
                and fmt in (None, q["format"])
                for q in questions
            ):
                raise MemoryRefused(
                    f"Quiz {quiz_id} has no choice question {problem_id} with that seed and"
                    " format, so this answer can't count toward it."
                )
            row = self.conn.execute(
                "INSERT INTO quiz_answers (quiz_id, problem_id, seed, format, choice, correct)"
                " VALUES (%s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (quiz_id, problem_id, seed) DO NOTHING RETURNING id",
                (quiz_id, problem_id, seed, fmt, choice, correct),
            ).fetchone()
        return {"answer_id": row["id"] if row else None, "counted": row is not None}

    def finish_quiz(self, quiz_id: int) -> dict[str, Any]:
        """Score = right choices + written questions whose last check in this quiz was correct.

        The first call saves the score. Later calls return that saved score, and look only at
        what was recorded up to the moment the quiz was finished."""
        self._own("quiz_results", quiz_id)
        with self.conn.transaction():
            quiz = self.conn.execute(
                "SELECT total, score, finished_at FROM quiz_results WHERE id = %s FOR UPDATE",
                (quiz_id,),
            ).fetchone()
            done = quiz["finished_at"]
            choices = self.conn.execute(
                "SELECT problem_id, correct FROM quiz_answers WHERE quiz_id = %s"
                " AND (%s::timestamptz IS NULL OR answered_at <= %s)",
                (quiz_id, done, done),
            ).fetchall()
            written = self.conn.execute(
                "SELECT DISTINCT ON (problem_id) problem_id, status = 'correct' AS correct"
                " FROM attempts WHERE quiz_id = %s"
                " AND (%s::timestamptz IS NULL OR checked_at <= %s)"
                " ORDER BY problem_id, checked_at DESC, id DESC",
                (quiz_id, done, done),
            ).fetchall()
            results: dict[str, bool] = {}
            for r in [*choices, *written]:
                results[r["problem_id"]] = results.get(r["problem_id"], False) or r["correct"]
            if done is None:
                score = min(sum(results.values()), quiz["total"])
                # clock_timestamp(), not now(): later than every result counted above.
                self.conn.execute(
                    "UPDATE quiz_results SET score = %s, finished_at = clock_timestamp()"
                    " WHERE id = %s",
                    (score, quiz_id),
                )
            else:
                score = quiz["score"]
        return {
            "quiz_id": quiz_id,
            "score": score,
            "total": quiz["total"],
            "percent": round(100 * score / quiz["total"]),
            "missed": sorted(p for p, ok in results.items() if not ok),
            "unanswered": max(0, quiz["total"] - len(results)),
        }

    # ------------------------------------------------------------------ forgetting

    def forget(self, all_courses: bool = False) -> dict[str, Any]:
        """Delete everything stored for this learner in this course, or in every course
        (after the learner confirmed in chat)."""
        if all_courses:
            cur = self.conn.execute(
                "DELETE FROM learners WHERE name = %s RETURNING course", (self.learner,)
            )
        else:
            cur = self.conn.execute(
                "DELETE FROM learners WHERE id = %s RETURNING course", (self.id,)
            )
        gone = sorted(r["course"] for r in cur.fetchall())
        return {"learner": self.learner, "courses": gone, "forgotten": True}
