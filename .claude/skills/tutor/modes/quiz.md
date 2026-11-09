# Mode: quiz (chapter checks and mock tests)

Every score comes from the checker. Memory computes the score itself from the answers the CLI
recorded, never from a number you send.

## 1. Build it

- **Chapter check.** Pick a fresh seed S, then run:
  - `tutor memory quiz start --kind chapter --chapters N --total K --seed S` (K is 3 to 8);
  - `tutor quiz --chapter N --count K --seed S`.
- **Mock midterm, final or quiz.** Ask which chapters. A midterm usually covers 1 to 6, a
  final 1 to 10.
  - Run `tutor test --kind midterm --chapters 1-6 --seed S`. The default style is `mixed`.
    Add `--variants` only if they want new-number versions, and say which questions are
    versions.
  - Then run `tutor memory quiz start --kind midterm --chapters 1-6 --total <number of questions> --seed S`.
  - Tell them `suggested_minutes` and ask whether they want to be timed.
  - If `skipped_chapters` is present, say those chapters have no checked problems yet.

Keep the output to yourself. It holds no answer keys, so never guess one either.

## 2. Ask

Go through `questions` in order.

- **`"format": "choice"`.**
  - Show the prompt in plain text, the `choice.stem`, the attempt's steps if it's a spot
    question, and the lettered choices.
  - End with `Reply with one letter.`
  - Grade the answer with `tutor answer <problem.id> --seed <choice.seed> --format <choice.format> --choice <letter> --record --quiz <quiz_id>`.
- **`"format": "written"`.**
  - Show the prompt and its `answer_format` (from `tutor show <id>`).
  - They write their work; you translate it into steps and confirm.
  - Check it once with `tutor check <id> --record --quiz <quiz_id> --session <session_id>`.
  - It's a test, so give no hints and no second tries.

**During a chapter check,** give each result right away: one line, then the explanation.
**During a mock test,** hold every result until the end, like a real exam. Collect their
answers, grade them all, then report.

## 3. Score and plan

1. Run `tutor memory quiz finish <quiz_id>`. It returns `score`, `total`, `percent`, `missed`
   and `unanswered`.
2. Report:
   - the score;
   - which chapters the misses came from;
   - for each miss, one line on the idea behind it. Use the `explanation` from `answer` or the
     flagged step from `check`.
3. For each missed idea, run `tutor memory review add --chapter N --idea "..." --problems <ids>`.
4. Set any chapter where they scored under 70% to `review` with `tutor memory chapter N review`.
5. Offer a next step: practise the review queue (`modes/practice.md`), or retake later with a
   new seed.

Finish the session as described in `SKILL.md`, and run `tutor memory export`.
