"""Multiple-choice questions built from the problem bank (SPEC §13.2), by rules, no AI.

Two formats:

- **answer**: "Which of these is the answer?" The right choice is the problem's own key. The
  wrong ones come from the problem's authored common mistakes first, then from small changes to
  the key (a number off by one, a sign flipped, one truth value flipped, an element dropped, P
  swapped for C), then from answers to sibling problems of the same kind. **Every wrong choice
  is run through the problem's checker and kept only if the checker marks it incorrect**, so a
  distractor can never secretly be right.
- **spot**: "Where does this attempt first go wrong?" The attempt is one of the problem's own
  worked examples (already tested), the choices are its step numbers plus "No mistake", and the
  checker's verdict on the attempt gives the right choice and the explanation.

The same (problem, seed) always gives the same question, so a question can be graded later by
rebuilding it from its id. Nothing about the right choice is sent to the browser until grading.
"""

from __future__ import annotations

import math
import random
import re
import threading
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from prooflab.engine.checker import get_handler
from prooflab.engine.models import (
    Problem,
    StepStatus,
    Submission,
    Verdict,
    VerdictStatus,
)

Format = Literal["answer", "spot"]
Runner = Callable[[Problem, Submission], Verdict]

KEYS = "abcde"
MAX_TRIES = 12
NO_MISTAKE = "No mistake: the attempt is correct"


@dataclass(frozen=True)
class Choice:
    key: str
    latex: str | None = None
    text: str | None = None
    explanation: str | None = None  # shown after grading when this choice was picked


@dataclass(frozen=True)
class SpotStep:
    kind: str
    content: str
    latex: str | None


@dataclass(frozen=True)
class ChoiceQuestion:
    problem_id: str
    seed: int
    format: Format
    stem: str
    choices: list[Choice]
    correct: str
    explanation: str | None = None  # why the right choice is right
    steps: list[SpotStep] = field(default_factory=list)
    attempt_answer: str | None = None


# --------------------------------------------------------------------------- distractors

_NUMBER = re.compile(r"(?<![\w.^])(\d+)(?![\w.])")
_SIGN = re.compile(r" ([+-]) ")


def _bump(n: int, rng: random.Random) -> list[int]:
    options = [n + 1, n - 1, 2 * n, n + 2] if n > 1 else [n + 1, n + 2, 2]
    rng.shuffle(options)
    return [m for m in options if m >= 0 and m != n]


def _number_edits(answer: str, rng: random.Random) -> list[str]:
    spots = list(_NUMBER.finditer(answer))
    rng.shuffle(spots)
    out: list[str] = []
    for m in spots[:3]:
        n = int(m[1])
        if n > 10**6:
            continue
        for new in _bump(n, rng)[:2]:
            out.append(answer[: m.start()] + str(new) + answer[m.end() :])
    return out


def _sign_edits(answer: str, rng: random.Random) -> list[str]:
    spots = list(_SIGN.finditer(answer))
    rng.shuffle(spots)
    out = []
    for m in spots[:2]:
        flipped = "-" if m[1] == "+" else "+"
        out.append(f"{answer[: m.start()]} {flipped} {answer[m.end() :]}")
    if answer.startswith("-") and not answer.startswith("--"):
        out.append(answer[1:].lstrip())
    elif re.match(r"^[\w(]", answer) and "=" not in answer and "," not in answer:
        out.append(f"-({answer})" if _SIGN.search(answer) else f"-{answer}")
    return out


def _function_swaps(answer: str) -> list[str]:
    out = []
    for a, b in (("sin", "cos"), ("cos", "sin"), ("e^", "e^-"), ("ln", "log")):
        if a in answer:
            out.append(answer.replace(a, b, 1))
    return out


def _truth_table_edits(answer: str, rng: random.Random) -> list[str]:
    cells = answer.split()
    if not cells or any(c not in {"T", "F"} for c in cells):
        return []
    flip = {"T": "F", "F": "T"}
    out = []
    order = list(range(len(cells)))
    rng.shuffle(order)
    for i in order[:3]:
        copy = list(cells)
        copy[i] = flip[copy[i]]
        out.append(" ".join(copy))
    if len(cells) >= 2:
        i, j = order[0], order[1]
        copy = list(cells)
        copy[i], copy[j] = flip[copy[i]], flip[copy[j]]
        out.append(" ".join(copy))
    out.append(" ".join(flip[c] for c in cells))
    return out


def _split_top(inner: str) -> list[str]:
    parts, depth, buf = [], 0, ""
    for ch in inner:
        if ch in "({[<":
            depth += 1
        elif ch in ")}]>":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts


