from __future__ import annotations

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
