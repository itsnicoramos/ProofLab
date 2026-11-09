"""The website's /tutor replay shows real CLI output (SPEC §21). Re-run its content and checker
commands and make sure the CLI still prints exactly what the page shows.

If this fails after a change to the checker, a problem or a lesson note, re-capture the replay:
``uv run --project backend --extra tutor python frontend/scripts/capture_replay.py``.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from prooflab import tutor

REPLAY = Path(__file__).resolve().parents[2] / "frontend" / "src" / "replay" / "practice-4.json"

pytestmark = pytest.mark.skipif(
    not REPLAY.exists(), reason="no frontend in this checkout (the backend Docker image)"
)


def steps() -> list[dict[str, Any]]:
    if not REPLAY.exists():
        return []
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    return [s for s in replay["steps"] if s["kind"] == "run"]


CONTENT = [s["args"] for s in steps() if s["args"][0] in {"show", "lesson"}]


def run_cli(capsys: pytest.CaptureFixture[str], argv: list[str], stdin: Any = None) -> Any:
    old = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(json.dumps(stdin))
    try:
        code = tutor.main(argv)
    finally:
        sys.stdin = old
    assert code == 0
    return json.loads(capsys.readouterr().out)


def test_the_replay_has_content_and_checker_steps() -> None:
    kinds = [s["args"][0] for s in steps()]
    assert "show" in kinds and "lesson" in kinds and kinds.count("check") == 2


@pytest.mark.parametrize("args", CONTENT)
def test_content_commands_still_print_what_the_page_shows(
    capsys: pytest.CaptureFixture[str], args: list[str]
) -> None:
    captured = next(s for s in steps() if s["args"] == args)
    assert run_cli(capsys, args) == captured["output"]


def test_the_checker_still_gives_the_page_its_verdicts(capsys: pytest.CaptureFixture[str]) -> None:
    for step in (s for s in steps() if s["args"][0] == "check"):
        problem = step["args"][1]
        hints = step["args"][step["args"].index("--hints-shown") + 1]
        out = run_cli(capsys, ["check", problem, "--hints-shown", hints], step["stdin"])
        assert out["checked_by"] == step["output"]["checked_by"]
        assert out["verdict"] == step["output"]["verdict"]
