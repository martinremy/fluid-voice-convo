from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class TranscriptEvent:
    kind: Literal["partial", "committed"]
    text: str


class STTProvider(Protocol):
    async def stream(
        self, audio_frames: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptEvent]: ...
