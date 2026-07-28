from __future__ import annotations

import asyncio
import fractions

import av
from aiortc.mediastreams import AudioStreamTrack, MediaStreamError

# 20ms at 16kHz s16 mono = 320 samples * 2 bytes = 640 bytes.
_FRAME_BYTES = 640
_IN_RATE = 16000
_OUT_RATE = 48000
_SAMPLES = 320  # 20ms at 16kHz


class TTSOutputTrack(AudioStreamTrack):
    """Outgoing audio track fed by PCM bytes (16 kHz s16 mono).

    push() appends PCM to an internal buffer; recv() builds the next 20 ms
    AudioFrame, resamples it to 48 kHz for the WebRTC Opus encoder, and returns
    it. stop_stream() signals end-of-stream; recv() raises MediaStreamError
    after the buffer drains.
    """

    def __init__(self) -> None:
        super().__init__()
        self._buffer = bytearray()
        self._ended = False
        self._timestamp = 0
        self._resampler = av.AudioResampler(format="s16", layout="mono", rate=_OUT_RATE)

    async def push(self, pcm: bytes) -> None:
        self._buffer.extend(pcm)

    async def stop_stream(self) -> None:
        self._ended = True

    async def recv(self) -> av.AudioFrame:
        if self.readyState != "live":
            raise MediaStreamError

        # Wait until we have a full frame or the stream has ended.
        while len(self._buffer) < _FRAME_BYTES:
            if self._ended:
                if self._buffer:
                    # Pad the final partial frame with silence.
                    self._buffer.extend(
                        b"\x00" * (_FRAME_BYTES - len(self._buffer))
                    )
                    break
                raise MediaStreamError
            await asyncio.sleep(0.01)

        chunk = bytes(self._buffer[:_FRAME_BYTES])
        del self._buffer[:_FRAME_BYTES]

        frame = av.AudioFrame(format="s16", layout="mono", samples=_SAMPLES)
        frame.planes[0].update(chunk)
        frame.pts = self._timestamp
        frame.sample_rate = _IN_RATE
        frame.time_base = fractions.Fraction(1, _IN_RATE)
        self._timestamp += _SAMPLES

        resampled = self._resampler.resample(frame)
        return resampled[0]
