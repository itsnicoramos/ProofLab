"""The student's progress in one SQLite file (SPEC §17). One student, no accounts.

What lives here is what used to live only in each browser: flashcard and problem reviews (the
study model is rebuilt from them), best verdicts, notes decks and practice-test records. Every
browser keeps a copy for speed and offline use and syncs with ``GET``/``POST /store``, so a
phone and a laptop share one schedule. Problems and concept cards stay JSON content files.

Reviews are an append-only event log (idempotent by the browser's ``uid``), so reviews made on
two devices merge without conflicts. Decks and test records are documents with an
``updated_at``: the newer write wins, and deletions leave a tombstone so other devices drop
their copy. Best verdicts only ever go up.

The default file is ``~/Library/Application Support/ProofLab/prooflab.sqlite3`` on macOS
(outside the iCloud-synced Desktop, which would corrupt a live database), else
``~/.local/share/prooflab/prooflab.sqlite3``; ``PROOFLAB_DB`` overrides it.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SCHEMA_VERSION = 1
RANK = {"invalid": 0, "incorrect": 1, "partial": 2, "correct": 3}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reviews (
    uid TEXT PRIMARY KEY,
    item TEXT NOT NULL,
    kind TEXT NOT NULL,
    course TEXT NOT NULL,
    topic TEXT NOT NULL,
    difficulty INTEGER,
    grade INTEGER NOT NULL,
    at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS reviews_at ON reviews (at);
CREATE TABLE IF NOT EXISTS progress (
    problem_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS decks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    cards TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tests (
    id TEXT PRIMARY KEY,
    record TEXT,
    updated_at INTEGER NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0
);
"""


def default_path() -> Path:
    if env := os.environ.get("PROOFLAB_DB"):
        return Path(env).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ProofLab" / "prooflab.sqlite3"
    return Path.home() / ".local" / "share" / "prooflab" / "prooflab.sqlite3"


# --------------------------------------------------------------------------- operations

Id = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._:~-]{1,200}$")]
Short = Annotated[str, StringConstraints(max_length=200)]
Millis = Annotated[int, Field(ge=0, le=10**14)]


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewOp(_Op):
    op: Literal["review"]
    uid: Id
    item: Id
    kind: Literal["card", "problem", "note"]
    course: Short
    topic: Short
    difficulty: int | None = Field(default=None, ge=1, le=3)
    grade: int = Field(ge=1, le=4)
    at: Millis


class ResetReviewsOp(_Op):
    op: Literal["reset_reviews"]


class ProgressOp(_Op):
    op: Literal["progress"]
    problem_id: Id
    status: Literal["invalid", "incorrect", "partial", "correct"]
    at: Millis


class DeckCard(_Op):
    id: Id
    front: Annotated[str, StringConstraints(min_length=1, max_length=400)]
    back: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class DeckOp(_Op):
    op: Literal["deck"]
    id: Id
    name: Annotated[str, StringConstraints(max_length=120)]
    created_at: Millis
    cards: list[DeckCard] = Field(max_length=500)
    updated_at: Millis


class DeckDeleteOp(_Op):
    op: Literal["deck_delete"]
    id: Id
    updated_at: Millis


class TestOp(_Op):
    op: Literal["test"]
    id: Id
    record: dict[str, Any]
    updated_at: Millis


class TestDeleteOp(_Op):
    op: Literal["test_delete"]
    id: Id
    updated_at: Millis


Op = Annotated[
    ReviewOp | ResetReviewsOp | ProgressOp | DeckOp | DeckDeleteOp | TestOp | TestDeleteOp,
    Field(discriminator="op"),
]


class SyncIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ops: list[Op] = Field(max_length=2000)


MAX_RECORD_BYTES = 400_000


# --------------------------------------------------------------------------- the store


