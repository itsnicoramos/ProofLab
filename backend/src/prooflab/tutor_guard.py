"""The tutor's hard rules as code (SPEC §22): which tool calls a tutoring agent may not make.

Two things use this. ``.claude/hooks/tutor-guard.sh`` runs it as a Claude Code ``PreToolUse``
hook, registered by the tutor skill, so a forbidden call is stopped before it happens. And
``prooflab-tutor audit`` grades a recorded session with the same function, for any agent.

Standard library only, and runnable as a plain file, so the hook starts fast and needs nothing
installed.

The shell rule is an allowlist. A tutor needs ``prooflab-tutor``, ``docker compose up -d
tutor-db``, ``cd`` inside the repo and a few read-only helpers (``ls``, ``cat``, ``head``,
``grep`` ...), so those are all a Bash call may run. Paths are resolved (links followed, case
folded, globs expanded) before they are judged, because macOS file names ignore case.
"""

from __future__ import annotations

import fnmatch
import glob as globbing
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass

PROBLEMS = "prooflab/content/problems"
WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
SUBAGENT_TOOLS = frozenset({"Agent", "Task"})

RULES = {
    "exercises-through-tools": "Rule 5: exercises are read only through prooflab-tutor.",
    "no-credentials": "Credentials are never read or shown.",
    "stay-local": "Rule 7: no API server, no website, no direct database access.",
    "no-writes": "Rule 7: the tutor writes no files; LEARNING.md comes from memory export.",
    "confirm-destructive": "Deleting or archiving memory needs the learner's own yes.",
    "tutor-commands-only": (
        "Rule 7: in a tutor session the shell runs prooflab-tutor, `docker compose up -d"
        " tutor-db`, cd inside the repo, and read-only helpers (ls, cat, head, tail, wc, grep,"
        " echo, pwd, date). Nothing else."
    ),
    "text-on-stdin": (
        "Text goes in on stdin through a quoted heredoc (<<'PROOFLAB_TEXT'), never on the"
        " command line: $, backticks, braces and unquoted heredocs run as shell code."
    ),
    "tutor-tools-only": "The tutor works through prooflab-tutor: no subagents, no MCP tools.",
}
BLOCKED_BY_GUARD = "Blocked by the ProofLab tutor's guardrail"
NEW_SESSION = " The tutor skill is active in this session; to work on the code, start a new one."

_HEREDOC = re.compile(
    r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1([^\n]*)\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)", re.S
)
_HEREDOC_MARK = "__PROOFLAB_HEREDOC__"
_ENV_FILE = re.compile(r"(?<![\w.-])\.env(?!\.example)(?:\.[\w-]+)?(?![\w-])", re.I)
_CREDENTIALS = re.compile(r"TUTOR_DB_PASSWORD|DATABASE_URL|\bprintenv\b|(?:^|[\s;&|(])env(?=$|\s)")
_STAY_LOCAL = re.compile(
    r"\buvicorn\b|prooflab\.main|\bsqlite3\b|\.sqlite3\b|\bpsql\b|\bpg_dump\b|\bpsycopg\b"
    r"|\bdocker-compose\b|\bdocker\s+(?:compose\s+)?(?:exec|run)\b"
    r"|\bnpm\b[^;&|\n]*\brun\s+(?:dev|start)\b|\bnext\s+(?:dev|start)\b",
    re.I,
)
_RECURSIVE_SEARCH = re.compile(
    r"\bgrep\s+(?:-[A-Za-z]*[rR][A-Za-z]*|--recursive)\b|(?:^|[\s;&|(])(?:rg|ag)\s|\bgit\s+grep\b"
)
_SAFE_SEARCH_ROOTS = (("backend", "src", "prooflab", "content", "lessons"), (".claude", "skills"))
_TUTOR = re.compile(r"\bprooflab-tutor\b")
_ASSIGNMENT = re.compile(
    r"(?:^|(?<=[\s;&|(]))([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|'[^']*'|[^\s;&|]+)"
)
_LEADING_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_BETWEEN_COMMANDS = re.compile(r"\|\||&&|[;\n|&]")
_NARROW_GLOB = re.compile(r"(?:\*\*/)?\*\.[A-Za-z0-9]+")
GLOBAL_OPTIONS = ("--course", "--learner")
TEXT_OPTIONS = ("--text", "--summary", "--idea")

