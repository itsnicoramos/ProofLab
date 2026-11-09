# Mode: practice (exercises, graded by ProofLab's checker)

Use this for "practise chapter N", "give me a problem", or "check my proof of <id>". It's also
the inner loop of `modes/learn.md`.

## 1. Choose the exercise

Choose in this order:
1. an id the learner named;
2. an `open_review` item for this chapter;
3. the next id in the lesson note's **Practice route** that isn't in `solved`;
4. the next unsolved id from `tutor problems --chapter N`, easiest first.

If a chapter has no problems (11 to 14), switch to the feedback-only exercise described in
`modes/learn.md` step 3.

Run `tutor show <id>`. Present:
- the title and the citation ("Book of Proof, Chapter 4 exercises, #1");
- the prompt, rewritten from `$...$` into plain text;
- in one line, what to write (`answer_format`).

Don't show `syntax_help` unless they ask how to type something. If they asked for new numbers,
use `tutor variant <id> --seed S`, and say plainly that it is "a ProofLab-made version, not a
book exercise". `check` accepts its id like any other.

## 2. Let them work

Ask them to write their work in their own words, or straight in ProofLab steps if they know
the syntax. Wait. If they ask for help before trying, go to step 4 (hints); don't give the
first move away.

## 3. Check it

1. **Translate.** Turn their work into `{"steps": [{"kind": ..., "content": ...}], "answer": ...}`.
   - Read the problem's `syntax_help` and the lesson note's "Typing it into ProofLab" first.
   - Use exactly the step kinds the problem allows, in the shape each kind expects. For
     example, an `expr` step holds an expression (`x^2`, then `4a^2` as the next step), not an
     equation like `x^2 = 4a^2`.
   - Keep their expressions as written. If a line is ambiguous, ask instead of choosing.
2. **Confirm.** Show the numbered steps: "Here's how I'll enter your work. Send it to the
   checker?"
3. **Check.** Run `tutor check <id> --hints-shown <authored hints shown so far> --record --session <session_id>`
   with the JSON on stdin.
4. **Read the verdict** (`verdict.status`, `verdict.steps[]`, `verdict.answer`,
   `verdict.hints[]`):
   - **`correct`.** Say so, crediting the checker. Mention first try if `first_try` is true
     and no hints were shown. If useful, add one line on what made it work. Then offer the
     next exercise.
   - **`incorrect` or `partial`.** Find the first step whose `status` is `error`; for
     `partial`, use the last message. Quote that step back to them, and explain its `message`
     in plain words. The `code` tells you which "Common mistakes" entry in the lesson note
     applies. Then ask them to try again (rule 4). Don't fix the step for them.
   - **`invalid`, or `"counted": false`.** ProofLab couldn't read the input: a
     `PARSE_ERROR`, `NOT_AN_EXPRESSION`, `UNKNOWN_STEP_KIND` or another format code. This is
     about typing, not math, and the CLI doesn't count it as an attempt.
     - If the slip was in your translation, say so and fix only the format. Show the
       corrected steps and check again.
     - If it was in what the learner typed, show them the syntax.
   - **Warnings or `unchecked` steps** don't count against them. Mention them only if they
     matter.

## 4. Hints, in this order

1. Ask a question that points at the flagged step.
2. If they're still stuck, give the next authored hint. A wrong verdict carries it as the
   `AUTHORED_HINT` entry in `verdict.hints`; otherwise use `tutor hint <id> N`. Add one to
   your hints-shown count.
3. When the authored hints run out, give one hint in your own words, grounded in the lesson
   note.
4. Give the solution only when they say they give up.
   - "Just give me the answer" while hints remain gets the next hint, plus one question:
     "Want to try with that, or give up and see the solution?" Show the solution on "I give
     up" or a second request.
   - Then run `tutor solution <id>`, walk through it briefly, and offer the same idea with new
     numbers (`tutor variant <id> --seed S`).
   Before that, run `tutor memory review add --chapter N --idea - --problems <id>`, with the
   idea they missed on stdin (`SKILL.md`, "Text goes in on stdin").

## 5. After each exercise

- Clear any `open_review` item this exercise settles: `tutor memory review clear <review_id>`.
- If they repeat the same slip (the same code twice), add a `memory note` of kind
  `misconception`.
- Offer the next exercise, or stop. Close the session as described in `SKILL.md` under
  "Every session".
