# ProofLab as a Linux, macOS and Windows agent harness: architecture plan

Status (2026-11-16): milestones 1 (macOS and Linux foundations) and 4 (the agent runtime,
`prooflab-agent`, SPEC §23) are done. The others are planned, with Windows last.
The README's [Roadmap](../README.md#roadmap-prooflab-as-an-agent-harness) has the summary.

## Context
ProofLab already is most of an agent harness. This plan does not start over. It hardens what exists and fills the gaps so the claim "checks every proof" is true and honest.

**Already there** (from the repo map):
- `prooflab-tutor`, a Python CLI run through uv. It prints JSON and uses exit codes 0/1/3 (`backend/src/prooflab/tutor.py`).
- A deterministic checker: SymPy plus written rules, a registry of handlers, and isolated workers with a timeout (`engine/checker.py`).
- Postgres memory: forward-only migrations 001-004, `tutor-db` in docker-compose (`tutor_memory/`).
- A guard: an allowlist hook on the agent's shell and file tools (`tutor_guard.py`, `.claude/hooks/tutor-guard.sh`).
- The agent contract: `AGENTS.md` and `.claude/skills/tutor/`.
- Rule evals: scripted learner scenarios (`tutor_evals.py`).

**Decisions:** the harness targets Linux, macOS and Windows. macOS and Linux come first and share one set of POSIX `sh` commands, and Windows follows (section 10). Scope is every *Book of Proof* proof, chapters 1-14.

**Gaps to close** (from the repo map):
1. Chapters 11-14 and MATH 223 have no checker. They get "feedback, not a verdict", and that is enforced by prompt only.
2. `check` only works on pre-authored problems. The agent translates English into steps and nothing verifies the translation.
3. The guard is Claude Code only. It fails open if Python is missing, and its path assumes `backend/.venv`.
4. There are no shell scripts (no setup, no CI entry point), and memory is learner-shaped, not proof-shaped.

## Principle
**The model translates. Code judges. Postgres remembers. The shell is the only door between them.**
The agent (Claude 4-family or any other) never decides correctness. Each layer below can be tested without the layers above it.

## Architecture (layers, top to bottom)
```
Learner (terminal, Y/N prompts)
  -> Agent runtime: `prooflab-agent run` (new)        bounded loop, tool registry, error trapping, human approval, structured logs
  -> LLM adapter (Claude by default, swappable)       translator + teacher only
  -> Guard (policy judge, allowlist)                  hard deny, the human cannot override it
  -> Shell contract: `prooflab-tutor <cmd>`           JSON on stdout, exit codes, learner text on stdin
  -> Checker core (registry -> handler -> verdict)    deterministic, isolated worker, timeout
  -> Memory (Postgres, forward-only migrations)       attempts, steps, mastery, notes, agent_events
```
Two ways in: `prooflab-agent run` (our own loop, described in 8), or any outside agent (Claude Code, Codex, Cursor) calling `prooflab-tutor` directly under `AGENTS.md`. Both end at the same checker and the same memory.

## Components and the logic behind each

### 1. Shell contract (`tutor.py`, `scripts/*.sh`)
- **Logic:** one command, one JSON object on stdout, and an exit code the agent can branch on (0 done, 1 bad request, 3 memory down).
- **Why:** a shell command is the one interface every agent can call. There is no SDK to maintain per agent. JSON means the agent can quote the verdict and cannot paraphrase it.
- **Learner text goes on stdin, never argv.** This stops shell injection and keeps the text out of the process list.
- **Change:** add `verify-all` (see 4) and `guard` (see 2). Everything else is unchanged.
- **New shell scripts, POSIX sh and Linux-safe:**
  - `scripts/setup.sh`: `uv sync --extra tutor`, `docker compose up -d tutor-db`, then `prooflab-tutor doctor`.
  - `scripts/ci.sh`: ruff, pytest, the memory tests against a throwaway Postgres, and `verify-all`. One entry point for laptops and CI.
  - `scripts/guard.sh`: replaces the macOS-shaped wrapper.

