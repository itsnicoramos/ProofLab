"""ProofLab-made variants of existing problems: ids, determinism, coverage and self-checks."""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import pytest

from prooflab import variants
from prooflab.content import load_registry
from prooflab.engine import hints
from prooflab.engine.checker import check, get_handler
from prooflab.engine.models import Problem, ReviewStatus, StepStatus, Submission, VerdictStatus
from prooflab.variants import (
    VARIANT_NOTE,
    VARIANT_RE,
    VARIANT_TAG,
    make_variant,
    parse_variant_id,
    supported_kinds,
    supports,
    variant_id,
)

REGISTRY = load_registry()
SERVED = REGISTRY.served()
SUPPORTED = [p for p in SERVED if supports(p)]
SEEDS = (1, 2, 3)
PAIRS = [(p, s) for p in SUPPORTED for s in SEEDS]

EXPECTED_KINDS = {
    "parity_proof",
    "truth_table",
    "finite_set",
    "induction",
    "derivative",
    "antiderivative",
    "definite_integral",
    "partial_derivative",
    "gradient",
    "divergence",
    "curl",
    "expression",
    "series_sum",
    "tangent_line",
    "iterated_integral",
    "ode_solution",
    "limit",
}

_TIMES: dict[tuple[str, int], float] = {}


def _variant(base: Problem, seed: int) -> Problem | None:
    """make_variant, timing the first (uncached) call."""
    start = time.perf_counter()
    made = make_variant(base, seed)
    _TIMES.setdefault((base.id, seed), time.perf_counter() - start)
    return made


def _codes(verdict) -> set[str]:
    out = {h.code for h in verdict.hints} | {s.code for s in verdict.steps if s.code}
    if verdict.answer is not None and verdict.answer.code:
        out.add(verdict.answer.code)
    return out


# --------------------------------------------------------------------------- ids


@pytest.mark.parametrize(
    "base_id",
    [
        "calc1.derivatives.chain-rule",
        "proofs.direct.ch4-ex01",
        "proofs.direct.ch4-ex01-v3",  # a base id that already looks like a variant
        "proofs.set-proofs.ch8-ex10",
        "precalc.some_topic.a-v-b",
    ],
)
@pytest.mark.parametrize("seed", [0, 5, 42, 999_999_999])
def test_variant_id_round_trip(base_id: str, seed: int) -> None:
    vid = variant_id(base_id, seed)
    assert vid == f"{base_id}-v{seed}"
    assert VARIANT_RE.fullmatch(vid)
    assert parse_variant_id(vid) == (base_id, seed)


def test_parse_variant_id_rejects_non_variants() -> None:
    assert parse_variant_id("proofs.direct.ch4-ex01") is None
    assert parse_variant_id("proofs.direct.ch4-ex01-v") is None
    assert parse_variant_id("proofs.direct.ch4-ex01-v05") is None  # not canonical
    assert parse_variant_id("proofs.direct.ch4-ex01-v1234567890") is None  # 10 digits
    assert parse_variant_id("not-a-problem-v3") is None
    # A real id ending in -v3 parses as variant 3 of the shorter id; callers look ids up first.
    assert parse_variant_id("proofs.direct.ch4-ex01-v3") == ("proofs.direct.ch4-ex01", 3)


def test_variant_of_a_base_whose_id_ends_in_v3() -> None:
    base = next(p for p in SUPPORTED if p.kind == "parity_proof")
    odd = Problem.model_validate({**base.model_dump(mode="json"), "id": f"{base.id}-v3"})
    made = make_variant(odd, 7)
    assert made is not None
    assert made.id == f"{base.id}-v3-v7"
    assert parse_variant_id(made.id) == (odd.id, 7)


# --------------------------------------------------------------------------- coverage


def test_supported_kinds() -> None:
    assert supported_kinds() == EXPECTED_KINDS
    assert {p.kind for p in SUPPORTED} == EXPECTED_KINDS, "every supported kind has a base"


def test_unsupported_kinds_and_shapes_give_none() -> None:
    other = next(p for p in SERVED if p.kind not in supported_kinds())
    assert not supports(other)
    assert make_variant(other, 1) is None
    shape = next(p for p in SERVED if p.kind in supported_kinds() and not supports(p))
    assert make_variant(shape, 1) is None
    fake = SUPPORTED[0].model_copy(update={"kind": "no_such_kind"})
    assert not supports(fake)
    assert make_variant(fake, 1) is None


@pytest.mark.parametrize("seed", [-1, variants.MAX_SEED + 1, True, 1.5])
def test_bad_seeds_give_none(seed) -> None:
    assert make_variant(SUPPORTED[0], seed) is None


def test_most_supported_bases_produce_a_variant() -> None:
    by_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    failed = []
    for base in SUPPORTED:
        made = [_variant(base, seed) for seed in SEEDS]
        ok = any(m is not None for m in made)
        by_kind[base.kind][0] += 1
        by_kind[base.kind][1] += ok
        if not ok:
            failed.append(base.id)
    produced = sum(ok for _, ok in by_kind.values())
    report = ", ".join(f"{k} {ok}/{n}" for k, (n, ok) in sorted(by_kind.items()))
    assert produced >= 0.8 * len(SUPPORTED), f"{report}; failed: {failed}"
    typical = statistics.median(_TIMES.values())
    assert typical < 2.0, f"median generation time {typical:.2f}s"


