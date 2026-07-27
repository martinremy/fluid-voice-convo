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
