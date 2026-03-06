from fastapi import FastAPI
from fastapi.routing import APIRoute, APIRouter


def test_create_router_returns_api_router():
    from voice_plugin import create_router

    app = FastAPI()
    app.state.session_manager = None
    app.state.event_bus = None
    app.state.bundle_registry = None
    app.state.settings = None
    router = create_router(app.state)
    assert isinstance(router, APIRouter)


def test_plugin_routes_registered():
    from voice_plugin import create_router

    app = FastAPI()
    app.state.session_manager = None
    app.state.event_bus = None
    app.state.bundle_registry = None
    app.state.settings = None
    router = create_router(app.state)
    paths = [r.path for r in router.routes if isinstance(r, APIRoute)]
    assert "/voice/" in paths or any("/voice" in p for p in paths)
