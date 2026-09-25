"""FastAPI application: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.api.middleware.body_guard import BodyGuardMiddleware
from app.api.middleware.request_context import RequestContextMiddleware
from app.api.routes import health
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json, settings.service_name)

    app = FastAPI(title="Football Assistant Retrieval", version=settings.version, redoc_url=None)
    app.state.settings = settings

    register_error_handlers(app, type_base_url=settings.error_type_base_url)
    # Added innermost first: the last one added runs first.
    app.add_middleware(
        BodyGuardMiddleware,
        max_body_bytes=settings.max_body_bytes,
        large_paths={"/index/upsert": settings.max_upsert_body_bytes},
        type_base_url=settings.error_type_base_url,
    )
    app.add_middleware(RequestContextMiddleware, type_base_url=settings.error_type_base_url)

    app.include_router(health.router)
    return app


def __getattr__(name: str) -> FastAPI:
    # `app.main:app` is built on first access so importing this module has no side effects.
    if name == "app":
        application = create_app()
        globals()["app"] = application
        return application
    raise AttributeError(name)
