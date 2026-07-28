import pytest

from app.config import (
    ElevenLabsSTTSettings,
    get_elevenlabs_api_key,
    get_openai_compatible_settings,
)


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


def test_openai_settings_returns_values(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "gpt-test")
    settings = get_openai_compatible_settings()
    assert settings.api_key == "sk-test"
    assert settings.base_url == "https://api.example.com/v1"
    assert settings.model == "gpt-test"


def test_openai_settings_raises_on_missing_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "gpt-test")
    with pytest.raises(RuntimeError, match="OPENAI_COMPATIBLE_API_KEY"):
        get_openai_compatible_settings()


def test_openai_settings_raises_on_missing_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_COMPATIBLE_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "gpt-test")
    with pytest.raises(RuntimeError, match="OPENAI_COMPATIBLE_BASE_URL"):
        get_openai_compatible_settings()


def test_openai_settings_raises_on_missing_model(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://api.example.com/v1")
    monkeypatch.delenv("OPENAI_COMPATIBLE_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_COMPATIBLE_MODEL"):
        get_openai_compatible_settings()
