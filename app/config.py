from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ElevenLabsSTTSettings:
    api_key: str
    model_id: str = "scribe_v2_realtime"


def get_elevenlabs_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not set. Copy .env.example to .env and "
            "add your ElevenLabs API key."
        )
    return key


@dataclass(frozen=True)
class OpenAICompatibleSettings:
    api_key: str
    base_url: str
    model: str


def get_openai_compatible_settings() -> OpenAICompatibleSettings:
    api_key = os.environ.get("OPENAI_COMPATIBLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_COMPATIBLE_API_KEY is not set. Copy .env.example to .env "
            "and add your OpenAI-compatible API key."
        )
    base_url = os.environ.get("OPENAI_COMPATIBLE_BASE_URL")
    if not base_url:
        raise RuntimeError(
            "OPENAI_COMPATIBLE_BASE_URL is not set. Copy .env.example to .env "
            "and add your endpoint URL."
        )
    model = os.environ.get("OPENAI_COMPATIBLE_MODEL")
    if not model:
        raise RuntimeError(
            "OPENAI_COMPATIBLE_MODEL is not set. Copy .env.example to .env "
            "and add the model name."
        )
    return OpenAICompatibleSettings(api_key=api_key, base_url=base_url, model=model)


@dataclass(frozen=True)
class ElevenLabsTTSSettings:
    api_key: str
    voice_id: str
    model_id: str = "eleven_multilingual_v2"


def get_elevenlabs_tts_settings() -> ElevenLabsTTSSettings:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not set. Copy .env.example to .env "
            "and add your ElevenLabs API key."
        )
    voice_id = os.environ.get("ELEVENLABS_TTS_VOICE_ID")
    if not voice_id:
        raise RuntimeError(
            "ELEVENLABS_TTS_VOICE_ID is not set. Copy .env.example to .env "
            "and add an ElevenLabs voice ID for TTS."
        )
    model_id = os.environ.get("ELEVENLABS_TTS_MODEL_ID", "eleven_multilingual_v2")
    return ElevenLabsTTSSettings(api_key=api_key, voice_id=voice_id, model_id=model_id)