# What a tutor's shell may run.
READ_ONLY = frozenset({"ls", "pwd", "cat", "head", "tail", "wc", "grep", "echo", "date", "true"})
DOCKER_OK = frozenset(
    {
        ("docker", "compose", "up", "-d", "tutor-db"),
        ("docker", "compose", "up", "-d"),
        ("docker", "compose", "start", "tutor-db"),
        ("docker", "compose", "ps"),
    }
)
SEARCHERS = frozenset({"rg", "ag", "find", "fd", "ack", "locate", "mdfind"})
UV_FLAGS = frozenset({"-q", "--quiet", "--frozen", "--locked", "--offline", "--no-sync"})
UV_VALUE_OPTIONS = frozenset({"--project", "--extra"})
# Maintainer commands: `eval` starts any command line, `audit` reads any file.
TUTOR_DENIED = frozenset({"eval", "audit"})
SEPARATORS = frozenset({";", "&&", "||", "|", "&", "|&"})
SINK_REDIRECTS = frozenset({">", ">>", "&>", "&>>", ">&"})


@dataclass(frozen=True)
class Finding:
    rule: str
    action: str  # "deny": never allowed. "ask": allowed only with the learner's go-ahead.
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "action": self.action, "reason": self.reason}


def _deny(rule: str, reason: str) -> Finding:
    return Finding(rule, "deny", reason)


EXERCISES = (
    "Exercise files hold solutions and worked attempts. Read exercises with"
    " `prooflab-tutor show <id>` and `prooflab-tutor problems --chapter N`."
)
SEARCH_LESSONS = " Search the lesson notes instead: backend/src/prooflab/content/lessons/."
CREDENTIALS = "That would read or print credentials. The tutor never does."


def strip_heredocs(command: str, mark: str = "") -> str:
    """The command without its here-document bodies: work and notes piped into the tools are
    data (they may say anything), so only the command line itself is judged. What follows the
    ``<<'X'`` on its own line is kept: it is still command line."""
    return _HEREDOC.sub(lambda m: f" {mark}{m.group(3)}", command)


def heredoc_bodies(command: str) -> list[str]:
    """What the command pipes in through here-documents, in order: the work and the notes."""
    return [found.group(4) for found in _HEREDOC.finditer(command)]


def _tutor_args(words: list[str]) -> list[str]:
    """A tutor call's arguments, with the course and learner options taken out."""
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
    return args


def tutor_calls(command: str) -> list[list[str]]:
    """Every ``prooflab-tutor`` invocation in a shell command, as its arguments (the course
    and learner options taken out). The audit reads traces with this.

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
        if args := _tutor_args(words):
            calls.append(args)
    return calls


def _destructive(args: list[str]) -> bool:
    return args[:2] == ["memory", "forget"] or args[:3] == ["memory", "plan", "archive"]


# ------------------------------------------------------------------------------ paths


def _resolve(path: str, cwd: str) -> str:
    """The real, case-folded path: links followed, so a link can't hide where a read goes."""
    full = os.path.realpath(os.path.join(cwd, os.path.expanduser(path or ".")))
    return full.replace(os.sep, "/").casefold()


def _under(full: str, parent: str) -> bool:
    return full == parent or full.startswith(parent.rstrip("/") + "/")


def _problems_dir(root: str) -> str:
    return _resolve(os.path.join(root, "backend", "src", *PROBLEMS.split("/")), root)


def _inside_problems(path: str, cwd: str, root: str = "") -> bool:
    full = _resolve(path, cwd)
    return PROBLEMS in full or _under(full, _problems_dir(root or cwd))


def _search_reaches_problems(path: str, cwd: str, root: str) -> bool:
    """A content search whose tree holds the exercise files would print their solutions."""
    return _under(_problems_dir(root), _resolve(path, cwd))


def _in_safe_root(path: str, cwd: str, root: str) -> bool:
    full = _resolve(path, cwd)
    return any(
        _under(full, _resolve(os.path.join(root, *parts), root)) for parts in _SAFE_SEARCH_ROOTS
    )


def _is_env(path: str) -> bool:
    return bool(_ENV_FILE.search(os.path.basename(path)))


def _path_finding(word: str, cwd: str, root: str) -> Finding | None:
    """Whether a word on the command line names an exercise file or a credentials file. Globs
    are expanded the way the shell would, so ``prob*`` and ``.e?v`` are judged by what they
    match."""
    if word.startswith("-"):
        if "=" not in word:
            return None
        word = word.split("=", 1)[1]
    candidates = [word]
    pattern = any(c in word for c in "*?[")
    if pattern:
        candidates += globbing.glob(os.path.join(cwd, os.path.expanduser(word)))
    for candidate in candidates:
        if _inside_problems(candidate, cwd, root):
            return _deny("exercises-through-tools", EXERCISES)
        if _is_env(candidate) or _is_env(_resolve(candidate, cwd)):
            return _deny("no-credentials", CREDENTIALS)
    # A pattern that would match .env once it exists (the shell's * skips dotfiles).
    base = os.path.basename(word).casefold()
    if pattern and base.startswith(".") and fnmatch.fnmatch(".env", base):
        return _deny("no-credentials", CREDENTIALS)
    return None


