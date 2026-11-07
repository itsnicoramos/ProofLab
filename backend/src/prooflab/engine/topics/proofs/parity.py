"""Parity proofs (SPEC §5.1): ``parity_proof``.

Even/odd is divisibility by 2, so this is a thin wrapper around the structured-proof engine in
``divisibility.py`` with even/odd vocabulary and parity-specific hints.
"""

from __future__ import annotations

from typing import Literal

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field

from prooflab.engine import hints
from prooflab.engine.checker import register
from prooflab.engine.models import Problem
from prooflab.engine.topics.proofs.divisibility import Condition, ModularProofHandler, ProofSpec

hints.register_many(
    {
        "EVEN_FORM": "An even integer is 2 times an integer: write it as 2 times a new integer "
        "variable.",
        "ODD_FORM": "An odd integer is one more than an even integer: 2 times a new integer, plus "
        "1. (Something like k + 1 isn't always odd.)",
    }
)

Parity = Literal["even", "odd"]
_REMAINDER = {"even": 0, "odd": 1}


class ParityHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    var: str
    is_: Parity = Field(alias="is")


class ParityParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variables: list[str] = Field(min_length=1)
    hypotheses: list[ParityHypothesis] = Field(default_factory=list)
    target: str
    goal: Parity


@register
class ParityProofHandler(ModularProofHandler):
    kind = "parity_proof"
    Params = ParityParams

    def spec(self, problem: Problem, params: ParityParams) -> ProofSpec:
        return self.build_spec(
            problem,
            params.variables,
            [(h.var, 2, _REMAINDER[h.is_]) for h in params.hypotheses],
            params.target,
            2,
            _REMAINDER[params.goal],
        )

    def describe(self, divisor: sp.Expr, remainder: sp.Expr) -> str:
        if divisor == 2:
            return "even" if remainder == 0 else "odd"
        return super().describe(divisor, remainder)

    def representation_hint(
        self, cond: Condition, coeff: sp.Expr, const: sp.Expr
    ) -> tuple[str, dict[str, object]] | None:
        if cond.divisor != 2:
            return None
        return ("EVEN_FORM" if cond.remainder == 0 else "ODD_FORM", {})
