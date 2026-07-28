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


async def test_recv_returns_silence_when_buffer_empty():
    """Between turns, the track must keep the sender alive with silence —
    not raise MediaStreamError (which permanently stops the sender)."""
    track = TTSOutputTrack()
    frame = await track.recv()
    assert isinstance(frame, AudioFrame)
    assert frame.sample_rate == 48000


async def test_recv_raises_after_track_stop():
    """The track ends only when the connection closes (base stop()), not per
    turn."""
    track = TTSOutputTrack()
    track.stop()
    from aiortc.mediastreams import MediaStreamError

    with pytest.raises(MediaStreamError):
        await track.recv()


async def test_track_survives_across_two_turns():
    """Regression guard for the Phase 4 bug where turn 2 went silent: after
    turn 1's audio drains, the track must still produce audio for turn 2
    (instead of the sender having stopped after a per-turn stop_stream)."""
    track = TTSOutputTrack()

    # Turn 1: push audio, drain at least one frame.
    await track.push(b"\x00\x01" * 320)
    first = await track.recv()
    assert isinstance(first, AudioFrame)

    # Between turns: recv() must keep returning (silence), not raise.
    between = await track.recv()
    assert isinstance(between, AudioFrame)

    # Turn 2: push fresh audio; recv() must still return frames.
    await track.push(b"\x01\x02" * 320)
    second = await track.recv()
    assert isinstance(second, AudioFrame)


async def test_stop_stream_is_noop():
    """stop_stream() must not end the track (the track lives for the connection)."""
    track = TTSOutputTrack()
    await track.stop_stream()
    # recv() still works after stop_stream.
    frame = await track.recv()
    assert isinstance(frame, AudioFrame)
