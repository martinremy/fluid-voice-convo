from unittest.mock import MagicMock

from av import AudioFrame

from app.audio import TTSOutputTrack
from app.webrtc import _respond_to_committed, _respond_with_tts


class FakeIntelligence:
    def __init__(self, tokens: list[str]) -> None:
        self._tokens = list(tokens)
        self.ingested: list[str] = []

    async def ingest(self, user_text: str) -> None:
        self.ingested.append(user_text)

    async def stream_response(self):
        for t in self._tokens:
            yield t


async def test_respond_to_committed_sends_tokens_then_done():
    channel = MagicMock()
    channel.readyState = "open"
    intelligence = FakeIntelligence(["Hel", "lo"])

    await _respond_to_committed(intelligence, "hi", channel)

    sent = [c.args[0] for c in channel.send.call_args_list]
    assert sent == [
        '{"kind": "assistant_token", "text": "Hel"}',
        '{"kind": "assistant_token", "text": "lo"}',
        '{"kind": "assistant_done", "text": ""}',
    ]
    assert intelligence.ingested == ["hi"]


async def test_respond_to_committed_surfaces_intelligence_error():
    channel = MagicMock()
    channel.readyState = "open"

    class BrokenIntelligence:
        async def ingest(self, user_text: str) -> None:
            raise RuntimeError("model down")

        async def stream_response(self):
            yield ""  # never reached
            yield ""  # pragma: no cover

    await _respond_to_committed(BrokenIntelligence(), "hi", channel)

    sent = [c.args[0] for c in channel.send.call_args_list]
    # An error event, then assistant_done (finally always runs).
    assert any('"kind": "error"' in s and "model down" in s for s in sent)
    assert sent[-1] == '{"kind": "assistant_done", "text": ""}'


class FakeTTS:
    def __init__(self, audio: list[bytes]) -> None:
        self._audio = list(audio)
        self.received_chunks: list[str] = []

    async def stream(self, text_chunks):
        async for chunk in text_chunks:
            self.received_chunks.append(chunk)
        for a in self._audio:
            yield a


async def test_respond_with_tts_tees_tokens_and_audio():
    channel = MagicMock()
    channel.readyState = "open"
    intelligence = FakeIntelligence(["Hel", "lo", " world."])
    tts = FakeTTS([b"audio1", b"audio2"])
    track = TTSOutputTrack()

    await _respond_with_tts(intelligence, tts, track, "hi", channel)

    sent = [c.args[0] for c in channel.send.call_args_list]
    # Tokens went to the channel.
    assert any('"kind": "assistant_token"' in s and "Hel" in s for s in sent)
    assert sent[-1] == '{"kind": "assistant_done", "text": ""}'
    # Text chunks went to TTS (boundary-batched).
    assert "".join(tts.received_chunks) == "Hello world."
    # Audio was pushed onto the track.
    first = await track.recv()
    assert isinstance(first, AudioFrame)


async def test_respond_with_tts_surfaces_tts_error():
    channel = MagicMock()
    channel.readyState = "open"

    class BrokenTTS:
        async def stream(self, text_chunks):
            raise RuntimeError("tts down")
            yield b""  # pragma: no cover

    track = TTSOutputTrack()
    await _respond_with_tts(
        FakeIntelligence(["hi"]), BrokenTTS(), track, "hi", channel
    )

    sent = [c.args[0] for c in channel.send.call_args_list]
    assert any('"kind": "error"' in s and "tts down" in s for s in sent)
    assert sent[-1] == '{"kind": "assistant_done", "text": ""}'