def _set_edits(answer: str, rng: random.Random) -> list[str]:
    s = answer.strip()
    if not (s.startswith("{") and s.endswith("}")):
        return []
    items = _split_top(s[1:-1])
    out: list[str] = []
    if len(items) >= 2:
        out.append("{" + ", ".join(items[:-1]) + "}")
        out.append("{" + ", ".join(items[1:]) + "}")
        k = rng.randrange(len(items))
        out.append("{" + ", ".join(items[:k] + items[k + 1 :]) + "}")
    ints = [int(x) for x in items if re.fullmatch(r"-?\d+", x)]
    if ints and len(ints) == len(items):
        out.append("{" + ", ".join(items + [str(max(ints) + 1)]) + "}")
        out.append("{" + ", ".join([str(min(ints) - 1)] + items) + "}")
    return out


_PRODUCT = re.compile(r"^\s*(\d+)(?:\s*\*\s*(\d+))+\s*$")
_BINOM = re.compile(r"(?:binom|C)\(\s*(\d+)\s*,\s*(\d+)\s*\)")
_PERM = re.compile(r"P\(\s*(\d+)\s*,\s*(\d+)\s*\)")
_POWER = re.compile(r"^\s*(\d+)\s*\^\s*(\d+)\s*$")


def _count_edits(answer: str) -> list[str]:
    """The classic counting slips: order vs. no order, repetition vs. none, a factor dropped."""
    out: list[str] = []
    if _PRODUCT.match(answer):
        factors = [int(x) for x in re.findall(r"\d+", answer)]
        out.append(f"{factors[0]}^{len(factors)}")  # repetition allowed by mistake
        out.append("*".join(str(f) for f in factors[1:]))  # a factor dropped
        if len(factors) <= 6:
            out.append(f"{'*'.join(map(str, factors))}/{math.factorial(len(factors))}")
    if m := _POWER.match(answer):
        n, k = int(m[1]), int(m[2])
        if k <= n <= 60:
            out.append("*".join(str(n - i) for i in range(k)))  # forgot repetition is allowed
            out.append(f"{k}^{n}")
    for m in _BINOM.finditer(answer):
        out.append(answer.replace(m[0], f"P({m[1]}, {m[2]})", 1))
    for m in _PERM.finditer(answer):
        out.append(answer.replace(m[0], f"C({m[1]}, {m[2]})", 1))
    return out


_WORD_SWAPS = {
    "diverges": ["converges", "converges absolutely"],
    "converges": ["diverges"],
    "converges absolutely": ["converges conditionally", "diverges"],
    "converges conditionally": ["converges absolutely", "diverges"],
    "dne": ["0", "1", "oo"],
    "not conservative": [],
}


def candidates(problem: Problem, rng: random.Random, siblings: Sequence[Problem]) -> list[str]:
    """Possible wrong answers, most plausible first. Unverified: the checker decides."""
    key = problem.answer.strip()
    out: list[str] = [m.answer for m in problem.mistakes]
    low = key.lower()
    if low in _WORD_SWAPS:
        out += _WORD_SWAPS[low]
    if problem.kind == "truth_table":
        out += _truth_table_edits(key, rng)
    elif problem.kind == "finite_set":
        out += _set_edits(key, rng)
    elif problem.kind == "count":
        out += _count_edits(key)
        out += _number_edits(key, rng)
    else:
        out += _sign_edits(key, rng) + _number_edits(key, rng) + _function_swaps(key)
    pool = [
        p.answer for p in siblings if p.id != problem.id and p.kind == problem.kind and p.answer
    ]
    rng.shuffle(pool)
    out += pool[:5]
    seen = {key}
    unique = []
    for c in out:
        c = c.strip()
        if c and c not in seen and len(c) <= 300:
            seen.add(c)
            unique.append(c)
    return unique


# --------------------------------------------------------------------------- builders


def answer_question(
    problem: Problem, seed: int, run: Runner, siblings: Sequence[Problem] = ()
) -> ChoiceQuestion | None:
    if not problem.answer.strip():
        return None
    rng = random.Random(f"{problem.id}|{seed}|answer")
    right = run(problem, Submission(answer=problem.answer))
    if right.answer is None or right.answer.status is not VerdictStatus.CORRECT:
        return None
    right_latex = right.answer.latex
    mistake_hints = {m.answer.strip(): m.hint for m in problem.mistakes}
    wrong: list[Choice] = []
    shown = {right_latex or problem.answer}
    for tries, cand in enumerate(candidates(problem, rng, siblings)):
        if len(wrong) == 3 or tries >= MAX_TRIES:
            break
        try:
            verdict = run(problem, Submission(answer=cand))
        except Exception:  # noqa: BLE001 - a candidate the checker can't take is just skipped
            continue
        ans = verdict.answer
        if ans is None or ans.status is not VerdictStatus.INCORRECT:
            continue
        label = ans.latex or cand
        if label in shown:
            continue
        shown.add(label)
        hint = mistake_hints.get(cand) or next(
            (h.message for h in verdict.hints if h.code != "KNOWN_MISTAKE"), None
        )
        wrong.append(
            Choice(
                key="",
                latex=ans.latex,
                text=None if ans.latex else cand,
                explanation=hint or ans.message or None,
            )
        )
    if len(wrong) < 2:
        return None
    correct = Choice(key="", latex=right_latex, text=None if right_latex else problem.answer)
    pool = [correct, *wrong]
    rng.shuffle(pool)
    choices = [
        Choice(key=KEYS[i], latex=c.latex, text=c.text, explanation=c.explanation)
        for i, c in enumerate(pool)
    ]
    return ChoiceQuestion(
        problem_id=problem.id,
        seed=seed,
        format="answer",
        stem="Which of these is the answer?",
        choices=choices,
        correct=KEYS[pool.index(correct)],
        explanation=right.answer.message or None,
    )