### 2. Guard (`tutor_guard.py`)
- **Logic:** an allowlist. Shell commands run only if they are read-only or a known tutor command. Paths are resolved (symlinks followed, case folded) before judging. Anything unclear is blocked.
- **Why:** the agent is untrusted input. Lessons, notes and the learner's text are data and cannot authorize an action. An allowlist fails closed, and a denylist does not.
- **Changes:**
  - Make it **fail closed** when Python is missing (today it exits 0).
  - Resolve the interpreter through `uv run` rather than `backend/.venv/bin/python`.
  - Expose it as `prooflab-tutor guard`, which reads a tool-call JSON on stdin and prints allow or deny. Claude Code, Codex and Cursor then each need only a few lines of config pointing at the same judge.
- **Honest limit:** other agents give no hook points, so for them the guard stays advisory and `audit` is the check.

### 3. Checker core (`engine/checker.py`, `engine/topics/proofs/*`)
- **Logic:** `problem.kind` selects a registered `TopicHandler`. The handler parses each step with the hand-written safe parser (no `eval` or `sympify` on learner input), applies its rules, and returns a verdict with per-step statuses and hint codes.
- **Why:** handlers per kind keep every rule small, testable and explainable. The step-level verdict is what lets the tutor point at the first wrong step.
- **Isolation:** forkserver workers with a hard timeout (10 s). On Linux add a CPU-time limit, a process-count limit and an optional no-network wrapper (`unshare -n` or `bwrap`). The existing 1 GB `RLIMIT_AS` already works on Linux.

### 4. Reaching "every proof" honestly (the main new work)
Chapters 1-10 have checkers. Chapters 11-14 need new handlers, added in this order, each with a clear "cannot verify" exit.
- **Verdict tiers (new):** `verified`, `refuted` and `cannot_verify`. The last one is a first-class status that never reads as "wrong". The agent may call work correct only on `verified`. This turns the "feedback, not a verdict" prompt rule into a code-enforced status.
- **11 Relations:** finite relations are checked by brute force over the stated set (reflexive, symmetric, transitive, equivalence classes).
- **12 Functions:** injective, surjective and bijective, checked by finite enumeration or by algebraic steps.
- **13 Calculus / 14 Cardinality:** epsilon-delta steps and explicit bijections, checked with SymPy inequalities and algebra.
  - Anything outside the supported pattern returns `cannot_verify`.
- **Not claimed:** a general-purpose theorem prover. The harness verifies *Book of Proof* exercise shapes. Free-form proofs outside those shapes get `cannot_verify`.
- **Self-test, `prooflab-tutor verify-all`:** for every problem, each authored correct example must verify and each incorrect example must fail. Chapters without a checker must return `cannot_verify` and never `correct`. This is the regression proof behind "checks every proof", and CI runs it.

### 5. Translation fidelity (the weak link)
- **Problem:** the agent turns the learner's English into steps, and a bad translation gives a verdict on the wrong proof.
- **Logic:** `check` echoes what it understood, as normalized steps. The agent shows them to the learner and the learner confirms before the verdict counts.
- **Change:** store a hash of the confirmed steps with the attempt.
- **Why:** the checker is only as honest as its input. A confirmation step is cheap and puts the learner in charge of what was submitted.

### 6. Memory (Postgres, `tutor_memory/`)
- **Logic:** forward-only SQL files run under an advisory lock on connect and are tracked in `schema_version`. Each course gets its own learner row. A failed `--record` still returns the verdict.
- **Why:** memory is never allowed to block a verdict. Forward-only means no destructive rollbacks, and any version can be rebuilt from the files.
- **Migration 005 (new):**
  - `checker_version` stamped on every attempt, so old verdicts stay reproducible after rules change.
  - `step_verdicts`, one row per step, so "where does this learner go wrong" is a query.
  - `skill_mastery`, per rule family, with a score and a last-seen date. It feeds review ordering and replaces guesswork.
- **Linux:** the docker-compose service stays the default. Allow a native Postgres through `PROOFLAB_TUTOR_DATABASE_URL`, with a documented role setup.

### 7. Evals and CI (`tutor_evals.py`, `scripts/ci.sh`)
- **Logic:** replay scripted learners, record the agent's tool calls and flag violations, which are facts, such as a rule broken or a verdict called "correct" without a checker result.
- **Why:** the harness's value is that the agent follows the rules, and that has to be measured.
- **Changes:** run the deterministic parts (`verify-all`, the guard unit tests, migrations on an empty database) in a GitHub Actions job on ubuntu with a Postgres service. Paid agent evals stay manual.

