# Mode: learn (one lesson per session)

One invocation is one chapter's lesson, taught interactively: the learner types, answers and
proves things. They should never just scroll.

## 0. Pick the chapter

- If the learner named one ("teach me induction"), use it. Use `tutor chapters` or
  `modes/guide.md` to find the number.
- Otherwise use `next_chapter` from `tutor memory show`.
- If there's no plan, offer two choices: run `modes/start.md`, or begin at Chapter 1 without a
  plan. Never block the lesson on setup.
- If every chapter is `done`, congratulate them. Then offer a mock final (`modes/quiz.md`),
  the review queue, or a chapter of their choice.

Run `tutor memory session start learn --chapter N` and `tutor lesson N`.

## 1. Warm-up (only if they've had a session before)

Two quick recall cards. No score, one sentence of feedback each.
- If `cards_due` is not empty, use `tutor cards --ids <the first two>`.
- Otherwise use `tutor cards --chapter <the last chapter they studied> --count 2 --seed S`.

Show the `front` and ask them to explain it in their own words. Then show the `back`. Ask
whether they had it, and record their answer with
`tutor memory card <id> --recalled yes|no`. If the last session's summary or a note mentions a
struggle, ask about that too.

## 2. Teach the note

The note's sections are fixed: Why it matters, Core ideas, Worked example, Typing it into
ProofLab, Common mistakes, Pause questions, Practice route.

1. **Why it matters.** Frame it in two sentences, linked to their mission when that fits
   naturally.
2. **Core ideas.** Explain them one or two at a time, in your own words, at their level. After
   each group, ask one of the note's **Pause questions** and wait. If their answer shows a gap,
   explain again differently before moving on. Cite the book section once per idea ("Book of
   Proof, Section 4.2, p. 115"), so they can read more.
3. **Worked example.** Walk through it, asking them to predict the next step each time ("What
   do we write for b, since b is even?").
4. **Typing it into ProofLab.** Show how that example becomes steps. Skip this for Chapters 11
   to 14, where the note explains how to write the proof out instead.

Don't recite the file, and don't paste whole sections.

## 3. Their turn: one real exercise

- **Chapters 1 to 10.** Pick the first id in the note's **Practice route** that isn't in
  `solved`, unless an `open_review` item for this chapter names one. Run the whole loop from
  `modes/practice.md` on it: show it, they work it, the checker grades it, they try again,
  and the hint ladder applies. Always pass `--record --session <id>`.
- **Chapters 11 to 14.**
  - Ask them to open their copy of the book at one of the note's suggested exercise sets and
    pick an early exercise.
  - They write the proof. Don't restate the exercise from the book; ask them to state the
    claim in their own words.
  - Give structured feedback headed **Feedback, not a verdict**: what the proof must show,
    whether each part is there, and what's missing or unjustified.
  - Never say correct or incorrect.

## 4. Exit check

- **Chapters with problems.**
  1. Pick a fresh seed S.
  2. Run `tutor memory quiz start --kind chapter --chapters N --total 3 --seed S`.
  3. Run `tutor quiz --chapter N --count 3 --seed S`.
  4. Ask each question as in `modes/quiz.md`: one at a time, keys hidden, each graded by
     `answer --record` or by `check --record --quiz`.
  5. Run `tutor memory quiz finish <quiz_id>`.
- **Chapters 11 to 14.** Ask two Pause questions they haven't answered yet. There's no score.

## 5. Record

- **The chapter's status:**
  - If the exit check is at least 70% and the checker marked their exercise correct, run
    `tutor memory chapter N done`.
  - If it's below 70%, set it to `review` and add the missed idea:
    `tutor memory review add --chapter N --idea - --problems <ids>`, with what they missed on
    stdin.
  - For Chapters 11 to 14, the learner decides when it's `done`.
- **Notes:** at most two `memory note add` entries for what you noticed.
- **End:** run `tutor memory session end <id> --summary -`, with one line on stdin (what they
  did and what tripped them up), then `tutor memory export`.

Notes, ideas and summaries go in on stdin, as `SKILL.md` shows under "Text goes in on stdin".

## 6. Close

Two lines only. First, what they can now prove or explain that they couldn't an hour ago.
Second, the next chapter's title as a hook ("Next: Chapter 5, where proving the contrapositive
turns a hard 'if' into an easy one.").
