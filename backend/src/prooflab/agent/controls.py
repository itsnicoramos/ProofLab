"""The controls: who may let a tool run, and the record of everything that happened (SPEC §23).

- Risk classes: reads run freely, writes ask [y/N], destructive calls need a typed "yes".
  With no terminal to ask, only reads run.
- The event log: one JSON object per line. It holds a hash of each tool's arguments, never
  the arguments, so a learner's proof never lands in a log file.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Any, TextIO


class Risk(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class Approver:
    """Asks the learner before a tool that writes or reveals something. ``ask`` is None when
    there is nobody to ask (a pipe, CI): then everything but a read is refused."""

    def __init__(self, ask: Callable[[str], str] | None) -> None:
        self.ask = ask

    def approve(self, command: str, risk: Risk) -> bool:
        if risk is Risk.READ:
            return True
        if self.ask is None:
            return False
        if risk is Risk.WRITE:
            prompt = f"\nThe agent wants to run:\n  {command}\nAllow it? [y/N] "
            return self._answer(prompt) in {"y", "yes"}
        prompt = (
            f"\nThe agent wants to run:\n  {command}\n"
            "This shows an answer or can't be undone. Type yes to allow it: "
        )
        return self._answer(prompt) == "yes"

    def _answer(self, prompt: str) -> str:
        try:
            return (self.ask(prompt) if self.ask else "").strip().casefold()
        except EOFError:
            return ""  # the input closed: that is a no


def args_hash(value: Any) -> str:
    """A short fingerprint of a tool's arguments: equal arguments, equal hash."""
    raw = json.dumps(value, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


class EventLog:
    """Structured logging: one JSON line per event, flushed as it happens."""

    def __init__(self, stream: TextIO, run_id: str | None = None) -> None:
        self.stream = stream
        self.run_id = run_id or uuid.uuid4().hex[:12]

    @classmethod
    def to_dir(cls, directory: Path) -> EventLog:
        directory.mkdir(parents=True, exist_ok=True)
        run_id = uuid.uuid4().hex[:12]
        return cls((directory / f"agent-{run_id}.jsonl").open("a", encoding="utf-8"), run_id)

    def event(self, event: str, **fields: Any) -> None:
        row = {"run_id": self.run_id, "ts": round(time.time(), 3), "event": event, **fields}
        self.stream.write(json.dumps(row, default=str) + "\n")
        self.stream.flush()
