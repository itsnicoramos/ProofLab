# ProofLab design direction

Read by the frontend (and by antislop) as design data: identity, palette, type, mood, dials.

Dial: ENERGY 1 / RHYTHM 2 / MOTION 1

## Identity

- **What it is:** a study desk for checking math one step at a time. One student, many
  courses (MATH 123 with *Book of Proof*, then precalculus and Calculus 1–4). For now only
  the Proof course is shown; the others are hidden, not removed (`COURSE_ORDER` in
  `frontend/src/lib/labels.ts`).
- **Personality:** calm, precise, honest. It never hypes and never pretends. It points at the
  exact step that went wrong, and it acknowledges earned XP plainly ("+20 XP"): no confetti,
  sounds, mascots or emoji (SPEC §19).
- **The math is the star.** Every screen's focal point is mathematics typeset with KaTeX:
  the problem's own statement, or the student's own steps. Chrome stays quiet around it.

## Browsing

- Home and course pages are **shelves**: one row per course topic (for MATH 123, per book
  chapter), scrolled sideways, like a streaming app's rows. This is the one borrowed
  pattern, borrowed for its job (lots of items, browse by category), not for its look.
- A card's "artwork" is the problem's actual statement, typeset. No illustrations, no icons.
- A "Continue" shelf shows problems this browser has started but not solved. It's only real
  local progress; nothing is invented.

## Navigation

- One sticky bar, always visible, solid (no blur). From tablet width up it is one row: the Σ
  mark and name, then every course as a direct link (current course marked), then
  **Flashcards**, **Tests**, today's XP ("35 / 50 XP", a link to Progress; the streak joins it
  from tablet width, `md`, 768 px) and **Search**. "Typing math" lives in the footer (and on every
  problem page).
- On a phone (below 640 px) the bar keeps the Σ mark, Search and a hamburger button with the
  word **Menu** next to the icon (never a bare icon). It opens a solid side sheet from the right:
  Practice, Flashcards, Tests, Progress (with today's XP), then every course, then Typing
  math, the current page on the accent tint. No bottom bar, so nothing sits over the page.
- Search is a magnifier button ("Search" plus a `/` key hint from tablet width up). Search is a
  modal dialog, top-aligned, solid surface: the one element allowed a shadow, because it sits
  above the page. `/` or ⌘/Ctrl + K opens it; arrows move, Enter opens, Esc closes.
- Step editor: "Scan work" sits beside "+ Add step" (camera outline icon, same quiet bordered
  style). It opens a modal: Take a photo (accent, the one primary action), Choose a file, a
  dashed drop zone, then an editable review of the text before anything reaches the steps.
- Test pages: one solid sticky bar under the navbar while a test is open (answered count, time
  so far, a jump to Finish). Results use the serif for the score, like a marked paper.
  Multiple-choice questions are full-width rows (48 px) with a lettered circle; after grading
  the right row turns green, a wrong pick red, and the explanation and worked solution follow.
  ProofLab-made versions carry a small bordered label "Made by ProofLab, not from the book".
- Flashcards: one card at a time on the surface colour, the term in the serif, "Show the
  answer" as a full-width button, then four grade buttons (Again, Hard, Good, Easy) each
  showing when the card comes back. Good is outlined in the accent as the usual answer.

## XP and progress (SPEC §19)

- XP is text, never a badge or glow: "+20 XP" in the semibold UI face under a Correct verdict,
  its breakdown in muted text beside it. A wrong answer gets a plain bordered **Try again**
  button and "No XP yet". The one goal line ("Daily goal done: 50 XP today.") sits in the same
  live region as the verdict in practice; on the flashcard, quiz and test-result screens focus
  moves to the result heading and the line follows it.
- Progress bars and the 12-week calendar use **ink**, not the accent or the status colours:
  line (no XP), ink at 35% (some), solid ink (goal met), a dashed outline (a freeze covered
  the day). Today's square gets the accent ring ("you are here"). Status green appears only
  where it already means "solved": "Chapter complete", "3 of 12 solved", and today's XP in the
  top bar once the goal is met.
- The Progress page is one column of the usual bordered surface cards (Today, Streak, Level,
  Chapters, Milestones, Recent XP); big numbers use the serif, like a marked paper.

## Palette (tokens in `frontend/src/app/globals.css`)

| Role | Light | Dark | Why |
|---|---|---|---|
| Paper (background) | `#f6f6f3` | `#111210` | warm off-white reads like a notebook page, easy on long sessions |
| Ink (text) | `#1b1c1a` | `#ecece8` | near-black and near-white keep contrast high for small math |
| Accent (one) | `#3446d4` | `#8f9cff` | a single ink-blue for the primary action, focus and "you are here" only |
| Status | green / amber / red | lighter tints | functional only: step verdicts. Never decoration |

Theme follows the system setting: the product has no reason to force light or dark.

## Typography

- **Headings and problem titles: Source Serif 4.** A textbook voice that sits naturally next
  to KaTeX's Computer Modern–style math, so titles and formulas read as one page.
- **UI text: Geist Sans.** Small, legible, and neutral, so controls recede behind the math.
- **Math input: Geist Mono.** Typed expressions need fixed-width characters so `(`, `^` and
  `*` line up and typos stand out. Never used as decoration.

## Motifs

- The **Σ mark**: summation, the student adding up steps toward a result.
- **Math as artwork**: problem statements typeset on cards instead of images.

## Motion

Hover and focus states only. Shelf arrows jump a page instantly (scroll-snap lines up the
next card). Nothing loops, pulses or animates on load; loading skeletons stop pulsing under
reduced motion.
