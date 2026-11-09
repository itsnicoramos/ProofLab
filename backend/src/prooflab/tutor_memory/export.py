"""``LEARNING.md``: a readable view of the tutor memory. Postgres stays the source of truth;
edits to the file are never read back."""

from __future__ import annotations

from typing import Any

STATUS_LABELS = {"skip": "Skip", "review": "Review", "do": "Do", "done": "Done", None: "Not set"}


def _cell(text: object) -> str:
    return str(text if text is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def _day(stamp: str | None) -> str:
    return stamp[:10] if stamp else ""


def render(
    show: dict[str, Any],
    history: dict[str, Any],
    chapters: dict[int, dict[str, Any]],
    heading: str = "My Book of Proof path",
) -> str:
    """``chapters`` maps a chapter number to its lesson summary (title, minutes). ``heading``
    names the course's path."""
    plan = show["plan"]
    out = [
        f"# {heading}",
        "",
        "<!-- Written by `prooflab-tutor memory export` from your tutor memory in Postgres.",
        "     Edits here are not read back: ask the tutor to change your plan instead. -->",
        "",
        "## Why I'm learning",
        "",
    ]
    if plan is None:
        out += ["No plan yet. Start one with `/tutor start`.", ""]
    else:
        out.append(plan["mission"])
        if plan.get("goal"):
            out += ["", f"Goal: {plan['goal']}"]
        out.append("")
        out += ["## Placement", ""]
        placement = plan.get("placement") or {}
        out.append(f"- Date: {_day(plan['created_at'])}")
        if "score" in placement and "total" in placement:
            out.append(f"- Score: {placement['score']}/{placement['total']}")
        elif placement.get("self_selected"):
            out.append("- Score: self-selected")
        if plan.get("entry_chapter"):
            n = plan["entry_chapter"]
            out.append(f"- Entry point: Chapter {n}: {chapters.get(n, {}).get('title', '')}")
        if plan.get("pace"):
            out.append(f"- Pace: {plan['pace']}")
        if plan.get("exam_date"):
            out.append(f"- Exam: {plan['exam_date']}")
        out.append("")

    out += ["## Path", "", "| Chapter | Title | Status | Est. hours |", "|---|---|---|---|"]
    for row in show["chapters"]:
        n = row["chapter"]
        meta = chapters.get(n, {})
        hours = f"{meta['minutes'] / 60:.1f}" if meta.get("minutes") else ""
        out.append(
            f"| {n} | {_cell(meta.get('title', ''))} | {STATUS_LABELS[row['status']]} | {hours} |"
        )
    out.append("")

    out += ["## Progress log", ""]
    sessions = history["sessions"]
    if sessions:
        out += ["| Date | Mode | Chapter | Checked correct | Note |", "|---|---|---|---|---|"]
        for s in sessions:
            correct = f"{s['correct']} of {s['checked']}" if s["checked"] else ""
            out.append(
                f"| {_day(s['started_at'])} | {s['mode']} | {s['chapter'] or ''} | {correct}"
                f" | {_cell(s['summary'])} |"
            )
    else:
        out.append("Nothing logged yet.")
    out.append("")

    out += ["## Solved (marked Correct by ProofLab's checker)", ""]
    if history["solved"]:
        for p in history["solved"]:
            first = ", first try" if p["first_try"] else ""
            out.append(f"- `{p['problem_id']}` ({_day(p['first_correct'])}{first})")
    else:
        out.append("None yet.")
    out.append("")

    out += ["## Quizzes", ""]
    finished = [q for q in history["quizzes"] if q["finished_at"]]
    if finished:
        for q in finished:
            chapters_text = ", ".join(str(c) for c in q["chapters"]) or "mixed"
            out.append(
                f"- {_day(q['finished_at'])}: {q['kind']} (chapters {chapters_text}):"
                f" {q['score']}/{q['total']}"
            )
    else:
        out.append("None yet.")
    out.append("")

    out += ["## Review queue", ""]
    if show["open_review"]:
        for r in show["open_review"]:
            ids = ", ".join(f"`{i}`" for i in r["problem_ids"])
            where = f"Chapter {r['chapter']}: " if r["chapter"] else ""
            out.append(f"- {where}{r['idea']}" + (f" ({ids})" if ids else ""))
    else:
        out.append("Empty.")
    out.append("")

    out += ["## What the tutor remembers", ""]
    if show["notes"]:
        for note in show["notes"]:
            where = f" (chapter {note['chapter']})" if note["chapter"] else ""
            out.append(f"- {note['kind']}{where}: {note['text']}")
    else:
        out.append("Nothing yet.")
    out.append("")
    return "\n".join(out)
