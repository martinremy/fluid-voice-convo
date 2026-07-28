from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from openai import AsyncOpenAI

from app.config import OpenAICompatibleSettings


class ChatCompleter(Protocol):
    """Injectable seam over an OpenAI-compatible streaming chat completions
    endpoint. The production implementation wraps the openai SDK; tests inject
    a fake so no real network call is made.

    `stream` is a regular method returning an AsyncIterator (async generator),
    not an async function returning one — so callers write
    `async for token in completer.stream(messages)` with no await.
    """

    def stream(
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


class OpenAIChatCompleter:
    """ChatCompleter backed by the openai async SDK.

    Calls an OpenAI-compatible /v1/chat/completions endpoint with stream=True
    and yields delta.content token strings (skipping empty/None deltas).
    """

    def __init__(self, settings: OpenAICompatibleSettings) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.api_key, base_url=settings.base_url
        )
        self._model = settings.model

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            stream=True,
        )
        async for chunk in stream:  # type: ignore[union-attr]
            if chunk.choices:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta


class OpenAICompatibleIntelligenceProvider:
    """Stateful intelligence provider over an OpenAI-compatible streaming
    chat completions endpoint.

    Holds the full message history in memory and re-sends the entire array on
    each stream_response() call (stateful interface over a stateless transport).
    No tool-calling, no decisions, no memory beyond the in-process history.
    """

    def __init__(
        self,
        settings: OpenAICompatibleSettings,
        _completer: ChatCompleter | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self._settings = settings
        self._completer = _completer
        self._system_prompt = system_prompt
        self._history: list[dict[str, str]] = []

    async def ingest(self, user_text: str) -> None:
        self._history.append({"role": "user", "content": user_text})

    async def stream_response(self) -> AsyncIterator[str]:
        completer = self._completer
        if completer is None:
            completer = self._build_real_completer()
        messages = self._messages_to_send()
        collected: list[str] = []
        try:
            async for token in completer.stream(messages):
                if token:
                    collected.append(token)
                    yield token
        finally:
            # Finalize the assistant message in history whether or not the
            # stream completed normally. Concatenated deltas become the content.
            self._history.append(
                {"role": "assistant", "content": "".join(collected)}
            )

    def _messages_to_send(self) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.extend(self._history)
        return messages

    def _build_real_completer(self) -> ChatCompleter:
        return OpenAIChatCompleter(self._settings)
