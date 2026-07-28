from collections.abc import AsyncIterator

from app.tts import TTSProvider, chunk_text


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
