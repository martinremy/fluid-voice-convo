from __future__ import annotations

from app.webrtc import STTStarter


class FakeTrack:
    kind = "audio"


class FakeChannel:
    def __init__(self, label: str) -> None:
        self.label = label


def _make_starter() -> tuple[STTStarter, list[tuple[FakeTrack, FakeChannel]]]:
    """Build a starter with an on_start spy that records real dispatch calls."""
    calls: list[tuple[FakeTrack, FakeChannel]] = []
    starter = STTStarter(on_start=lambda track, channel: calls.append((track, channel)))
    return starter, calls


def test_starter_starts_once_when_track_arrives_first():
    """Race that bit us in the manual demo: on('track') fires before the
    datachannel event. STT must still dispatch exactly once when the channel
    arrives later."""
    starter, calls = _make_starter()
    track = FakeTrack()
    channel = FakeChannel("transcript")

    starter.set_track(track)
    assert calls == []  # not yet — no channel

    starter.set_channel(channel)
    assert calls == [(track, channel)]  # on_start fired with the real pair


def test_starter_starts_once_when_channel_arrives_first():
    """The opposite ordering: datachannel before the audio track."""
    starter, calls = _make_starter()
    track = FakeTrack()
    channel = FakeChannel("transcript")

    starter.set_channel(channel)
    assert calls == []  # not yet — no track

    starter.set_track(track)
    assert calls == [(track, channel)]


def test_starter_starts_at_most_once():
    """Repeated/duplicate events must not dispatch a second time."""
    starter, calls = _make_starter()
    track = FakeTrack()
    channel = FakeChannel("transcript")

    starter.set_track(track)
    starter.set_channel(channel)
    starter.set_track(FakeTrack())  # duplicate track event
    starter.set_channel(FakeChannel("transcript"))  # duplicate channel event

    assert calls == [(track, channel)]


def test_starter_does_not_start_with_only_one_input():
    """A single event (track or channel) alone never dispatches."""
    starter, calls = _make_starter()

    starter.set_track(FakeTrack())
    assert calls == []

    starter2, calls2 = _make_starter()
    starter2.set_channel(FakeChannel("transcript"))
    assert calls2 == []


def test_starter_invokes_on_start_callback():
    """The on_start callback (which launches _run_stt in production) must fire
    exactly once when both inputs arrive. Regression guard for the refactor that
    once recorded start_calls but never dispatched anything."""
    calls: list[tuple[FakeTrack, FakeChannel]] = []
    starter = STTStarter(on_start=lambda track, channel: calls.append((track, channel)))
    track = FakeTrack()
    channel = FakeChannel("transcript")

    starter.set_track(track)
    assert calls == []  # not yet
    starter.set_channel(channel)

    assert calls == [(track, channel)]
    assert starter.start_calls == [(track, channel)]

    # A duplicate event must not fire the callback a second time.
    starter.set_track(FakeTrack())
    assert calls == [(track, channel)]
