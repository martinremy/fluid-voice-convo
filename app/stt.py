from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

from elevenlabs import (
    AudioFormat,
    CommitStrategy,
    ElevenLabs,
    RealtimeAudioOptions,
    RealtimeEvents,
)
from elevenlabs.realtime.connection import (
    RealtimeConnection as SDKRealtimeConnection,
)

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
        return ElevenLabsRealtimeConnection(
            api_key=self._settings.api_key, model_id=self._settings.model_id
        )


class ElevenLabsRealtimeConnection:
    """RealtimeConnection backed by the elevenlabs SDK.

    Uses VAD commit strategy for microphone input. Audio is sent as 16 kHz
    mono PCM (base64-encoded). Transcript events are queued from sync SDK
    callbacks onto an asyncio.Queue for async consumption.
    """

    _CLOSE_SENTINEL: dict = {"message_type": "__closed__"}

    def __init__(self, api_key: str, model_id: str) -> None:
        self._client = ElevenLabs(api_key=api_key)
        self._model_id = model_id
        self._conn: SDKRealtimeConnection | None = None
        self._incoming: asyncio.Queue[dict] = asyncio.Queue()

    async def connect(self) -> None:
        self._conn = await self._client.speech_to_text.realtime.connect(
            RealtimeAudioOptions(
                model_id=self._model_id,
                audio_format=AudioFormat.PCM_16000,
                sample_rate=16000,
                commit_strategy=CommitStrategy.VAD,
            )
        )
        for event in (
            RealtimeEvents.PARTIAL_TRANSCRIPT,
            RealtimeEvents.COMMITTED_TRANSCRIPT,
            RealtimeEvents.SESSION_STARTED,
            RealtimeEvents.INPUT_ERROR,
            RealtimeEvents.ERROR,
            RealtimeEvents.CLOSE,
        ):
            self._conn.on(event, self._enqueue)

    def _enqueue(self, msg: object) -> None:
        if isinstance(msg, dict):
            if msg.get("message_type") == RealtimeEvents.CLOSE:
                self._incoming.put_nowait(self._CLOSE_SENTINEL)
            else:
                self._incoming.put_nowait(msg)
        else:
            self._incoming.put_nowait(self._CLOSE_SENTINEL)

    async def send_audio(self, audio: bytes) -> None:
        if self._conn is None:
            raise RuntimeError("connect() not called")
        await self._conn.send(
            {"audio_base_64": base64.b64encode(audio).decode(), "sample_rate": 16000}
        )

    async def commit(self) -> None:
        if self._conn is not None:
            await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()

    def messages(self) -> AsyncIterator[dict]:
        async def gen() -> AsyncIterator[dict]:
            while True:
                msg = await self._incoming.get()
                if msg.get("message_type") == "__closed__":
                    return
                yield msg

        return gen()
