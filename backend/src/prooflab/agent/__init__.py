"""prooflab-agent: ProofLab's own agent harness in the terminal (SPEC §23).

    uv run --project backend --extra tutor --extra agent prooflab-agent run

An agent here is four parts, one module each:
- model.py     the LLM (Claude by default) that translates and teaches, never grades;
- tools.py     what it may do: typed `prooflab-tutor` commands, each with a risk class;
- loop.py      the bounded loop: model, tools, repeat, with error trapping;
- controls.py  the human approval prompts and the JSON-lines event log.
"""

from __future__ import annotations

import argparse
import functools
import os
import sys
from pathlib import Path

from prooflab.agent.controls import Approver, EventLog
from prooflab.agent.loop import MAX_STEPS, REPO, Agent
from prooflab.agent.model import DEFAULT_MODEL, ClaudeModel
from prooflab.agent.tools import run_cli

__all__ = ["Agent", "main"]


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prooflab-agent", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="start a tutoring session in this terminal")
    run.add_argument("--model", default=DEFAULT_MODEL, help=f"default {DEFAULT_MODEL}")
    run.add_argument("--max-steps", type=int, default=MAX_STEPS, choices=range(1, 51), metavar="N")
    run.add_argument("--course", default=None, help="course pack, e.g. math123")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        model = ClaudeModel(args.model)
    except ImportError:
        print("The agent needs its extra: uv sync --project backend --extra agent", file=sys.stderr)
        return 1

    log_dir = Path(os.environ.get("PROOFLAB_AGENT_LOG_DIR") or REPO / "logs")
    log = EventLog.to_dir(log_dir)
    approver = Approver(input if sys.stdin.isatty() else None)
    agent = Agent(
        model,
        approver,
        log,
        max_steps=args.max_steps,
        run=functools.partial(run_cli, course=args.course),
    )
    log.event("run_start", model=model.name, max_steps=args.max_steps)
    print(f"ProofLab agent ({model.name}). Say what you want to learn. Type exit to stop.")
    print(f"Log: {log_dir / f'agent-{log.run_id}.jsonl'}")
    turns = 0
    try:
        while True:
            try:
                text = input("\nyou> ").strip()
            except EOFError:
                break
            if text.casefold() in {"exit", "quit"}:
                break
            if not text:
                continue
            turns += 1
            outcome = agent.turn(text)
            print(f"\ntutor> {outcome.text}")
            if outcome.stop_reason != "end_turn":
                print(f"[stopped: {outcome.stop_reason} after {outcome.steps} step(s)]")
    finally:
        log.event("run_end", turns=turns)
        log.stream.close()
    return 0
