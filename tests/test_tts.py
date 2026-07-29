from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.config import ElevenLabsTTSSettings
from app.tts import ElevenLabsTTSProvider, TTSProvider, chunk_text


async def _aiter(items: list[str]) -> AsyncIterator[str]:
    for item in items:
        yield item


def test_tts_provider_protocol_exists():
    assert TTSProvider is not None
    assert hasattr(TTSProvider, "stream")


async def test_chunk_text_flushes_on_sentence_boundary():
    chunks = [c async for c in chunk_text(_aiter(["Hello", " world.", " Next"]))]
    assert chunks == ["Hello world.", " Next"]


async def test_chunk_text_flushes_on_clause_boundary():
    chunks = [c async for c in chunk_text(_aiter(["Well", ", ", "maybe"]))]
    assert chunks == ["Well, ", "maybe"]


async def test_chunk_text_flushes_on_threshold():
    # 30 chars, no boundary, threshold 10 -> flush in ~10-char chunks.
    tokens = ["abcdefghij", "klmnopqrst", "uvwxyz"]
    chunks = [c async for c in chunk_text(_aiter(tokens), threshold=10)]
    assert chunks == ["abcdefghij", "klmnopqrst", "uvwxyz"]


async def test_chunk_text_flushes_remaining_at_end():
    chunks = [c async for c in chunk_text(_aiter(["no boundary here"]))]
    assert chunks == ["no boundary here"]


async def test_chunk_text_empty_input_yields_nothing():
    chunks = [c async for c in chunk_text(_aiter([]))]
    assert chunks == []


def _tts_settings() -> ElevenLabsTTSSettings:
    return ElevenLabsTTSSettings(
        api_key="sk-test", voice_id="voice-1", model_id="eleven_test"
    )


def _fake_convert_realtime(audio_chunks: list[bytes]):
    """Return a sync callable matching convert_realtime's shape.

    Models real behavior: audio is only produced once the text iterator yields
    something, so empty text input yields no audio.
    """
    def _call(text_iter):
        produced = False
        for _text in text_iter:
            if not produced:
                yield from audio_chunks
                produced = True
    return _call


async def test_tts_provider_yields_audio_bytes_in_order():
    provider = ElevenLabsTTSProvider(
        _tts_settings(), _tts_callable=_fake_convert_realtime([b"a1", b"a2", b"a3"])
    )
    audio = [b async for b in provider.stream(_aiter(["hi", " there"]))]
    assert audio == [b"a1", b"a2", b"a3"]


async def test_tts_provider_empty_text_yields_no_audio():
    provider = ElevenLabsTTSProvider(
        _tts_settings(), _tts_callable=_fake_convert_realtime([b"x"])
    )
    audio = [b async for b in provider.stream(_aiter([]))]
    assert audio == []


def _recording_convert_realtime(audio_chunks: list[bytes]):
    """A fake callable that records the text chunks it receives, in order."""
    received: list[str] = []

    def _call(text_iter):
        for text in text_iter:
            received.append(text)
            yield from audio_chunks

    _call.received = received  # type: ignore[attr-defined]
    return _call


async def test_tts_provider_defers_synthesis_until_first_chunk():
    """Regression test: the TTS connection must not open until the first text
    chunk is available, so a slow LLM (time-to-first-token > 20s) doesn't
    trigger ElevenLabs' idle timeout.
    """
    call_started = asyncio.Event()

    def _tts_callable(text_iter):
        call_started.set()
        for _text in text_iter:
            yield b"audio"

    provider = ElevenLabsTTSProvider(_tts_settings(), _tts_callable=_tts_callable)

    async def _delayed_chunks() -> AsyncIterator[str]:
        # Simulate a slow LLM: hold the first chunk back for a moment.
        await asyncio.sleep(0.05)
        yield "first"
        yield "second"

    assert not call_started.is_set(), "TTS callable invoked before first chunk"
    audio = [b async for b in provider.stream(_delayed_chunks())]
    assert audio == [b"audio", b"audio"]
    assert call_started.is_set(), "TTS callable was never invoked"