### 8. Agent runtime loop (`prooflab-agent run`, new module `prooflab/agent/`)
This part is built around four requirements: a step limit, error trapping, human approval and structured logs. It is a Python program that owns the loop, so the harness, not the model, decides what happens next.

**8a. Bounded loop (step limit)**
- **Logic:** `for step in range(MAX_STEPS)` (default 12, set by `--max-steps`). Each pass: ask the LLM, run any tool calls, append the results, and stop when the model returns no tool call. If the loop runs out, log `stop_reason=step_limit`, tell the learner, and return. There is no `while True`.
- **Why:** a model can loop forever on a bad argument. A hard bound caps cost and time, and the stop reason is always recorded.
- **Extra brakes:** a consecutive-error limit (3 failed tool calls in a row ends the run) and a per-tool timeout.

**8b. Error trapping (a tool never crashes the harness)**
- **Logic:** every tool call sits in `try/except Exception`. On failure the harness returns the error as a short string to the model (`"ToolError: unknown problem id 'x'. Valid ids come from: problems --chapter N"`), marked as an error result, so the model can fix its arguments and retry.
- **Rules:**
  - Arguments are validated first (Pydantic). A bad argument becomes a precise message naming the field, never a stack trace.
  - Messages are truncated and redacted (no passwords, no `.env` values, no learner text echoed from stdin).
  - Only `Exception` is caught. `KeyboardInterrupt` and `SystemExit` pass through, so Ctrl-C still stops the run.
  - A failing tool counts toward the consecutive-error limit in 8a.
- **Why:** this turns a crash into a lesson for the model. It is also what keeps a Postgres outage (exit code 3) from ending a session: the verdict still returns and the model is told memory is down.

**8c. Human in the loop (Y/N approval)**
- **Logic:** each tool has a risk class, and the gate runs after the guard:
  - **read** (`courses`, `show`, `lesson`, `hint`, `chapters`): runs without asking.
  - **write** (`check --record`, `memory note add`, `memory session start`): shows the exact command and asks `[y/N]`.
  - **destructive** (`memory forget`, `memory plan archive`, `solution`): needs a typed `yes`, not a single keystroke.
  - **unknown tool:** treated as destructive.
- **Defaults:** the answer is N. With no terminal (CI, a pipe) every non-read call is denied. A denial returns `"denied by the learner"` to the model so it changes course instead of retrying blindly.
- **Order:** guard first (a guard deny is final), then the Y/N prompt, then execution.
- **Why:** the learner stays in control of anything that changes memory or reveals an answer. Every decision is logged.

**8d. Structured logging**
- **Logic:** one JSON object per line (`run_id`, `step`, `event`, `tool`, `args_sha`, `risk`, `decision`, `status`, `duration_ms`, `error_kind`). It is written to `logs/agent-<run_id>.jsonl` and, when memory is up, to a new `agent_events` table.
- **Events:** `run_start`, `llm_call`, `tool_requested`, `guard_denied`, `human_approved`, `human_denied`, `tool_ok`, `tool_error`, `run_end` with its stop reason.
- **Privacy:** log a hash of the arguments, never the learner's proof text or any credential.
- **Why:** you can replay any run, count errors per tool, and feed the same events to the evals in 7.

**8e. Tool registry and LLM adapter**
- **Logic:** one registry maps tool names to a typed wrapper around a `prooflab-tutor` subcommand (run as a subprocess, JSON parsed). The LLM adapter is a small interface (`complete(messages, tools) -> reply`). The default adapter calls Claude through the Anthropic SDK. The model id is a setting, and a fake adapter drives the tests.
- **Why:** wrapping the CLI, not importing the checker, means the loop can never reach the answer files. The adapter seam makes the loop testable with no network and no cost.

### 9. Agent adapters
- **Logic:** `AGENTS.md` stays the single entry point. Add thin adapter files (Cursor rules, a Codex note) that only point at `AGENTS.md` and the guard.
- **Why:** one source of truth, so the rules cannot drift between agents.

