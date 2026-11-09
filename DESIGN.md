# ProofLab design direction

Read by the frontend (and by antislop) as design data: identity, palette, type, mood, dials.

Dial: ENERGY 1 / RHYTHM 2 / MOTION 1

## Identity

- **What it is:** one page that shows what a coding agent does when someone types `/tutor` in
  the ProofLab repo (SPEC §21). ProofLab itself is a study desk for checking math one step at a
  time; the page explains the tutor that brings that desk into the learner's own agent. The
  practice site that used to live here is in git history up to commit `0eb0d0f`.
- **Personality:** calm, precise, honest. It never hypes and never pretends. It says plainly
  which words were written for the page and which output is real, and the real output is the
  star: commands and their JSON, and the checker's verdicts.
- **The math is still the star.** In a verdict, each step is shown the way the checker read
  it, typeset with KaTeX. Chrome stays quiet around it.

## The page

One column, in this order. Each section has a serif heading over a hairline rule.

- **Hero:** the question the page answers ("What your agent does when you type `/tutor`"), one
  paragraph, then **Set it up** (accent, the one primary action) and **Watch a session**
  (bordered). No badge, no illustration, no stats strip.
- **How the pieces fit:** the diagram is plain bordered cards joined by labelled arrows (↓),
  each label naming both ends ("The agent runs every command through prooflab-tutor"), so it
  reads right at any width. It is one column on a phone; the skill and the CLI sit side by side
  from `sm`, and content, checker and memory from `md`. The checker card has the ink border
  instead of the hairline, because it is the only judge.
- **One session, step by step:** a transcript that grows one step at a time.
  - A solid sticky bar under the navbar holds **Back**, **Next** (accent), "Step 11 of 22" and
    **Show all** / **Start over**.
  - Each step has a muted "Step N" and who acts. The learner's typing is mono on the surface
    colour, the tutor's words are sans on the surface colour, and what the agent reads or runs
    sits on the quieter idle tint ("behind the scenes").
  - The current step gets the accent ring ("you are here").
  - A check's verdict is a bordered card. Per step: its kind in mono, the step typeset, then
    "Checks out" in status green or "Flagged" in status red with the message and hint code.
  - A command's output sits in closed `<details>`: the piped input, the selected exercise and
    lesson fields (the ones the tutor uses), the lesson's practice route, and the memory excerpt
    (`LEARNING.md` from its second section). Other commands show their full JSON. The capture
    file keeps every command's full output.
  - From `lg` up, a sticky side panel lists the seven pieces and marks the ones the current
    step uses with the accent ring and tint.
- **Seven rules it keeps:** bordered cards, two columns from `md`, the number in the serif like
  a marked paper, each with "See it in step N" (a link that opens the replay at that step).
- **Set it up:** first one card for someone who has never used a terminal. It says to ask any
  AI assistant they like to walk them through the setup, and holds a prompt in mono on the
  idle tint with its own **Copy** button. Then numbered cards with the command in mono on the
  idle tint and a bordered **Copy** button. "Which agents work" is three cards (never a wide table, so nothing scrolls
  sideways on a phone).

## Navigation

- One sticky bar, solid (no blur): the Σ mark and name, then from `md` the section links (How it
  works, Session, Rules, Set up), and **GitHub** as a bordered button. Below `md` the section
  links give way to a single **Set up** link. A one-page site needs no menu.
- The footer contains the MIT line and source link.
- Every link and button is at least 44 px tall, including the footer's and the rule links.

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
- **Typed text: Geist Mono.** What the learner types, the steps the tutor proposes, and every
  command and its output: fixed-width characters keep `(`, `^` and `*` lined up and show that
  this is literal input. Never used as decoration.

## Motifs

- The **Σ mark**: summation, the student adding up steps toward a result.
- **The real thing as artwork**: the page has no illustrations. Its visuals are the captured
  session itself, the checker's typeset verdicts and the diagram of the repo's own pieces.

## Motion

Hover and focus states only. Next reveals a step instantly and scrolls it into view without
animation; a rule link jumps straight to its step. Nothing loops, pulses or animates on load.
