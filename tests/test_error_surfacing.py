from __future__ import annotations

from unittest.mock import MagicMock

from app.stt import TranscriptEvent
from app.webrtc import _send_closed, _send_error, _send_event


def test_main_calls_load_dotenv(tmp_path, monkeypatch):
    """app.main must load a .env file into os.environ at import time. Regression
    guard for the bug where python-dotenv was a declared dependency but never
    called, so ELEVENLABS_API_KEY stayed unset and STT failed with a swallowed
    RuntimeError.

    Hermetic behavior test: monkeypatch dotenv.find_dotenv to return a temp
    .env with a sentinel var, reload app.main, and assert the sentinel landed
    in the environment. We never print os.environ, so real secrets can't leak
    in failure output. (find_dotenv's default usecwd=False resolves from the
    calling module's location, so a bare chdir isn't enough to redirect it.)
    """
    import importlib
    import os

    sentinel = "FVC_TEST_DOTENV_SENTINEL"
    env_file = tmp_path / ".env"
    env_file.write_text(f"{sentinel}=loaded-by-dotenv\n")

    monkeypatch.delenv(sentinel, raising=False)
    # find_dotenv is imported into dotenv.main (where load_dotenv resolves the
    # path), so patch it there, not on the dotenv package re-export.
    monkeypatch.setattr("dotenv.main.find_dotenv", lambda *a, **kw: str(env_file))

    import app.main as main_module

    importlib.reload(main_module)

    value = os.environ.get(sentinel)
    assert value == "loaded-by-dotenv", (
        "app.main did not load .env into os.environ at import "
        "(load_dotenv() missing or not finding the file)"
    )


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
