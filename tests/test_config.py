import pytest

from app.config import ElevenLabsSTTSettings, get_elevenlabs_api_key


def test_get_api_key_returns_value(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key-123")
    assert get_elevenlabs_api_key() == "test-key-123"


def test_get_api_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        get_elevenlabs_api_key()


def test_settings_defaults_model_id():
    settings = ElevenLabsSTTSettings(api_key="k")
    assert settings.model_id == "scribe_v2_realtime"
    assert settings.api_key == "k"
