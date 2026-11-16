"""The tools: what the agent may do, each one a `prooflab-tutor` command (SPEC §23).

Every tool has typed arguments (checked before anything runs), a risk class, and the exact
command it runs. Text from the learner (proof steps, notes) goes on stdin, never on the
command line. The tools wrap the CLI instead of importing the checker, so the agent can only
see what the CLI shows: no solutions, no answer keys, no problem files.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from prooflab.agent.controls import Risk

CLI = "uv run --project backend --extra tutor prooflab-tutor"
TOOL_TIMEOUT = 60  # seconds; the checker inside has its own 10 s limit
MAX_OUTPUT = 12_000  # characters handed back to the model
SRC = Path(__file__).resolve().parents[2]  # backend/src, so the child finds this package
_RUN = "import sys; from prooflab.tutor import main; sys.exit(main(sys.argv[1:]))"

ProblemId = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$", description="e.g. proofs.direct.ch4-ex01")


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(Args):
    pass


class ChapterArgs(Args):
    chapter: int = Field(ge=1, le=99)


class ProblemsArgs(Args):
    chapter: int = Field(ge=1, le=99)
    difficulty: int | None = Field(default=None, ge=1, le=3)


class ProblemArgs(Args):
    problem_id: str = ProblemId


class HintArgs(Args):
    problem_id: str = ProblemId
    n: int = Field(ge=1, le=9, description="which authored hint, 1 first")


class StepArgs(Args):
    kind: str = Field(pattern=r"^[a-z_]{1,20}$", description="a step kind from show_problem")
    content: str = Field(max_length=500)


class CheckArgs(Args):
    problem_id: str = ProblemId
    steps: list[StepArgs] = Field(max_length=40)
    answer: str | None = Field(default=None, max_length=500)
    hints_shown: int = Field(default=0, ge=0, le=20)


class NoteArgs(Args):
    kind: Literal["struggle", "misconception", "preference", "goal"]
    text: str = Field(min_length=1, max_length=500)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    params: type[Args]
    risk: Risk
    argv: Callable[[Any], list[str]]
    stdin: Callable[[Any], str | None] = field(default=lambda _: None)

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.params.model_json_schema(),
        }

    def command(self, args: Args) -> str:
        """The command as a person would type it: what the guard judges and the learner sees."""
        return f"{CLI} {shlex.join(self.argv(args))}"


def _check_input(a: Args) -> str:
    assert isinstance(a, CheckArgs)
    steps = [s.model_dump() for s in a.steps]
    return json.dumps({"steps": steps, "answer": a.answer})


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in (
        Tool(
            "list_chapters",
            "The course's chapters, which have lessons, and which the checker can grade.",
            NoArgs,
            Risk.READ,
            lambda a: ["chapters"],
        ),
        Tool(
            "read_lesson",
            "ProofLab's own lesson note for a chapter. Teach from this, a few ideas at a time.",
            ChapterArgs,
            Risk.READ,
            lambda a: ["lesson", str(a.chapter)],
        ),
        Tool(
            "list_problems",
            "The checked exercises in a chapter, optionally at one difficulty (1 to 3).",
            ProblemsArgs,
            Risk.READ,
            lambda a: (
                ["problems", "--chapter", str(a.chapter)]
                + (["--difficulty", str(a.difficulty)] if a.difficulty else [])
            ),
        ),
        Tool(
            "show_problem",
            "One exercise: its prompt, the step kinds it accepts and how to type them. "
            "It never includes the answer.",
            ProblemArgs,
            Risk.READ,
            lambda a: ["show", a.problem_id],
        ),
        Tool(
            "get_hint",
            "An authored hint for an exercise. Give hints in order, after asking a question.",
            HintArgs,
            Risk.READ,
            lambda a: ["hint", a.problem_id, str(a.n)],
        ),
        Tool(
            "check_work",
            "Ask ProofLab's checker for a verdict on the learner's steps, translated exactly "
            "as they wrote them and confirmed with them first. The verdict is the only judge.",
            CheckArgs,
            Risk.READ,
            lambda a: ["check", a.problem_id, "--hints-shown", str(a.hints_shown)],
            _check_input,
        ),
        Tool(
            "show_memory",
            "What the tutor remembers about this learner: plan, progress, notes, reviews.",
            NoArgs,
            Risk.READ,
            lambda a: ["memory", "show"],
        ),
        Tool(
            "remember_note",
            "Save a short note about the learner (a struggle, misconception, preference or "
            "goal). The learner approves each save.",
            NoteArgs,
            Risk.WRITE,
            lambda a: ["memory", "note", "add", "--kind", a.kind, "--text", "-"],
            lambda a: " ".join(a.text.split()),  # one line: the CLI reads one
        ),
        Tool(
            "show_solution",
            "The worked solution. Only when the learner says they give up; they must type yes.",
            ProblemArgs,
            Risk.DESTRUCTIVE,
            lambda a: ["solution", a.problem_id],
        ),
    )
}


def run_cli(argv: list[str], stdin: str | None, course: str | None = None) -> tuple[int, str]:
    """Run one `prooflab-tutor` command in a child process: (exit code, its JSON output)."""
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    if course:
        env["PROOFLAB_TUTOR_COURSE"] = course
    done = subprocess.run(  # noqa: S603 - this package's own command line, fixed argv
        [sys.executable, "-c", _RUN, *argv],
        input=stdin or "",
        capture_output=True,
        text=True,
        timeout=TOOL_TIMEOUT,
        env=env,
        check=False,
    )
    out = (done.stdout or done.stderr).strip()
    return done.returncode, out[:MAX_OUTPUT]
