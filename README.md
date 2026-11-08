# ProofLab

ProofLab checks university math work **one step at a time**. Pick a problem, type your steps,
and ProofLab tells you which step went wrong and why, with hints written as rules, not
generated text.

- **No AI.** Every verdict comes from SymPy, numeric evaluation, and hand-written rules. The
  same input always gets the same verdict.
- **Built for math and STEM courses:** proofs (Book of Proof, Chapters 1–10) is the course
  on the site for now. Precalculus and Calculus 1–4 are written and checked too, but hidden
  until later: add a course back to `COURSE_ORDER` in `frontend/src/lib/labels.ts` to show it.
- **Practice tests.** Build a midterm, final or quick quiz from the problem bank, written out
  or as multiple choice (wrong choices are common mistakes, each confirmed wrong by the
  checker). Optionally adapt it to your weak chapters and mix in ProofLab-made versions with new
  numbers (labelled as not from the book). See `SPEC.md` §13.
- **Flashcards that schedule themselves.** Cited definition and theorem cards, one card per
  problem, and cards found in your own notes by written rules. Spaced repetition (FSRS) with a
  memory factor fitted to your own reviews, all in your browser. See `SPEC.md` §15.
- **XP, streaks and a daily goal.** Solve a problem or get a practice-test question right and
  you earn XP; get it wrong and you try again, at no cost. Flashcards pay 1 XP a card a day for
  reviewing them. XP feeds a daily goal, a streak (with earned freezes), levels, chapter progress
  and milestones. XP comes from the checker's verdict, a test's score, or a flashcard review,
  never from AI. See [XP and streaks](#xp-and-streaks) and `SPEC.md` §19.
- **Scan your work.** Photograph handwriting or pick a photo, PDF or Word document; ProofLab
  reads it on your Mac (Apple's on-device text recognizer), you fix any misreads, and the lines
  become steps. Reading never decides right or wrong. See `SPEC.md` §14.
- **Two parts:** a Python/FastAPI backend that does all the checking (`backend/`) and a
  Next.js website you study in (`frontend/`).

`SPEC.md` is the source of truth for behaviour. This README covers getting it running.

## XP and streaks

ProofLab borrows the game ideas that keep people practising (XP, a daily goal, a streak), not
anyone's look: no mascot, gems, leagues, sounds or confetti. The rules:

| You did | XP |
|---|---|
| Solved a problem (easy / medium / hard) | 10 / 15 / 20 |
| ...on the first check of the visit | +5 |
| ...after asking for extra hints | −5 each, never below 5 (the first hint, shown after a wrong check, is free) |
| ...after opening the worked solution | 0 for that problem today |
| ...again the same day | 0 |
| ...again on a later day (a review) | half |
| Partly there, not yet, or couldn't check | 0, and a **Try again** button |
| Practice test: each written question right / partly right | 10, 15 or 20 by difficulty / half |
| Practice test: each multiple-choice question right | 5 |
| Finished a quiz / midterm / final (half or more answered) | +5 / +20 / +30 |
| Scored 70% or more on a test | +10 |
| Retook the same test | only what beats your best on it |
| Graded a flashcard (any grade), or got a quiz card right | 1 per card per day |

- **Daily goal:** 20, 50 or 100 XP (default 50, about three problems), picked on the Progress
  page.
- **Streak:** days in a row with any XP. Every 7 days in a row earns a streak freeze (hold up to
  2); a missed day uses one automatically.
- **Levels:** level 2 at 100 XP, 3 at 300, 4 at 600, 5 at 1,000 (level n starts at
  50 × n × (n − 1)).
- **Where it shows:** "+20 XP" with its breakdown under a Correct verdict, XP on test results
  and at the end of a flashcard session, today's XP in the top bar, a Today line on the home
  page, "3 of 12 solved" on every chapter, and a **Progress** page (`/progress`) with the goal,
  streak, a 12-week calendar, level, chapters, milestones and recent XP.
- **How it's stored:** the browser keeps a log of what happened (solved, solution opened, test
  submitted, card graded); XP is recomputed from it (`frontend/src/lib/xpRules.ts`), so every
  device that shares the log gets the same XP. Work from before XP existed counts too, once:
  submitted tests and concept or notes flashcard reviews with their real dates (quiz answers
  included, right or wrong), and problems already solved as a flat 10 XP each (a ProofLab-made
  version counts under its book problem). Problem flashcards aren't backfilled: their grades
  are stored like practice checks, so they can't be told apart. The log syncs
  to the SQLite progress database like the rest of your progress; on the live Vercel site, which
  has no database, XP stays in each browser.

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

Needs [uv](https://docs.astral.sh/uv/) (`brew install uv`) and Node.js 20+ (the website's unit
tests need Node 22.18+ or 24, which run TypeScript directly). Use two terminals.

**1. Backend** (the checker, port 8000):

```bash
cd backend
uv sync
```

```bash
uv run uvicorn prooflab.main:create_app --factory --reload --reload-dir src --app-dir src
```

http://localhost:8000/docs has the interactive API docs.

**2. Website** (port 3000):

```bash
cd frontend
npm install
```

```bash
npm run dev
```

Then open http://localhost:3000. The website reads the backend's address from
`PROOFLAB_API_URL` (default `http://localhost:8000`; see `frontend/.env.example`). Drafts and
revealed hints stay in your browser; your progress (flashcard reviews, notes decks, test
results, best verdicts, XP and streaks) is also saved in a SQLite file on the Mac
(`PROOFLAB_DB`), so your phone and laptop share it.

Run the tests. In the backend terminal:

```bash
uv run pytest
```

In the frontend terminal (the website's XP rules):

```bash
npm test
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

## Live on Vercel

- Website: https://prooflab-ruby.vercel.app
- Checker API: https://prooflab-api.vercel.app (try `/health`)

The website and the checker deploy to Vercel from `main` (two projects, `frontend/` and
`backend/`; see `SPEC.md` §18). The hosted copy has no progress database (progress stays in
each browser) and reads only text files; run it locally for photo and PDF scanning and for
progress shared between your devices.

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
| `PROOFLAB_DB` | `~/Library/Application Support/ProofLab/prooflab.sqlite3` (Docker: `/data/prooflab.sqlite3`) | SQLite file for your progress (reviews, decks, test results, XP), shared by every device that opens the site |

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
| GET / POST | `/store` | your saved progress in SQLite, XP activity included; browsers sync with it (`SPEC.md` §17) |

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
├── frontend/        Next.js website (see frontend/README.md)
│   └── src/lib/xpRules.ts   XP, streak and level rules (SPEC §19), tested by `npm test`
└── backend/
    ├── src/prooflab/
    │   ├── main.py              app factory + settings
    │   ├── practice.py          practice-test algorithm (SPEC §13)
    │   ├── quiz.py              multiple-choice questions (SPEC §13.2)
    │   ├── variants.py          ProofLab-made versions with new numbers (SPEC §13.3)
    │   ├── cards.py, notes.py   flashcards and cards from notes (SPEC §15)
    │   ├── store.py             progress database, SQLite (SPEC §17)
    │   ├── reader.py            photos/PDFs/documents → text (SPEC §14)
    │   ├── api/                 routes.py, schemas.py
    │   ├── engine/
    │   │   ├── algebra.py       safe parser, equivalence, sets, solving
    │   │   ├── checker.py       kind registry, verdict rules, isolated worker
    │   │   ├── hints.py         hint catalog
    │   │   ├── models.py        Problem, Step, Verdict, Reference, Review
    │   │   └── topics/<course>/<topic>.py
    │   └── content/             references.json, courses.json, problems/**.json, cards/*.json
    └── tests/                   engine/, api/, test_content.py
```
