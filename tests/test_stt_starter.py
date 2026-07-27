from app.webrtc import STTStarter


class FakeTrack:
    kind = "audio"


class FakeChannel:
    def __init__(self, label: str) -> None:
        self.label = label


def test_starter_starts_once_when_track_arrives_first():
    """Race that bit us in the manual demo: on('track') fires before the
    datachannel event. STT must still start exactly once when the channel
    arrives later."""
    starter = STTStarter()
    track = FakeTrack()
    channel = FakeChannel("transcript")

    starter.set_track(track)
    assert starter.start_calls == []  # not yet — no channel

    starter.set_channel(channel)
    assert starter.start_calls == [(track, channel)]


def test_starter_starts_once_when_channel_arrives_first():
    """The opposite ordering: datachannel before the audio track."""
    starter = STTStarter()
    track = FakeTrack()
    channel = FakeChannel("transcript")

    starter.set_channel(channel)
    assert starter.start_calls == []  # not yet — no track

    starter.set_track(track)
    assert starter.start_calls == [(track, channel)]


def test_starter_starts_at_most_once():
    """Repeated/duplicate events must not start STT a second time."""
    starter = STTStarter()
    track = FakeTrack()
    channel = FakeChannel("transcript")

    starter.set_track(track)
    starter.set_channel(channel)
    starter.set_track(FakeTrack())  # duplicate track event
    starter.set_channel(FakeChannel("transcript"))  # duplicate channel event

    assert starter.start_calls == [(track, channel)]


def test_starter_does_not_start_with_only_one_input():
    """A single event (track or channel) alone never starts STT."""
    starter = STTStarter()

    starter.set_track(FakeTrack())
    assert starter.start_calls == []

    starter2 = STTStarter()
    starter2.set_channel(FakeChannel("transcript"))
    assert starter2.start_calls == []