### 10. Platforms: macOS and Linux first, then Windows
- **Logic:** macOS and Linux share POSIX `sh`, so each script (`setup.sh`, `ci.sh`, the guard wrapper) is written once. CI runs the backend checks on both `ubuntu-latest` and `macos-latest`. Only the Linux job runs the memory tests, because GitHub's macOS runners have no service containers.
- **Why:** one command set for two platforms means half the scripts to maintain, and CI catches anything macOS-only (BSD `sed`, case-insensitive paths) or Linux-only.
- **Differences already handled:**
  - The pyobjc scanning packages install only on macOS (an environment marker in `pyproject.toml`).
  - The checker's 1 GB memory limit applies only on Linux.
  - The guard folds case because macOS paths ignore case.
- **Windows plan (milestone 7):**
  - `scripts/setup.ps1` and `scripts/ci.ps1` repeat the same steps in PowerShell. WSL runs the `sh` scripts unchanged.
  - The guard runs as `prooflab-tutor guard` (section 2), a Python entry point, so no shell wrapper is needed.
  - Guard paths handle `\` separators, drive letters and `backend\.venv\Scripts\python.exe`.
  - The checker uses `spawn` (Windows has no forkserver) and relies on its timeout, because Unix rlimits don't exist there.
  - Postgres runs in Docker Desktop.
  - A `windows-latest` CI job runs the backend checks, without the memory tests.
- **Why last:** Windows needs the guard behind a Python entry point first, and that change also makes macOS and Linux simpler.

## Build order
1. macOS and Linux foundations: `scripts/setup.sh` and `scripts/ci.sh`, a fail-closed guard, a portable interpreter lookup, and CI on Ubuntu and macOS.
2. Verdict tiers (`verified`/`refuted`/`cannot_verify`) and `verify-all`. This enforces the chapter 11-14 rule in code.
3. Migration 005 (now including `agent_events`), then echo-back confirmation.
4. Agent runtime (8): tool registry, bounded loop, error trapping, Y/N gate, structured logs. Built and tested first against a fake LLM adapter.
5. Chapter 11 and 12 handlers, then 13 and 14.
6. Agent adapters, then a replay of the evals.
7. Windows: PowerShell scripts, `prooflab-tutor guard` as the hook, Windows paths, a `spawn` checker and a `windows-latest` CI job.

## Critical files
- `backend/src/prooflab/tutor.py`: the commands (`verify-all`, `guard`) and the confirmation echo.
- `backend/src/prooflab/engine/checker.py` and `engine/models.py`: the verdict tiers and the registry.
- `backend/src/prooflab/engine/topics/proofs/`: new handlers for chapters 11-14.
- `backend/src/prooflab/tutor_guard.py` and `.claude/hooks/tutor-guard.sh`: the portable, fail-closed guard.
- `backend/src/prooflab/tutor_memory/schema/005_*.sql` and `queries.py`.
- `SPEC.md` §20/§22, updated in the same change as each behaviour change.
- Reuse as-is: the `@register` handlers, `check_isolated`, `format_only()` and the `Memory` class.

## Verification
- `scripts/ci.sh` runs ruff, `uv run pytest`, the memory tests against a throwaway Postgres on :5433, and `prooflab-tutor verify-all`.
- On a clean Linux container (Ubuntu): `scripts/setup.sh`, then `prooflab-tutor doctor` must pass.
- Guard: tests for missing Python (denied), a symlink escape (denied) and `.env` reads (denied).
- Chapters 11-14: no problem ever returns `correct` without a registered handler.
- Re-capture the website replay if CLI output changes.
- Agent runtime tests, all with a fake LLM and no network:
  - A model that never stops ends at `step_limit` after exactly `MAX_STEPS` passes.
  - A tool that raises returns an error string to the model, and the loop continues.
  - Three failures in a row end the run with a logged reason.
  - A write tool with answer N is not executed, and the model receives the denial.
  - A destructive tool needs a typed `yes`, and with no terminal it is denied.
  - A guard deny cannot be overridden by `y`.
  - Ctrl-C (`KeyboardInterrupt`) is not swallowed.
  - Every log line parses as JSON and contains no proof text.

## Risks and limits to accept
- "Every proof" means every *Book of Proof* exercise shape. Anything else is `cannot_verify`, never "correct".
- Chapter 13 and 14 checking is the least certain and may need a formal backend (Lean) later.
- Agents without hooks get advisory rules only.
- Not verified: the mode files, the engine topic internals and any test run. The repo map was read-only.
