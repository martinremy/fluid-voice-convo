from __future__ import annotations

import asyncio
import fractions
import time
from collections import deque

import av
from aiortc.mediastreams import AudioStreamTrack, MediaStreamError

# 20ms at 16kHz s16 mono = 320 samples * 2 bytes = 640 bytes.
_FRAME_BYTES = 640
_IN_RATE = 16000
_OUT_RATE = 48000
_SAMPLES = 320  # 20ms at 16kHz


class TTSOutputTrack(AudioStreamTrack):
    """Outgoing audio track fed by PCM bytes (16 kHz s16 mono).

    The track lives for the whole peer-connection lifetime: ``push()`` feeds TTS
    audio and ``recv()`` returns resampled 48 kHz frames, producing **silence**
    when no TTS audio is available so the WebRTC sender keeps flowing between
    turns. ``stop_stream()`` is a no-op retained for API compatibility — do
    NOT end the track per turn, or aiortc's RTCRtpSender permanently stops
    pulling after a MediaStreamError and subsequent turns go silent.
    """

    def __init__(self) -> None:
        super().__init__()
        self._buffer = bytearray()
        self._resampler = av.AudioResampler(
            format="s16", layout="mono", rate=_OUT_RATE
        )
        self._resampled: deque[av.AudioFrame] = deque()
        self._timestamp = 0
        self._start_time: float | None = None

    async def push(self, pcm: bytes) -> None:
        self._buffer.extend(pcm)

    async def stop_stream(self) -> None:
        # No-op: the track stays alive for the connection lifetime and emits
        # silence between TTS bursts. Ending the track per turn kills the
        # sender (it stops pulling after MediaStreamError).
        pass

    async def recv(self) -> av.AudioFrame:
        if self.readyState != "live":
            raise MediaStreamError

        # Pace to 20ms real-time so the sender doesn't spin and audio plays
        # at the right rate (mirrors the base AudioStreamTrack.recv() pacing).
        if self._start_time is None:
            self._start_time = time.time()
            self._timestamp = 0
        else:
            self._timestamp += _SAMPLES
            wait = self._start_time + (self._timestamp / _IN_RATE) - time.time()
            if wait > 0:
                await asyncio.sleep(wait)

        # Pull one 20ms chunk from the TTS buffer, or silence if insufficient.
        if len(self._buffer) >= _FRAME_BYTES:
            chunk = bytes(self._buffer[:_FRAME_BYTES])
            del self._buffer[:_FRAME_BYTES]
        else:
            chunk = b"\x00" * _FRAME_BYTES

        frame = av.AudioFrame(format="s16", layout="mono", samples=_SAMPLES)
        frame.planes[0].update(chunk)
        frame.pts = self._timestamp
        frame.sample_rate = _IN_RATE
        frame.time_base = fractions.Fraction(1, _IN_RATE)

        # The resampler may buffer internally and return 0 or more frames per
        # input; queue whatever it gives and return one.
        for resampled in self._resampler.resample(frame):
            self._resampled.append(resampled)
        if self._resampled:
            return self._resampled.popleft()

        # Resampler buffered the input without outputting yet: return a
        # 48kHz silence frame so the sender keeps flowing this cycle.
        return self._silence_frame()

    def _silence_frame(self) -> av.AudioFrame:
        out_samples = _SAMPLES * (_OUT_RATE // _IN_RATE)
        out = av.AudioFrame(format="s16", layout="mono", samples=out_samples)
        out.planes[0].update(b"\x00" * (out_samples * 2))
        out.pts = self._timestamp
        out.sample_rate = _OUT_RATE
        out.time_base = fractions.Fraction(1, _OUT_RATE)
        return out
