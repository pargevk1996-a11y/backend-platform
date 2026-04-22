from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.health import router as health_router
from app.core.config import get_settings
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.validation import sanitize_validation_errors
from app.schemas.common import ErrorResponse

LOGGER = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="notification-service",
    version="0.1.0",
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    payload = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        request_id=request_id,
    )
    LOGGER.info("validation_error", extra={"errors": sanitize_validation_errors(exc.errors())})
    return JSONResponse(status_code=422, content=payload.model_dump())


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    payload = ErrorResponse(
        error_code="HTTP_ERROR",
        message=str(exc.detail),
        request_id=request_id,
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    LOGGER.exception("unhandled_exception")
    payload = ErrorResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message="Internal server error",
        request_id=request_id,
    )
    return JSONResponse(status_code=500, content=payload.model_dump())


app.include_router(health_router, prefix="/v1")
