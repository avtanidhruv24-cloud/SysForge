"""
SysForge — FastAPI application factory.

This module creates and configures the FastAPI app instance.  Import
``app`` from here to run with uvicorn or to use in tests via
``TestClient``.

Usage (development)::

    cd backend
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

Architecture notes
------------------
- All routes live under the versioned prefix ``/api/v1/``.
- A bare ``GET /health`` is also exposed for infrastructure probes
  (load balancers, Replit health checks) that do not know the versioned path.
- CORS origins are read from ``settings.cors_origins`` (env-configurable).
- All ``SysForgeError`` exceptions are caught globally and converted to
  the ``ErrorResponse`` JSON envelope.
- Unhandled ``RequestValidationError`` (Pydantic validation failure) is
  also caught and reformatted for consistency.
- Unhandled exceptions return a generic 500 so internal details never leak.
"""

from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.api.routes import health as health_router
from app.api.routes import analysis as analysis_router
from app.core.config import settings
from app.core.errors import (
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    ErrorSeverity,
    SysForgeError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """
    Build and return the configured FastAPI application.

    Separating construction into a factory makes the app easy to
    instantiate with different settings in tests.
    """
    application = FastAPI(
        title=settings.app_title,
        description=settings.app_description,
        version=settings.app_version,
        # Disable automatic /docs redirect so the versioned prefix is clean
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )

    _add_cors(application)
    _add_exception_handlers(application)
    _add_routers(application)

    return application


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


def _add_cors(app: FastAPI) -> None:
    """Configure Cross-Origin Resource Sharing."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


def _add_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    @app.exception_handler(SysForgeError)
    async def sysforge_error_handler(
        request: Request, exc: SysForgeError
    ) -> JSONResponse:
        """Convert any ``SysForgeError`` to the standard error envelope."""
        logger.warning(
            "SysForgeError [%s] on %s %s: %s",
            exc.code,
            request.method,
            request.url.path,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=exc.to_response().model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Reformat Pydantic validation errors as ``ErrorResponse``."""
        # Collect all field errors into a single human-readable message
        field_messages = []
        for error in exc.errors():
            loc = " → ".join(str(p) for p in error.get("loc", []))
            msg = error.get("msg", "invalid value")
            field_messages.append(f"{loc}: {msg}" if loc else msg)

        message = "; ".join(field_messages) if field_messages else "Invalid request."

        # Serialise validation errors safely — exc.errors() may contain
        # non-serialisable objects (e.g. ValueError in the 'ctx' field).
        safe_errors = []
        for err in exc.errors():
            safe_err = {
                "loc": [str(p) for p in err.get("loc", [])],
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
            safe_errors.append(safe_err)

        detail = ErrorDetail(
            code=ErrorCode.INVALID_REQUEST,
            message=message,
            severity=ErrorSeverity.ERROR,
            details={"validation_errors": safe_errors},
        )
        logger.warning(
            "Validation error on %s %s: %s",
            request.method,
            request.url.path,
            message,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(error=detail).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all handler — never leak internal details in production."""
        if settings.is_development:
            # In dev mode include the traceback for easier debugging
            tb = traceback.format_exc()
            logger.error("Unhandled exception on %s %s:\n%s", request.method, request.url.path, tb)
            message = f"{type(exc).__name__}: {exc}"
        else:
            logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
            message = "An internal server error occurred."

        detail = ErrorDetail(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            severity=ErrorSeverity.ERROR,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(error=detail).model_dump(),
        )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------


def _add_routers(app: FastAPI) -> None:
    """Mount all API routers."""

    # Versioned API routes — primary contract with the frontend
    app.include_router(
        health_router.router,
        prefix=settings.api_prefix,
        tags=["health"],
    )
    app.include_router(
        analysis_router.router,
        prefix=settings.api_prefix,
        tags=["analysis"],
    )

    # Bare /health for infrastructure probes (no version prefix)
    app.include_router(
        health_router.router,
        prefix="",
        tags=["health"],
        include_in_schema=False,   # hide from OpenAPI docs to avoid duplication
    )


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app: FastAPI = create_app()


# ---------------------------------------------------------------------------
# Startup / shutdown events
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def _on_startup() -> None:
    logger.info(
        "SysForge backend starting — env=%s host=%s port=%s",
        settings.app_env,
        settings.host,
        settings.port,
    )
    logger.info("CORS origins: %s", settings.cors_origins)
    logger.info("API prefix: %s", settings.api_prefix)


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    logger.info("SysForge backend shutting down.")
