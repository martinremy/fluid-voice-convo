from unittest.mock import MagicMock

from app.webrtc import _respond_to_committed


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
