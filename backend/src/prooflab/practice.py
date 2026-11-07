"""Practice tests: midterms and finals assembled from existing problems (SPEC §13).

Nothing is generated or invented: every question is a problem already in the bank. The
algorithm is deterministic: the same course, kind, topics, length and seed always give the
same test, so a test can be retaken or shared by its URL.

1. Scope: a final covers every topic that has problems; a midterm covers the first half of
   them in course order (rounded up). An explicit topic list overrides either.
2. Length: midterm 8, final 12 by default, capped by the problems available (and by 30).
3. Allocation: every topic in scope gets one question (when there are enough questions), and
   the rest are shared in proportion to topic size (largest-remainder rounding, capped by
   each topic's size). With fewer questions than topics, topics are spread evenly.
4. Within a topic: aim for an easy / medium / hard mix of 3 : 5 : 2, falling back to the
   nearest difficulty when one runs out, and rotate through problem kinds so one kind
   doesn't repeat while others are available.
5. Order: topics in course order; inside a topic, easier first, then the bank's own order.

Self-tuning tests (SPEC §13.1) add three optional inputs, all still deterministic:

- ``weights``: per-topic multipliers from the student's own results (kept in their browser).
  Weak topics get more of the extra questions; every topic in scope still gets one.
- ``prefer``: problem ids the student is due to review. They're picked first inside their topic.
- ``variants``: about three in four of the picked problems that ProofLab can remake become a
  version with new numbers (:mod:`prooflab.variants`), labelled as not from the book.

``style`` picks the question format: written (every step checked), choice (multiple choice
built by :mod:`prooflab.quiz`) or mixed (about half and half).
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from prooflab.content import Registry
from prooflab.engine.models import Course, Problem

Kind = Literal["midterm", "final", "quiz"]
Style = Literal["written", "mixed", "choice"]
Format = Literal["written", "choice"]

DEFAULT_LENGTH: dict[str, int] = {"midterm": 8, "final": 12, "quiz": 10}
MAX_LENGTH = 30
MINUTES_PER_DIFFICULTY: dict[int, int] = {1: 5, 2: 8, 3: 12}
DIFFICULTY_MIX: dict[int, float] = {1: 0.3, 2: 0.5, 3: 0.2}
MINUTES_RULE = "about 5, 8 and 12 minutes per easy, medium and hard question"


class PracticeTestError(ValueError):
    """The request can't produce a test (unknown topic, no problems)."""


@dataclass(frozen=True)
class Question:
    problem: Problem
    format: Format
    variant_of: str | None = None


@dataclass(frozen=True)
class PracticeTest:
    id: str
    course: Course
    kind: Kind
    seed: int
    topics: list[str]
    questions: list[Question]
    suggested_minutes: int

    @property
    def problems(self) -> list[Problem]:
        return [q.problem for q in self.questions]


def available_topics(registry: Registry, course: Course) -> list[str]:
    """Topics of ``course`` that have served problems, in course order."""
    served = {p.topic for p in registry.served() if p.course is course}
    return [t for t in registry.topics.get(course.value, []) if t in served]


def default_topics(registry: Registry, course: Course, kind: Kind) -> list[str]:
    topics = available_topics(registry, course)
    if kind in ("final", "quiz"):
        return topics
    return topics[: max(1, math.ceil(len(topics) / 2))]


def _largest_remainder(total: int, weights: Sequence[float], caps: Sequence[int]) -> list[int]:
    """Split ``total`` in proportion to ``weights`` without exceeding ``caps``."""
    out = [0] * len(weights)
    remaining = total
    active = [i for i, cap in enumerate(caps) if cap > 0]
    while remaining > 0 and active:
        weight = sum(weights[i] for i in active) or len(active)
        shares = {i: remaining * ((weights[i] or 1) / weight) for i in active}
        floors = {i: min(int(shares[i]), caps[i] - out[i]) for i in active}
        for i, f in floors.items():
            out[i] += f
        remaining -= sum(floors.values())
        order = sorted(active, key=lambda i: (-(shares[i] - int(shares[i])), i))
        for i in order:
            if remaining == 0:
                break
            if out[i] < caps[i]:
                out[i] += 1
                remaining -= 1
        active = [i for i in active if out[i] < caps[i]]
    return out


def allocate(
    length: int, sizes: Sequence[int], weights: Sequence[float] | None = None
) -> list[int]:
    """How many questions each topic gets (step 3 of the algorithm)."""
    k = len(sizes)
    w = list(weights) if weights is not None else [1.0] * k
    if length < k:
        picked = (
            {round(i * (k - 1) / max(length - 1, 1)) for i in range(length)} if length > 1 else {0}
        )
        return [1 if i in picked else 0 for i in range(k)]
    base = [1] * k
    extra = _largest_remainder(
        length - k, [(s - 1) * wi for s, wi in zip(sizes, w, strict=True)], [s - 1 for s in sizes]
    )
    return [b + e for b, e in zip(base, extra, strict=True)]


def _difficulty_targets(quota: int, counts: dict[int, int]) -> dict[int, int]:
    targets = dict.fromkeys((1, 2, 3), 0)
    split = _largest_remainder(
        quota, [DIFFICULTY_MIX[d] for d in (1, 2, 3)], [counts.get(d, 0) for d in (1, 2, 3)]
    )
    for d, n in zip((1, 2, 3), split, strict=True):
        targets[d] = n
    return targets