def spot_question(problem: Problem, seed: int, run: Runner) -> ChoiceQuestion | None:
    rng = random.Random(f"{problem.id}|{seed}|spot")
    wrong_ones = [
        e
        for e in problem.examples
        if e.expect.first_error is not None and 2 <= len(e.submission.steps) <= 8
    ]
    right_ones = [
        e
        for e in problem.examples
        if e.expect.status is VerdictStatus.CORRECT and 2 <= len(e.submission.steps) <= 8
    ]
    # Mostly flawed attempts (that's the skill), sometimes a correct one, so "No mistake" is real.
    pool = wrong_ones if wrong_ones and (not right_ones or rng.random() < 0.75) else right_ones
    if not pool:
        return None
    example = rng.choice(pool)
    verdict = run(problem, example.submission)
    steps = [
        SpotStep(kind=s.kind, content=s.content, latex=r.latex)
        for s, r in zip(example.submission.steps, verdict.steps, strict=False)
    ]
    first_bad = next((r.index for r in verdict.steps if r.status is StepStatus.ERROR), None)
    if example.expect.first_error is not None:
        if first_bad != example.expect.first_error:
            return None  # the attempt no longer behaves as authored; don't guess
        explanation = verdict.steps[first_bad].message
    else:
        if verdict.status is not VerdictStatus.CORRECT or first_bad is not None:
            return None
        explanation = "Every step follows from the one before, and the attempt is complete."

    n = len(steps)
    if n <= 4:
        shown = list(range(n))
    else:  # keep the choices short: the right step and three others, in order
        others = [i for i in range(n) if i != first_bad]
        rng.shuffle(others)
        keep = [first_bad] if first_bad is not None else []
        shown = sorted(keep + others[: 4 - len(keep)])
    choices = [Choice(key=KEYS[j], text=f"Step {i + 1}") for j, i in enumerate(shown)]
    choices.append(Choice(key=KEYS[len(shown)], text=NO_MISTAKE))
    correct = KEYS[shown.index(first_bad)] if first_bad is not None else KEYS[len(shown)]
    return ChoiceQuestion(
        problem_id=problem.id,
        seed=seed,
        format="spot",
        stem="Here is an attempt. Where does it first go wrong?",
        choices=choices,
        correct=correct,
        explanation=(
            f"Step {first_bad + 1}: {explanation}" if first_bad is not None else explanation
        ),
        steps=steps,
        attempt_answer=example.submission.answer,
    )


def has_answer(problem: Problem) -> bool:
    handler = get_handler(problem.kind)
    return bool(problem.answer.strip()) and handler.has_answer(problem, handler.params(problem))


_CACHE: OrderedDict[tuple[str, int, str], ChoiceQuestion | None] = OrderedDict()
_LOCK = threading.Lock()


def build_question(
    problem: Problem,
    seed: int,
    run: Runner,
    siblings: Sequence[Problem] = (),
    fmt: Format | None = None,
) -> ChoiceQuestion | None:
    """A multiple-choice question for ``problem``, or None if none can be made safely.

    ``fmt`` forces a format; otherwise problems with a final answer get "answer" and proofs get
    "spot", each falling back to the other.
    """
    key = (problem.id, seed, fmt or "")
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    if fmt == "answer":
        order: list[Format] = ["answer"]
    elif fmt == "spot":
        order = ["spot"]
    else:
        order = ["answer", "spot"] if has_answer(problem) else ["spot", "answer"]
    question = None
    for f in order:
        question = (
            answer_question(problem, seed, run, siblings)
            if f == "answer"
            else spot_question(problem, seed, run)
        )
        if question is not None:
            break
    with _LOCK:
        _CACHE[key] = question
        while len(_CACHE) > 1024:
            _CACHE.popitem(last=False)
    return question


def grade(question: ChoiceQuestion, choice: str) -> tuple[bool, str | None]:
    """Whether ``choice`` is right, and what to say about the choice that was picked."""
    if choice == question.correct:
        return True, question.explanation
    picked = next((c for c in question.choices if c.key == choice), None)
    return False, (picked.explanation if picked and picked.explanation else question.explanation)
