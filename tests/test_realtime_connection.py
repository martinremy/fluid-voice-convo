from __future__ import annotations

from app.stt import ElevenLabsRealtimeConnection


def test_enqueue_with_dict_queues_message():
    """Transcript/error events arrive as dicts and must be queued as-is."""
    conn = ElevenLabsRealtimeConnection(api_key="dummy", model_id="m")
    conn._enqueue({"message_type": "partial_transcript", "text": "hi"})
    assert conn._incoming.qsize() == 1
    queued = conn._incoming.get_nowait()
    assert queued == {"message_type": "partial_transcript", "text": "hi"}


def test_enqueue_with_no_arg_queues_close_sentinel():
    """The SDK emits RealtimeEvents.CLOSE with NO argument — the handler must
    accept that (not crash with 'missing 1 required positional argument') and
    queue the close sentinel so messages() can return.

    Regression guard for the bug where _enqueue(self, msg) required msg and the
    CLOSE callback raised, hanging the stream.
    """
    conn = ElevenLabsRealtimeConnection(api_key="dummy", model_id="m")
    conn._enqueue()  # no arg — simulates SDK's bare _emit(CLOSE)
    assert conn._incoming.qsize() == 1
    sentinel = conn._incoming.get_nowait()
    assert sentinel is conn._CLOSE_SENTINEL


def test_enqueue_with_none_arg_queues_close_sentinel():
    """Non-dict payloads (e.g. None) also map to the close sentinel."""
    conn = ElevenLabsRealtimeConnection(api_key="dummy", model_id="m")
    conn._enqueue(None)
    assert conn._incoming.get_nowait() is conn._CLOSE_SENTINEL


async def test_messages_generator_ends_on_close_sentinel():
    """messages() must terminate when the close sentinel is queued, so the
    async-for in ElevenLabsSTTProvider.stream can finish."""
    conn = ElevenLabsRealtimeConnection(api_key="dummy", model_id="m")
    conn._incoming.put_nowait({"message_type": "partial_transcript", "text": "x"})
    conn._enqueue()  # close sentinel

    gen = conn.messages()
    seen = []
    async for msg in gen:
        seen.append(msg)
    assert seen == [{"message_type": "partial_transcript", "text": "x"}]
