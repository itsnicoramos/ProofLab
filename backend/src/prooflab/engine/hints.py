"""Rule-based hints (SPEC §4.2).

Every hint has a stable UPPER_SNAKE ``code`` and a message template. Core codes are defined
here; topic modules register their own with :func:`register` at import time. Hints should
point at the problem without giving the answer away.
"""

from __future__ import annotations

import re

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_CATALOG: dict[str, str] = {}


def register(code: str, template: str) -> None:
    """Add a hint code. Re-registering the same code with the same text is a no-op."""
    if not _CODE_RE.fullmatch(code):
        raise ValueError(f"hint code {code!r} must be UPPER_SNAKE")
    existing = _CATALOG.get(code)
    if existing is not None and existing != template:
        raise ValueError(f"hint code {code!r} is already registered with different text")
    _CATALOG[code] = template


def register_many(templates: dict[str, str]) -> None:
    for code, template in templates.items():
        register(code, template)


def is_registered(code: str) -> bool:
    return code in _CATALOG


def catalog() -> dict[str, str]:
    return dict(_CATALOG)


def message(code: str, **params: object) -> str:
    template = _CATALOG.get(code)
    if template is None:
        raise KeyError(f"unknown hint code {code!r}")
    try:
        return template.format(**params)
    except (KeyError, IndexError, ValueError):
        return template


register_many(
    {
        # input problems
        "PARSE_ERROR": "ProofLab couldn't read that: {detail}",
        "EMPTY": "This is empty.",
        "UNKNOWN_NAME": "{detail}",
        "NOT_AN_EXPRESSION": "Enter an expression here, not an equation or inequality.",
        "NOT_AN_EQUATION": "Write an equation with exactly one '='.",
        "TOO_LONG": "That input is too long or too deeply nested for ProofLab to check.",
        "TOO_LARGE": "That number is too large for ProofLab to check.",
        "DIVISION_BY_ZERO": "Division by zero.",
        "WRONG_DIMENSION": "That has the wrong number of components.",
        "BAD_SOLUTION_LIST": "Write each solution as x = value, separated by 'or' or commas.",
        "BAD_INTERVAL": "Interval endpoints must be numbers.",
        "BAD_SET": "Write the set in interval notation, like (-oo, 2) U (2, oo), or as an "
        "inequality.",
        "UNKNOWN_STEP_KIND": "Step {step_number} is a '{step_kind}' step, which this problem "
        "doesn't use.",
        "EMPTY_SUBMISSION": "Nothing to check yet. Enter your steps and a final answer.",
        # step-level
        "STEP_OK": "This step checks out.",
        "NOT_EQUIVALENT": "This step doesn't follow from the one before it: the two aren't equal.",
        "STEP_NOT_EQUAL_TO_TARGET": "This step isn't equal to what you're working on.",
        "UNVERIFIED_STEP": "ProofLab couldn't verify this step automatically, so it doesn't count "
        "for or against you.",
        "STEP_ERRORS": "Your final answer is right, but step {step_number} has a problem. "
        "Check the work, not just the answer.",
        "NO_ANSWER": "Your steps check out so far. Finish by entering a final answer.",
        # answer-level diagnostics
        "CORRECT": "Correct.",
        "WRONG": "Not quite. That isn't the correct answer.",
        "UNVERIFIED": "ProofLab couldn't verify this answer automatically. Try writing it in a "
        "simpler form.",
        "SIGN_ERROR": "You're off by a sign. Look for a minus sign that was dropped or "
        "distributed incorrectly.",
        "CONSTANT_FACTOR": "Your answer is {factor} times the correct one. Look for a missing or "
        "extra constant factor.",
        "ADDITIVE_CONSTANT": "Your answer is off by a constant ({shift}).",
        "INEXACT": "That looks like a decimal approximation. Give an exact value (fractions, "
        "radicals, π, e, ...).",
        "KNOWN_MISTAKE": "{hint}",
        "AUTHORED_HINT": "Hint {level}: {hint}",
        # engine
        "TIMEOUT": "This took too long to check. Try simplifying your input.",
        "ENGINE_ERROR": "ProofLab hit an internal error while checking this. It isn't your "
        "fault; please report it.",
        "BUSY": "ProofLab is busy checking other work. Try again in a moment.",
    }
)
