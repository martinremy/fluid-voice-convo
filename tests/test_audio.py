import pytest
from av import AudioFrame

from app.audio import TTSOutputTrack


async def test_recv_returns_frame_from_pushed_pcm():
    track = TTSOutputTrack()
    # 640 bytes = one 20ms frame at 16kHz s16 mono.
    await track.push(b"\x00\x01" * 320)
    frame = await track.recv()
    assert isinstance(frame, AudioFrame)
    assert frame.sample_rate == 48000  # resampled for WebRTC


async def test_recv_buffers_partial_frames_across_pushes():
    track = TTSOutputTrack()
    await track.push(b"\x00\x01" * 160)  # half a frame
    await track.push(b"\x00\x01" * 160)  # other half
    frame = await track.recv()
    assert isinstance(frame, AudioFrame)


async def test_recv_raises_after_end_of_stream():
    track = TTSOutputTrack()
    await track.stop_stream()
    from aiortc.mediastreams import MediaStreamError

    with pytest.raises(MediaStreamError):
        await track.recv()


async def test_recv_yields_remaining_then_ends():
    track = TTSOutputTrack()
    await track.push(b"\x00\x01" * 320)  # one full frame
    await track.stop_stream()
    first = await track.recv()
    assert isinstance(first, AudioFrame)
    from aiortc.mediastreams import MediaStreamError

    with pytest.raises(MediaStreamError):
        await track.recv()
