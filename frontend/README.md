# ProofLab website

One static page that shows what a coding agent does when you type `/tutor` in the ProofLab
repo (SPEC §21). It calls no API and stores nothing. See the [root README](../README.md) for the
tutor itself and [SPEC.md](../SPEC.md) for how checking works.

```
src/
├── app/
│   ├── page.tsx           the page: hero, how the pieces fit, the session replay, rules, setup
│   ├── layout.tsx         top bar and footer
│   └── error.tsx, not-found.tsx
├── components/
│   ├── Replay.tsx         the step-through (client): Back, Next, Show all, #step-N links
│   ├── StepView.tsx       one replay step, rendered on the server; the checker's verdict view
│   ├── Diagram.tsx        the pieces diagram and the replay's "working in this step" panel
│   ├── CopyButton.tsx     copies a setup command
│   ├── Rich.tsx, Logo.tsx
├── lib/
│   ├── replay.ts          replay types and helpers (no imports, so `npm test` can load it)
│   ├── site.ts            the rules, pieces, setup steps and agents the page lists
│   ├── rich.ts            safe Markdown-subset + LaTeX renderer
│   └── replay.test.ts     the replay keeps the tutor's rules; no em dashes in page text
└── replay/
    ├── practice-4.script.json   the session's turns (written) and commands (to run)
    └── practice-4.json          the same, with every command's real output (generated)
scripts/
└── capture_replay.py      runs the script's commands with prooflab-tutor and writes the JSON
```

Capture the replay again from the repo root after changing the checker, Chapter 4's content or
the CLI's output. It needs the tutor's memory (`docker compose up -d tutor-db`) and uses a
throwaway schema, so your own memory is never touched:

```bash
uv run --project backend --extra tutor python frontend/scripts/capture_replay.py
```

`npm test` runs `src/lib/*.test.ts` with Node's built-in test runner (Node 24 runs TypeScript
directly). `backend/tests/test_tutor_replay.py` checks that the CLI still prints what the page
shows.
