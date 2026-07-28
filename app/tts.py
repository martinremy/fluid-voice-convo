from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

_BOUNDARIES = ".!?,"
_DEFAULT_THRESHOLD = 200


class TTSProvider(Protocol):
    """Streaming text-to-speech: consumes text chunks, yields PCM audio bytes."""

    async def stream(
        self, text_chunks: AsyncIterator[str]
    ) -> AsyncIterator[bytes]: ...


async def chunk_text(
    tokens: AsyncIterator[str], *, threshold: int = _DEFAULT_THRESHOLD
) -> AsyncIterator[str]:
    """Accumulate token deltas and yield sentence/clause-boundary chunks.

    Flush when the accumulated text ends with a boundary char (`.`, `,`, `!`,
    `?`), or when its length reaches `threshold`, or at end-of-stream (flush
    any remaining text). Empty accumulated text is never yielded.
    """
    buffer = ""
    async for token in tokens:
        buffer += token
        # Flush when the buffer ends with a boundary char OR when the token we
        # just added contains a boundary (e.g. ", " — boundary isn't last).
        has_boundary = any(ch in _BOUNDARIES for ch in token)
        if buffer and (has_boundary or len(buffer) >= threshold):
            yield buffer
            buffer = ""
    if buffer:
        yield buffer
