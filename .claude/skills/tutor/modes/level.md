# Mode: level (placement)

Ten multiple-choice questions, two per area, built from real *Book of Proof* exercises and
graded by ProofLab's checker. No stakes: it only picks a starting chapter.

## 1. Build it

1. Pick a fresh seed S.
2. Run `tutor memory quiz start --kind placement --total 10 --seed S` and keep `quiz_id`.
3. Run `tutor quiz --placement --seed S`. Keep the output to yourself; it has no answers in it.

Each question has:
- `area` and `chapter`;
- `problem.prompt`;
- `choice`. A `"format": "answer"` question asks "which is the answer". A `"format": "spot"`
  question shows an attempt in `choice.steps` and asks where it first goes wrong.

## 2. Ask, one at a time

- Show the prompt in plain text, then the stem.
- For a `spot` question, list the steps, numbered.
- List the choices as `a)`, `b)` and so on, using each choice's `text` or `latex`.
- End with `Reply with one letter.` Give no hints and no reactions that leak the answer.

Grade each answer as soon as it comes in:

```bash
uv run --project backend --extra tutor prooflab-tutor answer <problem.id> --seed <choice.seed> --format <choice.format> --choice <letter> --record --quiz <quiz_id>
```

Reply in one line: "ProofLab's checker: right." or "ProofLab's checker: not this one." Add the
`explanation` if there is one. Don't teach yet; that comes in the lessons. "I don't know" is a
fine answer: record nothing for it and move on.

## 3. Score it

Run `tutor memory quiz finish <quiz_id>`. Then work out each area's score (0, 1 or 2) from the
answers you graded, and turn it into chapter statuses:

| Area | Chapters |
|---|---|
| Sets | 1 |
| Logic | 2 |
| Counting | 3 |
| Direct and contrapositive proof | 4, 5 |
| Contradiction and induction | 6, 10 |

- An area score of 2 makes its chapters `done`. A score of 1 makes them `review`. A score of
  0 makes them `do`.
- Chapters 7, 8 and 9 sit between the areas. They are `do` unless the learner scored 2 in both
  of the last two areas; then they are `review`.
- Chapters 11 to 14 are `do`.
- The entry chapter is the first one that isn't `done`.

Save it with `tutor memory plan set` (`placement`, `chapters`, `entry_chapter`). When this
mode was called from `start`, return there for the hand-off. Otherwise show the new path in
one short table and offer `/tutor next`.