# ------------------------------------------------------------------------------ the shell


def _expand_tutor_variables(line: str) -> str:
    """Put a variable that holds the tutor's command line back in place, so ``$T show x`` is
    judged as what it runs. Any other ``$`` is left for the text rule to stop."""
    values = {}
    for name, value in _ASSIGNMENT.findall(line):
        if _TUTOR.search(value):
            values[name] = value[1:-1] if value[:1] in "\"'" and value[-1:] == value[:1] else value
    line = _ASSIGNMENT.sub(lambda m: " " if m.group(1) in values else m.group(0), line)
    for name, value in values.items():
        pattern = r"\$\{?" + re.escape(name) + r"\}?(?![A-Za-z0-9_])"
        line = re.sub(pattern, lambda _m, v=value: v, line)
    return line


def _simple_commands(line: str) -> list[list[str]] | Finding:
    """The command line as simple commands (lists of words), or the finding that stops it."""
    line = line.replace("\\\n", " ").replace("\n", " ; ")
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return _deny(
            "tutor-commands-only",
            "The shell can't read that command line (a quote"
            " is left open). " + RULES["tutor-commands-only"],
        )
    commands: list[list[str]] = [[]]
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in SEPARATORS:
            commands.append([])
        elif set(token) <= set("();<>|&"):
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            if token in SINK_REDIRECTS and (
                target == "/dev/null" or (token == ">&" and target in {"1", "2"})
            ):
                if commands[-1] and commands[-1][-1].isdigit():
                    commands[-1].pop()  # the file descriptor, as in 2>/dev/null
                i += 2
                continue
            reason = "Redirects, subshells and other shell plumbing write or read files."
            return _deny("tutor-commands-only", reason + " " + RULES["tutor-commands-only"])
        else:
            commands[-1].append(token)
        i += 1
    return [c for c in commands if c]


def _recursive_grep(words: list[str]) -> bool:
    for word in words[1:]:
        if word in ("--recursive", "--dereference-recursive", "--directories=recurse"):
            return True
        if word.startswith("-") and not word.startswith("--") and set(word[1:]) & {"r", "R"}:
            return True
    return False


def _grep_paths(words: list[str]) -> list[str]:
    """The paths a grep searches: its words after the pattern (or all of them with -e/-f)."""
    rest = words[1:]
    explicit = any(w in ("-e", "-f") or w.startswith(("--regexp", "--file")) for w in rest)
    plain = [w for w in rest if not w.startswith("-")]
    return plain if explicit else plain[1:]


def _tutor_call(words: list[str], cwd: str, root: str) -> list[str] | Finding | None:
    """A ``prooflab-tutor`` call's arguments, a finding, or None when it isn't the tutor."""
    i = 0
    if words[0] == "uv":
        if words[1:2] != ["run"]:
            return None
        i = 2
        while i < len(words) and words[i].startswith("-"):
            name, eq, value = words[i].partition("=")
            if name in UV_FLAGS and not eq:
                i += 1
                continue
            if name not in UV_VALUE_OPTIONS:
                reason = f"`uv run {name}` isn't something the tutor needs."
                return _deny("tutor-commands-only", reason + " " + RULES["tutor-commands-only"])
            if not eq:
                value = words[i + 1] if i + 1 < len(words) else ""
                i += 1
            i += 1
            backend = _resolve(os.path.join(root, "backend"), root)
            if (
                name == "--project"
                and value not in ("backend", "./backend", "backend/")
                and (_resolve(value, cwd) != backend)
            ):
                reason = "The tutor runs only this repository's backend project."
                return _deny("tutor-commands-only", reason + " " + RULES["tutor-commands-only"])
    program = words[i] if i < len(words) else ""
    installed = _resolve(os.path.join(root, "backend", ".venv", "bin", "prooflab-tutor"), root)
    if program != "prooflab-tutor" and _resolve(program, cwd) != installed:
        return None
    return _tutor_args(words[i + 1 :])


