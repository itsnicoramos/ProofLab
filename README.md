# ProofLab

ProofLab checks university math work **one step at a time**: it tells you which step went
wrong and why, with hints written as rules, not generated text. You use it through a tutor that
runs inside your own coding agent, or through its HTTP API.

- **No AI in the verdicts.** Every verdict comes from SymPy, numeric evaluation, and
  hand-written rules. The same input always gets the same verdict.
- **A tutor in your own coding agent.** Clone the repo, open Claude Code, Codex or another
  agent in it, and type `/tutor`. It teaches all 14 chapters of *Book of Proof* from
  ProofLab's own lesson notes and has you prove real exercises. ProofLab's checker grades
  every attempt, never the AI. It remembers your plan and progress in a local Postgres. See
  [Learn with the tutor](#learn-with-the-tutor) and `SPEC.md` §20.
- **A website that shows how the tutor works.** https://prooflab-ruby.vercel.app is one page:
  a diagram of the pieces, a step-by-step replay of a real `/tutor practice 4` session (every
  command's output captured from the CLI), the tutor's seven rules and the setup steps. See
  `SPEC.md` §21.
- **Built for math and STEM courses.** Proofs (*Book of Proof*, Chapters 1 to 10) is what the
  checker and the tutor cover. Precalculus and Calculus 1 to 4 are written and checked too,
  through the API.
- **Practice tests, multiple choice and flashcards** come from the backend (`/practice-tests`,
  `/quiz/answer`, `/cards`; `SPEC.md` §13 and §15), and the tutor uses them
  (`prooflab-tutor test`, `quiz`, `cards`). Wrong choices are common mistakes, each confirmed
  wrong by the checker.
- **Two parts:** a Python/FastAPI backend that does all the checking, plus the tutor's CLI
  (`backend/`), and the Next.js explainer page (`frontend/`).

The practice website that used to live at the same address (problem shelves, the step editor,
scanning, flashcard study, tests, XP and streaks) was removed on 2026-11-08. Its code is in git
history up to commit `0eb0d0f`, and `SPEC.md` §13 to §19 still describe it.

`SPEC.md` is the source of truth for behaviour. This README covers getting it running.

## Scope disclaimer

ProofLab is a study aid. It checks a fixed set of problem *kinds* (derivatives, limits,
structured parity/divisibility proofs, ODE solutions, …; see `SPEC.md` §5) and can only verify
what those kinds model. It does not read free-form proofs, it is not a proof assistant, and a
"correct" verdict is not a substitute for your instructor's judgement. Problems marked `draft`
have machine-verified answer keys but have not been reviewed by a person yet.

## What a check looks like

```bash
curl -s localhost:8000/check -H 'content-type: application/json' -d '{
  "problem_id": "calc1.derivatives.product-rule",
  "steps": [{"kind": "expr", "content": "2x cos(x)"}],
  "answer": "2x cos(x)"
}'
```

```jsonc
{
  "status": "incorrect",
  "score": 0.0,
  "steps": [{"index": 0, "status": "error", "latex": "2 x \\cos{\\left(x \\right)}",
             "message": "This step isn't equal to f′(x)."}],
  "answer": {"status": "incorrect", "message": "Not quite. That isn't the correct answer."},
  "hints": [{"code": "PRODUCT_RULE", "step": 0,
             "message": "Check the product rule: (uv)′ = u′v + uv′, not u′v′."},
            {"code": "AUTHORED_HINT", "message": "Hint 1: f is a product u·v with u = x² and v = sin x."}]
}
```

## Run it locally

Needs [uv](https://docs.astral.sh/uv/) (`brew install uv`). The explainer page also needs
Node.js 20+ (its tests need Node 22.18+ or 24, which run TypeScript directly).

**1. Backend** (the checker, port 8000):

```bash
cd backend
uv sync
```

```bash
uv run uvicorn prooflab.main:create_app --factory --reload --reload-dir src --app-dir src
```

http://localhost:8000/docs has the interactive API docs.

**2. Website** (port 3000, optional): the explainer page. It needs no backend.

```bash
cd frontend
npm install
```

```bash
npm run dev
```

Then open http://localhost:3000.

Run the tests. In the backend terminal:

```bash
uv run pytest
```

In the frontend terminal (the replay's checks: the captured session keeps the tutor's rules):

```bash
npm test
```

After changing the checker, Chapter 4's content or the CLI's output, capture the replay again
from the repo root (it needs the tutor's memory running, and uses a throwaway schema):

```bash
uv run --project backend --extra tutor python frontend/scripts/capture_replay.py
```

While writing content for one course, limit the content tests to it:

```bash
PROOFLAB_TEST_COURSES=calc1 uv run pytest tests/test_content.py
```

> **macOS + Python 3.13 or newer:** uv marks files inside `.venv` as hidden, and Python 3.13+
> skips hidden `.pth` files, so the editable install isn't importable. The commands above
> work around it (`--app-dir src` for uvicorn, `pythonpath = ["src"]` for pytest). Docker
> doesn't have this problem.

> **If ProofLab lives in an iCloud-synced folder (like Desktop or Documents):** keep the
> generated folders out of iCloud, or iCloud uploads tens of thousands of files and, when the
> disk is low, offloads them so every read stalls. After `uv sync`, `npm install` or a fresh
> clone, run:
>
> ```bash
> xattr -w 'com.apple.fileprovider.ignore#P' 1 backend/.venv frontend/node_modules frontend/.next
> ```
>
> Also right-click the ProofLab folder in Finder → **Keep Downloaded** so source files are
> never offloaded.

## Learn with the tutor

The repo ships a math tutor for *Book of Proof* that runs inside your own coding agent, in the
spirit of *AI Engineering from Scratch*, but for proofs.
- **It teaches** each chapter from an original lesson note.
- **It quizzes you** and coaches you through real exercises.
- **ProofLab's checker** (the same deterministic rules as the API) decides whether your
  work is right. The agent explains and hints; it never grades.
- **It remembers** your plan, chapter progress, graded attempts, quiz scores, review queue,
  and what you tend to trip on. It keeps that in a local Postgres, separate from the
  API's progress database.

You need [uv](https://docs.astral.sh/uv/), Docker (Docker Desktop, or Colima on a Mac), and a
coding agent such as Claude Code or Codex.

```bash
git clone https://github.com/itsnicoramos/ProofLab.git && cd ProofLab
```

```bash
docker compose up -d tutor-db
```

```bash
cd backend && uv sync --extra tutor && uv run prooflab-tutor memory init && cd ..
```

Then open your agent in the `ProofLab` folder and start:

| Agent | Start | Next lesson | Practise a chapter | Quiz or mock test |
|---|---|---|---|---|
| Claude Code | `/tutor` | `/tutor next` | `/tutor practice 4` | `/tutor quiz 6`, `/tutor midterm 1-6` |
| Codex | `use the tutor skill to start` | `next lesson` | `practise chapter 4` | `quiz me on chapter 6` |
| Other agents | `Read AGENTS.md and be my tutor` | `next lesson` | `practise chapter 4` | `give me a mock midterm on chapters 1 to 6` |

What a session looks like:
1. A warm-up from your last session.
2. A chapter taught a few ideas at a time, with questions for you.
3. A worked example.
4. An exercise you prove yourself. The checker marks it, and you try again until it's right.
5. A short exit check.

Chapters 11 to 14 have lessons, but ProofLab can't check them yet, so the tutor's comments on
those proofs are labelled "feedback, not a verdict".

The pieces:
- **Skill:** `.claude/skills/tutor/`. Other agents reach it through `AGENTS.md`.
- **Lesson notes:** `backend/src/prooflab/content/lessons/proofs/`.
- **Tools the agent runs:** `uv run --project backend --extra tutor prooflab-tutor --help`.
- **Readable copy of your memory:** run `prooflab-tutor memory export` to get `LEARNING.md`
  (ignored by git).

Memory notes:
- Without the database, the tutor still teaches and checks; it just can't save.
- `docker compose down` keeps your memory, which lives in the `tutor-db-data` volume.
- `prooflab-tutor memory forget --confirm` deletes it.

## Live on Vercel

- Website: https://prooflab-ruby.vercel.app
- Checker API: https://prooflab-api.vercel.app (try `/health`)

The explainer page and the checker deploy to Vercel from `main` (two projects, `frontend/` and
`backend/`; see `SPEC.md` §18). The hosted checker has no progress database and reads only
text files; run it locally for photo and PDF reading and for `/store`.

## Run it with Docker

```bash
cd backend
docker build -t prooflab .
docker run --rm -p 8000:8000 -v prooflab-data:/data prooflab
```

The image keeps the progress database (reviews, test results, XP and streaks) at
`/data/prooflab.sqlite3`. The `prooflab-data` volume keeps it when the container is removed;
without `-v` it lasts only as long as the container.

The Dockerfile uses BuildKit cache mounts. Docker Desktop has BuildKit built in. With Colima,
install the buildx plugin (`brew install docker-buildx`), add the plugin folder to
`~/.docker/config.json` as brew's install note says (`"cliPluginsExtraDirs":
["$(brew --prefix)/lib/docker/cli-plugins"]`, with the path written out), and check that
`docker buildx version` works. Otherwise `docker build` stops at the first `RUN --mount` step.

Run the test suite on Python 3.12 (the production version) inside Docker:

```bash
docker build --target test -t prooflab-test backend
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `PROOFLAB_CORS_ORIGINS` | `http://localhost:3000` | comma-separated origins allowed to call the API (the Next.js dev server) |
| `PROOFLAB_CHECK_TIMEOUT` | `10` | seconds before a check is killed |
| `PROOFLAB_ISOLATE` | `1` | run each check in its own worker process (`0` = in-process, for debugging) |
| `PROOFLAB_MAX_CONCURRENT_CHECKS` | `4` | checks running at once; more get HTTP 503 |
| `PROOFLAB_DB` | `~/Library/Application Support/ProofLab/prooflab.sqlite3` (Docker: `/data/prooflab.sqlite3`) | SQLite file for your progress (reviews, decks, test results, XP), behind the `/store` endpoints |
| `TUTOR_DB_PASSWORD` | `prooflab-local` | password of the tutor's local Postgres (`docker-compose.yml`; set it in `.env`, see `.env.example`) |
| `PROOFLAB_TUTOR_DATABASE_URL` | the compose `tutor-db` on `127.0.0.1:5433` | any other Postgres for the tutor's memory |
| `PROOFLAB_TUTOR_LEARNER` | `me` | the tutor memory's profile name, if several people share a clone |

## API

| Method | Path | |
|---|---|---|
| GET | `/health` | status, version, problem count |
| GET | `/courses` | course tracks, topics, problem counts |
| GET | `/problems` | filter with `course`, `topic`, `kind`, `tag`, `difficulty`, `status` |
| GET | `/problems/{id}` | prompt, input help, citation, review status (never the answer) |
| GET | `/problems/{id}/solution` | worked solution and answer key |
| POST | `/check` | `{problem_id, steps, answer, hints_revealed}` → verdict |
| GET | `/read` | what this server can read (photos and PDFs need macOS) |
| POST | `/read` | file bytes in, lines of text out (transcription only) |
| GET | `/practice-tests` | a midterm, final or quiz from `course`, `kind`, `seed`, `topics`, `length`, `style`, `variants`, `weights`, `prefer` |
| POST | `/quiz/answer` | grade a multiple-choice answer (the right key never leaves the server) |
| GET | `/cards` | a course's flashcards (`concepts`, `problems`) |
| POST | `/cards/from-notes` | notes text in, draft flashcards out (written rules, no AI) |
| GET / POST | `/store` | saved progress in SQLite, XP activity included; the removed practice site synced with it (`SPEC.md` §17) |

## Typing math

Plain text, like a calculator: `2x sin(x)`, `x^2`, `sqrt(x+1)`, `e^(2x)`, `ln(x)`, `|x|`,
`sin^2(x)`, `pi`, `oo`. Note that `log(x)` is **base 10** and `ln(x)` is natural log. Every
step is echoed back as LaTeX so you can see how ProofLab read it. Full table: `SPEC.md` §3.

## Adding a problem

1. Create `backend/src/prooflab/content/problems/<course>/<slug>.json` (calc4 uses
   `calc4/vector_calc/` and `calc4/diff_eq/`). Copy an existing problem of the same `kind`.
2. Write an **original** problem and cite the open-textbook section that teaches it
   (`references.json` lists the books; see `REFERENCES.md`).
3. Add at least one correct example and one wrong one with the verdict you expect.
4. `uv run pytest tests/test_content.py`: it validates the file, re-derives the answer key with
   SymPy, and runs your examples.
5. Leave `review.status` as `draft` until a person has checked it, then set `reviewed` with
   `reviewer` and `reviewed_on`.

Tag problems with your course code (e.g. `"tags": ["math123"]`) and filter with
`GET /problems?tag=math123`.

## Layout

```
prooflab/
├── SPEC.md          source of truth
├── REFERENCES.md    books, licenses, citation policy
├── CONTRIBUTING.md  how to report bugs and send changes
├── AGENTS.md        instructions for AI agents, the tutor's rules (CLAUDE.md imports it)
├── docker-compose.yml   the tutor's memory: Postgres on 127.0.0.1:5433
├── .claude/skills/tutor/   the tutor skill: SKILL.md + modes/ (SPEC §20)
├── frontend/        Next.js explainer page (SPEC §21, see frontend/README.md)
│   ├── src/replay/          the captured /tutor session the page replays
│   └── scripts/capture_replay.py   re-runs every command in it for real
└── backend/
    ├── src/prooflab/
    │   ├── main.py              app factory + settings
    │   ├── practice.py          practice-test algorithm (SPEC §13)
    │   ├── quiz.py              multiple-choice questions (SPEC §13.2)
    │   ├── variants.py          ProofLab-made versions with new numbers (SPEC §13.3)
    │   ├── cards.py, notes.py   flashcards and cards from notes (SPEC §15)
    │   ├── store.py             progress database, SQLite (SPEC §17)
    │   ├── reader.py            photos/PDFs/documents → text (SPEC §14)
    │   ├── tutor.py             prooflab-tutor, the tutor's command line (SPEC §20)
    │   ├── tutor_memory/        the tutor's Postgres memory: schema/, queries, LEARNING.md export
    │   ├── lessons.py           lesson-note loader (content/lessons/)
    │   ├── api/                 routes.py, schemas.py
    │   ├── engine/
    │   │   ├── algebra.py       safe parser, equivalence, sets, solving
    │   │   ├── checker.py       kind registry, verdict rules, isolated worker
    │   │   ├── hints.py         hint catalog
    │   │   ├── models.py        Problem, Step, Verdict, Reference, Review
    │   │   └── topics/<course>/<topic>.py
    │   └── content/             references.json, courses.json, problems/**.json, cards/*.json,
    │                            lessons/proofs/chNN-*.md
    └── tests/                   engine/, api/, test_content.py, test_tutor*.py, test_lessons.py
```

## Contributing

Bug reports, bug fixes, website improvements and tutor improvements are welcome. Problems and
lesson notes are written by the maintainer for now; suggest them in an issue.
[CONTRIBUTING.md](CONTRIBUTING.md) has the workflow, the checks a pull request must pass, and
the rules every change keeps.

## License

[MIT](LICENSE), copyright itsnicoramos. That covers the code and ProofLab's own content: its
restatements of exercises, hints, worked solutions, flashcards and lesson notes.

*Book of Proof* itself is not in this repository. It is by Richard Hammack, licensed CC
BY-NC-ND 4.0, and free to read at <https://richardhammack.github.io/BookOfProof/>. ProofLab
cites its sections and exercise numbers and never copies its text (`REFERENCES.md`).
