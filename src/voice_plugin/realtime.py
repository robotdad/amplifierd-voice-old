"""OpenAI Realtime GA API client for voice sessions.

Provides two functions used by the voice plugin:
  - create_client_secret: Creates an ephemeral token via /client_secrets
  - exchange_sdp: Exchanges WebRTC SDP offer/answer via /calls
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import HTTPException

OPENAI_REALTIME_BASE = "https://api.openai.com/v1/realtime"
CLIENT_SECRETS_ENDPOINT = f"{OPENAI_REALTIME_BASE}/client_secrets"
SDP_EXCHANGE_ENDPOINT = f"{OPENAI_REALTIME_BASE}/calls"


@dataclass
class VoiceConfig:
    """Configuration for a voice session."""

    model: str
    voice: str
    instructions: str
    tools: list[dict[str, Any]] = field(default_factory=list)
    openai_api_key: str = ""


async def create_client_secret(config: VoiceConfig) -> str:
    """Create an ephemeral client secret via the GA Realtime API.

    Returns the ephemeral token string (e.g. 'ek_...').
    """
    headers = {
        "Authorization": f"Bearer {config.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "session": {
            "type": "realtime",
            "model": config.model,
            "instructions": config.instructions,
            "tools": config.tools,
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            CLIENT_SECRETS_ENDPOINT,
            json=payload,
            headers=headers,
        )

    if resp.is_error:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()
    return data["value"]


async def exchange_sdp(sdp_offer: str, ephemeral_token: str, model: str) -> str:
    """Exchange WebRTC SDP offer for an answer via the GA Realtime API."""
    headers = {
        "Authorization": f"Bearer {ephemeral_token}",
        "Content-Type": "application/sdp",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            SDP_EXCHANGE_ENDPOINT,
            content=sdp_offer,
            headers=headers,
            params={"model": model},
        )

    if resp.is_error:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return resp.text
