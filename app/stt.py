from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

from app.config import ElevenLabsSTTSettings


@dataclass(frozen=True)
class TranscriptEvent:
    kind: Literal["partial", "committed"]
    text: str


class STTProvider(Protocol):
    async def stream(
        self, audio_frames: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptEvent]: ...


class RealtimeConnection(Protocol):
    """Connection seam: the ElevenLabs SDK client in prod, a fake in tests."""

    async def connect(self) -> None: ...
    async def send_audio(self, audio: bytes) -> None: ...
    async def commit(self) -> None: ...
    async def close(self) -> None: ...
    def messages(self) -> AsyncIterator[dict]: ...


class ElevenLabsSTTProvider:
    """Streaming STT via ElevenLabs Scribe v2 Realtime.

    Audio frames (16 kHz mono PCM) are base64-encoded and sent as chunks.
    Incoming partial_transcript / committed_transcript messages are mapped to
    TranscriptEvent. Empty-text transcripts are skipped.
    """

    def __init__(
        self,
        settings: ElevenLabsSTTSettings,
        _connection: RealtimeConnection | None = None,
    ) -> None:
        self._settings = settings
        self._connection = _connection

    async def stream(
        self, audio_frames: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptEvent]:
        conn = self._connection
        if conn is None:
            conn = self._build_real_connection()
        await conn.connect()
        try:
            pump = asyncio.create_task(self._pump_audio(conn, audio_frames))
            async for msg in conn.messages():
                event = self._map_message(msg)
                if event is not None:
                    yield event
            await pump
        finally:
            await conn.close()

    async def _pump_audio(
        self, conn: RealtimeConnection, audio_frames: AsyncIterator[bytes]
    ) -> None:
        async for chunk in audio_frames:
            await conn.send_audio(chunk)

    @staticmethod
    def _map_message(msg: dict) -> TranscriptEvent | None:
        kind_str = msg.get("message_type")
        text = msg.get("text", "")
        if kind_str == "partial_transcript" and text:
            return TranscriptEvent(kind="partial", text=text)
        if kind_str == "committed_transcript" and text:
            return TranscriptEvent(kind="committed", text=text)
        return None

    def _build_real_connection(self) -> RealtimeConnection:
        # Implemented in Task 4.
        raise NotImplementedError