def _judge_bash(command: str, root: str, cwd: str) -> Finding | None:
    for found in _HEREDOC.finditer(command):
        if not found.group(1):
            return _deny("text-on-stdin", RULES["text-on-stdin"])
    line = strip_heredocs(command, _HEREDOC_MARK + " ")
    folded = line.casefold()
    if PROBLEMS in folded or "content/problems" in folded:
        return _deny("exercises-through-tools", EXERCISES)
    if _ENV_FILE.search(line) or _CREDENTIALS.search(line):
        return _deny("no-credentials", CREDENTIALS)
    if _STAY_LOCAL.search(line):
        return _deny("stay-local", RULES["stay-local"] + NEW_SESSION)
    line = _expand_tutor_variables(line)
    if any(c in line for c in "$`{}") or "<<" in line.replace(_HEREDOC_MARK, ""):
        return _deny("text-on-stdin", RULES["text-on-stdin"])
    commands = _simple_commands(line)
    if isinstance(commands, Finding):
        return commands

    ask: Finding | None = None
    for words in commands:
        piped = _HEREDOC_MARK in words
        words = [w for w in words if w != _HEREDOC_MARK]
        if not words:
            continue
        if _LEADING_ASSIGNMENT.match(words[0]):
            reason = "Setting variables for a command can point the tools somewhere else."
            return _deny("tutor-commands-only", reason + " " + RULES["tutor-commands-only"])
        for word in words[1:]:
            if found := _path_finding(word, cwd, root):
                return found
        program = words[0]
        if piped and program != "uv" and program != "prooflab-tutor":
            return _deny("text-on-stdin", RULES["text-on-stdin"])
        if program == "cd":
            target = _resolve(words[1] if len(words) > 1 else "~", cwd)
            if not _under(target, _resolve(root, root)):
                reason = "The tutor stays inside the repository."
                return _deny("tutor-commands-only", reason + " " + RULES["tutor-commands-only"])
            cwd = target
            continue
        if program in READ_ONLY and not piped:
            if program == "grep" and _recursive_grep(words):
                paths = _grep_paths(words) or ["."]
                if not all(_in_safe_root(p, cwd, root) for p in paths):
                    reason = "A search across the repo reaches the exercise files."
                    return _deny("exercises-through-tools", reason + SEARCH_LESSONS)
            continue
        if program == "docker":
            if tuple(words) in DOCKER_OK:
                continue
            return _deny("stay-local", RULES["stay-local"] + NEW_SESSION)
        if program in SEARCHERS or (program == "git" and "grep" in words):
            reason = "A search across the repo reaches the exercise files."
            return _deny("exercises-through-tools", reason + SEARCH_LESSONS)
        args = _tutor_call(words, cwd, root)
        if isinstance(args, Finding):
            return args
        if args is None:
            reason = f"`{program}` isn't one of the tutor's commands."
            return _deny("tutor-commands-only", reason + " " + RULES["tutor-commands-only"])
        if args and args[0] in TUTOR_DENIED:
            reason = f"`prooflab-tutor {args[0]}` is a maintainer command, not a tutor one."
            return _deny("tutor-commands-only", reason + NEW_SESSION)
        if _destructive(args):
            reason = (
                "This deletes or archives what the tutor remembers. Run it only if the learner"
                " asked for exactly this, in their own words, in this conversation."
            )
            ask = Finding("confirm-destructive", "ask", reason)
    return ask


# ------------------------------------------------------------------------------ judging


def judge(
    tool: str, tool_input: dict[str, object], root: str = "", cwd: str = ""
) -> Finding | None:
    """The hard rule this tool call breaks, or None. ``root`` is the repository root and
    ``cwd`` the directory the call runs in (both default to the current directory)."""
    root = root or os.getcwd()
    cwd = cwd or root
    if tool in WRITE_TOOLS:
        return _deny("no-writes", RULES["no-writes"] + NEW_SESSION)
    if tool in SUBAGENT_TOOLS or tool.startswith("mcp__"):
        return _deny("tutor-tools-only", RULES["tutor-tools-only"] + NEW_SESSION)
    if tool == "Read":
        path = str(tool_input.get("file_path") or "")
        if _inside_problems(path, cwd, root):
            return _deny("exercises-through-tools", EXERCISES)
        if _is_env(path) or _is_env(_resolve(path, cwd)):
            return _deny("no-credentials", "That file holds credentials. The tutor never reads it.")
        return None
    if tool == "Grep":
        path = str(tool_input.get("path") or "")
        pattern = str(tool_input.get("glob") or "")
        kind = str(tool_input.get("type") or "").casefold()
        # Only a search limited to one other file type (say *.md) can't print an exercise file.
        narrow = (kind and kind != "json") or (
            _NARROW_GLOB.fullmatch(pattern) and not pattern.casefold().endswith(".json")
        )
        if _inside_problems(path, cwd, root) or (
            not narrow and _search_reaches_problems(path, cwd, root)
        ):
            return _deny("exercises-through-tools", EXERCISES + SEARCH_LESSONS)
        return None
    if tool != "Bash":
        return None
    return _judge_bash(str(tool_input.get("command") or ""), root, cwd)


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
    try:
        code, out, err = hook(
            payload if isinstance(payload, dict) else {}, sys.argv[1] if sys.argv[1:] else ""
        )
    except Exception as exc:  # noqa: BLE001 - a guard that crashes must not let the call through
        print(
            f"{BLOCKED_BY_GUARD} (guard-error). The guard couldn't judge this call ({exc!r}),"
            " so it was stopped to be safe.",
            file=sys.stderr,
        )
        return 2
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
