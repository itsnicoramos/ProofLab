# Mode: start (onboarding)

Goal: a study plan in memory that every later session builds on. Keep it short. Three
questions and a placement quiz are all you need.

## 0. Is there already a plan?

`tutor memory show`. If `plan` is not null, don't redo onboarding. Summarize in two or three
lines: the mission, the entry chapter, what's done (chapter statuses and `stats`). Then offer
exactly three choices:

- **Resume.** Go to `modes/learn.md`.
- **Re-run placement.** Follow `modes/level.md`. It updates only the placement and the chapter
  statuses. The mission and the history stay.
- **Start over.** Ask for an explicit yes first. Then run `tutor memory plan archive`, which
  keeps the old plan and its history, and continue below.

If memory is unreachable (exit code 3), say so once and onboard anyway. Then show the plan at
the end so the learner can keep it, since nothing is saved.

In an empty course (`tutor chapters` says `"status": "empty"`), ask the three questions below,
skip placement, and save a plan with no `entry_chapter`, `placement` or `chapters`. Then
follow `modes/coach.md`.

## 1. Three questions

Use your host's question tool if it has one; otherwise list lettered options and wait.

1. **Why are you learning this?** Offer: taking MATH 123 now, getting ready for a proofs
   course, exam soon, curiosity. Keep their own words.
2. **How much time a week?** Offer about 2 hours, about 5 hours, about 10 hours, or as fast as
   possible. This sets the pace text only. It never cuts content.
3. **Is there an exam date?** Optional. If there is, note it.

Don't ask more. Placement measures what they know.

## 2. Placement

Offer the 10-question placement (`modes/level.md`, about 15 minutes), or a self-chosen start
("start me at chapter 6").

For a self-chosen start:
- chapters before it are `skip`;
- that chapter and every later one are `do`;
- placement is `{"self_selected": true}`.

## 3. Save the plan

Call `tutor memory plan set` with JSON on stdin:

```json
{
  "mission": "<their why, in their words>",
  "goal": "<optional: what they want to be able to do>",
  "pace": "~5 h/week",
  "exam_date": "2026-12-10",
  "entry_chapter": 4,
  "placement": {"score": 6, "total": 10, "areas": {"Sets": 2, "Logic": 1}},
  "chapters": {"1": "done", "2": "review", "3": "done", "4": "do", "5": "do"}
}
```

Leave `exam_date` out if there isn't one. Give all 14 chapters a status. Then run
`tutor memory export`.

## 4. Hand off

Three lines, nothing more:
- The entry chapter and the estimated hours for every `do` and `review` chapter. Add up
  `minutes` from `tutor chapters`.
- How to continue: `/tutor next` (or the host's form), which starts the first lesson and picks
  up from memory every time.
- How to jump: `/tutor guide <topic>` finds where any idea is taught.
