from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Protocol

from app.config import ElevenLabsTTSSettings

_BOUNDARIES = ".!?,"
_DEFAULT_THRESHOLD = 200

logger = logging.getLogger(__name__)


class TTSProvider(Protocol):
    """Streaming text-to-speech: consumes text chunks, yields PCM audio bytes.

    `stream` is an async generator function (declared `async def` with `yield`),
    so callers write `async for audio in tts.stream(chunks)` with no await on
    the call itself.
    """

    def stream(
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


class ElevenLabsTTSProvider:
    """Streaming TTS via ElevenLabs, wrapped to satisfy the async TTSProvider.

    The SDK's convert_realtime is synchronous (sync text Iterator in, sync
    bytes Iterator out). We bridge it to async: a background executor thread
    runs the sync callable; async text chunks are pushed onto a thread-safe
    queue the sync iterator reads, and sync audio bytes are pushed onto an
    asyncio.Queue the async generator yields.
    """

    def __init__(
        self,
        settings: ElevenLabsTTSSettings,
        _tts_callable: Callable[[Iterator[str]], Iterator[bytes]] | None = None,
    ) -> None:
        self._settings = settings
        self._tts_callable = _tts_callable

    async def stream(
        self, text_chunks: AsyncIterator[str]
    ) -> AsyncIterator[bytes]:
        tts_callable = self._tts_callable or self._build_real_callable()
        loop = asyncio.get_running_loop()
        text_queue: asyncio.Queue[str | None] = asyncio.Queue()
        audio_queue: asyncio.Queue[bytes | None | Exception] = asyncio.Queue()

        def _sync_text_iter() -> Iterator[str]:
            while True:
                future = asyncio.run_coroutine_threadsafe(text_queue.get(), loop)
                item = future.result()
                if item is None:
                    return
                yield item

        def _run_sync_tts() -> None:
            try:
                for audio_chunk in tts_callable(_sync_text_iter()):
                    fut = asyncio.run_coroutine_threadsafe(
                        audio_queue.put(audio_chunk), loop
                    )
                    fut.result()
            except Exception as exc:
                logger.exception("sync TTS thread failed")
                asyncio.run_coroutine_threadsafe(
                    audio_queue.put(exc), loop
                ).result()
            finally:
                asyncio.run_coroutine_threadsafe(
                    audio_queue.put(None), loop
                ).result()

        tts_thread = loop.run_in_executor(None, _run_sync_tts)
        try:
            async for chunk in text_chunks:
                await text_queue.put(chunk)
            await text_queue.put(None)  # signal end of text

            while True:
                item = await audio_queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            await tts_thread

    def _build_real_callable(self) -> Callable[[Iterator[str]], Iterator[bytes]]:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=self._settings.api_key)
        voice_id = self._settings.voice_id
        model_id = self._settings.model_id

        def _call(text_iter: Iterator[str]) -> Iterator[bytes]:
            result = client.text_to_speech.convert_realtime(
                voice_id=voice_id,
                text=text_iter,
                model_id=model_id,
                output_format="pcm_16000",
            )
            return iter(result)

        return _call
