# Contributing to ProofLab

Thanks for helping. ProofLab checks university math work one step at a time, and its verdicts
never come from AI. Every change has to keep that true. [`SPEC.md`](SPEC.md) is the source of
truth for how ProofLab behaves; this file covers how to send a change.

## What's welcome

- **Bug reports.** A wrong verdict, a crash, a page that breaks on a phone, a tutor that
  misbehaves.
- **Bug fixes** in the checker, the API, the website, or the tutor's command line
  (`prooflab-tutor`), with a test that fails before the fix and passes after it.
- **Website improvements.** The page that explains the tutor: layout, accessibility, clearer
  wording.
- **Tutor improvements.** Changes to the `/tutor` skill (`.claude/skills/tutor/`) and its
  modes that make it teach better while keeping its rules (see below).

The course content itself is written by the maintainer for now:
- new problems;
- the lesson notes;
- new problem kinds, such as checking Chapters 11 to 14.

Each problem maps to one *Book of Proof* exercise and is checked against the book, so these go
through one person. If you have an idea for content, or spot a mistake in it, open an issue.
Point to the exercise by chapter and number, never by pasting its text.

## Reporting a bug

Open an issue at <https://github.com/itsnicoramos/ProofLab/issues> with:

- **Where it happened:** the website (browser, phone or desktop), the API, or the
  tutor (which agent, and which command or mode).
- **What you did:** for a wrong verdict, the problem id (like `proofs.direct.ch4-ex01`) and
  the exact steps you typed.
- **What happened and what you expected,** and why you think the verdict is wrong. If you can,
  paste the verdict JSON or a screenshot.

Never paste *Book of Proof* text into an issue (its licence doesn't allow copies). Refer to it
as "Chapter 4 exercises, #1".

Found a security problem? Don't describe it in a public issue. Open an issue that only says
you found one, and we'll arrange a private way to share the details.

## Sending a change

1. **For anything big, open an issue first** so we can agree on the approach before you spend
   time on it. Big means:
   - a new dependency;
   - a database or memory schema change;
   - a new API endpoint;
   - a redesign of a page;
   - a change to how the tutor grades or remembers.

   Small fixes can go straight to a pull request.
2. **Fork the repo,** then create a branch from `main` with a short name, like
   `fix-set-parser-braces`.
3. **Make the change.** Keep it to one topic, and update `SPEC.md` in the same change if
   behaviour changes.
4. **Run the checks** (below) and make sure they pass.
5. **Open a pull request to `main`.** Say what changed, why, and how you tested it. For website
   changes, add screenshots at phone width (375px) and desktop width.

## Setup and checks

[README.md](README.md#run-it-locally) explains how to run ProofLab locally. These are the
checks a pull request has to pass.

Backend (from `backend/`):

```bash
uv sync --extra tutor
```

```bash
uv run pytest
```

```bash
uv run ruff check src tests && uv run ruff format --check src tests
```

The tutor memory tests need the local Postgres (`docker compose up -d tutor-db` from the repo
root). Each test uses its own schema and drops it, so your own tutor memory is never touched:

```bash
PROOFLAB_TUTOR_TEST_DATABASE_URL=postgresql://prooflab:prooflab-local@127.0.0.1:5433/prooflab_tutor uv run pytest tests/test_tutor_memory.py
```

Website (from `frontend/`):

```bash
npm install
```

```bash
npm test && npx tsc --noEmit && npm run lint
```

```bash
npm run build
```

## Rules every change keeps

- **Verdicts come from the checker only:** SymPy, numeric evaluation and written rules. The same
  input always gets the same verdict. Nothing that marks work right or wrong may call an AI
  model.
- **No *Book of Proof* text anywhere** in the repo: code, tests, comments, issues or pull
  requests. Cite sections and exercise numbers instead (`REFERENCES.md`).
- **Tests never touch real data.**
  - `backend/tests/conftest.py` points the progress database and the tutor memory at
    throwaway places. Keep it that way.
  - The website's replay is captured with a throwaway memory schema
    (`frontend/scripts/capture_replay.py`), never with your own tutor memory.
- **The website shows only real CLI output.** If your change alters what `prooflab-tutor`
  prints for the replay's commands, capture the replay again; `tests/test_tutor_replay.py`
  fails until you do.
- **Schema changes are new files.** Add a migration (`backend/src/prooflab/tutor_memory/schema/NNN_*.sql`)
  and never edit one that has already shipped. The SQLite progress store follows `SPEC.md` §17.
- **Website text** has no em dashes. Tap targets are at least 44px, and every page works at
  phone width (`DESIGN.md`).
- **Tutor changes keep the tutor's rules** (`AGENTS.md`):
  - the checker judges;
  - learner work is translated, never fixed;
  - hints come before solutions;
  - exercises are read only through `prooflab-tutor`;
  - memory changes go only through `prooflab-tutor memory`.

  If you change the CLI's output, update `.claude/skills/tutor/` and `SPEC.md` §20 to match.

## Using AI to help

Contributions written with help from an AI coding agent (Claude Code, Codex, Cursor and
similar) are welcome, on three conditions:

- **You read every line** and can explain it. Don't submit agent output you haven't reviewed.
- **You ran the checks above** yourself, and they pass.
- **You say so in the pull request:** name the tool, and say roughly what it did.

Agents working in this repo should follow [`AGENTS.md`](AGENTS.md). Claude Code loads it
through `CLAUDE.md`.

## License

ProofLab is [MIT licensed](LICENSE). By sending a contribution, you agree it is released under
the same license. There's no separate agreement to sign.

## Be decent

Be kind and specific in issues and reviews. Criticise the change, not the person. Assume people
are students and beginners unless they say otherwise.