# --------------------------------------------------------------------------- self-checks


@pytest.mark.parametrize(("base", "seed"), PAIRS, ids=[f"{p.id}-s{s}" for p, s in PAIRS])
def test_variant_passes_self_checks(base: Problem, seed: int) -> None:
    v = _variant(base, seed)
    if v is None:
        pytest.skip("no variant for this seed (coverage is checked separately)")

    # 1. a valid Problem, labelled as ProofLab-made
    assert Problem.model_validate(v.model_dump()) == v
    assert v.id == variant_id(base.id, seed) and parse_variant_id(v.id) == (base.id, seed)
    for name in ("course", "topic", "kind", "answer_format", "difficulty"):
        assert getattr(v, name) == getattr(base, name), name
    short = base.title.split(" · ")[0]
    assert v.title == f"New version of {short}"
    assert v.tags == [t for t in base.tags if t != "book-of-proof"] + [VARIANT_TAG]
    assert v.reference.book == base.reference.book
    assert v.reference.section == base.reference.section
    assert v.reference.note == VARIANT_NOTE
    assert v.review.status is ReviewStatus.DRAFT
    assert v.data != base.data and v.prompt != base.prompt, "the variant must differ"
    texts = [v.prompt, v.answer, *v.solution, *v.hints, *(m.hint for m in v.mistakes)]
    assert not any("—" in t or "–" in t for t in texts), "no em or en dashes"
    assert v.prompt.count("$") % 2 == 0, "balanced math delimiters"

    # 2-3. the handler accepts it and SymPy doesn't reject the key
    handler = get_handler(v.kind)
    params = handler.params(v)
    handler.validate(v, params)
    assert handler.verify_key(v, params) is not False

    # 4. every example gets its expected verdict
    statuses = {e.expect.status for e in v.examples}
    assert VerdictStatus.CORRECT in statuses and statuses != {VerdictStatus.CORRECT}
    for example in v.examples:
        verdict = check(v, example.submission)
        dump = verdict.model_dump_json(indent=2)
        assert verdict.status == example.expect.status, f"{example.name}\n{dump}"
        errors = [s.index for s in verdict.steps if s.status is StepStatus.ERROR]
        if example.expect.first_error is not None:
            assert errors and errors[0] == example.expect.first_error, f"{example.name}\n{dump}"
        if example.expect.status is VerdictStatus.CORRECT:
            assert not errors, f"{example.name}\n{dump}"
        codes = _codes(verdict)
        assert set(example.expect.hint_codes) <= codes, f"{example.name}\n{dump}"
        assert all(hints.is_registered(c) for c in codes)
        assert "ENGINE_ERROR" not in codes

    # authored mistakes are really wrong
    for mistake in v.mistakes:
        assert check(v, Submission(answer=mistake.answer)).status is not VerdictStatus.CORRECT


# --------------------------------------------------------------------------- determinism


def _one_per_kind() -> list[Problem]:
    seen: dict[str, Problem] = {}
    for p in SUPPORTED:
        seen.setdefault(p.kind, p)
    return list(seen.values())


def test_same_base_and_seed_give_the_same_problem() -> None:
    for base in _one_per_kind():
        first = make_variant(base, 11)
        fresh = variants._generate(base, 11)  # bypasses the cache
        assert first is not None and fresh is not None, base.id
        assert first.model_dump() == fresh.model_dump(), base.id
        first.prompt = "changed by a caller"
        assert make_variant(base, 11).prompt != first.prompt, "callers get their own copy"


def test_other_seeds_give_other_variants() -> None:
    for base in _one_per_kind():
        made = [make_variant(base, s) for s in SEEDS]
        dumps = {json.dumps(m.model_dump(mode="json"), sort_keys=True) for m in made if m}
        assert len(dumps) >= 2, base.id


def test_variants_do_not_depend_on_the_hash_seed() -> None:
    """A fresh process with another PYTHONHASHSEED rebuilds the same variants."""
    bases = _one_per_kind()
    script = (
        "import json, sys\n"
        "from prooflab.content import load_registry\n"
        "from prooflab.variants import make_variant\n"
        "reg = load_registry()\n"
        "out = {}\n"
        "for pid in sys.argv[1:]:\n"
        "    v = make_variant(reg.get(pid), 11)\n"
        "    out[pid] = None if v is None else v.model_dump(mode='json')\n"
        "print(json.dumps(out))\n"
    )
    src = str(Path(__file__).resolve().parents[1] / "src")
    env = {**os.environ, "PYTHONHASHSEED": "4242", "PYTHONPATH": src}
    result = subprocess.run(
        [sys.executable, "-c", script, *(b.id for b in bases)],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
        check=True,
    )
    other = json.loads(result.stdout.strip().splitlines()[-1])
    for base in bases:
        here = make_variant(base, 11)
        assert here is not None
        assert other[base.id] == here.model_dump(mode="json"), base.id
