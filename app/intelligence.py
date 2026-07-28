from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol


class ChatCompleter(Protocol):
    """Injectable seam over an OpenAI-compatible streaming chat completions
    endpoint. The production implementation wraps the openai SDK; tests inject
    a fake so no real network call is made.
    """

    async def stream(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]: ...


class IntelligenceProvider(Protocol):
    """Stateful provider: ingests user turns and streams assistant token deltas.

    The interface is Hermes-shaped (stateful, decision-capable) so a future
    stateful agent backend can implement the same protocol without breaking the
    voice transport. v1 has no tool-calling/decisions — straight streamed chat.
    """

    async def ingest(self, user_text: str) -> None: ...

    async def stream_response(self) -> AsyncIterator[str]: ...
