from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings


class VoicePluginSettings(BaseSettings):
    home_dir: Path = Path.home() / ".amplifier-voice"

    model_config = {"env_prefix": "VOICE_PLUGIN_"}


def get_voice_config() -> dict[str, Any]:
    """Load voice config from environment, with safe defaults."""
    return {
        "voice": os.environ.get("AMPLIFIER_VOICE_VOICE", "ash"),
        "model": os.environ.get("AMPLIFIER_VOICE_MODEL", "gpt-4o-realtime-preview"),
        "instructions": os.environ.get("AMPLIFIER_VOICE_INSTRUCTIONS", ""),
        "assistant_name": os.environ.get(
            "AMPLIFIER_VOICE_ASSISTANT_NAME", "Amplifier"
        ),
    }
