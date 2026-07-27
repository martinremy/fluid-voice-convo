from unittest.mock import MagicMock

from app.stt import TranscriptEvent
from app.webrtc import _send_closed, _send_error, _send_event


def test_main_calls_load_dotenv():
    """app.main must call load_dotenv() at import time so a .env file is read
    into the environment. Regression guard for the bug where python-dotenv was
    a declared dependency but never called, so ELEVENLABS_API_KEY stayed unset
    at runtime and STT failed with a swallowed RuntimeError.

    A source-level assertion is used deliberately: a behavior test that reloads
    the module risks leaking real secrets via os.environ in failure output, and
    load_dotenv's no-arg search/override semantics make a hermetic behavior
    test fragile. Asserting the call exists is the precise guarantee we need.
    """
    from pathlib import Path

    import app.main as main_module

    source = Path(main_module.__file__).read_text()
    assert "load_dotenv()" in source
    assert "from dotenv import load_dotenv" in source


def test_send_error_surfaces_message_to_open_channel():
    """Errors must reach the browser as an 'error' event, not be swallowed."""
    channel = MagicMock()
    channel.readyState = "open"
    _send_error(channel, "ELEVENLABS_API_KEY is not set")
    assert channel.send.called
    sent = channel.send.call_args.args[0]
    assert '"kind": "error"' in sent
    assert "ELEVENLABS_API_KEY is not set" in sent


def test_send_error_noop_on_closed_channel():
    channel = MagicMock()
    channel.readyState = "closed"
    _send_error(channel, "boom")
    assert not channel.send.called


def test_send_event_skips_on_closed_channel():
    channel = MagicMock()
    channel.readyState = "closed"
    _send_event(channel, TranscriptEvent(kind="partial", text="hi"))
    assert not channel.send.called


def test_send_closed_skips_on_closed_channel():
    channel = MagicMock()
    channel.readyState = "closed"
    _send_closed(channel)
    assert not channel.send.called