class Store:
    """A thin, thread-safe wrapper around one SQLite file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript(_SCHEMA)
        self._db.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema', ?)", (str(SCHEMA_VERSION),)
        )

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            else:
                self._db.execute("COMMIT")

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ----------------------------------------------------------------- writes

    def apply(self, ops: list[Op]) -> int:
        """Apply a batch of operations in one transaction; returns how many changed anything."""
        changed = 0
        with self._tx() as db:
            for op in ops:
                changed += self._apply_one(db, op)
        return changed

    def _apply_one(self, db: sqlite3.Connection, op: Op) -> int:
        if isinstance(op, ReviewOp):
            cur = db.execute(
                "INSERT OR IGNORE INTO reviews (uid, item, kind, course, topic, difficulty, grade,"
                " at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (op.uid, op.item, op.kind, op.course, op.topic, op.difficulty, op.grade, op.at),
            )
            return cur.rowcount
        if isinstance(op, ResetReviewsOp):
            return db.execute("DELETE FROM reviews").rowcount
        if isinstance(op, ProgressOp):
            row = db.execute(
                "SELECT status FROM progress WHERE problem_id = ?", (op.problem_id,)
            ).fetchone()
            if row is not None and RANK[row["status"]] >= RANK[op.status]:
                return 0
            db.execute(
                "INSERT INTO progress (problem_id, status, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT (problem_id) DO UPDATE SET status = excluded.status,"
                " updated_at = excluded.updated_at",
                (op.problem_id, op.status, op.at),
            )
            return 1
        if isinstance(op, DeckOp | DeckDeleteOp):
            row = db.execute("SELECT updated_at FROM decks WHERE id = ?", (op.id,)).fetchone()
            if row is not None and row["updated_at"] > op.updated_at:
                return 0  # a newer write already won
            if isinstance(op, DeckDeleteOp):
                db.execute(
                    "INSERT INTO decks (id, name, created_at, cards, updated_at, deleted)"
                    " VALUES (?, '', 0, '[]', ?, 1) ON CONFLICT (id) DO UPDATE SET deleted = 1,"
                    " cards = '[]', updated_at = excluded.updated_at",
                    (op.id, op.updated_at),
                )
                return 1
            cards = json.dumps([c.model_dump() for c in op.cards], ensure_ascii=False)
            db.execute(
                "INSERT INTO decks (id, name, created_at, cards, updated_at, deleted)"
                " VALUES (?, ?, ?, ?, ?, 0) ON CONFLICT (id) DO UPDATE SET name = excluded.name,"
                " created_at = excluded.created_at, cards = excluded.cards,"
                " updated_at = excluded.updated_at, deleted = 0",
                (op.id, op.name, op.created_at, cards, op.updated_at),
            )
            return 1
        if isinstance(op, TestOp | TestDeleteOp):
            row = db.execute("SELECT updated_at FROM tests WHERE id = ?", (op.id,)).fetchone()
            if row is not None and row["updated_at"] > op.updated_at:
                return 0
            if isinstance(op, TestDeleteOp):
                db.execute(
                    "INSERT INTO tests (id, record, updated_at, deleted) VALUES (?, NULL, ?, 1)"
                    " ON CONFLICT (id) DO UPDATE SET record = NULL, deleted = 1,"
                    " updated_at = excluded.updated_at",
                    (op.id, op.updated_at),
                )
                return 1
            record = json.dumps(op.record, ensure_ascii=False)
            if len(record.encode()) > MAX_RECORD_BYTES:
                raise ValueError(f"test record {op.id} is too large")
            db.execute(
                "INSERT INTO tests (id, record, updated_at, deleted) VALUES (?, ?, ?, 0)"
                " ON CONFLICT (id) DO UPDATE SET record = excluded.record,"
                " updated_at = excluded.updated_at, deleted = 0",
                (op.id, record, op.updated_at),
            )
            return 1
        raise TypeError(f"unknown operation {op!r}")  # pragma: no cover

    # ----------------------------------------------------------------- reads

    def snapshot(self) -> dict[str, Any]:
        """Everything, for a browser to merge into its copy."""
        with self._lock:
            db = self._db
            reviews = [
                {k: r[k] for k in r.keys()}
                for r in db.execute("SELECT * FROM reviews ORDER BY at, uid")
            ]
            progress = {r["problem_id"]: r["status"] for r in db.execute("SELECT * FROM progress")}
            decks = []
            for r in db.execute("SELECT * FROM decks ORDER BY created_at"):
                decks.append(
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "created_at": r["created_at"],
                        "cards": json.loads(r["cards"]),
                        "updated_at": r["updated_at"],
                        "deleted": bool(r["deleted"]),
                    }
                )
            tests = [
                {
                    "id": r["id"],
                    "record": json.loads(r["record"]) if r["record"] else None,
                    "updated_at": r["updated_at"],
                    "deleted": bool(r["deleted"]),
                }
                for r in db.execute("SELECT * FROM tests ORDER BY updated_at")
            ]
        return {
            "schema": SCHEMA_VERSION,
            "now": int(time.time() * 1000),
            "reviews": reviews,
            "progress": progress,
            "decks": decks,
            "tests": tests,
        }

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {
                table: self._db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
                for table in ("reviews", "progress", "decks", "tests")
            }


_STORES: dict[str, Store] = {}
_STORES_LOCK = threading.Lock()


def open_store(path: Path | str) -> Store:
    """One Store per file for the whole process (SQLite handles the rest)."""
    key = str(Path(path).expanduser().resolve()) if str(path) != ":memory:" else ":memory:"
    with _STORES_LOCK:
        if key not in _STORES:
            _STORES[key] = Store(Path(key) if key != ":memory:" else key)
        return _STORES[key]
