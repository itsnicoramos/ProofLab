"""Capture the website's /tutor replay: run every command for real and save what it printed.

Run it from the repo root with the tutor memory up (``docker compose up -d tutor-db``):

    uv run --project backend --extra tutor python frontend/scripts/capture_replay.py

It reads ``frontend/src/replay/practice-4.script.json``, runs each command with the
``prooflab-tutor`` CLI against a throwaway memory schema (dropped before and after, so your own
tutor memory is never touched), and writes ``frontend/src/replay/practice-4.json`` for the page.

- A ``{session}`` argument becomes the id the last ``memory session start`` returned.
- ``stdin_from: N`` sends step N's proposed steps to ``check``, so the page can only show a
  verdict for exactly the steps the tutor showed the learner.
- Absolute paths inside the repo are shortened to repo-relative ones before saving.
- An existing ``LEARNING.md`` at the repo root is put back afterwards.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPLAY = ROOT / "frontend" / "src" / "replay"
NAME = "practice-4"
SCHEMA = "replay_capture"
CLI = "uv run --project backend --extra tutor prooflab-tutor"


def drop_schema() -> None:
    import psycopg
    from psycopg import sql

    from prooflab.tutor_memory import database_url

    with psycopg.connect(database_url(), autocommit=True, connect_timeout=3) as conn:
        conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(SCHEMA)))


def shorten(value: Any) -> Any:
    prefix = f"{ROOT}{os.sep}"
    if isinstance(value, str):
        return value.replace(prefix, "")
    if isinstance(value, list):
        return [shorten(v) for v in value]
    if isinstance(value, dict):
        return {k: shorten(v) for k, v in value.items()}
    return value


def run(args: list[str], stdin: Any = None) -> tuple[int, Any]:
    exe = shutil.which("prooflab-tutor")
    if exe is None:
        sys.exit("prooflab-tutor isn't on PATH. Run this script with `uv run`, as shown above.")
    env = {**os.environ, "PROOFLAB_TUTOR_DB_SCHEMA": SCHEMA, "PROOFLAB_TUTOR_LEARNER": "me"}
    proc = subprocess.run(
        [exe, *args],
        input=None if stdin is None else json.dumps(stdin),
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        check=False,
    )
    try:
        output = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(f"`{' '.join(args)}` printed no JSON (exit {proc.returncode}):\n{proc.stderr}")
    if proc.returncode != 0:
        sys.exit(f"`{' '.join(args)}` failed (exit {proc.returncode}): {output}")
    return proc.returncode, shorten(output)


def main() -> None:
    script = json.loads((REPLAY / f"{NAME}.script.json").read_text(encoding="utf-8"))
    learning = ROOT / "LEARNING.md"
    kept = learning.read_bytes() if learning.exists() else None
    session: str | None = None

    def resolve(args: list[str]) -> list[str]:
        if "{session}" in args and session is None:
            sys.exit("A step uses {session} before any `memory session start`.")
        return [session if a == "{session}" else a for a in args]

    def note_session(args: list[str], output: Any) -> None:
        nonlocal session
        if args[:3] == ["memory", "session", "start"]:
            session = str(output["session_id"])

    drop_schema()
    try:
        setup = []
        for step in script["setup"]:
            args = resolve(step["args"])
            code, output = run(args, step.get("stdin"))
            note_session(args, output)
            setup.append({**step, "args": args, "exit": code, "output": output})

        steps = []
        for step in script["steps"]:
            if step["kind"] != "run":
                steps.append(step)
                continue
            out = {k: v for k, v in step.items() if k != "stdin_from"}
            stdin = step.get("stdin")
            if "stdin_from" in step:
                source = script["steps"][step["stdin_from"]]
                stdin = {"steps": source["proposal"], "answer": None}
            args = resolve(step["args"])
            code, output = run(args, stdin)
            note_session(args, output)
            out.update(args=args, exit=code, output=output)
            if stdin is not None:
                out["stdin"] = stdin
            if "file" in step:
                out["file_text"] = (ROOT / step["file"]).read_text(encoding="utf-8")
            steps.append(out)
    finally:
        drop_schema()
        if kept is not None:
            learning.write_bytes(kept)
        else:
            learning.unlink(missing_ok=True)

    result = {
        "title": script["title"],
        "about": script["about"],
        "setup_note": script["setup_note"],
        "captured_on": datetime.date.today().isoformat(),
        "cli": CLI,
        "setup": setup,
        "steps": steps,
    }
    target = REPLAY / f"{NAME}.json"
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {target.relative_to(ROOT)}: {len(steps)} steps.")


if __name__ == "__main__":
    main()
