from __future__ import annotations

from collections.abc import AsyncIterator

from app.config import OpenAICompatibleSettings
from app.intelligence import (
    ChatCompleter,
    IntelligenceProvider,
    OpenAICompatibleIntelligenceProvider,
)


def test_intelligence_provider_protocol_exists():
    assert IntelligenceProvider is not None
    assert hasattr(IntelligenceProvider, "ingest")
    assert hasattr(IntelligenceProvider, "stream_response")


def test_chat_completer_protocol_exists():
    assert ChatCompleter is not None
    assert hasattr(ChatCompleter, "stream")


def _settings() -> OpenAICompatibleSettings:
    return OpenAICompatibleSettings(
        api_key="sk-test",
        base_url="https://api.example.com/v1",
        model="gpt-test",
    )


class FakeChatCompleter:
    """Records the message arrays it receives and replays a canned token stream."""

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = list(tokens)
        self.calls: list[list[dict[str, str]]] = []

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        self.calls.append([dict(m) for m in messages])
        for tok in self._tokens:
            yield tok


async def _drain(agen) -> list[str]:
    return [t async for t in agen]


async def test_ingest_appends_user_message_to_history():
    completer = FakeChatCompleter(["hi"])
    provider = OpenAICompatibleIntelligenceProvider(_settings(), _completer=completer)

    await provider.ingest("hello")

    await _drain(provider.stream_response())
    assert completer.calls[0][-1] == {"role": "user", "content": "hello"}


async def test_stream_response_yields_token_deltas_in_order():
    completer = FakeChatCompleter(["Hel", "lo", " world"])
    provider = OpenAICompatibleIntelligenceProvider(_settings(), _completer=completer)
    await provider.ingest("hi")

    tokens = [t async for t in provider.stream_response()]

    assert tokens == ["Hel", "lo", " world"]


async def test_stream_response_finalizes_assistant_message_in_history():
    completer = FakeChatCompleter(["Hel", "lo"])
    provider = OpenAICompatibleIntelligenceProvider(_settings(), _completer=completer)
    await provider.ingest("hi")
    await _drain(provider.stream_response())

    completer2 = FakeChatCompleter(["ok"])
    provider._completer = completer2
    await provider.ingest("again")
    await _drain(provider.stream_response())

    roles = [m["role"] for m in completer2.calls[0]]
    assert roles == ["user", "assistant", "user"]
    assert completer2.calls[0][1]["content"] == "Hello"


async def test_history_accumulates_across_turns():
    completer = FakeChatCompleter(["a"])
    provider = OpenAICompatibleIntelligenceProvider(_settings(), _completer=completer)
    await provider.ingest("turn 1")
    await _drain(provider.stream_response())
    await provider.ingest("turn 2")
    await _drain(provider.stream_response())

    second = completer.calls[1]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert second[0]["content"] == "turn 1"
    assert second[2]["content"] == "turn 2"


async def test_system_prompt_prepended_to_every_call():
    completer = FakeChatCompleter(["ok"])
    provider = OpenAICompatibleIntelligenceProvider(
        _settings(),
        _completer=completer,
        system_prompt="You are a helpful voice assistant.",
    )
    await provider.ingest("hi")
    await _drain(provider.stream_response())

    assert completer.calls[0][0] == {
        "role": "system",
        "content": "You are a helpful voice assistant.",
    }


async def test_empty_token_delta_is_not_yielded():
    completer = FakeChatCompleter(["", "hi", ""])
    provider = OpenAICompatibleIntelligenceProvider(_settings(), _completer=completer)
    await provider.ingest("hello")

    tokens = [t async for t in provider.stream_response()]

    assert tokens == ["hi"]
