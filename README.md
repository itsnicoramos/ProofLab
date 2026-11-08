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
- **Scan your work.** Photograph handwriting or pick a photo, PDF or Word document; ProofLab
  reads it on your Mac (Apple's on-device text recognizer), you fix any misreads, and the lines
  become steps. Reading never decides right or wrong. See `SPEC.md` §14.
- **Two parts:** a Python/FastAPI backend that does all the checking (`backend/`) and a
  Next.js website you study in (`frontend/`).

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

Needs [uv](https://docs.astral.sh/uv/) (`brew install uv`) and Node.js 20+. Use two terminals.

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
results, best verdicts) is also saved in a SQLite file on the Mac (`PROOFLAB_DB`), so your phone
and laptop share it.

Run the tests:

```bash
uv run pytest
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
docker run --rm -p 8000:8000 prooflab
```

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
| `PROOFLAB_DB` | `~/Library/Application Support/ProofLab/prooflab.sqlite3` | SQLite file for your progress (reviews, decks, test results), shared by every device that opens the site |

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
| GET / POST | `/store` | your saved progress in SQLite; browsers sync with it (`SPEC.md` §17) |

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