def _rotate_kinds(problems: list[Problem]) -> list[Problem]:
    """Round-robin over problem kinds, keeping each kind's (shuffled) order."""
    by_kind: dict[str, list[Problem]] = {}
    for p in problems:
        by_kind.setdefault(p.kind, []).append(p)
    out: list[Problem] = []
    while any(by_kind.values()):
        for kind in list(by_kind):
            if by_kind[kind]:
                out.append(by_kind[kind].pop(0))
    return out


def pick_from_topic(
    pool: list[Problem],
    quota: int,
    rng: random.Random,
    prefer: frozenset[str] = frozenset(),
) -> list[Problem]:
    """Step 4: preferred (due) problems first, then a difficulty mix of 3 : 5 : 2 with variety."""
    due = [p for p in pool if p.id in prefer]
    rng.shuffle(due)
    chosen: list[Problem] = due[:quota]
    quota -= len(chosen)
    if quota <= 0:
        return chosen
    buckets: dict[int, list[Problem]] = {1: [], 2: [], 3: []}
    for p in pool:
        if p.id not in prefer:
            buckets[p.difficulty].append(p)
    for bucket in buckets.values():
        rng.shuffle(bucket)
    targets = _difficulty_targets(quota, {d: len(b) for d, b in buckets.items()})
    for d in (1, 2, 3):
        chosen.extend(_rotate_kinds(buckets[d])[: targets[d]])
    return chosen


def build_practice_test(
    registry: Registry,
    course: Course,
    kind: Kind,
    *,
    seed: int,
    topics: Sequence[str] | None = None,
    length: int | None = None,
    style: Style = "written",
    weights: dict[str, float] | None = None,
    prefer: Sequence[str] = (),
    variants: bool = False,
) -> PracticeTest:
    available = available_topics(registry, course)
    if not available:
        raise PracticeTestError(f"{course.value} has no problems to build a test from.")
    scope = list(topics) if topics else default_topics(registry, course, kind)
    unknown = [t for t in scope if t not in available]
    if unknown:
        raise PracticeTestError(f"No problems in topic(s) {', '.join(unknown)} for {course.value}.")
    scope = [t for t in available if t in scope]  # course order, no duplicates

    served = [p for p in registry.served() if p.course is course]
    pools = {t: [p for p in served if p.topic == t] for t in scope}
    total = sum(len(pool) for pool in pools.values())
    n = max(1, min(length or DEFAULT_LENGTH[kind], total, MAX_LENGTH))

    w = {t: max(0.1, min(10.0, float((weights or {}).get(t, 1.0)))) for t in scope}
    due = frozenset(prefer)
    key = f"{course.value}|{kind}|{seed}|{','.join(scope)}|{n}"
    extras = []
    if style != "written":
        extras.append(f"style={style}")
    if weights:
        extras.append("w=" + ",".join(f"{t}:{w[t]:.2f}" for t in scope))
    if due:
        extras.append("prefer=" + ",".join(sorted(due)))
    if variants:
        extras.append("variants")
    if extras:  # plain tests keep their old ids (and seeds) so saved results still match
        key += "|" + "|".join(extras)
    rng = random.Random(key)
    quotas = allocate(n, [len(pools[t]) for t in scope], [w[t] for t in scope])

    bank_order = {p.id: i for i, p in enumerate(served)}
    picked_all: list[Problem] = []
    for topic, quota in zip(scope, quotas, strict=True):
        picked = pick_from_topic(pools[topic], quota, rng, due) if quota else []
        picked_all.extend(sorted(picked, key=lambda p: (p.difficulty, bank_order[p.id])))

    questions = [_question(p, style, variants and p.id not in due, rng) for p in picked_all]
    minutes = sum(
        MINUTES_PER_DIFFICULTY[q.problem.difficulty] * (0.4 if q.format == "choice" else 1)
        for q in questions
    )
    test_id = f"{kind}-{hashlib.sha1(key.encode()).hexdigest()[:10]}"
    return PracticeTest(
        id=test_id,
        course=course,
        kind=kind,
        seed=seed,
        topics=scope,
        questions=questions,
        suggested_minutes=max(5, 5 * math.ceil(minutes / 5)),
    )


def _question(problem: Problem, style: Style, variants: bool, rng: random.Random) -> Question:
    """Format and (maybe) a ProofLab-made version for one picked problem. Uses ``rng`` the same
    number of times whatever the outcome, so one question never shifts the next one's dice."""
    format_roll, variant_roll, variant_seed = rng.random(), rng.random(), rng.randrange(1, 10**6)
    fmt: Format = (
        "choice" if style == "choice" or (style == "mixed" and format_roll < 0.5) else "written"
    )
    if variants and variant_roll < 0.75:
        made = _make_variant(problem, variant_seed)
        if made is not None:
            return Question(problem=made, format=fmt, variant_of=problem.id)
    return Question(problem=problem, format=fmt)


def _make_variant(problem: Problem, seed: int) -> Problem | None:
    try:
        from prooflab.variants import make_variant, supports
    except ImportError:  # pragma: no cover - the generator module is optional
        return None
    return make_variant(problem, seed) if supports(problem) else None
