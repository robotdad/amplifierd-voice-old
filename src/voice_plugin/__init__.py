from __future__ import annotations

from typing import Any

from fastapi import APIRouter


def create_router(state: Any) -> APIRouter:
    """Plugin entry point. Called by amplifierd plugin discovery."""
    from voice_plugin.config import VoicePluginSettings
    from voice_plugin.routes import (
        create_session_routes,
        create_signaling_routes,
        create_static_routes,
        create_tool_routes,
    )

    settings = VoicePluginSettings()
    settings.home_dir.mkdir(parents=True, exist_ok=True)

    # Extract sessions_dir from amplifierd settings (may be None)
    sessions_dir = getattr(
        getattr(state, "settings", None), "sessions_dir", None
    )

    router = APIRouter()

    @router.get("/voice/health", tags=["voice"])
    async def voice_health():
        return {"status": "ok", "plugin": "voice"}

    router.include_router(
        create_static_routes()
    )
    router.include_router(
        create_signaling_routes(settings)
    )
    router.include_router(
        create_session_routes(
            state=state,
            settings=settings,
            sessions_dir=sessions_dir,
        )
    )
    router.include_router(
        create_tool_routes(state=state)
    )
    return router
