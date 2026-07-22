"""FastAPI application factory and entry point for the local backend.

Security posture:
  * Binds to 127.0.0.1 only (never 0.0.0.0).
  * Every route except ``/health`` requires the session token in the
    ``X-LensTrace-Token`` header, compared in constant time.
  * CORS is restricted to loopback origins used by the Vite dev server and the
    packaged Electron app (``app://`` / ``file://``).
"""

from __future__ import annotations

import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from backend.api import (
    routes_bots,
    routes_config,
    routes_delivery,
    routes_files,
    routes_metadata,
    routes_presets,
)
from backend.config import get_settings
from backend.logging_config import configure_logging, get_logger
from core.exceptions import LensTraceError

logger = get_logger(__name__)


def verify_token(x_lenstrace_token: str = Header(default="")) -> None:
    """Constant-time check of the per-session token on every protected route."""
    expected = get_settings().session_token
    if not secrets.compare_digest(x_lenstrace_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing session token.",
        )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="LensTrace Studio Local API",
        version="0.1.0",
        description="Local-only metadata engine API for the desktop app.",
    )

    # The Vite dev server's port is not fixed (vite.config.ts sets
    # strictPort: false), so it may land on 5174+ if 5173 is already taken by
    # another project. Match any loopback origin/port instead of hardcoding
    # one, plus the app://file:// schemes used by a packaged Electron build.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^(http://(127\.0\.0\.1|localhost):\d+|app://.*|file://.*)$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        """Unauthenticated liveness probe used by the launcher."""
        return {"status": "ok", "service": "lenstrace-backend"}

    protected = [Depends(verify_token)]
    app.include_router(routes_files.router, dependencies=protected)
    app.include_router(routes_metadata.router, dependencies=protected)
    app.include_router(routes_presets.router, dependencies=protected)
    app.include_router(routes_delivery.router, dependencies=protected)
    app.include_router(routes_bots.router, dependencies=protected)
    app.include_router(routes_config.router, dependencies=protected)

    @app.exception_handler(LensTraceError)
    async def _domain_error_handler(_request, exc: LensTraceError):  # noqa: ANN001
        from fastapi.responses import JSONResponse

        logger.warning("Domain error: %s", exc)
        return JSONResponse(status_code=400, content={"error": exc.user_message})

    @app.on_event("startup")
    def _on_startup() -> None:
        # Only starts bots the user explicitly marked auto-start AND configured.
        from backend.services.bot_supervisor import get_supervisor

        try:
            get_supervisor().start_auto_start_bots()
        except Exception:  # noqa: BLE001 - never block startup on bot issues
            logger.warning("Auto-start of bots skipped due to an error.")

    @app.on_event("shutdown")
    def _on_shutdown() -> None:
        # Stop child bot processes so none are orphaned when LensTrace exits.
        from backend.services import settings_service
        from backend.services.bot_supervisor import get_supervisor

        if settings_service.get_config().lifecycle.stop_bots_on_exit:
            get_supervisor().shutdown_all()

    logger.info("Backend initialised (host=%s port=%s)", settings.host, settings.port)
    return app


app = create_app()


def run() -> None:
    """Run the backend with uvicorn using the configured host/port."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    run()
