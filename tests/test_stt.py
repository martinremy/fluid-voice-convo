import dataclasses

import pytest

from app.stt import TranscriptEvent


def test_transcript_event_partial():
    ev = TranscriptEvent(kind="partial", text="hello")
    assert ev.kind == "partial"
    assert ev.text == "hello"


def test_transcript_event_committed():
    ev = TranscriptEvent(kind="committed", text="hello world")
    assert ev.kind == "committed"
    assert ev.text == "hello world"


def test_transcript_event_is_frozen():
    ev = TranscriptEvent(kind="partial", text="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.text = "changed"
