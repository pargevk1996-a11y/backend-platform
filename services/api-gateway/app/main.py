from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.health import router as health_router
from app.api.v1.proxy import router as proxy_router
from app.core.config import get_settings
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.validation import sanitize_validation_errors
from app.exceptions.base import AppException
from app.lifecycle import lifespan
from app.schemas.common import ErrorResponse

LOGGER = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="api-gateway",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "Idempotency-Key",
        "X-CSRF-Token",
    ],
)

app.mount("/ui", StaticFiles(directory="app/static", html=True), name="ui")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/")


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    payload = ErrorResponse(error_code=exc.error_code, message=exc.message, request_id=request_id)
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


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
app.include_router(proxy_router, prefix="/v1")
