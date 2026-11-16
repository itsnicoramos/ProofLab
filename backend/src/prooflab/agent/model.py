"""The model: the LLM the agent talks to (SPEC §23).

The loop only needs ``complete(system, messages, tools)`` returning a reply with
``stop_reason`` and ``content`` blocks, so tests drive it with a scripted model and no network.
The model translates and teaches; it never grades. ProofLab's checker does that.
"""

from __future__ import annotations

from typing import Any, Protocol

DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000


class Model(Protocol):
    name: str

    def complete(self, system: str, messages: list[dict[str, Any]], tools: list[dict]) -> Any: ...


class ClaudeModel:
    """Claude through the Anthropic SDK (the optional ``agent`` extra)."""

    def __init__(self, name: str = DEFAULT_MODEL) -> None:
        import anthropic  # imported here so the rest of ProofLab never needs it

        self.name = name
        self._client = anthropic.Anthropic()

    def complete(self, system: str, messages: list[dict[str, Any]], tools: list[dict]) -> Any:
        return self._client.beta.messages.create(
            model=self.name,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=tools,
            messages=messages,
            # If the model declines on policy grounds, the API retries on a fallback model
            # inside the same call instead of ending the lesson.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
