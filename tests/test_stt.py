import dataclasses
from collections.abc import AsyncIterator

import pytest

from app.config import ElevenLabsSTTSettings
from app.stt import ElevenLabsSTTProvider, TranscriptEvent


def test_transcript_event_partial():
    ev = TranscriptEvent(kind="partial", text="hello")
    assert ev.kind == "partial"
    assert ev.text == "hello"


def test_transcript_event_committed():
    ev = TranscriptEvent(kind="committed", text="hello world")
    assert ev.kind == "committed"
    assert ev.text == "hello world"


def test_transcript_event_is_frozen():
    ev = TranscriptEvent(kind="partial", text="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.text = "changed"


class FakeRealtimeConnection:
    """In-memory stand-in for the ElevenLabs realtime WebSocket."""

    def __init__(self, messages: list[dict]) -> None:
        self._messages = list(messages)
        self.sent_audio: list[bytes] = []
        self.committed: bool = False
        self.closed: bool = False

    async def connect(self) -> None:
        pass

    async def send_audio(self, audio: bytes) -> None:
        self.sent_audio.append(audio)

    async def commit(self) -> None:
        self.committed = True

    async def close(self) -> None:
        self.closed = True

    def messages(self) -> AsyncIterator[dict]:
        async def gen():
            for m in self._messages:
                yield m
        return gen()


async def async_iter(items: list[bytes]) -> AsyncIterator[bytes]:
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_provider_yields_partial_then_committed():
    messages = [
        {"message_type": "session_started"},
        {"message_type": "partial_transcript", "text": "hel"},
        {"message_type": "partial_transcript", "text": "hello"},
        {"message_type": "committed_transcript", "text": "hello"},
    ]
    fake = FakeRealtimeConnection(messages)
    provider = ElevenLabsSTTProvider(
        settings=ElevenLabsSTTSettings(api_key="k"),
        _connection=fake,
    )

    events = [e async for e in provider.stream(async_iter([b"\x00\x01", b"\x02\x03"]))]

    assert events == [
        TranscriptEvent(kind="partial", text="hel"),
        TranscriptEvent(kind="partial", text="hello"),
        TranscriptEvent(kind="committed", text="hello"),
    ]
    assert fake.sent_audio == [b"\x00\x01", b"\x02\x03"]
    assert fake.closed is True


@pytest.mark.asyncio
async def test_provider_surfaces_error_events():
    """Error events (input_error, auth_error, etc.) must be surfaced as
    TranscriptEvent(kind="error") so the browser shows what went wrong, not
    silently dropped."""
    messages = [
        {"message_type": "session_started"},
        {"message_type": "input_error", "reason": "bad audio"},
    ]
    fake = FakeRealtimeConnection(messages)
    provider = ElevenLabsSTTProvider(
        settings=ElevenLabsSTTSettings(api_key="k"),
        _connection=fake,
    )

    events = [e async for e in provider.stream(async_iter([]))]

    assert len(events) == 1
    assert events[0].kind == "error"
    assert "input_error" in events[0].text
    assert "bad audio" in events[0].text
    assert fake.closed is True


@pytest.mark.asyncio
async def test_provider_skips_empty_text_transcripts():
    messages = [
        {"message_type": "partial_transcript", "text": ""},
        {"message_type": "committed_transcript", "text": ""},
    ]
    fake = FakeRealtimeConnection(messages)
    provider = ElevenLabsSTTProvider(
        settings=ElevenLabsSTTSettings(api_key="k"),
        _connection=fake,
    )

    events = [e async for e in provider.stream(async_iter([]))]

    assert events == []
