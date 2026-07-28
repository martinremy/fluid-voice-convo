from __future__ import annotations

import pytest

from app.config import (
    ElevenLabsSTTSettings,
    get_elevenlabs_api_key,
    get_elevenlabs_tts_settings,
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


def test_tts_settings_returns_values(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVENLABS_TTS_VOICE_ID", "voice-123")
    monkeypatch.setenv("ELEVENLABS_TTS_MODEL_ID", "eleven_v3")
    settings = get_elevenlabs_tts_settings()
    assert settings.api_key == "sk-test"
    assert settings.voice_id == "voice-123"
    assert settings.model_id == "eleven_v3"


def test_tts_settings_defaults_model_id(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVENLABS_TTS_VOICE_ID", "voice-123")
    monkeypatch.delenv("ELEVENLABS_TTS_MODEL_ID", raising=False)
    settings = get_elevenlabs_tts_settings()
    assert settings.model_id == "eleven_multilingual_v2"


def test_tts_settings_raises_on_missing_voice_id(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    monkeypatch.delenv("ELEVENLABS_TTS_VOICE_ID", raising=False)
    with pytest.raises(RuntimeError, match="ELEVENLABS_TTS_VOICE_ID"):
        get_elevenlabs_tts_settings()


def test_tts_settings_raises_on_missing_api_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("ELEVENLABS_TTS_VOICE_ID", "voice-123")
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        get_elevenlabs_tts_settings()
