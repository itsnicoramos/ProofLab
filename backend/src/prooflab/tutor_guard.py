"""The tutor's hard rules as code (SPEC §22): which tool calls a tutoring agent may not make.

Two things use this. ``.claude/hooks/tutor-guard.sh`` runs it as a Claude Code ``PreToolUse``
hook, registered by the tutor skill, so a forbidden call is stopped before it happens. And
``prooflab-tutor audit`` grades a recorded session with the same function, for any agent.

Standard library only, and runnable as a plain file, so the hook starts fast and needs nothing
installed. The checks are deliberately narrow: each one names something a tutor never needs
to do, so a lesson is never blocked by a guess.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass

PROBLEMS = "prooflab/content/problems"
WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

RULES = {
    "exercises-through-tools": "Rule 5: exercises are read only through prooflab-tutor.",
    "no-credentials": "Credentials are never read or shown.",
    "stay-local": "Rule 7: no API server, no website, no direct database access.",
    "no-writes": "Rule 7: the tutor writes no files; LEARNING.md comes from memory export.",
    "confirm-destructive": "Deleting or archiving memory needs the learner's own yes.",
}
BLOCKED_BY_GUARD = "Blocked by the ProofLab tutor's guardrail"
NEW_SESSION = " The tutor skill is active in this session; to work on the code, start a new one."

_HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)", re.S
)
_ENV_FILE = re.compile(r"(?<![\w.-])\.env(?!\.example)(?:\.[\w-]+)?(?![\w-])")
_STAY_LOCAL = re.compile(
    r"\buvicorn\b|prooflab\.main|\bsqlite3\b|\.sqlite3\b|\bpsql\b|\bpg_dump\b"
    r"|\bdocker\s+(?:compose\s+)?exec\b|\bnpm\s+run\s+(?:dev|start)\b|\bnext\s+dev\b"
)
_RECURSIVE_SEARCH = re.compile(
    r"\bgrep\s+(?:-[A-Za-z]*[rR][A-Za-z]*|--recursive)\b|(?:^|[\s;&|(])(?:rg|ag)\s|\bgit\s+grep\b"
)
_SAFE_SEARCH_ROOTS = ("content/lessons", ".claude/skills")
_TUTOR = re.compile(r"\bprooflab-tutor\b")
_ASSIGNMENT = re.compile(
    r"(?:^|(?<=[\s;&|(]))([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|'[^']*'|[^\s;&|]+)"
)
_BETWEEN_COMMANDS = re.compile(r"\|\||&&|[;\n|&]")
GLOBAL_OPTIONS = ("--course", "--learner")
TEXT_OPTIONS = ("--text", "--summary", "--idea")


@dataclass(frozen=True)
class Finding:
    rule: str
    action: str  # "deny": never allowed. "ask": allowed only with the learner's go-ahead.
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "action": self.action, "reason": self.reason}


def _deny(rule: str, reason: str) -> Finding:
    return Finding(rule, "deny", reason)


def strip_heredocs(command: str) -> str:
    """The command without its here-document bodies: work and notes piped into the tools are
    data (they may say anything), so only the command line itself is judged."""
    return _HEREDOC.sub(" ", command)


def heredoc_bodies(command: str) -> list[str]:
    """What the command pipes in through here-documents, in order: the work and the notes."""
    return [found.group(3) for found in _HEREDOC.finditer(command)]


def tutor_calls(command: str) -> list[list[str]]:
    """Every ``prooflab-tutor`` invocation in a shell command, as its arguments (the course
    and learner options taken out).

    Agents chain several in one call and often keep the long command line in a variable
    (``T="uv run ... prooflab-tutor"; $T show x; $T memory show``), so a variable that holds
    the tutor's command line counts as the tutor. Here-document bodies are not looked at.
    """
    line = strip_heredocs(command)
    names = [name for name, value in _ASSIGNMENT.findall(line) if _TUTOR.search(value)]
    line = _ASSIGNMENT.sub(lambda m: " " if m.group(1) in names else m.group(0), line)
    for name in names:
        line = re.sub(r"\$\{?" + re.escape(name) + r"\}?(?![A-Za-z0-9_])", "prooflab-tutor", line)
    calls: list[list[str]] = []
    for part in _BETWEEN_COMMANDS.split(line):
        found = _TUTOR.search(part)
        if found is None:
            continue
        rest = part[found.end() :]
        try:
            words = shlex.split(rest)
        except ValueError:
            words = rest.split()
        args: list[str] = []
        skip = False
        for i, word in enumerate(words):
            is_text = i > 0 and words[i - 1] in TEXT_OPTIONS  # a text option's own value
            if skip:
                skip = False
            elif word in GLOBAL_OPTIONS and not is_text:
                skip = True
            elif is_text or not word.startswith(tuple(o + "=" for o in GLOBAL_OPTIONS)):
                args.append(word)
        if args:
            calls.append(args)
    return calls


def _destructive(args: list[str]) -> bool:
    return args[:2] == ["memory", "forget"] or args[:3] == ["memory", "plan", "archive"]


def _inside_problems(path: str, cwd: str) -> bool:
    full = os.path.normpath(os.path.join(cwd, os.path.expanduser(path)))
    return PROBLEMS in full.replace(os.sep, "/")


def _search_reaches_problems(path: str, cwd: str, root: str) -> bool:
    """A content search whose tree holds the exercise files would print their solutions."""
    searched = os.path.normpath(os.path.join(cwd, os.path.expanduser(path or ".")))
    problems = os.path.normpath(os.path.join(root, "backend", "src", *PROBLEMS.split("/")))
    return problems == searched or problems.startswith(searched.rstrip(os.sep) + os.sep)


def judge(
    tool: str, tool_input: dict[str, object], root: str = "", cwd: str = ""
) -> Finding | None:
    """The hard rule this tool call breaks, or None. ``root`` is the repository root and
    ``cwd`` the directory the call runs in (both default to the current directory)."""
    root = root or os.getcwd()
    cwd = cwd or root
    exercises = (
        "Exercise files hold solutions and worked attempts. Read exercises with"
        " `prooflab-tutor show <id>` and `prooflab-tutor problems --chapter N`."
    )
    if tool in WRITE_TOOLS:
        return _deny("no-writes", RULES["no-writes"] + NEW_SESSION)
    if tool == "Read":
        path = str(tool_input.get("file_path") or "")
        if _inside_problems(path, cwd):
            return _deny("exercises-through-tools", exercises)
        if _ENV_FILE.search(os.path.basename(path)):
            return _deny("no-credentials", "That file holds credentials. The tutor never reads it.")
        return None
    if tool == "Grep":
        path = str(tool_input.get("path") or "")
        narrowed = str(tool_input.get("glob") or "") + str(tool_input.get("type") or "")
        # A search limited to other file types (say *.md) can't print an exercise file.
        wide = not narrowed or "json" in narrowed
        if _inside_problems(path, cwd) or (wide and _search_reaches_problems(path, cwd, root)):
            hint = " Search the lesson notes instead: backend/src/prooflab/content/lessons/."
            return _deny("exercises-through-tools", exercises + hint)
        return None
    if tool != "Bash":
        return None

    command = strip_heredocs(str(tool_input.get("command") or ""))
    if PROBLEMS in command or "content/problems" in command:
        return _deny("exercises-through-tools", exercises)
    if _ENV_FILE.search(command) or "TUTOR_DB_PASSWORD" in command:
        reason = "That would read or print credentials. The tutor never does."
        return _deny("no-credentials", reason)
    if _STAY_LOCAL.search(command):
        return _deny("stay-local", RULES["stay-local"] + NEW_SESSION)
    if _RECURSIVE_SEARCH.search(command) and not any(r in command for r in _SAFE_SEARCH_ROOTS):
        hint = " Search the lesson notes instead: backend/src/prooflab/content/lessons/."
        return _deny(
            "exercises-through-tools", "A search across the repo reaches the exercise files." + hint
        )
    if any(_destructive(args) for args in tutor_calls(str(tool_input.get("command") or ""))):
        reason = (
            "This deletes or archives what the tutor remembers. Run it only if the learner"
            " asked for exactly this, in their own words, in this conversation."
        )
        return Finding("confirm-destructive", "ask", reason)
    return None


def hook(payload: dict[str, object], root: str = "") -> tuple[int, str, str]:
    """Answer a Claude Code ``PreToolUse`` hook: (exit code, stdout, stderr).

    A denied call exits 2 with the reason on stderr, which Claude Code shows to the model. A
    call that needs the learner's go-ahead prints the JSON that makes Claude Code ask them.
    """
    tool_input = payload.get("tool_input")
    finding = judge(
        str(payload.get("tool_name") or ""),
        tool_input if isinstance(tool_input, dict) else {},
        root or str(os.environ.get("CLAUDE_PROJECT_DIR") or ""),
        str(payload.get("cwd") or ""),
    )
    if finding is None:
        return 0, "", ""
    if finding.action == "ask":
        decision = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": finding.reason,
            }
        }
        return 0, json.dumps(decision), ""
    return 2, "", f"{BLOCKED_BY_GUARD} ({finding.rule}). {finding.reason}"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0  # not a hook payload: nothing to judge
    code, out, err = hook(
        payload if isinstance(payload, dict) else {}, sys.argv[1] if sys.argv[1:] else ""
    )
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
